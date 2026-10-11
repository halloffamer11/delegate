# 13 — The plain wizard writes the Order it prints

**What to build:** Candidate F, ticket F1 (lane catalog-write, after all of D). Add
`agents/skills/delegate/scripts/catalog_draft.py` with `CatalogDraft`, `LaneDecision` and
`Change`, using the full interface from the spec (`carry`, `place`, `apply`,
`set_routing`, `settle`, `is_settled`, `lane`, `tier_lanes`, `documents`, `changes` and
`__eq__`). `documents()` returns `{"lanes": ..., "routing": ...}`, keyed by
`catalog_commit.DOCUMENTS` names. `__eq__` sets `__hash__` to None, so a draft is never a
dict key or set member.

Add `catalog.carried_in_tier(lanes, tier)` as the one tie-break: by Order, with unordered
Lanes after the ordered ones, then by lane name. Route `catalog_edit._plan_set` and
`_plan_order` and `catalog._effective_lanes` through it, and delete
`catalog_edit._carried_in_tier`.

Migrate `setup.py --plain` onto a `CatalogDraft` built from D's launch `CatalogRead`
(`read.lanes`, and `read.routing` with the default Classes added), `whole=False`:
- The `--tiers-from` branch calls `draft.apply(parsed['decided'], 'off')` and prints
  `tier_lines_summary(parsed, dropped)`.
- `ask_lanes(lanes_doc, draft)` keeps the same prompts and calls `draft.place` for each
  Lane.
- `ask_routing(draft)` calls `set_routing`, so the meters default rule lives only in the
  draft.
- `show_bench` reads `draft.documents()`.
- `confirm_and_write(draft, read)` prints each Lane's line from `draft.documents()` and
  calls `catalog_commit.commit(read, draft.documents())`, with no `refresh` or `targets`
  parameter, since D's commit owns Agent files and the queue. F3 moves the printed text
  into `setup_tui.placement_text`.

Delete `tier_lines.apply_tier_lines_to_doc` and `write_order_from_lines`, and move
`test_bench_page.py` 35.4 onto `CatalogDraft.apply`. Write `tests/test_catalog_draft.py`
with every interface case listed in the spec, and add a `carried_in_tier` test to
`test_catalog.py`.

Write the failing test first: `test_setup.py::case_a_prompted_tier_change_moves_the_lane_to_the_end_of_its_new_tier`.
Its fixture is the sample catalog with every carried Lane numbered in its Tier, and its
answers move `terra-high@codex` from Tier 2 to Tier 3. It runs with `--no-bench` and
`--no-discover` under a temporary `HOME`.

`CONTEXT.md`'s Draft entry and its sharpened Order entry were added with the spec; keep
them true to what ships. Add a `catalog_draft.py` entry to `references/architecture.md`.
No TUI view changes in this ticket.

Spec: `.scratch/delegate-deepening/spec.md` (F. Catalog draft; decisions F.1, F.2, F.3 and F.5)

**Blocked by:** 10 Agent files and the model queue follow every catalog commit; 11 A focused setup screen saves only the change made on it; 12 catalog set and the dashboard write through the one commit (lane order: all of D before F)

**Status:** landed 2026-10-11. `catalog_draft.CatalogDraft` holds `--plain`'s decisions and its `documents()` go whole to `catalog_commit.commit`, so a prompt that moves a Lane to another Tier puts it at that Tier's end and the listing prints the Order written; `catalog.carried_in_tier` is the one tie-break. Verified by test_setup's `case_a_prompted_tier_change_moves_the_lane_to_the_end_of_its_new_tier` (red on the base first), the eighteen cases of the new `tests/test_catalog_draft.py`, test_catalog 22.1 and test_bench_page 35.4; no box is open.

- [x] `case_a_prompted_tier_change_moves_the_lane_to_the_end_of_its_new_tier` fails before this ticket (terra written 3/1 beside sol 3/1, grok left at 2/2) and passes after: terra 3/2, sol 3/1, grok 2/1, and stdout has "terra-high@codex: tier 3, order 2".
- [x] `tests/test_catalog_draft.py` exercises every entry point only through the interface and runs under `make test`.
- [x] `--plain` with default answers still writes the sample catalog byte for byte (`case_all_harnesses_write_canonical_samples`), and `--tiers-from` still writes the lines' order (`case_tiers_from_applies_the_page_lines`).
- [x] `confirm_and_write` takes `(draft, read)`, commits through `catalog_commit.commit`, and has no `refresh` or `targets` parameter.
- [x] `tier_lines.apply_tier_lines_to_doc`, `tier_lines.write_order_from_lines` and `catalog_edit._carried_in_tier` are gone, and nothing imports them.
- [x] `catalog set`, `catalog order` and Project order tests in `test_catalog.py` pass unchanged.
- [x] `CONTEXT.md`'s Draft and Order entries match what shipped, and `references/architecture.md` names `catalog_draft.py` and what it owns.
- [x] `make test` is green on Python 3.9 (`$(uv python find 3.9)`) and on `python3.13`.

## Landed, 2026-10-11

What shipped:

