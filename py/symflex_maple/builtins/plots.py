"""Plotting: plot / logplot family / pointplot / listplot / display / odeplot / animate / plot3d /
spacecurve / implicitplot / textplot producing PlotSpec dicts (docs/ARCHITECTURE.md).
Sampling, discontinuities and smartview live in plots_numeric.py."""
from __future__ import annotations

import math

import sympy as sp
from sympy.core.function import AppliedUndef

from ..errors import MapleError
from ..printer import lprint
from ..values import MEquation, MList, MMatrix, MRange, MSet, MString, PlotValue, Procedure, deep_map
from . import Library, is_true
from .plots_numeric import (
    adaptive, discontinuities, evaluator, free_names, implicit_curves, open_samples, smart_range,
    to_float,
)

lib = Library()
builtin = lib.builtin

PLOT_OPTIONS = {
    "legend": None, "color": None, "colour": None, "style": None, "thickness": None,
    "numpoints": None, "title": None, "labels": None, "linestyle": None, "scaling": None,
    "view": None, "axes": None, "discont": None, "gridlines": None, "symbol": None,
    "symbolsize": None, "adaptive": None, "filled": None, "font": None, "titlefont": None,
    "labelfont": None, "tickmarks": None, "size": None, "caption": None, "transparency": None,
    "axis": None, "legendstyle": None, "resolution": None, "sample": None, "smartview": None,
    "coords": None, "refine": None, "connect": None, "labeldirections": None, "axesfont": None,
    "background": None, "captionfont": None,
}
PLOT3D_OPTIONS = dict(PLOT_OPTIONS, grid=None, shading=None, lightmodel=None, orientation=None,
                      glossiness=None, contours=None, projection=None)
LINESTYLES = ["solid", "dot", "dash", "dashdot", "longdash", "spacedash", "spacedot"]
TRIG = (sp.sin, sp.cos, sp.tan, sp.sec, sp.csc, sp.cot)


def register(env):
    lib.register(env)


def empty_spec(kind="2d"):
    return {"type": kind, "title": "", "xlabel": "", "ylabel": "", "zlabel": "", "xlog": False,
            "ylog": False, "xrange": None, "yrange": None, "scaling": "unconstrained",
            "curves": []}


def _num(ctx, v):
    if not isinstance(v, sp.Basic):
        r = None
    elif v.is_Float:   # the decimal value (0.1, not its 10-digit binary approximation)
        r = to_float(float(str(v)))
    else:   # ranges like 0..2*Pi to full double precision, not Digits
        r = to_float(sp.N(v, 17)) if v.is_number else to_float(ctx.evalf(v))
    if r is None:
        if isinstance(v, sp.Basic) and v.has(sp.oo, -sp.oo):
            raise MapleError("infinite plotting ranges are not supported in SymFlex")
        raise MapleError(f"expected a real constant, received {lprint(v)}")
    return r


def _text(v):
    if isinstance(v, MString):
        return str(v)
    if getattr(v, "func", None) is not None and str(v.func) == "typeset":   # typeset("x = ", x)
        return "".join(_text(a) for a in v.args)
    return lprint(v)


def _opt(opts, key, i):
    """Option value for curve i: a list option distributes over the curves."""
    v = opts.get(key)
    if isinstance(v, MList):
        return v.items[i] if i < len(v.items) else None
    return v


def _color(c):
    """An explicit colour option as CSS; "" when none (the UI then picks from its palette by "ci")."""
    if c is None:
        return ""
    if isinstance(c, AppliedUndef) and type(c).__name__ in ("RGB", "COLOR", "COLOUR") and len(c.args) >= 3:
        r, g, b = (max(0, min(255, round(255 * float(v)))) for v in c.args[-3:])
        return f"rgb({r},{g},{b})"
    return _text(c).strip('"')


def _dash(d):
    if d is None:
        return "solid"
    if isinstance(d, sp.Integer) and 1 <= int(d) <= len(LINESTYLES):
        return LINESTYLES[int(d) - 1]
    return _text(d).lower()


def _curve(ctx, xs, ys, i, opts, zs=None, legend=None, style=None):
    """One PlotSpec curve; i indexes list-valued options and the default colour sequence."""
    if legend is None:
        lg = _opt(opts, "legend", i)
        legend = "" if lg is None else _text(lg)
    st = style or _opt(opts, "style", i)
    thick = _opt(opts, "thickness", i)
    c = {"x": xs, "y": ys, "legend": legend,
         "color": _color(_opt(opts, "color", i) or _opt(opts, "colour", i)), "ci": i,
         "style": "point" if st is not None and _text(st).lower() == "point" else "line",
         "thickness": int(_num(ctx, thick)) if thick is not None else 1,
         "dash": _dash(_opt(opts, "linestyle", i))}
    if zs is not None:
        c["z"] = zs
    sym, size = _opt(opts, "symbol", i), _opt(opts, "symbolsize", i)
    if sym is not None:
        c["symbol"] = _text(sym).lower()
    if size is not None:
        c["symbolsize"] = int(_num(ctx, size))
    return c


