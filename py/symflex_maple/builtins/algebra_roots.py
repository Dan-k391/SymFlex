"""The order in which Maple's solve lists the roots of a univariate polynomial.

Course code relies on it (`t1, t2 := solve(...)`, `solve(...)[1]`), so solve reorders
SymPy's solutions to follow it.  Maple applies the quadratic formula to the polynomial as
written (with a positive leading coefficient when it has symbolic parameters) and lists the
`+` root first; a biquadratic gives `sqrt(w), -sqrt(w)` for each root `w`; a lone root 0
comes first and a repeated one last; other float polynomials are listed by argument in
[0, 2*Pi), then modulus.  The roots are computed numerically, with any parameters set to
generic positive values, and only used to match against the exact solutions.
"""
from __future__ import annotations

import cmath
import math

import mpmath
import sympy as sp

_GENERIC = (1.37, 2.71, 1.93, 3.17, 2.29, 1.61, 2.53, 3.41)


def generic_point(syms) -> dict:
    return {s: sp.Float(_GENERIC[i % len(_GENERIC)] + i // len(_GENERIC))
            for i, s in enumerate(sorted(syms, key=str))}


def _num(c, point) -> complex:
    return complex(sp.N(sp.sympify(c).xreplace(point), 30))


def _arg_key(z: complex):
    if abs(z.imag) <= 1e-12 * max(1.0, abs(z)):
        return (0.0 if z.real >= 0 else math.pi, abs(z))
    return (math.atan2(z.imag, z.real) % (2 * math.pi), abs(z))


def _order(cs, x, point, floats):
    """Roots of sum(cs[i]*x^(n-i)) in Maple's order, or None if not known."""
    n = len(cs) - 1
    if n <= 0:
        return []
    k = 0
    while k < n and cs[n - k] == 0:
        k += 1
    if k:
        rest = _order(cs[:n + 1 - k], x, point, floats)
        if rest is None:
            return None
        return [0j] + rest if k == 1 else rest + [0j] * k
    if n == 1:
        return [-_num(cs[1], point) / _num(cs[0], point)]
    if n == 2:
        a, b, c = (_num(v, point) for v in cs)
        d = cmath.sqrt(b * b - 4 * a * c)
        return [(-b + d) / (2 * a), (-b - d) / (2 * a)]
    if n == 4 and cs[1] == 0 and cs[3] == 0:
        ws = _order([cs[0], cs[2], cs[4]], x, point, floats)
        return [r for w in ws for r in (cmath.sqrt(w), -cmath.sqrt(w))]
    _, facs = sp.factor_list(sp.Poly(cs, x).as_expr(), x)
    facs = [(sp.Poly(f, x), m) for f, m in facs if f.has(x)]
    if len(facs) == 1 and facs[0][1] == 1:
        if not floats:
            return None
        with mpmath.workdps(30):
            roots = mpmath.polyroots([_num(c, point) for c in cs], maxsteps=200, extraprec=60)
        return sorted((complex(r) for r in roots), key=_arg_key)
    linear = sorted(((_order(f.all_coeffs(), x, point, floats)[0], m)
                     for f, m in facs if f.degree() == 1), key=lambda rm: _arg_key(rm[0]))
    out = [r for r, m in linear for _ in range(m)]
    for f, m in facs:
        if f.degree() > 1:
            rs = _order(f.all_coeffs(), x, point, floats)
            if rs is None:
                return None
            if f.degree() == 2 and f.all_coeffs()[1] != 0 and abs(rs[0].imag) > 1e-12:
                rs = rs[::-1]   # a complex pair from a factor comes out conjugate first
            out += [r for r in rs for _ in range(m)]
    return out


def maple_root_order(expr, x, floats):
    """Numeric roots of the numerator of expr (polynomial in x) in Maple's solve order,
    with the parameter values used, or None."""
    num = sp.together(expr).as_numer_denom()[0]
    if not num.is_polynomial(x):
        return None
    try:
        poly = sp.Poly(num, x)
    except sp.PolynomialError:
        return None
    params = num.free_symbols - {x}
    if params and poly.LC().could_extract_minus_sign():
        poly = -poly
    point = generic_point(params)
    try:
        refs = _order(poly.all_coeffs(), x, point, floats)
    except (TypeError, ValueError, ZeroDivisionError, mpmath.libmp.NoConvergence):
        return None
    return None if refs is None else (refs, point)


def reorder(items, value_of, refs, point):
    """items arranged to follow the reference roots (repeated for multiplicity), or None."""
    try:
        vals = [_num(value_of(it), point) for it in items]
    except (TypeError, ValueError):
        return None
    out, used = [], set()
    for r in refs:
        j = min(range(len(vals)), key=lambda i: abs(vals[i] - r))
        if abs(vals[j] - r) > 1e-6 * max(1.0, abs(r)):
            return None
        out.append(items[j])
        used.add(j)
    return out if len(used) == len(items) else None


# Maple's solve inverts these with the principal branch only: solve(sin(x) = 1/2) is Pi/6.
_INVERSE = {sp.sin: sp.asin, sp.cos: sp.acos, sp.tan: sp.atan, sp.cot: sp.acot,
            sp.sec: sp.asec, sp.csc: sp.acsc, sp.cosh: sp.acosh, sp.sinh: sp.asinh,
            sp.tanh: sp.atanh, sp.exp: sp.log}
_PERIODIC = (sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc, sp.cosh)


def principal_solutions(expr, x, floats):
    """Solutions of expr = 0 the way Maple's solve inverts trigonometric functions of a
    linear argument (principal values, factor by factor), or None when that does not apply."""
    num = sp.together(expr).as_numer_denom()[0]
    if not any(f.func in _PERIODIC and f.has(x) for f in num.atoms(sp.Function)):
        return None
    out = []
    for fac in sp.Mul.make_args(sp.factor_terms(num)):
        if isinstance(fac, sp.Pow) and fac.exp.is_Integer and fac.exp > 0:
            fac = fac.base
        if not fac.has(x):
            continue
        kernels = {f for f in fac.atoms(sp.Function) if f.has(x)}
        if not kernels:
            vals = sp.solve(fac, x)
        elif len(kernels) == 1 and (k := kernels.pop()).func in _INVERSE:
            arg = k.args[0]
            u = sp.Dummy("u")
            q = fac.xreplace({k: u})
            if not (arg.is_polynomial(x) and sp.degree(arg, x) == 1) or q.has(x):
                return None
            a, b = sp.Poly(arg, x).all_coeffs()
            us = sp.solve(q, u)
            ref = maple_root_order(q, u, floats)
            if ref is not None:
                us = reorder(us, lambda v: v, *ref) or us
            vals = []
            for v in us:
                inv = _INVERSE[k.func](v)
                if inv.is_finite is not False:
                    vals.append((inv - b) / a)
        else:
            return None
        out += vals
    return out
