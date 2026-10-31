"""Calculus: diff, D, int, limit, series and their inert forms.  First working versions."""
from __future__ import annotations

import sympy as sp
from sympy.core.function import AppliedUndef
from mpmath.libmp import prec_to_dps

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


def _integral_evalf(self, prec):
    """evalf of our Integral subclasses (SymPy's evalf table only knows Integral itself)."""
    if any(len(lim) == 3 and (lim[2] - lim[1]).is_zero for lim in self.limits):
        return sp.Float(0, precision=prec)
    r = sp.Integral(*self.args).evalf(prec_to_dps(prec))
    return type(self)(*r.args) if isinstance(r, sp.Integral) else r


# Inert forms print with Maple's capitalised names (Int, Limit, ...); value() evaluates them.
class Int(sp.Integral):
    _eval_evalf = _integral_evalf


class Limit(sp.Limit):
    def _eval_evalf(self, prec):
        r = sp.Limit(*self.args).doit()
        return None if r.has(sp.Limit) else r.evalf(prec_to_dps(prec))


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


class _Abs(sp.Function):
    """abs while differentiating: SymPy's derivative of abs(x) for complex x is Re/Im noise;
    Maple's abs(1, x) is signum(x) for real x."""

    def fdiff(self, argindex=1):
        return sp.sign(self.args[0])


class Diff(sp.Derivative):
    """Inert derivative (prints as Diff); value() evaluates it."""


def diff_value(e, vars_):
    if not vars_:
        return e

    def d(x):
        if not isinstance(x, sp.Basic):
            return x
        r = x.replace(sp.Abs, _Abs)
        for v in vars_:
            if isinstance(v, AppliedUndef):
                tmp = sp.Dummy("f")
                r = sp.diff(r.subs(v, tmp), tmp).subs(tmp, v)
            else:
                r = sp.diff(r, v)
        return r.replace(_Abs, sp.Abs)
    return deep_map(d, e)


@builtin("diff", sig="diff(f, x1, ..., xn)", doc="Differentiate f with respect to x1, ..., xn (diff(f, x$2) for 2nd derivative).")
def m_diff(ctx, e, *vars_):
    if not vars_:
        raise MapleError("invalid input: diff expects 2 or more arguments, but received 1")
    return diff_value(e, _diff_vars(vars_))


@builtin("Diff", sig="Diff(f, x)", doc="Inert derivative.")
def m_Diff(ctx, e, *vars_):
    return Diff(e, *_diff_vars(vars_), evaluate=False)


@builtin("value", sig="value(expr)", doc="Evaluate inert forms (Int, Diff, Sum, Limit).")
def m_value(ctx, e):
    def integral(z):
        f = z.function
        for lim in z.limits:
            f = integrate(ctx, f, *lim)
        return f

    def ev(x):
        x = x.replace(lambda z: isinstance(z, Int), integral)
        return x.replace(lambda z: isinstance(z, (Limit, sp.Derivative, sp.Sum, sp.Product)),
                         lambda z: (sp.Limit(*z.args) if isinstance(z, Limit) else z).doit())
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
        if isinstance(f, BuiltinProc) and isinstance(body, sp.Function) and body.args == tuple(vs):
            g = ctx.lookup(lprint(body).split("(")[0])
            if isinstance(g, BuiltinProc):
                return g    # D(sin) = cos, D(exp) = exp
        return lambda_proc(vs, body)
    if isinstance(f, sp.Basic) and f.is_number:
        return sp.Integer(0)
    raise MapleError(f"invalid input: D expects a procedure, received {lprint(f)}")


@builtin("D", sig="D(f) or D[i](f)", doc="Differential operator: D(f)(x) is the derivative of f at x.",
         indexed=True)
def m_D(ctx, f, index=None):
    return d_operator(ctx, f, index)


