"""The semantic comparator used by tests/run_maple_corpus.py."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maple_compare as mc  # noqa: E402


def ok(g, o):
    d = mc.compare_math(g, o)
    assert d is None, d


def fails(g, o, subtype=None):
    d = mc.compare_math(g, o)
    assert d is not None, f"{g!r} unexpectedly matched {o!r}"
    if subtype:
        assert d.subtype == subtype, d


def test_sets_are_unordered():
    ok("sol := {x = 3/2, y = 1/2}", "sol := {y = 1/2, x = 3/2}")
    fails("{x = 3/2, y = 1/2}", "{x = 3/2, y = 1/3}", "value")
    fails("{x = 1}", "{x = 1, y = 2}", "structure")


def test_assignment_and_equations():
    ok("a := b+1 = c", "a := 1+b = c")
    fails("a := 1", "b := 1")
    fails("a = b", "b = a", "value")
    ok("x > 1", "1 < x")


def test_floats():
    ok("W := 392.40", "W := 392.4")
    ok(".6974633199", "0.69746331990001")
    fails("1.5", "1.6", "value")
    ok("[t = 1., z(t) = .367879356307219]", "[t = 1.0, z(t) = .3678793563]")


def test_float_vs_exact():
    fails("1.570796327", "1/2*Pi", "float-vs-exact")
    fails("x := 1/10*cos(t)", "x := .1*cos(t)", "float-vs-exact")
    fails("{On = 0., Ot = 15.27777778}", "{On = 0, Ot = 15.27777778}", "float-vs-exact")


def test_symbolic_equivalence():
    ok("1/4*t^3*(t+27)", "1/4*t^4+27/4*t^3")
    ok("sin(t)^2+cos(t)^2", "1")
    ok("s30 := (5-4*cos(1/6*Pi))^(1/2)", "s30 := sqrt(5-2*sqrt(3))")
    fails("sin(t)", "cos(t)", "value")
    ok("-300*s(t)-10*D(s)(t)", "-300*s(t)-10*diff(s(t),t)")
    ok("diff(g(x,y),x,y $ 2)", "D[1,2,2](g)(x,y)")
    ok("D(y)(0) = 1", "D(y)(0) = 1")
    ok("t~^2+1", "t^2+1")
    ok("x(t) = c__1*exp(t)+c__2*exp(-2*t)", "x(t) = _C2*exp(t)+_C1*exp(-2*t)")
    fails("x(t) = c__1*exp(t)", "x(t) = _C1*exp(-t)", "value")


def test_sequences():
    fails("2^(1/2), -2^(1/2)", "-2^(1/2), 2^(1/2)", "order")
    ok("{x = 1}, {x = 2}", "{x = 2}, {x = 1}")
    fails("1, 2", "1, 2, 3", "structure")


VG = "Vector[column](3,{1 = -3, 3 = 1},datatype = anything,storage = rectangular,order = Fortran_order,shape = [])"


def test_vector_and_matrix():
    ok(VG, "Vector[column](3,{3 = 1, 1 = -3},datatype = anything,storage = rectangular,order = Fortran_order,shape = [])")
    ok(VG, "Vector[column](3,{1 = -3, 2 = 0, 3 = 1},datatype = anything)")
    ok("v := " + VG, "v := <-3, 0, 1>")
    fails(VG, VG.replace("column", "row"), "structure")
    fails(VG, VG.replace("3 = 1", "2 = 1"), "value")
    ok("Vector[column](2,{1 = -.213368589463414e-8, 2 = -13.5479152995046},datatype = float[8])",
       "Vector[column](2,{1 = -.7232301868e-8, 2 = -13.5479153},datatype = anything)")
    M = "Matrix(2,2,{(1, 1) = 1, (2, 1) = x},datatype = anything,storage = rectangular,order = Fortran_order,shape = [])"
    ok(M, "Matrix(2,2,{(2, 1) = x, (1, 1) = 1, (2, 2) = 0})")
    fails(M, M.replace("(2, 1)", "(1, 2)"), "value")


def test_piecewise():
    ok("PIECEWISE([t, t < 1],[2, otherwise])", "piecewise(t < 1, t, 2)")
    ok("a := PIECEWISE([-9.81+25.0/(-.1*t+2), t < 10.],[-9.81, otherwise])",
       "a := PIECEWISE([25./(-.1*t+2)-9.81, t < 10.0],[-9.81, otherwise])")
    ok("PIECEWISE([t, t < 1],[2, 1 <= t])", "PIECEWISE([t, t < 1],[2, otherwise])")
    fails("PIECEWISE([t, t < 1],[2, otherwise])", "PIECEWISE([t, t < 2],[2, otherwise])", "value")


def test_procedures():
    ok("f := t -> t^2", "f := t -> t*t")
    fails("f := t -> t^2", "f := t -> t^3", "value")
    ok("q := proc (t) local _res; option `Copyright`; `...` end proc", "q := proc (t) 1 end proc")


def test_print_text():
    assert mc.compare_print("x = 1.50 m\nnext", "x = 1.5   m next") is None
    assert mc.compare_print("x = 1.50", "x = 1.51") is not None
    assert mc.compare_print("hello", "world") is not None


def _gplot(fs, xlog=False, ylog=False, n=120):
    xs = [0.05 + 3 * i / (n - 1) for i in range(n)]
    return {"type": "2d", "options": [], "xlog": xlog, "ylog": ylog,
            "objects": [{"kind": "curve", "points": [[x, f(x)] for x in xs]} for f in fs]}


def _ours(fs, n=200, xlog=False, ylog=False):
    xs = [3.05 * i / (n - 1) for i in range(n)]
    return {"type": "2d", "xlog": xlog, "ylog": ylog,
            "curves": [{"x": xs, "y": [f(x) for x in xs]} for f in fs]}


def test_plots():
    assert mc.compare_plot(_gplot([math.sin, math.cos]), _ours([math.sin, math.cos])) is None
    assert mc.compare_plot(_gplot([math.sin]), _ours([math.cos])).subtype == "plot-data"
    assert mc.compare_plot(_gplot([math.sin]), _ours([lambda x: 1.05 * math.sin(x)])).subtype == "plot-data"
    assert mc.compare_plot(_gplot([math.sin]), _ours([math.sin, math.cos])).subtype == "plot-curves"
    assert mc.compare_plot(_gplot([math.exp], ylog=True), _ours([math.exp])).subtype == "plot-axes"
    assert mc.compare_plot(_gplot([math.exp], ylog=True), _ours([math.exp], ylog=True)) is None
    circle = {"type": "2d", "options": [], "objects": [{"kind": "curve", "points": [
        [math.cos(2 * math.pi * i / 90), math.sin(2 * math.pi * i / 90)] for i in range(91)]}]}
    th = [2 * math.pi * i / 299 for i in range(300)]
    assert mc.compare_plot(circle, {"type": "2d", "curves": [
        {"x": [math.cos(t) for t in th], "y": [math.sin(t) for t in th]}]}) is None
    assert mc.compare_plot(circle, {"type": "2d", "curves": [
        {"x": [1.1 * math.cos(t) for t in th], "y": [math.sin(t) for t in th]}]}) is not None


@pytest.mark.parametrize("golden, ours, verdict", [
    ([{"kind": "math", "text": "x := 3"}], [{"kind": "warning", "text": "Warning, w"}, {"kind": "math", "text": "x := 3"}], "pass"),
    ([{"kind": "error", "text": "Error, (in solve) a"}], [{"kind": "error", "text": "Error, b"}], "pass"),
    ([{"kind": "error", "text": "Error, x"}], [{"kind": "math", "text": "1"}], "fail"),
    ([{"kind": "math", "text": "1"}, {"kind": "math", "text": "2"}], [{"kind": "print", "text": "1"}, {"kind": "print", "text": "2"}], "pass"),
    ([{"kind": "math", "text": "1"}], [], "fail"),
])
def test_statement(golden, ours, verdict):
    assert mc.compare_statement(golden, ours)["verdict"] == verdict


def test_piecewise_values():
    ok("PIECEWISE([-9.81+25.0/(-.1*t+2), t < 10.],[-9.81, 10. <= t])",
       "PIECEWISE([25./(-.1*t+2)-9.81, t < 10.0],[-9.81, otherwise])")
    ok("5-PIECEWISE([t, t < 10],[10, otherwise])", "PIECEWISE([5-t, t < 10],[-5, otherwise])")
    fails("PIECEWISE([t, t < 10],[10, otherwise])", "PIECEWISE([t, t < 10],[11, otherwise])", "value")
    fails("x^2", "PIECEWISE([x^2, x <> I],[0, otherwise])", "structure")
