# 02 — The benchmark page is one screen

**What to build:** `bench_page.render` fills `assets/bench_page.html` (the round-2 Opus prototype, productionized): plot of one board beside the resizable matrix panel, the score axis fitted to the board, drag-box zoom with a Reset button, a board list grouped by category, harnesses in use preselected, and the system's light or dark theme.

Spec: `.scratch/delegate-tui-polish/spec.md`

**Blocked by:** None — can start immediately.

**Status:** implemented 2026-11-01, on `claude/project-thread-5eiff5`. The last box waits on the user.

- [x] `assets/bench_page.js` and the long page's evidence tables are gone; `plot_data` adds each board's `category`.
- [x] AutomationBench and MMMU-Pro fill the plot's height (checked in Chromium on the user's catalog).
- [x] A drag zooms, Reset zoom returns, and a click on a dot still steps its tier.
- [x] `test_bench_page.py` covers the data and checks the page's script parses under node.
- [ ] The user opens the page with `o` and confirms hover, zoom and the panel width.