def _range(ctx, r):
    return [_num(ctx, r.lo), _num(ctx, r.hi)]


def _apply_common(ctx, spec, opts):
    """Plot-level options: title, labels, view, scaling, axes, gridlines."""
    if opts.get("title") is not None:
        spec["title"] = _text(opts["title"])
    labels = opts.get("labels")
    if isinstance(labels, MList):
        for key, lab in zip(("xlabel", "ylabel", "zlabel"), labels.items):
            spec[key] = _text(lab)
    if opts.get("scaling") is not None:
        spec["scaling"] = _text(opts["scaling"]).lower()
    view = opts.get("view")
    if isinstance(view, MList):
        for key, r in zip(("xrange", "yrange", "zrange"), view.items):
            if isinstance(r, MRange):
                spec[key] = _range(ctx, r)
    elif isinstance(view, MRange):
        spec["zrange" if spec["type"] == "3d" else "yrange"] = _range(ctx, view)
    if opts.get("axes") is not None:
        spec["axes"] = _text(opts["axes"]).lower()
    if opts.get("gridlines") is not None:
        spec["gridlines"] = is_true(opts["gridlines"])
    return spec


def _numbers(ctx, v):
    """Floats of a list / Vector of numbers, else None."""
    items = v.items if isinstance(v, MList) else list(v.m) if isinstance(v, MMatrix) and 1 in v.m.shape \
        else None
    if not items or not all(isinstance(x, sp.Basic) and x.is_number for x in items):
        return None
    return [to_float(ctx.evalf(x)) for x in items]


def _point_list(ctx, v, dim=2):
    """[[x, y], ...] (or a 2-column Matrix) -> column lists, else None."""
    if isinstance(v, MMatrix) and 1 not in v.m.shape and v.m.shape[1] == dim:
        rows = [list(v.m.row(i)) for i in range(v.m.rows)]
    elif isinstance(v, MList) and v.items and all(isinstance(p, MList) and len(p.items) == dim for p in v.items):
        rows = [p.items for p in v.items]
    else:
        return None
    if not all(isinstance(x, sp.Basic) and x.is_number for r in rows for x in r):
        return None
    return [[to_float(ctx.evalf(r[k])) for r in rows] for k in range(dim)]


def _is_param(item):
    return isinstance(item, MList) and len(item.items) == 3 and (
        isinstance(item.items[2], MRange) or
        isinstance(item.items[2], MEquation) and isinstance(item.items[2].rhs, MRange))


def _depth(opts):
    ad = opts.get("adaptive")
    if ad is None or is_true(ad):
        return 6
    if isinstance(ad, sp.Integer):
        return int(ad)
    return 0


def _initial(ctx, lo, hi, opts, n):
    s = opts.get("sample")
    if isinstance(s, MList):
        return sorted(_num(ctx, v) for v in s.items)
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def _warn_names(ctx, expr, var, names):
    found = f"name {names[0]}" if len(names) == 1 else f"names [{', '.join(names)}]"
    ctx.warn(f"expecting only range variable {lprint(var) if var is not None else ''} in expression "
             f"{lprint(expr)} to be plotted but found {found}")


def _screen(xlog, ylog):
    """(x, y) data point -> sampling (screen) coordinates, None where a log axis cannot show it."""
    def f(x, y):
        if x is None or y is None or (xlog and x <= 0) or (ylog and y <= 0):
            return None
        return (math.log10(x) if xlog else x, math.log10(y) if ylog else y)
    return f


def _unscreen(pts, xlog, ylog):
    xs = [None if p is None else 10 ** p[0] if xlog else p[0] for p in pts]
    ys = [None if p is None else 10 ** p[1] if ylog else p[1] for p in pts]
    return xs, ys


