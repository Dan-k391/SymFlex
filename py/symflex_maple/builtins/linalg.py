"""Vectors and matrices: constructors, rtable arithmetic (`+ - * / ^ .`, `&x`, indexing), and the
LinearAlgebra / VectorCalculus exports used in the course.

Maple semantics reproduced here:
* rtable entries are stored as built and are *not* re-evaluated when the rtable's name is looked
  up (`v;` still shows an entry name assigned since), but they are fully evaluated when the rtable
  takes part in arithmetic, is indexed, or is passed to LinearAlgebra/VectorCalculus functions and
  to `diff`, `simplify`, `map`, `collect`, `evalc` (not `eval`, `subs`, `evalf`).
* `+`, `-`, `.` (and LinearSolve, MatrixInverse, ...) switch to hardware floats (datatype float[8],
  every entry a float) when every operand entry is a number and at least one is a float;
  VectorCalculus also does this for scalar multiplication.
* `.` of two column Vectors conjugates the first one, except under VectorCalculus.
"""
from __future__ import annotations

import dataclasses
import functools

import mpmath
import sympy as sp

from ..errors import MapleError
from ..printer import lprint
from ..values import ExprSeq, MEquation, MList, MMatrix, MSet, MVector, Procedure, seq_items
from . import Library, is_true

lib = Library()
builtin = lib.builtin

LA, VC = "LinearAlgebra", "VectorCalculus"
HW_DIGITS = 15

# global functions that evaluate rtable entries before working on them (Maple maps over them)
_ENTRY_EVAL = ("diff", "simplify", "map", "collect", "evalc")


def register(env):
    lib.register(env)
    for name in _ENTRY_EVAL:
        p = env.functions.get(name)
        if p is not None:
            env.functions[name] = dataclasses.replace(p, fn=_entries_evaluated(p.fn))
    p = env.functions.get("solve")
    if p is not None:
        env.functions["solve"] = dataclasses.replace(p, fn=_solve_rtables(p.fn))


# ====================================================================== helpers
def _ev(ctx, v):
    """Full evaluation of an rtable's entries (or of a scalar)."""
    if isinstance(v, MMatrix):
        return _with_dtype(v.map_leaves(ctx.full_eval), _dtype(v))
    return ctx.full_eval(v) if isinstance(v, sp.Basic) else v


def _entries_evaluated(fn):
    @functools.wraps(fn)
    def wrapper(ctx, *args, **kw):
        return fn(ctx, *[_ev(ctx, a) if isinstance(a, MMatrix) else a for a in args], **kw)
    return wrapper


def _solve_rtables(fn):
    """solve(<..> = <..>) and solve(<..>) mean the set of entrywise equations."""
    @functools.wraps(fn)
    def wrapper(ctx, *args, **kw):
        if args:
            e = args[0]
            if isinstance(e, MEquation) and (isinstance(e.lhs, MMatrix) or isinstance(e.rhs, MMatrix)):
                e = op_sub(ctx, e.lhs, e.rhs)
            if isinstance(e, MMatrix):
                args = (MSet(x for x in _ev(ctx, e).m if x != 0), *args[1:])
        return fn(ctx, *args, **kw)
    return wrapper


def la_builtin(name, **kw):
    """@builtin whose rtable arguments arrive with their entries evaluated."""
    def deco(fn):
        builtin(name, **kw)(_entries_evaluated(fn))
        return fn
    return deco


def _vec(v, what="Vector"):
    if isinstance(v, MVector):
        return v
    if isinstance(v, MList):
        return MVector(v.items)
    raise MapleError(f"invalid input: expected a {what}, received {lprint(v)}")


def _mat(v, where):
    if isinstance(v, MMatrix) and not isinstance(v, MVector):
        return v
    raise MapleError(f"invalid input: {where} expects a Matrix, received {lprint(v)}", where=where)


def _square(a, where):
    a = _mat(a, where)
    if a.m.shape[0] != a.m.shape[1]:
        raise MapleError("matrix must be square", where=where)
    return a


def _like(m, like):
    """Wrap a SymPy matrix as the same kind of rtable as `like`."""
    if isinstance(like, MVector):
        return MVector(list(m), like.orient)
    return MMatrix(m)


