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

**Status:** ready-for-agent

- [ ] `tests/test_lane_evidence.py` tests `available`, `model_rows`, `lane_rows` and `unmatched` on the OPUS_TWO_HARNESSES, OPUS_ONE_AGY, AGY_CARRY_LANES, GUARD_LANES and PUBLISHED_AS_OPUS fixtures.
- [ ] test_bench_page "one Opus point both harnesses share strikes only the Lane carry proposes off" fails before the change and passes after it.
- [ ] test_bench "agy's only Opus Lane is not proposed off by an effort agy does not run" fails before and passes after.
- [ ] test_tier_proposal "a published_as name on Claude Code's Opus Lane scores agy's Opus Lanes too" and "carry and the Tier proposal claim the same rows for a Lane" fail before and pass after.
- [ ] test_bench_page "a pre-screen failure stops the page instead of drawing no verdicts" fails before and passes after.
- [ ] test_bench_page "every Python function bench_page.js cites lives where it says" fails before and passes after.
- [ ] `carry.families`, `carry.family_of`, `carry.dominating_row`, `resolve_effort_rows`, `bench_page._proposals`, `_decision_for` and `_lane_at` no longer exist, and grep finds no `published_names` import in scripts or tests, including the test_setup_tui reads F2 rewrote.
- [ ] `carry.decisions` compares no efforts itself; its no-rows check reads `lane_rows`.
- [ ] Every new test that calls `bench.collect` passes `tests/fixture/bench-epoch.csv`.
- [ ] `CONTEXT.md`'s Lane evidence entry matches what shipped, and `architecture.md`'s carry paragraph names `LaneEvidence.model_rows`.
- [ ] `make test` passes on Python 3.9 (`$(uv python find 3.9)`) and on `python3.13`.
