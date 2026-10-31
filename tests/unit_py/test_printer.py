"""1-D printer vs strings captured from real cmaple (printer_cases.json, regenerate with
gen_printer_cases.py), plus LaTeX spot checks."""
import json
import pathlib

import sympy as sp

from symflex_maple import Session
from symflex_maple.printer import latex, lprint, maple_float

HERE = pathlib.Path(__file__).parent

# Known, accepted differences (mostly decimal-vs-binary float mantissas and term order).
# The corpus comparator is semantic, so these do not affect golden tests.
KNOWN = {
    "1.0": "1.",                                  # Maple keeps the literal mantissa 10*10^-1
    "1.5e3": "1500.",                             # Maple: .15e4 (literal mantissa)
    "3.0*2": "6.",
    "9.81*40": "392.4",                           # Maple: 392.40 (decimal arithmetic)
    "2.0*x": "2.*x",
    "x^2*1.0e-5": ".1e-4*x^2",
    "f := 1/2*exp(-t)*(sin(2*t)+2*cos(2*t))": "f := 1/2*(sin(2*t)+2*cos(2*t))*exp(-t)",
    "a^(-2)*b": "b/a^2",
    "int(sin(x)^2,x)": "1/2*x-1/2*sin(x)*cos(x)",
    "solve(x^2=4)": "-2, 2",
    "solve(x^2+1=0)": "-I, I",
    "evalc(exp(I*x))": "I*sin(x)+cos(x)",
    "series(exp(x), x=0, 3)": "series(1+x+1/2*x^2+O(x^3),x,3)",
    # applying an assigned expression as a function: Maple distributes over exp(-t) etc.
    "f(x,y)": None,
    # Maple also prints a "Warning, solving for expressions..." first
    "solve([x+y=1,x-y=0],[x,y])": "Error, (in solve) a constant is invalid as a variable, -.1e-2",
}


def test_against_cmaple():
    cases = json.loads((HERE / "printer_cases.json").read_text())
    s = Session()
    bad = []
    for src, maple in cases:
        ours = "\n".join(o.get("text", "<plot>") for o in s.run(src + ";"))
        expected = KNOWN.get(src, maple)
        if expected is not None and ours != expected:
            bad.append(f"{src!r}: ours={ours!r} maple={maple!r}")
    assert not bad, "\n".join(bad)


def test_float_format():
    f = lambda s, d=10: maple_float(sp.Float(s, d))
    assert f("0.3333333333") == ".3333333333"
    assert f("1200") == "1200."
    assert f("0.012") == ".12e-1"
    assert f("1e20") == ".1e21"
    assert f("-0.5") == "-.5"
    assert f("0") == "0."
    assert maple_float(sp.Float(0.367879441171442)) == ".367879441171442"


def test_latex():
    assert latex(sp.Float("392.4", 10)) == "392.4"
    assert latex(sp.Float("0.25", 10)) == "0.25"
    assert latex(sp.Symbol("c__1")) == "c_{1}"
    assert latex(sp.Symbol("theta")) == "\\theta"
    t = sp.Symbol("t")
    y = sp.Function("y")
    assert latex(sp.Derivative(y(t), t)).startswith("\\frac{d}{dt}")
    assert "\\begin{cases}" in latex(sp.Piecewise((t, t < 1), (2, True)))
    assert latex(sp.Float("1.2e-5", 10)) == "1.2\\times 10^{-5}"
    assert latex(sp.Float("3.14159", 10), displayprecision=2) == "3.14"


def test_latex_outputs_from_session():
    s = Session()
    out = s.run("W := 392.4; M := Matrix([[1,2],[3,4]]); {a, b};")
    assert out[0]["latex"] == "W := 392.4"
    assert "\\begin{matrix}" in out[1]["latex"]
    assert out[2]["latex"].startswith("\\left\\{")


def test_lprint_wrappers():
    from symflex_maple.values import MEquation, MList, MRange, MSet, MString
    x = sp.Symbol("x")
    assert lprint(MSet([MEquation(x, 1)])) == "{x = 1}"
    assert lprint(MList([MString("a"), MRange(0, 1)])) == '["a", 0 .. 1]'
