"""Core Maple functions: evaluation, structure, sequences, types, printing, elementary math."""
from __future__ import annotations

import re
import time as _time

import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..printer import lprint
from ..values import (
    FAIL, NULL, AppliedProc, BuiltinProc, ExprSeq, MEquation, MList, MLogic, MMatrix, Module,
    MRange, MRelation, MSet, MString, MTable, MUneval, MVector, PlotValue, Procedure,
    RememberProc, UserProc, deep_map, make_seq, seq_items,
)
from . import Library, is_true

lib = Library()
builtin = lib.builtin


def register(env):
    lib.register(env)


# ====================================================================== shared helpers
# (imported by the other builtins modules)

def to_sympy(v):
    """Convert a Maple value to a SymPy object (relations -> unevaluated relationals)."""
    if isinstance(v, sp.Basic):
        return v
    if isinstance(v, MRelation):
        l, r = to_sympy(v.lhs), to_sympy(v.rhs)
        cls = {"=": sp.Eq, "<>": sp.Ne, "<": sp.Lt, "<=": sp.Le}.get(v.op)
        if cls is None:
            raise MapleError(f"cannot convert relation {v.op}")
        return cls(l, r, evaluate=False)
    if isinstance(v, MLogic):
        args = [to_sympy(a) for a in v.args]
        return {"and": sp.And, "or": sp.Or, "not": sp.Not, "xor": sp.Xor,
                "implies": sp.Implies}[v.op](*args)
    if isinstance(v, (MList, ExprSeq)):
        return sp.Tuple(*[to_sympy(x) for x in v.items])
    if isinstance(v, MSet):
        return sp.FiniteSet(*[to_sympy(x) for x in v.items])
    if isinstance(v, MString):
        return sp.Symbol(str(v))
    if isinstance(v, bool):
        return sp.true if v else sp.false
    if isinstance(v, int):
        return sp.Integer(v)
    raise MapleError(f"invalid argument: {lprint(v)}")


def from_sympy_rel(e):
    """SymPy relational / boolean back to Maple wrappers."""
    if isinstance(e, sp.Equality):
        return MEquation(e.lhs, e.rhs)
    if isinstance(e, sp.Unequality):
        return MRelation("<>", e.lhs, e.rhs)
    if isinstance(e, sp.core.relational.Relational):
        return MRelation(e.rel_op, e.lhs, e.rhs)
    if isinstance(e, sp.And):
        return MLogic("and", [from_sympy_rel(a) for a in e.args])
    if isinstance(e, sp.Or):
        return MLogic("or", [from_sympy_rel(a) for a in e.args])
    return e


def has_float(v) -> bool:
    found = []

    def f(e):
        if isinstance(e, sp.Basic) and e.has(sp.Float):
            found.append(1)
        return e
    deep_map(f, v)
    return bool(found)


def equations_of(v) -> list:
    """Flatten an equation, list/set of equations, or sequence into a list."""
    out = []
    for x in seq_items(v):
        if isinstance(x, (MList, MSet)):
            out.extend(equations_of(ExprSeq(x.items)))
        else:
            out.append(x)
    return out


def as_items(v) -> list:
    if isinstance(v, (MList, MSet, ExprSeq)):
        return list(v.items)
    return [v]


def _replace_function(expr, name, new, ctx):
    """Replace calls name(args) (and D(name)) in expr by applying `new` to the args."""
    if not isinstance(expr, sp.Basic) or not expr.has(AppliedUndef):
        return expr

    def match(e):
        return isinstance(e, AppliedUndef) and type(e).__name__ == name

    def repl(e):
        r = ctx.apply(new, list(e.args)) if ctx is not None else sp.Function(str(new))(*e.args)
        return r if isinstance(r, sp.Basic) else e
    return expr.replace(match, repl)


def subs_value(ctx, eqs, expr):
    """Maple subs: eqs is a list of MEquation (applied simultaneously)."""
    plain = {}
    funcs = []
    for eq in eqs:
        if not isinstance(eq, MEquation):
            raise MapleError("invalid input: subs expects equations or sets/lists of equations")
        l, r = eq.lhs, eq.rhs
        if isinstance(l, sp.Symbol) and not isinstance(r, sp.Basic):
            funcs.append((l.name, r))
            continue
        if isinstance(l, sp.Symbol) and isinstance(r, sp.Symbol):
            funcs.append((l.name, r))
        if isinstance(l, sp.Basic) and isinstance(r, sp.Basic):
            plain[l] = r
        elif isinstance(l, sp.Symbol):
            pass
        else:
            plain[to_sympy(l)] = to_sympy(r) if not isinstance(r, sp.Basic) else r

    def one(e):
        if not isinstance(e, sp.Basic):
            return e
        for name, new in funcs:
            if isinstance(new, (Procedure, sp.Symbol)):
                e = _replace_function(e, name, new, ctx)
        if plain:
            try:
                e = e.subs(plain, simultaneous=True) if len(plain) > 1 else e.subs(plain)
            except Exception:  # noqa: BLE001
                e = e.xreplace(plain)
        return e

    # whole-value replacement of a symbol by a non-algebraic value (x = [1,2])
    nonalg = {eq.lhs: eq.rhs for eq in eqs if isinstance(eq.lhs, sp.Symbol) and
              not isinstance(eq.rhs, sp.Basic) and not isinstance(eq.rhs, Procedure)}

    def walk(v):
        if isinstance(v, sp.Symbol) and v in nonalg:
            return nonalg[v]
        if isinstance(v, sp.Basic):
            r = one(v)
            if nonalg and isinstance(r, sp.Basic) and any(s in nonalg for s in r.free_symbols):
                r = ctx.reeval_with(r, nonalg) if hasattr(ctx, "reeval_with") else r
            return r
        if isinstance(v, (MList, MSet, ExprSeq, MRelation, MRange, MMatrix, MLogic)):
            return v.map_leaves(walk)
        return v
    return walk(expr)


def lambda_proc(variables, expr, label=None):
    """A procedure value `x -> expr` (what unapply returns). Prints as x -> expr."""
    variables = list(variables)

    def fn(ctx, args):
        if len(args) != len(variables):
            if len(args) < len(variables):
                raise MapleError("invalid input: too few arguments")
        mapping = dict(zip(variables, args))
        if all(isinstance(a, sp.Basic) for a in args):
            if isinstance(expr, sp.Basic):
                return expr.xreplace(mapping) if all(isinstance(v, sp.Symbol) for v in variables) \
                    else expr.subs(mapping)
            return deep_map(lambda e: e.xreplace(mapping), expr)
        return subs_value(ctx, [MEquation(k, v) for k, v in mapping.items()], expr)
    if label is None:
        label = sp.Lambda(tuple(variables), expr) if isinstance(expr, sp.Basic) else None
    p = AppliedProc(fn, label=label)
    p.lambda_vars = variables
    p.lambda_expr = expr
    return p


def proc_as_lambda(ctx, f, nargs=1):
    """(vars, expr) for a procedure value f by applying it to fresh symbols."""
    if isinstance(f, AppliedProc) and hasattr(f, "lambda_vars"):
        return f.lambda_vars, f.lambda_expr
    if isinstance(f, UserProc):
        names = [p.name for p in f.params if not p.keyword] or ["x"]
        vs = [sp.Symbol(n) for n in names]
    else:
        vs = [sp.Symbol(f"x{i}") if nargs > 1 else sp.Symbol("x") for i in range(1, nargs + 1)]
    return vs, ctx.apply(f, vs)


