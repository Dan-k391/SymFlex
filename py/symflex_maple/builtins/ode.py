"""ODEs: dsolve (symbolic via SymPy, numeric via an adaptive Dormand-Prince RK45).
First working version; the numeric solution object is an AppliedProc so it can be called
like Maple's `proc(x_rkf45) ... end proc`."""
from __future__ import annotations

import math

import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..values import AppliedProc, ExprSeq, MEquation, MList, MSet, make_seq, seq_items
from . import Library, is_true
from .core import equations_of, has_float

lib = Library()
builtin = lib.builtin


def register(env):
    lib.register(env)


def _split(eqs):
    odes, ics = [], []
    for e in equations_of(eqs):
        if not isinstance(e, MEquation):
            e = MEquation(e, sp.Integer(0))
        if isinstance(e.lhs, (AppliedUndef, sp.Subs)) and not e.rhs.has(sp.Derivative):
            ics.append(e)
        else:
            odes.append(e)
    return odes, ics


def _funcs_of(odes):
    fs = set()
    for e in odes:
        for side in (e.lhs, e.rhs):
            for d in side.atoms(sp.Derivative):
                if isinstance(d.expr, AppliedUndef):
                    fs.add(d.expr)
    return sorted(fs, key=str)


def _rename_constants(expr):
    reps = {}
    for s in expr.free_symbols:
        if s.name.startswith("C") and s.name[1:].isdigit():
            reps[s] = sp.Symbol("_C" + s.name[1:])
    return expr.xreplace(reps) if reps else expr


@builtin("dsolve", sig="dsolve({ode, ics}, y(t), options)",
         doc="Solve ODEs symbolically, or numerically with the numeric option.",
         options={"numeric": False, "output": None, "method": None, "range": None,
                  "abserr": None, "relerr": None, "maxfun": None, "type": None, "parameters": None})
def m_dsolve(ctx, eqs, *rest, numeric=False, output=None, method=None, range=None, **opts):
    odes, ics = _split(eqs)
    if not odes:
        raise MapleError("no differential equations found")
    if is_true(numeric):
        return _numeric(ctx, odes, ics, output)
    funcs = _funcs_of(odes)
    sym_eqs = [sp.Eq(e.lhs, e.rhs) for e in odes]
    floats = has_float(eqs)
    if floats:
        sym_eqs = [sp.nsimplify(e, rational=True) for e in sym_eqs]
    ic_map = {}
    t = funcs[0].args[0] if funcs else None
    for e in ics:
        lhs, rhs = _ic_lhs(e.lhs, t), e.rhs
        ic_map[lhs] = sp.nsimplify(rhs, rational=True) if floats else rhs
    try:
        if len(sym_eqs) == 1:
            sol = sp.dsolve(sym_eqs[0], funcs[0], ics=ic_map or None)
        else:
            sol = sp.dsolve(sym_eqs, funcs, ics=ic_map or None)
    except NotImplementedError as e:
        raise MapleError(f"unable to solve: {e}")
    sols = sol if isinstance(sol, list) else [sol]
    out = []
    for s in sols:
        rhs = _rename_constants(s.rhs)
        if floats:
            rhs = ctx.evalf(rhs)
        out.append(MEquation(s.lhs, rhs))
    if len(sym_eqs) > 1:
        return MSet(out)
    return make_seq(out)


def _ic_lhs(lhs, t):
    """SymPy wants D(x)(0) as Subs(Derivative(x(t), t), t, 0) in the ODE's own variable."""
    if isinstance(lhs, sp.Subs) and isinstance(lhs.expr, sp.Derivative) and t is not None:
        der = lhs.expr
        f = type(der.expr)
        n = sum(int(c) for _, c in der.variable_count)
        return sp.Subs(sp.Derivative(f(t), (t, n)), t, lhs.point[0])
    return lhs


# ====================================================================== numeric
def _first_order_system(odes, funcs, t):
    """Return state symbols [(func, order_k)], and rhs callables for y' = F(t, y)."""
    highest = {}
    for e in odes:
        for side in (e.lhs, e.rhs):
            for d in side.atoms(sp.Derivative):
                if isinstance(d.expr, AppliedUndef):
                    n = sum(int(c) for _, c in d.variable_count)
                    highest[d.expr] = max(highest.get(d.expr, 0), n)
    tops = [sp.Derivative(f, (t, highest[f])) if highest[f] > 1 else sp.Derivative(f, t)
            for f in funcs]
    sol = sp.solve([e.lhs - e.rhs for e in odes], tops, dict=True)
    if not sol:
        raise MapleError("unable to isolate the highest derivatives")
    sol = sol[0]
    states = []
    for f in funcs:
        for k in range(highest[f]):
            states.append((f, k))
    syms = [sp.Dummy(f"y{i}") for i in range(len(states))]
    reps = {}
    for (f, k), s in zip(states, syms):
        reps[f if k == 0 else sp.Derivative(f, (t, k)) if k > 1 else sp.Derivative(f, t)] = s
    # replace highest-order derivatives first so that lower ones do not clash
    order = sorted(reps, key=lambda e: -sum(int(c) for _, c in e.variable_count)
                   if isinstance(e, sp.Derivative) else 0)
    rhs = []
    for (f, k), s in zip(states, syms):
        if k + 1 < highest[f]:
            nxt = states.index((f, k + 1))
            rhs.append(syms[nxt])
        else:
            top = tops[funcs.index(f)]
            e = sol[top]
            for key in order:
                e = e.subs(key, reps[key])
            rhs.append(e)
    F = sp.lambdify([t] + syms, rhs, modules="math")
    return states, F