# ====================================================================== integration
class UnevalInt(sp.Integral):
    """An integral Maple leaves unevaluated (prints as int).  simplify normalises it like Maple:
    floats in the integrand become rationals and the constant factor is pulled out."""
    _eval_evalf = _integral_evalf

    def _eval_simplify(self, **kwargs):
        f = self.function
        n, d = sp.fraction(sp.cancel(sp.together(_rational(f))))
        cn, n = n.as_content_primitive()
        cd, d = d.as_content_primitive()
        c = cn / cd
        if f.has(sp.Float):
            c = sp.Float(c, precision=max(a._prec for a in f.atoms(sp.Float)))
        return c * type(self)(n / d, *self.limits)


def _rational(e):
    return sp.nsimplify(e, rational=True) if e.has(sp.Float) else e


def _at(F, x, c, dirn):
    """F at x = c, as a one-sided limit where F is singular there (x*ln(x) at 0)."""
    v = F.subs(x, c)
    if v.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        v = sp.limit(F, x, c, dirn)
    return v


def _real_logs(F, x, s):
    """ln(u) -> ln(-u) wherever u < 0 at x = s: still an antiderivative (they differ by the
    constant I*Pi) but real near s, like Maple's ln(-t+20)."""
    rep = {}
    for lg in F.atoms(sp.log):
        u = lg.args[0]
        if u.has(x) and (v := u.subs(x, s)).is_number and v.is_extended_negative:
            rep[lg] = sp.log(sp.expand(-u))
    return F.xreplace(rep)


def _antiderivative(f, x):
    # conds='none': Maple gives the generic answer, not SymPy's special cases (mu = I/2, a = 0)
    # meijerg=False: its indefinite results are meijerg() terms Maple never shows (Heaviside)
    F = sp.integrate(f, x, conds="none", meijerg=False)
    if F.has(sp.Integral):
        return None
    params = f.free_symbols - {x}
    if params and F.has(sp.I) and not f.has(sp.I):
        # Maple takes parameters as real: arctan(x/a)/a rather than SymPy's complex logs.  SymPy
        # is buggy with real symbols (1/(a - x^2) integrates to 0), so the result is checked.
        real = {s: sp.Dummy(s.name, real=True) for s in params}
        fr = f.xreplace(real)
        G = sp.integrate(fr, x, conds="none", meijerg=False)
        if not G.has(sp.Integral, sp.Piecewise, sp.I) and _is_antiderivative(G, fr, x):
            F = G.xreplace({v: k for k, v in real.items()})
    return F


def _is_antiderivative(F, f, x):
    dF = sp.diff(F, x)
    syms = sorted(dF.free_symbols | f.free_symbols, key=str)
    for k in range(3):
        pt = {s: sp.Float(0.37 + 0.61 * i + 0.29 * k) for i, s in enumerate(syms)}
        a, b = complex(dF.xreplace(pt).evalf(15)), complex(f.xreplace(pt).evalf(15))
        if abs(a - b) > 1e-8 * (1 + abs(b)):
            return False
    return True


def _pw_antiderivative(f, x):
    """Continuous antiderivative of a piecewise in x, Maple-shaped
    PIECEWISE([F1, x <= b1], ..., [Fn, b(n-1) < x]); None unless all breakpoints are numbers."""
    pts = set()
    for _, c in f.args:
        for r in c.atoms(sp.core.relational.Relational):
            d = r.lhs - r.rhs
            if d.free_symbols != {x} or not d.is_polynomial(x) or (p := sp.Poly(d, x)).degree() != 1:
                return None
            pts.add(-p.nth(0) / p.nth(1))
    pts = sorted(pts)
    if not pts:
        return None
    samples = [pts[0] - 1, *((a + b) / 2 for a, b in zip(pts, pts[1:])), pts[-1] + 1]
    pieces = []
    for s in samples:
        e = next((e for e, c in f.args if c.subs(x, s) == sp.true), sp.Integer(0))
        G = _antiderivative(e, x)
        if G is None:
            return None
        pieces.append(_real_logs(G, x, s))
    out, C = [pieces[0]], sp.Integer(0)
    for i, b in enumerate(pts):
        C += _at(pieces[i], x, b, "-") - _at(pieces[i + 1], x, b, "+")
        out.append(pieces[i + 1] + C)
    return sp.Piecewise(*[(G, x <= b) for G, b in zip(out, pts)], (out[-1], x > pts[-1]))


