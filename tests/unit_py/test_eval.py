"""Evaluation semantics: full evaluation, ditto, restart, procedures, loops, errors, outputs."""
from helpers import run1, texts

from symflex_maple import Session


def test_full_evaluation_picks_up_later_assignments():
    assert run1("ff := mu*N: N := 5: ff;") == ["5*mu"]
    assert run1("a := b: b := c: c := 3: a;") == ["3"]


def test_unassign_and_recursive_assignment():
    assert run1("x := 5: x := 'x': x;") == ["x"]
    assert run1("x := 5; x := 'x';") == ["x := 5", "x := 'x'"]
    assert run1("y := y + 1;") == ["Error, recursive assignment"]


def test_ditto():
    s = Session()
    # each ditto statement pushes its own value too (verified with cmaple)
    assert texts(s, "1+1: 2+2: x := 7: %; %%; %%%;") == ["7", "7", "7"]
    # NULL results do not update ditto
    assert texts(s, "5: NULL; print(1): %;") == ["1", "5"]


def test_restart_clears_state_and_digits():
    s = Session()
    texts(s, "x := 3: Digits := 20:")
    assert texts(s, "restart; x; Digits;") == ["x", "10"]


def test_statement_display_rules():
    assert run1("a := 1: b := 2; c := 3:") == ["b := 2"]
    assert run1("for i to 3 do i^2 end do;") == ["1", "4", "9"]
    assert run1("for i to 3 do i^2 end do:") == []
    assert run1("for i to 2 do for j to 2 do i*j end do end do;") == []
    assert run1("if 1 < 2 then 5 else 6 end if;") == ["5"]
    assert run1("a, b := 1, 2;") == ["a, b := 1, 2"]


def test_loops():
    assert run1("s := 0: for i from 1 by 2 to 9 do s := s + i end do: s; i;") == ["25", "11"]
    assert run1("L := []: for x in [a, b] do L := [op(L), x^2] end do: L;") == ["[a^2, b^2]"]
    assert run1("n := 0: while n < 5 do n := n + 2 end do: n;") == ["6"]
    assert run1("k := 0: do k := k + 1; if k = 3 then break end if end do: k;") == ["3"]
    assert run1("t := 0: for i to 5 do if i = 2 then next end if; t := t + i od: t;") == ["13"]


def test_procedures_and_scoping():
    out = run1("f := proc(x) local y; y := x^2; y + 1 end proc: f(3); f;")
    assert out == ["10", "f"]
    assert run1("g := x -> x^2: g(a+1);") == ["(a+1)^2"]
    assert run1("h := (x, y) -> x*y: h(2, 3);") == ["6"]
    # lexical scoping: inner arrow captures outer local
    assert run1("mk := proc(a) x -> a*x end proc: k := mk(3): k(5);") == ["15"]
    assert run1("c := proc() nargs, [args] end proc: c(1, 2, 3);") == ["3, [1, 2, 3]"]
    assert run1("r := proc(n) if n < 2 then return n end if; r(n-1) + r(n-2) end proc: r(10);") \
        == ["55"]
    assert run1("d := proc(x, y := 10) x + y end proc: d(1); d(1, 2);") == ["11", "3"]


def test_implicit_local_warning():
    out = run1("f := proc(x) y := x; y end proc;")
    assert out[0] == "Warning, (in f) `y` is implicitly declared local"


def test_type_checked_parameters():
    out = run1("f := proc(x::numeric) x^2 end proc: f(a);")
    assert out == ["Error, invalid input: f expects its 1st argument, x, to be of type numeric, "
                   "but received a"]


def test_error_and_try():
    assert run1('f := proc(x) error "bad value %1", x end proc: f(3);') == \
        ["Error, (in f) bad value 3"]
    assert run1('error "top %1 %2", a, 2;') == ["Error, top a 2"]
    out = run1('try error "boom" catch "bo": r := caught finally z := 1 end try: r; z;')
    assert out == ["caught", "1"]
    assert run1("1/0;") == ["Error, numeric exception: division by zero"]


