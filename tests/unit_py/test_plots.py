"""plots package: PlotSpec shape and Maple behaviours checked against cmaple (curve counts, labels,
default ranges, discont splitting, warnings)."""
import json
import math

from symflex_maple import Session


def run(code, s=None):
    s = s or Session()
    return s.run(code)


def spec(code, s=None):
    outs = [o for o in run(code, s) if o["kind"] == "plot"]
    assert outs, run(code, s)
    json.dumps(outs[-1]["spec"])   # the worker sends specs as JSON
    return outs[-1]["spec"]


def finite(c, axis="y"):
    return [v for v in c[axis] if v is not None]


def test_default_ranges_and_labels():
    assert spec("plot(sin(x));")["xrange"] == [-2 * math.pi, 2 * math.pi]
    sp_ = spec("plot(x^2);")
    assert sp_["xrange"] == [-10.0, 10.0] and sp_["xlabel"] == "x" and sp_["ylabel"] == ""
    assert spec("plot(x^2, x=0..1, y=0..2);")["ylabel"] == "y"
    assert spec("f := x -> x^3: plot(f, -2..2);")["xlabel"] == ""
    assert spec("plot(0.1*x, x=0.1..1);")["xrange"][0] == 0.1


def test_symbolic_parameter_warns_and_plots_nothing():
    out = run("plot(a*x+b, x=0..1);")
    assert out[0] == {"kind": "warning", "text": "Warning, expecting only range variable x in expression "
                                                 "a*x+b to be plotted but found names [a, b]"}
    assert all(v is None for v in out[1]["spec"]["curves"][0]["y"][1:])
    assert run("plot(x+t);")[0]["text"] == "Error, (in plot) cannot determine plotting variable"


def test_unevaluated_procedure_call_is_sampled():
    c = spec("g := proc(x) if x < 1 then x else 2-x end if end proc: plot('g(x)', x=0..2);")["curves"][0]
    assert max(finite(c)) > 0.99 and min(finite(c)) >= 0


def test_data_plots():
    c = spec("plot([1,2,3], [4,5,7]);")["curves"]
    assert len(c) == 1 and c[0]["x"] == [1, 2, 3] and c[0]["y"] == [4, 5, 7]
    assert spec("plot(<1,2>, <3,4>, style=point);")["curves"][0]["style"] == "point"
    pts = spec("plots:-pointplot([[1,2],[2,3]], connect=true);")["curves"][0]
    assert pts["style"] == "line" and pts["y"] == [2, 3]
    assert spec("plots:-pointplot([1,2], [5,6]);")["curves"][0]["style"] == "point"


def test_parametric_has_no_fixed_x_range():
    s = spec("plot([[cos(t), sin(t), t=0..2*Pi], [2*cos(t), sin(t), t=0..Pi]]);")
    assert len(s["curves"]) == 2 and s["xrange"] is None
    assert max(finite(s["curves"][1], "x")) > 1.99


def test_discont_splits_at_jumps_only():
    assert len(spec("plot(tan(x), x=-Pi..Pi, discont=true);")["curves"]) == 3
    assert len(spec("plot(1/(x-1)^2, x=0..3, discont=true);")["curves"]) == 1      # even pole: no jump
    assert len(spec("plot(piecewise(x<0, 0, x), x=-1..1, discont=true);")["curves"]) == 1
    c = spec("plot(piecewise(x<0, -1, x<1, x^2, 2), x=-2..3, discont=true, legend=\"p\");")["curves"]
    assert [k["style"] for k in c] == ["line"] * 3 + ["point"]
    assert c[3]["x"] == [0.0, 1.0] and c[3]["y"] == [0.0, 2.0]
    assert [k["legend"] for k in c] == ["p", "", "", ""]
    # every piece stops short of the jump but gets close to it
    assert max(finite(c[0], "x")) < 0 and max(finite(c[0], "x")) > -1e-4
    assert len(spec("plot(floor(x), x=0..3, discont=true);")["curves"]) == 4
    assert len(spec("plot(round(x), x=0..2, discont=true);")["curves"]) == 4


def test_smartview_cuts_singular_spikes():
    lo, hi = spec("plot(1/x, x=-1..1);")["yrange"]
    assert -15 < lo < -3 and 3 < hi < 15
    assert spec("plot(x^2, x=-1..1);")["yrange"] is None
    assert spec("plot(1/x, x=-1..1, smartview=false);")["yrange"] is None


def test_adaptive_sampling_resolves_fast_oscillation():
    c = spec("plot(8*cos(10*t), t=0..20);")["curves"][0]
    peaks = [y for y in finite(c) if y < -7.9]
    assert len(peaks) >= 30         # every trough of the 32 periods is sampled near its minimum
    assert len(spec("plot(sin(x), x=0..10, adaptive=false, numpoints=50);")["curves"][0]["x"]) == 50


def test_curve_options():
    s = spec('plot([x, x^2], x=0..1, color=[red, "Blue"], legend=["a", b], thickness=[1, 3], '
             'linestyle=[dash, 4], title="T", labels=["u", "v"], view=[0..2, -1..1], axes=boxed);')
    c = s["curves"]
    assert [k["color"] for k in c] == ["red", "Blue"] and [k["legend"] for k in c] == ["a", "b"]
    assert [k["thickness"] for k in c] == [1, 3] and [k["dash"] for k in c] == ["dash", "dashdot"]
    assert (s["title"], s["xlabel"], s["ylabel"], s["xrange"], s["yrange"], s["axes"]) == \
        ("T", "u", "v", [0.0, 2.0], [-1.0, 1.0], "boxed")
    assert spec("plot(x, x=0..1);")["curves"][0]["color"] == "#78000E"   # Maple's first default colour


