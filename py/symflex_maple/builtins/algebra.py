"""Algebra: solve, fsolve, simplify, expand, factor, normal, collect, coeff, degree,
maximize/minimize.  First working versions; extend freely (see README.md)."""
from __future__ import annotations

import mpmath
import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.simplify.fu import TR8

from ..errors import MapleError
from ..printer import lprint
from ..values import (
    NULL, ExprSeq, MEquation, MList, MRange, MRelation, MSet, deep_map, make_seq, seq_items,
)
from . import Library, is_true
from .algebra_roots import generic_point, maple_root_order, principal_solutions, reorder
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


def _sol_dicts(exprs, vars_, floats=False):
    # SymPy only solves through abs() for real unknowns
    real = {v: sp.Dummy(v.name, real=True) for v in vars_
            if isinstance(v, sp.Symbol) and any(e.has(sp.Abs) for e in exprs)}
    try:
        sols = sp.solve([e.xreplace(real) for e in exprs], [real.get(v, v) for v in vars_], dict=True)
    except NotImplementedError:
        sols = []
    if real:
        back = {d: v for v, d in real.items()}
        sols = [{back.get(k, k): val.xreplace(back) for k, val in s.items()} for s in sols]
    if not sols and floats and len(exprs) == len(vars_) == 1 and exprs[0].is_polynomial(vars_[0]):
        # no radical formula (quintic and up): numeric roots are all Maple shows anyway
        x = vars_[0]
        num = sp.together(exprs[0]).as_numer_denom()[0]
        sols = [{x: r} for r in sp.Poly(num, x).all_roots()]
    return sols


def solve_maple(ctx, eqs, vars_spec=None):
    """Core of solve(); returns a Maple-shaped value."""
    single_input = not isinstance(eqs, (MSet, MList)) and len(seq_items(eqs)) == 1
    eq_list = equations_of(eqs)
    exprs, rels = [], []
    for e in eq_list:
        if isinstance(e, MRelation) and e.op != "=":
            rels.append(e)
        else:
            exprs.append(_as_expr(e))
    floats = has_float(eqs)
    if floats:
        exprs = [sp.nsimplify(x, rational=True) for x in exprs]
    if vars_spec is None:
        vars_ = unknowns_of([side for e in eq_list for side in
                             ((e.lhs, e.rhs) if isinstance(e, MRelation) else (e,))
                             if isinstance(side, sp.Basic)])
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
    if rels and not exprs:
        return _solve_inequalities(ctx, rels, vars_, vars_shape, floats)
    if all(sp.expand(e) == 0 for e in exprs):   # an identity: every unknown is free
        sols = [{v: v for v in vars_}]
    else:
        sols = _sol_dicts(exprs, vars_, floats)
    if rels:
        sols = [s for s in sols if all(_holds(r, s) for r in rels)]
        if vars_shape == "value":
            vars_shape = "set"

    def fix(v):
        if not floats:
            return v
        v = _chop(ctx.evalf(v), ctx.digits)
        return sp.Float(v, ctx.digits) if isinstance(v, sp.Rational) else v
    if len(exprs) == 1 and len(vars_) == 1 and not rels:
        x = vars_[0]
        principal = principal_solutions(exprs[0], x, floats) if isinstance(x, sp.Symbol) else None
        if principal is not None:
            sols = [{x: v} for v in principal]
        ordered = _maple_order(exprs[0], x, sols, floats)
        if ordered is not None:
            sols = ordered
        elif vars_shape == "value" and not floats and exprs[0].is_polynomial(x):
            # Maple reports repeated roots of polynomials with multiplicity
            try:
                mult = sp.roots(sp.Poly(exprs[0], x))
                if mult and sum(mult.values()) == sp.degree(exprs[0], x):
                    sols = [{x: r} for r in mult for _ in range(mult[r])]
            except Exception:  # noqa: BLE001 - fall back to plain solutions
                pass
    if vars_shape == "value":
        x = vars_[0]
        if not sols:
            return NULL
        return make_seq([fix(s[x]) for s in sols if x in s])
    if len(vars_) > 1:
        sols = _order_system(sols, exprs, vars_, floats)
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


