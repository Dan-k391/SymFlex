"""Calculus: diff, D, int, limit, series and their inert forms.  First working versions."""
from __future__ import annotations

import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..printer import lprint
from ..values import (
    AppliedProc, BuiltinProc, ExprSeq, MEquation, MList, MRange, MRelation, Procedure, UserProc,
    deep_map, seq_items,
)
from . import Library, is_true
from .core import lambda_proc, proc_as_lambda

lib = Library()
builtin = lib.builtin


def register(env):
    lib.register(env)


# Inert forms print with Maple's capitalised names (Int, Limit, ...); value() evaluates them.
class Int(sp.Integral):
    pass


class Limit(sp.Limit):
    pass


# ====================================================================== diff
def _diff_vars(args):
    out = []
    for i, a in enumerate(args, 2):
        if isinstance(a, MList):
            out += list(a.items)
        elif isinstance(a, ExprSeq):
            out += list(a.items)
        else:
            out.append(a)
    for i, v in enumerate(out, 2):
        if not isinstance(v, (sp.Symbol, sp.Indexed, AppliedUndef)):
            raise MapleError(f"invalid input: diff received {lprint(v)}, which is not valid for "
                             f"its {_ord(i)} argument")
    return out


def _ord(n):
    from ..evaluator import ordinal
    return ordinal(n)


def diff_value(e, vars_):
    if not vars_:
        return e

    def d(x):
        if not isinstance(x, sp.Basic):
            return x
        r = x
        for v in vars_:
            if isinstance(v, AppliedUndef):
                tmp = sp.Dummy("f")
                r = sp.diff(r.subs(v, tmp), tmp).subs(tmp, v)
            else:
                r = sp.diff(r, v)
        return r
    return deep_map(d, e)


@builtin("diff", sig="diff(f, x1, ..., xn)", doc="Differentiate f with respect to x1, ..., xn (diff(f, x$2) for 2nd derivative).")
def m_diff(ctx, e, *vars_):
    if not vars_:
        raise MapleError("invalid input: diff expects 2 or more arguments, but received 1")
    return diff_value(e, _diff_vars(vars_))


@builtin("Diff", sig="Diff(f, x)", doc="Inert derivative.")
def m_Diff(ctx, e, *vars_):
    return sp.Derivative(e, *_diff_vars(vars_), evaluate=False)


@builtin("value", sig="value(expr)", doc="Evaluate inert forms (Int, Diff, Sum, Limit).")
def m_value(ctx, e):
    def ev(x):
        x = x.replace(lambda z: isinstance(z, (Int, Limit)),
                      lambda z: (sp.Integral if isinstance(z, Int) else sp.Limit)(*z.args))
        return x.doit()
    return deep_map(ev, e)


# ====================================================================== D operator
def d_unknown(name, counts=()):
    """D applied to an unknown function name: (D@@n)(y) or D[i,j](f)."""
    counts = tuple(counts)
    n = len(counts)
    if all(c == 1 for c in counts):
        label = f"D({name})" if n == 1 else f"(D@@{n})({name})"
    else:
        label = f"D[{','.join(map(str, sorted(counts)))}]({name})"

    def fn(ctx, args):
        if not all(isinstance(a, sp.Basic) for a in args):
            from ..evaluator import MCall
            return MCall(sp.Symbol(label), args)
        f = sp.Function(name)
        dummies = [sp.Dummy(f"x{i}") for i in range(len(args))] if len(args) > 1 else [sp.Dummy("x")]
        vs = []
        for c in counts:
            if c - 1 >= len(dummies):
                raise MapleError("invalid input: D index exceeds the number of arguments")
            vs.append(dummies[c - 1])
        der = sp.Derivative(f(*dummies), *vs)
        if all(isinstance(a, sp.Symbol) for a in args) and len(set(args)) == len(args):
            return der.xreplace(dict(zip(dummies, args)))
        return sp.Subs(der, tuple(dummies), tuple(args))
    p = AppliedProc(fn, label=sp.Symbol(label))
    p.d_unknown = (name, counts)
    return p


