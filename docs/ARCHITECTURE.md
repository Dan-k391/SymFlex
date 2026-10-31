# SymFlex — architecture & contracts

SymFlex is a Jupyter-style web notebook that emulates **Maple 2024** (1-D Maple input) and
**FlexPDE 8** scripts well enough to run every example from the McMaster EP 2CD4 course
notes and lab solutions. Real Maple (`cmaple.exe`) and FlexPDE (`FlexPDE8n.exe -S`) are
installed locally and are used **only** to produce golden outputs for the test suites; the
web app never calls them.

## Layout

```
SymFlex/
  index.html, package.json, vite.config.js
  src/ui/            notebook UI (vanilla JS + CodeMirror 6 + KaTeX + Plotly)
  src/ui/lang/       Maple + FlexPDE CodeMirror languages, completion/hover data
  src/maple/         worker.js: Pyodide web worker hosting the Python Maple engine
  src/flex/          FlexPDE engine (pure JS, runs in Node and in a web worker)
  py/symflex_maple/  Maple engine (Python + SymPy; runs in CPython for tests, Pyodide in browser)
  public/pyodide/    vendored Pyodide + sympy/mpmath wheels (scripts/fetch_pyodide.mjs; gitignored)
  corpus/raw/        auto-extracted code blocks (scripts/extract_corpus.py) — do not hand edit
  corpus/cases/      cleaned, runnable test cases: <source>/<source>_<nn>.mpl|.pde
  corpus/golden/     outputs from the real tools: <source>/<source>_<nn>.json
  corpus/media, corpus/pages   reference images (Maple output images, PDF pages)
  scripts/           automation (extract, golden generation, bundling, test runners)
  tests/             test runners + unit tests
  docs/flexpde_help/ decompiled FlexPDE 8 manual (HTML) — the syntax reference
```

## Maple engine (Python, `py/symflex_maple`)

Public API (the only thing the worker and tests use):

```python
from symflex_maple import Session
s = Session()
outs = s.run(code: str)          # runs one notebook cell; state persists across calls
s.complete(prefix: str) -> list  # [{label, kind, detail, doc}] names for IntelliSense (builtins + user vars)
s.reset()                         # same as restart
```

`run` returns a list of output dicts, in order:

| kind      | fields                                   | when |
|-----------|------------------------------------------|------|
| `math`    | `text` (Maple 1-D lprint form, e.g. `W := 392.40`), `latex` | statement ended by `;` |
| `plot`    | `spec` (PlotSpec JSON, below)            | a plot value is displayed |
| `print`   | `text`                                   | print/printf/lprint output |
| `warning` | `text` (`Warning, ...`)                  | |
| `error`   | `text` (`Error, (in solve) ...`)         | stops the rest of the cell, like Maple |

`text` must follow Maple's `interface(prettyprint=0)` format closely (this is what the golden
files contain), e.g. `sol := {x = 3/2, y = 1/2}`, `u(t) = 1/2*exp(-t)*(sin(2*t)+2*cos(2*t))`,
`PIECEWISE([t, t < 1],[2, otherwise])`, `[t = 1., z(t) = .367879356307219]`.
Comparison with golden output is *semantic* (see tests), so exact term order/float digits need
not match, but the structure (assignment prefix, list vs set, equation sides) must.

Internals (owned by the core; library modules plug in):
- `lexer.py`, `parser.py` → AST for full 1-D Maple statement syntax.
- `evaluator.py` → Maple evaluation rules (full evaluation of names, `%`/`%%`/`%%%`,
  `restart`, `assign`, unassign `x:='x'`, procs, arrow functions, loops, if, seq, `$`, ...).
- values: SymPy objects for algebra; wrapper classes in `values.py` for list, set, equation /
  inequality (never let SymPy auto-evaluate `Eq`), range, string, expression sequence, NULL,
  procedure, table, Vector/Matrix, plot.
