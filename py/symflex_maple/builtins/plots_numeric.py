"""Numeric core of the plots package: evaluators, Maple-like adaptive sampling, discontinuities
(discont=true), smartview and implicit curves.  Pure Python floats; no SymPy in the inner loops
except the evalf fallback."""
from __future__ import annotations

import math

import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..printer import lprint
from ..values import Procedure

ADAPT_TOL = 4e-3     # midpoint deviation from the chord (fraction of the plot box) that triggers a bisection


def to_float(r):
    """A finite real float, or None (complex, infinite, symbolic)."""
    if isinstance(r, bool):
        return float(r)
    if isinstance(r, (int, float)):
        r = float(r)
    else:
        try:
            c = complex(r)
        except (TypeError, ValueError):
            return None
        if abs(c.imag) > 1e-12 * max(1.0, abs(c.real)):
            return None
        r = c.real
    return r if math.isfinite(r) else None


def free_names(ctx, expr, variables):
    """Names in expr other than the plotting variables, and unassigned function names (y in y(x))."""
    names = {s.name for s in expr.free_symbols - set(variables)}
    for f in expr.atoms(AppliedUndef):
        name = type(f).__name__
        try:
            bound = isinstance(ctx.lookup(name), Procedure)
        except MapleError:
            bound = False
        if not bound:
            names.add(name)
    return sorted(names)


# float versions of Maple functions that stay unevaluated calls in symbolic expressions
FAST = {"round": lambda v: math.copysign(math.floor(abs(float(v)) + 0.5), float(v)),
        "trunc": lambda v: float(math.trunc(float(v))), "frac": lambda v: float(v) - math.trunc(float(v))}


def evaluator(ctx, f, variables):
    """float args -> float|None for an expression in `variables` or a procedure.  Undefined points
    (errors, complex values) give None, like Maple's undefined plot points."""
    variables = list(variables)
    if isinstance(f, Procedure):
        def g(*xs):
            try:
                return to_float(ctx.evalf(ctx.apply(f, [sp.Float(x, 15) for x in xs])))
            except MapleError:
                return None
            except (TypeError, ValueError, ZeroDivisionError, ArithmeticError):
                return None
        return g
    if not isinstance(f, sp.Basic):
        raise MapleError(f"invalid plotting of {lprint(f)}")
    expr = f
    if any(type(c).__name__ not in FAST for c in expr.atoms(AppliedUndef)):
        # calls of procedures ('g(x)', round(x), ...): evaluate through the interpreter at each point
        def g(*xs):
            try:
                v = ctx.full_eval(expr.subs(dict(zip(variables, (sp.Float(x, 15) for x in xs)))))
                return to_float(ctx.evalf(v))
            except (MapleError, TypeError, ValueError, ZeroDivisionError, ArithmeticError):
                return None
        return g
    try:
        fn = sp.lambdify(variables, expr, modules=[FAST, "math", "mpmath"])
    except Exception:  # noqa: BLE001 - unprintable functions fall back to evalf
        fn = None

    def g(*xs):
        if fn is not None:
            try:
                return to_float(fn(*xs))
            except (TypeError, ValueError, ZeroDivisionError, OverflowError, ArithmeticError, NameError):
                pass
        try:
            return to_float(expr.subs(dict(zip(variables, xs))).evalf(15))
        except (TypeError, ValueError, ZeroDivisionError, ArithmeticError):
            return None
    return g


def quantile(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, max(0, int(q * (len(sorted_vals) - 1))))]