def _function_curves(ctx, item, var, a, b, opts, i, xlog, ylog):
    """Curves of one function plot item (several when discont=true splits it)."""
    n = int(_num(ctx, opts["numpoints"])) if opts.get("numpoints") is not None else 200
    depth = _depth(opts)
    if isinstance(item, sp.Basic):
        names = free_names(ctx, item, [var] if var is not None else [])
        if names:
            _warn_names(ctx, item, var, names)
            # Maple's degenerate curve when the expression involves the variable, else nothing
            return [_curve(ctx, [0.0, None], [0.0, None], i, opts)] if var in item.free_symbols else []
        g1 = evaluator(ctx, item, [var] if var is not None else [])
        g = g1 if var is not None else (lambda x: g1())
    else:
        g = evaluator(ctx, item, [None])
    polar = opts.get("coords") is not None and _text(opts["coords"]) == "polar"
    to_screen = _screen(xlog and not polar, ylog and not polar)

    def point(t):
        x = 10 ** t if xlog and not polar else t
        y = g(x)
        if polar:
            return None if y is None else (y * math.cos(x), y * math.sin(x))
        return to_screen(x, y)
    lo, hi = (math.log10(a), math.log10(b)) if xlog and not polar else (a, b)
    marks = []
    if is_true(opts.get("discont")) and isinstance(item, sp.Basic) and var is not None:
        ds = discontinuities(item, var, a, b, g)
        marks = [d for d, m in ds if m]
        cuts = [math.log10(d) if xlog else d for d, _ in ds if a < d < b and (not xlog or d > 0)]
        bounds = [lo] + cuts + [hi]
        pieces = [adaptive(point, open_samples(p, q, n, refine_lo=k > 0, refine_hi=k < len(cuts)), depth)
                  for k, (p, q) in enumerate(zip(bounds, bounds[1:]))]
    else:
        pieces = [adaptive(point, _initial(ctx, lo, hi, opts, n), depth)]
    curves = []
    for k, pts in enumerate(pieces):
        xs, ys = _unscreen(pts, xlog and not polar, ylog and not polar)
        curves.append(_curve(ctx, xs, ys, i, opts, legend=None if k == 0 else ""))
    if is_true(opts.get("filled")) and not polar:   # the region between the curve and the axis
        fill = []
        for c in curves:
            pts = [(x, y) for x, y in zip(c["x"], c["y"]) if x is not None]
            if pts:
                fill += [(pts[0][0], 0.0)] + pts + [(pts[-1][0], 0.0), (pts[0][0], 0.0)]
        if fill:
            poly = _curve(ctx, [p[0] for p in fill], [p[1] for p in fill], i, opts, legend="")
            poly["filled"] = True
            curves.append(poly)
    pts = [(d, g(d)) for d in marks if g(d) is not None]
    if pts:
        curves.append(_curve(ctx, [p[0] for p in pts], [p[1] for p in pts], i, opts, legend="", style=sp.Symbol("point")))
    return curves


def _param_curve(ctx, item, opts, i, xlog, ylog):
    fx, fy, r = item.items
    var, rng = (r.lhs, r.rhs) if isinstance(r, MEquation) else (None, r)
    a, b = _range(ctx, rng)
    vs = [var] if var is not None else [None]
    gx, gy = evaluator(ctx, fx, vs), evaluator(ctx, fy, vs)
    n = int(_num(ctx, opts["numpoints"])) if opts.get("numpoints") is not None else 200
    polar = opts.get("coords") is not None and _text(opts["coords"]) == "polar"
    to_screen = _screen(xlog, ylog)

    def point(t):
        u, v = gx(t), gy(t)
        if polar:
            return None if u is None or v is None else (u * math.cos(v), u * math.sin(v))
        return to_screen(u, v)
    pts = adaptive(point, _initial(ctx, a, b, opts, n), _depth(opts))
    xs, ys = _unscreen(pts, xlog and not polar, ylog and not polar)
    return _curve(ctx, xs, ys, i, opts)