def _order_system(sols, exprs, vars_, floats):
    """Order the solutions of a system as Maple tends to (fitted to cmaple's output; its
    order is not documented): by the roots of an equation in a single unknown if there
    is one, else increasing in the alphabetically last unknown when its values are
    rational, and decreasing in the last unknown asked for when they involve radicals."""
    if len(sols) < 2:
        return sols
    if not floats:
        for e in exprs:
            us = [v for v in vars_ if e.has(v)]
            if len(us) == 1 and (ordered := _maple_order(e, us[0], sols, floats)):
                return ordered
    radical = any(not p.exp.is_Integer for s in sols for v in s.values() for p in v.atoms(sp.Pow))
    key_var = vars_[-1] if radical else max(vars_, key=str)
    vals = [s.get(key_var) for s in sols]
    if any(v is None for v in vals):
        return sols
    point = generic_point(set().union(*(v.free_symbols for v in vals)))
    try:
        keys = [complex(sp.N(v.xreplace(point))) for v in vals]
    except TypeError:
        return sols
    if any(abs(k.imag) > 1e-12 * max(1.0, abs(k)) for k in keys):
        return sols
    order = sorted(range(len(sols)), key=lambda i: keys[i].real, reverse=radical)
    return [sols[i] for i in order]


def _maple_order(expr, x, sols, floats):
    """sols (dicts) reordered like Maple lists the roots of a univariate polynomial."""
    if not sols or any(x not in s for s in sols):
        return None
    ref = maple_root_order(expr, x, floats)
    if ref is None:
        return None
    return reorder(sols, lambda s: s[x], *ref)


def _holds(rel, sol) -> bool:
    """Does the solution satisfy the inequality?  Parameters are taken to be generic
    positive values (Maple keeps x = a^(1/2) for x > 0); undecidable counts as yes."""
    d = (rel.lhs - rel.rhs).subs(sol)
    d = sp.N(d.xreplace(generic_point(d.free_symbols)))
    if not d.is_number or not d.is_real:
        return d.is_real is not False
    return {"<": d < 0, "<=": d <= 0, "<>": d != 0}[rel.op] == sp.true


def _solve_inequalities(ctx, rels, vars_, vars_shape, floats):
    if len(vars_) != 1:
        raise MapleError("solving inequalities in several variables is not implemented in SymFlex")
    x = vars_[0]
    xr = sp.Dummy(str(x), real=True)
    region = sp.S.Reals
    for r in rels:
        rel = to_sympy(r).xreplace({x: xr})
        if floats:
            rel = sp.nsimplify(rel, rational=True)
        try:
            region = region.intersect(sp.solve_univariate_inequality(rel, xr, relational=False))
        except (NotImplementedError, ValueError) as exc:
            raise MapleError(f"cannot solve the inequality {lprint(r)}") from exc
    num = (lambda v: ctx.evalf(v)) if floats else (lambda v: v)
    parts = list(region.args) if isinstance(region, sp.Union) else [region]
    if vars_shape == "value":
        if region == sp.S.Reals:
            return x
        out = []
        for p in parts:
            if isinstance(p, sp.FiniteSet):
                out += [num(v) for v in p]
            elif isinstance(p, sp.Interval):
                out.append(sp.Function("RealRange")(
                    _end(num(p.start), p.left_open), _end(num(p.end), p.right_open)))
        return make_seq(out)
    out = []
    for p in parts:
        if isinstance(p, sp.FiniteSet):
            out += [MSet([MEquation(x, num(v))]) for v in p]
        elif isinstance(p, sp.Interval):
            conds = []
            if p.start != -sp.oo:
                conds.append(MRelation("<" if p.left_open else "<=", num(p.start), x))
            if p.end != sp.oo:
                conds.append(MRelation("<" if p.right_open else "<=", x, num(p.end)))
            out.append(MSet(conds or [MEquation(x, x)]))
    return make_seq(out)


