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

**Status:** landed 2026-10-11 (cab402d, with the review fixes in "delegate-deepening F: review fixes"). `setup_tui.Wizard` keeps every carry, Tier, Order and routing decision in one public `self.draft` (`catalog_draft.CatalogDraft`, `whole=True` in the full wizard, `whole=False` on a focused screen); `result()` is `draft.documents()`, a focused save commits only the documents `draft.changes()` touches, and the five structures, their materialisations and `tier_lines.unnamed_carried` are gone. Verified by test_setup_tui 39, 44b and 53 on the new starting order, the new 75 case (a tick undone on a tier page leaves `r` a rescan), the two test_catalog_draft cases that took over 20, 21 and 53's written-document checks, and all 140 test_setup_tui cases with no private read; no box is open.

- [x] `Wizard` has no `_enabled`, `_assigned`, `_marks`, `_tier_order`, `_line_order`, `_review_order`, `_original_lanes`, `_original_routing` or `_loaded` attribute, and no `current_lanes`, `_final_tier`, `_focused_lanes`, `_meter_coverage`, `_start_key`, `_arrange_review` or `_choices` method.
- [x] `grep -nE '\b(w|w2|full|focused|fresh|carry_wizard|tier|trip|undone|first|second|plain|pressed|q)\._[a-z]'` over `tests/test_setup_tui.py` and `tests/test_tier_proposal.py` finds nothing, and no test reads `__dict__`.
- [x] Tests 1a, 1b, 2, 3, 4, 5, 8, 8b, 16, 17, 18, 39b, 48-52, 55-61 and 75-78 pass with the same keys pressed.
- [x] 39, 44b and 53 assert the new starting order, and the new case in 75 (a tick undone on a tier page is no choice) passes.
- [x] Frames at 80x24 and 200x50 are unchanged except for the review page's order (tests 33, 40, 54, 65-68 and 72-74 pass unchanged).
- [x] `tier_lines.unnamed_carried` is gone; `tier_lines` keeps `parse_tier_lines` and `tier_lines_summary`.
- [x] No code uses a `CatalogDraft` as a dict key or set member.
- [x] `references/architecture.md` states the starting order: Order as read, then lane name; lines and `p` first in their order; a Lane joining a Tier at its end; undo restores the starting place.
- [x] `make test` is green on Python 3.9 and on `python3.13`.

## Landed, 2026-10-11