def adaptive(g, ts, depth=6, max_evals=None):
    """Sample the planar curve g(t) -> (X, Y) | None at ts, then bisect every segment whose midpoint
    leaves the chord by more than ADAPT_TOL of the plot box, at most `depth` times (Maple's
    adaptive sampling).  Refinement goes level by level so a limited budget is spread over the
    whole range.  Returns [(X, Y) | None] in t order."""
    pts = [(t, g(t)) for t in ts]
    good = [p for _, p in pts if p is not None]
    if depth <= 0 or len(pts) < 2 or not good:
        return [p for _, p in pts]
    xs, ys = sorted(p[0] for p in good), sorted(p[1] for p in good)
    sx = (xs[-1] - xs[0]) or 1.0
    sy = (quantile(ys, 0.98) - quantile(ys, 0.02)) or (ys[-1] - ys[0]) or max(abs(ys[0]), 1.0)
    budget = max_evals if max_evals is not None else 8 * len(ts)
    active = [p0 is not None or p1 is not None for (_, p0), (_, p1) in zip(pts, pts[1:])]
    for _ in range(depth):
        n_active = sum(active)
        if not n_active or n_active > budget:
            break
        budget -= n_active
        new_pts, new_active = [pts[0]], []
        for k, ((t0, p0), (t1, p1)) in enumerate(zip(pts, pts[1:])):
            if active[k]:
                tm = (t0 + t1) / 2
                pm = g(tm)
                if p0 is None or p1 is None or pm is None or                         math.hypot((pm[0] - (p0[0] + p1[0]) / 2) / sx, (pm[1] - (p0[1] + p1[1]) / 2) / sy) > ADAPT_TOL:
                    new_pts.append((tm, pm))
                    new_active += [p0 is not None or pm is not None, pm is not None or p1 is not None]
                    new_pts.append((t1, p1))
                    continue
            new_pts.append((t1, p1))
            new_active.append(False)
        pts, active = new_pts, new_active
    return [p for _, p in pts]


def open_samples(lo, hi, n, refine_lo=True, refine_hi=True, levels=8):
    """Cell midpoints of n cells, plus points crowding towards the open ends (pieces next to a
    discontinuity: Maple never evaluates on it but gets close)."""
    h = (hi - lo) / n
    mids = [lo + h * (i + 0.5) for i in range(n)]
    left = [lo + h / 2 ** k for k in range(levels, 0, -1)] if refine_lo else []
    right = [hi - h / 2 ** k for k in range(1, levels + 1)] if refine_hi else []
    return left + mids + right


# ---------------------------------------------------------------- discontinuities
def _linear(u, x):
    """(p, q) with u = p*x + q, or None."""
    try:
        poly = sp.Poly(u, x)
    except sp.PolynomialError:
        return None
    if poly.degree() != 1:
        return None
    p, q = poly.all_coeffs()
    try:
        return float(p), float(q)
    except TypeError:
        return None


def _roots(u, x, a, b):
    """Real zeros of u in [a, b]: exact for polynomials, else sign changes on a fine grid."""
    try:
        poly = sp.Poly(u, x)
        if poly.degree() > 0 and all(c.is_number for c in poly.all_coeffs()):
            return [float(sp.re(r)) for r in poly.nroots() if abs(sp.im(r)) < 1e-9 and a <= float(sp.re(r)) <= b]
    except (sp.PolynomialError, sp.polys.polyerrors.PolificationFailed, TypeError, ValueError):
        pass
    g = evaluator(None, u, [x]) if not u.atoms(AppliedUndef) else None
    if g is None:
        return []
    n = 400
    xs = [a + (b - a) * i / n for i in range(n + 1)]
    vs = [g(v) for v in xs]
    out = []
    for x0, x1, v0, v1 in zip(xs, xs[1:], vs, vs[1:]):
        if v0 is None or v1 is None or v0 * v1 > 0:
            continue
        for _ in range(60):
            xm = (x0 + x1) / 2
            vm = g(xm)
            if vm is None:
                break
            if (vm <= 0) == (v0 <= 0):
                x0, v0 = xm, vm
            else:
                x1 = xm
        out.append((x0 + x1) / 2)
    return out


def _periodic(u, x, a, b, offset, period):
    """x in [a, b] where the linear u equals offset + k*period."""
    lin = _linear(u, x)
    if lin is None or lin[0] == 0:
        return []
    p, q = lin
    lo, hi = sorted((p * a + q, p * b + q))
    k0 = math.ceil((lo - offset) / period)
    return [(offset + k * period - q) / p for k in range(k0, math.floor((hi - offset) / period) + 1)]


