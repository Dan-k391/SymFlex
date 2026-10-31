---
name: symflex-test
description: Run SymFlex test suites (Maple corpus vs real-Maple goldens, FlexPDE corpus vs real-FlexPDE goldens, unit tests, Pyodide parity) and drive a fix loop. Use when asked to test, check regressions, or fix engine failures.
---

# Running SymFlex tests

All commands run from the repo root (`D:/Maple/SymFlex`).

| Suite | Command | Notes |
|---|---|---|
| Everything | `npm test` | wraps the ones below |
| Maple unit | `python -m pytest tests/unit_py -q` | parser, evaluator, printer, comparator |
| Maple corpus | `python tests/run_maple_corpus.py [filter...] [-v] [--jobs 6]` | compares with `corpus/golden/*.json`; details in `tests/out/maple_report.json` |
| FlexPDE unit | `node --test tests/flex/*.test.mjs` | |
| FlexPDE corpus | `node tests/run_flex_corpus.mjs` | PASS / NEAR (within one time step) / FAIL |
| Browser parity | `node tests/pyodide_parity.mjs` | needs `npm run setup` first |

## Fix loop

1. Run the corpus suite, read the first failing statement of each FAIL (`-v <case>` shows golden vs ours).
2. Find the owning module: `py/symflex_maple/builtins/{algebra,calculus,ode,linalg,plots,core}.py`, `printer.py`/`evaluator.py`, or `src/flex/`.
3. When unsure what Maple does, ask the real one:
   `"D:/Maple/Installed/bin.X86_64_WINDOWS/cmaple.exe" -q file.mpl` (start the file with `interface(prettyprint=0, screenwidth=infinity):`).
4. Fix the general behavior (students type variations), add a unit test, re-run the filtered cases, then the full suite to catch regressions.
5. Engine code must stay pure Python + sympy/mpmath (it runs in Pyodide): no threads, signals or subprocess.

If golden and ours are genuinely equivalent but reported as FAIL, fix `tests/maple_compare.py`, not the engine.