def _vc(ctx):
    return VC in ctx.loaded


def _leaves(*vals):
    for v in vals:
        yield from (v.m if isinstance(v, MMatrix) else (v,))


def _dtype(v):
    return getattr(v, "datatype", "anything")


def _with_dtype(r, dtype):
    if dtype != "anything":
        r.datatype = dtype
    return r


def _is_hw(*vals):
    xs = list(_leaves(*vals))
    return all(isinstance(x, sp.Number) for x in xs) and any(x.is_Float for x in xs)


def _hw(v, dtype="float[8]"):
    """Convert to hardware floats (re-reading a float's decimal digits, as Maple does).
    15-digit SymPy Floats have a 53-bit mantissa, so their arithmetic rounds like doubles."""
    def f(x):
        return sp.Float(str(x) if x.is_Float else x, HW_DIGITS) if isinstance(x, sp.Number) else x
    if not isinstance(v, MMatrix):
        return f(v)
    return _with_dtype(v.map_leaves(f), dtype)


def _hw_op(op, *vals):
    """Apply op, in hardware floats when the operands call for it."""
    if _is_hw(*vals):
        return _hw(op(*[_hw(v) for v in vals]))
    return op(*vals)


def _dims(v):
    if isinstance(v, MVector):
        return f"Vector[{v.orient}](1 .. {len(v.m)})"
    return f"Matrix(1 .. {v.m.shape[0]},1 .. {v.m.shape[1]})"


def _same_shape(a, b):
    return isinstance(a, MVector) == isinstance(b, MVector) and a.m.shape == b.m.shape


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
    if isinstance(a, MMatrix):
        return MVector(list(_ev(ctx, a).m), orient)
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
            return MMatrix(sp.Matrix.hstack(*[_ev(ctx, r).m if r.orient == "column" else _ev(ctx, r).m.T
                                              for r in rows]))
        return MMatrix([rows])
    if isinstance(a, MMatrix):
        return MMatrix(_ev(ctx, a).m)
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
    return _angle_default(",", [_ev(ctx, x) for x in items])


@lib.operator("<|>")
def angle_row(ctx, items):
    from ..evaluator import _angle_default
    return _angle_default("|", [_ev(ctx, x) for x in items])


# ====================================================================== operators
@lib.operator("index")
def op_index(ctx, base, idx):
    from ..evaluator import _rtable_index
    return _ev(ctx, _rtable_index(base, idx))


def _add(ctx, a, b):
    if isinstance(a, MMatrix) and isinstance(b, MMatrix):
        if not _same_shape(a, b):
            raise MapleError(f"invalid input: dimensions do not match: {_dims(a)} cannot be added "
                             f"to {_dims(b)}", where="rtable/Sum")
        return _hw_op(lambda x, y: _like(x.m + y.m, x), a, b)
    s, m = (b, a) if isinstance(a, MMatrix) else (a, b)
    if s == 0:
        return m
    if isinstance(m, MVector):
        raise MapleError("a constant cannot be added to a Vector; use +~ for elementwise addition "
                         "instead of +")
    return MMatrix(m.m + s * sp.eye(*m.m.shape))


def _scale(ctx, s, m):
    """Scalar times rtable: hardware floats when the rtable has float entries (and, under
    VectorCalculus, also when only the scalar is a float)."""
    def mul(s, m):
        return m.map_leaves(lambda x: s * x)
    if isinstance(s, sp.Number) and (_is_hw(m) or _vc(ctx)):
        return _hw_op(mul, s, m)
    return mul(s, m)


def _scalar(v):
    return isinstance(v, sp.Basic)


@lib.operator("+")
def op_add(ctx, a, b):
    if not all(isinstance(x, MMatrix) or _scalar(x) for x in (a, b)):
        return NotImplemented
    return _add(ctx, _ev(ctx, a), _ev(ctx, b))


@lib.operator("-")
def op_sub(ctx, a, b):
    if not all(isinstance(x, MMatrix) or _scalar(x) for x in (a, b)):
        return NotImplemented
    a, b = _ev(ctx, a), _ev(ctx, b)
    return _add(ctx, a, _scale(ctx, sp.Integer(-1), b) if isinstance(b, MMatrix) else -b)


