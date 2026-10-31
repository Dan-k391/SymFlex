"""solve, fsolve, maximize/minimize and the simplifiers; expected texts are real cmaple
(Maple 2024) output, compared semantically (order of roots and solutions included)."""
import sys
from pathlib import Path

import pytest
from helpers import run1

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maple_compare as mc  # noqa: E402


def same(code, maple):
    ours = run1(code)
    assert len(ours) == len(maple), ours
    for o, g in zip(ours, maple):
        d = mc.compare_math(g, o)
        assert d is None, f"{d}\n ours:  {o}\n maple: {g}"


@pytest.mark.parametrize("code, maple", [
    # quadratic formula on the polynomial as written: `+` root first
    ("solve(x^2=2);", "2^(1/2), -2^(1/2)"),
    ("solve(2=x^2);", "-2^(1/2), 2^(1/2)"),
    ("solve(x^2-3*x+2);", "2, 1"),
    ("solve(-x^2+3*x-2);", "1, 2"),
    ("solve(1/x=x-1);", "-1/2*5^(1/2)+1/2, 1/2*5^(1/2)+1/2"),
    ("solve(-2.0*x^2+3.0);", "-1.224744871, 1.224744871"),
    # with parameters the leading coefficient is made positive first
    ("solve(-x^2+3*x+z,x);", "3/2+1/2*(9+4*z)^(1/2), 3/2-1/2*(9+4*z)^(1/2)"),
    ("solve(-a*x^2+b,x);", "1/a*(a*b)^(1/2), -1/a*(a*b)^(1/2)"),
    ("solve(-3*x^4+(2-4*z^2)*x^2+1, x);",
     "1/3*(3-6*z^2+6*(z^4-z^2+1)^(1/2))^(1/2), -1/3*(3-6*z^2+6*(z^4-z^2+1)^(1/2))^(1/2), "
     "1/3*(3-6*z^2-6*(z^4-z^2+1)^(1/2))^(1/2), -1/3*(3-6*z^2-6*(z^4-z^2+1)^(1/2))^(1/2)"),
    ("solve(x^4+3.0*x^2+1);", ".6180339888*I, -.6180339888*I, 1.618033989*I, -1.618033989*I"),
    # float polynomials of degree >= 3: by argument, then modulus
    ("solve(x^3-2.0*x+0.5);", ".2586520225, 1.267035098, -1.525687121"),
    ("solve(x^4-3.0*x^2+0.5*x+0.1);", ".2898010504, 1.629574791, -.1175182406, -1.801857601"),
    ("solve(0.3*x^5-x+0.1);", ".1000030004, 1.324949735, -.2491515986e-1+1.352348992*I, "
                              "-1.375122416, -.2491515986e-1-1.352348992*I"),
    ("solve(x^2*(x-2.0)*(x+1.5));", "2., -1.500000000, 0., 0."),
    ("solve(x*(x^2-2.0));", "0., 1.414213562, -1.414213562"),
    ("solve(x^3=8);", "2, -1-I*3^(1/2), -1+I*3^(1/2)"),
    ("solve(x^2-2*x+1,{x});", "{x = 1}, {x = 1}"),
    ("solve(x^2=2,[x]);", "[[x = 2^(1/2)], [x = -2^(1/2)]]"),
    ("solve(x^2=0.0);", "0., 0."),
    ("solve({x*2.0=0, y=1});", "{x = 0., y = 1.}"),
])
def test_solve_root_order(code, maple):
    same(code, [maple])


@pytest.mark.parametrize("code, maple", [
    ("solve(sin(x)=0.5);", ".5235987756"),
    ("solve(cos(x)=1/2, x);", "1/3*Pi"),
    ("solve(sin(x)^2=0.3);", ".5796397404, -.5796397404"),
    ("solve(cos(x)^2-0.2*cos(x)=0.1);", "1.124461330, 1.804582632"),
    ("solve(v^2*sin(2*theta)/9.81=10, theta);", ".5000000000*arcsin(98.09999999/v^2)"),
    ("solve(exp(-0.5*t)*cos(3*t)=0, t);", ".5235987756"),
    ("solve(sin(x)=2);", "arcsin(2)"),
    ("solve(cosh(x)=2.0);", "1.316957897"),
    ("solve(abs(x-1)=2);", "-1, 3"),   # Maple: 3, -1
])
def test_solve_principal_values(code, maple):
    same(code, [maple])


@pytest.mark.parametrize("code, maple", [
    ("solve(x^2<4, x);", "RealRange(Open(-2),Open(2))"),
    ("solve(x^2<4, {x});", "{-2 < x, x < 2}"),
    ("solve(x^2>4, x);", "RealRange(-infinity,Open(-2)), RealRange(Open(2),infinity)"),
    ("solve(x^2>=4);", "RealRange(-infinity,-2), RealRange(2,infinity)"),
    ("solve({2*x+1>3});", "{1 < x}"),
    ("solve(x^2+1>0, x);", "x"),
    ("solve(x^2<=0,x);", "0"),
    ("solve({x>1, x<3}, x);", "{1 < x, x < 3}"),
    ("solve([x^2=4, x>0], x);", "{x = 2}"),
    ("solve([x^2=4, x>0], [x]);", "[[x = 2]]"),
    ("solve({x^2=4.0, x>0});", "{x = 2.}"),
    ("solve({x^2+y^2=1, x-y=0, x>0});", "{x = 1/2*2^(1/2), y = 1/2*2^(1/2)}"),
    ("solve({x^2=a, x>0}, x);", "{x = a^(1/2)}"),
])
def test_solve_inequalities(code, maple):
    same(code, [maple])


def test_solve_inequality_without_solutions():
    assert run1("solve(x^2+1<0, x); solve([x^2=4, x>5]);") == []