def _poles(f, x):
    """Real poles of f in x (roots of the polynomial factors of its denominator); for a
    piecewise only those inside their own branch."""
    if isinstance(f, sp.Piecewise):
        out, before = [], sp.false
        for e, c in f.args:
            out += [p for p in _poles(e, x) if sp.And(c, sp.Not(before)).subs(x, p) != sp.false]
            before = sp.Or(before, c)
        return out
    out = []
    for fac in sp.Mul.make_args(sp.denom(sp.together(f))):
        b = fac.as_base_exp()[0]
        if not (b.has(x) and b.is_polynomial(x)):
            continue
        p = sp.Poly(b, x)
        if p.free_symbols == {x}:
            out += p.real_roots()
        elif p.degree() <= 2:    # shortcut: symbolic poles only from linear and quadratic factors
            # Maple takes the parameters as real: x^2 + a^2 has no real pole, g - k*x^2 may have
            real = {s: sp.Dummy(s.name, real=True, nonzero=True) for s in p.free_symbols - {x}}
            out += [r for r in sp.roots(p, multiple=True) if r.xreplace(real).is_real is not False]
    return list(dict.fromkeys(out))


def _bounds(ctx, e):
    """((lower, strict), (upper, strict)) bounds of a limit of integration known from assume()."""
    if e.is_number:
        return (e, False), (e, False)
    lo, hi = (-sp.oo, False), (sp.oo, False)

    def tighter(new, old, up):
        if new[0] == old[0]:
            return old[0], old[1] or new[1]
        return new if bool(new[0] < old[0]) == up else old

    if isinstance(e, sp.Symbol):
        for rel in ctx.assumptions.get(e.name, []):
            if isinstance(rel, MRelation) and rel.op in ("<", "<="):
                if rel.lhs == e and rel.rhs.is_number:
                    hi = tighter((rel.rhs, rel.op == "<"), hi, True)
                elif rel.rhs == e and rel.lhs.is_number:
                    lo = tighter((rel.lhs, rel.op == "<"), lo, False)
            elif str(rel) in ("positive", "nonnegative"):
                lo = tighter((sp.Integer(0), str(rel) == "positive"), lo, False)
            elif str(rel) in ("negative", "nonpositive"):
                hi = tighter((sp.Integer(0), str(rel) == "negative"), hi, True)
    return lo, hi


def _outside(ctx, c, lo, hi):
    """True when the pole c is known to lie outside the range of integration."""
    if not (c.is_number and c.is_extended_real):
        return False
    (l1, u1), (l2, u2) = _bounds(ctx, lo), _bounds(ctx, hi)
    beyond = lambda v, s, sign: bool(sign * (c - v) > 0) or (s and c == v)   # noqa: E731
    return all(beyond(*b, -1) for b in (l1, l2)) or all(beyond(*b, 1) for b in (u1, u2))


def _integrate_exact(ctx, f, x, lo, hi, warn):
    """Maple's int on float-free input; None where Maple leaves it unevaluated."""
    if any(i.has(x) for i in f.atoms(sp.Integral)):
        return None
    f = sp.piecewise_fold(f)
    pw = isinstance(f, sp.Piecewise) and f.has(x)
    if lo is None:
        F = _pw_antiderivative(f, x) if pw else None
        return F if F is not None else _antiderivative(f, x)
    if (lo.is_number and hi.is_number) or lo.is_infinite or hi.is_infinite:
        if f.has(sp.Heaviside):     # SymPy's meijerg route returns meijerg() terms for these
            f = f.rewrite(sp.Piecewise)
        r = sp.integrate(f, (x, lo, hi), conds="none")
        return None if r.has(sp.Integral) else r
    # a symbolic limit: Maple integrates only if no pole can lie between the limits
    undecided = [c for c in _poles(f, x) if not _outside(ctx, c, lo, hi)]
    if undecided:
        if warn:
            for c in undecided:
                ctx.warn(f"unable to determine if {lprint(c)} is between {lprint(lo)} and {lprint(hi)}; "
                         f"try to use assumptions or use the AllSolutions option")
        return None
    F = _pw_antiderivative(f, x) if pw else None
    if F is None:
        F = _antiderivative(f, x)
        if F is None:
            return None
        s = lo if lo.is_number else hi if hi.is_number else None
        if s is not None:
            F = _real_logs(F, x, s)
    # shortcut: assumes F is continuous between the limits (SymPy's atan(tan(x/2)) forms are not);
    # add a jump correction if such integrands turn up
    return _at(F, x, hi, "-") - _at(F, x, lo, "+")


