"""Core evaluation/printing behaviours checked against real cmaple (Maple 2024)."""
import pytest
from helpers import run1, texts

from symflex_maple import Session


@pytest.mark.parametrize("code, out", [
    ("sin(0.);", "0."), ("cos(0.);", "1."), ("exp(0.);", "1."), ("ln(1.);", "0."),
    ("arccos(0.);", "1.570796327"), ("arctan(1., 0);", "1.570796327"),
    ("arctan(0., -1);", "3.141592654"), ("arctan(0, 0);", "0"), ("log10(10.);", "1."),
    ("floor(2.5);", "2"), ("signum(-2.);", "-1"), ("arctan(1, 1);", "1/4*Pi"),
])
def test_float_argument_gives_float(code, out):
    assert run1(code) == [out]


def test_float_zero_is_kept():
    assert run1("0.*x; 2.*0; 1.*x-1.*x; 0.*x+1; x-x;") == ["0.", "0.", "0.", "1.", "0"]
    assert run1("subs(a=0., m*a); a := 0.: F := m*a;") == ["0.", "F := 0."]
    assert run1("evalf(0); evalf([0, 1]);") == ["0.", "[0., 1.]"]


def test_pi_meets_float():
    assert run1("Pi/180.0; 2.*Pi*t; Pi+1.; Pi^2*1.0;") == [
        ".1745329252e-1", "6.283185308*t", "4.141592654", "9.869604404"]
    # other constants and Pi inside functions stay symbolic, like Maple
    assert run1("sqrt(2)*1.; 1.*exp(1); 1.*sin(Pi/7); 1.*x+Pi;") == [
        "1.*2^(1/2)", "1.*exp(1)", "1.*sin(1/7*Pi)", "1.*x+Pi"]


def test_rtable_entries_evaluate_in_arithmetic_not_display():
    s = Session()
    texts(s, "v := <a, 2>: a := 3:")
    vec = "Vector[column](2,{1 = %s, 2 = %s},datatype = anything,storage = rectangular," \
          "order = Fortran_order,shape = [])"
    assert texts(s, "v; v[1]; 2*v; map(x -> x, v);") == [
        vec % ("a", 2), "3", vec % (6, 4), vec % (3, 2)]


def test_rtable_print_omits_float_zero_entries():
    assert run1("<1., 0, 0.>;") == ["Vector[column](3,{1 = 1.},datatype = anything,storage = "
                                     "rectangular,order = Fortran_order,shape = [])"]


def test_min_max_print_maple_names():
    assert run1("min(x, y); a := max(t, 10.);") == ["min(x,y)", "a := max(10.,t)"]


@pytest.mark.parametrize("code", ["f(a, , b);", "f(a,);", "[1,,2];", "{1,};", "x := 1, , 2;"])
def test_empty_sequence_item_is_syntax_error(code):
    out = run1(code)
    assert len(out) == 1 and out[0].startswith("Error,") and "unexpected" in out[0]


def test_convert():
    assert run1("convert(3.14159, rational); convert(2.718281828, rational); convert(9.81, fraction);"
                "convert(0.333, fraction); convert(1.5*x+0.2, rational);") == [
        "76149/24239", "49171/18089", "981/100", "333/1000", "3/2*x+1/5"]
    assert run1("convert(Pi/4, degrees); convert(0.5, degrees); convert(45*degrees, radians);") == [
        "45*degrees", "28.64788976*degrees", "1/4*Pi"]
    assert run1("convert(30, radians);") == ["Error, (in convert/radians) unable to convert"]


def test_whattype_and_types():
    assert run1("whattype(a, b); whattype(); whattype(I); whattype(exp(1)); whattype(a and b);") == [
        "exprseq", "exprseq", "complex(extended_numeric)", "function", "`and`"]
    assert run1("type(sqrt(2), radical); type(sin(x), trig); type(x^2, radical);") == [
        "true", "true", "false"]


def test_seq_over_string_characters():
    assert run1('seq(c, c in "abc");') == ['"a", "b", "c"']


def test_printf_argument_checks():
    assert run1('printf("%d\\n", 4.0);') == ["Error, (in fprintf) integer expected for integer format"]
    assert run1('printf("%f\\n", x);') == [
        "Error, (in fprintf) number expected for floating point format"]
    assert run1('printf("%s\\n", 2.5);') == ["Error, (in fprintf) string expected for string format"]
    assert run1('printf("%a\\n");') == [
        "Error, (in fprintf) insufficient parameters for algebraic format"]
    assert run1('printf("%f %s %d\\n", 2, x, 3);') == ["2.000000 x 3"]


def test_interface_returns_previous_values():
    s = Session()
    assert texts(s, "interface(displayprecision=2); interface(displayprecision);"
                    "interface(displayprecision=-1);") == ["-1", "2", "2"]


@pytest.mark.parametrize("code, out", [
    ("g := proc(a, b) a + b end proc: g(1);",
     "Error, invalid input: g uses a 2nd argument, b, which is missing"),
    ("op(5, [1, 2]);", "Error, improper op or subscript selector"),
    ("sin(1, 2);", "Error, (in sin) expecting 1 argument, got 2"),
    ("nops();", "Error, invalid input: nops expects 1 argument, but received 0"),
    ("lhs(5);", "Error, invalid input: lhs received 5, which is not valid for its 1st argument, expr"),
    ("subs(x, y);", "Error, invalid input: subs received x, which is not valid for its 1st argument"),
    ("[1, 2] + [1, 2, 3];", "Error, adding lists of different length"),
    ("sin([1, 2]);", "Error, invalid input: sin expects its 1st argument, x, to be of type "
                     "algebraic, but received [1, 2]"),
])
def test_error_messages(code, out):
    assert run1(code) == [out]


def test_keyboard_interrupt_is_reported_and_session_survives(monkeypatch):
    s = Session()
    sin = s.ev.env.functions["sin"]

    def interrupted(ctx, *args):
        raise KeyboardInterrupt
    monkeypatch.setattr(sin, "fn", interrupted)
    out = texts(s, "a := 1; f := proc(x) local i; for i to 3 do sin(x) end do end proc: f(2); b := 2;")
    assert out == ["a := 1", "Error, computation interrupted"]
    monkeypatch.undo()
    assert texts(s, "a; sin(0);") == ["1", "0"]
