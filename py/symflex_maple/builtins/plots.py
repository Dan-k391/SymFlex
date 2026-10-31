"""Plotting: plot / logplot family / pointplot / display / odeplot producing PlotSpec dicts
(docs/ARCHITECTURE.md).  First working versions."""
from __future__ import annotations

import math

import sympy as sp

from ..errors import MapleError
from ..printer import lprint
from ..values import (
    AppliedProc, MEquation, MList, MRange, MSet, MString, PlotValue, Procedure, deep_map,
)
from . import Library

lib = Library()
builtin = lib.builtin

PLOT_OPTIONS = {
    "legend": None, "color": None, "colour": None, "style": None, "thickness": None,
    "numpoints": None, "title": None, "labels": None, "linestyle": None, "scaling": None,
    "view": None, "axes": None, "discont": None, "gridlines": None, "symbol": None,
    "symbolsize": None, "adaptive": None, "filled": None, "font": None, "titlefont": None,
    "labelfont": None, "tickmarks": None, "size": None, "caption": None, "transparency": None,
    "axis": None, "legendstyle": None, "resolution": None, "sample": None, "smartview": None,
    "frames": None, "coords": None, "refine": None, "connect": None,
}
PALETTE = ["#c00000", "#0000c0", "#008000", "#c000c0", "#00a0a0", "#c08000", "#606060", "#000000"]


def register(env):
    lib.register(env)


def empty_spec(kind="2d"):
    return {"type": kind, "title": "", "xlabel": "", "ylabel": "", "zlabel": "", "xlog": False,
            "ylog": False, "xrange": None, "yrange": None, "scaling": "unconstrained",
            "curves": []}


def _num(v):
    try:
        return float(sp.N(v))
    except (TypeError, ValueError):
        raise MapleError(f"expected a numeric value, received {lprint(v)}")


def _text(v):
    return str(v) if isinstance(v, MString) else lprint(v)


def numeric_function(ctx, f, var=None):
    """A float -> float|None evaluator for an expression in var, or a procedure."""
    if isinstance(f, Procedure):
        def g(x):
            try:
                r = ctx.apply(f, [sp.Float(x, 15)])
                return _to_float(r)
            except Exception:  # noqa: BLE001 - undefined points become gaps
                return None
        return g
    if not isinstance(f, sp.Basic):
        raise MapleError(f"invalid plotting of {lprint(f)}")
    expr = f
    free = expr.free_symbols - ({var} if var is not None else set())
    if free:
        raise MapleError("expected a real constant or expression in the plotting variable, but "
                         f"received {lprint(expr)}")
    try:
        fn = sp.lambdify([var] if var is not None else [], expr, modules=["math", "mpmath"])
    except Exception:  # noqa: BLE001
        fn = None

    def g(x):
        try:
            r = fn(x) if var is not None else fn()
            return _to_float(r)
        except Exception:  # noqa: BLE001
            try:
                return _to_float(expr.subs(var, x).evalf(15) if var is not None else expr.evalf(15))
            except Exception:  # noqa: BLE001
                return None
    return g


def _to_float(r):
    if isinstance(r, (int, float)):
        r = float(r)
    elif isinstance(r, complex):
        if abs(r.imag) > 1e-12 * max(1.0, abs(r.real)):
            return None
        r = r.real
    else:
        try:
            c = complex(r)
        except (TypeError, ValueError):
            return None
        if abs(c.imag) > 1e-12 * max(1.0, abs(c.real)):
            return None
        r = c.real
    return r if math.isfinite(r) else None