def plot2d(ctx, args, opts, xlog=False, ylog=False):
    """Shared implementation of plot / logplot / loglogplot / semilogplot."""
    args = list(args)
    if not args:
        raise MapleError("invalid input: plot expects at least 1 argument")
    f, rest = args[0], args[1:]
    spec = empty_spec()
    spec["xlog"], spec["ylog"] = xlog, ylog
    xs = _numbers(ctx, f)
    if xs is not None and rest and _numbers(ctx, rest[0]) is not None:   # plot(X, Y) data
        ys = _numbers(ctx, rest[0])
        if len(xs) != len(ys):
            raise MapleError("the data lists must have the same length")
        spec["curves"].append(_curve(ctx, xs, ys, 0, opts))
        return _apply_common(ctx, spec, opts)
    var, xr, yr = None, None, None
    for r in rest:
        if isinstance(r, MEquation) and isinstance(r.rhs, MRange) or isinstance(r, MRange):
            name, rr = (r.lhs, r.rhs) if isinstance(r, MEquation) else (None, r)
            if xr is None:
                var, xr = name, rr
            elif yr is None:
                yr = rr
                if name is not None:
                    spec["ylabel"] = _text(name)
        elif isinstance(r, sp.Symbol) and xr is None and var is None:
            var = r
        else:
            raise MapleError(f"unexpected option: {lprint(r)}")
    items = list(f.items) if isinstance(f, (MList, MSet)) and not _is_param(f) and \
        _point_list(ctx, f) is None else [f]
    funcs = [it for it in items if not _is_param(it) and _point_list(ctx, it) is None]
    if var is None:
        names = set()
        for it in funcs:
            if isinstance(it, sp.Basic):
                names |= set(free_names(ctx, it, []))
        if len(names) > 1:
            if xr is None:
                raise MapleError("cannot determine plotting variable")
        elif names:
            var = sp.Symbol(names.pop())
    if xr is None:
        trig = any(isinstance(it, sp.Basic) and it.has(*TRIG) for it in funcs)
        a, b = (-2 * math.pi, 2 * math.pi) if trig else (-10.0, 10.0)
    else:
        a, b = _range(ctx, xr)
    if xlog and (a <= 0 or b <= 0):
        raise MapleError("the horizontal range must be positive for a logarithmic axis")
    func_curves = []
    for i, item in enumerate(items):
        pts = _point_list(ctx, item)
        if pts is not None:
            spec["curves"].append(_curve(ctx, pts[0], pts[1], i, opts))
        elif _is_param(item):
            spec["curves"].append(_param_curve(ctx, item, opts, i, xlog, ylog))
            spec["curves"][-1]["label"] = lprint(MList(item.items[:2]))
        else:
            cs = _function_curves(ctx, item, var, a, b, opts, i, xlog, ylog)
            if cs:   # names the curve in the UI's automatic legend (several curves, no legend option)
                cs[0]["label"] = lprint(item)
            spec["curves"] += cs
            func_curves += cs
    if func_curves and opts.get("coords") is None:
        spec["xrange"] = [a, b]
        if var is not None:
            spec["xlabel"] = _text(var)
    if yr is not None:
        spec["yrange"] = _range(ctx, yr)
    elif func_curves and not ylog and opts.get("view") is None and \
            not (opts.get("smartview") is not None and not is_true(opts["smartview"])):
        spec["yrange"] = smart_range([(c["x"], c["y"]) for c in func_curves if not c.get("filled")],
                                     xlog=xlog)
    return _apply_common(ctx, spec, opts)


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


@builtin("polarplot", package="plots", sig="polarplot(r, theta = a..b)", doc="Plot in polar coordinates.",
         options=PLOT_OPTIONS)
def m_polarplot(ctx, f, *args, **opts):
    if not args and not _is_param(f):
        syms = sorted(f.free_symbols, key=str) if isinstance(f, sp.Basic) else []
        args = (MEquation(syms[0], MRange(-sp.pi, sp.pi)) if syms else MRange(-sp.pi, sp.pi),)
    opts["coords"] = sp.Symbol("polar")
    spec = plot2d(ctx, [f, *args], opts)
    spec["xlabel"] = spec["ylabel"] = ""
    return PlotValue(spec)


def _points_spec(ctx, pts, rest, opts, style="point"):
    """pointplot / listplot data -> PlotSpec (2-D, or 3-D for [x, y, z] points)."""
    cols = _point_list(ctx, pts)
    if cols is None and rest and _numbers(ctx, pts) is not None and _numbers(ctx, rest[0]) is not None:
        cols, rest = [_numbers(ctx, pts), _numbers(ctx, rest[0])], rest[1:]
    if cols is None and (cols3 := _point_list(ctx, pts, 3)) is not None:
        spec = empty_spec("3d")
        spec["curves"].append(_curve(ctx, cols3[0], cols3[1], 0, opts, zs=cols3[2], style=sp.Symbol(style)))
        return _apply_common(ctx, spec, opts)
    if cols is None:
        raise MapleError(f"points are not in the correct format: {lprint(pts)}")
    if is_true(opts.get("connect")):
        style = "line"
    spec = empty_spec()
    spec["curves"].append(_curve(ctx, cols[0], cols[1], 0, opts, style=opts.get("style") or sp.Symbol(style)))
    return _apply_common(ctx, spec, opts)


@builtin("pointplot", package="plots", sig="pointplot([[x1, y1], ...]) or pointplot(X, Y)", doc="Plot points.",
         options=PLOT_OPTIONS)
def m_pointplot(ctx, pts, *rest, **opts):
    return PlotValue(_points_spec(ctx, pts, rest, opts))


@builtin("pointplot3d", package="plots", sig="pointplot3d([[x1, y1, z1], ...])", doc="Plot points in 3-D.",
         options=PLOT_OPTIONS)
