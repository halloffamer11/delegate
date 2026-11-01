# 01 — The wizard sets tiers on one matrix

**What to build:** Replace the four tier pages with one tiers page: models by efforts, grouped by harness, models dearest first; space steps a lane's tier through 1-4 and off, 0-4 set it; `[`/`]` switch the board the legend describes; `h` shows the harnesses with no carried lane.

Spec: `.scratch/delegate-tui-polish/spec.md`

**Blocked by:** None — can start immediately.

**Status:** implemented 2026-11-01, on `claude/project-thread-5eiff5`. The last box waits on the user.

- [x] `tier_matrix.py` gives families, class order, harnesses in use and board order.
- [x] `setup_tui.py` draws the tiers page, and `--screen tiers` (or `tier1`-`tier4`) opens it.
- [x] `test_setup_tui.py` covers the matrix, the keys, board order and hidden harnesses.
- [ ] The user runs `delegate global` on the Mac and checks the page reads well at 80x24.
