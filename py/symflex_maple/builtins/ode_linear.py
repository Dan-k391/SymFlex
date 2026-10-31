"""Closed-form solvers dsolve tries before SymPy's general `dsolve`, which can run for minutes on
the course's damped/forced oscillators (float-derived rationals, symbolic forcing frequency).

* linear constant-coefficient scalar ODEs: characteristic roots + undetermined coefficients;
* autonomous y'' = f(y) with both initial conditions: Maple's implicit RootOf(Int(...)) form.

Every function returns None when the input is outside its class, so the caller can fall back."""
from __future__ import annotations

import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.integrals.manualintegrate import manualintegrate
from sympy.simplify.fu import TR8

from .calculus import Int


def ode_order(expr, y, t):
    return max([sum(int(c) for _, c in d.variable_count)
                for d in expr.atoms(sp.Derivative) if d.expr == y] or [0])


def _slots(expr, y, t):
    """Replace y, y', ..., y^(n) by dummies d[0..n]; None if y occurs any other way."""
    n = ode_order(expr, y, t)
    ds = [sp.Dummy(f"d{k}") for k in range(n + 1)]
    reps = {y: ds[0], **{sp.Derivative(y, (t, k)): ds[k] for k in range(1, n + 1)}}
    e = expr.xreplace(reps)
    if e.has(y.func):
        return None
    return e, ds


def linear_coeffs(expr, y, t):
    """For expr = 0 linear in y with t-free coefficients: ([a0, ..., an], forcing f) such that
    sum a_k y^(k) = f. Otherwise None."""
    s = _slots(expr, y, t)
    if s is None:
        return None
    e, ds = s
    a = [sp.diff(e, d) for d in ds]
    if any(c.has(t, *ds) for c in a):     # all partials constant => e is affine in the slots
        return None
    return a, -e.subs({d: 0 for d in ds})


def _char_roots(a):
    """Roots of sum a_k r^k as [(alpha, beta, multiplicity)] meaning alpha +- I*beta (beta=0: real),
    or None when they cannot be found cheaply."""
    k0 = next(i for i, c in enumerate(a) if c != 0)
    out = [(sp.S.Zero, sp.S.Zero, k0)] if k0 else []
    b = a[k0:]
    m = len(b) - 1
    if m == 1:
        out.append((-b[0] / b[1], sp.S.Zero, 1))
    elif m == 2:
        c, bb, aa = b
        alpha = -bb / (2 * aa)
        disc = sp.expand(bb ** 2 - 4 * aa * c)
        if disc == 0:
            out.append((alpha, sp.S.Zero, 2))
        elif disc.is_negative or (disc.is_Mul and disc.as_coeff_Mul()[0].is_negative):
            out.append((alpha, sp.sqrt(-disc) / (2 * aa), 1))
        else:
            sq = sp.sqrt(disc) / (2 * aa)
            out += [(alpha + sq, sp.S.Zero, 1), (alpha - sq, sp.S.Zero, 1)]
    elif m > 2:
        if any(c.free_symbols for c in b):
            return None
        r = sp.Dummy("r")
        roots = sp.roots(sp.Poly(list(reversed(b)), r))
        if sum(roots.values()) != m:
            return None
        for root, mult in roots.items():
            re, im = root.as_real_imag()
            if im == 0:
                out.append((re, sp.S.Zero, mult))
            elif im.is_positive:
                out.append((re, im, mult))
            elif not im.is_negative:          # the conjugate (im < 0) is covered by its partner
                return None
    return out


def _basis(roots, t):
    out = []
    for alpha, beta, mult in roots:
        for j in range(mult):
            g = t ** j * sp.exp(alpha * t)
            out += [g * sp.cos(beta * t), g * sp.sin(beta * t)] if beta != 0 else [g]
    return out


def _linear_in(arg, t):
    """(c0, c1) with arg = c0 + c1*t, or None."""
    c1 = sp.diff(arg, t)
    if c1.has(t):
        return None
    return sp.expand(arg - c1 * t), c1


