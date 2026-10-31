"""int, diff, D, limit, series and inert forms; expected texts are real cmaple (Maple 2024) output."""
import re
import sys
from pathlib import Path

import pytest
from helpers import run1

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maple_compare as mc  # noqa: E402


def same(code, maple):
    """Each output of code equals cmaple's text semantically (warnings included)."""
    ours = run1(code)
    assert len(ours) == len(maple), ours
    for o, g in zip(ours, maple):
        d = mc.compare_print(g, o) if g.startswith("Warning") else mc.compare_math(g, o)
        assert d is None, f"{d}\n ours:  {o}\n maple: {g}"


WARN = "Warning, unable to determine if {} is between {} and {}; try to use assumptions or use the AllSolutions option"


@pytest.mark.parametrize("code, maple", [
    # generic answer, not SymPy's special cases (mu_k = I/2, a = -1)
    ("int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta);",
     ["-gr*exp(-2*mu_k*theta)*(2*cos(theta)*mu_k^2-3*mu_k*sin(theta)-cos(theta))/(4*mu_k^2+1)"]),
    ("int(x^a, x);", ["x^(a+1)/(a+1)"]),
    ("int(sin(a*x), x = 0 .. t);", ["-(-1+cos(a*t))/a"]),
    ("int(1/(x^2+a^2), x = 0 .. t);", ["arctan(t/a)/a"]),
    # floats: integrated exactly, then evaluated
    ("int(0.5*x^2+1.2*x, x = 0 .. t);", [".1666666667*t^3+.6000000000*t^2"]),
    ("int(exp(-0.3*x)*sin(2*x), x = 0 .. t);",
     [".4889975550-.4889975550*exp(-.3000000000*t)*cos(2.*t)-.7334963325e-1*exp(-.3000000000*t)*sin(2.*t)"]),
    ("int(25.0/(2-0.1*t), t = 0 .. 5);", ["71.92051811"]),
    ("int(exp(-x^2)*cos(x), x = 0 .. 1.5);", [".6954434862"]),
    # a pole that may lie between the limits: unevaluated (a warning only for exact input)
    ("int(1/(x^2-3*x+2), x = 0 .. t);", [WARN.format(1, 0, "t"), WARN.format(2, 0, "t"),
                                         "int(1/(x^2-3*x+2),x = 0 .. t)"]),
    ("int(1/(x-a), x = 0 .. t);", [WARN.format("a", 0, "t"), "int(1/(x-a),x = 0 .. t)"]),
    ("int(1.5/(x+1), x = 0 .. t);", ["int(1.5/(x+1),x = 0 .. t)"]),
    ("int(1/(x^2+1), x = 0 .. t);", ["arctan(t)"]),
    ("int(1/(x-1), x = 0 .. 3);", ["undefined"]),
    ("int(1/(x-1)^2, x = 0 .. 3);", ["infinity"]),
    # assumptions put the poles outside the range
    ("assume(0 < t, t < 10): int(1/(s^2-30*s+200), s = 0 .. t);",
     ["-1/10*ln(2)-1/10*ln(10-t)+1/10*ln(20-t)"]),
    ("assume(0 < t, t < 5): int(82800000.*784000/(1184000-3500*t2)/(30000*t2^2+1000000.), t2 = 0 .. t);",
     ["29.52769362-5.400864744*ln(2368.-7.*t)+2.700432372*ln(3.*t^2+100.)+316.4518119*arctan(.1732050808*t)"]),
    # piecewise integrands: Maple-shaped piecewise antiderivatives
    ("int(piecewise(x<1, x, x<3, 2, 5-x), x);",
     ["PIECEWISE([1/2*x^2, x <= 1],[2*x-3/2, x <= 3],[5*x-1/2*x^2-6, 3 < x])"]),
    ("int(piecewise(x<1, x, x<3, 2, 5-x), x = -2 .. t);",
     ["-2+PIECEWISE([1/2*t^2, t <= 1],[2*t-3/2, t <= 3],[5*t-1/2*t^2-6, 3 < t])"]),
    ("int(piecewise(x<1, x, x<3, 2, 5-x), x = 0 .. 5);", ["13/2"]),
    ("int(piecewise(0<x and x<1, x, 0), x = 0 .. t);", ["PIECEWISE([0, t <= 0],[1/2*t^2, t <= 1],[1/2, 1 < t])"]),
    ("int(piecewise(x<1, 1/(x-2), 0), x = 0 .. t);", ["-ln(2)+PIECEWISE([ln(-t+2), t <= 1],[0, 1 < t])"]),
    ("int(piecewise(t<10., -9.81+25.0/(-.1*t+2), -9.81), t = 0 .. t);",
     ["748.9330684-9.810000000*t-PIECEWISE([250.*ln(-t+20.), t <= 10.],[575.6462732, 10. < t])"]),
    ("int(Heaviside(t-1), t);", ["t*Heaviside(t-1)-Heaviside(t-1)"]),
    ("int(Heaviside(t-1)*t, t = 0 .. 3);", ["4"]),
    # nested
    ("int(int(x*y, x = 0 .. 1), y = 0 .. 2);", ["1"]),
    ("int(int(t2, t2 = 0 .. t2), t2 = 0 .. t);", ["1/6*t^3"]),
])
def test_int(code, maple):
    same(code, maple)


