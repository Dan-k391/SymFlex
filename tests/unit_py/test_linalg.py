"""Vector/Matrix semantics checked against real Maple 2024 (cmaple) output."""
from helpers import run1

TAIL = ",storage = rectangular,order = Fortran_order,shape = [])"


def vec(entries, dtype="anything", n=3, orient="column"):
    return f"Vector[{orient}]({n},{{{entries}}},datatype = {dtype}" + TAIL


def test_entries_evaluated_by_operations_not_by_lookup():
    out = run1("v := <0,0,a>: a := 5: v; v[3]; v + <1,2,3>; 2*v; -v; map(x -> x^2, v); "
               "<1,2,3> . v; diff(<a*t, 0, 0>, t);")
    assert out == [vec("3 = a"), "5", vec("1 = 1, 2 = 2, 3 = 8"), vec("3 = 10"), vec("3 = -5"),
                   vec("3 = 25"), "15", vec("1 = 5")]


def test_eval_subs_evalf_leave_entries_alone():
    out = run1("v := <a*t, b>: a := 2: subs(b = 3, v); evalf(v);")
    assert out == [vec("1 = a*t, 2 = 3", n=2), vec("1 = a*t, 2 = b", n=2)]


def test_matrix_entries_evaluated():
    out = run1("m := Matrix([[a, b], [c, d]]): b := 7: m[1, 2]; m . <1, 1>; "
               "with(LinearAlgebra): Determinant(m);")
    assert out[:2] == ["7", vec("1 = a+7, 2 = c+d", n=2)]
    assert out[2] == "a*d-7*c"


def test_cross_product_needs_a_package():
    out = run1("<1,2,3> &x <0,0,1>;")
    assert "&x" in out[0] and "{1 = 1, 2 = 2, 3 = 3}" in out[0]   # stays unevaluated
    out = run1("with(LinearAlgebra): <1,2,3> &x <0,0,1>; <1,2> &x <3,4>;")
    assert out[0] == vec("1 = 2, 2 = -1")
    assert out[1].startswith("Error, (in LinearAlgebra:-&x) invalid input: LinearAlgebra:-&x expects "
                             "its 1st argument, V1, to be of type Vector(3)")


def test_hardware_float_contagion():
    out = run1("<1,2,3> + <0,0,2.5>; 2.0*<1,2>; 2*<1.5,2>; <1,2,x> + <0.5,0,0>; "
               "Matrix([[1,2],[3,4.0]]) . <1,2>;")
    assert out[0] == vec("1 = 1., 2 = 2., 3 = 5.5", "float[8]")
    assert out[1] == vec("1 = 2., 2 = 4.", n=2)
    assert out[2] == vec("1 = 3., 2 = 4.", "float[8]", n=2)
    assert out[3] == vec("1 = 1.5, 2 = 2, 3 = x")
    assert out[4] == vec("1 = 5., 2 = 11.", "float[8]", n=2)
    # VectorCalculus also turns float scalar multiples into hardware floats
    assert run1("with(VectorCalculus): 2.0*<1,2>;")[0] == vec("1 = 2., 2 = 4.", "float[8]", n=2)


def test_dot_conjugates_except_under_vectorcalculus():
    assert run1("<a,b> . <c,d>;") == ["c*conjugate(a)+d*conjugate(b)"]
    assert run1("<a|b> . <c,d>;") == ["a*c+b*d"]
    assert run1("with(VectorCalculus): <a,b> . <c,d>;") == ["a*c+b*d"]


def test_rtable_arithmetic_errors():
    out = run1("<1,2> + 1;")
    assert out == ["Error, a constant cannot be added to a Vector; use +~ for elementwise addition "
                   "instead of +"]
    assert run1("<1,2> + 0;") == [vec("1 = 1, 2 = 2", n=2)]
    assert run1("<1,2> + <1,2,3>;") == [
        "Error, (in rtable/Sum) invalid input: dimensions do not match: Vector[column](1 .. 2) "
        "cannot be added to Vector[column](1 .. 3)"]
    assert run1("<1,2> * <1,2>;")[0].startswith("Error, (in rtable/Product) use *~")
    assert run1("Matrix([[1,2],[2,4]])^(-1);") == ["Error, (in rtable/Power) singular matrix"]


def test_linear_solve():
    out = run1("with(LinearAlgebra): LinearSolve(Matrix([[1,2],[3,4]]), <5,6>); "
               "LinearSolve(Matrix([[1,1],[1,1]]), <2,2>); LinearSolve(Matrix([[1,1],[1,1]]), <2,3>);")
    assert out[0] == vec("1 = -4, 2 = 9/2", n=2)
    assert out[1] == vec("1 = -_t[2]+2, 2 = _t[2]", n=2)
    assert out[2] == "Error, (in LinearAlgebra:-LinearSolve) inconsistent system"


def test_eigenvalues():
    out = run1("with(LinearAlgebra): Eigenvalues(Matrix([[2,0],[0,3]])); "
               "Eigenvalues(Matrix([[4.,1],[2,3]]));")
    assert out[0] in (vec("1 = 2, 2 = 3", n=2), vec("1 = 3, 2 = 2", n=2))
    assert out[1] == vec("1 = 5., 2 = 2.", "complex[8]", n=2)


def test_solve_vector_equation():
    assert run1("solve(<a+b, a-b> = <3, 1>, {a, b});") == ["{a = 2, b = 1}"]
    assert run1("solve(<a+b-3, a-b-1>);") == ["{a = 2, b = 1}"]


def test_norms():
    out = run1("with(LinearAlgebra): Norm(<3,-4>); Norm(<3,-4>, 1); Norm(<3,-4>, 2); "
               "Norm(Matrix([[1,-2],[3,4]])); Normalize(<3,4>, Euclidean);")
    assert out == ["4", "7", "5", "7", vec("1 = 3/5, 2 = 4/5", n=2)]