def int_of(v, what="argument") -> int:
    if isinstance(v, sp.Integer):
        return int(v)
    if isinstance(v, sp.Basic) and v.is_number and v == int(v):
        return int(v)
    raise MapleError(f"invalid input: expected an integer {what}, got {lprint(v)}")


# ====================================================================== evaluation
@builtin("eval", sig="eval(expr, x = a)", doc="Evaluate expr, optionally at a point given by equations.")
def m_eval(ctx, e, *pts):
    if not pts:
        return ctx.full_eval(e)
    if len(pts) == 1 and isinstance(pts[0], sp.Integer):
        return ctx.full_eval(e)
    eqs = []
    for p in pts:
        eqs += equations_of(p)
    if isinstance(e, sp.Symbol) or isinstance(e, AppliedUndef):
        # eval(q(t), dsolve-solution list): pick the matching right-hand side
        for eq in eqs:
            if isinstance(eq, MEquation) and _same(eq.lhs, e):
                return eq.rhs
    r = subs_value(ctx, eqs, e)
    return ctx.full_eval(deep_map(lambda x: x.doit() if isinstance(x, sp.Subs) else x, r))


def _same(a, b):
    try:
        return a == b
    except Exception:  # noqa: BLE001
        return False


@builtin("subs", sig="subs(x = a, expr)", doc="Substitute equations into an expression.")
def m_subs(ctx, *args):
    if len(args) < 2:
        raise MapleError("invalid input: subs expects 2 or more arguments")
    expr = args[-1]
    for spec in args[:-1]:
        expr = subs_value(ctx, equations_of(spec), expr)
    return expr


@builtin("evalf", sig="evalf(expr, n)", doc="Evaluate numerically with Digits (or n) digits.",
         indexed=True)
def m_evalf(ctx, e, n=None, index=None):
    digits = int(index[0]) if index else (int(n) if n is not None else None)
    return ctx.evalf(e, digits)


@builtin("evalhf", sig="evalhf(expr)", doc="Evaluate in hardware floating point (15 digits).")
def m_evalhf(ctx, e):
    return ctx.evalf(e, 15)


@builtin("evalb", sig="evalb(relation)", doc="Evaluate a relation to true or false.")
def m_evalb(ctx, e):
    t = ctx.try_truth(e)
    if t is None:
        if isinstance(e, MRelation) and e.op in ("<", "<="):
            return e
        return FAIL if not isinstance(e, MRelation) else (sp.false if e.op == "=" else sp.true)
    return sp.true if t else sp.false


@builtin("is", sig="is(relation)", doc="Test a property; returns true, false or FAIL.")
def m_is(ctx, e, prop=None):
    if prop is not None:
        return sp.true if ctx.type_check(e, prop) else sp.false
    t = ctx.try_truth(e)
    if t is None and isinstance(e, MRelation) and e.op in ("<", "<="):
        d = sp.simplify(e.lhs - e.rhs)
        ok = d.is_negative if e.op == "<" else d.is_nonpositive
        if ok is not None:
            return sp.true if ok else sp.false
    return FAIL if t is None else (sp.true if t else sp.false)


@builtin("evalc", sig="evalc(expr)", doc="Complex evaluation assuming unknowns are real.")
def m_evalc(ctx, e):
    def f(x):
        syms = [s for s in x.free_symbols]
        reals = {s: sp.Symbol(s.name, real=True) for s in syms if not isinstance(s, sp.Dummy)}
        back = {v: k for k, v in reals.items()}
        y = sp.expand_complex(x.xreplace(reals))
        re_, im_ = y.as_real_imag()
        return (re_ + sp.I * im_).xreplace(back)
    return deep_map(f, e)


@builtin("assign", sig="assign(x = value)", doc="Perform the assignments in a set/list of equations.")
def m_assign(ctx, *args):
    if len(args) == 2 and not isinstance(args[0], (MEquation, MList, MSet)):
        args = (MEquation(args[0], args[1]),)
    for eq in equations_of(ExprSeq(args)):
        if not isinstance(eq, MEquation):
            raise MapleError(f"invalid arguments")
        _assign_lhs(ctx, eq.lhs, eq.rhs)
    return NULL


def _assign_lhs(ctx, lhs, value):
    frame = ctx.frame
    if isinstance(lhs, sp.Dummy):
        f = frame
        while f is not None:
            for k, v in f.vars.items():
                if v is lhs:
                    f.vars[k] = value
                    return
            f = f.parent
    if isinstance(lhs, sp.Symbol):
        ctx.assign_name(lhs.name, value, frame)
    elif isinstance(lhs, AppliedUndef):
        ctx.assign_call(type(lhs).__name__, tuple(lhs.args), value, frame)
    elif isinstance(lhs, sp.Indexed):
        from ..nodes import Name
        ctx.assign_index(Name(str(lhs.base.label)), list(lhs.indices), value, frame)
    elif isinstance(lhs, MString):
        ctx.assign_name(str(lhs), value, frame)
    else:
        raise MapleError(f"invalid left hand side in assignment")


@builtin("unassign", sig="unassign('x')", doc="Remove the values of names.")
def m_unassign(ctx, *names):
    for n in names:
        if isinstance(n, sp.Symbol):
            ctx.globals.pop(n.name, None)
    return NULL


@builtin("assigned", sig="assigned(x)", doc="Test whether a name has a value.", evaluate=False)
def m_assigned(ctx, node):
    from .. import nodes as N
    if isinstance(node, N.Name):
        return sp.true if ctx.is_assigned(node.name, ctx.frame) else sp.false
    return sp.false


@builtin("unapply", sig="unapply(expr, x, y, ...)", doc="Make a procedure from an expression.")
def m_unapply(ctx, e, *vars):
    vs = []
    for v in vars:
        vs += as_items(v)
    return lambda_proc(vs, e)


@builtin("if", sig="`if`(cond, a, b)", doc="Conditional expression.", evaluate=False)
def m_if(ctx, c, a, b):
    return ctx.eval(a, ctx.frame) if ctx.truth(ctx.eval(c, ctx.frame)) else ctx.eval(b, ctx.frame)


@builtin("parse", sig='parse("expr")', doc="Parse (and evaluate) a string as Maple input.")
def m_parse(ctx, s, *opts):
    from ..parser import parse_expr
    return ctx.eval(parse_expr(str(s)), ctx.frame)


