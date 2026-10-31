# SymFlex FlexPDE 8 engine (`src/flex`)

Pure ES modules, no dependencies; runs in Node 22 and in a browser Web Worker.

```js
import { runFlex, lintFlex } from './src/flex/index.js'
const r = await runFlex(text, { onProgress: msg => {}, trace: [] }) // trace: {t,h,E,ok} per step attempt
// r = { title, log, errors:[{line,col,msg,severity:'error'|'warning'}], reports:[{label,value,expr}],
//       final:{t, values:{var:number}, range:{var:[min,max]}}, plots:[PlotSpec], halted, fields? }
lintFlex(text) // -> [{line, col, msg, severity:'error'|'warning'}]
```

| file | role |
|------|------|
| `lexer.js` | tokens, comments (`!`, nested `{}` and `/* */`), FlexPDE-style token names for errors |
| `parser.js` | free-form section parser -> problem description with expression ASTs |
| `expr.js` | expression compiler (AST -> closures), built-in functions, vectors, derivatives |
| `model.js` | unknown layout, definitions, `dt(dt(u))` rewrite, uniform-field context |
| `timestep.js` | FlexPDE-style BDF2 time stepper (error estimate, step control, plot-time landing, halt) |
| `ode.js` | spatially uniform (ngrid=1) systems: implicit residual + dense Newton |
| `mesh.js` | boundary paths -> polygons, Delaunay mesh (2D) / segments (1D), point location |
| `fem.js` | P1 finite elements: weak form, BCs, Newton, banded LU with RCM ordering |
| `plots.js` | PlotSpec builders (history, elevation, contour, surface, vector, grid) |
| `lint.js` | editor diagnostics |

## Supported syntax

- Sections (case-insensitive, free-form, newlines not significant): `TITLE`, `COORDINATES`
  (`cartesian1`, `cartesian2`; others parse but are treated as cartesian), `SELECT` (any
  `name[=value]`; `ngrid`, `errlim`, `terrlim` are used), `VARIABLES` / `GLOBAL VARIABLES`
  (`u`, `u(threshold=..)`, `u(1e-3)`, `r(threshold=..) = vector(rx, ry)`), `DEFINITIONS`
  (constants, expressions of `t`/`x`/`y`/variables, `f(a,b)=...`; names resolve in source order,
  so a use before the definition is "Undefined Name" as in FlexPDE 8), `staged(a, .., z)` (last stage only),
  `INITIAL VALUES`, `EQUATIONS` (`v: dt(v) = a`, unlabeled in variable order, vector
  equations, `dt(dt(x))`, residual form `expr` = 0), `CONSTRAINTS`/`EXTRUSION`/... (skipped),
  `BOUNDARIES` (`REGION n ['name']` with region-local `k = ...`, `START ['name'] (x,y)`,
  `LINE TO (..) TO (..)`, `TO CLOSE`/`CLOSE`, `ARC TO (mid) TO (end)`, `ARC(CENTER=..) TO|ANGLE=`,
  `ARC(RADIUS=..)`, `VALUE(u)=`, `NATURAL(u)=`, `LOAD/NEUMANN(u)=`, `POINT VALUE/LOAD` (1D),
  `EXCLUDE`), `TIME a TO b [BY dt]`, `TIME a BY dt TO b`, `FROM ...`, `HALT cond` / `HALT (cond)`
  / `HALT minimum_dt`, `LIMIT`, `MONITORS` (parsed, not output), `PLOTS`/`HISTORIES`, `END`.
  Comments `!`, `{}` (nested), `/* */`; `;` is an optional statement terminator.
- Plot statements: `for t = a by d to b [by d2 to c]`, `for t = e1, e2`, `for cycle = n`,
  `history(e,..) [at (p) (p2)..] [vs e]`, `elevation(e,..) from (a) to (b)`, `contour(e)`,
  `surface(e)`, `vector(v)|vector(vx,vy) [norm] [points=n]`, `grid(x,y)`, `summary`,
  `report e [as 'label']`, `report (e1, e2)`, `report 'text'`; modifiers `as`, `window(a,b)`,
  `window=w` and the export/format/file/range/zoom/painted/... family (accepted, ignored).
- Expressions: `+ - * / ^` (left-assoc power, `-2^2=-4`, sign after `*` rejected like FlexPDE),
  `< > <= >= = <> and or not`, `if c then a else if ... else b`, `**`/`//` (as `*`/`/`).
  Functions: sin cos tan asin/arcsin acos/arccos atan/arctan atan2 sinh cosh tanh sech csch coth
  exp ln log10 sqrt abs sign min max mod floor ceil erf erfc ustep uramp upulse random,
  vector magnitude dot cross xcomp ycomp zcomp, val/eval, integral (area, region, boundary),
  globalmax/globalmin, dt dx dy grad div curl del2 dxx dyy dxy, `u(x,y)` point values.
  Names: pi, t, x, y, z, r, theta, endtime, deltat.

## Numerics

