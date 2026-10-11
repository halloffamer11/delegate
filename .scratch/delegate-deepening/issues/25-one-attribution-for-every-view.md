# 25 — An Epoch row reaches the same Lane in every benchmark view

**What to build:** Candidate A, ticket A2 (lane bench-evidence). Add
`LaneEvidence.records()` and `identify(name)`. A row's printed names are its `model`, then
its `slug`, and `lane_model` is the Model's display name (a whole-name Lane model, else
the harness family base).

`bench.collect` builds one evidence for the Epoch rows and one for the effort rows, and
keeps its signature, `collect(lanes_doc, epoch_csv=None, effort_rows=None)`; H1 later
swaps `epoch_csv` for `epoch_rows`. The model-level view reads records with the model's
`model_key`, and the lane section reads `lane_rows`. Each model figure names the Lanes
that claim it, and `bench_page._figure_cell` reads them. `bench.evidence_records(evidence)`,
`bench.epoch_records(evidence)` and `inspect_model` read `records`, `identify` and
`lane_rows`; these are the final signatures, and H keeps them. `bench_page.render`
annotates the records once and passes the items to the plots, the boards and the rows
blocks, and it groups points by the Model's display name.

Delete `model_matches_slug`, `match_epoch_rows`, `aa_component_rows`,
`effort_attributes`, `lane_figure`, `_canonical_model`, `identity_of`, `inspect_targets`,
`_ident_models`, `_lanes_at`, `_attributed`, `_record_matches_query`, the Epoch slug
fallback, `resolve_published_model` and `resolve_published_models`. Port test_catalog 7.5
to 7.9 and test_setup_tui case 30 to `identify`, `lane_rows` and `unmatched`. Every new
test that calls `collect` passes the Epoch fixture. Update the `bench_page` and `bench`
paragraphs of `references/architecture.md`.

Spec: `.scratch/delegate-deepening/spec.md` (A. Lane evidence; decisions A.4 and A.5)

**Blocked by:** 24 The benchmark page and the wizard reach the same verdict for every Lane

**Status:** landed 2026-10-11 (`f17302f`; review fixes in "delegate-deepening A: review fixes"). `LaneEvidence` gained `records()` and `identify(name)`, and `bench.collect`, `evidence_records`, `epoch_records`, `inspect_model` and `bench_page.render` read them and `lane_rows` instead of their own name matching; test_bench "an Epoch row reaches a Lane in the scores table and in model inspection alike", test_bench_page "an agy Model's efforts are one sweep, so its finding shows the arithmetic" and "render reads the evidence records once", and test_lane_evidence "a record's lanes are exactly the Lanes whose lane_rows hold its row" and the ported 7.5 to 7.9 verify it. Every box is met on this branch; none waits on the user.

- [x] test_bench "an Epoch row reaches a Lane in the scores table and in model inspection alike" (claude-fable-5-1 at high; Epoch row "Claude Fable 5.1", model_version `claude-fable-5-1-20260901_high`, DeepSWE 0.61; a second case uses `published_as` "Fable 5.1") fails before and passes after.
- [x] test_bench_page "an agy Model's efforts are one sweep, so its finding shows the arithmetic" fails before and passes after: both points' model is `gemini-3.8-flash`, and the finding says "high scores 0.1 less than medium and costs $1 more (+100%)".
- [x] test_lane_evidence asserts, over every fixture, that a record's lanes are exactly the Lanes whose `lane_rows` hold its row.
- [x] `bench.collect`, `evidence_records`, `epoch_records` and `inspect_model` call no identity helper outside `lane_evidence`, and `collect` keeps the signature `collect(lanes_doc, epoch_csv=None, effort_rows=None)`.
- [x] `bench_page.render` calls `bench.evidence_records` once per render.
- [x] The bench names listed above and `lane_evidence.resolve_published_model` and `resolve_published_models` no longer exist.
- [x] test_catalog 7.5 to 7.9 and test_setup_tui case 30 assert the same printed names through `identify`, `lane_rows` and `unmatched`.
- [x] `make test` passes on Python 3.9 and on `python3.13`.

## Landed, 2026-10-11

**Commits.** `f17302f`, then the review fixes in "delegate-deepening A: review fixes".

