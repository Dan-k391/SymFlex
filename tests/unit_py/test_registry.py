"""The builtins registry API that library modules use."""
import sympy as sp

from symflex_maple import Session
from symflex_maple.builtins import Library, get_registry, is_true
from symflex_maple.values import MList


def _install():
    lib = Library()

    @lib.builtin("demo_opts", sig="demo_opts(x, numeric, n = 3)", doc="Test function.",
                 options={"numeric": False, "n": None})
    def demo(ctx, x, numeric=False, n=None):
        return MList([x, sp.true if is_true(numeric) else sp.false, n if n is not None else 0])

    @lib.builtin("demo_raw", evaluate=False, doc="Receives AST nodes.")
    def raw(ctx, node):
        from symflex_maple.printer import unparse
        return sp.Symbol(unparse(node))

    @lib.builtin("demo_idx", indexed=True, doc="Indexed call.")
    def idx(ctx, x, index=None):
        return x * (index[0] if index else 1)

    @lib.builtin("Thing", package="DemoPkg", doc="Package export.")
    def thing(ctx):
        return sp.Integer(42)

    lib.register(get_registry())


_install()


def run(code):
    return [o["text"] for o in Session().run(code)]


def test_options_and_flags():
    assert run("demo_opts(y, numeric, n = 5); demo_opts(y);") == ["[y, true, 5]", "[y, false, 0]"]


def test_unevaluated_arguments():
    assert run("a := 3: demo_raw(a + 1);") == ["`a+1`"]


def test_indexed_call():
    assert run("demo_idx[3](x); demo_idx(x);") == ["3*x", "x"]


def test_package_exports_and_with():
    assert run("DemoPkg:-Thing(); with(DemoPkg); Thing();") == ["42", "[Thing]", "42"]


def test_python_exceptions_become_maple_errors():
    assert run("demo_opts();")[0].startswith("Error, invalid input: demo_opts")


def test_docs_reach_completion():
    items = Session().complete("demo_o")
    assert items[0]["detail"] == "demo_opts(x, numeric, n = 3)"