@lib.operator("*")
def op_mul(ctx, a, b):
    a, b = _ev(ctx, a), _ev(ctx, b)
    if isinstance(a, MMatrix) and isinstance(b, MMatrix):
        raise MapleError("use *~ for elementwise multiplication of Vectors or Matrices; use . (dot) "
                         "for Vector/Matrix multiplication", where="rtable/Product")
    s, m = (b, a) if isinstance(a, MMatrix) else (a, b)
    if not _scalar(s):
        return NotImplemented
    return _scale(ctx, s, m)


@lib.operator("/")
def op_div(ctx, a, b):
    a, b = _ev(ctx, a), _ev(ctx, b)
    if isinstance(b, MMatrix):
        if not _scalar(a):
            return NotImplemented
        return _scale(ctx, a, op_pow(ctx, b, sp.Integer(-1)))
    if not _scalar(b):
        return NotImplemented
    return _scale(ctx, sp.Integer(1) / b, a)


@lib.operator("^")
def op_pow(ctx, a, n):
    if not isinstance(a, MMatrix) or isinstance(n, MMatrix):
        return NotImplemented
    a = _ev(ctx, a)
    if isinstance(a, MVector):
        raise MapleError("exponentiation operation not defined for Vectors", where="rtable/Power")
    if n == 0:
        return sp.Integer(1)
    if not (isinstance(n, sp.Integer)):
        return NotImplemented
    a = _square(a, "rtable/Power")
    if n < 0:
        a = MMatrix(_inverse(a, "rtable/Power"))
    return _hw_op(lambda x: MMatrix(x.m ** abs(int(n))), a)


def _inverse(a, where):
    def inv(x):
        try:
            return MMatrix(x.m.inv())
        except (ValueError, ZeroDivisionError):
            raise MapleError("singular matrix", where=where) from None
    return _hw_op(inv, a).m


def dot(a, b, conj=True):
    """Maple's `.` / DotProduct / Multiply."""
    if isinstance(a, MVector) and isinstance(b, MVector):
        if len(a.m) != len(b.m):
            raise MapleError("vectors must have the same dimension", where="LinearAlgebra:-DotProduct")
        if a.orient == "column" and b.orient == "row":
            return _hw_op(lambda x, y: MMatrix(x.m * y.m), a, b)
        cj = conj and a.orient == "column"
        return _hw_op(lambda x, y: sp.Add(*[(sp.conjugate(p) if cj else p) * q
                                            for p, q in zip(x.m, y.m)]), a, b)
    if isinstance(a, MMatrix) and isinstance(b, MMatrix):
        if a.m.shape[1] != b.m.shape[0]:
            if isinstance(b, MVector):
                msg = (f"Vector dimension ({len(b.m)}) must be the same as the Matrix column "
                       f"dimension ({a.m.shape[1]})")
            else:
                msg = (f"first matrix column dimension ({a.m.shape[1]}) <> second matrix row "
                       f"dimension ({b.m.shape[0]})")
            raise MapleError(msg, where="LinearAlgebra:-Multiply")
        like = b if isinstance(b, MVector) else a if isinstance(a, MVector) else None
        return _hw_op(lambda x, y: _like(x.m * y.m, like), a, b)
    if isinstance(a, MMatrix) or isinstance(b, MMatrix):
        s, m = (b, a) if isinstance(a, MMatrix) else (a, b)
        return m.map_leaves(lambda x: s * x)
    return a * b


@lib.operator(".")
def op_dot(ctx, a, b):
    if not (isinstance(a, MMatrix) or isinstance(b, MMatrix)):
        return NotImplemented
    if not all(isinstance(x, MMatrix) or _scalar(x) for x in (a, b)):
        return NotImplemented
    return dot(_ev(ctx, a), _ev(ctx, b), conj=not _vc(ctx))