Commits: `cab402d` ("delegate-deepening 14: The setup wizard keeps every decision in one
draft"), then the review fixes in "delegate-deepening F: review fixes".

What shipped:

- `setup_tui.Wizard` keeps one public `self.draft`. `_load` builds it from the launch
  documents (routing with the default Classes) with `whole=not focus`, carries the carry
  proposals in the full wizard, then calls `settle()`; `apply_start_lines` applies the lines
  through `draft.apply(parsed["decided"], "off")` and settles again. `made_choice()` is
  `not draft.is_settled()`.
- The carry page toggles through `draft.carry`. A tier page's box reads
  `lane.tier == N`; a tick places the Lane at once, at that Tier's end. An untick returns it
  to its start Tier when that Tier is lower, and otherwise unplaces it (full wizard) or moves
  it one Tier down (focused screen, where Tier 1 still refuses). Entering tier 1 in the full
  wizard places each Lane still unplaced at Tier 1 in lane-name order; enter decides nothing.
- The review page reads `draft.tier_lanes(4..1)`; J/K place the Lane at `place ± 1` and 1-4
  at `"end"`, the cursor following it. `v` applies lines with `"off"`, `p` applies the
  proposal order with `"keep"`. The routing page edits through `draft.set_routing` and reads
  `documents()["routing"]`; `rewrite_bench_page` and the meter warning read
  `documents()["lanes"]`.
- `result()` is `draft.documents()` (`{"lanes", "routing"}`); `setup.main` commits it whole
  for the full wizard, and for a focused screen only the documents
  `setup_tui.changed_documents(draft.changes())` names (plus an absent one on a first run, as
  before). The focused confirm rows render `draft.changes()` plus the file and target rows.
- A rescan builds a new Draft from the routing the Wizard was given, and is refused after
  any carry, Tier, Order or routing decision.
- Deleted: the attributes `_enabled`, `_assigned`, `_marks`, `_tier_order`, `_line_order`,
  `_review_order`, `_original_lanes`, `_original_routing`, `_loaded` and `routing_doc`;
  the methods `current_lanes`, `_final_tier`, `_focused_lanes`, `_meter_coverage`,
  `_start_key`, `_arrange_review`, `_choices`, `_flatten_review`, `_move_in_tier`,
  `_move_to_tier`, `_place`, `_settle`, `_toggle_enabled` and `_set_meters`; and
  `tier_lines.unnamed_carried`.
- Docs: `references/architecture.md` says the Wizard keeps a Draft, states the starting
  order (the Order as read, then lane name; lines and `p` first in their order; a Lane
  joining a Tier at its end; undo restores the starting place) and the tick, untick and
  tier 1 rules, says the `o` page and the focused confirm rows come from the Draft, and that
  a rescan is refused after any decision. `CONTEXT.md`'s Order and Draft entries were
  already true and are unchanged.

Verified:

- Red first: on the base the rewritten tests failed on the missing `draft` attribute and
  the tuple `result()`, and 39, 44b and 53 on the benchmark starting order.
- `tests/test_setup_tui.py`, 140 cases, none reading private state or `__dict__`. 39, 44b
  and 53 assert literal lists in the new starting order. 44b shows `sol-high@codex` ticked
  onto Tier 4 at its end after the Fable Lanes, and `fable-low@claude` at the end of Tier 3.
  53 shows luna, grok and sol by their Order, then fable, flash and terra by lane name. The
  new 75 case unticks and reticks the Lane under the cursor on tier 4, then unticks a marked
  Lane, looks at tier 3, comes back and ticks it again; `r` still rescans. Breaking the
  tick's return to the starting place fails it. 20's record and 26 are deleted, and 21 now
  checks only the carry page.
- `tests/test_catalog_draft.py`, 18 cases. The gap-closing case adds 53's fixture: all
  Lanes at Tier 1, Orders 1, 2 and 7, written 1 to 6 by Order then lane name. The whole-save
  case adds 21's check: a Lane given `enabled: false` and switched on takes back its place
  and loses the key. 20's switched-off check and 26's round trip were already the whole-save
  and "no decision writes the catalog back" cases.
- `tests/test_tier_proposal.py` reads `draft.tier_lanes` and `result()["lanes"]`, and
  `tests/test_bench_page.py` reads `draft.lane(name).carried`. test_setup's D3 focused-save
  cases pass unchanged.
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and
  3.13.16: every file ok, the dashboard test included.

Deviations:

- The `frontend-design:frontend-design` skill was not in this session's skill list, so it
  was not loaded. Visible changes stay to what the ticket names: the review page's starting
  order and the tick, untick and tier 1 placement.
- Tests 73 and 74 render the same frames. They change only in how they reach state: 73
  counts settings off the view, and 74 turns meters off through `w.draft.set_routing`,
  because there is no `routing_doc` left to mutate.
- Test 64 now presses real keys. 64c ticks `grok46-high@grok` on the tier 4 page and reads
  the rewritten page, where it used to read `current_lanes()`.
- 77 and 78 compare the public evidence and a state tuple, plus `w.draft == fresh.draft`,
  in place of private attributes and `__dict__`. The Wizard's own failed-rescan restore
  still copies `__dict__`.
- Test 47's dropped Lanes come from `CatalogDraft.apply`, so it expects them in catalog
  order (grok, luna, flash).
- The focused confirm rows follow `changes()` order, so a focused routing screen that
  changes both lists margin before gate. Nothing else on the page moves.
- `setup_tui.changed_documents(changes)` is new: `setup.main` and the confirm rows share it.
- An off Lane keeps its start Tier (F.5), so a Lane that lines place and then switch off
  keeps the lines' Tier.
- A routing edit now refuses a rescan (F.7), where the old Wizard allowed one.
- Known leftover: the Wizard still takes 18 constructor parameters. H3 adds `epoch_rows`
  on top of that.

Review fixes ("delegate-deepening F: review fixes"):

- The focused half of decision F.6 had no test: no case unticked a Lane ticked onto a
  focused Tier, and none pressed space on a focused tier 1, before or after this ticket.
  New test_setup_tui 61b: on `--screen tier3` over a catalog with luna and flash numbered
  in Tier 1, luna ticked onto Tier 3 joins it after sol, and unticked returns to Tier 1
  before flash, so the confirm page says nothing will be written and `y` writes the
  catalog back; on `--screen tier1` an untick is refused and decides nothing. Making a
  focused untick always go one Tier down, or dropping the tier 1 refusal, fails it.
- `references/architecture.md`'s last focused-setup sentence said an unmark always moves
  a Lane one Tier down; it now names the return to the lower start Tier as well.
