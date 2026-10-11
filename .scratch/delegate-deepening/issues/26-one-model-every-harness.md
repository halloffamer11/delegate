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

**Status:** ready-for-agent

- [ ] test_catalog "7.10 one published name on Lanes of one Model on two harnesses is accepted" (opus-high@claude on `claude-opus-5-5` and opus-high@agy on `claude-opus-5-5-high`, both `published_as` "Opus 5.5 Thinking") fails before and passes after.
- [ ] test_catalog 7.3 and 7.7 still refuse a name across two Models, with a message naming both model strings.
- [ ] test_lane_evidence "kiro's claude-opus-5.5, Claude Code's claude-opus-5-5 and agy's claude-opus-5-5-high are one Model; codex gpt-6-edge-low and gpt-6-edge-high are two" passes.
- [ ] test_setup_tui groups_of, 43 and 44 and test_bench_page's lane grouping use `lane_evidence.model_identity`.
- [ ] `carry.model_of`, `strip_effort_suffix`, `MODEL_EFFORT_SUFFIXES` and `published_as_map` no longer exist, and no module outside `lane_evidence` normalizes a printed name for Lane attribution (`harnesses/claude.py`'s `PUBLISHED_NAME` stays, as above); no comment cites `published_names`.
- [ ] `architecture.md`, `catalog.md` and `effort.py` name `lane_evidence`, and they and `CONTEXT.md`'s Published name entry say that a published name reaches every Harness that runs its Model.
- [ ] `make test` passes on Python 3.9 and on `python3.13`.
