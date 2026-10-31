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

### Maple engine core: contract extensions (owner: Maple core, `py/symflex_maple`)

- **Output dicts**: `print` outputs from `print(...)` also carry `latex`. `printf` without a
  trailing `\n` is appended to the previous `print` output of the same cell (one line per `\n`).
- **Plots**: an assignment whose value is a plot (`p := plot(...);`) emits a `plot` output, like
  the GUI, rather than `PLOT(...)` text.
- **Vector/Matrix text** uses cmaple's exact lprint form
  `Vector[column](3,{1 = -3, 3 = 1},datatype = anything,storage = rectangular,order = Fortran_order,shape = [])`
  (zero entries omitted); VectorCalculus' `attributes = [...]` field is not printed.
- **Known text differences** (the comparator must be semantic about these): floats are binary
  (SymPy) so a computed `392.40` prints `392.4` and the last digit can differ by one ulp; term and
  factor order follows SymPy; repeated roots are listed with multiplicity like Maple.
- **Builtins registry** (`py/symflex_maple/builtins/__init__.py`, documented in
  `py/symflex_maple/builtins/README.md`): each area module defines `lib = Library()`,
  decorates `fn(ctx, *args, **options)` with `@lib.builtin(name, sig=, doc=, options=,
  evaluate=, indexed=, package=)`, can register operators (`@lib.operator('.')`), types
  (`@lib.type('numeric')`) and `with()` hooks (`@lib.on_with('VectorCalculus')`), and exports
  `register(env)`. `ctx` is the `Evaluator` (API listed in the README).
- **Package export lists** shown by `with(...)` come from real Maple
  (`builtins/packages_data.py`); exports not implemented yet raise
  `Error, Pkg:-name is not implemented in SymFlex` when called via `Pkg:-name`, and are simply
  not bound by `with()`.

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

### FlexPDE engine: contract extensions (owned by `src/flex`)

- `import { lintFlex } from './src/flex/index.js'`; `lintFlex(text) -> [{line, col, msg, severity}]`
  (`severity` is `'error'` or `'warning'`), for editor diagnostics; it never solves.
- `BUILTIN_NAMES` (exported from `src/flex/index.js`): built-in function/constant names for completion.
- `errors[]` entries also carry `col` (1-based, as FlexPDE prints `Line L Col C:`) and `severity`
  (`'error'` stops the run; `'warning'`, e.g. a FlexPDE 6-style bare-field `report rx`, does not).
- `reports[]` entries also carry `expr` (source text of the reported expression; `label` is the
  `AS` string when given, else the expression text, as in FlexPDE). `REPORT 'text'` gives
  `{label: 'text', value: null}`.
- `final.range = {var: [min, max]}` over the run (ODE mode); `final.values` holds every variable
  component at the final time (ODE mode).
- `fields = {var: {x:[], y:[], tri:[[i,j,k]], values:[]}}` nodal FEM solution at the final time
  (FEM mode only; 1D meshes have `tri` pairs `[i,j]`).
- History PlotSpec curves also carry `t: []` (sample times, also for `vs` plots); histories are
  sampled at every time step, which always includes every `for t = ...` plot time and the end.
- Vector PlotSpecs with `NORM` have unit `arrows.u/v` plus `arrows.magnitude` and `arrows.norm: true`.

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
Maple plots also use: curve `"symbol"`, `"symbolsize"`, `"filled": true` (a closed polygon to fill,
from `filled=true`), `null` x/y entries (gaps: undefined points), spec `"texts": [{x, y, text, color}]`
(textplot), `"axes"` (`normal|boxed|frame|none`), `"gridlines"`, `"zrange"`, and
`{ "type": "array", "rows", "cols", "cells": [PlotSpec | null] }` (row-major, from `display(Array(...))`).

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

## UI (`src/ui`, `src/maple`): extensions to the contracts above

Added by the web-app component; engines do not need to change for any of this.

- **Maple worker protocol** (`src/maple/worker.js`, client `MapleKernel` in `src/ui/kernel.js`):
  in `{type:'init', baseUrl, interruptBuffer?}`, `{type:'run', id, code}`, `{type:'complete', id, prefix}`,
  `{type:'reset', id}`, `{type:'reload', id}`; out `{type:'progress', pct, msg}`, `{type:'ready'}`,
  `{type:'fatal', message}`, `{type:'result', id, outputs}`, `{type:'items', id, items}`, `{type:'done', id}`.
  The worker imports Pyodide at runtime from `public/pyodide/` and unpacks `public/symflex_maple.zip`
  (built from `py/symflex_maple` by `scripts/bundle_py.mjs`) into `/home/pyodide/symflex`.
  `Session.run` results are passed through `json.dumps(default=str)`, so output dicts must be JSON-able.
  Exceptions escaping `Session.run` become `{kind:'error', text:'Error, (internal) ...'}`; anything the
  engine prints to stdout is prepended as a `print` output. `reload` drops all `symflex_maple*`
  modules and builds a new `Session` (used by `npm run dev` when files under `py/` change).
- **Interrupt**: when the page is cross-origin isolated (COOP/COEP headers are set by vite dev and
  preview), `pyodide.setInterruptBuffer` is used and an interrupt raises `KeyboardInterrupt` inside
  `Session.run` (the engine should let it propagate). Otherwise the worker is terminated and restarted.
- **FlexPDE worker** (`src/ui/flexWorker.js`): in `{type:'run', id, code}` / `{type:'lint', id, code}`;
  out `{type:'progress', id, msg}` (msg = whatever `onProgress` receives: a string, or an object with
  `msg`/`message`/`t`), `{type:'result', id, result}`, `{type:'lint', id, diagnostics}`.
  Uses `lintFlex(text)` when `src/flex/index.js` exports it; diagnostics are `{line, col?, endCol?, msg, severity?}`
  (1-based line/col). Errors in `result.errors` with a `line` are clickable and shown as editor squiggles.
- **PlotSpec details assumed by the renderer**: `grid.z[j][i]` is the value at `(x[i], y[j])`
  (Plotly orientation; `z[i][j]` is detected and transposed when the shape makes it unambiguous).
  `type:'contour'` with `mesh` is resampled to a 60x60 grid; `type:'surface'` with `mesh` is a Plotly
  `mesh3d`. `frames[k]` fields override the parent spec for frame k; 2-D animation axes are fixed
  to the union of all frames. Colors are any CSS color (Maple names like `red`, `"Orange"` work).
- **Notebook file** `.symflex.json`: `{format:'symflex', version:1, name, cells:[{type:'maple'|'flexpde'|'markdown',
  source, outputs, execCount, collapsed}]}`; FlexPDE cells store `outputs: [{kind:'flex', result}]`.
- **Examples** `public/examples.json` (from `scripts/build_examples.py`):
  `[{source, title, items:[{id, title, context, kind:'mpl'|'pde', code}]}]`; corpus header comment lines
  (`# SOURCE:`, `# DEPENDS:`, `# NOTE:`, `{ SOURCE: ... }`) are stripped from `code`.