# ====================================================================== structure
def _op_list(v):
    if isinstance(v, (MList, MSet, ExprSeq)):
        return list(v.items)
    if isinstance(v, MRelation):
        return [v.lhs, v.rhs]
    if isinstance(v, MRange):
        return [v.lo, v.hi]
    if isinstance(v, MLogic):
        return list(v.args)
    if isinstance(v, MString):
        return [v]
    if isinstance(v, MVector):
        return [sp.Integer(len(v.m)), MSet(MEquation(sp.Integer(i), x)
                                            for i, x in enumerate(v.m, 1) if x != 0)]
    if isinstance(v, MMatrix):
        r, c = v.m.shape
        return [sp.Integer(r), sp.Integer(c)]
    if isinstance(v, MTable):
        return [MList(MEquation(make_seq(k), x) for k, x in v.entries.items())]
    if isinstance(v, sp.Basic):
        if isinstance(v, sp.Add):
            from ..printer import _ordered_terms
            return list(_ordered_terms(v))
        if isinstance(v, sp.Mul):
            c, rest = v.as_coeff_Mul()
            fs = list(sp.Mul.make_args(rest))
            return ([c] if c != 1 else []) + fs
        if isinstance(v, sp.Pow):
            return [v.base, v.exp]
        if isinstance(v, sp.Rational) and not v.is_Integer:
            return [sp.Integer(v.p), sp.Integer(v.q)]
        if isinstance(v, sp.Float):
            from ..printer import float_parts
            sign, ds, e = float_parts(v)
            return [sp.Integer(int(sign + ds)), sp.Integer(e)]
        if isinstance(v, sp.Indexed):
            return list(v.indices)
        if isinstance(v, sp.Derivative):
            return [v.expr] + [x for x, n in v.variable_count for _ in range(int(n))]
        if isinstance(v, (sp.Integral, sp.Sum, sp.Product)):
            lim = v.limits[0]
            r = lim[0] if len(lim) == 1 else MEquation(lim[0], MRange(lim[1], lim[2]))
            return [v.function, r]
        if isinstance(v, sp.Piecewise):
            out = []
            for val, cond in v.args:
                if cond is not sp.true:
                    out.append(from_sympy_rel(cond))
                out.append(val)
            return out
        if v.is_Atom:
            return [v]
        return list(v.args)
    return [v]


def _op_head(v):
    if isinstance(v, sp.Add):
        return sp.Symbol("+")
    if isinstance(v, sp.Mul):
        return sp.Symbol("*")
    if isinstance(v, sp.Pow):
        return sp.Symbol("^")
    if isinstance(v, AppliedUndef):
        return sp.Symbol(type(v).__name__)
    if isinstance(v, sp.Indexed):
        return v.base.label
    if isinstance(v, sp.Function):
        from ..printer import FUNC_NAMES
        n = type(v).__name__
        return sp.Symbol(FUNC_NAMES.get(n, n))
    return m_whattype(None, v)


@builtin("op", sig="op(i, expr)", doc="Operands of an expression (op(expr) gives all).")
def m_op(ctx, *args):
    if len(args) == 1:
        return make_seq(_op_list(args[0]))
    i, e = args[0], args[1]
    if isinstance(i, MList):
        for k in i.items:
            e = m_op(ctx, k, e)
        return e
    ops = _op_list(e)
    if isinstance(i, MRange):
        lo, hi = int_of(i.lo), int_of(i.hi)
        n = len(ops)
        lo = lo if lo > 0 else n + lo + 1
        hi = hi if hi > 0 else n + hi + 1
        return make_seq(ops[lo - 1:hi])
    k = int_of(i)
    if k == 0:
        return _op_head(e)
    if k < 0:
        k = len(ops) + k + 1
    if not 1 <= k <= len(ops):
        raise MapleError(f"improper op or subscript selector")
    return ops[k - 1]


@builtin("nops", sig="nops(expr)", doc="Number of operands.")
def m_nops(ctx, e):
    return sp.Integer(len(_op_list(e)))


@builtin("lhs", sig="lhs(eqn)", doc="Left-hand side of an equation, inequality or range.")
def m_lhs(ctx, e):
    if isinstance(e, MRelation):
        return e.lhs
    if isinstance(e, MRange):
        return e.lo
    raise MapleError(f"invalid input: lhs received {lprint(e)}, which is not valid for its 1st argument")


@builtin("rhs", sig="rhs(eqn)", doc="Right-hand side of an equation, inequality or range.")
def m_rhs(ctx, e):
    if isinstance(e, MRelation):
        return e.rhs
    if isinstance(e, MRange):
        return e.hi
    raise MapleError(f"invalid input: rhs received {lprint(e)}, which is not valid for its 1st argument")


@builtin("numelems", sig="numelems(container)", doc="Number of elements of a list, set, table or rtable.")
def m_numelems(ctx, e):
    if isinstance(e, MMatrix):
        return sp.Integer(len(e.m))
    if isinstance(e, MTable):
        return sp.Integer(len(e.entries))
    return sp.Integer(len(as_items(e)))


@builtin("member", sig="member(x, L)", doc="Test membership in a list or set.")
def m_member(ctx, x, coll, *pos):
    items = as_items(coll) if not isinstance(coll, MMatrix) else list(coll.m)
    for i, y in enumerate(items, 1):
        if _same(x, y):
            return sp.true
    return sp.false


@builtin("has", sig="has(expr, x)", doc="Test whether expr contains x.")
def m_has(ctx, e, x):
    targets = as_items(x) if isinstance(x, (MList, MSet)) else [x]
    found = []

    def walk(v):
        if isinstance(v, sp.Basic):
            for t in targets:
                if isinstance(t, sp.Basic) and (v.has(t) or v == t):
                    found.append(1)
        return v
    if any(_same(e, t) for t in targets):
        return sp.true
    deep_map(walk, e)
    return sp.true if found else sp.false


@builtin("indets", sig="indets(expr, type)", doc="Set of indeterminates of an expression.")
def m_indets(ctx, e, typ=None):
    out = []

    def walk(v):
        if isinstance(v, sp.Basic):
            out.extend(s for s in v.free_symbols if not isinstance(s, sp.Dummy))
            if typ is None:
                out.extend(a for a in v.atoms(sp.Function) if not a.is_number)
            elif str(typ) == "function":
                out.clear()
                out.extend(v.atoms(AppliedUndef))
        return v
    deep_map(walk, e)
    if typ is not None and str(typ) not in ("name", "symbol", "function"):
        out = [x for x in out if ctx.type_check(x, typ)]
    return MSet(out)


@builtin("map", sig="map(f, expr)", doc="Apply f to each operand of expr.")
def m_map(ctx, f, e, *extra):
    def ap(x):
        return ctx.apply(f, [x, *extra])
    if isinstance(e, MList):
        return MList(ap(x) for x in e.items)
    if isinstance(e, MSet):
        return MSet(ap(x) for x in e.items)
    if isinstance(e, ExprSeq):
        return make_seq(ap(x) for x in e.items)
    if isinstance(e, MRelation):
        return e.map_leaves(ap)
    if isinstance(e, MMatrix):
        return e.map_leaves(ap)
    if isinstance(e, MTable):
        return e.map_leaves(ap)
    if isinstance(e, sp.Add):
        return _fold(ctx, "+", [ap(x) for x in e.args])
    if isinstance(e, sp.Mul):
        return _fold(ctx, "*", [ap(x) for x in e.args])
    if isinstance(e, sp.Basic) and not e.is_Atom and isinstance(e, sp.Function):
        return e.func(*[ap(x) for x in e.args])
    return ap(e)


def _fold(ctx, op, vals):
    acc = vals[0]
    for v in vals[1:]:
        acc = ctx.binop(op, acc, v)
    return acc


@builtin("map2", sig="map2(f, a, expr)", doc="Apply f(a, x) to each operand x of expr.")
def m_map2(ctx, f, a, e, *extra):
    return m_map(ctx, AppliedProc(lambda c, args: c.apply(f, [a, *args])), e, *extra)


@builtin("zip", sig="zip(f, L1, L2)", doc="Combine two lists elementwise with f.")
def m_zip(ctx, f, a, b, default=None):
    xs, ys = as_items(a), as_items(b)
    n = max(len(xs), len(ys)) if default is not None else min(len(xs), len(ys))
    xs = xs + [default] * (n - len(xs))
    ys = ys + [default] * (n - len(ys))
    return MList(ctx.apply(f, [x, y]) for x, y in zip(xs, ys))