- `printer.py` → 1-D Maple text and LaTeX for every value.
- `builtins/` → one module per area, each exporting a `register(env)`:
  `core.py` (eval, subs, op, nops, lhs, rhs, assign, seq, map, type, whattype, convert, evalf, ...),
  `algebra.py` (simplify, expand, factor, normal, collect, coeff, solve, fsolve, maximize, minimize, ...),
  `calculus.py` (diff, D, int, limit, sum, product, series, piecewise, ...),
  `ode.py` (dsolve symbolic/numeric incl. `output=listprocedure`, odetest, ...),
  `linalg.py` (Matrix, Vector, LinearAlgebra, VectorCalculus incl. `&x`, `.`, Normalize, BasisFormat, ...),
  `plots.py` (plot, loglogplot, semilogplot, logplot, odeplot, display, pointplot, animate, plot3d, ...).
- Floats: `Digits` (default 10) governs evalf precision and display.

## FlexPDE engine (JS, `src/flex`)

```js
import { runFlex } from './src/flex/index.js'
const result = await runFlex(scriptText, { onProgress(msg) {} })
// result = { title, log: [..], errors: [{line, msg}], reports: [{label, value}],
//            final: {t, values: {var: number}}, plots: [PlotSpec], halted: bool }
```
Must handle everything in the course: COORDINATES cartesian1/2, SELECT (ngrid, errlim, ...),
VARIABLES incl. `threshold=` and vector variables `r = vector(rx, ry)`, DEFINITIONS (incl.
`if..then..else`, vector(), magnitude(), dot(), xcomp()/ycomp(), functions of t), INITIAL VALUES,
EQUATIONS `v: dt(v) = ...`, BOUNDARIES (REGION/START/LINE TO/CLOSE, VALUE/NATURAL BCs),
TIME a TO b [by dt] [halt cond], PLOTS/MONITORS/SUMMARY with `for t = a by d to endtime`,
history(...) at (...) [vs ...], report, elevation, contour, surface, vector plots, END.
ODE-style problems (ngrid=1) integrate the time system with an adaptive integrator; real 2-D
steady/transient PDEs (e.g. the default `div(grad(u))=0` template) use a simple P1 FEM.

## PlotSpec (shared by both engines, rendered by `src/ui/plot.js` with Plotly)

```json
{ "type": "2d" | "3d" | "contour" | "surface" | "vector",
  "title": "", "xlabel": "", "ylabel": "", "zlabel": "",
  "xlog": false, "ylog": false, "xrange": [a,b] | null, "yrange": [a,b] | null,
  "scaling": "unconstrained" | "constrained",
  "curves": [{ "x": [], "y": [], "z": [] , "legend": "", "color": "", "style": "line"|"point",
               "thickness": 1, "dash": "solid" }],
  "grid": { "x": [], "y": [], "z": [[...]] },          // contour/surface on a grid
  "mesh": { "x": [], "y": [], "tri": [[i,j,k]], "values": [] },  // FEM data
  "arrows": { "x": [], "y": [], "u": [], "v": [] },
  "frames": [ PlotSpec ]                              // animations
}
```

## Tests

- `scripts/gen_golden_maple.py` runs each `corpus/cases/**/*.mpl` through real cmaple with
  `interface(prettyprint=0, screenwidth=infinity)` (re-applied after every `restart`) and records
  one entry per displayed output: `{kind: math|plot|print|warning|error, text, plot?}` where plot
  data comes from `plottools:-getdata`.
- `scripts/gen_golden_flex.py` runs each `.pde` through FlexPDE8n -S with extra exports and
  records reports, final values and history series.
- `tests/run_maple_corpus.py` / `tests/run_flex_corpus.mjs` run our engines on the same cases
  and compare semantically (numbers to ~1e-6 relative for exact/symbolic, looser for numeric
  ODE/FEM; symbolic expressions by random-point evaluation; plots by sampled curves).
- `npm test` runs everything and prints a pass/fail table (`tests/report.md`).