@pytest.mark.parametrize("code, maple", [
    ("solve([x+y=5, x*y=6], [x,y]);", "[[x = 3, y = 2], [x = 2, y = 3]]"),
    ("solve([x-y=1, x^2+y^2=25], [x,y]);", "[[x = -3, y = -4], [x = 4, y = 3]]"),
    ("solve({x^2-y=0, x+y=2});", "{x = 1, y = 1}, {x = -2, y = 4}"),
    ("solve([x^2=4, y=x+1], [x,y]);", "[[x = 2, y = 3], [x = -2, y = -1]]"),
    ("solve([x+y=1, x^2+y^2=3.0],[x,y]);",
     "[[x = -.6180339887, y = 1.618033989], [x = 1.618033989, y = -.6180339888]]"),
    ("solve([x+y=5, x*y=6.0], [x,y]);", "[[x = 3., y = 2.], [x = 2., y = 3.]]"),
    ("solve([On = 1.55*0^2*.5, 50-Ot = 1.55*.5*alpha, .5*50 = .56*alpha]);",
     "{On = 0., Ot = 15.40178571, alpha = 44.64285714}"),
])
def test_solve_system_order(code, maple):
    same(code, [maple])


@pytest.mark.parametrize("code, maple", [
    ("fsolve(x^2=2);", ["-1.414213562, 1.414213562"]),
    ("fsolve(x^2-4, x=-5..5);", ["-2.000000000, 2.000000000"]),
    ("fsolve(x^2=2, x=1);", ["-1.414213562, 1.414213562"]),
    ("fsolve(x^2+1);", []),
    ("fsolve(x^2-4, x=1..1.5);", []),
    ("fsolve(x^3-x, x, maxsols=2);", ["-1.000000000, 0."]),
    ("fsolve(x^3-1, x, complex);",
     ["-.5000000000-.8660254038*I, -.5000000000+.8660254038*I, 1."]),
    ("fsolve(exp(x)=x, x, complex);", [".3181315052-1.337235701*I"]),
    ("fsolve(sin(x), x=-1..10);", ["0."]),
    ("fsolve(sin(x), x=1..2);", ["fsolve(sin(x),x,1 .. 2)"]),
    ("fsolve({x^2+y^2=4, x*y=1}, {x=0..1, y=1..3});", ["{x = .5176380902, y = 1.931851653}"]),
])
def test_fsolve(code, maple):
    same(code, maple)


def test_fsolve_results_are_decimal():
    # Maple's floats are decimal: the difference of two 10-digit roots has no binary tail
    same("r1 := fsolve(x^2=1.0201, x=0..2): r2 := fsolve(x^2=0.9801, x=0..2): r1 - r2;",
         [".200000000e-1"])


@pytest.mark.parametrize("code, maple", [
    ("maximize(x*(1-x), location);", "1/4, {[{x = 1/2}, 1/4]}"),
    ("minimize(x^2-2*x, x=-1..3, location);", "-1, {[{x = 1}, -1]}"),
    ("maximize(sin(x), x=0..5, location);", "1, {[{x = 1/2*Pi}, 1]}"),
    ("maximize(x^3-x, x=-2..2, location);", "6, {[{x = 2}, 6]}"),
    ("maximize(x^3);", "infinity"),
    ("minimize(x^2+1.5*x);", "-.5625000000"),
    ("maximize(-(x-1)^2+3.0, location);", "3., {[{x = 1.}, 3.]}"),
    ("maximize(piecewise(x<1, x, 2-x), location);", "1, {[{x = 1}, 1]}"),
    ("minimize(abs(x-2), x=0..5, location);", "0, {[{x = 2}, 0]}"),
    ("maximize(sin(x)*exp(-0.1*x), x=0..10, location);",
     ".8589127508, {[{x = 1.471127674}, .8589127508]}"),
    ("maximize(x^2*exp(-x), x=0..10);", "4*exp(-2)"),
    ("maximize(a*x^2, x=0..1);", "max(0,a)"),
    ("minimize(cos(x));", "-1"),
    # piecewise rocket height: no hang, numeric critical point in the second piece
    ("maximize(piecewise(t<10, 5*t^2, 500+100*(t-10)-4.9*(t-10)^2), t=0..40, location);",
     "1010.204082, {[{t = 20.20408163}, 1010.204082]}"),
])
def test_extrema(code, maple):
    same(code, [maple])


@pytest.mark.parametrize("code, maple", [
    ("expand(sin(a+b));", "sin(a)*cos(b)+cos(a)*sin(b)"),
    ("expand(cos(2*x));", "2*cos(x)^2-1"),
    ("expand((x+1)^2/(x+2)^2);", "1/(x+2)^2*x^2+2/(x+2)^2*x+1/(x+2)^2"),
    ("expand((x+1)*(x-1)/(x^2+1));", "1/(x^2+1)*x^2-1/(x^2+1)"),
    ("combine(sin(x)^2);", "1/2-1/2*cos(2*x)"),
    ("combine(cos(x)^3);", "1/4*cos(3*x)+3/4*cos(x)"),
    ("combine(a*exp(x)*exp(2*x)+ln(2)+ln(3));", "ln(6)+a*exp(3*x)"),
    ("combine(ln(a)+ln(b));", "ln(a)+ln(b)"),
    ("combine(ln(a)+ln(b), symbolic);", "ln(a*b)"),
    ("simplify(sqrt(4*x^2), symbolic);", "2*x"),
    ("collect(a*x*y+b*x*y+c*x, [x,y]);", "((a+b)*y+c)*x"),
    ("isolate(a*sin(t)=b, t);", "t = arcsin(b/a)"),
    ("isolate(x^2+3=7, x);", "x = 2"),
])
def test_simplifiers(code, maple):
    same(code, [maple])