def cross(a, b, where="LinearAlgebra:-&x"):
    for k, v in (("1st", a), ("2nd", b)):
        if not (isinstance(v, MVector) and len(v.m) == 3):
            got = f"Vector({len(v.m)}, [...], datatype = anything)" if isinstance(v, MVector) else lprint(v)
            raise MapleError(f"invalid input: {where} expects its {k} argument, V{k[0]}, to be of type "
                             f"Vector(3) but received {got}", where=where)
    def cr(a, b):
        return MVector(list(sp.Matrix(list(a.m)).cross(sp.Matrix(list(b.m)))), a.orient)
    if "float[8]" in (_dtype(a), _dtype(b)) and _is_hw(a, b):
        return _hw(cr(_hw(a), _hw(b)), "anything")
    return cr(a, b)


@la_builtin("CrossProduct", package=[LA, VC], sig="CrossProduct(u, v)", doc="Cross product of 3-D vectors.")
def m_cross(ctx, a, b):
    return cross(a, b, "LinearAlgebra:-CrossProduct")


@la_builtin("&x", package=[LA, VC], sig="u &x v", doc="Cross product operator.")
def m_cross_op(ctx, a, b):
    return cross(a, b)


@la_builtin("DotProduct", package=LA, sig="DotProduct(u, v)", doc="Dot product (conjugates u).",
            options={"conjugate": None})
def m_dotp(ctx, a, b, conjugate=None):
    return dot(_vec(a), _vec(b), conj=conjugate is None or is_true(conjugate))


@la_builtin("DotProduct", package=VC, sig="DotProduct(u, v)", doc="Dot product.")
def m_dotp_vc(ctx, a, b):
    return dot(_vec(a), _vec(b), conj=False)


@la_builtin("Multiply", package=LA, sig="Multiply(A, B)", doc="Matrix/Vector product A . B.")
def m_multiply(ctx, a, b):
    return dot(a, b)


@la_builtin("Add", package=LA, sig="Add(A, B, c1, c2)", doc="c1*A + c2*B.")
def m_add(ctx, a, b, c1=sp.Integer(1), c2=sp.Integer(1)):
    return _add(ctx, _scale(ctx, c1, a), _scale(ctx, c2, b))


@la_builtin("ScalarMultiply", package=LA, sig="ScalarMultiply(A, s)", doc="s*A.")
def m_scalarmul(ctx, a, s=sp.Integer(1)):
    return _scale(ctx, s, a)


# ====================================================================== LinearAlgebra
@la_builtin("Transpose", package=LA, sig="Transpose(A)", doc="Transpose of a Matrix or Vector.")
def m_transpose(ctx, a):
    if isinstance(a, MVector):
        return _with_dtype(MVector(a.m, "row" if a.orient == "column" else "column"), _dtype(a))
    return _with_dtype(MMatrix(_mat(a, "LinearAlgebra:-Transpose").m.T), _dtype(a))


@la_builtin("HermitianTranspose", package=LA, sig="HermitianTranspose(A)", doc="Conjugate transpose.")
def m_htranspose(ctx, a):
    return m_transpose(ctx, a).map_leaves(sp.conjugate)


@la_builtin("Determinant", package=LA, sig="Determinant(A)", doc="Determinant.")
def m_det(ctx, a, *opts):
    a = _square(a, "LinearAlgebra:-Determinant")
    return _hw_op(lambda x: x.m.det(), a)


@la_builtin("MatrixInverse", package=LA, sig="MatrixInverse(A)", doc="Matrix inverse.")
def m_inverse(ctx, a, *opts):
    return MMatrix(_inverse(_square(a, "MatrixInverse"), "MatrixInverse"))


@la_builtin("Trace", package=LA, sig="Trace(A)", doc="Sum of the diagonal entries.")
def m_trace(ctx, a):
    return _hw_op(lambda x: x.m.trace(), _square(a, "LinearAlgebra:-Trace"))


@la_builtin("Rank", package=LA, sig="Rank(A)", doc="Rank of a Matrix.")
def m_rank(ctx, a):
    return sp.Integer(_mat(a, "LinearAlgebra:-Rank").m.rank(simplify=True))


@la_builtin("ReducedRowEchelonForm", package=LA, sig="ReducedRowEchelonForm(A)",
            doc="Reduced row echelon form.")
def m_rref(ctx, a):
    return MMatrix(_mat(a, "LinearAlgebra:-ReducedRowEchelonForm").m.rref(simplify=True)[0])


