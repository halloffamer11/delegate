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

**Status:** landed 2026-10-11. The full confirm page gives each Lane `setup_tui.placement_text`, read from `draft.documents()["lanes"]` (`tier N, order M`, or `tier N` for an off Lane), and `--plain`'s confirm listing prints the same text; `handle` takes the confirm and routing cursor bounds from the row builders the view draws. Verified by test_setup_tui 81, the test_setup case "plain and the TUI confirm print the same placement for every Lane", and the focused-rows assertion added to D3's focused tier case; no box is open.

- [x] Test 81 fails before this ticket (value "tier 2" with no order) and passes after.
- [x] On a focused screen (refresh-2026-09-22 fixtures, `--fixture-dir`, `--no-bench`, `--screen tier3`, one Lane unticked, under a temporary `HOME`), the confirm page's change rows equal `draft.changes()`.
- [x] At 80x24 every confirm row reads whole and the list can be read to its end (tests 19, 33 and 74 pass); at 200x50 the layout is unchanged except for the order text.
- [x] `--plain`'s confirm listing and the TUI confirm page print the same placement text for every Lane.
- [x] `handle` no longer contains its own row count for the confirm or routing page.
- [x] `make test` is green on Python 3.9 and on `python3.13`.

## Landed, 2026-10-11

What shipped:

- `setup_tui.placement_text(lane)`: `tier N, order M` for a carried Lane record with an
  Order, `tier N` for an off Lane (`enabled: false`) or a carried one without an Order.
- `Wizard._confirm_rows()` is the confirm page's one row list: `_focus_rows()` on a focused
  screen; in the full wizard each Lane from `draft.documents()["lanes"]` with
  `placement_text` as its value (the carry column unchanged), then each Class Range,
  margin, gate, meters and the two files. `view()` draws it and `handle` bounds the cursor
  with its length.
- The routing page's `handle` reads the setting under the cursor from `_routing_settings()`,
  the list `_routing_rows` draws: its length bounds the cursor, and the kind (`floor`,
  `ceiling`, `margin`, `gate`, `meters`) decides the edit. The index arithmetic over
  `len(self.classes)` is gone.
- `setup.confirm_and_write` prints `<lane>: <placement_text>`, with `, off` after an off
  Lane as before.
- Docs: `references/architecture.md` says the confirm page lists each lane as `y` writes it,
  through `placement_text`, which `--plain` prints too, and that both cursors run over the
  rows the page draws. `CONTEXT.md`'s Draft entry ("the confirm page lists it") was already
  true and is unchanged.

Verified:

- Red first: test_setup_tui 81 failed on the base with every value read `tier N` and no
  order (`grok46-high@grok: tier 2` beside `result()`'s (2, 2)). It walks the sample
  catalog with flash switched off, presses J on grok in Tier 2, and asserts the literal
  values (`tier 2, order 2` for grok, `tier 1` for the off flash) and the literal tiers and
  orders `result()` writes.
- The new test_setup case "plain and the TUI confirm print the same placement for every
  Lane" runs `--plain` and the TUI in process on the same numbered sample catalog and the
  same `--tiers-from` lines (one Lane off), declines both, and asserts both list the literal
  placements, `--plain` adding `, off`. It failed on the base on the TUI's side.
- D3's "a focused tier screen saves only the change made on it" now also asserts that the
  focused confirm page's change rows are `draft.changes()`, one `<lane>.<field>  old → new`
  row each, followed by the one lanes.json file row, and that they name exactly the fields
  the save changed on disk. It passed on the base, since ticket 14 already built those rows
  from `changes()`; dropping one change from `_focus_rows` fails it.
- Frames: the confirm page rendered at 80x24 and 200x50, on the base and after, differ only
  in the order text. Tests 19, 33, 40, 74 and every other test_setup_tui case pass; the
  routing handler's rewrite keeps tests 6, 13, 57 and 80 green with the same keys.
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and
  3.13.16: every file ok, the dashboard test included.

Deviations:

- The `frontend-design:frontend-design` skill was not in this session's skill list, so it
  was not loaded. The one visible change is the confirm page's Order text, as the ticket
  names.
- The ticket asked for test 81 and one focused assertion; a third case in test_setup checks
  the box that `--plain` and the TUI print the same placement text.
- `--plain` no longer prints an Order on an off Lane. A focused-scope save keeps an off
  Lane's record as given, so a catalog that already held `enabled: false` with an `order`
  used to print `tier N, order M, off`; it now prints `tier N, off`, as the TUI does.
- At 80 places the item column's 24-place cap still cuts `classes.mechanical.ceiling`, as on
  the base; every Lane value and path reads whole. That cap is outside this ticket.
