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

**Status:** ready-for-agent

- [ ] `case_a_prompted_tier_change_moves_the_lane_to_the_end_of_its_new_tier` fails before this ticket (terra written 3/1 beside sol 3/1, grok left at 2/2) and passes after: terra 3/2, sol 3/1, grok 2/1, and stdout has "terra-high@codex: tier 3, order 2".
- [ ] `tests/test_catalog_draft.py` exercises every entry point only through the interface and runs under `make test`.
- [ ] `--plain` with default answers still writes the sample catalog byte for byte (`case_all_harnesses_write_canonical_samples`), and `--tiers-from` still writes the lines' order (`case_tiers_from_applies_the_page_lines`).
- [ ] `confirm_and_write` takes `(draft, read)`, commits through `catalog_commit.commit`, and has no `refresh` or `targets` parameter.
- [ ] `tier_lines.apply_tier_lines_to_doc`, `tier_lines.write_order_from_lines` and `catalog_edit._carried_in_tier` are gone, and nothing imports them.
- [ ] `catalog set`, `catalog order` and Project order tests in `test_catalog.py` pass unchanged.
- [ ] `CONTEXT.md`'s Draft and Order entries match what shipped, and `references/architecture.md` names `catalog_draft.py` and what it owns.
- [ ] `make test` is green on Python 3.9 (`$(uv python find 3.9)`) and on `python3.13`.