@la_builtin("NullSpace", package=LA, sig="NullSpace(A)", doc="Basis of the null space (a set of Vectors).")
def m_nullspace(ctx, a):
    return MSet(MVector(list(v)) for v in _mat(a, "LinearAlgebra:-NullSpace").m.nullspace(simplify=True))


@la_builtin("CharacteristicPolynomial", package=LA, sig="CharacteristicPolynomial(A, lambda)",
            doc="det(lambda*I - A).")
def m_charpoly(ctx, a, lam):
    a = _square(a, "LinearAlgebra:-CharacteristicPolynomial")
    return sp.expand((lam * sp.eye(a.m.shape[0]) - a.m).det())


def _from_mp(z):
    re, im = sp.Float(z.real, HW_DIGITS), sp.Float(z.imag, HW_DIGITS)
    return re if abs(z.imag) <= 1e-13 * max(1, abs(z)) else re + sp.I * im


def _eig_hw(a, vectors=False):
    with mpmath.workdps(HW_DIGITS):
        return mpmath.eig(mpmath.matrix(_hw(a).m.tolist()), left=False, right=vectors)


def _eigenvalues(ctx, a):
    """Eigenvalues with multiplicity, in the order solve gives the roots of the characteristic
    polynomial (as Maple does); for a float Matrix in QR-algorithm order, which matches LAPACK's
    for 2 x 2 matrices, with each conjugate pair listed +I first."""
    if _is_hw(a):
        vals = [_from_mp(z) for z in _eig_hw(a)]
        for i in range(len(vals) - 1):
            z, w = complex(vals[i]), complex(vals[i + 1])
            if z.imag < 0 and abs(w - z.conjugate()) <= 1e-12 * abs(z):
                vals[i], vals[i + 1] = vals[i + 1], vals[i]
        return vals
    lam = sp.Dummy("lambda")
    return list(seq_items(ctx.call("solve", m_charpoly(ctx, a, lam), lam)))


@la_builtin("Eigenvalues", package=LA, sig="Eigenvalues(A)", doc="Eigenvalues as a column Vector.",
            options={"output": None, "implicit": None})
def m_eigenvalues(ctx, a, output=None, implicit=None):
    vals = _eigenvalues(ctx, _square(a, "LinearAlgebra:-Eigenvalues"))
    if output is not None and str(output) == "list":
        return MList(vals)
    return _with_dtype(MVector(vals), "complex[8]" if _is_hw(a) else "anything")


@la_builtin("Eigenvectors", package=LA, sig="Eigenvectors(A)",
            doc="Eigenvalues (Vector) and eigenvectors (Matrix columns), in matching order.")
def m_eigenvectors(ctx, a, *opts):
    a = _square(a, "LinearAlgebra:-Eigenvectors")
    n = a.m.shape[0]
    vals = _eigenvalues(ctx, a)
    if _is_hw(a):
        ev, er = _eig_hw(a, vectors=True)
        cols, free = [], list(range(n))
        for v in vals:
            j = min(free, key=lambda k: abs(ev[k] - complex(v)))
            free.remove(j)
            col = [er[i, j] for i in range(n)]
            nrm = mpmath.sqrt(sum(abs(x) ** 2 for x in col))
            cols.append([_from_mp(x / nrm) for x in col])
        return ExprSeq([_with_dtype(MVector(vals), "complex[8]"),
                        _with_dtype(MMatrix(sp.Matrix(cols).T), "complex[8]")])
    cols, done = [], []
    for v in vals:
        if any(sp.simplify(v - d) == 0 for d in done):
            continue
        done.append(v)
        basis = (a.m - v * sp.eye(n)).nullspace(simplify=True)
        mult = sum(1 for w in vals if sp.simplify(w - v) == 0)
        basis = [b / b[max(i for i in range(n) if b[i] != 0)] for b in basis]
        cols += [list(b) for b in basis[:mult]] + [[0] * n] * (mult - len(basis))
    return ExprSeq([MVector(vals), MMatrix(sp.Matrix(cols).T)])


@la_builtin("LinearSolve", package=LA, sig="LinearSolve(A, b)", doc="Solve A . x = b.",
            options={"free": None, "method": None})