def test_error_stops_the_cell():
    assert run1("a := 1; 1/0; b := 2;") == ["a := 1", "Error, numeric exception: division by zero"]


def test_syntax_error_after_valid_statements():
    out = run1("a := 1; b := );")
    assert out[0] == "a := 1" and out[1].startswith("Error,")


def test_protected_names():
    assert run1("sin := 3;")[0].startswith("Error, attempting to assign to `sin` which is protected")


def test_seq_and_dollar():
    assert run1("seq(i^2, i = 1..4);") == ["1, 4, 9, 16"]
    assert run1("i := 7: seq(i, i = 1..3); i;") == ["1, 2, 3", "7"]
    assert run1("diff(x^3, x$2);") == ["6*x"]
    assert run1("[seq(seq(i*j, i = 1..2), j = 1..2)];") == ["[1, 2, 2, 4]"]


def test_indexing_and_tables():
    assert run1("L := [a, b, c]: L[2]; L[-1]; L[2..3];") == ["b", "c", "[b, c]"]
    assert run1("T[1] := 5: T[1]; T[2];") == ["5", "T[2]"]
    assert run1("L := [1, 2, 3]: L[2] := 9: L;") == ["[1, 9, 3]"]
    assert run1("V := <1, 2, 3>: V[2] := 7: V[2];") == ["7"]


def test_assign_and_function_remember():
    assert run1("assign({a = 1, b = 2}): a + b;") == ["3"]
    out = run1("assign(x(t) = 5*t): x(t); x(1);")
    assert out == ["5*t", "x(1)"]


def test_unknown_functions_and_names():
    assert run1("y(t) + lambda + gamma + N + E;") == ["E+N+gamma+lambda+y(t)"]
    assert run1("Pi; evalf(Pi);") == ["Pi", "3.141592654"]


def test_digits():
    assert run1("Digits := 20: evalf(Pi);") == ["3.1415926535897932385"]
    assert run1("evalf[5](1/3);") == [".33333"]


def test_with_prints_exports_and_binds():
    s = Session()
    out = texts(s, "with(plots);")
    assert out[0].startswith("[animate, animate3d,")
    assert texts(s, "with(VectorCalculus): Norm(<3, 4>);") == ["5"]


def test_member_access():
    assert run1("VectorCalculus:-Norm(<3, 4>);") == ["5"]
    assert run1("plots:-nonexistent(1);")[0] == "Error, module does not export `nonexistent`"


def test_outputs_kinds():
    s = Session()
    outs = s.run('print(1/2); printf("%d|%5.2f\\n", 3, 2.5); plot(x^2, x = 0..1); x := 1;')
    kinds = [o["kind"] for o in outs]
    assert kinds == ["print", "print", "plot", "math"]
    assert outs[1]["text"] == "3| 2.50"
    spec = outs[2]["spec"]
    assert spec["type"] == "2d" and len(spec["curves"][0]["x"]) >= 200
    assert outs[3]["latex"] == "x := 1"


def test_printf_formats():
    out = run1('printf("%d %f %.3f %g %e %s %a %q|%%\\n", 3, 2.5, 3.14159, 0.0001, 12345.678, '
               '"hi", x^2, [1,2]);')
    assert out == ["3 2.500000 3.142 0.0001 1.234568e+04 hi x^2 [1, 2]|%"]


def test_complete():
    s = Session()
    s.run("myvar := 3:")
    labels = [c["label"] for c in s.complete("my")]
    assert "myvar" in labels
    sol = [c for c in s.complete("sol") if c["label"] == "solve"][0]
    assert sol["detail"].startswith("solve(") and sol["doc"]


def test_relations_never_autoevaluate():
    assert run1("e := 2 = 2; evalb(e); x = x;") == ["e := 2 = 2", "true", "x = x"]
    assert run1("(a = b)*2 + 1;") == ["2*a+1 = 2*b+1"]


def test_operator_algebra_and_lne():
    assert run1("f := t -> t^2: g := t -> 2*t: (f + g)(3); f^2;") == ["15", "f^2"]
    assert run1("(sin@cos)(x); (D@@2)(sin);") == ["sin(cos(x))", "x -> -sin(x)"]
