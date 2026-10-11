# 15 — The confirm page lists exactly what save writes

**What to build:** Candidate F, ticket F3 (lane catalog-write, its last ticket). Build
this under `/frontend-design:frontend-design` if that skill is available (ADR 0001),
because it changes the confirm page view. D3 owns the focused screen's start (no
generation refresh) and its failing-first test; this ticket does not repeat them.

Write the failing test first: `test_setup_tui.py` "81 the confirm page lists each carried
Lane with the Order y writes". It walks the sample catalog, presses J once on the review
page, and checks that each Lane row's value equals `result()`'s tier and order.

Then fix it. On the full confirm page, each Lane line's value becomes
`setup_tui.placement_text(lane)`, which reads "tier N, order M" for a carried Lane and
"tier N" for an off Lane. It comes from `draft.documents()["lanes"]`, one line per Lane,
with the carry column unchanged. `setup.confirm_and_write` prints the same
`placement_text`. In `handle`, the confirm-page and routing-page cursor bounds come from
the same row builders the view uses.

Add one assertion on top of D3's focused case: on a focused screen, the confirm page's
change rows equal `draft.changes()`.

Spec: `.scratch/delegate-deepening/spec.md` (F. Catalog draft; decision F.3)

**Blocked by:** 14 The setup wizard keeps every decision in one draft; 11 A focused setup screen saves only the change made on it

**Status:** ready-for-agent

- [ ] Test 81 fails before this ticket (value "tier 2" with no order) and passes after.
- [ ] On a focused screen (refresh-2026-09-22 fixtures, `--fixture-dir`, `--no-bench`, `--screen tier3`, one Lane unticked, under a temporary `HOME`), the confirm page's change rows equal `draft.changes()`.
- [ ] At 80x24 every confirm row reads whole and the list can be read to its end (tests 19, 33 and 74 pass); at 200x50 the layout is unchanged except for the order text.
- [ ] `--plain`'s confirm listing and the TUI confirm page print the same placement text for every Lane.
- [ ] `handle` no longer contains its own row count for the confirm or routing page.
- [ ] `make test` is green on Python 3.9 and on `python3.13`.
