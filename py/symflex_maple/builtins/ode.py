"""ODEs: dsolve (symbolic: ode_linear's closed forms first, then SymPy; numeric via an adaptive
Dormand-Prince RK45) and odetest. Numeric solutions are AppliedProcs callable like Maple's
`proc(x_rkf45) ... end proc`."""
from __future__ import annotations

import itertools
import math

import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..values import NULL, AppliedProc, ExprSeq, MEquation, MList, MSet, make_seq, seq_items
from . import Library, is_true
from .core import equations_of, has_float
from .ode_linear import apply_ics, linear_coeffs, ode_order, solve_autonomous, solve_linear

lib = Library()
builtin = lib.builtin


def register(env):
    lib.register(env)


def _split(eqs):
    odes, ics = [], []
    for e in equations_of(eqs):
        if not isinstance(e, MEquation):
            e = MEquation(e, sp.Integer(0))
        if _is_ic(e):
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
            reps[s] = sp.Symbol("c__" + s.name[1:])
    return expr.xreplace(reps) if reps else expr


def _ic_parts(e):
    """y(t0) = v -> (y, 0, t0, v); D(y)(t0) = v -> (y, 1, t0, v); None for anything else."""
    lhs = e.lhs
    if isinstance(lhs, AppliedUndef) and len(lhs.args) == 1:
        return lhs.func, 0, lhs.args[0], e.rhs
    if isinstance(lhs, sp.Subs) and isinstance(lhs.expr, sp.Derivative):
        der = lhs.expr
        return der.expr.func, sum(int(c) for _, c in der.variable_count), lhs.point[0], e.rhs
    return None


def _plus_first(sols):
    """Maple lists y = +r before y = -r; SymPy gives the negative branch first."""
    if len(sols) == 2 and sp.expand(sols[0].rhs + sols[1].rhs) == 0             and sols[0].rhs.could_extract_minus_sign():
        return sols[::-1]
    return sols


@builtin("dsolve", sig="dsolve({ode, ics}, y(t), options)",
         doc="Solve ODEs symbolically, or numerically with the numeric option.",
         options={"numeric": False, "output": None, "method": None, "range": None,
                  "abserr": None, "relerr": None, "maxfun": None, "type": None, "parameters": None})
def m_dsolve(ctx, eqs, *rest, numeric=False, output=None, method=None, range=None, **opts):
    odes, ics = _split(eqs)
    if not odes:
        raise MapleError("no differential equations found")
    if is_true(numeric) or str(opts.get("type")) == "numeric":
        return _numeric(ctx, odes, ics, output)
    funcs = _funcs_of(odes)
    t = funcs[0].args[0]
    # Maple converts floats to rationals and answers exactly
    rat = (lambda e: sp.nsimplify(e, rational=True)) if has_float(eqs) else (lambda e: e)
    exprs = [rat(e.lhs - e.rhs) for e in odes]
    ics = [MEquation(rat(e.lhs), rat(e.rhs)) for e in ics]
    ic_parts = [p for p in map(_ic_parts, ics) if p is not None]
    if len(exprs) == 1 and len(funcs) == 1:
        y = funcs[0]
        conds = [(k, t0, v) for f, k, t0, v in ic_parts if f == y.func]
        consts = (sp.Symbol(f"c__{i}") for i in itertools.count(1))
        gen = solve_linear(exprs[0], y, t, consts, conds[0][1] if conds else None)
        if gen is not None:
            sol = apply_ics(*gen, conds, t) if conds else gen[0]
            return NULL if sol is None else MEquation(y, sol)
        if linear_coeffs(exprs[0], y, t) is None and ode_order(exprs[0], y, t) > 1:
            roots = solve_autonomous(exprs[0], y, t, conds)
            # higher-order nonlinear ODEs: give up quietly (SymPy may not return)
            return make_seq([MEquation(y, r) for r in roots]) if roots else NULL
    ic_map = {_ic_lhs(e.lhs, t): e.rhs for e in ics}
    sym_eqs = [sp.Eq(e, 0) for e in exprs]
    try:
        if len(sym_eqs) == 1:
            try:    # Bernoulli gives explicit answers (like Maple) where 'separable' is implicit
                sol = sp.dsolve(sym_eqs[0], funcs[0], hint="Bernoulli", ics=ic_map or None)
            except ValueError:
                sol = sp.dsolve(sym_eqs[0], funcs[0], ics=ic_map or None)
        else:
            sol = sp.dsolve(sym_eqs, funcs, ics=ic_map or None)
    except NotImplementedError:
        return NULL
    sols = [MEquation(s.lhs, _rename_constants(s.rhs)) for s in (sol if isinstance(sol, list) else [sol])]
    if len(sym_eqs) > 1:
        return MSet(sols)
    return make_seq(_plus_first(sols))