def m_linsolve(ctx, a, b=None, free=None, method=None):
    where = "LinearAlgebra:-LinearSolve"
    a = _mat(a, where)
    if b is None:   # augmented Matrix
        a, b = MMatrix(a.m[:, :-1]), MVector(list(a.m[:, -1]))
    if a.m.shape[0] != b.m.shape[0]:
        raise MapleError("number of rows of the Matrix and the Vector must agree", where=where)
    hw = _is_hw(a, b)
    if hw:
        a, b = _hw(a), _hw(b)
    try:
        sol, params, free_cols = a.m.gauss_jordan_solve(b.m, freevar=True)
    except ValueError:
        raise MapleError("inconsistent system", where=where) from None
    t = sp.IndexedBase(str(free) if free is not None else "_t")
    sol = sol.subs({p: t[j + 1] for p, j in zip(params, free_cols)})
    sol = sol.applyfunc(sp.simplify) if not hw else sol
    r = MVector(list(sol)) if isinstance(b, MVector) else MMatrix(sol)
    return _hw(r) if hw else r


@la_builtin("GenerateEquations", package=LA, sig="GenerateEquations(A, vars, b)",
            doc="The equations A . vars = b as a list.")
def m_geneqs(ctx, a, xs, b=None):
    xs = list(seq_items(xs)) if not isinstance(xs, MList) else xs.items
    lhs = a.m * sp.Matrix(xs)
    rhs = b.m if b is not None else sp.zeros(lhs.shape[0], 1)
    return MList(MEquation(l, r) for l, r in zip(lhs, rhs))


@la_builtin("GenerateMatrix", package=LA, sig="GenerateMatrix(eqs, vars)",
            doc="Coefficient Matrix and right-hand side Vector of linear equations.")
def m_genmatrix(ctx, eqs, xs):
    def items(v):
        return v.items if isinstance(v, (MList, MSet)) else list(seq_items(v))
    exprs = [e.lhs - e.rhs if isinstance(e, MEquation) else e for e in items(eqs)]
    A, b = sp.linear_eq_to_matrix(exprs, items(xs))
    return ExprSeq([MMatrix(A), MVector(list(b))])


@builtin("IdentityMatrix", package=LA, sig="IdentityMatrix(n)", doc="n x n identity matrix.")
def m_identity(ctx, n, m=None):
    return MMatrix(sp.eye(int(n), int(m) if m is not None else int(n)))


@builtin("ZeroMatrix", package=LA, sig="ZeroMatrix(n, m)", doc="n x m zero Matrix.")
def m_zeromatrix(ctx, n, m=None):
    return MMatrix(sp.zeros(int(n), int(m) if m is not None else int(n)))


@builtin("ZeroVector", package=LA, sig="ZeroVector(n)", doc="Zero Vector of dimension n.", indexed=True)
def m_zerovector(ctx, n, index=None):
    return MVector([sp.Integer(0)] * int(n), str(index[0]) if index else "column")


@builtin("DiagonalMatrix", package=LA, sig="DiagonalMatrix([d1, d2, ...])", doc="Diagonal Matrix.")
def m_diagonal(ctx, d, *opts):
    return MMatrix(sp.diag(*(d.m if isinstance(d, MMatrix) else seq_items(d) if not isinstance(d, MList)
                             else d.items)))


@la_builtin("Dimension", package=LA, sig="Dimension(A)", doc="Dimensions of a Matrix or Vector.")
def m_dimension(ctx, a):
    if isinstance(a, MVector):
        return sp.Integer(len(a.m))
    return ExprSeq([sp.Integer(a.m.shape[0]), sp.Integer(a.m.shape[1])])


@la_builtin("RowDimension", package=LA, sig="RowDimension(A)", doc="Number of rows.")
def m_rowdim(ctx, a):
    return sp.Integer(a.m.shape[0])


@la_builtin("ColumnDimension", package=LA, sig="ColumnDimension(A)", doc="Number of columns.")
def m_coldim(ctx, a):
    return sp.Integer(a.m.shape[1])


@la_builtin("Column", package=LA, sig="Column(A, j)", doc="Column j of A as a column Vector.")
def m_column(ctx, a, j):
    return MVector(list(a.m.col(int(j) - 1 if int(j) > 0 else int(j))))


