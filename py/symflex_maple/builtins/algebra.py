"""Algebra: solve, fsolve, simplify, expand, factor, normal, collect, coeff, degree,
maximize/minimize.  First working versions; extend freely (see README.md)."""
from __future__ import annotations

import mpmath
import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..printer import lprint
from ..values import (
    NULL, ExprSeq, MEquation, MList, MRange, MRelation, MSet, deep_map, make_seq, seq_items,
)
from . import Library, is_true
from .core import as_items, equations_of, has_float, to_sympy

lib = Library()
builtin = lib.builtin


def register(env):
    lib.register(env)


# ====================================================================== solve
def _as_expr(e):
    """Equation/relation/expression -> expression equal to zero."""
    if isinstance(e, MEquation):
        return e.lhs - e.rhs
    if isinstance(e, sp.Basic):
        return e
    raise MapleError(f"invalid equation")


def unknowns_of(exprs) -> list:
    """Indeterminates to solve for when none are given: names and unknown function calls."""
    syms = set()
    for e in exprs:
        syms |= {s for s in e.free_symbols}
        syms |= set(e.atoms(AppliedUndef))
        syms |= set(e.atoms(sp.Indexed))
    # indexed names subsume their base/indices
    for ix in [s for s in syms if isinstance(s, sp.Indexed)]:
        syms.discard(ix.base.label)
        syms -= set(ix.indices) if all(isinstance(i, sp.Symbol) for i in ix.indices) else set()
    return sorted(syms, key=lambda s: str(s))


def _sol_dicts(exprs, vars_):
    try:
        sols = sp.solve(exprs, vars_, dict=True)
    except NotImplementedError:
        sols = []
    return sols


def solve_maple(ctx, eqs, vars_spec=None):
    """Core of solve(); returns a Maple-shaped value."""
    single_input = not isinstance(eqs, (MSet, MList)) and len(seq_items(eqs)) == 1
    eq_list = equations_of(eqs)
    exprs = []
    for e in eq_list:
        if isinstance(e, MRelation) and e.op != "=":
            raise MapleError("solving inequalities is not implemented yet in SymFlex")
        exprs.append(_as_expr(e))
    floats = has_float(eqs)
    if floats:
        exprs = [sp.nsimplify(x, rational=True) for x in exprs]
    if vars_spec is None:
        vars_ = unknowns_of(exprs)
        vars_shape = "set" if not (single_input and len(vars_) == 1) else "value"
    elif isinstance(vars_spec, MList):
        vars_ = list(vars_spec.items)
        vars_shape = "list"
    elif isinstance(vars_spec, MSet):
        vars_ = list(vars_spec.items)
        vars_shape = "set"
    else:
        vars_ = [vars_spec]
        vars_shape = "value" if single_input else "set"
    if not vars_:
        return NULL
    for v in vars_:
        if isinstance(v, sp.Basic) and v.is_number:
            raise MapleError(f"a constant is invalid as a variable, {lprint(v)}")
    sols = _sol_dicts(exprs, vars_)

    def fix(v):
        return _chop(ctx.evalf(v), ctx.digits) if floats else v
    if vars_shape == "value":
        x = vars_[0]
        vals = []
        for s in sols:
            if x in s:
                vals.append(fix(s[x]))
        if not vals and not sols:
            return NULL
        # Maple reports repeated roots of polynomials with multiplicity
        if len(exprs) == 1 and exprs[0].is_polynomial(x) and not floats:
            try:
                mult = sp.roots(sp.Poly(exprs[0], x))
                if mult and sum(mult.values()) == sp.degree(exprs[0], x):
                    vals = [fix(r) for r in mult for _ in range(mult[r])]
            except Exception:  # noqa: BLE001 - fall back to plain solutions
                pass
        return make_seq(vals)
    results = []
    for s in sols:
        eqs_out = [MEquation(v, fix(s.get(v, v))) for v in vars_]
        if vars_spec is None:
            eqs_out = [MEquation(v, fix(s[v])) for v in vars_ if v in s] + \
                [MEquation(v, v) for v in vars_ if v not in s]
        results.append(MList(eqs_out) if vars_shape == "list" else MSet(eqs_out))
    if vars_shape == "list":
        return MList(results)
    return make_seq(results)


