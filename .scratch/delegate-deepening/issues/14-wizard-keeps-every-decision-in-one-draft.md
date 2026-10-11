# 14 — The setup wizard keeps every decision in one draft

**What to build:** Candidate F, ticket F2 (lane catalog-write). Build this under
`/frontend-design:frontend-design` if that skill is available (ADR 0001), because it
changes `setup_tui.Wizard`'s handlers and the state `view()` reads, though not the
layout.

Give `Wizard` a public `self.draft`:
- `_load` builds it with `whole=not focus` from the `CatalogRead`'s dicts, applies the
  carry proposals in the full wizard, then calls `settle()`. `apply_start_lines` applies
  the lines and calls `settle()` again.
- The carry page toggles through `draft.carry`.
- On the tier pages, the box reads `lane.tier == N` and a tick calls `place(N)`. An
  untick returns the Lane to its start Tier when that Tier is below N; otherwise it calls
  `place(None)` in the full wizard or `place(N-1)` in a focused screen, where Tier 1
  still refuses. Entering page 1 in the full wizard places each unplaced Lane at Tier 1 in
  lane-name order, and enter commits nothing.
- On the review page, sections read `draft.tier_lanes`, J/K calls `place(at=place±1)` and
  1-4 calls `place(at='end')`. `v` and start lines call `apply(parsed['decided'], 'off')`,
  and `p` calls `apply(proposal order, 'keep')`.
- The routing page calls `set_routing` and reads `documents()["routing"]`.
- `made_choice` becomes `not draft.is_settled()`. `rewrite_bench_page` and the meter
  coverage warning read `documents()["lanes"]`.
- The focused confirm rows render `draft.changes()` plus the file and target rows.
  `result()` returns `documents()`. The full wizard commits both documents; a focused
  screen commits only the documents `changes()` touches.
- A rescan builds a new draft from the routing document the Wizard was given; it already
  refuses after any choice.

Delete the five structures, the six materialisations and the Wizard methods listed in the
spec, and delete `tier_lines.unnamed_carried`.

Rewrite all 62 private-state reads in `tests/test_setup_tui.py`, and the one in
`tests/test_tier_proposal.py`, onto `w.view()`, `w.draft` and the then-current public
evidence functions (`published_names` and `carry.decisions(L, rows)`); A1's rebase later
converts the evidence reads to `LaneEvidence`. Update tests 39, 44b and 53 to the new
starting order: Order as read, then lane name, with a Lane ticked onto another Tier at
that Tier's end. Move the written-document checks of 20, 21 and 53 into
`test_catalog_draft.py`, delete 26, and add a case to 75 showing that a tick undone on a
tier page leaves `r` as a rescan. New `setup.main` cases pass `--no-bench` and
`--no-discover`.

Rewrite the wizard paragraph of `references/architecture.md` to state the starting order.
H3 later adds an `epoch_rows` constructor argument on top of this ticket. The Wizard
still takes 18 constructor parameters; record that as a known leftover when this ticket
lands, not a fix in scope.

Spec: `.scratch/delegate-deepening/spec.md` (F. Catalog draft; decisions F.2, F.5, F.6 and F.7)

**Blocked by:** 13 The plain wizard writes the Order it prints

**Status:** ready-for-agent

- [ ] `Wizard` has no `_enabled`, `_assigned`, `_marks`, `_tier_order`, `_line_order`, `_review_order`, `_original_lanes`, `_original_routing` or `_loaded` attribute, and no `current_lanes`, `_final_tier`, `_focused_lanes`, `_meter_coverage`, `_start_key`, `_arrange_review` or `_choices` method.
- [ ] `grep -nE '\b(w|w2|full|focused|fresh|carry_wizard|tier|trip|undone|first|second|plain|pressed|q)\._[a-z]'` over `tests/test_setup_tui.py` and `tests/test_tier_proposal.py` finds nothing, and no test reads `__dict__`.
- [ ] Tests 1a, 1b, 2, 3, 4, 5, 8, 8b, 16, 17, 18, 39b, 48-52, 55-61 and 75-78 pass with the same keys pressed.
- [ ] 39, 44b and 53 assert the new starting order, and the new case in 75 (a tick undone on a tier page is no choice) passes.
- [ ] Frames at 80x24 and 200x50 are unchanged except for the review page's order (tests 33, 40, 54, 65-68 and 72-74 pass unchanged).
- [ ] `tier_lines.unnamed_carried` is gone; `tier_lines` keeps `parse_tier_lines` and `tier_lines_summary`.
- [ ] No code uses a `CatalogDraft` as a dict key or set member.
- [ ] `references/architecture.md` states the starting order: Order as read, then lane name; lines and `p` first in their order; a Lane joining a Tier at its end; undo restores the starting place.
- [ ] `make test` is green on Python 3.9 and on `python3.13`.