def integrate(ctx, f, x, lo=None, hi=None):
    """int(f, x) / int(f, x = lo..hi).  Float input is integrated exactly (SymPy is unreliable on
    floats) and evaluated back, as Maple returns floats for float input."""
    if not isinstance(f, sp.Basic):
        return f
    limits = (x,) if lo is None else (x, lo, hi)
    if any(a.has(sp.Float) for a in (f, *limits[1:])):
        r = _integrate_exact(ctx, _rational(f), x, *(map(_rational, limits[1:]) if lo is not None
                                                      else (None, None)), warn=False)
        if r is None and lo is not None and lo.is_number and hi.is_number:
            r = sp.Integral(f, limits)      # Maple falls back to numeric integration for floats
        return UnevalInt(f, limits) if r is None else ctx.evalf(r)
    r = _integrate_exact(ctx, f, x, lo, hi, warn=True)
    return UnevalInt(f, limits) if r is None else r


def _int_spec(ctx, f, spec, numeric=False):
    if isinstance(spec, MList):
        for s in spec.items:
            f = _int_spec(ctx, f, s, numeric)
        return f
    if isinstance(spec, MEquation) and isinstance(spec.rhs, MRange):
        var, lo, hi = spec.lhs, spec.rhs.lo, spec.rhs.hi
        if numeric:
            return ctx.evalf(sp.Integral(f, (var, lo, hi)))
        return integrate(ctx, f, var, lo, hi)
    if isinstance(spec, (sp.Symbol, sp.Indexed)):
        return integrate(ctx, f, spec)
    raise MapleError(f"integration range or variable must be specified in the second argument, "
                     f"got {lprint(spec)}")


@builtin(["int", "integrate"], sig="int(f, x) or int(f, x = a..b)", doc="Indefinite or definite integration.",
         options={"numeric": False, "method": None, "AllSolutions": False, "CauchyPrincipalValue": False})
def m_int(ctx, f, spec=None, *rest, numeric=False, method=None, **opts):
    if spec is None:
        raise MapleError("integration range or variable must be specified in the second argument")
    return deep_map(lambda x: _int_spec(ctx, x, spec, is_true(numeric)), f)


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

    def lim(e):
        r = sp.limit(e, x, a, d)
        if r is sp.zoo:
            return sp.nan     # undefined
        if isinstance(r, sp.AccumBounds):
            return MRange(r.min, r.max)
        return r
    try:
        return deep_map(lim, f)
    except ValueError:      # SymPy: the left and right limits differ
        return sp.nan
    except NotImplementedError:
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
    z = sp.Dummy("z")
    g = f.subs(x, z + a)
    s = sp.series(g, z, 0, order)
    if not s.has(sp.Order):
        return s.subs(z, x - a)
    # Maple's O-term is the next term that is not zero (sin(x), x, 6 -> ... + O(x^7))
    more = sp.series(g, z, 0, order + 4).removeO()
    exps = (t.as_coeff_exponent(z)[1] for t in sp.Add.make_args(more))
    m = min((e for e in exps if e >= order), default=order + 4)
    return s.removeO().subs(z, x - a) + sp.Order((x - a) ** m, (x, a))