def _chop(v, digits):
    """Drop round-off imaginary parts that exact radical formulas leave behind."""
    if isinstance(v, sp.Basic) and v.is_number:
        re_, im_ = v.as_real_imag()
        if im_ != 0 and abs(im_) <= sp.Float(10) ** (3 - digits) * max(1, abs(re_)):
            return re_
    return v


@builtin("solve", sig="solve(eqns, vars)", doc="Solve equations (or systems) exactly.",
         options={"explicit": None, "allsolutions": None, "useassumptions": None})
def m_solve(ctx, eqs, vars_spec=None, **opts):
    return solve_maple(ctx, eqs, vars_spec)


# ====================================================================== fsolve
def _lambdify(expr, var, dps):
    f = sp.lambdify(var, expr, modules="mpmath")

    def g(x):
        with mpmath.workdps(dps):
            return f(x)
    return g


def _real_roots_poly(expr, var, digits):
    p = sp.Poly(expr, var)
    roots = []
    for r in p.nroots(n=digits + 5, maxsteps=200):
        if abs(sp.im(r)) < sp.Float(10) ** (-digits):
            roots.append(sp.re(r))
    return sorted(roots)


def _bracket_roots(f, a, b, n=400):
    """Sign-change brackets of f on [a, b]."""
    xs = [a + (b - a) * i / n for i in range(n + 1)]
    out = []
    prev = None
    for x in xs:
        try:
            y = f(x)
            if isinstance(y, mpmath.mpc):
                y = y.real if abs(y.imag) < 1e-12 else None
        except (ZeroDivisionError, ValueError, OverflowError, TypeError):
            y = None
        if y is not None and prev is not None and prev[1] is not None:
            if y == 0:
                out.append((x, x))
            elif prev[1] * y < 0:
                out.append((prev[0], x))
        prev = (x, y)
    return out


def _fsolve1(ctx, expr, var, rng):
    digits = ctx.digits
    dps = digits + 6
    f = _lambdify(expr, var, dps)
    if rng is None and expr.is_polynomial(var):
        rr = _real_roots_poly(expr, var, digits)
        return [sp.Float(r, digits) for r in rr]
    candidates = []
    if rng is not None:
        a, b = (float(sp.N(rng.lo)), float(sp.N(rng.hi)))
        if expr.is_polynomial(var):
            rr = [r for r in _real_roots_poly(expr, var, digits) if a <= r <= b]
            return [sp.Float(r, digits) for r in rr[:1]] if rr else []
        brackets = _bracket_roots(f, a, b)
        for lo, hi in brackets:
            r = _refine(f, lo, hi, dps)
            if r is not None:
                return [sp.Float(r, digits)]
        # no sign change: try Newton from the middle
        r = _newton(f, (a + b) / 2, dps)
        if r is not None and a <= r <= b:
            return [sp.Float(r, digits)]
        return []
    for span in (1, 10, 100, 1000):
        brackets = _bracket_roots(f, -span, span, 200)
        if brackets:
            best = min(brackets, key=lambda br: abs(br[0] + br[1]))
            r = _refine(f, best[0], best[1], dps)
            if r is not None:
                candidates.append(r)
                break
    if not candidates:
        r = _newton(f, 0.5, dps)
        if r is not None:
            candidates.append(r)
    return [sp.Float(r, digits) for r in candidates[:1]]


def _refine(f, lo, hi, dps):
    with mpmath.workdps(dps):
        try:
            if lo == hi:
                return mpmath.mpf(lo)
            r = mpmath.findroot(f, (mpmath.mpf(lo), mpmath.mpf(hi)), solver="anderson")
            if isinstance(r, mpmath.mpc):
                r = r.real
            return r
        except (ValueError, ZeroDivisionError):
            try:
                return mpmath.findroot(f, (mpmath.mpf(lo), mpmath.mpf(hi)), solver="bisect")
            except Exception:  # noqa: BLE001
                return None


def _newton(f, x0, dps):
    with mpmath.workdps(dps):
        try:
            r = mpmath.findroot(f, mpmath.mpf(x0))
            if isinstance(r, mpmath.mpc):
                if abs(r.imag) > 1e-10:
                    return None
                r = r.real
            return r
        except Exception:  # noqa: BLE001
            return None


@builtin("fsolve", sig="fsolve(eqns, x = a..b)", doc="Numerical root finding.",
         options={"maxsols": None, "complex": None, "avoid": None, "fulldigits": None})
