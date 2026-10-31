"""dsolve (symbolic and numeric) and odetest; expected texts are real cmaple (Maple 2024) output."""
import sys
import time
from pathlib import Path

import pytest
from helpers import run1, texts

from symflex_maple import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maple_compare as mc  # noqa: E402


def same(code, maple):
    """Each output of code equals cmaple's text semantically."""
    ours = run1(code)
    assert len(ours) == len(maple), ours
    for o, g in zip(ours, maple):
        d = mc.compare_math(g, o)
        assert d is None, f"{d}\n ours:  {o}\n maple: {g}"


@pytest.mark.parametrize("code, maple", [
    # floats are converted to rationals and the answer stays exact
    ("dsolve(diff(y(x),x)=0.5*y(x));", "y(x) = c__1*exp(1/2*x)"),
    ("dsolve({diff(y(t),t,t)+0.2*diff(y(t),t)+4*y(t)=sin(t), y(0)=0.1, D(y)(0)=0});",
     "y(t) = -86/10735*exp(-1/10*t)*399^(1/2)*sin(1/10*399^(1/2)*t)+69/565*exp(-1/10*t)*"
     "cos(1/10*399^(1/2)*t)-5/226*cos(t)+75/226*sin(t)"),
    # resonance, polynomial*exp forcing, higher order with complex roots
    ("dsolve({diff(y(t),t,t)+4*y(t)=sin(2*t), y(0)=0, D(y)(0)=0});",
     "y(t) = 1/8*sin(2*t)-1/4*cos(2*t)*t"),
    ("dsolve(diff(y(t),t,t)+4*y(t)=t*exp(t));",
     "y(t) = sin(2*t)*c__2+cos(2*t)*c__1+1/25*(5*t-2)*exp(t)"),
    ("dsolve(diff(y(t),t,t,t)-y(t)=0);",
     "y(t) = c__1*exp(t)+c__2*exp(-1/2*t)*sin(1/2*3^(1/2)*t)+c__3*exp(-1/2*t)*cos(1/2*3^(1/2)*t)"),
    ("dsolve(m*diff(y(t),t,t)=-k*y(t));",
     "y(t) = c__1*sin(k^(1/2)/m^(1/2)*t)+c__2*cos(k^(1/2)/m^(1/2)*t)"),
    ("dsolve(diff(y(t),t,t)+2*diff(y(t),t)+5*y(t)=3);",
     "y(t) = exp(-t)*sin(2*t)*c__2+exp(-t)*cos(2*t)*c__1+3/5"),
    # forcing outside undetermined-coefficient forms: variation of parameters
    ("dsolve(diff(y(t),t)+y(t)=f(t));", "y(t) = (Int(f(t)*exp(t),t)+c__1)*exp(-t)"),
    ("sol := dsolve(diff(y(t),t,t)+3*diff(y(t),t)+2*y(t)=1/(1+exp(t))):"
     "odetest(sol, diff(y(t),t,t)+3*diff(y(t),t)+2*y(t)=1/(1+exp(t)));", "0"),
    # systems and nonlinear first order (SymPy)
    ("dsolve({diff(x(t),t)=y(t), diff(y(t),t)=-x(t), x(0)=1, y(0)=0});",
     "{x(t) = cos(t), y(t) = -sin(t)}"),
    ("dsolve({diff(y(t),t)=0.3*y(t)*(1-y(t)), y(0)=0.1});", "y(t) = 1/(1+9*exp(-3/10*t))"),
    # autonomous y'' = f(y): implicit energy-integral form
    ("dsolve([diff(y(t),t,t)=-sin(y(t)), y(0)=0, D(y)(0)=1]);",
     "y(t) = RootOf(-Int(1/(2*cos(_a)-1)^(1/2),_a = 0 .. _Z)+t)"),
    ("dsolve([diff(y(t),t,t)=cos(y(t)), y(1)=0, D(y)(1)=0]);",
     "y(t) = RootOf(-Int(-1/2*2^(1/2)/sin(_a)^(1/2),_a = 0 .. _Z)+t-1), "
     "y(t) = RootOf(-Int(1/2*2^(1/2)/sin(_a)^(1/2),_a = 0 .. _Z)+t-1)"),
    ("odetest(y(t)=cos(2*t), [diff(y(t),t,t)=-4*y(t), y(0)=1, D(y)(0)=0]);", "[0, 0, 0]"),
    ("odetest(y(t)=cos(2*t), {diff(y(t),t,t)=-4*y(t), y(0)=2, D(y)(0)=1});", "{0, 1}"),
    ("odetest(y(t)=exp(t), diff(y(t),t)=-y(t));", "2*exp(t)"),
    ("odetest({x(t)=cos(t), y(t)=sin(t)}, [diff(x(t),t)=y(t), diff(y(t),t)=-x(t)]);",
     "[-2*sin(t), 2*cos(t)]"),
])
def test_dsolve_matches_maple(code, maple):
    same(code, [maple] if isinstance(maple, str) else maple)


def test_dsolve_symbolic_forcing_frequency_is_fast():
    # notes3_damped_14: float coefficients + symbolic omega used to hang SymPy's dsolve
    code = ("m:=1: y0:=.05: g:=9.81: k:=m*g/y0: b:=sqrt(4*m*k)/8:"
            "ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=3*sin(omega*t):"
            "s := evalf(dsolve({ode, x(0)=0.02, D(x)(0)=0})): evalf(subs(omega=3, t=1, rhs(s)));")
    t0 = time.time()
    out = run1(code)
    assert time.time() - t0 < 10
    assert abs(float(out[0]) - 0.003866376676) < 1e-11      # cmaple: .3866376676e-2


def test_nonlinear_higher_order_gives_up_quickly():
    t0 = time.time()
    out = run1("dsolve({diff(q(t),t,t)=.3*diff(q(t),t)^2+29.43*cos(q(t))-29.43*sin(q(t)),"
               " q(0)=Pi/2, D(q)(0)=0});")
    assert out == [] and time.time() - t0 < 10


def test_numeric_listprocedure_is_callable():
    s = Session()
    out = texts(s, "s2 := dsolve({diff(y(t),t)=-y(t), y(0)=1}, numeric, output=listprocedure):"
                   "ys := eval(y(t), s2); ys(1); s2(0.5); fsolve(ys(t)=0.5, t=0..2); ys(t);")
    assert out[0].startswith("ys := proc (t)")
    assert abs(float(out[1]) - 0.367879356307219) < 1e-6
    assert out[2].startswith("[t(.5) = .5, y(t)(.5) = .60653")
    assert abs(float(out[3]) - 0.6931471806) < 1e-6
    # unevaluated for a symbolic argument, evaluated again once it is a number
    assert texts(s, "eval(ys(t), t=1);") == [out[1]]


def test_numeric_procedure_output():
    out = run1("sol := dsolve({diff(y(t),t)=-y(t), y(0)=1}, numeric); sol(1.0);")
    assert out[0] == "sol := proc (x_rkf45) `...` end proc"
    same("dsolve({diff(y(t),t)=-y(t), y(0)=1}, numeric)(1.0);", ["[t = 1.0, y(t) = .367879356307219]"])
