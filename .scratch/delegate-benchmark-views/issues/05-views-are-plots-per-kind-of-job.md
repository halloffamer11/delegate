# 05 — Each View is a set of zoomable plots for one kind of job

**Blocked by:** None. Supersedes 01.

**What to build:** the design the user chose on 2026-10-14 after six prototype rounds: Claude's
plots with Opus 5.5's range table, one live page (`prototypes/claude-v6.src.html`), built into the
real page. The layout and the tier rule are in `spec.md`.

- Python (`scripts/bench_page.py`): `views.json` v2 (four Views, one marked reference);
  `load_views`, `view_boards` (newest version per pair), `display_name` (a Model's name with its
  version, read from its id), `reference_keys` (one name for a Reference model printed two ways);
  each point's `group` and `ref`, each Lane's `label`; the tab row, a shell per View, the theme
  toggle and the palette. `coverage` and the Frontier tab are gone.
- Script (`assets/bench_page.js`): pure `pick`, `viewSeries`, `indexBoard`, `percentile`,
  `viewScore`, `favouredEffort`, `viewTiers` and `cutRanked` (shared with `cutBoard`); `makeViews`
  draws the bar, the plots and the range table with DOM calls only; `bootTheme`; `makeTabs` opens
  on the first View.

**Status:** implemented 2026-10-14 on the branch for this effort. The last box waits on the user.

- [x] One flat row of tabs: each View, All boards, Prices, Numbers; Overall is marked reference.
- [x] A plot per board: a line per Model on a Harness through its efforts, the frontier band,
      box and wheel zoom with shrinking markers and effort labels.
- [x] Click shows one Model or effort, shift-click adds or removes, Clear filters resets; a
      Harness name hides or shows its Lanes.
- [x] Reference models are grey dots, pinnable as named dashed lines, never ranked.
- [x] Names carry their version (Fable 5.1, Astra 6, Opus 5.5), read from the id, never a list.
- [x] The range table: dots per measured effort per board, mean percentile, relative cost, tier
      now and here, favoured effort.
- [x] Light by default, with a toggle kept in the browser; the validated harness palette.
- [x] `views.json` names no model, harness or effort.
- [x] Tests: `tests/test_bench_page.py` V1 to V18; `make test` passes.
- [ ] The user opens the page from `delegate global` with `o` and confirms the Views.

## Implemented, 2026-10-14

Rendered with `prototypes/render_sample.py` (the frozen catalog in
`tests/fixtures/refresh-2026-09-22/` plus two Kiro Lanes, against the repo's accepted AA, tbench
and swerb rows) and checked in Chromium at desktop and phone widths, light and dark, with a
select, a zoom and the All boards tab: no console errors and no sideways scroll.
