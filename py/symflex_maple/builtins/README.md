# Adding Maple functions (builtins)

Every area module (`core.py`, `algebra.py`, `calculus.py`, `ode.py`, `linalg.py`, `plots.py`)
follows the same pattern and is loaded by `get_registry()` in `__init__.py` (in the order of
`AREA_MODULES`; a later module overrides an earlier one for the same global name).

```python
import sympy as sp
from ..errors import MapleError
from ..values import MEquation, MList, MSet, MRange, NULL, deep_map, make_seq
from . import Library, is_true
from .core import equations_of, has_float, to_sympy, subs_value, lambda_proc, as_items

lib = Library()
builtin = lib.builtin


def register(env):          # required: called once when the registry is built
    lib.register(env)


@builtin("simplify", sig="simplify(expr)", doc="Simplify an expression.")
def m_simplify(ctx, e, *opts):
    return deep_map(sp.simplify, e)          # deep_map walks lists, sets, equations, matrices


@builtin("dsolve", sig="dsolve({ode, ics}, y(t), options)", doc="Solve ODEs.",
         options={"numeric": False, "output": None, "method": None})
def m_dsolve(ctx, eqs, *rest, numeric=False, output=None, method=None):
    if is_true(numeric): ...
    if output is not None and str(output) == "listprocedure": ...


@builtin("seq", evaluate=False, doc="Arguments arrive as AST nodes.")
def m_seq(ctx, body, spec=None, step=None):
    v = ctx.eval(body, ctx.frame)            # evaluate a node yourself


@builtin("evalf", indexed=True, doc="evalf[n](x) passes index=(n,)")
def m_evalf(ctx, e, n=None, index=None): ...


@builtin("Normalize", package="VectorCalculus", sig="Normalize(v)", doc="Unit vector.")
def m_normalize(ctx, v): ...                 # only visible as VectorCalculus:-Normalize / after with()


@lib.operator(".")                           # binary operators on rtables: fn(ctx, a, b)
def op_dot(ctx, a, b): ...                   # return NotImplemented to fall back to the core


@lib.type("numeric")                         # type(x, numeric), proc(x::numeric)
def t_numeric(ctx, v, *params): return ...


@lib.on_with("VectorCalculus")               # runs on every with(VectorCalculus)
def vc_loaded(ctx): ...
```

## `@lib.builtin(name, *, sig, doc, options, evaluate, indexed, package, also_global)`

| argument | meaning |
|---|---|
| `name` | Maple name, or a list of aliases (`["int", "integrate"]`) |
| `sig`, `doc` | one-line signature and description, returned by `Session.complete()` |
| `options` | names recognised in the argument list. `name = value` equations become keyword arguments and a bare `name` becomes `name=sp.true`; everything else stays positional. Use `is_true(v)` to test flags. Python keywords get a trailing underscore (`lambda` -> `lambda_`). |
| `evaluate=False` | the function receives AST nodes (`nodes.py`); evaluate with `ctx.eval(node, ctx.frame)`. Needed for `seq`, `add`, `` `if` ``, `assigned`, ... |
| `indexed=True` | `f[a, b](x)` calls `f(ctx, x, index=(a, b))` |
| `package` | install as an export of that package (string or list); `also_global=True` also installs it globally |

The function is called as `fn(ctx, *positional, **options)` with fully evaluated Maple values
(expression sequences flattened). Return any Maple value; `None` means `NULL`.

Errors: raise `MapleError("message")`. The core prefixes `(in name)` automatically (Maple style
`Error, (in solve) ...`) unless the message starts with `invalid input` or `numeric exception`,
or you pass `where=` yourself. Any other Python exception is converted to
`Error, (in name) <exception text>`, so a crash never escapes `Session.run`. Wrong argument counts
give `Error, invalid input: name does not accept N arguments here`.

## Values (see `values.py`)