**ODE mode** (no spatial operator in the equations, e.g. every course `ngrid=1` script): each
variable / vector component is one unknown, integrated with FlexPDE 8.01's own time stepper,
reverse-engineered from its debug logs (`<name>_output/<name>_debug.txt`: CYCLE, DTP, "Max Time
Err", STARTUP lines) and documented in `timestep.js`:
- variable-step BDF2 solved by Newton; error `E = |y - P| h/(h + h_prev) / max(threshold, errlim|y|)`
  with `P` the quadratic through the last three points (equal to FlexPDE's to 1e-4 when its own
  step sequence is replayed);
- the step is steered by a filtered ratio `F += 0.2 (x^-1/4 - F)` (`x = E/errlim`), changed only
  when `F` leaves `[0.98, 1.02]` (max 1.25x); rejection when `x^-1/4 < 0.7`, retry at `h x^-1/4`;
  the step after a rejection and steps landing on plot times leave `F` alone; a plot time within
  1.25 steps is reached in one stretched or clipped step;
- start-up: implicit Euler half/whole steps of size d (cut 10x/2x on its error measure), stored value
  `Yb + (Yb - Yf)/3`, and after a rejected attempt FlexPDE's stale second half-step from `Y0`, which
  offsets every later value (`dt(u)=c` gives `u(2d) = c 2d/3`); the first regular step is
  `d min(1, sqrt(3/M))`.
HALT is tested at the end of each step, so the halt time is a step end (projectile: t=3.8).
Replaying FlexPDE's step sequence reproduces its reports to ~1e-4 (lab3_09 `v(0.5)`
0.0017853020 vs 0.001785302; lab4_07 `vb` 0.000404059 vs 0.000404039 after 8305 steps).

**FEM mode**: P1 triangles (2D) or segments (1D). Mesh: boundary nodes every h plus a hexagonal
interior lattice, Delaunay-triangulated, h = extent/(2*ngrid) (twice FlexPDE's initial density to
compensate for linear instead of cubic elements). Each equation residual is split into
divergence terms `c*div(V)` (integrated by parts; `del2`, `dxx`, `dyy`, `dxy` are rewritten as
divergences) and source terms; `NATURAL(u)=g` is the outward boundary flux, default natural 0;
`VALUE` replaces the nodal equation. Newton with element-wise finite-difference Jacobians, banded
LU after RCM ordering. Pure-Neumann problems get a vanishing mass term, so the course "New
Problem" template (`div(grad(u))=0`, no BCs) returns u=0 like FlexPDE. Time-dependent PDEs use the
same BDF2 stepper with per-node thresholds.

FlexPDE 8 rules reproduced: undefined names (also names used before their definition) give
"Undefined Name: NAME" at their position; grammar errors use FlexPDE's wording ("FlexPDE grammar
does not allow '<identifier>' in this location.", plus a hint for a misspelled section such as
`EQUATION`); `GLOBAL VARIABLES` without `VARIABLES` is "Section Must follow VARIABLES". Bare
fields in REPORT/HISTORY without a location (`report rx`, accepted by FlexPDE 6/7 which the course
scripts were written for, an error in FlexPDE 8) run: they are evaluated at the first START point
and give a `severity: 'warning'` entry in `errors` (and the log) with FlexPDE 8's message;
`lintFlex` warns about them and about a REPORT not attached to a plot command.

## Accuracy against real FlexPDE 8.01 (`node tests/run_flex_corpus.mjs`)

16 PASS, 7 NEAR, 1 ERR-OK (notes2_12, same error and line), 0 FAIL. Bare-field cases (lab2_16,
lab2_20, lab3_*) run with warnings and are compared with the golden of the patched script.
NEAR: lab1_24, lab1_25, lab1_img120, lab2_17, lab2_20, lab3_05, lab4_07. Their step sequences
follow FlexPDE's to ~0.1% but are not identical, and these runs are sensitive to it: halts on a
fast crossing (lab2_17 lands one 3.5 s step later, ry differs by that step's travel), failure
cascades at a burnout discontinuity or at the `errlim=1e-2` close charge pass (lab1_24: rx -1.0505
vs -1.0468; with FlexPDE's step sequence replayed we get -1.0464), and late phase drift in long
oscillator runs (lab4_07). The corpus comparison therefore also accepts, after a HALT, 1e-4 of
the range the quantity sweeps (the value at a crossing is near zero while the error scales with
the variable), and as NEAR the golden trajectory at our end time.

Why exact replication stops at ~0.1%: the start-up measure `M` depends on FlexPDE's stale internal
state for some variables (fitted to 0.5-5%, e.g. projectile `yd`), and the controller's +-2%
deadband keeps any early difference in the step size; the step after a failure followed by a
plot-time landing also updates `F` in a way not yet identified (lab1_24).

## Known gaps

- Step sequences match FlexPDE's to ~0.1%, not bit-identically (see above), so values at a HALT
  can differ by one step.
- FEM is linear (P1) on a fixed mesh: no adaptive regridding, no cubic elements; nonconforming
  interior region boundaries (regions are assigned per element by centroid); no 3D, no
  cylindrical weighting (`ycylinder` is treated as cartesian), no vector variables in FEM mode,
  no CONSTRAINTS, contact/jump/periodic boundaries, moving meshes, eigenvalues, staged problems
  (only the last stage runs), FILLET/BEVEL, BOUNDARY CONDITIONS sets, TABLE/arrays/matrices.
  Accuracy on small samples: within 0.5% of FlexPDE on smooth problems (Poisson, disk, transient
  heat, `tests/flex/samples.test.mjs`); mixed VALUE/NATURAL corners converge slowly (a two-region
  slab is 6-15% off at the default mesh).
- Second derivatives are evaluated by finite differences of the P1 field outside the weak form
  (so `dxx(u)` in a definition used for plotting is ~0); terms like `k(x)*div(grad(u))` drop the
  `grad(k)` contribution.
- MONITORS are not output; exports (`EXPORT`, `FILE`, `FORMAT`), `TABLE`, `PRINT` are ignored.