def _ic_lhs(lhs, t):
    """SymPy wants D(x)(0) as Subs(Derivative(x(t), t), t, 0) in the ODE's own variable."""
    if isinstance(lhs, sp.Subs) and isinstance(lhs.expr, sp.Derivative) and t is not None:
        der = lhs.expr
        f = type(der.expr)
        n = sum(int(c) for _, c in der.variable_count)
        return sp.Subs(sp.Derivative(f(t), (t, n)), t, lhs.point[0])
    return lhs


def _is_ic(e):
    return isinstance(e.lhs, (AppliedUndef, sp.Subs)) and not e.rhs.has(sp.Derivative)


@builtin("odetest", sig="odetest(sol, ode)",
         doc="Residual of an ODE (and initial conditions) at a dsolve solution: 0 when satisfied.")
def m_odetest(ctx, sol, ode):
    reps = {e.lhs.func: (e.lhs.args[0], e.rhs) for e in equations_of(sol)
            if isinstance(e, MEquation) and isinstance(e.lhs, AppliedUndef) and len(e.lhs.args) == 1}

    def plug(e):
        e = e.replace(lambda a: isinstance(a, AppliedUndef) and a.func in reps,
                      lambda a: reps[a.func][1].subs(reps[a.func][0], a.args[0]))
        return sp.simplify(e.doit())
    res = []
    rat = (lambda e: sp.nsimplify(e, rational=True)) if has_float(ode) else (lambda e: e)
    for e in equations_of(ode):
        e = MEquation(rat(e.lhs), rat(e.rhs)) if isinstance(e, MEquation) else MEquation(rat(e), sp.Integer(0))
        res.append(plug(e.rhs - e.lhs) if _is_ic(e) else plug(e.lhs - e.rhs))
    if isinstance(ode, MSet):
        return MSet(res)
    return MList(res) if isinstance(ode, MList) else make_seq(res)


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
        self.last = (t0, list(y0))

    def at(self, tv):
        tv = float(tv)
        # plots and fsolve sample nearby points in turn: restart from the closest known state
        ts, ys = self.last if abs(tv - self.last[0]) < abs(tv - self.t0) else (self.t0, self.y0)
        y = rk45(self.F, ts, ys, tv)
        self.last = (tv, y)
        return y

    def labels(self):
        out = []
        for f, k in self.states:
            out.append(f if k == 0 else sp.Derivative(f, (self.t, k)) if k > 1 else sp.Derivative(f, self.t))
        return out


_numeric_ids = itertools.count(1)


def _numeric_function(fn):
    """The call of a numeric-solution procedure on a non-number stays unevaluated (as in Maple);
    it evaluates as soon as the argument becomes a number, and through `_imp_` in lambdify/evalf
    (plot, fsolve). Names are unique because lambdify keys implementations by name."""
    def eval_(cls, x):
        if x.is_number and x.is_extended_real:
            return sp.Float(fn(float(x)), 15)
    return type(f"dsolve_numeric{next(_numeric_ids)}", (sp.Function,),
                {"nargs": 1, "eval": classmethod(eval_), "_imp_": staticmethod(fn)})


def _proc_label(param):
    return f"proc ({param}) `...` end proc"


def _numeric(ctx, odes, ics, output):
    funcs = _funcs_of(odes)
    t = funcs[0].args[0]
    states, F = _first_order_system(odes, funcs, t)
    t0, y0 = _ic_values(ics, states, t)
    ns = NumericSolution(t, funcs, states, F, t0, y0)
    labels = ns.labels()
    if output is not None and str(output) == "listprocedure":
        items = [MEquation(t, AppliedProc(lambda c, a: a[0], name=_proc_label(t)))]
        for i, l in enumerate(labels):
            items.append(MEquation(l, _component_proc(ns, i)))
        return MList(items)

    def at_point(ctx_, args):
        tv = args[0]
        if not (isinstance(tv, sp.Basic) and tv.is_number):
            return sp.Function("dsolve_numeric")(tv)
        tv = float(sp.N(tv))
        return MList([MEquation(t, sp.Float(tv, 15))] +
                     [MEquation(l, sp.Float(v, 15)) for l, v in zip(labels, ns.at(tv))])
    p = AppliedProc(at_point, name=_proc_label("x_rkf45"))
    p.numeric_solution = ns
    return p


def _component_proc(ns, i):
    f = _numeric_function(lambda tv: ns.at(tv)[i])
    p = AppliedProc(lambda ctx, args: f(*args), name=_proc_label(ns.t))
    p.numeric_solution = ns
    p.component = i
    return p