def _end(v, open_):
    return sp.Function("Open")(v) if open_ and v.is_finite else v


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
def _dec(r, digits):
    """r rounded to `digits` decimal digits, as Maple's decimal floats are (a binary
    rounding keeps tail bits that show up after cancellation, e.g. x1 - x2)."""
    return sp.Float(mpmath.nstr(mpmath.mpf(r), digits, min_fixed=-mpmath.inf, max_fixed=mpmath.inf), digits)


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
        return [_dec(r, digits) for r in rr]
    candidates = []
    if rng is not None:
        a, b = (float(sp.N(rng.lo)), float(sp.N(rng.hi)))
        if expr.is_polynomial(var):
            return [_dec(r, digits) for r in _real_roots_poly(expr, var, digits) if a <= r <= b]
        brackets = _bracket_roots(f, a, b)
        for lo, hi in brackets:
            r = _refine(f, lo, hi, dps)
            if r is not None:
                # a root at 0 is found only to within the bracketing round-off
                return [_dec(0 if abs(r) < 1e-20 * max(1, abs(a), abs(b)) else r, digits)]
        # no sign change: try Newton from the middle
        r = _newton(f, (a + b) / 2, dps)
        if r is not None and a <= r <= b:
            return [_dec(r, digits)]
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
    return [_dec(r, digits) for r in candidates[:1]]


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
    from ..evaluator import MCall
    if len(exprs) == 1 and len(vars_) == 1:
        x = vars_[0]
        expr = exprs[0]
        rng = ranges.get(x)
        poly = sp.together(expr).as_numer_denom()[0]
        is_poly = poly.is_polynomial(x)
        if is_true(opts.get("complex")) or any(str(r) == "complex" for r in rest):
            roots = _fsolve_complex(ctx, poly if is_poly else expr, x, is_poly)
        elif rng is not None and not isinstance(rng, MRange) and not is_poly:
            r = _newton(_lambdify(expr, x, ctx.digits + 6), float(rng), ctx.digits + 6)
            roots = [_dec(r, ctx.digits)] if r is not None else []
        else:
            roots = _fsolve1(ctx, expr, x, rng if isinstance(rng, MRange) else None)
        if opts.get("maxsols") is not None:
            roots = roots[:int(opts["maxsols"])]
        if not roots:
            if is_poly:   # a polynomial with no (real) roots in the range
                return NULL
            return MCall(sp.Symbol("fsolve"), [eqs, x] + ([rng] if rng is not None else []))
        return make_seq(roots)
    # systems: Newton from range midpoints / given starts, else from a few generic points
    fixed = {v: (float(sp.N(r.lo)) + float(sp.N(r.hi))) / 2 if isinstance(r, MRange)
             else float(sp.N(r)) for v, r in ranges.items()}
    if len(fixed) == len(vars_):
        starts = [[fixed[v] for v in vars_]]
    else:
        starts = [[fixed.get(v, 0.5 + 0.37 * i) * sgn for i, v in enumerate(vars_)]
                  for sgn in (1, -1, 3, -3)]
    fs = [sp.lambdify(vars_, e, modules="mpmath") for e in exprs]
    sol = None
    with mpmath.workdps(ctx.digits + 6):
        for start in starts:
            try:
                sol = mpmath.findroot(lambda *a: [f(*a) for f in fs], start)
                break
            except Exception:  # noqa: BLE001 - try the next start
                continue
    if sol is None:
        return MCall(sp.Symbol("fsolve"), [eqs, vars_spec] if vars_spec is not None else [eqs])
    vals = [sol] if len(vars_) == 1 else [sol[i] for i in range(len(vars_))]
    return MSet(MEquation(v, _dec(mpmath.re(x), ctx.digits)) for v, x in zip(vars_, vals))


def _fsolve_complex(ctx, expr, x, is_poly):
    """fsolve(..., complex): every root of a polynomial (sorted by real, then imaginary
    part, like Maple), else one root found by Newton from a complex start."""
    digits = ctx.digits
    if is_poly:
        roots = sp.Poly(sp.nsimplify(expr, rational=True), x).nroots(n=digits + 5, maxsteps=200)
        roots = sorted((complex(r) for r in roots), key=lambda z: (round(z.real, digits), z.imag))
    else:
        f = _lambdify(expr, x, digits + 6)
        with mpmath.workdps(digits + 6):
            try:
                roots = [complex(mpmath.findroot(f, mpmath.mpc(0.5, -0.5)))]
            except Exception:  # noqa: BLE001 - no convergence: unevaluated
                return []

    def num(z):
        re_ = _dec(z.real, digits) if abs(z.real) > 1e-14 * abs(z) else sp.S.Zero
        im_ = _dec(z.imag, digits) if abs(z.imag) > 1e-14 * abs(z) else sp.S.Zero
        return re_ + im_ * sp.I if im_ else re_
    return [num(z) for z in roots]


