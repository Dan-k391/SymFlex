"""Vectors and matrices: constructors, the `.` and `&x` operators, and first versions of the
LinearAlgebra / VectorCalculus exports used in the course."""
from __future__ import annotations

import sympy as sp

from ..errors import MapleError
from ..printer import lprint
from ..values import MEquation, MList, MMatrix, MVector, Procedure, deep_map, seq_items
from . import Library

lib = Library()
builtin = lib.builtin

LA, VC = "LinearAlgebra", "VectorCalculus"


def register(env):
    lib.register(env)


def _vec(v, what="Vector"):
    if isinstance(v, MVector):
        return v
    if isinstance(v, MList):
        return MVector(v.items)
    raise MapleError(f"invalid input: expected a {what}, received {lprint(v)}")


# ====================================================================== constructors
@builtin("Vector", sig="Vector([x1, x2, ...]) or Vector[row](...)", doc="Create a Vector.",
         indexed=True, options={"orientation": None, "datatype": None, "shape": None, "storage": None,
                                "attributes": None})
def m_Vector(ctx, *args, index=None, orientation=None, **opts):
    orient = str(index[0]) if index else (str(orientation) if orientation is not None else "column")
    if not args:
        return MVector([], orient)
    a = args[0]
    if isinstance(a, MList):
        return MVector(a.items, orient)
    if isinstance(a, MVector):
        return MVector(a.m, orient)
    if isinstance(a, sp.Integer):
        n = int(a)
        if len(args) > 1:
            init = args[1]
            if isinstance(init, Procedure):
                return MVector([ctx.apply(init, [sp.Integer(i)]) for i in range(1, n + 1)], orient)
            if isinstance(init, MList):
                items = list(init.items) + [sp.Integer(0)] * (n - len(init.items))
                return MVector(items[:n], orient)
            return MVector([init] * n, orient)
        return MVector([sp.Integer(0)] * n, orient)
    return MVector(list(seq_items(a)), orient)


@builtin("Matrix", sig="Matrix([[a, b], [c, d]]) or Matrix(m, n, f)", doc="Create a Matrix.",
         options={"datatype": None, "shape": None, "storage": None, "symbol": None})
def m_Matrix(ctx, *args, **opts):
    if not args:
        return MMatrix(sp.zeros(0, 0))
    a = args[0]
    if isinstance(a, MList):
        rows = list(a.items)
        if rows and all(isinstance(r, MList) for r in rows):
            return MMatrix([list(r.items) for r in rows])
        if rows and all(isinstance(r, MVector) for r in rows):
            return MMatrix(sp.Matrix.hstack(*[r.m if r.orient == "column" else r.m.T for r in rows]))
        return MMatrix([rows])
    if isinstance(a, MMatrix):
        return MMatrix(a.m)
    if isinstance(a, sp.Integer):
        r = int(a)
        c = int(args[1]) if len(args) > 1 and isinstance(args[1], sp.Integer) else r
        init = args[2] if len(args) > 2 else (args[1] if len(args) > 1 and
                                             not isinstance(args[1], sp.Integer) else None)
        if isinstance(init, Procedure):
            return MMatrix([[ctx.apply(init, [sp.Integer(i), sp.Integer(j)]) for j in range(1, c + 1)]
                            for i in range(1, r + 1)])
        if isinstance(init, MList):
            items = list(init.items)
            if items and isinstance(items[0], MList):
                return MMatrix([list(x.items) for x in items])
            flat = items + [sp.Integer(0)] * (r * c - len(items))
            return MMatrix([flat[i * c:(i + 1) * c] for i in range(r)])
        if init is not None:
            return MMatrix([[init] * c for _ in range(r)])
        return MMatrix(sp.zeros(r, c))
    raise MapleError(f"invalid input: Matrix received {lprint(a)}")


@lib.operator("<,>")
def angle_col(ctx, items):
    from ..evaluator import _angle_default
    return _angle_default(",", items)


@lib.operator("<|>")
def angle_row(ctx, items):
    from ..evaluator import _angle_default
    return _angle_default("|", items)


# ====================================================================== operators
def dot(a, b):
    if isinstance(a, MVector) and isinstance(b, MVector):
        if len(a.m) != len(b.m):
            raise MapleError("invalid input: vector dimensions do not match")
        if a.orient == "column" and b.orient == "row":
            return MMatrix(a.m * b.m)
        return sp.Add(*[x * y for x, y in zip(a.m, b.m)])
    if isinstance(a, MMatrix) and isinstance(b, MMatrix):
        m = a.m * b.m
        if isinstance(b, MVector) and b.orient == "column":
            return MVector(list(m), "column")
        if isinstance(a, MVector) and a.orient == "row":
            return MVector(list(m), "row")
        return MMatrix(m)
    if isinstance(a, MMatrix) or isinstance(b, MMatrix):
        s, m = (b, a) if isinstance(a, MMatrix) else (a, b)
        return m.map_leaves(lambda x: s * x)
    return a * b