def _select(ctx, f, e, extra, keep):
    def ok(x):
        return ctx.truth(ctx.apply(f, [x, *extra])) == keep
    if isinstance(e, MList):
        return MList(x for x in e.items if ok(x))
    if isinstance(e, MSet):
        return MSet(x for x in e.items if ok(x))
    if isinstance(e, ExprSeq):
        return make_seq(x for x in e.items if ok(x))
    if isinstance(e, sp.Add):
        return sp.Add(*[x for x in e.args if ok(x)])
    if isinstance(e, sp.Mul):
        return sp.Mul(*[x for x in e.args if ok(x)])
    return e


@builtin("select", sig="select(f, L)", doc="Operands for which f returns true.")
def m_select(ctx, f, e, *extra):
    return _select(ctx, f, e, extra, True)


@builtin("remove", sig="remove(f, L)", doc="Operands for which f returns false.")
def m_remove(ctx, f, e, *extra):
    return _select(ctx, f, e, extra, False)


@builtin("selectremove", sig="selectremove(f, L)", doc="Both select and remove results.")
def m_selectremove(ctx, f, e, *extra):
    return ExprSeq([_select(ctx, f, e, extra, True), _select(ctx, f, e, extra, False)])


@builtin("sort", sig="sort(L)", doc="Sort a list (or a polynomial).")
def m_sort(ctx, e, *opts):
    if isinstance(e, MList):
        items = list(e.items)
        if opts and isinstance(opts[0], Procedure):
            import functools
            cmp = opts[0]

            def c(x, y):
                return -1 if ctx.truth(ctx.apply(cmp, [x, y])) else 1
            return MList(sorted(items, key=functools.cmp_to_key(c)))
        rev = bool(opts) and str(opts[0]) == "`>`"
        try:
            return MList(sorted(items, key=lambda x: float(x), reverse=rev))
        except (TypeError, ValueError):
            return MList(sorted(items, key=lprint, reverse=rev))
    return e


@builtin("table", sig="table([i = v, ...])", doc="Create a table.")
def m_table(ctx, init=None):
    t = MTable()
    if isinstance(init, MList):
        for i, x in enumerate(init.items, 1):
            if isinstance(x, MEquation):
                t.entries[tuple(seq_items(x.lhs))] = x.rhs
            else:
                t.entries[(sp.Integer(i),)] = x
    return t


@builtin("entries", sig="entries(t)", doc="Entries of a table.")
def m_entries(ctx, t, *opts):
    if isinstance(t, MTable):
        return make_seq(MList([v]) for v in t.entries.values())
    raise MapleError("invalid input: entries expects a table")


@builtin("indices", sig="indices(t)", doc="Indices of a table.")
def m_indices(ctx, t, *opts):
    if isinstance(t, MTable):
        return make_seq(MList(list(k)) for k in t.entries)
    raise MapleError("invalid input: indices expects a table")


# ====================================================================== sequences / sums
def _iter_spec(ctx, spec_node):
    """Decode `i = a..b`, `i = L`, `i in L` (unevaluated) -> (name, values)."""
    from .. import nodes as N
    if isinstance(spec_node, N.Rel) and spec_node.op == "=" and isinstance(spec_node.left, N.Name):
        name = spec_node.left.name
        rng = ctx.eval(spec_node.right, ctx.frame)
    elif isinstance(spec_node, N.BinOp) and spec_node.op == "in" and isinstance(spec_node.left, N.Name):
        name = spec_node.left.name
        rng = ctx.eval(spec_node.right, ctx.frame)
    else:
        return None, ctx.eval(spec_node, ctx.frame)
    return name, rng


def _range_values(rng, step=None):
    if isinstance(rng, MRange):
        lo, hi = rng.lo, rng.hi
        st = step if step is not None else sp.Integer(1)
        if not all(isinstance(x, sp.Basic) and x.is_number for x in (lo, hi, st)):
            raise MapleError("unable to execute seq")
        out, k = [], lo
        if st > 0:
            while k <= hi:
                out.append(k)
                k = k + st
        else:
            while k >= hi:
                out.append(k)
                k = k + st
        return out
    if isinstance(rng, MMatrix):
        return list(rng.m)
    return as_items(rng) if isinstance(rng, (MList, MSet, ExprSeq)) else \
        list(rng.args) if isinstance(rng, (sp.Add, sp.Mul)) else [rng]


def _iterate(ctx, body, spec, step_node, combine):
    name, rng = _iter_spec(ctx, spec)
    step = ctx.eval(step_node, ctx.frame) if step_node is not None else None
    if name is None:   # seq(L) / seq(a..b)
        return combine([*_range_values(rng, step)])
    vals = []
    for k in _range_values(rng, step):
        vals.append(ctx._with_temp(name, k, ctx.frame, lambda: ctx.eval(body, ctx.frame)))
    return combine(vals)


@builtin("seq", sig="seq(f(i), i = a..b)", doc="Create an expression sequence.", evaluate=False)
def m_seq(ctx, body, spec=None, step=None):
    if spec is None:
        v = ctx.eval(body, ctx.frame)
        return make_seq(_range_values(v))
    return _iterate(ctx, body, spec, step, make_seq)


@builtin("add", sig="add(f(i), i = a..b)", doc="Add a finite sequence of values.", evaluate=False)
def m_add(ctx, body, spec=None, step=None):
    def comb(vals):
        return _fold(ctx, "+", vals) if vals else sp.Integer(0)
    if spec is None:
        return comb(_range_values(ctx.eval(body, ctx.frame)))
    return _iterate(ctx, body, spec, step, comb)


@builtin("mul", sig="mul(f(i), i = a..b)", doc="Multiply a finite sequence of values.", evaluate=False)
def m_mul(ctx, body, spec=None, step=None):
    def comb(vals):
        return _fold(ctx, "*", vals) if vals else sp.Integer(1)
    if spec is None:
        return comb(_range_values(ctx.eval(body, ctx.frame)))
    return _iterate(ctx, body, spec, step, comb)


def _sym_sum(ctx, f, spec, fn, inert):
    if isinstance(spec, MEquation) and isinstance(spec.rhs, MRange):
        var, lo, hi = spec.lhs, spec.rhs.lo, spec.rhs.hi
        if all(isinstance(x, sp.Integer) for x in (lo, hi)) and hi - lo < 1000:
            vals = [ctx.full_eval(f.xreplace({var: k})) for k in range(int(lo), int(hi) + 1)]
            return sp.Add(*vals) if fn is sp.summation else sp.Mul(*vals)
        r = fn(f, (var, lo, hi))
        return r
    if isinstance(spec, sp.Symbol):
        return inert(f, spec)
    raise MapleError("invalid summation range")


@builtin("sum", sig="sum(f, i = a..b)", doc="Symbolic or definite summation.")
def m_sum(ctx, f, spec):
    return _sym_sum(ctx, f, spec, sp.summation, sp.Sum)


@builtin("product", sig="product(f, i = a..b)", doc="Symbolic or definite product.")
def m_product(ctx, f, spec):
    return _sym_sum(ctx, f, spec, sp.product, sp.Product)


class Sum(sp.Sum):
    """Inert Sum (prints as Sum); value()/doit() evaluates."""


class Product(sp.Product):
    """Inert Product."""


@builtin("Sum", sig="Sum(f, i = a..b)", doc="Inert summation.")
def m_Sum(ctx, f, spec):
    if isinstance(spec, MEquation) and isinstance(spec.rhs, MRange):
        return Sum(f, (spec.lhs, spec.rhs.lo, spec.rhs.hi))
    return Sum(f, spec)