def sample(g, a, b, n=200, refine=True):
    """Uniform samples plus one refinement pass where the curve bends sharply."""
    xs = [a + (b - a) * i / (n - 1) for i in range(n)]
    ys = [g(x) for x in xs]
    if not refine:
        return xs, ys
    out_x, out_y = [xs[0]], [ys[0]]
    span = [y for y in ys if y is not None]
    scale = (max(span) - min(span)) if span else 1.0
    scale = scale or 1.0
    for i in range(1, len(xs)):
        if i + 1 < len(xs) and None not in (ys[i - 1], ys[i], ys[i + 1]):
            bend = abs(ys[i + 1] - 2 * ys[i] + ys[i - 1]) / scale
            if bend > 0.05:
                for k in (1, 2, 3):
                    xm = xs[i - 1] + (xs[i] - xs[i - 1]) * k / 4
                    out_x.append(xm)
                    out_y.append(g(xm))
        out_x.append(xs[i])
        out_y.append(ys[i])
    return out_x, out_y


def _curve(xs, ys, i, legend=None, opts=None):
    opts = opts or {}
    color = opts.get("color")
    if isinstance(color, MList):
        color = color.items[i] if i < len(color.items) else None
    style = opts.get("style")
    if isinstance(style, MList):
        style = style.items[i] if i < len(style.items) else None
    thick = opts.get("thickness")
    if isinstance(thick, MList):
        thick = thick.items[i] if i < len(thick.items) else None
    dash = opts.get("linestyle")
    if isinstance(dash, MList):
        dash = dash.items[i] if i < len(dash.items) else None
    return {"x": xs, "y": ys, "legend": legend or "", "color": _color(color, i),
            "style": "point" if style is not None and _text(style) == "point" else "line",
            "thickness": int(_num(thick)) if thick is not None else 1,
            "dash": _text(dash).lower() if dash is not None else "solid"}


def _color(c, i):
    if c is None:
        return PALETTE[i % len(PALETTE)]
    s = _text(c).strip('"')
    return s


def _legends(opts, n):
    lg = opts.get("legend")
    if lg is None:
        return [""] * n
    items = list(lg.items) if isinstance(lg, MList) else [lg]
    return [_text(x) for x in items] + [""] * (n - len(items))


def _apply_common(spec, opts, var=None):
    if var is not None and not spec["xlabel"]:
        spec["xlabel"] = _text(var)
    if opts.get("title") is not None:
        spec["title"] = _text(opts["title"])
    if opts.get("labels") is not None and isinstance(opts["labels"], MList):
        labs = [_text(x) for x in opts["labels"].items]
        spec["xlabel"], spec["ylabel"] = (labs + ["", ""])[:2]
    if opts.get("scaling") is not None:
        spec["scaling"] = _text(opts["scaling"])
    view = opts.get("view")
    if isinstance(view, MList) and len(view.items) == 2:
        for key, r in zip(("xrange", "yrange"), view.items):
            if isinstance(r, MRange):
                spec[key] = [_num(r.lo), _num(r.hi)]
    elif isinstance(view, MRange):
        spec["yrange"] = [_num(view.lo), _num(view.hi)]
    return spec