def d_operator(ctx, f, index=None):
    idx = [int(i) for i in index] if index else [1]
    if isinstance(f, sp.Symbol) and not isinstance(f, sp.Dummy):
        return d_unknown(f.name, idx)
    if isinstance(f, AppliedProc) and hasattr(f, "d_unknown"):
        name, counts = f.d_unknown
        return d_unknown(name, counts + tuple(idx))
    if isinstance(f, (Procedure,)):
        nargs = max(idx)
        if isinstance(f, UserProc):
            nargs = max(nargs, len([p for p in f.params if not p.keyword]))
        vs, body = proc_as_lambda(ctx, f, nargs)
        for i in idx:
            body = diff_value(body, [vs[i - 1]])
        if isinstance(body, sp.Basic) and body.is_number:
            return body     # Maple: D of a linear operator is the constant itself
        return lambda_proc(vs, body)
    if isinstance(f, sp.Basic) and f.is_number:
        return sp.Integer(0)
    raise MapleError(f"invalid input: D expects a procedure, received {lprint(f)}")


@builtin("D", sig="D(f) or D[i](f)", doc="Differential operator: D(f)(x) is the derivative of f at x.",
         indexed=True)
def m_D(ctx, f, index=None):
    return d_operator(ctx, f, index)


# ====================================================================== integration
def _int_one(f, spec, numeric=False):
    if isinstance(spec, MEquation) and isinstance(spec.rhs, MRange):
        var, lo, hi = spec.lhs, spec.rhs.lo, spec.rhs.hi
        if numeric:
            return sp.Integral(f, (var, lo, hi)).evalf()
        r = sp.integrate(f, (var, lo, hi))
        if isinstance(r, sp.Integral) and (lo.has(sp.Float) or hi.has(sp.Float) or f.has(sp.Float)) \
                and lo.is_number and hi.is_number:
            return r.evalf()
        return r
    if isinstance(spec, MList):
        r = f
        for s in spec.items:
            r = _int_one(r, s, numeric)
        return r
    if isinstance(spec, (sp.Symbol, sp.Indexed)):
        return sp.integrate(f, spec)
    raise MapleError(f"integration range or variable must be specified in the second argument, "
                     f"got {lprint(spec)}")


@builtin(["int", "integrate"], sig="int(f, x) or int(f, x = a..b)", doc="Indefinite or definite integration.",
         options={"numeric": False, "method": None, "AllSolutions": False, "CauchyPrincipalValue": False})
def m_int(ctx, f, spec=None, *rest, numeric=False, method=None, **opts):
    if spec is None:
        raise MapleError("integration range or variable must be specified in the second argument")
    num = is_true(numeric)
    r = deep_map(lambda x: _int_one(x, spec, num), f)
    return ctx.evalf(r) if num else r


@builtin("Int", sig="Int(f, x = a..b)", doc="Inert integral.")
def m_Int(ctx, f, spec):
    if isinstance(spec, MEquation) and isinstance(spec.rhs, MRange):
        return Int(f, (spec.lhs, spec.rhs.lo, spec.rhs.hi))
    return Int(f, spec)


# ====================================================================== limits / series
def _limit_args(spec, dirn):
    if not isinstance(spec, MEquation):
        raise MapleError("invalid limiting point")
    d = str(dirn) if dirn is not None else None
    return spec.lhs, spec.rhs, {"right": "+", "left": "-"}.get(d, "+-")


@builtin("limit", sig="limit(f, x = a)", doc="Limit of f as x approaches a (optionally right/left).")
def m_limit(ctx, f, spec, dirn=None):
    x, a, d = _limit_args(spec, dirn)
    if isinstance(x, sp.Basic) and x.is_number:
        raise MapleError(f"limit variable previously assigned, 2nd argument evaluates to {lprint(spec)}")
    if a in (sp.oo, -sp.oo):
        d = "-" if a == sp.oo else "+"
    try:
        return deep_map(lambda e: sp.limit(e, x, a, d), f)
    except (ValueError, NotImplementedError):
        return sp.Limit(f, x, a, d if d != "+-" else "+")


@builtin("Limit", sig="Limit(f, x = a)", doc="Inert limit.")
def m_Limit(ctx, f, spec, dirn=None):
    x, a, d = _limit_args(spec, dirn)
    return Limit(f, x, a, d)


@builtin(["series", "taylor"], sig="series(f, x = a, n)", doc="Series expansion to order n (default 6).")
def m_series(ctx, f, spec, n=None):
    if isinstance(spec, MEquation):
        x, a = spec.lhs, spec.rhs
    else:
        x, a = spec, sp.Integer(0)
    order = int(n) if n is not None else 6
    return sp.series(f, x, a, order)
