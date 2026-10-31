# SymFlex FlexPDE 8 engine (`src/flex`)

Pure ES modules, no dependencies; runs in Node 22 and in a browser Web Worker.

```js
import { runFlex, lintFlex } from './src/flex/index.js'
const r = await runFlex(text, { onProgress: msg => {} })
// r = { title, log, errors:[{line,col,msg}], reports:[{label,value,expr}],
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
  (constants, expressions of `t`/`x`/`y`/variables, `f(a,b)=...`, forward references),
  `INITIAL VALUES`, `EQUATIONS` (`v: dt(v) = a`, unlabeled in variable order, vector
  equations, `dt(dt(x))`, residual form `expr` = 0), `CONSTRAINTS`/`EXTRUSION`/... (skipped),
  `BOUNDARIES` (`REGION n ['name']` with region-local `k = ...`, `START ['name'] (x,y)`,
  `LINE TO (..) TO (..)`, `TO CLOSE`/`CLOSE`, `ARC TO (mid) TO (end)`, `ARC(CENTER=..) TO|ANGLE=`,
  `ARC(RADIUS=..)`, `VALUE(u)=`, `NATURAL(u)=`, `LOAD/NEUMANN(u)=`, `POINT VALUE/LOAD` (1D),
  `EXCLUDE`), `TIME a TO b [BY dt]`, `TIME a BY dt TO b`, `FROM ...`, `HALT cond` / `HALT (cond)`
  / `HALT minimum_dt`, `LIMIT`, `MONITORS` (parsed, not output), `PLOTS`/`HISTORIES`, `END`.
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
variable / vector component is one unknown. Steps use FlexPDE's own scheme, calibrated on its
logs: variable-step BDF2 solved by Newton; error `E = max |y - P| / (2 max(threshold, errlim|y|))`
with `P` the quadratic extrapolation of the last three steps; growth <= 1.25x relaxing towards
errlim; rejection above 3*errlim; steps clipped to land on every plot time; HALT tested at the
end of each step (so the halt time is a step end, e.g. the projectile halts at t=3.8). The
start-up mimics FlexPDE 8.01 too, including its first double step that advances only 1/3 of the
true increment (visible in every FlexPDE run, e.g. projectile `vy` is offset by 1.6e-3). Step
counts are within a few percent of FlexPDE's (lab4_07: 8234 vs 8306) and the BDF2 global error
is reproduced (lab3_09 `v(0.5)` 0.001819 vs FlexPDE 0.001785, exact 0.00003).

**FEM mode**: P1 triangles (2D) or segments (1D). Mesh: boundary nodes every h plus a hexagonal
interior lattice, Delaunay-triangulated, h = extent/(2*ngrid) (twice FlexPDE's initial density to
compensate for linear instead of cubic elements). Each equation residual is split into
divergence terms `c*div(V)` (integrated by parts; `del2`, `dxx`, `dyy`, `dxy` are rewritten as
divergences) and source terms; `NATURAL(u)=g` is the outward boundary flux, default natural 0;
`VALUE` replaces the nodal equation. Newton with element-wise finite-difference Jacobians, banded
LU after RCM ordering. Pure-Neumann problems get a vanishing mass term, so the course "New
Problem" template (`div(grad(u))=0`, no BCs) returns u=0 like FlexPDE. Time-dependent PDEs use the
same BDF2 stepper with per-node thresholds.

FlexPDE 8 rules reproduced: `report rx` with a field and no location fails with
"A Scalar Evaluation has encountered a Field value with no Location Specified" at the report
line/column; undefined names give "Undefined Name: NAME" at their position; grammar errors use
FlexPDE's wording ("FlexPDE grammar does not allow '<identifier>' in this location.").

## Accuracy against real FlexPDE 8.01 (`node tests/run_flex_corpus.mjs`)

PASS: lab2_13, notes2_01, notes2_11, notes2_16 (template). ERR-OK: notes2_12 (same error, same
line). NEAR (every value on FlexPDE's trajectory, but some value at the end differs by more than
1e-3 relative because FlexPDE's last step(s) differ from ours): lab1_img120, lab2_11, lab2_14,
lab2_16*, lab2_17, lab2_20*, lab3_04*, lab3_05*, lab3_06*, lab3_09*, lab3_14*, lab3_20*,
lab3_22*, lab4_07, notes1_21, notes2_14, notes2_15 (*: FlexPDE 8 rejects the original script;
we reproduce the error and compare the patched script as the golden generator does).
FAIL: lab1_24, lab1_25 (`errlim=1e-2` close charge encounter: FlexPDE ends at rx=-1.047, we at
-0.976, the exact answer is -0.874; the BDF2 error at that tolerance depends on the exact step
sequence).

Typical differences: halted runs stop one FlexPDE step earlier/later (values at a crossing like
`v` at the apex or `ry` at landing then differ by one step's change); oscillators carry
FlexPDE's BDF2 phase error to within a few percent of itself.

## Known gaps

- Step sequences are not bit-identical to FlexPDE's (its controller and start-up failure test
  are only approximated), so values at a HALT can differ by one step.
- FEM is linear (P1) on a fixed mesh: no adaptive regridding, no cubic elements; nonconforming
  interior region boundaries (regions are assigned per element by centroid); no 3D, no
  cylindrical weighting (`ycylinder` is treated as cartesian), no vector variables in FEM mode,
  no CONSTRAINTS, contact/jump/periodic boundaries, moving meshes, eigenvalues, staged problems,
  TABLE/arrays/matrices.
- Second derivatives are evaluated by finite differences of the P1 field outside the weak form
  (so `dxx(u)` in a definition used for plotting is ~0); terms like `k(x)*div(grad(u))` drop the
  `grad(k)` contribution.
- MONITORS are not output; exports (`EXPORT`, `FILE`, `FORMAT`), `TABLE`, `PRINT` are ignored.