def m_fsolve(ctx, eqs, vars_spec=None, *rest, **opts):
    eq_list = equations_of(eqs)
    exprs = [_as_expr(e) for e in eq_list]
    ranges = {}
    vars_ = None
    if vars_spec is not None:
        specs = as_items(vars_spec)
        vars_ = []
        for s in specs:
            if isinstance(s, MEquation) and isinstance(s.rhs, MRange):
                ranges[s.lhs] = s.rhs
                vars_.append(s.lhs)
            elif isinstance(s, MEquation):
                ranges[s.lhs] = s.rhs   # starting point
                vars_.append(s.lhs)
            else:
                vars_.append(s)
    if vars_ is None:
        vars_ = unknowns_of(exprs)
    extra = sorted({str(s) for e in exprs for s in e.free_symbols} - {str(v) for v in vars_})
    if extra:
        names = extra[0] if len(extra) == 1 else "{" + ", ".join(extra) + "}"
        raise MapleError(f"{names} {'is' if len(extra) == 1 else 'are'} in the equation, "
                         f"and {'is' if len(extra) == 1 else 'are'} not solved for")
    if len(exprs) != len(vars_):
        raise MapleError(f"number of equations, {len(exprs)}, does not match number of "
                         f"variables, {len(vars_)}")
    if len(exprs) == 1 and len(vars_) == 1:
        x = vars_[0]
        rng = ranges.get(x)
        if rng is not None and not isinstance(rng, MRange):
            r = _newton(_lambdify(exprs[0], x, ctx.digits + 6), float(rng), ctx.digits + 6)
            return sp.Float(r, ctx.digits) if r is not None else NULL
        roots = _fsolve1(ctx, exprs[0], x, rng)
        if not roots:
            from ..evaluator import MCall
            return MCall(sp.Symbol("fsolve"), [eqs] + ([vars_spec] if vars_spec is not None else []))
        return make_seq(roots)
    # systems: Newton from range midpoints / given starts / 0.5
    start = []
    for v in vars_:
        r = ranges.get(v)
        if isinstance(r, MRange):
            start.append((float(sp.N(r.lo)) + float(sp.N(r.hi))) / 2)
        elif r is not None:
            start.append(float(sp.N(r)))
        else:
            start.append(0.5)
    fs = [sp.lambdify(vars_, e, modules="mpmath") for e in exprs]
    with mpmath.workdps(ctx.digits + 6):
        try:
            sol = mpmath.findroot(lambda *a: [f(*a) for f in fs], start)
        except Exception:  # noqa: BLE001
            from ..evaluator import MCall
            return MCall(sp.Symbol("fsolve"), [eqs, vars_spec] if vars_spec is not None else [eqs])
    vals = [sol] if len(vars_) == 1 else [sol[i] for i in range(len(vars_))]
    return MSet(MEquation(v, sp.Float(mpmath.re(x), ctx.digits)) for v, x in zip(vars_, vals))


# ====================================================================== simplification
def _map(f):
    return lambda ctx, e, *a: deep_map(lambda x: f(x, *a), e)


def _simplify(x, *opts):
    if opts and str(opts[0]) == "trig":
        return sp.trigsimp(x)
    r = sp.simplify(x)
    return r


lib.builtin("simplify", sig="simplify(expr)", doc="Simplify an expression.")(_map(_simplify))
lib.builtin("expand", sig="expand(expr)", doc="Expand products and powers.")(
    _map(lambda x, *a: sp.expand(x, trig=False) if not a else sp.expand(x)))
lib.builtin("normal", sig="normal(expr)", doc="Normalize a rational expression.")(
    _map(lambda x, *a: sp.cancel(sp.together(x))))
lib.builtin("combine", sig="combine(expr)", doc="Combine terms (powers, trig, exp, ln).")(
    _map(lambda x, *a: sp.powsimp(sp.trigsimp(x))))
lib.builtin("rationalize", sig="rationalize(expr)", doc="Rationalize the denominator.")(
    _map(lambda x, *a: sp.radsimp(x)))


@builtin("factor", sig="factor(expr)", doc="Factor a polynomial or rational expression.")
def m_factor(ctx, e, *ext):
    return deep_map(lambda x: sp.factor(x), e)


@builtin("collect", sig="collect(expr, x)", doc="Collect coefficients of powers of x.")
def m_collect(ctx, e, x, *opts):
    xs = as_items(x)
    return deep_map(lambda v: sp.collect(sp.expand(v), xs if len(xs) > 1 else xs[0]), e)