def _split_trig(e, t):
    """sin(w*t + p) -> sin(w*t)*cos(p) + cos(w*t)*sin(p), so the phase becomes a coefficient."""
    def split(f):
        lin = _linear_in(f.args[0], t)
        if lin is None or lin[0] == 0 or lin[1] == 0:
            return f
        p, w = lin[0], lin[1] * t
        if isinstance(f, sp.sin):
            return sp.sin(w) * sp.cos(p) + sp.cos(w) * sp.sin(p)
        return sp.cos(w) * sp.cos(p) - sp.sin(w) * sp.sin(p)
    return e.replace(lambda f: isinstance(f, (sp.sin, sp.cos)) and f.has(t), split)


def _classify(term, t):
    """A forcing term c * t^k * exp(alpha*t) * {1, sin(beta*t), cos(beta*t)} -> (alpha, beta, k)."""
    alpha, beta, k = sp.S.Zero, sp.S.Zero, 0
    for f in sp.Mul.make_args(term.as_independent(t, as_Add=False)[1]):
        base, ex = f.as_base_exp()
        if base == t and ex.is_Integer and ex > 0:
            k += int(ex)
        elif isinstance(f, sp.exp):
            lin = _linear_in(f.args[0], t)
            if lin is None:
                return None
            alpha += lin[1]
        elif isinstance(f, (sp.sin, sp.cos)) and beta == 0:
            lin = _linear_in(f.args[0], t)
            if lin is None or lin[0] != 0:
                return None
            beta = lin[1]
        elif f != 1:
            return None
    return alpha, beta, k


def _forcing_groups(f, t):
    """{(alpha, beta): (max t-degree, sum of terms)}, or None if f is not of that form."""
    groups = {}
    for term in sp.Add.make_args(sp.expand(_split_trig(f, t))):
        trig = [g.as_base_exp() for g in sp.Mul.make_args(term)
                if isinstance(g.as_base_exp()[0], (sp.sin, sp.cos)) and g.has(t)]
        if len(trig) > 1 or any(e != 1 for _, e in trig):
            term = sp.expand(TR8(term))      # products/powers of sin, cos -> sums
        for p in sp.Add.make_args(term):
            c = _classify(p, t)
            if c is None:
                return None
            alpha, beta, k = c
            deg, total = groups.get((alpha, beta), (0, sp.S.Zero))
            groups[(alpha, beta)] = (max(deg, k), total + p)
    return groups


def _undetermined(a, alpha, beta, deg, f, t):
    """Particular solution of sum a_k y^(k) = f for one forcing group."""
    n = len(a) - 1
    C, S = sp.Dummy("C"), sp.Dummy("S")
    cos_, sin_ = sp.cos(beta * t), sp.sin(beta * t)
    for s in range(n + 1):     # s = multiplicity of alpha + I*beta as a characteristic root
        A = [sp.Dummy(f"A{j}") for j in range(deg + 1)]
        B = [sp.Dummy(f"B{j}") for j in range(deg + 1)] if beta != 0 else []
        poly = sum(t ** (j + s) * (A[j] * cos_ + (B[j] * sin_ if B else 0)) for j in range(deg + 1)) \
            if B else sum(A[j] * t ** (j + s) for j in range(deg + 1))
        yp = sp.exp(alpha * t) * poly
        lhs = sum(c * sp.diff(yp, t, k) for k, c in enumerate(a) if c != 0)
        res = sp.powsimp(sp.expand((lhs - f) * sp.exp(-alpha * t)))
        res = res.xreplace({cos_: C, sin_: S}) if beta != 0 else res
        try:
            eqs = sp.Poly(res, t, C, S).coeffs()
        except sp.PolynomialError:
            return None
        sol = sp.linsolve(eqs, A + B)
        if sol:
            vals = next(iter(sol))
            reps = {u: sp.cancel(v).xreplace({w: 0 for w in A + B}) for u, v in zip(A + B, vals)}
            return yp.xreplace(reps)
    return None


def _antiderivative(g, t, t0):
    """Int(g, t) (from t0 when given), evaluated when manualintegrate manages it, else inert
    like Maple's Int(f(t)*exp(t), t)."""
    # shortcut: exp*trig integrands send manualintegrate into endless integration by parts,
    # so they stay inert; upgrade if a bounded integrator becomes available
    exp_trig = g.has(sp.exp) and any(f.has(t) for f in g.atoms(sp.sin, sp.cos, sp.tan))
    if not g.has(AppliedUndef) and not exp_trig:
        prim = manualintegrate(g, t)
        if not prim.has(sp.Integral):
            return prim if t0 is None else prim - prim.subs(t, t0)
    if t0 is None:
        return Int(g, t)
    z = sp.Symbol("_z1")
    return Int(g.subs(t, z), (z, t0, t))