- `scripts/catalog_draft.py`: `CatalogDraft(lanes_doc, routing_doc, whole=)` with
  `LaneDecision` and `Change`, the whole interface from the spec: `carry`, `place` (`at`
  None, an int clamped to the Tier's places, or `"end"`; `tier=None` unplaces), `apply`
  (`unnamed="off"` returns the carried Lanes it switched off; `"keep"` keeps the rest
  after the named ones), `set_routing` (the meters-on rule: no key where the catalog had
  none), `settle`, `is_settled`, `lane`, `tier_lanes`, `documents()` (`{"lanes",
  "routing"}`, keyed by `catalog_commit.DOCUMENTS` names), `changes()` and `__eq__` (with
  `__hash__ = None`). It deep-copies what it is given, validates nothing, and raises
  `KeyError` for an unknown Lane or Class and `ValueError` for a bad Tier, `at`,
  `unnamed`, pair value or routing key, before changing anything.
- `catalog.carried_in_tier(lanes, tier)`: by Order, a Lane without one after every Lane
  with one, ties by lane name, off Lanes skipped. `catalog_edit._plan_set` (through
  `_append_order_in_tier`) and `_plan_order`, and `catalog._effective_lanes` call it;
  `catalog_edit._carried_in_tier` is deleted.
- `setup.py --plain` builds one draft with `whole=False` from the documents
  `load_or_propose` takes from the launch Catalog read (`read.lanes`, or the sample on a
  first run, with the in-memory generation refresh; `read.routing` with the default
  Classes). `--tiers-from` calls `draft.apply(parsed["decided"], "off")` and prints
  `tier_lines_summary(parsed, dropped)`. `ask_lanes(lanes_doc, draft)` keeps its prompts
  and places each Lane, defaulting to `draft.lane(name).tier`; `ask_routing(draft)` sets
  each answer on the draft; `show_bench(args, draft, rows=)` reports on
  `draft.documents()["lanes"]`; `confirm_and_write(draft, read)` prints each Lane from
  `draft.documents()` and commits those documents with `catalog_commit.commit(read, ...)`.
- `tier_lines.apply_tier_lines_to_doc` and `write_order_from_lines` are deleted;
  `tier_lines` keeps the parser, `unnamed_carried` (F2 deletes it) and the summary.
- Docs: `references/architecture.md` gains the `catalog_draft.py` entry, says the Draft
  applies tier lines, and that a `--plain` prompt moving a carried lane numbers the tiers
  it left and joined. `CONTEXT.md`'s Draft entry names routing decisions too, and the
  Order entry names who numbers unordered lanes by lane name (setup's Draft, `catalog set`,
  `catalog order`) rather than setup as a whole, since the TUI review page still starts
  unordered lanes in benchmark order until F2.

Verified:

- `tests/test_setup.py`, new: `case_a_prompted_tier_change_moves_the_lane_to_the_end_of_its_new_tier`
  (`--plain --no-bench --no-discover` under a temp `HOME`, the sample with every carried
  Lane numbered). On the base it failed as the spec says: terra written 3/1 beside sol 3/1,
  grok left at 2/2, and the listing printed `terra-high@codex: tier 3, order 1`. Now terra
  3/2, sol 3/1, grok 2/1, and stdout has `terra-high@codex: tier 3, order 2`.
- `tests/test_catalog_draft.py`, new, eighteen cases through the interface only: no
  decision writes the catalog back (byte for byte with `whole=False`, places only with
  `whole=True`); a Tier as read numbered by Order then name with gaps closed (orders 7 and
  1 and two unordered Lanes); a Lane placed in another Tier goes to its end and placed back
  takes its starting place; off and on gives back Tier and place (also for a Lane off as
  given); `at` inside a Tier, clamped at both ends, and `"end"`; an unplaced Lane written at
  its Tier as given with no place, and an off Lane's prompted Tier kept; bad decisions and
  bad lines refused with nothing changed; lines carry, place, order and switch off; a
  proposal names first and keeps the rest; lines that keep a Tier's sequence still write it;
  a focused save writes only changed fields (an unchanged `enabled: true` and an unchanged
  Tier's gaps survive, a Lane switched off loses `order`); a whole save; meters off and on;
  `changes()` equals the field diff of `documents()` over six decision scripts and rebuilds
  `documents()` from the documents as given, plus one literal list; `settle`/`is_settled`
  over seven change-and-undo pairs; value equality and no hash; the documents given are
  never mutated.
- `tests/test_catalog.py` 22.1 `carried_in_tier` orders by Order, then lane name, and
  skips off Lanes (red on the base with `AttributeError`). `tests/test_bench_page.py` 35.4
  goes through `CatalogDraft.apply`.
- Unchanged and passing: `case_all_harnesses_write_canonical_samples`,
  `case_tiers_from_applies_the_page_lines`, `case_plain_prints_the_refresh_change_lines`,
  `case_the_plain_save_refuses_a_catalog_changed_while_it_asked`, and the `catalog set`,
  `catalog order` and Project order cases of test_catalog (8.x, 10.x, 14.x; 10.11 with
  its helper call renamed, see Deviations).
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and
  3.13.16: every file ok, the dashboard test included.

Deviations:

- Lines and proposals number the Tiers they set even under `whole=False`. The spec says a
  focused save numbers a Tier only when its sequence changed, and also that the order of
  lines and proposals is the order written (rule 4). Where lines name a Tier's Lanes in the
  very sequence the catalog gave (unordered Lanes in name order), the first rule alone
  writes no Order, so with Meters on rank would reorder them by pace, while the old
  `--plain` wrote the lines' order. The draft keeps the Tiers `apply` set and numbers them;
  test case "lines that keep a Tier's sequence still write it as its order" pins it. A
  proposal (`p`) that leaves a Tier numbered 1 to n as given still writes nothing. F2 inherits this
  for a focused screen's `v` and `p`.
- test_catalog 10.11 (a `catalog set` case) and test_setup_tui 61 read the deleted
  `catalog_edit._carried_in_tier`; each now calls `catalog.carried_in_tier` with the same
  assertion. test_setup_tui drops its now-unused `catalog_edit` import. The spec lists 61
  under F2; it moved here because F1 deletes the helper.
- `show_bench` takes the draft in place of the two documents, so
  `case_plain_collects_bench_in_process` passes it a draft of the sample proposal.
