# SymFlex

SymFlex is a Jupyter-style web notebook that emulates **Maple 2024** (1-D input) and **FlexPDE 8**
for the McMaster EP 2CD4 dynamics course: kinematics, Newton's laws with friction, rockets and drag
(nonlinear ODEs), damped and driven oscillators, rigid-body planar kinetics, energy and Lagrange.

**Try it:** https://dan-k391.github.io/SymFlex/ (GitHub Pages can't send cross-origin isolation headers,
so Stop restarts the Maple kernel there instead of interrupting it.)

Everything runs in the browser and works offline:

- **Maple cells** run a Python/SymPy reimplementation of Maple (`py/symflex_maple`) inside Pyodide in a
  web worker. All Maple cells of a notebook share one session, like a Maple worksheet.
- **FlexPDE cells** run a JavaScript FlexPDE engine (`src/flex`) in its own worker.
- **Text cells** are Markdown with `$...$` / `$$...$$` math.

Real Maple and FlexPDE are only used to produce golden outputs for the test suites. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the components and their contracts.

## Setup

Requires Node 22+ and Python 3 (for the build scripts).

```sh
npm install
npm run setup      # vendors Pyodide + sympy/mpmath wheels into public/pyodide, zips the engine, builds examples
npm run dev        # http://localhost:5173
```

`npm run build` writes a static site to `dist/` (serve it with `npm run preview`, or any static server;
set the COOP/COEP headers from `vite.config.js` to enable interrupts). All paths are relative, so `dist/`
can be served from any sub-path (e.g. GitHub Pages). The first load downloads about 20 MB (Pyodide +
SymPy) from your own server; later loads come from the browser cache.

While `npm run dev` is running, editing files under `py/` re-zips the engine and reloads it in the
running kernel once it is idle (kernel state is reset).

## Features

- Notebook: Maple, FlexPDE and text cells; execution counter `[n]`; run cell / run all / run above /
  run below; interrupt; restart (and run all); add, move, duplicate, delete (with undo), change type,
  collapse output, clear outputs.
- Multiple notebooks, autosaved to browser storage; open/save `.symflex.json`; import `.mpl`, `.pde`,
  `.txt` and Maple `.mw` worksheets (drag-and-drop works too); export `.mpl`, `.pde`, static `.html`.
- Outputs: Maple math rendered with KaTeX and centred like Maple's GUI (hover to copy the 1-D text);
  print output, warnings (amber) and errors (red); Plotly plots for every PlotSpec type: 2-D curves and
  points (log axes, parametric), 3-D curves, surfaces and contours from grids or FEM meshes, vector
  fields, animations with a play slider.
- FlexPDE outputs: progress while running, reports table and final values, all plots, run log, and errors
  with line numbers (click to jump; also shown as squiggles in the editor).
- Editor (CodeMirror 6): Maple and FlexPDE syntax highlighting; autocomplete for about 260 Maple
  functions with signature, docs and examples, packages after `with(`, members after `plots:-`,
  options inside calls (`numeric`, `output = listprocedure`, `color =`, `labels =` ...), names from the
  notebook and from the kernel; FlexPDE sections, functions, SELECT controls (from the manual), plot
  commands and your own definitions; hover docs; signature hints; bracket matching and auto-close;
  search; comment toggle; lint for unbalanced brackets/strings (Maple) and the FlexPDE linter.
- Sidebar: notebooks, course examples (Labs 1-5, Notes 1-5, searchable; click to open as a notebook),
  and a searchable Maple/FlexPDE function reference with "insert example".
- Light and dark themes, keyboard-first, accessible labels and focus order.

## Keyboard shortcuts

Press `H` or `?` in command mode for the full list.

| Keys | Action |
| --- | --- |
| `Shift+Enter` | run cell, select next |
| `Ctrl+Enter` | run cell in place |
| `Alt+Enter` | run cell, insert below |
| `Esc` / `Enter` | command mode / edit mode |
| `↑` `↓` (`K` `J`) | select cell (command mode) |
| `Alt+↑` `Alt+↓` | move cell |
| `A` / `B` | insert cell above / below |
| `D`,`D` / `Z` | delete cell / undo delete |
| `Y` / `F` / `M` | Maple / FlexPDE / text cell |
| `O` | toggle output |
| `I`,`I` / `0`,`0` | interrupt / restart kernel |
| `Ctrl+Space`, `Ctrl+/`, `Ctrl+F` | autocomplete, toggle comment, search (edit mode) |
| `Ctrl+S` | save |

## Project layout

```
index.html, vite.config.js      app entry; dev/preview headers; py/ hot-reload plugin
src/ui/                         notebook UI
  main.js                       shell: menus, files, theme, kernel status
  notebook.js                   cells, command/edit modes, execution queue
  editor.js                     CodeMirror setup
  lang/                         Maple + FlexPDE languages, docs data, completion/hover/lint
  output.js, plot.js            output and PlotSpec rendering
  store.js, io.js               notebook model, persistence, import/export
  kernel.js, flexWorker.js      worker clients; FlexPDE worker
  sidebar.js, markdown.js, styles.css
src/maple/                      Pyodide worker + environment-independent kernel core
src/flex/                       FlexPDE engine
py/symflex_maple/               Maple engine
scripts/                        fetch_pyodide.mjs, bundle_py.mjs, build_examples.py, corpus tools
corpus/                         course code (raw, cleaned cases, golden outputs)
tests/                          engine test runners
```

## Testing

```sh
npm test           # UI + kernel unit tests, FlexPDE unit tests, Maple and FlexPDE corpus runners, Pyodide parity
npm run test:ui    # only the UI / kernel tests (node --test)
node tests/pyodide_parity.mjs [filters...] [--all]   # Maple engine in Pyodide vs CPython
```

The parity test runs corpus cases through the engine in Pyodide (offline, as the browser worker does)
and in CPython, and reports SAME / NEAR (float round-off) / HASHDEP (output depends on the Python hash
seed, an engine nondeterminism) / DIFF, with the Pyodide load time and per-case times. The browser
kernel fixes `PYTHONHASHSEED=0`, so a notebook gives the same output on every reload.

`npm test` runs every suite that exists, skipping missing ones, and prints a summary. The kernel test
boots the real Pyodide under Node from `public/pyodide`, so run `npm run setup` first.