# ====================================================================== simplification
def _map(f):
    return lambda ctx, e, *a: deep_map(lambda x: f(x, *a), e)


def _simplify(x, *opts):
    names = {str(o) for o in opts}
    if "trig" in names:
        return sp.trigsimp(x)
    if "symbolic" in names:   # take every name to be positive, so sqrt(x^2) = x
        pos = {v: sp.Dummy(v.name, positive=True) for v in x.free_symbols}
        return sp.simplify(x.xreplace(pos)).xreplace({d: v for v, d in pos.items()})
    return sp.simplify(x)


def _expand(x, *keep):
    """Maple's expand: products, powers and trig/exp of sums; a denominator stays as it
    is and the expanded numerator is distributed over it.  Arguments after the first are
    subexpressions to leave alone."""
    hold = {k: sp.Dummy() for k in keep if isinstance(k, sp.Basic)}
    x = x.subs(hold) if hold else x
    out = []
    for t in sp.Add.make_args(x):
        n, d = sp.fraction(t)
        out += [m / d for m in sp.Add.make_args(sp.expand(n, trig=True))]
    return sp.Add(*out).subs({d: k for k, d in hold.items()})


def _combine(x, *opts):
    names = {str(o) for o in opts}
    if "trig" in names:
        return TR8(x)
    if names & {"exp", "power"}:
        return sp.powsimp(x)
    if "ln" in names:
        return sp.logcombine(x, force="symbolic" in names)
    return sp.logcombine(sp.powsimp(TR8(x)), force="symbolic" in names)


lib.builtin("simplify", sig="simplify(expr)", doc="Simplify an expression.")(_map(_simplify))
lib.builtin("expand", sig="expand(expr)", doc="Expand products and powers.")(_map(_expand))
lib.builtin("normal", sig="normal(expr)", doc="Normalize a rational expression.")(
    _map(lambda x, *a: sp.cancel(sp.together(x))))
lib.builtin("combine", sig="combine(expr)", doc="Combine terms (powers, trig, exp, ln).")(
    _map(_combine))
lib.builtin("rationalize", sig="rationalize(expr)", doc="Rationalize the denominator.")(
    _map(lambda x, *a: sp.radsimp(x)))


@builtin("factor", sig="factor(expr)", doc="Factor a polynomial or rational expression.")
def m_factor(ctx, e, *ext):
    return deep_map(lambda x: sp.factor(x), e)


@builtin("collect", sig="collect(expr, x)", doc="Collect coefficients of powers of x.")
def m_collect(ctx, e, x, *opts):
    return deep_map(lambda v: _collect(v, as_items(x)), e)


def _collect(v, xs):
    """collect(v, [x, y]) is recursive like Maple's: ((a+b)*y+c)*x."""
    if not xs:
        return v
    parts = sp.collect(sp.expand(v), xs[0], evaluate=False)
    return sp.Add(*[k * _collect(c, xs[1:]) for k, c in parts.items()])


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
    sols = seq_items(solve_maple(ctx, eq, x))
    if not sols:
        return eq
    return MEquation(x, sols[0])