**What shipped.**
- `LaneEvidence.records()` returns one record per row: `row`, `published` (the printed name
  that decided it), `key`, `effort` (`unknown` when the row states none), `identity`,
  `identity_reason`, `candidates`, `model_key`, `lane_model` (the Model's display name: a
  Lane model string equal to the identity, else the harness family base), `lane_models`
  (every Lane model string of the Model), `model_lanes`, `lanes` (exactly the Lanes whose
  `lane_rows` hold the row) and `attributed`. `identify(name)` answers the same identity for
  one name. A row's printed names are its `model`, then its `slug`; the first that names
  exactly one Model decides it, and an unresolved row says "empty published name", "no
  catalog model" or "conflicting identity". `unmatched` lists the deciding printed name.
- `bench.collect(lanes_doc, epoch_csv=None, effort_rows=None)` builds one evidence over the
  Epoch rows and one over the accepted rows. The model view reads the records whose
  `model_key` is the catalog model's (through `identify`), and each figure names the Lanes
  that claim it; the lane section reads `lane_rows`. `bench_page._figure_cell` reads those
  Lanes.
- `bench.evidence_records(evidence)`, `epoch_records(evidence)` and `inspect_model` build
  their display records from `records`; `inspect_model` finds the family with `identify` and
  each Lane's rows with `lane_rows`, so a member slug's query shows the whole Model.
- `bench_page.render` annotates the records once and hands the items to the plots, the
  boards and the rows blocks; points group by the Model's display name, so an agy Model's
  efforts draw as one sweep.
- Deleted: `model_matches_slug`, `match_epoch_rows`, `aa_component_rows`,
  `effort_attributes`, `lane_figure`, `_canonical_model`, `identity_of`, `inspect_targets`,
  `_ident_models`, bench's `_lanes_at`, `_attributed`, `_record_matches_query`, the Epoch
  slug fallback, `resolve_published_model` and `resolve_published_models`.
- test_catalog 7.5 to 7.9 moved to test_lane_evidence on `identify`, `lane_rows` and
  `unmatched`; test_setup_tui case 30 reads `identify(...)["lane_models"]` and `unmatched()`.
- `references/architecture.md`: the lane_evidence entry and the `bench` and `bench_page`
  paragraphs say what the records carry and who reads them. `CONTEXT.md` already matched.

**How verified.** The three named tests were run against the code before this ticket (a
`git archive` of the base): the Fable case printed `(None, [0.61])` for both the display
name and the `published_as` entry, the agy points came back as `gemini-3.8-flash-medium` and
`gemini-3.8-flash-high` with no arithmetic in the finding, and render read the evidence
records three times. All pass after. `make test` passes on Python 3.9 and on `python3.13`
with the proxy pointed at a closed port.

**Deviations.**
- The Fable test writes its own one-row local Epoch CSV (the row the box names) and passes it
  as `epoch_csv`, instead of `tests/fixture/bench-epoch.csv`; nothing reaches the web.
- test_bench_page "an unstated effort is attributed to no lane and says so" now reaches the
  figure through `collect` with a copy of the fixture whose DeepSWE row is renamed, and the
  "post-fix cell shape" data carries each figure's `lanes`, because the cell now reads them.
- `lane_models` is every Lane model string of the Model, whatever the effort, so inspection
  names all its Lanes.
- `published_as_map`, `normalize_name` and `strip_effort_suffix` stay for A3; nothing in bench
  calls them. `group_lanes` and `bench_order_key` still use `carry.model_of` until A3.
- `bench_page.plot_data` delegates to a private `_plot_data(items, ...)`; `_boards_block` and
  `_rows_block` take the items. `effort.py`'s docstring names `lane_evidence`.
- Two tests beyond the boxes: test_bench "an Artificial Analysis component row reaches both
  harnesses' Opus in collect's lane section" and test_bench_page "render reads the evidence
  records once".

**Review fixes.** `lane_evidence`'s identity reasons and its unstated-effort tuple are
private (`_EMPTY_NAME`, `_NO_MODEL`, `_CONFLICT`, `_UNSTATED_EFFORTS`): nothing outside the
module read them, and the spec's interface names none of them. `UNKNOWN_EFFORT` stays
public, because `bench` keys a figure's cell on it.