def plot2d(ctx, args, opts, xlog=False, ylog=False):
    """Shared implementation of plot / logplot / loglogplot / semilogplot."""
    args = list(args)
    if not args:
        raise MapleError("invalid input: plot expects at least 1 argument")
    f = args[0]
    ranges = [a for a in args[1:] if isinstance(a, (MEquation, MRange))]
    if not ranges and len(args) > 1 and isinstance(args[1], sp.Symbol):
        # plot(f, x): Maple's default range, -2*Pi..2*Pi when trig functions are involved
        x = args[1]
        trig = isinstance(f, sp.Basic) and f.has(sp.sin, sp.cos, sp.tan, sp.sec, sp.csc, sp.cot)
        lim = 2 * sp.pi if trig else sp.Integer(10)
        ranges = [MEquation(x, MRange(-lim, lim))]
    n = int(_num(opts["numpoints"])) if opts.get("numpoints") is not None else 200
    spec = empty_spec()
    spec["xlog"], spec["ylog"] = xlog, ylog
    var, a, b = None, -10.0, 10.0
    if ranges:
        r0 = ranges[0]
        if isinstance(r0, MEquation) and isinstance(r0.rhs, MRange):
            var, a, b = r0.lhs, _num(r0.rhs.lo), _num(r0.rhs.hi)
        elif isinstance(r0, MRange):
            a, b = _num(r0.lo), _num(r0.hi)
        if len(ranges) > 1:
            r1 = ranges[1]
            rr = r1.rhs if isinstance(r1, MEquation) else r1
            if isinstance(rr, MRange):
                spec["yrange"] = [_num(rr.lo), _num(rr.hi)]
                if isinstance(r1, MEquation):
                    spec["ylabel"] = _text(r1.lhs)
    spec["xrange"] = [a, b]

    def xsamples(g):
        if xlog:
            la, lb = math.log10(a), math.log10(b)
            xs, ys = sample(lambda u: g(10 ** u), la, lb, n)
            return [10 ** u for u in xs], ys
        return sample(g, a, b, n)

    items = list(f.items) if isinstance(f, (MList, MSet)) else [f]
    # parametric [x(t), y(t), t = a..b]
    if isinstance(f, MList) and len(f.items) == 3 and isinstance(f.items[2], MEquation) and \
            isinstance(f.items[2].rhs, MRange):
        t, ta, tb = f.items[2].lhs, _num(f.items[2].rhs.lo), _num(f.items[2].rhs.hi)
        gx, gy = numeric_function(ctx, f.items[0], t), numeric_function(ctx, f.items[1], t)
        ts = [ta + (tb - ta) * i / (n - 1) for i in range(n)]
        spec["curves"].append(_curve([gx(x) for x in ts], [gy(x) for x in ts], 0,
                                     _legends(opts, 1)[0], opts))
        spec["xrange"] = None
        return _apply_common(spec, opts)
    # point data [[x1, y1], [x2, y2], ...]
    if isinstance(f, MList) and f.items and all(isinstance(p, MList) and len(p.items) == 2
                                                 for p in f.items):
        xs = [_num(p.items[0]) for p in f.items]
        ys = [_num(p.items[1]) for p in f.items]
        spec["curves"].append(_curve(xs, ys, 0, _legends(opts, 1)[0], opts))
        spec["xrange"] = None
        return _apply_common(spec, opts)
    legends = _legends(opts, len(items))
    for i, item in enumerate(items):
        if isinstance(item, MList) and len(item.items) == 3 and isinstance(item.items[2], MEquation):
            sub = plot2d(ctx, [item], opts)
            for c in sub["curves"]:
                c["legend"] = legends[i]
                spec["curves"].append(c)
            continue
        g = numeric_function(ctx, item, var)
        xs, ys = xsamples(g)
        spec["curves"].append(_curve(xs, ys, i, legends[i], opts))
    return _apply_common(spec, opts, var)


@builtin("plot", sig="plot(f, x = a..b, options)", doc="2-D plot of expressions, procedures or parametric curves.",
         options=PLOT_OPTIONS)
def m_plot(ctx, *args, **opts):
    return PlotValue(plot2d(ctx, args, opts))


@builtin("logplot", package="plots", sig="logplot(f, x = a..b)", doc="Plot with a logarithmic vertical axis.",
         options=PLOT_OPTIONS)
def m_logplot(ctx, *args, **opts):
    return PlotValue(plot2d(ctx, args, opts, ylog=True))


@builtin("semilogplot", package="plots", sig="semilogplot(f, x = a..b)",
         doc="Plot with a logarithmic horizontal axis.", options=PLOT_OPTIONS)
def m_semilogplot(ctx, *args, **opts):
    return PlotValue(plot2d(ctx, args, opts, xlog=True))


@builtin("loglogplot", package="plots", sig="loglogplot(f, x = a..b)",
         doc="Plot with logarithmic axes.", options=PLOT_OPTIONS)
def m_loglogplot(ctx, *args, **opts):
    return PlotValue(plot2d(ctx, args, opts, xlog=True, ylog=True))