def _ic_values(ics, states, t):
    t0 = None
    vals = {}
    for e in ics:
        lhs = e.lhs
        if isinstance(lhs, AppliedUndef) and len(lhs.args) == 1:
            t0 = lhs.args[0]
            vals[(type(lhs).__name__, 0)] = e.rhs
        elif isinstance(lhs, sp.Subs):
            der = lhs.expr
            n = sum(int(c) for _, c in der.variable_count)
            t0 = lhs.point[0]
            vals[(type(der.expr).__name__, n)] = e.rhs
    y0 = []
    for f, k in states:
        v = vals.get((type(f).__name__, k))
        if v is None:
            raise MapleError(f"missing initial condition for {f}" + (f" derivative {k}" if k else ""))
        y0.append(float(sp.N(v)))
    return float(sp.N(t0 if t0 is not None else 0)), y0


_DP = (
    (1 / 5,),
    (3 / 40, 9 / 40),
    (44 / 45, -56 / 15, 32 / 9),
    (19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729),
    (9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656),
    (35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84),
)
_C = (0, 1 / 5, 3 / 10, 4 / 5, 8 / 9, 1, 1)
_B5 = (35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84, 0)
_B4 = (5179 / 57600, 0, 7571 / 16695, 393 / 640, -92097 / 339200, 187 / 2100, 1 / 40)


def rk45(F, t0, y0, t1, rtol=1e-9, atol=1e-11):
    """Integrate y' = F(t, *y) from t0 to t1 (either direction); returns y(t1)."""
    if t1 == t0:
        return list(y0)
    direction = 1.0 if t1 > t0 else -1.0
    t, y = t0, list(y0)
    h = direction * min(abs(t1 - t0), 1e-2)
    n = len(y)
    for _ in range(1_000_000):
        if direction * (t + h - t1) > 0:
            h = t1 - t
        k = [F(t, *y)]
        for i, row in enumerate(_DP):
            yi = [y[j] + h * sum(a * kk[j] for a, kk in zip(row, k)) for j in range(n)]
            k.append(F(t + _C[i + 1] * h, *yi))
        y5 = [y[j] + h * sum(b * kk[j] for b, kk in zip(_B5, k)) for j in range(n)]
        y4 = [y[j] + h * sum(b * kk[j] for b, kk in zip(_B4, k)) for j in range(n)]
        err = max(abs(a - b) / (atol + rtol * max(abs(a), abs(c))) for a, b, c in zip(y5, y4, y)) \
            if n else 0.0
        if err <= 1.0 or abs(h) < 1e-14:
            t, y = t + h, y5
            if direction * (t - t1) >= 0:
                return y
        fac = 0.9 * (1.0 / err) ** 0.2 if err > 0 else 5.0
        h *= min(5.0, max(0.2, fac))
    raise MapleError("cannot evaluate the solution further: too many steps")


class NumericSolution:
    def __init__(self, t, funcs, states, F, t0, y0):
        self.t, self.funcs, self.states, self.F = t, funcs, states, F
        self.t0, self.y0 = t0, y0

    def at(self, tv):
        return rk45(self.F, self.t0, self.y0, float(tv))

    def labels(self):
        out = []
        for f, k in self.states:
            out.append(f if k == 0 else sp.Derivative(f, (self.t, k)) if k > 1 else sp.Derivative(f, self.t))
        return out


def _numeric(ctx, odes, ics, output):
    funcs = _funcs_of(odes)
    t = funcs[0].args[0]
    states, F = _first_order_system(odes, funcs, t)
    t0, y0 = _ic_values(ics, states, t)
    ns = NumericSolution(t, funcs, states, F, t0, y0)
    labels = ns.labels()

    def at_point(ctx_, args):
        tv = args[0]
        if not (isinstance(tv, sp.Basic) and tv.is_number):
            return sp.Function("dsolve_numeric")(tv)
        ys = ns.at(float(sp.N(tv)))
        return MList([MEquation(t, sp.Float(float(sp.N(tv)), 15))] +
                     [MEquation(l, sp.Float(v, 15)) for l, v in zip(labels, ys)])
    if output is not None and str(output) == "listprocedure":
        items = [MEquation(t, AppliedProc(lambda c, a: a[0], label=sp.Symbol("proc(t) ... end proc")))]
        for i, l in enumerate(labels):
            items.append(MEquation(l, _component_proc(ns, i)))
        return MList(items)
    p = AppliedProc(at_point, label=sp.Symbol("proc(x_rkf45) ... end proc"))
    p.numeric_solution = ns
    return p


def _component_proc(ns, i):
    def fn(ctx, args):
        tv = args[0]
        if not (isinstance(tv, sp.Basic) and tv.is_number):
            return sp.Function("dsolve_numeric")(tv)
        return sp.Float(ns.at(float(sp.N(tv)))[i], 15)
    p = AppliedProc(fn, label=sp.Symbol("proc(t) ... end proc"))
    p.numeric_solution = ns
    p.component = i
    return p