@builtin("coeff", sig="coeff(p, x, n)", doc="Coefficient of x^n in a polynomial.")
def m_coeff(ctx, p, x, n=None):
    p = sp.expand(p)
    if n is not None:
        return p.coeff(x, n)
    if isinstance(x, sp.Pow) and x.exp.is_Integer:
        return p.coeff(x.base, x.exp)
    return p.coeff(x)


@builtin("coeffs", sig="coeffs(p, x)", doc="Sequence of coefficients.")
def m_coeffs(ctx, p, x=None):
    poly = sp.Poly(p, *( [x] if x is not None else []))
    return make_seq([c for c in poly.coeffs()])


@builtin("degree", sig="degree(p, x)", doc="Degree of a polynomial.")
def m_degree(ctx, p, x=None):
    if x is None:
        return sp.Integer(sp.Poly(p).total_degree())
    return sp.degree(p, x)


@builtin("ldegree", sig="ldegree(p, x)", doc="Low degree of a polynomial.")
def m_ldegree(ctx, p, x):
    return sp.Integer(min(m[0] for m in sp.Poly(p, x).monoms()))


@builtin("lcoeff", sig="lcoeff(p, x)", doc="Leading coefficient.")
def m_lcoeff(ctx, p, x=None):
    return sp.Poly(p, *([x] if x is not None else [])).LC()


@builtin("quo", sig="quo(a, b, x)", doc="Polynomial quotient.")
def m_quo(ctx, a, b, x):
    return sp.quo(a, b, x)


@builtin("rem", sig="rem(a, b, x)", doc="Polynomial remainder.")
def m_rem(ctx, a, b, x):
    return sp.rem(a, b, x)


@builtin("isolate", sig="isolate(eqn, x)", doc="Isolate x on the left-hand side.")
def m_isolate(ctx, eq, x):
    sols = sp.solve(_as_expr(eq), x)
    if not sols:
        return eq
    return MEquation(x, sols[0])


# ====================================================================== optimisation
def _extremum(ctx, e, rng_spec, sign, location):
    var = None
    lo = hi = None
    if isinstance(rng_spec, MEquation) and isinstance(rng_spec.rhs, MRange):
        var, lo, hi = rng_spec.lhs, rng_spec.rhs.lo, rng_spec.rhs.hi
    else:
        syms = sorted(e.free_symbols, key=str)
        if len(syms) != 1:
            raise MapleError("only single-variable maximize/minimize is implemented")
        var = syms[0]
    cands = []
    try:
        crit = sp.solve(sp.diff(e, var), var)
    except NotImplementedError:
        crit = []
    for c in crit:
        if c.is_real is False or (c.is_number and sp.im(sp.N(c)) != 0):
            continue
        if lo is not None and c.is_number and not (sp.N(lo) <= sp.N(c) <= sp.N(hi)):
            continue
        cands.append(c)
    if lo is not None:
        cands += [lo, hi]
    if not cands:
        if lo is None:
            return sign * sp.oo
        cands = [lo, hi]
    vals = [(sp.simplify(e.subs(var, c)), c) for c in cands]
    num = [(v, c) for v, c in vals if v.is_number]
    if lo is None:
        lim_vals = [sp.limit(e, var, sp.oo), sp.limit(e, var, -sp.oo)]
        for lv in lim_vals:
            if (sign > 0 and lv == sp.oo) or (sign < 0 and lv == -sp.oo):
                return lv
    if not num:
        raise MapleError("unable to find extrema")
    best_val = max(num, key=lambda p: sign * float(sp.N(p[0])))[0]
    if has_float(e) or has_float(rng_spec):
        best_val = ctx.evalf(best_val)
    if not location:
        return best_val
    locs = [MList([MSet([MEquation(var, c)]), v]) for v, c in num
            if sp.simplify(v - best_val) == 0 or abs(float(sp.N(v - best_val))) < 1e-9]
    return ExprSeq([best_val, MSet(locs)])


@builtin("maximize", sig="maximize(expr, x = a..b)", doc="Maximum value of an expression.",
         options={"location": False})
def m_maximize(ctx, e, rng=None, *rest, location=False):
    return _extremum(ctx, e, rng, 1, is_true(location))


@builtin("minimize", sig="minimize(expr, x = a..b)", doc="Minimum value of an expression.",
         options={"location": False})
def m_minimize(ctx, e, rng=None, *rest, location=False):
    return _extremum(ctx, e, rng, -1, is_true(location))