def test_log_axes_sample_positive_log_spaced_x():
    s = spec("plots:-loglogplot(x^2, x=1..100);")
    xs = finite(s["curves"][0], "x")
    assert s["xlog"] and s["ylog"] and min(xs) >= 1 and xs[1] / xs[0] > 1.01


def test_filled_adds_a_polygon():
    c = spec("plot(x^2, x=0..1, filled=true);")["curves"]
    assert len(c) == 2 and c[1]["filled"] and c[1]["y"][0] == 0.0


def test_odeplot_labels_ranges_and_listprocedure():
    s = Session()
    run("sol := dsolve({diff(y(t),t,t)+y(t)=0, y(0)=1, D(y)(0)=0}, numeric):", s)
    p = spec("plots:-odeplot(sol, [[t, y(t)], [t, diff(y(t),t)]], 0..10);", s)
    assert (p["xlabel"], p["ylabel"]) == ("t", "y, y'") and len(p["curves"]) == 2
    c = spec("plots:-odeplot(sol, [t, y(t)]);", s)["curves"][0]
    assert c["x"][0] == -10.0 and abs(c["y"][0] - math.cos(-10)) < 1e-6
    run("sol2 := dsolve({diff(x(t),t)=-y(t), diff(y(t),t)=x(t), x(0)=1, y(0)=0}, numeric, output=listprocedure):", s)
    p = spec("plots:-odeplot(sol2, [t, x(t), y(t)], 0..5);", s)
    assert p["type"] == "3d" and p["zlabel"] == "y" and abs(p["curves"][0]["z"][-1] - math.sin(5)) < 1e-6
    assert len(spec("plots:-odeplot(sol, [t, y(t)], 0..1, frames=4);", s)["frames"]) == 4


def test_display_merges_animates_and_arrays():
    s = Session()
    run("p1 := plot(sin(x), x=0..1): p2 := plot(cos(x), x=0..2):", s)
    d = spec("plots:-display(p1, p2, title=\"both\");", s)
    assert len(d["curves"]) == 2 and d["xrange"] == [0.0, 2.0] and d["title"] == "both"
    anim = spec("plots:-display([p1, p2], insequence=true);", s)
    assert len(anim["frames"]) == 2 and len(anim["frames"][1]["curves"]) == 1
    arr = spec("plots:-display(Array([p1, p2]));", s)
    assert (arr["type"], arr["rows"], arr["cols"], len(arr["cells"])) == ("array", 1, 2, 2)
    mixed = spec("plots:-display(plots:-display([p1, p2], insequence=true), plots:-pointplot([[0, 0]]));", s)
    assert [len(f["curves"]) for f in mixed["frames"]] == [2, 2]
    assert "Error" in run("plots:-display(3);", s)[0]["text"]


def test_animate_frames_titles_and_trace():
    a = spec("plots:-animate(plot, [sin(x - t), x=0..2*Pi], t=0..1, frames=5);")
    assert len(a["frames"]) == 5 and a["frames"][0]["title"] == "t = 0." and a["frames"][4]["title"] == "t = 1."
    assert len(spec("plots:-animate(plot, [a*x^2, x=-1..1], a=1..3);")["frames"]) == 25
    tr = spec("plots:-animate(plot, [x + t, x=0..1], t=0..1, frames=5, trace=5);")
    assert [len(f["curves"]) for f in tr["frames"]] == [1, 2, 3, 4, 5]
    old = spec("plots:-animate(sin(x*t), x=0..1, t=1..2);")
    assert len(old["frames"]) == 16 and old["frames"][0]["title"] == ""


def test_plot3d_grid_orientation():
    s = spec("plot3d(x + 10*y, x=0..1, y=0..2, grid=[3, 5]);")
    g = s["grid"]
    assert s["type"] == "3d" and len(g["x"]) == 3 and len(g["y"]) == 5
    assert g["z"][4][1] == g["x"][1] + 10 * g["y"][4]      # z[j][i] is the value at (x[i], y[j])
    assert (s["xlabel"], s["ylabel"]) == ("x", "y")
    c = spec("plots:-spacecurve([cos(t), sin(t), t], t=0..4*Pi);")["curves"][0]
    assert len(c["z"]) == 200


def test_implicitplot_components():
    c = spec("plots:-implicitplot(x^2+y^2=1, x=-2..2, y=-2..2);")["curves"]
    assert len(c) == 1 and c[0]["x"][0] == c[0]["x"][-1]          # one closed loop
    assert all(abs(math.hypot(x, y) - 1) < 1e-6 for x, y in zip(c[0]["x"], c[0]["y"]))
    assert len(spec("plots:-implicitplot(x^2-y^2=1, x=-3..3, y=-3..3);")["curves"]) == 2
    assert len(spec("plots:-implicitplot(x*y=1, x=-3..3, y=-3..3);")["curves"]) == 2   # no segment across the pole
    two = spec("plots:-implicitplot([x^2+y^2=1, y=x], x=-2..2, y=-2..2);")["curves"]
    assert len(two) == 2 and two[0]["color"] != two[1]["color"]


def test_textplot_and_polarplot():
    d = spec('plots:-display(plot(x, x=0..2), plots:-textplot([1, 1, "A"], color=red));')
    assert d["texts"] == [{"x": 1.0, "y": 1.0, "text": "A", "color": "red"}] and len(d["curves"]) == 1
    c = spec("plots:-polarplot(1, theta=0..Pi);")["curves"][0]
    assert all(abs(math.hypot(x, y) - 1) < 1e-9 for x, y in zip(c["x"], c["y"]))
