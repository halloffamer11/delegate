# 24 — The benchmark page and the wizard reach the same verdict for every Lane

**What to build:** Candidate A, ticket A1 (lane bench-evidence, its first ticket). Move
`scripts/published_names.py` to `scripts/lane_evidence.py` with `git mv`. Repoint every
import in `bench`, `carry`, `catalog`, `tier_proposal`, `setup_tui` and the tests, and drop
the unused import from `harnesses/agy.py`.

Add `LaneEvidence(lanes_doc, rows)` with `available`, `model_rows(lane)`,
`lane_rows(lane)` and `unmatched()`. Its identity rule works by harness family, a
`published_as` entry names the Model of the Lane that carries it, and `model_rows` holds
only rows at efforts the Lane's Harness runs (`offers_effort`), plus rows that state no
effort.

Migrate:
- `carry.decisions(lanes_doc, evidence)` and `evidence_unavailable(evidence, decided)`;
  delete `carry.families`, `family_of` and `dominating_row`.
- `tier_proposal.propose(lanes_doc, evidence, settings, names)`.
- `Wizard._load` builds one evidence per scrub, and `_unmatched`, `_proposals` and
  `tier_proposals` read it. Delete `resolve_effort_rows`.
- `bench_page.render` builds one evidence and asks carry once, with no try/except. Each
  point lists its Lanes, each with its own verdict, and a point is struck only when every
  Lane on it is proposed off. `beatenBy` comes from an off verdict on the board's own
  source, and the finding names only the off Lanes. Delete `_proposals`,
  `_decision_for`, `_lane_at` and the re-keying.
- In `bench_page.js`, show each Lane's verdict in the tooltip and the evidence table, and
  fix the citations of `setup_tui._beats`, `setup_tui.group_lanes` and
  `setup_tui.parse_tier_lines`.

Every new `test_bench` and `test_bench_page` case that calls `collect` passes the Epoch
fixture `tests/fixture/bench-epoch.csv`, so no test reaches the web.

Rebase: catalog-write merges before this lane. At the rebase, build the one
`LaneEvidence` in F2's rewritten `Wizard._load`, and convert F2's test_setup_tui evidence
reads (`published_names.resolve_effort_rows`, `carry.decisions(L, rows)`) to
`LaneEvidence(...).unmatched()` and `carry.decisions(L, LaneEvidence(L, rows))`.

`CONTEXT.md`'s Lane evidence entry was added with the spec; keep it true to what ships.
Update the carry paragraph in `references/architecture.md`.

Spec: `.scratch/delegate-deepening/spec.md` (A. Lane evidence; decisions A.1 to A.3)

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-11 (`d0c2a73`; review fixes in "delegate-deepening A: review fixes"). `lane_evidence.LaneEvidence` (the moved `published_names.py`) decides which rows are each Lane's, and carry, the Tier proposal, the wizard and the benchmark page read one; test_lane_evidence's eight cases, test_bench "agy's only Opus Lane is not proposed off by an effort agy does not run", test_tier_proposal's two new cases and test_bench_page's shared-point, pre-screen-failure and citation cases verify it. Every box is met. The deletion box's F2 part was met at the merge onto catalog-write ("delegate-deepening: merge the bench-evidence lane"): F2's `Wizard._load` builds the one `LaneEvidence` that `_unmatched`, `_proposals` and `tier_proposals` read, and F2's test_setup_tui reads (28d, 71, 77) build `LaneEvidence(...)` for `unmatched()` and `carry.decisions`. test_setup_tui 78's failing rebuild now uses a Lane record that is not an object, since the evidence gives a Lane with no model no rows and raises for none.

- [x] `tests/test_lane_evidence.py` tests `available`, `model_rows`, `lane_rows` and `unmatched` on the OPUS_TWO_HARNESSES, OPUS_ONE_AGY, AGY_CARRY_LANES, GUARD_LANES and PUBLISHED_AS_OPUS fixtures.
- [x] test_bench_page "one Opus point both harnesses share strikes only the Lane carry proposes off" fails before the change and passes after it.
- [x] test_bench "agy's only Opus Lane is not proposed off by an effort agy does not run" fails before and passes after.
- [x] test_tier_proposal "a published_as name on Claude Code's Opus Lane scores agy's Opus Lanes too" and "carry and the Tier proposal claim the same rows for a Lane" fail before and pass after.
- [x] test_bench_page "a pre-screen failure stops the page instead of drawing no verdicts" fails before and passes after.
- [x] test_bench_page "every Python function bench_page.js cites lives where it says" fails before and passes after.
- [x] `carry.families`, `carry.family_of`, `carry.dominating_row`, `resolve_effort_rows`, `bench_page._proposals`, `_decision_for` and `_lane_at` no longer exist, and grep finds no `published_names` import in scripts or tests, including the test_setup_tui reads F2 rewrote.
- [x] `carry.decisions` compares no efforts itself; its no-rows check reads `lane_rows`.
- [x] Every new test that calls `bench.collect` passes `tests/fixture/bench-epoch.csv`.
- [x] `CONTEXT.md`'s Lane evidence entry matches what shipped, and `architecture.md`'s carry paragraph names `LaneEvidence.model_rows`.
- [x] `make test` passes on Python 3.9 (`$(uv python find 3.9)`) and on `python3.13`.

## Landed, 2026-10-11

**Commits.** `d0c2a73`, then the review fixes in "delegate-deepening A: review fixes".

