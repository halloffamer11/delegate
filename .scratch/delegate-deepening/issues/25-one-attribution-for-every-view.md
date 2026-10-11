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

**Status:** ready-for-agent

- [ ] test_bench "an Epoch row reaches a Lane in the scores table and in model inspection alike" (claude-fable-5-1 at high; Epoch row "Claude Fable 5.1", model_version `claude-fable-5-1-20260901_high`, DeepSWE 0.61; a second case uses `published_as` "Fable 5.1") fails before and passes after.
- [ ] test_bench_page "an agy Model's efforts are one sweep, so its finding shows the arithmetic" fails before and passes after: both points' model is `gemini-3.8-flash`, and the finding says "high scores 0.1 less than medium and costs $1 more (+100%)".
- [ ] test_lane_evidence asserts, over every fixture, that a record's lanes are exactly the Lanes whose `lane_rows` hold its row.
- [ ] `bench.collect`, `evidence_records`, `epoch_records` and `inspect_model` call no identity helper outside `lane_evidence`, and `collect` keeps the signature `collect(lanes_doc, epoch_csv=None, effort_rows=None)`.
- [ ] `bench_page.render` calls `bench.evidence_records` once per render.
- [ ] The bench names listed above and `lane_evidence.resolve_published_model` and `resolve_published_models` no longer exist.
- [ ] test_catalog 7.5 to 7.9 and test_setup_tui case 30 assert the same printed names through `identify`, `lane_rows` and `unmatched`.
- [ ] `make test` passes on Python 3.9 and on `python3.13`.
