"""Parser: structure checks and unparse round-trips (parse -> unparse -> parse is stable)."""
import pytest

from symflex_maple import nodes as N
from symflex_maple.errors import MapleSyntaxError
from symflex_maple.parser import Parser, parse, parse_expr
from symflex_maple.printer import unparse, unparse_stmt

ROUND_TRIP = [
    "a+b*c^2", "-x^2", "a-b-c", "a/b/c", "(a+b)*c", "2^(-1)", "x^-2", "a*-b",
    "x = 1 .. 2", "t = 0 .. t", "a <> b", "a <= b", "not a and b", "a or b xor c implies d",
    "diff(y(t), t $ 2)", "D(y)(0)", "evalf[4](x)", "a[i][j]", "a[1 .. 2]", "plottools:-getdata(p)",
    "'x'", "`my name`", '"str"', "5!", "f@g", "D@@2", "a &x b", "A . B", "x mod 3",
    "{1, 2} union {3}", "s minus {1}", "a subset b", "x in S", "x -> x^2", "(x, y) -> x+y",
    "[1, 2, 3]", "{a, b}", "<1, 2, 3>", "<1|2|3>", "<<1, 2>|<3, 4>>", "%", "%%", "%%%",
    ".5", "1.", "2.5e-3", "1.5e3", "$1 .. 4", "a, b, c", "f()", "x::integer",
    "proc (x::numeric, y := 2) local z; z := x+y; z^2 end proc",
    "proc (n) option remember; if n < 2 then n else procname(n-1)+procname(n-2) end if end proc",
]


@pytest.mark.parametrize("src", ROUND_TRIP)
def test_round_trip(src):
    tree = parse_expr(src)
    text = unparse(tree)
    assert unparse(parse_expr(text)) == text


def test_precedence():
    e = parse_expr("a + b*c^2")
    assert isinstance(e, N.BinOp) and e.op == "+"
    assert e.right.op == "*" and e.right.right.op == "^"
    rel = parse_expr("t = 0..t")
    assert isinstance(rel, N.Rel) and isinstance(rel.right, N.Range)
    neg = parse_expr("-x^2")
    assert isinstance(neg, N.UnOp) and neg.operand.op == "^"
    seq = parse_expr("diff(y(t), t$2)")
    assert isinstance(seq.args[1], N.SeqOp)


def test_power_is_non_associative():
    with pytest.raises(MapleSyntaxError, match="ambiguous use of `\\^`"):
        parse_expr("x^y^z")


def test_statements_and_terminators():
    tops = parse("a := 1: b := 2; c")
    assert [t.display for t in tops] == [False, True, True]
    assert isinstance(tops[0].stmt, N.Assign)
    multi = parse("a, b := 1, 2;")[0].stmt
    assert len(multi.targets) == 2


def test_compound_statements():
    src = """
    for i from 1 by 2 to 9 while i < 7 do x := i od;
    for x in [1,2] do print(x) end do;
    while true do break end do;
    if a then 1 elif b then 2 else 3 fi;
    try error "boom %1", 3 catch "boom": 1 finally 2 end try;
    f := proc(x) local y := 1; global g; description "d"; return x+y end proc;
    use LinearAlgebra in Transpose(A) end use;
    """
    kinds = [type(t.stmt).__name__ for t in parse(src)]
    assert kinds == ["For", "For", "For", "If", "Try", "Assign", "Use"]
    loop = parse("for i from 1 by 2 to 9 while i < 7 do x := i od;")[0].stmt
    assert loop.var == "i" and loop.cond is not None


def test_comments_and_continuation():
    tops = parse("x := 1 + # comment\n 2; (* block\ncomment *) y := [1,\n2];")
    assert len(tops) == 2


def test_angle_brackets_vs_relations():
    e = parse_expr("<a, b> + c")
    assert isinstance(e, N.BinOp) and isinstance(e.left, N.Angle)
    r = parse_expr("a < b")
    assert isinstance(r, N.Rel)
    m = parse_expr("<<1,2>|<3,4>>")
    assert m.sep == "|" and len(m.items) == 2


def test_number_forms():
    assert isinstance(parse_expr("1..3"), N.Range)
    assert parse_expr("1.").text == "1."
    assert parse_expr("5e3").text == "5e3"
    assert isinstance(parse_expr(".5"), N.FloatLit)


def test_syntax_errors_are_lazy():
    p = Parser("a := 1; b := ); c := 3;")
    it = p.top_statements()
    assert isinstance(next(it).stmt, N.Assign)
    with pytest.raises(MapleSyntaxError):
        next(it)


def test_missing_operator():
    with pytest.raises(MapleSyntaxError, match="missing operator"):
        parse("x y;")


def test_unparse_statements():
    s = parse("if x > 0 then y := 1 else y := 2 end if;")[0].stmt
    assert unparse_stmt(s) == "if x > 0 then y := 1 else y := 2 end if"