@builtin("Product", sig="Product(f, i = a..b)", doc="Inert product.")
def m_Product(ctx, f, spec):
    if isinstance(spec, MEquation) and isinstance(spec.rhs, MRange):
        return Product(f, (spec.lhs, spec.rhs.lo, spec.rhs.hi))
    return Product(f, spec)


# ====================================================================== types
def _num(v):
    return isinstance(v, sp.Basic) and v.is_Number and v.is_finite is not False and v is not sp.nan


TYPES = {
    "anything": lambda v: True,
    "integer": lambda v: isinstance(v, sp.Integer),
    "posint": lambda v: isinstance(v, sp.Integer) and v > 0,
    "negint": lambda v: isinstance(v, sp.Integer) and v < 0,
    "nonnegint": lambda v: isinstance(v, sp.Integer) and v >= 0,
    "nonposint": lambda v: isinstance(v, sp.Integer) and v <= 0,
    "even": lambda v: isinstance(v, sp.Integer) and v % 2 == 0,
    "odd": lambda v: isinstance(v, sp.Integer) and v % 2 == 1,
    "numeric": lambda v: _num(v) and v.is_real,
    "extended_numeric": lambda v: isinstance(v, sp.Basic) and v.is_Number,
    "float": lambda v: isinstance(v, sp.Float),
    "sfloat": lambda v: isinstance(v, sp.Float),
    "rational": lambda v: isinstance(v, sp.Rational),
    "fraction": lambda v: isinstance(v, sp.Rational) and not isinstance(v, sp.Integer),
    "positive": lambda v: _num(v) and v > 0,
    "negative": lambda v: _num(v) and v < 0,
    "nonnegative": lambda v: _num(v) and v >= 0,
    "nonpositive": lambda v: _num(v) and v <= 0,
    "realcons": lambda v: isinstance(v, sp.Basic) and not v.is_Boolean and v.is_number and
    v.is_real is not False and not v.has(sp.I),
    "constant": lambda v: isinstance(v, sp.Basic) and not v.is_Boolean and v.is_number,
    "complex": lambda v: isinstance(v, sp.Basic) and v.is_number and
    all(x.is_Number for x in (v.as_real_imag())),
    "complexcons": lambda v: isinstance(v, sp.Basic) and v.is_number,
    "name": lambda v: isinstance(v, (sp.Symbol, sp.Indexed)) and v not in (sp.true, sp.false),
    "symbol": lambda v: isinstance(v, sp.Symbol),
    "indexed": lambda v: isinstance(v, sp.Indexed),
    "string": lambda v: isinstance(v, MString),
    "list": lambda v: isinstance(v, MList),
    "set": lambda v: isinstance(v, MSet),
    "=": lambda v: isinstance(v, MEquation),
    "equation": lambda v: isinstance(v, MEquation),
    "<>": lambda v: isinstance(v, MRelation) and v.op == "<>",
    "<": lambda v: isinstance(v, MRelation) and v.op == "<",
    "<=": lambda v: isinstance(v, MRelation) and v.op == "<=",
    "relation": lambda v: isinstance(v, MRelation),
    "range": lambda v: isinstance(v, MRange),
    "..": lambda v: isinstance(v, MRange),
    "procedure": lambda v: isinstance(v, Procedure),
    "operator": lambda v: isinstance(v, Procedure),
    "appliable": lambda v: isinstance(v, Procedure),
    "function": lambda v: isinstance(v, (sp.Function, AppliedUndef)) and not v.is_number or
    isinstance(v, sp.Function),
    "algebraic": lambda v: isinstance(v, sp.Basic) and not v.is_Boolean,
    "boolean": lambda v: isinstance(v, (MRelation, MLogic)) or v in (sp.true, sp.false, FAIL),
    "truefalse": lambda v: v in (sp.true, sp.false),
    "+": lambda v: isinstance(v, sp.Add),
    "*": lambda v: isinstance(v, sp.Mul),
    "^": lambda v: isinstance(v, sp.Pow),
    "table": lambda v: isinstance(v, MTable),
    "Matrix": lambda v: isinstance(v, MMatrix) and not isinstance(v, MVector),
    "Vector": lambda v: isinstance(v, MVector),
    "rtable": lambda v: isinstance(v, MMatrix),
    "module": lambda v: isinstance(v, Module),
    "package": lambda v: isinstance(v, Module),
    "exprseq": lambda v: isinstance(v, ExprSeq),
    "polynom": lambda v: isinstance(v, sp.Basic) and not v.is_Boolean and v.is_polynomial(),
    "infinity": lambda v: v in (sp.oo, -sp.oo),
    "undefined": lambda v: v is sp.nan,
}

for _name, _fn in TYPES.items():
    lib.types[_name] = (lambda f: lambda ctx, v, *p: f(v))(_fn)


@lib.type("list")
def _t_list(ctx, v, *p):
    return isinstance(v, MList) and (not p or all(ctx.type_check(x, p[0]) for x in v.items))


@lib.type("set")
def _t_set(ctx, v, *p):
    return isinstance(v, MSet) and (not p or all(ctx.type_check(x, p[0]) for x in v.items))


@lib.type("polynom")
def _t_polynom(ctx, v, *p):
    if not (isinstance(v, sp.Basic) and not v.is_Boolean):
        return False
    if len(p) >= 2:
        vs = as_items(p[1])
        return v.is_polynomial(*vs)
    return v.is_polynomial()


@lib.type("specfunc")
def _t_specfunc(ctx, v, *p):
    if not isinstance(v, (sp.Function, AppliedUndef)):
        return False
    name = lprint(_op_head(v))
    return not p or name == lprint(p[-1])


@builtin("type", sig="type(expr, t)", doc="Test whether expr is of type t.")
def m_type(ctx, e, t):
    return sp.true if ctx.type_check(e, t) else sp.false


@builtin("whattype", sig="whattype(expr)", doc="The basic type of an expression.")
def m_whattype(ctx, v):
    S = sp.Symbol
    if isinstance(v, ExprSeq):
        return S("exprseq")
    if isinstance(v, MList):
        return S("list")
    if isinstance(v, MSet):
        return S("set")
    if isinstance(v, MRelation):
        return S(v.op)
    if isinstance(v, MRange):
        return S("..")
    if isinstance(v, MString):
        return S("string")
    if isinstance(v, MLogic):
        return S(v.op)
    if isinstance(v, MVector):
        return sp.Indexed(sp.IndexedBase(S("Vector")), S(v.orient))
    if isinstance(v, MMatrix):
        return S("Matrix")
    if isinstance(v, MTable):
        return S("table")
    if isinstance(v, Procedure):
        return S("procedure")
    if isinstance(v, Module):
        return S("module")
    if isinstance(v, sp.Basic):
        if v in (sp.true, sp.false):
            return S("symbol")
        if isinstance(v, sp.Integer):
            return S("integer")
        if isinstance(v, sp.Rational):
            return S("fraction")
        if isinstance(v, sp.Float):
            return S("float")
        if isinstance(v, sp.Symbol):
            return S("symbol")
        if isinstance(v, sp.Indexed):
            return S("indexed")
        if isinstance(v, sp.Add):
            return S("+")
        if isinstance(v, sp.Mul):
            return S("*")
        if isinstance(v, sp.Pow):
            return S("^")
        if v is sp.pi or v is sp.oo or v is sp.E:
            return S("symbol")
        return S("function")
    return S("anything")