**What shipped.**
- `scripts/published_names.py` moved to `scripts/lane_evidence.py` with `git mv`.
  `resolve_effort_rows` is gone; `normalize_name`, `strip_effort_suffix`,
  `MODEL_EFFORT_SUFFIXES`, `published_as_map` and the two resolvers stay for A2 and A3.
  Every import in `bench`, `carry`, `catalog`, `tier_proposal`, `setup_tui` and the tests
  points at `lane_evidence`, and `harnesses/agy.py` no longer imports it.
- `LaneEvidence(lanes_doc, rows)` attributes every row once and answers `available`,
  `model_rows(lane)`, `lane_rows(lane)` and `unmatched()` by lookup, with the caller's own
  row objects in input order. A printed name names a Model when, normalized, it equals a
  `published_as` entry (the Model of the Lane carrying it), a Lane's Model identity (the
  harness family base, normalized) or a Lane's model string; a name that matches two
  Models is unmatched. `model_rows` holds the Model's rows that state no effort or one the
  Lane's Harness offers for that Model (`offers_effort`, any of its Lanes there; no
  adapter runs every effort); `lane_rows` is the part at the Lane's own effort.
- `carry.decisions(lanes_doc, evidence)` splits each Lane's certain `model_rows` into its
  own rows (`lane_rows`) and its rivals; `dominating_effort(own, rivals, source)` and
  `first_domination(own, rivals)` take those rows. Its no-rows check reads `lane_rows`.
  `evidence_unavailable(evidence, decided)` reads `available`. `families`, `family_of` and
  `dominating_row` are gone.
- `tier_proposal.propose(lanes_doc, evidence, settings, names)` scores a Lane from the
  first row of its `lane_rows` on the chosen benchmark.
- `Wizard._load` builds one `LaneEvidence` per scrub; `_unmatched`, `_proposals` and
  `tier_proposals` read it.
- `bench_page.render` builds one evidence and asks carry once (`_prescreen`), with no
  try/except. Each point's Lanes come from `lane_rows`, and each Lane carries its own
  `off`, `kind`, `source` and `competitor`. A point is `lane_off` only when every Lane on it
  is off; `beatenBy` comes from an off verdict on the board's own source (and, as before,
  only on a row that counts); the finding, the sweep table and the rows table name only the
  off Lanes. `_proposals`, `_decision_for`, `_lane_at` and the re-keying are gone.
- `bench_page.js` shows each Lane's verdict in the tooltip and the frontier table, and cites
  `bench.group_lanes`, `tier_lines.parse_tier_lines` and `carry.beats`.
- `references/architecture.md`: the carry paragraph names `LaneEvidence.model_rows` and
  `lane_rows`; the module list, the `bench` and the `bench_page` lines no longer cite
  deleted names. `CONTEXT.md`'s Lane evidence entry already matched.

**How verified.** Each live bug was run on the code before this ticket first: agy's only
Opus Lane came back dominated by xhigh, the shared high point was `lane_off` with
`beatenBy` xhigh, `propose` scored only `opus-high@claude` for "Opus 5.5 Thinking" and
nothing for "Gemini Flash 3.8 Preview" while carry gave `flash-low@agy` rows, and a
`carry.decisions` that raised still rendered a page. The citation test failed naming
`setup_tui._beats`, `setup_tui.group_lanes` and `setup_tui.parse_tier_lines`. On the frozen
real catalog (`tests/fixtures/refresh-2026-09-22`) with the accepted AA and Terminal-Bench
rows, the carry verdicts and the unmatched names are unchanged. `make test` passes on
Python 3.9 and 3.13 with the proxy pointed at a closed port.

**Deviations.**
- test_setup "the refreshed rows reach the new lanes" called `bench.collect` without the
  Epoch fixture and failed at the base under the closed proxy on both Pythons; it now passes
  the fixture, the same line ticket 01 committed on its lane.
- `LaneEvidence` has value equality (`__eq__`): the wizard keeps the evidence, and
  test_setup_tui 78 compares the wizard before and after a failed rescan by value.
- `bench_page.plot_data`'s third parameter is now `prescreen`, the (evidence, verdicts)
  pair; every caller outside the module passes only rows and lanes. The point keeps its own
  `off`, `carryKind`, `source` and `competitor`, set only when it is struck.
- The Model identity is the private `lane_evidence._model_identity`; A3 makes it the public
  `model_identity`. The point's Lanes are worked out from `lane_rows` inside
  `bench_page._annotate` until A2's `records()`.
- `tier_proposal.lane_scores` walks the Lanes in `names` order, so `beaten_by` between two
  equal beaters follows the catalog's order rather than the rows'.
- `harnesses/agy.py`'s comments now cite `lane_evidence.strip_effort_suffix` and
  `lane_evidence`; A3 deletes `strip_effort_suffix` and rewrites that comment again.

**Review fixes.**
- Two off Lanes on one point that lose to different efforts (Claude Code's high to xhigh,
  agy's high to medium) shared one arithmetic in the board's finding and one "beaten by"
  in the rows table, so a Lane read another Lane's reason (decision A.1). `_annotate` now
  keeps each off Lane's competitor on the board's source (`_beaten`); the finding gives each
  competitor its own sentence, and the rows table names each when they differ. `beatenBy`
  is unchanged: the first such competitor. Red first: test_bench_page "a shared point whose
  off Lanes lose to different efforts gives each its own arithmetic".
- A point no Lane runs took its colour from every Lane whose model string the Model has,
  worked out again from `lane_models`; it now reads the record's `model_lanes`, so Opus at
  max is Claude Code's colour, not agy's too, and `bench_page._lanes_of_model` is gone. Red
  first: test_bench_page "a point no Lane runs takes the colour of the Harnesses that run its
  effort".