# ====================================================================== optimisation
def _extremum(ctx, e, rng_spec, sign, location):
    if isinstance(rng_spec, MEquation) and isinstance(rng_spec.rhs, MRange):
        var, window = rng_spec.lhs, sp.Interval(rng_spec.rhs.lo, rng_spec.rhs.hi)
    elif rng_spec is None:
        syms = sorted(e.free_symbols, key=str)
        if len(syms) > 1:
            raise MapleError("only single-variable maximize/minimize is implemented")
        if not syms:
            return ExprSeq([e, MSet([MList([MSet([]), e])])]) if location else e
        var, window = syms[0], sp.S.Reals
    else:
        raise MapleError(f"invalid range {lprint(rng_spec)}")
    rng_var = var
    floats = has_float(e) or has_float(rng_spec)
    xr = sp.Dummy(str(var), real=True)
    f = e.xreplace({var: xr})
    if f.has(sp.Abs, sp.Max, sp.Min, sp.Heaviside, sp.sign):
        f = f.rewrite(sp.Piecewise)
    f, var = sp.piecewise_fold(f), xr
    pairs = f.as_expr_set_pairs() if isinstance(f, sp.Piecewise) else [(f, sp.S.Reals)]
    cands, symbolic = [], []                     # (value, point or None); values with parameters
    for expr, where in pairs:
        where = where.intersect(window)
        for part in (where.args if isinstance(where, sp.Union) else [where]):
            if isinstance(part, sp.FiniteSet):
                points = list(part)
            elif isinstance(part, sp.Interval):
                points = [x for x in (part.start, part.end) if x.is_finite]
                points += _critical_points(ctx, expr, var, part, floats)
                for end, inf in ((part.start, -sp.oo), (part.end, sp.oo)):
                    if end == inf:
                        lim = sp.limit(sp.nsimplify(expr, rational=True) if floats else expr, var, inf)
                        if lim == sign * sp.oo:
                            return ExprSeq([lim, MSet([])]) if location else lim
                        if lim.is_number and lim.is_real and lim.is_finite:
                            cands.append((lim, None))
            else:
                continue
            for c in points:
                v = expr.subs(var, c)
                v = sp.N(v, ctx.digits + 5) if floats else sp.simplify(v)
                if v.is_number and v.is_real:
                    cands.append((v, c))
                elif not v.is_number:
                    symbolic.append(v)
    if symbolic:
        vals = list(dict.fromkeys([v for v, _ in cands] + symbolic))
        return vals[0] if len(vals) == 1 else sp.Function("max" if sign > 0 else "min")(*vals)
    if not cands:
        raise MapleError("unable to find extrema")
    best = max(cands, key=lambda vc: sign * float(vc[0]))[0]
    tol = 1e-9 * max(1.0, abs(float(best)))

    def fix(v):   # numeric critical points of exact input also come out as floats
        return _dec(v, ctx.digits) if floats or isinstance(v, sp.Float) else v
    if not location:
        return fix(best)
    locs, seen = [], set()
    for v, c in cands:
        if c is not None and abs(float(v - best)) <= tol and c not in seen:
            seen.add(c)
            locs.append(MList([MSet([MEquation(rng_var, fix(c))]), fix(v)]))
    return ExprSeq([fix(best), MSet(locs)])


def _critical_points(ctx, expr, var, part, floats):
    """Zeros of d/dvar expr inside the interval: exact for exact input, else numeric."""
    d = sp.diff(expr, var)
    if d == 0:
        return []

    def inside(c):
        return c.is_number and c.is_real is not False and abs(sp.im(sp.N(c))) < 1e-12 \
            and part.closure.contains(sp.re(sp.N(c))) == sp.true
    if not floats:
        try:
            return [c for c in sp.solve(d, var) if inside(c)]
        except NotImplementedError:
            pass
    q = sp.nsimplify(d, rational=True) if floats else d
    num = sp.together(q).as_numer_denom()[0]
    if num.is_polynomial(var):
        roots = sp.Poly(num, var).nroots(n=ctx.digits + 5, maxsteps=200)
        return [sp.re(r) for r in roots if inside(r)]
    # transcendental: sign changes of the derivative on a finite window of the interval
    ends = [abs(float(x)) for x in (part.start, part.end) if x.is_finite]
    span = 10 * max([10.0] + ends)
    a = float(part.start) if part.start.is_finite else -span
    b = float(part.end) if part.end.is_finite else span
    g = _lambdify(d, var, ctx.digits + 6)
    out = []
    for lo, hi in _bracket_roots(g, a, b):
        r = _refine(g, lo, hi, ctx.digits + 6)
        if r is not None and a <= r <= b:
            out.append(sp.Float(r, ctx.digits + 5))
    return out


@builtin("maximize", sig="maximize(expr, x = a..b)", doc="Maximum value of an expression.",
         options={"location": False})
def m_maximize(ctx, e, rng=None, *rest, location=False):
    return _extremum(ctx, e, rng, 1, is_true(location))


@builtin("minimize", sig="minimize(expr, x = a..b)", doc="Minimum value of an expression.",
         options={"location": False})
def m_minimize(ctx, e, rng=None, *rest, location=False):
    return _extremum(ctx, e, rng, -1, is_true(location))