def _variation(a, basis, f, t, t0):
    """Variation of parameters: y_p = sum phi_i * Int(W_i * f / (a_n * W))."""
    n = len(basis)
    W = sp.Matrix([[sp.diff(phi, t, k) for phi in basis] for k in range(n)])
    w = sp.simplify(W.det())
    yp = sp.S.Zero
    for i, phi in enumerate(basis):
        Wi = W.copy()
        Wi[:, i] = sp.Matrix([0] * (n - 1) + [1])
        g = sp.simplify(sp.powsimp(sp.expand(sp.simplify(Wi.det() / w) * f / a[n])))
        yp += phi * _antiderivative(g, t, t0)
    return yp


def solve_linear(expr, y, t, consts, t0=None):
    """General solution of the linear constant-coefficient ODE expr = 0 as (rhs, constants used),
    or None. `consts` yields fresh constant symbols; t0 is where initial conditions will be
    imposed (lower limit of unevaluated integrals)."""
    lc = linear_coeffs(expr, y, t)
    if lc is None:
        return None
    a, f = lc
    roots = _char_roots(a)
    if roots is None:
        return None
    basis = _basis(roots, t)
    yp = sp.S.Zero
    groups = _forcing_groups(f, t) if f != 0 else {}
    for (alpha, beta), (deg, part) in (groups or {}).items():
        p = _undetermined(a, alpha, beta, deg, part, t)
        if p is None:
            groups = None
            break
        yp += p
    if groups is None:
        yp = _variation(a, basis, f, t, t0)
    cs = [next(consts) for _ in basis]
    return sum(c * phi for c, phi in zip(cs, basis)) + yp, cs


def apply_ics(sol, cs, ics, t):
    """Fix constants from ics = [(k, t0, value)] meaning y^(k)(t0) = value; None if inconsistent."""
    def at(k, t0):
        e = sp.diff(sol, t, k).subs(t, t0)
        # an integral from t0 to t vanishes at t0
        return e.replace(lambda i: isinstance(i, sp.Integral) and len(i.limits[0]) == 3
                         and i.limits[0][1] == i.limits[0][2], lambda i: sp.S.Zero)
    res = sp.linsolve([at(k, t0) - v for k, t0, v in ics], cs)
    if not res:
        return None
    vals = next(iter(res))
    return sol.xreplace({c: sp.factor(sp.cancel(sp.radsimp(v))) for c, v in zip(cs, vals)})


def solve_autonomous(expr, y, t, ics):
    """y'' = f(y) with y(t0) = y0, y'(t0) = v0, by the energy integral:
    t - t0 = Int(1/y', y0..y) with y'^2 = v0^2 + 2*Int(f, y0..y). Returns a list of rhs or None."""
    s = _slots(expr, y, t)
    if s is None or len(s[1]) != 3:
        return None
    e, (d0, d1, d2) = s
    a2 = sp.diff(e, d2)
    rest = sp.expand(e - a2 * d2)
    if a2.has(t, d1, d2) or rest.has(t, d1, d2):
        return None
    vals = {k: (t0, v) for k, t0, v in ics}
    if set(vals) != {0, 1} or vals[0][0] != vals[1][0]:
        return None
    t0, y0 = vals[0]
    v0 = vals[1][1]
    u, z = sp.Symbol("_a"), sp.Symbol("_Z")
    prim = manualintegrate((-rest / a2).subs(d0, u), u)
    if prim.has(sp.Integral):
        return None
    energy = 2 * (prim - prim.subs(u, y0)) + v0 ** 2
    signs = [1] if v0.is_positive else [-1] if v0.is_negative else [-1, 1] if v0 == 0 else None
    if signs is None:
        return None
    num, den = sp.fraction(sp.together(energy))
    speed = sp.sqrt(num * den) / den      # Maple's radical form sqrt(a/b) = sqrt(a*b)/b
    root_of = sp.Function("RootOf")
    return [root_of(-Int(sgn / speed, (u, y0, z)) + t - t0) for sgn in signs]