@la_builtin("Row", package=LA, sig="Row(A, i)", doc="Row i of A as a row Vector.")
def m_row(ctx, a, i):
    return MVector(list(a.m.row(int(i) - 1 if int(i) > 0 else int(i))), "row")


# ---------------------------------------------------------------- norms
def _norm_vc(v):
    return sp.sqrt(sp.Add(*[x ** 2 for x in v.m]))


@la_builtin("Norm", package=VC, sig="Norm(v)", doc="Euclidean norm (VectorCalculus).")
def m_norm_vc(ctx, v, p=None):
    if p is not None:
        return m_norm_la(ctx, v, p)
    return _norm_vc(_vec(v))


def _pnorm(xs, p):
    xs = [sp.Abs(x) for x in xs]
    if p is None or p == sp.oo or str(p) == "infinity":
        return sp.Max(*xs)
    if str(p) in ("Euclidean", "Frobenius"):
        p = sp.Integer(2)
    if p == 1:
        return sp.Add(*xs)
    if p == 2:
        return sp.sqrt(sp.Add(*[x ** 2 for x in xs]))
    return sp.Add(*[x ** p for x in xs]) ** (sp.Integer(1) / p)


@la_builtin("Norm", package=LA, sig="Norm(A, p)", doc="p-norm of a Vector or Matrix (default infinity).")
def m_norm_la(ctx, v, p=None):
    if isinstance(v, MList):
        v = MVector(v.items)
    if isinstance(v, MVector):
        return _hw_op(lambda x: _pnorm(x.m, p), v)
    m = _mat(v, "LinearAlgebra:-Norm").m
    rows, cols = m.shape
    if p is None or p == sp.oo or str(p) == "infinity":
        r = sp.Max(*[sp.Add(*[sp.Abs(x) for x in m.row(i)]) for i in range(rows)])
    elif p == 1:
        r = sp.Max(*[sp.Add(*[sp.Abs(x) for x in m.col(j)]) for j in range(cols)])
    elif str(p) in ("Frobenius", "Euclidean"):
        r = _pnorm(list(m), 2)
    elif p == 2:
        r = sp.sqrt(sp.Max(*(m.H * m).eigenvals()))
    else:
        raise MapleError(f"invalid input: unsupported Matrix norm {lprint(p)}", where="LinearAlgebra:-Norm")
    return _hw(r) if _is_hw(v) else r


@la_builtin("Normalize", package=VC, sig="Normalize(v)", doc="Unit vector in the direction of v.")
def m_normalize_vc(ctx, v):
    v = _vec(v)
    n = _norm_vc(v)
    return _hw_op(lambda x: x.map_leaves(lambda e: e / n), v)


@la_builtin("Normalize", package=LA, sig="Normalize(v, p)", doc="Vector scaled to unit p-norm (default infinity).")
def m_normalize_la(ctx, v, p=None):
    n = m_norm_la(ctx, v, p)
    r = _vec(v).map_leaves(lambda x: x / n)
    return _hw(r) if _dtype(v) == "float[8]" else r


@la_builtin("VectorAngle", package=LA, sig="VectorAngle(u, v)", doc="Angle between two Vectors.")
def m_vectorangle(ctx, a, b):
    a, b = _vec(a), _vec(b)
    return sp.acos(dot(a, b) / (_pnorm(a.m, 2) * _pnorm(b.m, 2)))


# ====================================================================== VectorCalculus
@builtin("BasisFormat", package=VC, sig="BasisFormat(true|false)", doc="Choose how Vectors are displayed.")
def m_basisformat(ctx, flag=None):
    prev = ctx.settings.get("BasisFormat", sp.true)
    if flag is not None:
        ctx.settings["BasisFormat"] = flag
    return prev


@la_builtin("dot", sig="dot(u, v)", doc="Dot product of two vectors.")
def m_dot_global(ctx, a, b):
    return dot(_vec(a), _vec(b), conj=False)


@la_builtin("magnitude", sig="magnitude(v)", doc="Euclidean length of a vector.")
def m_magnitude(ctx, v):
    return _norm_vc(_vec(v))
