# symflex_maple — Maple 2024 (1-D input) emulator on SymPy

Pure Python; depends only on `sympy` and `mpmath`, so the same code runs in CPython 3.12+
(tests) and in Pyodide (the browser worker). No threads, subprocesses or numpy.

```python
from symflex_maple import Session
s = Session()
s.run("m := 40: g := 9.81: W := m*g;")   # [{'kind': 'math', 'text': 'W := 392.4', 'latex': 'W := 392.4'}]
s.complete("so")                        # [{'label': 'solve', 'kind': 'function', 'detail': ..., 'doc': ...}, ...]
s.reset()                               # same as restart
```

Output kinds and their fields are specified in `docs/ARCHITECTURE.md`.

## Layout

| file | role |
|---|---|
| `lexer.py` | tokens: names, back-quoted names, numbers (`.5`, `1.`, `2.5e-3`), strings, `&`-operators, comments `#` / `(* *)` |
| `parser.py` | recursive descent parser for the full statement syntax -> `nodes.py` dataclasses. Statements are yielded one at a time, so a syntax error only stops the statements after it (like Maple) |
| `nodes.py` | AST dataclasses |
| `values.py` | wrapper values (lists, sets, equations, ranges, strings, sequences, tables, Vector/Matrix, procedures, packages, plots) |
| `evaluator.py` | Maple evaluation rules (names, assignment, ditto, procedures, loops, errors, indexing, arithmetic dispatch) |
| `printer.py` | 1-D text (`interface(prettyprint=0)` style), LaTeX for the UI, and AST unparsing (procedure display) |
| `session.py` | the public `Session` |
| `builtins/` | Maple functions written in Python, one module per area; see `builtins/README.md` |

## How evaluation works

* **Names.** An unassigned name is a SymPy `Symbol` with exactly the Maple name (`lambda`, `N`,
  `E`, `gamma` are ordinary names). `Pi`, `I`, `infinity`, `true`, `false`, `FAIL` are constants.
  Global values are stored as evaluated at assignment time and **fully re-evaluated on every
  lookup** (`Evaluator.full_eval`): if a stored expression mentions names or functions that have
  been assigned since, they are substituted (`ff := mu_k*N` followed by `assign(%)`). Locals
  evaluate one level. `x := 'x'` unassigns; `x := x + 1` with `x` unassigned is
  `Error, recursive assignment`.
* **Calls.** `f(args)` evaluates `f` and the arguments, then applies: builtins get evaluated
  arguments (or AST nodes when `evaluate=False`), user procedures run in a new `Frame` whose
  parent is the frame they were defined in (lexical scoping; `args`, `nargs`, `procname`,
  parameter types and defaults, keyword parameters `{opt := v}`, `option remember`), unknown
  names give `Function(name)(args)` (or an `MCall` when arguments are not algebraic).
  Assigning `f(x) := v` or `assign(f(x) = v)` creates a remember table (`RememberProc`).
  Named procedures use last-name evaluation: `f;` shows `f`, `f^2` stays symbolic and
  `(f + g)(x)` applies both.
* **Operators.** SymPy arithmetic for algebraic values; lists, equations (`(a = b)*2`),
  sets (`union`/`minus`/`intersect`), procedures (`@`, `@@`), strings/names (`||`) and
  rtables are handled in `_generic_binop`; libraries can override `.`, `&x`, `<,>`, `<|>` and
  rtable arithmetic through `Library.operator`. Relations are never auto-evaluated; `if`,
  `while`, `evalb`, `and`/`or` decide them (numerically for real constants).
* **Statements.** `;` displays, `:` does not. Statements inside a top-level `if`/loop display
  when the compound statement ends with `;` (printlevel 1; deeper nesting does not).
  `%`, `%%`, `%%%` hold the last three non-NULL top-level results (assignments included).
  An error stops the rest of the cell. `restart` clears user state and `Digits`;
  `interface()` settings survive.
* **Floats.** Float literals keep at least `Digits` significant digits; arithmetic follows
  SymPy precision rules (binary, so the last digit can differ from Maple's decimal arithmetic).
  The text printer reproduces Maple's float format (`.3333333333`, `1200.`, `.12e-1`, `.1e21`);
  `interface(displayprecision=n)` only affects the LaTeX output, like the Maple GUI.

## Adding functions

See `symflex_maple/builtins/README.md` for the registry API (`Library`, `@lib.builtin`,
options/flags, unevaluated arguments, indexed calls, packages, operators, types, `with` hooks)
and the `ctx` API.

## Tests

```
python -m pytest tests/unit_py -q
python tests/unit_py/gen_printer_cases.py   # refresh printer_cases.json from the real cmaple
```