@builtin("pointplot", package="plots", sig="pointplot([[x1, y1], ...])", doc="Plot points.",
         options=PLOT_OPTIONS)
def m_pointplot(ctx, pts, *args, **opts):
    opts.setdefault("style", sp.Symbol("point"))
    return PlotValue(plot2d(ctx, [pts, *args], opts))


@builtin("listplot", package="plots", sig="listplot([y1, y2, ...])", doc="Plot a list of values.",
         options=PLOT_OPTIONS)
def m_listplot(ctx, data, *args, **opts):
    items = list(data.items)
    if items and not isinstance(items[0], MList):
        items = [MList([sp.Integer(i), y]) for i, y in enumerate(items, 1)]
    return PlotValue(plot2d(ctx, [MList(items), *args], opts))


@builtin("display", package="plots", sig="display(p1, p2, ...)", doc="Combine plots.",
         options=dict(PLOT_OPTIONS, insequence=None))
def m_display(ctx, *plots, insequence=None, **opts):
    items = []
    for p in plots:
        items += list(p.items) if isinstance(p, (MList, MSet)) else [p]
    specs = [p.spec for p in items if isinstance(p, PlotValue)]
    if not specs:
        raise MapleError("invalid input: display expects plot structures")
    out = dict(specs[0])
    if insequence is not None and str(insequence) == "true":
        out = dict(specs[0])
        out["frames"] = specs
        return PlotValue(out)
    out["curves"] = [c for s in specs for c in s.get("curves", [])]
    for key in ("xlog", "ylog"):
        out[key] = any(s.get(key) for s in specs)
    xr = [s["xrange"] for s in specs if s.get("xrange")]
    if xr:
        out["xrange"] = [min(r[0] for r in xr), max(r[1] for r in xr)]
    return PlotValue(_apply_common(out, opts))


@builtin("odeplot", package="plots", sig="odeplot(sol, [t, x(t)], a..b)", doc="Plot a numeric dsolve solution.",
         options=PLOT_OPTIONS)
def m_odeplot(ctx, sol, what=None, rng=None, *rest, **opts):
    from .ode import rk45
    ns = getattr(sol, "numeric_solution", None)
    if ns is None:
        raise MapleError("odeplot expects the result of dsolve(..., numeric)")
    if isinstance(what, MRange) and rng is None:
        what, rng = None, what
    if rng is None:
        a, b = ns.t0, ns.t0 + 10
    elif isinstance(rng, MEquation):
        a, b = _num(rng.rhs.lo), _num(rng.rhs.hi)
    else:
        a, b = _num(rng.lo), _num(rng.hi)
    n = int(_num(opts["numpoints"])) if opts.get("numpoints") is not None else 200
    ts = [a + (b - a) * i / (n - 1) for i in range(n)]
    # integrate sequentially from t0 to each sample
    states = []
    y = ns.at(a)
    tprev = a
    for tv in ts:
        y = rk45(ns.F, tprev, y, tv)
        tprev = tv
        states.append(y)
    labels = ns.labels()
    pairs = what.items if isinstance(what, MList) and what.items and isinstance(what.items[0], MList) \
        else [what] if what is not None else [MList([ns.t, labels[0]])]

    def series(e):
        vals = []
        for tv, ys in zip(ts, states):
            reps = {ns.t: tv}
            reps.update({l: v for l, v in zip(labels, ys)})
            ex = e
            for k in sorted(reps, key=lambda z: -len(str(z))):
                ex = ex.subs(k, reps[k]) if isinstance(ex, sp.Basic) else ex
            vals.append(_to_float(ex))
        return vals
    spec = empty_spec()
    legends = _legends(opts, len(pairs))
    for i, p in enumerate(pairs):
        xe, ye = p.items[0], p.items[1]
        spec["curves"].append(_curve(series(xe), series(ye), i, legends[i], opts))
        if i == 0:
            spec["xlabel"], spec["ylabel"] = _text(xe), _text(ye)
    return PlotValue(_apply_common(spec, opts))