def m_pointplot3d(ctx, pts, *rest, **opts):
    return PlotValue(_points_spec(ctx, pts, rest, opts))


@builtin("listplot", package="plots", sig="listplot([y1, y2, ...])", doc="Plot a list of values.",
         options=PLOT_OPTIONS)
def m_listplot(ctx, data, *rest, **opts):
    ys = _numbers(ctx, data)
    if ys is not None and not rest:
        data = MList([MList([sp.Integer(i), y]) for i, y in enumerate(data.items if isinstance(data, MList)
                                                                     else list(data.m), 1)])
    return PlotValue(_points_spec(ctx, data, rest, opts, style="line"))


# ---------------------------------------------------------------- display
def _plot_items(v):
    if isinstance(v, (MList, MSet)):
        return [p for x in v.items for p in _plot_items(x)]
    return [v]


def _array_spec(ctx, call, opts):
    """display(Array([...])): a grid of plots, row-major."""
    data = call.args[0] if call.args else MList([])
    rows = data.items if isinstance(data, MList) else []
    if rows and not any(isinstance(r, MList) for r in rows):
        rows = [MList(rows)]
    grid = [[x for x in (r.items if isinstance(r, MList) else [r])] for r in rows]
    cols = max((len(r) for r in grid), default=0)
    cells = [_display_one(ctx, r[j], {}) if j < len(r) and isinstance(r[j], PlotValue) else None
             for r in grid for j in range(cols)]
    return {"type": "array", "rows": len(grid), "cols": cols, "cells": cells,
            "title": _text(opts["title"]) if opts.get("title") is not None else ""}


def _display_one(ctx, p, opts):
    return _apply_common(ctx, dict(p.spec), opts)


def merge_specs(ctx, specs, opts):
    """Superimpose PlotSpecs (display(p1, p2, ...)); animations are merged frame by frame."""
    animated = [s for s in specs if s.get("frames")]
    if animated:
        n = max(len(s["frames"]) for s in animated)
        frames = [merge_specs(ctx, [s["frames"][min(k, len(s["frames"]) - 1)] if s.get("frames") else s
                                    for s in specs], opts) for k in range(n)]
        out = dict(frames[0])
        out["frames"] = frames
        return out
    out = dict(specs[0])
    out["type"] = "3d" if any(s["type"] == "3d" for s in specs) else specs[0]["type"]
    # Each plot's default colours continue after the previous plot's (Maple restarts them, which
    # draws every single-curve plot of a display in the same colour).
    out["curves"], off = [], 0
    for s in specs:
        cs = s.get("curves", [])
        out["curves"] += [dict(c, ci=c.get("ci", 0) + off) for c in cs]
        off += max((c.get("ci", 0) for c in cs), default=-1) + 1
    texts = [t for s in specs for t in s.get("texts", [])]
    if texts:
        out["texts"] = texts
    for s in specs[1:]:
        if s.get("grid") and not out.get("grid"):
            out["grid"] = s["grid"]
        for key in ("xlabel", "ylabel", "zlabel", "title"):
            if not out.get(key) and s.get(key):
                out[key] = s[key]
    for key in ("xlog", "ylog"):
        out[key] = any(s.get(key) for s in specs)
    for key, axis in (("xrange", "x"), ("yrange", "y")):
        if any(s.get(key) for s in specs):
            spans = [s[key] if s.get(key) else _extent(s, axis) for s in specs]
            spans = [r for r in spans if r]
            out[key] = [min(r[0] for r in spans), max(r[1] for r in spans)]
    return _apply_common(ctx, out, opts)


def _extent(spec, axis):
    vals = [v for c in spec.get("curves", []) for v in c.get(axis, []) if v is not None]
    vals += [t[axis] for t in spec.get("texts", [])]
    return [min(vals), max(vals)] if vals else None


@builtin("display", package="plots", sig="display(p1, p2, ...)", doc="Combine plots.",
         options=dict(PLOT3D_OPTIONS, insequence=None))
def m_display(ctx, *plots, insequence=None, **opts):
    from ..evaluator import MCall
    items = [p for x in plots for p in _plot_items(x)]
    if len(items) == 1 and isinstance(items[0], MCall) and str(items[0].func) in ("Array", "Matrix"):
        return PlotValue(_array_spec(ctx, items[0], opts))
    if not items or not all(isinstance(p, PlotValue) for p in items):
        bad = next((p for p in items if not isinstance(p, PlotValue)), None)
        raise MapleError("expecting plot structures" + (f" but received {lprint(bad)}" if bad is not None else ""))
    specs = [p.spec for p in items]
    if is_true(insequence):
        frames = [_apply_common(ctx, dict(s), opts) for s in specs]
        out = dict(frames[0])
        out["frames"] = frames
        return PlotValue(out)
    return PlotValue(merge_specs(ctx, specs, opts))


