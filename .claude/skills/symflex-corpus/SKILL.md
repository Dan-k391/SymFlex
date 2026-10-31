---
name: symflex-corpus
description: Add or regenerate SymFlex test cases from course material (PDF notes, lab .docx) and regenerate golden outputs with the real Maple 2024 / FlexPDE 8. Use when new course content arrives or a case/golden must change.
---

# Corpus pipeline

Course files live in `D:/Maple/Course Content`. Pipeline (repo root `D:/Maple/SymFlex`):

1. `python scripts/extract_corpus.py "D:/Maple/Course Content"` — pulls Courier-New code blocks into `corpus/raw/<source>/NN.mpl|.pde` + `index.json` (never hand-edit raw).
   New PDFs: add their hash → topic name to `PDF_NAMES` in that script.
2. `python scripts/prep_media.py` — output images (WMF→PNG) to `corpus/media/`, PDF page renders to `corpus/pages/` (gitignored; for visual checks).
3. Clean each raw block into `corpus/cases/<source>/<source>_NN.mpl|.pde`:
   - line 1 `# SOURCE: <source> block NN (page|para N) - <context>`; optional `# NOTE:`, `# EXPECT: error`, `# DEPENDS: <case>` (prepend the earlier code it needs).
   - only fix extraction artifacts (prompts `> `, wrapped lines, smart quotes); keep the author's code otherwise.
   - verify with real cmaple / FlexPDE (run FlexPDE on a copy under `.work/`, it writes `<name>_output/`).
4. Goldens: `python scripts/gen_golden_maple.py [case paths]` and `python scripts/gen_golden_flex.py [case paths]` (`--force` to redo).
   FlexPDE-6 style bare `report X` cases are re-run with `report val(X,pt)` and marked `"patched"`.
5. `python scripts/build_examples.py` refreshes the app's Course examples list.
6. Run the `symflex-test` skill's suites and commit cases + goldens together.