@lib.operator(".")
def op_dot(ctx, a, b):
    return dot(a, b)


def cross(a, b):
    a, b = _vec(a), _vec(b)
    if len(a.m) != 3 or len(b.m) != 3:
        raise MapleError("invalid input: CrossProduct expects 3-D Vectors")
    x = sp.Matrix(list(a.m)).cross(sp.Matrix(list(b.m)))
    return MVector(list(x), a.orient)


@lib.operator("&x")
def op_cross(ctx, a, b):
    return cross(a, b)


@builtin("CrossProduct", package=[LA, VC], sig="CrossProduct(u, v)", doc="Cross product of 3-D vectors.")
def m_cross(ctx, a, b):
    return cross(a, b)


@builtin("&x", package=[LA, VC], sig="u &x v", doc="Cross product operator.")
def m_cross_op(ctx, a, b):
    return cross(a, b)


@builtin("DotProduct", package=[LA, VC], sig="DotProduct(u, v)", doc="Dot product.",
         options={"conjugate": None})
def m_dotp(ctx, a, b, conjugate=None):
    return dot(_vec(a), _vec(b))


@builtin("Transpose", package=LA, sig="Transpose(A)", doc="Transpose of a Matrix or Vector.")
def m_transpose(ctx, a):
    if isinstance(a, MVector):
        return MVector(a.m, "row" if a.orient == "column" else "column")
    return MMatrix(a.m.T)


@builtin("Determinant", package=LA, sig="Determinant(A)", doc="Determinant.")
def m_det(ctx, a, *opts):
    return a.m.det()


@builtin("MatrixInverse", package=LA, sig="MatrixInverse(A)", doc="Matrix inverse.")
def m_inverse(ctx, a, *opts):
    return MMatrix(a.m.inv())


@builtin("IdentityMatrix", package=LA, sig="IdentityMatrix(n)", doc="n x n identity matrix.")
def m_identity(ctx, n, m=None):
    return MMatrix(sp.eye(int(n), int(m) if m is not None else int(n)))


@builtin("Dimension", package=LA, sig="Dimension(A)", doc="Dimensions of a Matrix or Vector.")
def m_dimension(ctx, a):
    if isinstance(a, MVector):
        return sp.Integer(len(a.m))
    from ..values import ExprSeq
    return ExprSeq([sp.Integer(a.m.shape[0]), sp.Integer(a.m.shape[1])])


def _norm_vc(v):
    return sp.sqrt(sp.Add(*[x ** 2 for x in v.m]))


@builtin("Norm", package=VC, sig="Norm(v)", doc="Euclidean norm (VectorCalculus).")
def m_norm_vc(ctx, v, p=None):
    return _norm_vc(_vec(v))


@builtin("Norm", package=LA, sig="Norm(v, p)", doc="p-norm (default infinity).")
def m_norm_la(ctx, v, p=None):
    v = _vec(v)
    if p is None or p == sp.oo:
        return sp.Max(*[sp.Abs(x) for x in v.m])
    if p == 2 or str(p) == "Euclidean":
        return sp.sqrt(sp.Add(*[sp.Abs(x) ** 2 for x in v.m]))
    return sp.Add(*[sp.Abs(x) ** p for x in v.m]) ** (sp.Integer(1) / p)


@builtin("Normalize", package=VC, sig="Normalize(v)", doc="Unit vector in the direction of v.")
def m_normalize_vc(ctx, v):
    v = _vec(v)
    n = _norm_vc(v)
    return v.map_leaves(lambda x: x / n)


@builtin("Normalize", package=LA, sig="Normalize(v, p)", doc="Vector scaled to unit p-norm (default infinity).")
def m_normalize_la(ctx, v, p=None):
    n = m_norm_la(ctx, v, p)
    return _vec(v).map_leaves(lambda x: x / n)


@builtin("BasisFormat", package=VC, sig="BasisFormat(true|false)", doc="Choose how Vectors are displayed.")
def m_basisformat(ctx, flag=None):
    prev = ctx.settings.get("BasisFormat", sp.true)
    if flag is not None:
        ctx.settings["BasisFormat"] = flag
    return prev


@builtin("dot", sig="dot(u, v)", doc="Dot product of two vectors.")
def m_dot_global(ctx, a, b):
    return dot(_vec(a), _vec(b))


@builtin("magnitude", sig="magnitude(v)", doc="Euclidean length of a vector.")
def m_magnitude(ctx, v):
    return _norm_vc(_vec(v))