* Algebraic values are SymPy objects: `Symbol` for unassigned names (Maple names verbatim, only
  `Pi`, `I`, `infinity`, `true`, `false`, `FAIL` are special), `Function(name)(args)` for
  unknown calls (`y(t)`), `Float` at `ctx.digits` precision, `Piecewise`, `Derivative`,
  `Subs(Derivative(y(x), x), x, 0)` for `D(y)(0)`, `Indexed` for `a[i]`.
* Wrappers: `MList`, `MSet` (dedup + deterministic order), `MEquation(lhs, rhs)` and
  `MRelation(op, lhs, rhs)` with op in `= <> < <=` (`>`/`>=` are flipped; never SymPy `Eq`),
  `MRange(lo, hi)`, `MString` (a `str`), `ExprSeq` / `NULL`, `MLogic` (unevaluated and/or/not),
  `MTable`, `MMatrix(m)` / `MVector(items, orient)` around a SymPy `Matrix` (`.m`),
  `PlotValue(spec)` (PlotSpec dict from ARCHITECTURE.md), `Module` (packages), procedures
  (`UserProc`, `BuiltinProc`, `RememberProc`, `AppliedProc(fn(ctx, args), label=...)`).
* `deep_map(f, v)` applies `f` to every SymPy leaf; `make_seq(items)` builds a sequence (a
  single item stays itself); `seq_items(v)` views any value as a tuple.
* `core.lambda_proc([x], expr)` builds a procedure value that prints as `x -> expr`
  (what `unapply` and `D` return); `core.proc_as_lambda(ctx, f)` goes the other way.
* `core.to_sympy(v)` converts relations to unevaluated SymPy relationals (for `Piecewise`
  conditions, `solve` of inequalities, ...); `core.from_sympy_rel` converts back.

## The `ctx` (Evaluator) API for libraries

| member | use |
|---|---|
| `ctx.digits` | current `Digits` |
| `ctx.evalf(v, n=None)` | numeric evaluation of any value |
| `ctx.apply(f, args)` | call any procedure value (user proc, builtin, unknown name -> `f(args)`) |
| `ctx.call("name", *args)` | call a Maple function by name (honours user/with() bindings) |
| `ctx.eval(node, ctx.frame)` | evaluate an AST node (for `evaluate=False` builtins) |
| `ctx.full_eval(v)` | re-evaluate names that have been assigned since `v` was built |
| `ctx.binop(op, a, b)` | Maple arithmetic on any values (`+ - * / ^ .`) |
| `ctx.truth(v)` / `ctx.try_truth(v)` | evalb semantics (raise / return None when undecidable) |
| `ctx.type_check(v, t)` | Maple `type(v, t)` |
| `ctx.assign_name(name, v, ctx.frame)`, `ctx.assign_call(name, args, v, frame)` | assignments (used by `assign`) |
| `ctx.print_text(text)`, `ctx.warn(msg)`, `ctx.emit(dict)` | add outputs (`print`, `Warning, msg`, any kind) |
| `ctx.to_text(v)`, `ctx.to_latex(v)` | printers |
| `ctx.settings` | `interface()` settings (`displayprecision`, `BasisFormat`, ...) |
| `ctx.bound`, `ctx.loaded` | names bound by `with()`, packages loaded |
| `ctx.mkfloat(text)` | a Float literal at the current precision |

## Tips

* Keep results Maple-shaped (sets of equations from `solve`, sequences for multiple results,
  `x(t) = ...` from `dsolve`) — the golden tests compare structure.
* If the input contains floats, Maple returns floats: `core.has_float(args)` then
  `ctx.evalf(result)`.
* Avoid SymPy calls that can run for minutes on float-heavy input (there are no threads or
  timeouts in Pyodide); rationalise with `sp.nsimplify(..., rational=True)` or go numeric.
* Add tests to `tests/unit_py/` (pytest); `tests/unit_py/test_registry.py` shows the API.