def discontinuities(expr, x, a, b, f):
    """Jump points of expr on [a, b] for discont=true, as (point, marked) pairs: piecewise
    breakpoints and floor/round/frac/... jumps are `marked` (Maple draws the point value), poles
    and Heaviside/abs steps are not.  f is expr's float evaluator."""
    cands = {}

    def add(points, marked):
        for d in points:
            if a - 1e-12 * (b - a) <= d <= b + 1e-12 * (b - a):
                cands[round(d, 12)] = cands.get(round(d, 12), False) or marked

    pi = math.pi
    for node in sp.preorder_traversal(expr):
        if isinstance(node, sp.Piecewise):
            for _, cond in node.args:
                if isinstance(cond, sp.Basic):
                    for rel in cond.atoms(sp.core.relational.Relational):
                        add(_roots(rel.lhs - rel.rhs, x, a, b), True)
        elif isinstance(node, (sp.floor, sp.ceiling)):
            add(_periodic(node.args[0], x, a, b, 0.0, 1.0), True)
        elif isinstance(node, AppliedUndef) and type(node).__name__ in ("round", "trunc", "frac") and node.args:
            add(_periodic(node.args[0], x, a, b, 0.5 if type(node).__name__ == "round" else 0.0, 1.0), True)
        elif isinstance(node, sp.Heaviside):
            add(_roots(node.args[0], x, a, b), False)
        elif isinstance(node, (sp.tan, sp.sec)):
            add(_periodic(node.args[0], x, a, b, pi / 2, pi), False)
        elif isinstance(node, (sp.cot, sp.csc)):
            add(_periodic(node.args[0], x, a, b, 0.0, pi), False)
        elif isinstance(node, sp.Pow) and node.exp.is_number and node.exp.is_negative:
            add(_roots(node.base, x, a, b), False)
    out = []
    span = b - a
    for d in sorted(cands):
        # only real jumps split the curve: not continuous breakpoints, nor even poles (1/x^2)
        eps = 1e-7 * span
        lv, rv = f(d - eps), f(d + eps)
        if lv is None and rv is None or                 lv is not None and rv is not None and abs(lv - rv) <= 1e-4 * max(1.0, abs(lv), abs(rv)):
            continue
        out.append((d, cands[d]))
    return out


# ---------------------------------------------------------------- smartview
def smart_range(curves, xlog=False):
    """A y range that cuts off singular spikes (Maple's smartview), or None when the curves have
    none.  curves: [(xs, ys)] of function plots; quantiles are weighted by the on-screen x span of
    a point (log x on a logarithmic axis) since adaptive sampling crowds points into spikes."""
    pts = []
    for xs, ys in curves:
        P = [(math.log10(x) if xlog else x, y) for x, y in zip(xs, ys)
             if x is not None and y is not None and (not xlog or x > 0)]
        for i, (_, y) in enumerate(P):
            w = (P[min(i + 1, len(P) - 1)][0] - P[max(i - 1, 0)][0]) / 2
            pts.append((y, abs(w)))
    if len(pts) < 10:
        return None
    pts.sort()
    total = sum(w for _, w in pts) or 1.0

    def q(frac):
        acc = 0.0
        for y, w in pts:
            acc += w
            if acc >= frac * total:
                return y
        return pts[-1][0]
    lo_q, hi_q, ymin, ymax = q(0.08), q(0.92), pts[0][0], pts[-1][0]
    core = (hi_q - lo_q) or 1.0
    lo = lo_q if lo_q - ymin > 3 * core else ymin
    hi = hi_q if ymax - hi_q > 3 * core else ymax
    if lo == ymin and hi == ymax:
        return None
    pad = 0.05 * (hi - lo)
    return [lo - pad if lo != ymin else lo, hi + pad if hi != ymax else hi]