# ---------------------------------------------------------------- odeplot
def _numeric_solution(sol):
    ns = getattr(sol, "numeric_solution", None)
    if ns is None and isinstance(sol, MList):   # output = listprocedure
        ns = next((getattr(e.rhs, "numeric_solution", None) for e in sol.items
                   if isinstance(e, MEquation) and getattr(e.rhs, "numeric_solution", None) is not None), None)
    if ns is None:
        raise MapleError("the first argument must be the result of dsolve(..., numeric)")
    return ns


def _states(ctx, ns, ts):
    """Solution states at the sorted times ts (None past a singularity), integrating outwards
    from the initial point."""
    from .ode import rk45
    out = {}
    for side, seq in (("right", [t for t in ts if t >= ns.t0]), ("left", [t for t in reversed(ts) if t < ns.t0])):
        y, tprev = list(ns.y0), ns.t0
        for tv in seq:
            try:
                y = rk45(ns.F, tprev, y, tv)
            except (MapleError, OverflowError, ZeroDivisionError):
                ctx.warn(f"cannot evaluate the solution further {side} of {lprint(sp.Float(tprev, ctx.digits))}, "
                         "probably a singularity")
                break
            tprev = tv
            out[tv] = y
    return [out.get(t) for t in ts]


def _ode_label(e, t):
    """Maple's odeplot axis label: y(t) -> y, diff(y(t), t) -> y'."""
    reps = {}
    for d in e.atoms(sp.Derivative):
        if isinstance(d.expr, AppliedUndef):
            reps[d] = sp.Symbol(type(d.expr).__name__ + "'" * sum(int(c) for _, c in d.variable_count))
    e = e.xreplace(reps)
    e = e.xreplace({f: sp.Symbol(type(f).__name__) for f in e.atoms(AppliedUndef) if f.args == (t,)})
    return lprint(e).replace("`", "")


@builtin("odeplot", package="plots", sig="odeplot(sol, [t, x(t)], a..b)", doc="Plot a numeric dsolve solution.",
         options=dict(PLOT_OPTIONS, frames=None))
def m_odeplot(ctx, sol, *args, frames=None, **opts):
    ns = _numeric_solution(sol)
    what, a, b = None, -10.0, 10.0
    for r in args:
        if isinstance(r, MList):
            what = r
        elif isinstance(r, MRange) or isinstance(r, MEquation) and isinstance(r.rhs, MRange):
            a, b = _range(ctx, r.rhs if isinstance(r, MEquation) else r)
        else:
            raise MapleError(f"unexpected option: {lprint(r)}")
    labels = ns.labels()
    if what is None:
        groups = [[ns.t, labels[0]]]
    elif what.items and all(isinstance(p, MList) for p in what.items):
        groups = [list(p.items) for p in what.items]
    else:
        groups = [list(what.items)]
    if any(len(g) not in (2, 3) for g in groups):
        raise MapleError("the plot variables must be given as [x, y] or [x, y, z]")
    n = int(_num(ctx, opts["numpoints"])) if opts.get("numpoints") is not None else 200
    ts = [a + (b - a) * i / (n - 1) for i in range(n)]
    states = _states(ctx, ns, ts)
    dummies = [sp.Dummy() for _ in labels]
    swap = dict(zip(labels, dummies))

    def series(e):
        e = e.xreplace(swap) if isinstance(e, sp.Basic) else e
        if not isinstance(e, sp.Basic):
            raise MapleError(f"invalid plot variable {lprint(e)}")
        fn = sp.lambdify([ns.t, *dummies], e, modules=["math", "mpmath"])
        vals = []
        for tv, ys in zip(ts, states):
            if ys is None:
                vals.append(None)
                continue
            try:
                vals.append(to_float(fn(tv, *ys)))
            except (TypeError, ValueError, ZeroDivisionError, OverflowError):
                vals.append(None)
        return vals
    spec = empty_spec("3d" if any(len(g) == 3 for g in groups) else "2d")
    for i, g in enumerate(groups):
        cols = [series(e) for e in g]
        spec["curves"].append(_curve(ctx, cols[0], cols[1], i, opts, zs=cols[2] if len(cols) == 3 else None))
        spec["curves"][-1]["label"] = ", ".join(lprint(e) for e in g[1:])
    for k, key in enumerate(("xlabel", "ylabel", "zlabel")[:len(groups[0])]):
        spec[key] = ", ".join(dict.fromkeys(_ode_label(g[k], ns.t) for g in groups if k < len(g)))
    spec = _apply_common(ctx, spec, opts)
    if frames is not None:   # the curves grow with t
        m = int(_num(ctx, frames))
        cuts = [max(1, round(n * (k + 1) / m)) for k in range(m)]
        spec["frames"] = [dict(spec, curves=[dict(c, **{ax: c[ax][:cut] for ax in ("x", "y", "z") if ax in c})
                                             for c in spec["curves"]]) for cut in cuts]
    return PlotValue(spec)