# ====================================================================== conversion
@builtin("convert", sig="convert(expr, form)", doc="Convert between forms (float, list, set, exp, ...).")
def m_convert(ctx, e, form, *extra):
    f = lprint(form).strip("`")
    if f == "float":
        return ctx.evalf(e)
    if f == "rational":
        return deep_map(lambda x: sp.nsimplify(x, rational=True) if x.has(sp.Float) else x, e)
    if f == "list":
        if isinstance(e, MMatrix):
            return MList(list(e.m))
        if isinstance(e, MTable):
            return MList(e.entries.values())
        if isinstance(e, MRelation):
            return MList([e.lhs, e.rhs])
        return MList(as_items(e) if isinstance(e, (MSet, ExprSeq, MList)) else _op_list(e))
    if f == "set":
        if isinstance(e, MMatrix):
            return MSet(list(e.m))
        return MSet(as_items(e) if isinstance(e, (MList, ExprSeq, MSet)) else _op_list(e))
    if f == "string":
        return MString(str(e) if isinstance(e, MString) else lprint(e))
    if f in ("name", "symbol"):
        return sp.Symbol(str(e) if isinstance(e, MString) else lprint(e))
    if f in ("exp", "sin", "cos", "tan", "sincos", "ln", "log", "trig", "expln", "tanh", "sinh"):
        target = {"sincos": sp.cos, "trig": sp.cos, "ln": sp.log, "log": sp.log, "expln": sp.exp,
                  "exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "tanh": sp.tanh,
                  "sinh": sp.sinh}[f]
        r = deep_map(lambda x: x.rewrite(target), e)
        if f in ("sincos", "trig"):
            r = deep_map(lambda x: x.rewrite(sp.sin) if x.has(sp.tan) else x, r)
        return r
    if f == "parfrac":
        var = extra[0] if extra else None
        return deep_map(lambda x: sp.apart(x, var) if var is not None else sp.apart(x), e)
    if f == "+":
        return _fold(ctx, "+", as_items(e)) if as_items(e) else sp.Integer(0)
    if f == "*":
        return _fold(ctx, "*", as_items(e)) if as_items(e) else sp.Integer(1)
    if f == "degrees":
        return deep_map(lambda x: x * 180 / sp.pi, e)
    if f == "radians":
        return deep_map(lambda x: x * sp.pi / 180, e)
    if f == "polynom":
        return deep_map(lambda x: x.removeO() if hasattr(x, "removeO") else x, e)
    if f in ("diff", "D"):
        return e
    if f == "piecewise":
        return deep_map(lambda x: x.rewrite(sp.Piecewise), e)
    if f == "Heaviside":
        return deep_map(lambda x: x.rewrite(sp.Heaviside), e)
    if f == "Matrix":
        return ctx.call("Matrix", e)
    if f == "Vector":
        return ctx.call("Vector", e)
    if f == "listlist" and isinstance(e, MMatrix):
        return MList(MList(e.m.row(i)) for i in range(e.m.shape[0]))
    raise MapleError(f"invalid input: convert does not support conversion to `{f}` yet")


# ====================================================================== elementary functions
def _f1(name, fn, doc, sig=None):
    @builtin(name, sig=sig or f"{name}(x)", doc=doc)
    def wrapper(ctx, x, *rest):
        if rest:
            raise MapleError(f"invalid input: {name} expects 1 argument, but received {1 + len(rest)}")
        return deep_map(fn, x) if not isinstance(x, sp.Basic) else fn(x)
    return wrapper


for _n, _fn, _doc in [
    ("sin", sp.sin, "Sine."), ("cos", sp.cos, "Cosine."), ("tan", sp.tan, "Tangent."),
    ("sec", sp.sec, "Secant."), ("csc", sp.csc, "Cosecant."), ("cot", sp.cot, "Cotangent."),
    ("arcsin", sp.asin, "Inverse sine."), ("arccos", sp.acos, "Inverse cosine."),
    ("arcsec", sp.asec, "Inverse secant."), ("arccsc", sp.acsc, "Inverse cosecant."),
    ("arccot", sp.acot, "Inverse cotangent."),
    ("sinh", sp.sinh, "Hyperbolic sine."), ("cosh", sp.cosh, "Hyperbolic cosine."),
    ("tanh", sp.tanh, "Hyperbolic tangent."), ("sech", sp.sech, "Hyperbolic secant."),
    ("csch", sp.csch, "Hyperbolic cosecant."), ("coth", sp.coth, "Hyperbolic cotangent."),
    ("arcsinh", sp.asinh, "Inverse hyperbolic sine."), ("arccosh", sp.acosh, "Inverse hyperbolic cosine."),
    ("arctanh", sp.atanh, "Inverse hyperbolic tangent."),
    ("exp", sp.exp, "Exponential function."), ("ln", sp.log, "Natural logarithm."),
    ("sqrt", sp.sqrt, "Square root."), ("abs", sp.Abs, "Absolute value."),
    ("signum", sp.sign, "Sign of a real or complex number."), ("floor", sp.floor, "Greatest integer <= x."),
    ("ceil", sp.ceiling, "Least integer >= x."), ("factorial", sp.factorial, "n!"),
    ("Re", sp.re, "Real part."), ("Im", sp.im, "Imaginary part."),
    ("conjugate", sp.conjugate, "Complex conjugate."), ("argument", sp.arg, "Complex argument."),
    ("erf", sp.erf, "Error function."), ("GAMMA", sp.gamma, "Gamma function."),
    ("Heaviside", sp.Heaviside, "Heaviside step function."), ("Dirac", sp.DiracDelta, "Dirac delta."),
    ("LambertW", sp.LambertW, "Lambert W function."), ("csgn", lambda x: sp.sign(sp.re(x)) if x.is_number else sp.Function("csgn")(x), "Complex sign."),
]:
    _f1(_n, _fn, _doc)


@builtin("arctan", sig="arctan(x) or arctan(y, x)", doc="Inverse tangent (two-argument form gives the angle of (x, y)).")
def m_arctan(ctx, y, x=None):
    if x is None:
        return deep_map(sp.atan, y)
    return sp.atan2(y, x)


@builtin("log", sig="log(x) or log[b](x)", doc="Logarithm (natural, or base b with log[b]).", indexed=True)
def m_log(ctx, x, b=None, index=None):
    base = index[0] if index else b
    if base is None:
        return sp.log(x)
    return sp.log(x) / sp.log(base)


@builtin("log10", sig="log10(x)", doc="Base-10 logarithm.")
def m_log10(ctx, x):
    return sp.log(x) / sp.log(10)


@builtin("log2", sig="log2(x)", doc="Base-2 logarithm.")
def m_log2(ctx, x):
    return sp.log(x) / sp.log(2)


@builtin("root", sig="root(x, n)", doc="n-th root.", indexed=True)
def m_root(ctx, x, n=None, index=None):
    n = index[0] if index else n
    return sp.Pow(x, sp.Integer(1) / n)


@builtin("surd", sig="surd(x, n)", doc="Real n-th root.")
def m_surd(ctx, x, n):
    return sp.real_root(x, n)


@builtin("sign", sig="sign(expr)", doc="Sign of the leading coefficient (1 for 0).")
def m_sign(ctx, x):
    if isinstance(x, sp.Basic) and x.is_number:
        v = x.evalf() if not x.is_Number else x
        if v.is_real is False:
            return sp.sign(x)
        return sp.Integer(-1) if v < 0 else sp.Integer(1)
    c = sp.Poly(x).LC() if isinstance(x, sp.Basic) and x.is_polynomial() else x.as_coeff_Mul()[0]
    return sp.Integer(-1) if c < 0 else sp.Integer(1)