def test_unevaluated_int_simplify_normalises_like_maple():
    out = run1("alpha := 82800000.*784000/(1184000-3500*t)/(30000*t^2+1000000.):"
               "omega := simplify(int(subs(t = t2, alpha), t2 = 0 .. t));"
               "theta := simplify(int(subs(t = t2, omega), t2 = 0 .. t));")
    assert out[0].startswith("omega := ") and out[0].count("int(") == 1
    const, integrand = out[0].split("*int(")
    assert const.endswith(".") and not re.search(r"\d\.", integrand), out[0]
    assert out[1].count("int(") == 2 and "t2 = 0 .. t2),t2 = 0 .. t)" in out[1], out[1]


@pytest.mark.parametrize("code, maple", [
    ("evalf(Int(exp(-x^3)*sin(x), x = 0 .. 1));", [".3261940545"]),
    ("value(Int(Int(x*y, x = 0 .. 1), y = 0 .. 2));", ["1"]),
    ("Diff(sin(x), x);", ["Diff(sin(x),x)"]),
    ("Diff(x^3, x) = diff(x^3, x);", ["Diff(x^3,x) = 3*x^2"]),
    ("value(Diff(sin(x), x$2));", ["-sin(x)"]),
    ("Limit(x^2, x = 2) = limit(x^2, x = 2);", ["Limit(x^2,x = 2) = 4"]),
    ("evalf(Limit(sin(x)/x, x = 0));", ["1."]),
])
def test_inert(code, maple):
    same(code, maple)


@pytest.mark.parametrize("code, maple", [
    ("D(sin);", ["cos"]),
    ("D(exp);", ["exp"]),
    ("diff(abs(x), x);", ["signum(x)"]),   # Maple prints abs(1,x), which is signum(x) for real x
    ("diff(Heaviside(t-1), t);", ["Dirac(t-1)"]),
    ("diff(piecewise(t < 2, t^2, 4), t);", ["PIECEWISE([2*t, t < 2],[0, otherwise])"]),
])
def test_diff(code, maple):
    same(code, maple)


@pytest.mark.parametrize("code, maple", [
    ("limit(1/x, x = 0);", ["undefined"]),
    ("limit(abs(x)/x, x = 0);", ["undefined"]),
    ("limit(1/x, x = 0, right);", ["infinity"]),
    ("limit(sin(x), x = infinity);", ["-1 .. 1"]),
    ("limit(v0*exp(-k*t), t = infinity);", ["limit(v0*exp(-k*t),t = infinity)"]),
])
def test_limit(code, maple):
    same(code, maple)


@pytest.mark.parametrize("code, maple", [
    ("series(sin(x), x = 0, 8);", ["series(1*x-1/6*x^3+1/120*x^5-1/5040*x^7+O(x^9),x,9)"]),
    ("series(cos(x), x, 5);", ["series(1-1/2*x^2+1/24*x^4+O(x^6),x,6)"]),
    ("series(1/(1-x^2), x, 4);", ["series(1+1*x^2+O(x^4),x,4)"]),
    ("series(x^3+x^5, x, 4);", ["series(1*x^3+O(x^5),x,5)"]),
    ("series(exp(x), x = 1, 3);", ["series(exp(1)+exp(1)*(x-1)+1/2*exp(1)*(x-1)^2+O((x-1)^3),x=1,3)"]),
    ("series(cos(x), x = Pi, 4);", ["series(-1+1/2*(x-Pi)^2+O((x-Pi)^4),x=-(-Pi),4)"]),
])
def test_series(code, maple):
    same(code, maple)


@pytest.mark.parametrize("code, maple", [
    ("sum(a*r^k, k = 0 .. n-1);", ["(r^n/(r-1)-1/(r-1))*a"]),
    ("product(1+1/k, k = 1 .. n);", ["GAMMA(n+2)/GAMMA(n+1)"]),
])
def test_sum_product(code, maple):
    same(code, maple)