# ---------------------------------------------------------------- animate
@builtin("animate", package="plots", sig="animate(plot, [f(x, t), x = a..b], t = c..d, frames = n)",
         doc="Animation: one frame per value of the parameter.",
         options=dict(PLOT3D_OPTIONS, frames=None, trace=None, paramdisplay=None))
def m_animate(ctx, *args, frames=None, trace=None, paramdisplay=None, background=None, **opts):
    if len(args) >= 3 and isinstance(args[0], Procedure) and isinstance(args[1], MList):
        fn, fargs, prange = args[0], list(args[1].items), args[2]
        default_frames = 25
    elif len(args) >= 3:   # old calling sequence animate(f(x, t), x = a..b, t = c..d)
        fn, fargs, prange = ctx.lookup("plot"), [args[0], args[1]], args[2]
        default_frames = 16
        if paramdisplay is None:
            paramdisplay = sp.false
    else:
        raise MapleError("invalid input: animate expects a plot command, its arguments and a parameter range")
    if not (isinstance(prange, MEquation) and isinstance(prange.rhs, MRange)):
        raise MapleError(f"the animation parameter must be given as name = range, received {lprint(prange)}")
    t, (a, b) = prange.lhs, _range(ctx, prange.rhs)
    n = int(_num(ctx, frames)) if frames is not None else default_frames
    show = paramdisplay is None or is_true(paramdisplay)
    specs = []
    for k in range(n):
        v = sp.Float(a + (b - a) * k / (n - 1) if n > 1 else a, ctx.digits)
        p = ctx.apply(fn, [deep_map(lambda e: e.subs(t, v) if isinstance(e, sp.Basic) else e, x) for x in fargs])
        if not isinstance(p, PlotValue):
            raise MapleError(f"the plot command returned {lprint(p)}, not a plot")
        spec = dict(p.spec)
        if show:
            spec["title"] = lprint(MEquation(t, v))
        specs.append(spec)
    if trace is not None:   # keep `trace` evenly spaced earlier frames on screen
        m = int(_num(ctx, trace))
        keep = {round(j * (n - 1) / max(1, m - 1)) for j in range(m)} if m > 0 else set()
        specs = [dict(s, curves=[c for j in sorted(keep) if j < k for c in specs[j]["curves"]] + s["curves"])
                 for k, s in enumerate(specs)]
    if isinstance(background, PlotValue):
        specs = [merge_specs(ctx, [background.spec, s], {}) for s in specs]
    frames_ = [_apply_common(ctx, s, opts) for s in specs]
    out = dict(frames_[0])
    out["frames"] = frames_
    return PlotValue(out)


# ---------------------------------------------------------------- 3-D
def _ranges3(ctx, rest, k):
    """k ranges name = a..b (or a..b for procedures) from rest."""
    out = []
    for r in rest:
        if isinstance(r, MEquation) and isinstance(r.rhs, MRange):
            out.append((r.lhs, *_range(ctx, r.rhs)))
        elif isinstance(r, MRange):
            out.append((None, *_range(ctx, r)))
        else:
            raise MapleError(f"unexpected option: {lprint(r)}")
    if len(out) != k:
        raise MapleError(f"expecting {k} plotting ranges")
    return out


def _grid_opt(ctx, opts, default):
    g = opts.get("grid")
    if isinstance(g, MList) and len(g.items) == 2:
        return [max(2, int(_num(ctx, v))) for v in g.items]
    return default


@builtin("plot3d", sig="plot3d(f, x = a..b, y = c..d, options)", doc="3-D surface plot.",
         options=PLOT3D_OPTIONS)
