# 01 — The benchmark page is flat views with a Frontier tab

**Blocked by:** None — can start immediately.

**What to build:** the layout in `spec.md`. `assets/views.json` with six Views;
`bench_page.load_views`, `view_boards` and `coverage`; the tab row and one section per View in
`render`; `heldTiers`, `cutBoard` (shared with `sensitivity`), `viewTiers`, `viewColumns`,
`coverageCell`, `drawFrontier`, `drawView` and `makeTabs` in `assets/bench_page.js`.

**Status:** implemented 2026-10-13 on the branch for this effort. The last box waits on the user.

- [x] One flat row of tabs: Frontier, each View, All boards, Prices, Numbers.
- [x] A View names its board without a version and draws the newest one.
- [x] The Frontier matrix has one row per Model on a Harness, so the same Model on two
      Harnesses is two rows with the same measurements and their own Lanes.
- [x] Each coverage cell shows the measured efforts and rings the efforts a carried Lane runs.
- [x] Each View lists its four tiers best first; the Frontier lists each View's tier and the Net tier.
- [x] `views.json` names no model, harness or effort.
- [x] Tests: `tests/test_bench_page.py` V1 to V11; `make test` passes.
- [ ] The user opens the page from `delegate global` with `o` and confirms the six Views.

## Implemented, 2026-10-13

Built and screenshotted on the frozen catalog in `tests/fixtures/refresh-2026-09-22/` with two
Kiro Lanes added, against the repo's accepted AA, tbench and swerb rows.
