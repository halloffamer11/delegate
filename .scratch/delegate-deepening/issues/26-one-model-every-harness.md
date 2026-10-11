# 26 — One published name names one Model on every Harness that runs it

**What to build:** Candidate A, ticket A3 (lane bench-evidence, the last A ticket). Add
`lane_evidence.published_as_conflict(lanes)`. It allows one name on the Lanes of one
Model across several Harnesses and refuses a name that would denote two Models, keeping
the current wording and naming both model strings. `catalog.validate_lanes` calls it and
keeps only the shape checks.

Add `model_identity(lane)` and use it in `bench.group_lanes`, `bench_order_key` and
`bench_page._lane_list` instead of `carry.model_of`. Delete `carry.model_of`,
`strip_effort_suffix`, `MODEL_EFFORT_SUFFIXES` and `published_as_map`, make
`normalize_name` private, and delete test_catalog 7.8 (strip) and 20.1. Fix the comment in
`harnesses/agy.py` that cites `published_names.strip_effort_suffix`.

`harnesses/claude.py`'s `PUBLISHED_NAME`, by which discovery's `generation()` reads a
published `Claude <Level> <version>` as `claude-<level>-<n>`, stays in the claude
adapter: it names a Model no Lane carries yet, so it is not Lane attribution, and the
"no module outside `lane_evidence` normalizes a printed name" check does not count it.

Update `references/architecture.md` (`published_names` becomes `lane_evidence`),
`references/catalog.md` (a `published_as` entry reaches every Harness that runs the
Model), and `effort.py`'s docstring. `CONTEXT.md`'s sharpened Model and Published name
entries were added with the spec; keep them true to what ships.

Spec: `.scratch/delegate-deepening/spec.md` (A. Lane evidence)

**Blocked by:** 25 An Epoch row reaches the same Lane in every benchmark view

**Status:** landed 2026-10-11 (`d1ca9b0`). `lane_evidence.published_as_conflict` now decides whether one published name would denote two Models, so a name shared by one Model's Lanes on several Harnesses is accepted, and `model_identity` is the one grouping key for `bench.group_lanes`, `bench_order_key` and `bench_page._lane_list`; test_catalog 7.10 (with 7.3 and 7.7), test_lane_evidence's two A3 cases and test_setup_tui 43b verify it. Every box is met on this branch; none waits on the user.

- [x] test_catalog "7.10 one published name on Lanes of one Model on two harnesses is accepted" (opus-high@claude on `claude-opus-5-5` and opus-high@agy on `claude-opus-5-5-high`, both `published_as` "Opus 5.5 Thinking") fails before and passes after.
- [x] test_catalog 7.3 and 7.7 still refuse a name across two Models, with a message naming both model strings.
- [x] test_lane_evidence "kiro's claude-opus-5.5, Claude Code's claude-opus-5-5 and agy's claude-opus-5-5-high are one Model; codex gpt-6-edge-low and gpt-6-edge-high are two" passes.
- [x] test_setup_tui groups_of, 43 and 44 and test_bench_page's lane grouping use `lane_evidence.model_identity`.
- [x] `carry.model_of`, `strip_effort_suffix`, `MODEL_EFFORT_SUFFIXES` and `published_as_map` no longer exist, and no module outside `lane_evidence` normalizes a printed name for Lane attribution (`harnesses/claude.py`'s `PUBLISHED_NAME` stays, as above); no comment cites `published_names`.
- [x] `architecture.md`, `catalog.md` and `effort.py` name `lane_evidence`, and they and `CONTEXT.md`'s Published name entry say that a published name reaches every Harness that runs its Model.
- [x] `make test` passes on Python 3.9 and on `python3.13`.

## Landed, 2026-10-11

**Commits.** `d1ca9b0`. The candidate's review ("delegate-deepening A: review fixes") changed nothing of this ticket's.

**What shipped.**
- `lane_evidence.published_as_conflict(lanes)` takes a lanes document's `{name: lane}` mapping
  and returns `(lane name, message)` for the first `published_as` entry that would make one name
  denote two Models, else None. An entry may not be another Model's identity or model string,
  and one name may not sit on Lanes of two Models; one name on the Lanes of one Model is allowed
  on any Harness. Both messages keep the catalog's wording and name both model strings.
  `catalog.validate_lanes` keeps the shape checks and calls it once after them; its `owners` and
  `claimed` block is gone.
- `lane_evidence.model_identity(lane)` is public (it was `_model_identity`): the harness's family
  base, normalized, so kiro's `claude-opus-5.5`, Claude Code's `claude-opus-5-5` and agy's
  `claude-opus-5-5-high` are one key. `bench.group_lanes`, `bench_order_key` and
  `bench_page._lane_list` group by it, so kiro's Opus now groups with Claude Code's on the tier
  pages and the benchmark page.
- `LaneEvidence` and `published_as_conflict` share private helpers for which Lanes name a Model
  (`_model_lanes`), the names a Model answers to on its own (`_own_names`) and a Lane's
  `published_as` strings (`_published_as`), so the "names a Model" rule lives in one place.
- Deleted: `carry.model_of`, `lane_evidence.strip_effort_suffix`, `MODEL_EFFORT_SUFFIXES` and
  `published_as_map`. `normalize_name` and its separator pattern are private. test_catalog 7.8
  (strip) and 20.1 (suffixes) are deleted, and test_catalog no longer imports `lane_evidence`.
- `harnesses/agy.py`'s comment names `lane_evidence.model_identity` instead of
  `strip_effort_suffix`. `references/architecture.md` drops `published_names` and describes
  `model_identity` and `published_as_conflict`; `references/catalog.md` and `effort.py`'s
  docstring say a `published_as` entry reaches every Harness that runs its Model.
  `CONTEXT.md`'s Model and Published name entries already matched and are unchanged.

**How verified.** New cases: test_catalog "7.10 one published name on Lanes of one Model on two
harnesses is accepted"; test_lane_evidence "kiro's claude-opus-5.5, Claude Code's
claude-opus-5-5 and agy's claude-opus-5-5-high are one Model; codex gpt-6-edge-low and
gpt-6-edge-high are two" and "published_as_conflict allows one name on one Model's Lanes across
harnesses and refuses it across Models"; test_setup_tui "43b kiro's Opus groups with Claude
Code's and agy's Opus, as one Model". Against the code before this ticket (a `git archive` of the
base), 7.10 was refused with "names the same model", the two lane_evidence cases raised
AttributeError for the missing public names, and 43b put `opus-low@kiro` in a group of its own.
All pass after, and 7.3 and 7.7 still refuse with both model strings named. test_setup_tui's
`groups_of`, 43 and 44 and test_bench_page's lane grouping read `lane_evidence.model_identity`.
`make test` passes on Python 3.9 and on `python3.13` with the proxy pointed at a closed port.

**Deviations.**
- Two tests beyond the boxes: the spec's test_lane_evidence case for `published_as_conflict`,
  and test_setup_tui 43b, the red test for the visible change (kiro's Opus joins Claude Code's
  group).
- The catalog now runs every lane's shape checks before the conflict check, so a catalog with
  both a shape error and a conflict reports the shape error first.
- `LaneEvidence` reads `published_as` only when it is a list; it used to iterate a bare string's
  characters, which only an unvalidated catalog could hold.
- `harnesses/base.py` and `claude.py` keep `generation(self, models, published_names)`: the
  parameter is a list of published names, not a citation of the old module.
- `bench_page.price_rows` still groups the price chart by `harnesses.family` base; it reads no
  printed name and attributes no row, so it is outside this ticket.