def m_plot3d(ctx, f, *rest, **opts):
    if isinstance(f, (MList, MSet)):
        raise MapleError("parametric and multiple surfaces are not implemented in SymFlex")
    (xv, xa, xb), (yv, ya, yb) = _ranges3(ctx, rest, 2)
    variables = [xv, yv] if xv is not None else [None, None]
    if isinstance(f, sp.Basic):
        names = free_names(ctx, f, [v for v in variables if v is not None])
        if names:
            raise MapleError(f"expecting only range variables {lprint(MList([xv, yv]))} in expression "
                             f"{lprint(f)} to be plotted but found name {', '.join(names)}")
    g = evaluator(ctx, f, variables)
    nx, ny = _grid_opt(ctx, opts, [49, 49])
    xs = [xa + (xb - xa) * i / (nx - 1) for i in range(nx)]
    ys = [ya + (yb - ya) * j / (ny - 1) for j in range(ny)]
    spec = empty_spec("3d")
    spec["grid"] = {"x": xs, "y": ys, "z": [[g(x, y) for x in xs] for y in ys]}
    if xv is not None:
        spec["xlabel"], spec["ylabel"] = _text(xv), _text(yv)
    spec["xrange"], spec["yrange"] = [xa, xb], [ya, yb]
    return PlotValue(_apply_common(ctx, spec, opts))


@builtin("spacecurve", package="plots", sig="spacecurve([x(t), y(t), z(t)], t = a..b)", doc="3-D curve.",
         options=PLOT3D_OPTIONS)
def m_spacecurve(ctx, f, *rest, **opts):
    items = list(f.items) if isinstance(f, MList) else []
    if len(items) == 4 and isinstance(items[3], MEquation):
        items, rest = items[:3], (items[3], *rest)
    if len(items) != 3:
        raise MapleError(f"expecting a list [x(t), y(t), z(t)], received {lprint(f)}")
    ((t, a, b),) = _ranges3(ctx, rest, 1)
    n = int(_num(ctx, opts["numpoints"])) if opts.get("numpoints") is not None else 200
    gs = [evaluator(ctx, e, [t]) for e in items]
    ts = [a + (b - a) * i / (n - 1) for i in range(n)]
    cols = [[g(v) for v in ts] for g in gs]
    spec = empty_spec("3d")
    spec["curves"].append(_curve(ctx, cols[0], cols[1], 0, opts, zs=cols[2]))
    return PlotValue(_apply_common(ctx, spec, opts))


# ---------------------------------------------------------------- implicitplot / textplot
@builtin("implicitplot", package="plots", sig="implicitplot(f(x, y) = 0, x = a..b, y = c..d)",
         doc="Plot the curve where an equation holds.", options=PLOT3D_OPTIONS)
def m_implicitplot(ctx, f, *rest, **opts):
    (xv, xa, xb), (yv, ya, yb) = _ranges3(ctx, rest, 2)
    items = list(f.items) if isinstance(f, (MList, MSet)) else [f]
    variables = [xv, yv] if xv is not None else [None, None]
    nx, ny = _grid_opt(ctx, opts, [60, 60])
    spec = empty_spec()
    for i, eq in enumerate(items):
        e = ctx.binop("-", eq.lhs, eq.rhs) if isinstance(eq, MEquation) else eq
        if isinstance(e, sp.Basic) and (names := free_names(ctx, e, [v for v in variables if v is not None])):
            raise MapleError(f"expecting only range variables {lprint(MList([xv, yv]))} in the equation "
                             f"but found name {', '.join(names)}")
        g = evaluator(ctx, e, variables)
        for k, line in enumerate(implicit_curves(g, xa, xb, ya, yb, nx, ny)):
            spec["curves"].append(_curve(ctx, [p[0] for p in line], [p[1] for p in line], i, opts,
                                         legend=None if k == 0 else ""))
            if k == 0:
                spec["curves"][-1]["label"] = lprint(eq)
    if xv is not None:
        spec["xlabel"], spec["ylabel"] = _text(xv), _text(yv)
    return PlotValue(_apply_common(ctx, spec, opts))


@builtin("textplot", package="plots", sig='textplot([x, y, "text"])', doc="Place text in a plot.",
         options=dict(PLOT_OPTIONS, align=None))
def m_textplot(ctx, data, *rest, align=None, **opts):
    items = data.items if isinstance(data, MList) else []
    entries = list(items) if items and all(isinstance(e, MList) for e in items) else [data]
    texts = []
    for e in entries:
        if not (isinstance(e, MList) and len(e.items) in (3, 4)):
            raise MapleError(f'expecting [x, y, "text"], received {lprint(e)}')
        if len(e.items) == 4:
            raise MapleError("textplot3d data is not implemented in SymFlex")
        texts.append({"x": _num(ctx, e.items[0]), "y": _num(ctx, e.items[1]), "text": _text(e.items[2]),
                      "color": _color(opts.get("color") or opts.get("colour"))})
    spec = empty_spec()
    spec["texts"] = texts
    return PlotValue(_apply_common(ctx, spec, opts))