def _num_or_fn(name, f):
    def g(x):
        if isinstance(x, sp.Basic) and x.is_number:
            return f(x)
        return sp.Function(name)(x)
    return g


def _round(x):
    v = sp.nsimplify(x) if x.is_Float else x
    return sp.sign(v) * sp.floor(abs(v) + sp.Rational(1, 2)) if v.is_real else \
        _round(sp.re(x)) + sp.I * _round(sp.im(x))


def _trunc(x):
    return sp.sign(x) * sp.floor(abs(x)) if x.is_real else _trunc(sp.re(x)) + sp.I * _trunc(sp.im(x))


@builtin("round", sig="round(x)", doc="Round to the nearest integer.")
def m_round(ctx, x):
    return deep_map(_num_or_fn("round", _round), x)


@builtin("trunc", sig="trunc(x)", doc="Truncate towards zero.")
def m_trunc(ctx, x):
    return deep_map(_num_or_fn("trunc", _trunc), x)


@builtin("frac", sig="frac(x)", doc="Fractional part x - trunc(x).")
def m_frac(ctx, x):
    return deep_map(_num_or_fn("frac", lambda v: v - _trunc(v)), x)


@builtin("binomial", sig="binomial(n, k)", doc="Binomial coefficient.")
def m_binomial(ctx, n, k):
    return sp.binomial(n, k)


@builtin("irem", sig="irem(m, n)", doc="Integer remainder (sign of m).")
def m_irem(ctx, m, n, q=None):
    m, n = int_of(m), int_of(n)
    r = abs(m) % abs(n)
    return sp.Integer(-r if m < 0 else r)


@builtin("iquo", sig="iquo(m, n)", doc="Integer quotient (truncated).")
def m_iquo(ctx, m, n, r=None):
    m, n = int_of(m), int_of(n)
    q = abs(m) // abs(n)
    return sp.Integer(q if (m >= 0) == (n > 0) else -q)


@builtin(["mod", "modp"], sig="modp(a, m)", doc="Positive remainder modulo m.")
def m_mod(ctx, a, m):
    if isinstance(a, sp.Rational) and not isinstance(a, sp.Integer):
        return sp.Integer(a.p * pow(a.q, -1, int(m))) % m
    if isinstance(a, sp.Basic) and not a.is_number:
        p = sp.Poly(a)
        return sp.Poly([c % m for c in p.all_coeffs()], *p.gens).as_expr()
    return sp.Mod(a, m)


@builtin("mods", sig="mods(a, m)", doc="Symmetric remainder modulo m.")
def m_mods(ctx, a, m):
    r = sp.Mod(a, m)
    return r - m if r > m / 2 else r


@builtin("gcd", sig="gcd(a, b)", doc="Greatest common divisor (integers or polynomials).")
def m_gcd(ctx, a, b):
    return sp.gcd(a, b)


@builtin("lcm", sig="lcm(a, b, ...)", doc="Least common multiple.")
def m_lcm(ctx, *args):
    r = args[0]
    for a in args[1:]:
        r = sp.lcm(r, a)
    return r


@builtin(["igcd"], sig="igcd(a, b, ...)", doc="Integer gcd.")
def m_igcd(ctx, *args):
    return sp.igcd(*[int_of(a) for a in args])


@builtin(["ilcm"], sig="ilcm(a, b, ...)", doc="Integer lcm.")
def m_ilcm(ctx, *args):
    return sp.ilcm(*[int_of(a) for a in args])


@builtin("isprime", sig="isprime(n)", doc="Primality test.")
def m_isprime(ctx, n):
    return sp.true if sp.isprime(int_of(n)) else sp.false


@builtin("ithprime", sig="ithprime(i)", doc="The i-th prime.")
def m_ithprime(ctx, i):
    return sp.prime(int_of(i))


@builtin("nextprime", sig="nextprime(n)", doc="Smallest prime > n.")
def m_nextprime(ctx, n):
    return sp.nextprime(int_of(n))


@builtin("ifactor", sig="ifactor(n)", doc="Integer factorization.")
def m_ifactor(ctx, n):
    n = int_of(n)
    blank = sp.Function("")
    parts = [sp.Pow(blank(sp.Integer(p)), e, evaluate=False) if e > 1 else blank(sp.Integer(p))
             for p, e in sorted(sp.factorint(abs(n)).items())]
    r = sp.Mul(*parts, evaluate=False) if len(parts) > 1 else parts[0] if parts else sp.Integer(n)
    return -r if n < 0 else r


@builtin("numer", sig="numer(expr)", doc="Numerator.")
def m_numer(ctx, e):
    return sp.fraction(sp.together(e))[0]


@builtin("denom", sig="denom(expr)", doc="Denominator.")
def m_denom(ctx, e):
    return sp.fraction(sp.together(e))[1]


def _flat_numbers(args):
    out = []
    for a in args:
        if isinstance(a, (MList, MSet, ExprSeq)):
            out += _flat_numbers(a.items)
        elif isinstance(a, MMatrix):
            out += list(a.m)
        else:
            out.append(a)
    return out


@builtin("max", sig="max(a, b, ...)", doc="Maximum.")
def m_max(ctx, *args):
    xs = _flat_numbers(args)
    if not xs:
        return -sp.oo
    return sp.Max(*xs)


@builtin("min", sig="min(a, b, ...)", doc="Minimum.")
def m_min(ctx, *args):
    xs = _flat_numbers(args)
    if not xs:
        return sp.oo
    return sp.Min(*xs)


@builtin("piecewise", sig="piecewise(cond1, f1, cond2, f2, ..., otherwise)",
         doc="Piecewise-defined expression.")
def m_piecewise(ctx, *args):
    pairs = []
    i = 0
    while i + 1 < len(args):
        c = args[i]
        t = ctx.try_truth(c)
        cond = sp.true if t is True else sp.false if t is False else to_sympy(c)
        pairs.append((args[i + 1], cond))
        i += 2
    if i < len(args):
        pairs.append((args[i], sp.true))
    else:
        pairs.append((sp.Integer(0), sp.true))
    return sp.Piecewise(*pairs)


# ====================================================================== printing
@builtin("print", sig="print(e1, e2, ...)", doc="Display expressions.")
def m_print(ctx, *args):
    ctx.emit({"kind": "print", "text": ", ".join(lprint(a) for a in args),
              "latex": ", ".join(ctx.to_latex(a) for a in args)})
    return NULL


@builtin("lprint", sig="lprint(e1, ...)", doc="Print in 1-D (linear) form.")
def m_lprint(ctx, *args):
    ctx.emit({"kind": "print", "text": ", ".join(lprint(a) for a in args)})
    return NULL


_FMT = re.compile(r"%([-+ 0#]*)(\*|\d+)?(?:\.(\*|\d+))?([a-zA-Z%])")