# ---------------------------------------------------------------- implicit curves
def implicit_curves(F, xa, xb, ya, yb, nx, ny):
    """Polylines of F(x, y) = 0 on a grid (marching squares, crossings refined on the cell edges)."""
    xs = [xa + (xb - xa) * i / (nx - 1) for i in range(nx)]
    ys = [ya + (yb - ya) * j / (ny - 1) for j in range(ny)]
    V = [[F(x, y) for x in xs] for y in ys]
    cross = {}

    def edge(key):
        """Crossing point on a grid edge ('h', i, j): (i,j)-(i+1,j); ('v', i, j): (i,j)-(i,j+1)."""
        if key in cross:
            return cross[key]
        kind, i, j = key
        i2, j2 = (i + 1, j) if kind == "h" else (i, j + 1)
        v0, v1 = V[j][i], V[j2][i2]
        pt = None
        if v0 is not None and v1 is not None and (v0 >= 0) != (v1 >= 0):   # zero counts as positive
            p0, p1 = (xs[i], ys[j]), (xs[i2], ys[j2])
            s0, s1, a0, a1 = 0.0, 1.0, v0, v1
            s = 0.0
            for _ in range(30):   # regula falsi (Illinois) along the edge
                s = s0 - a0 * (s1 - s0) / (a1 - a0) if a1 != a0 else (s0 + s1) / 2
                vs = F(p0[0] + s * (p1[0] - p0[0]), p0[1] + s * (p1[1] - p0[1]))
                if vs is None or vs == 0:
                    break
                if (vs >= 0) == (a0 >= 0):
                    s0, a0, a1 = s, vs, a1 / 2
                else:
                    s1, a1, a0 = s, vs, a0 / 2
                if s1 - s0 < 1e-12:
                    break
            vs = F(p0[0] + s * (p1[0] - p0[0]), p0[1] + s * (p1[1] - p0[1]))
            if vs is not None and abs(vs) <= 1e-3 * (abs(v0) + abs(v1)):   # not a pole
                pt = (p0[0] + s * (p1[0] - p0[0]), p0[1] + s * (p1[1] - p0[1]))
        cross[key] = pt
        return pt

    adj = {}

    def link(k1, k2):
        adj.setdefault(k1, []).append(k2)
        adj.setdefault(k2, []).append(k1)

    for j in range(ny - 1):
        for i in range(nx - 1):
            ks = [("h", i, j), ("v", i + 1, j), ("h", i, j + 1), ("v", i, j)]
            hit = [k for k in ks if edge(k) is not None]
            if len(hit) == 2:
                link(*hit)
            elif len(hit) == 4:   # saddle: pair the edges around the corner whose sign the centre shares
                c = F((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)
                if c is not None and (c >= 0) == (V[j][i] >= 0):
                    link(ks[0], ks[1])
                    link(ks[2], ks[3])
                else:
                    link(ks[0], ks[3])
                    link(ks[1], ks[2])
    # components in grid scan order (x, then y), each traced from an open end when it has one
    seen, lines = set(), []
    for s in sorted(adj, key=lambda k: (k[1], k[2], k[0])):
        if s in seen:
            continue
        comp, stack = {s}, [s]
        while stack:
            for nb in adj[stack.pop()]:
                if nb not in comp:
                    comp.add(nb)
                    stack.append(nb)
        s = next((k for k in sorted(comp, key=lambda k: (k[1], k[2], k[0])) if len(adj[k]) == 1), s)
        line, k, prev = [s], s, None
        seen.add(s)
        while True:
            nxt = [n for n in adj[k] if n != prev and n not in seen]
            if not nxt:
                if len(line) > 2 and s in adj[k]:
                    line.append(s)   # closed loop
                break
            prev, k = k, nxt[0]
            seen.add(k)
            line.append(k)
        seen |= comp
        if len(line) > 1:
            lines.append([cross[k] for k in line])
    return lines