def maple_sprintf(fmt: str, args) -> str:
    args = list(args)
    out = []
    pos = 0
    ai = 0

    def nxt():
        nonlocal ai
        if ai >= len(args):
            raise MapleError("invalid input: not enough arguments for the format string")
        v = args[ai]
        ai += 1
        return v
    for m in _FMT.finditer(fmt):
        out.append(fmt[pos:m.start()])
        pos = m.end()
        flags, width, prec, conv = m.groups()
        if conv == "%":
            out.append("%")
            continue
        if width == "*":
            width = str(int(nxt()))
        if prec == "*":
            prec = str(int(nxt()))
        spec = "%" + flags + (width or "") + ("." + prec if prec is not None else "")
        if conv == "q":
            rest = args[ai:]
            ai = len(args)
            out.append(", ".join(lprint(a) for a in rest))
            continue
        v = nxt()
        if conv in "aA":
            out.append((spec + "s") % lprint(v))
        elif conv == "s":
            out.append((spec + "s") % (str(v) if isinstance(v, MString) else lprint(v)))
        elif conv == "c":
            out.append(str(v)[:1])
        elif conv in "dioxXu":
            try:
                iv = int(v) if not isinstance(v, sp.Float) else int(round(float(v)))
            except (TypeError, ValueError):
                out.append(lprint(v))
                continue
            out.append((spec + ("d" if conv in "iu" else conv)) % iv)
        elif conv in "feEgG":
            try:
                out.append((spec + conv) % float(sp.N(v) if isinstance(v, sp.Basic) else v))
            except (TypeError, ValueError):
                out.append(lprint(v))
        else:
            out.append(m.group(0))
    out.append(fmt[pos:])
    return "".join(out)


@builtin("printf", sig='printf("fmt", args)', doc="Formatted printing (C-style %d %f %e %g %s %a %q).")
def m_printf(ctx, fmt, *args):
    text = maple_sprintf(str(fmt), args)
    outs = ctx.outputs
    if outs and outs[-1].get("kind") == "print" and ctx._printf_open is outs[-1]:
        outs[-1]["text"] += text
    else:
        outs.append({"kind": "print", "text": text})
    last = outs[-1]
    if last["text"].endswith("\n"):
        last["text"] = last["text"][:-1]
        ctx._printf_open = None
    else:
        ctx._printf_open = last
    return NULL


@builtin("sprintf", sig='sprintf("fmt", args)', doc="Formatted string.")
def m_sprintf(ctx, fmt, *args):
    return MString(maple_sprintf(str(fmt), args))


@builtin("nprintf", sig='nprintf("fmt", args)', doc="Formatted name.")
def m_nprintf(ctx, fmt, *args):
    return sp.Symbol(maple_sprintf(str(fmt), args))


@builtin("cat", sig="cat(a, b, ...)", doc="Concatenate strings/names.")
def m_cat(ctx, *args):
    def txt(a):
        return str(a) if isinstance(a, MString) else lprint(a).strip("`")
    s = "".join(txt(a) for a in args)
    if args and isinstance(args[0], MString):
        return MString(s)
    return sp.Symbol(s)


@builtin("length", sig="length(expr)", doc="Length of a string (or size of an expression).")
def m_length(ctx, e):
    if isinstance(e, MString):
        return sp.Integer(len(e))
    if isinstance(e, sp.Integer):
        return sp.Integer(len(str(abs(int(e)))))
    return sp.Integer(len(lprint(e)))


def _st(name, fn, doc):
    @builtin(name, package="StringTools", sig=f"{name}(s)", doc=doc)
    def w(ctx, s, *rest):
        return fn(str(s), *rest)


_st("Length", lambda s: sp.Integer(len(s)), "Length of a string.")
_st("UpperCase", lambda s: MString(s.upper()), "Upper-case a string.")
_st("LowerCase", lambda s: MString(s.lower()), "Lower-case a string.")
_st("Reverse", lambda s: MString(s[::-1]), "Reverse a string.")
_st("Trim", lambda s: MString(s.strip()), "Strip leading and trailing whitespace.")
_st("Split", lambda s, sep=None: MList(MString(x) for x in (s.split(str(sep)) if sep else s.split())),
    "Split a string into a list of words.")
_st("Join", lambda s, sep=" ": MString(s), "Join strings.")


# ====================================================================== session / system
@builtin("restart", sig="restart", doc="Clear all user variables (like a fresh Maple session).")
def m_restart(ctx):
    ctx.restart()
    return NULL


@builtin("interface", sig="interface(option = value)", doc="Set interface options (displayprecision, ...).")
def m_interface(ctx, *args):
    prev = NULL
    for a in args:
        if isinstance(a, MEquation) and isinstance(a.lhs, sp.Symbol):
            key = a.lhs.name
            prev = ctx.settings.get(key, NULL)
            val = a.rhs
            ctx.settings[key] = int(val) if isinstance(val, sp.Integer) else val
        elif isinstance(a, sp.Symbol):
            return ctx.settings.get(a.name, NULL)
    return NULL if prev is None else NULL


@builtin("kernelopts", sig="kernelopts(...)", doc="Kernel options (ignored).")
def m_kernelopts(ctx, *args):
    return NULL


@builtin("time", sig="time()", doc="CPU time in seconds.", indexed=True)
def m_time(ctx, *args, index=None):
    if args:
        return sp.Float(0.0, 15)
    return sp.Float(round(_time.process_time() if not index else _time.time(), 3), 15)


@builtin("with", sig="with(Package)", doc="Make the short names of a package's exports available.")
def m_with(ctx, pkg, *names):
    if not isinstance(pkg, Module):
        raise MapleError(f"invalid input: with expects its 1st argument, pname, to be of type "
                         f"{{`module`, package}}, but received {lprint(pkg)}")
    for n, v in pkg.exports.items():
        ctx.bound[n] = v
    if pkg.name not in ctx.loaded:
        ctx.loaded.append(pkg.name)
    for hook in ctx.env.with_hooks.get(pkg.name, []):
        hook(ctx)
    return MList(sp.Symbol(n) for n in pkg.export_names)


@builtin("assume", sig="assume(x > 0)", doc="Record assumptions about names.")
def m_assume(ctx, *props):
    for p in props:
        if isinstance(p, MRelation):
            for side in (p.lhs, p.rhs):
                if isinstance(side, sp.Symbol):
                    ctx.assumptions.setdefault(side.name, []).append(p)
    if len(props) == 2 and isinstance(props[0], sp.Symbol):
        ctx.assumptions.setdefault(props[0].name, []).append(props[1])
    return NULL


@builtin("about", sig="about(x)", doc="Show assumptions on a name.")
def m_about(ctx, x):
    a = ctx.assumptions.get(lprint(x), [])
    ctx.print_text(f"{lprint(x)}:\n  " + (", ".join(lprint(p) for p in a) if a else "nothing known"))
    return NULL


@builtin("ERROR", sig='ERROR("msg")', doc="Raise an error.")
def m_ERROR(ctx, *args):
    from ..evaluator import format_error
    raise MapleError(format_error(args))


@builtin("WARNING", sig='WARNING("msg", args)', doc="Issue a warning.")
def m_WARNING(ctx, *args):
    from ..evaluator import format_error
    ctx.warn(format_error(args))
    return NULL


@builtin("userinfo", sig="userinfo(...)", doc="Informational messages (ignored).")
def m_userinfo(ctx, *args):
    return NULL


@builtin("infolevel", sig="infolevel", doc="Ignored.")
def m_infolevel(ctx, *args):
    return NULL


@builtin("rand", sig="rand(a..b)", doc="Random integer generator.")
def m_rand(ctx, r=None):
    import random
    if isinstance(r, MRange):
        lo, hi = int_of(r.lo), int_of(r.hi)
        return AppliedProc(lambda c, args: sp.Integer(random.randint(lo, hi)), label=sp.Symbol("proc() ... end proc"))
    return sp.Integer(random.randint(0, 10 ** 12))

