# 27 — One carry policy and one same-model rule

**What to build:** A `carry.py` module owns `families()`, `decisions()` (structured `{kind, source, competitor}`) and `beats()`, used by the wizard, the bench page and `tier_proposal`; renderers keep their wording. `bench.model_group` and `harnesses.slug_family` go, leaving the adapter's `family` as the one rule for which slugs are the same model.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed in delegate#6 2026-10-03. `scripts/carry.py` owns `families()`, `model_of(lane)`, `beats()`, `decisions()` (was `bench.propose_enabled`; each decision `{lane, enabled, kind, source, competitor}`), `dominating_effort`, `dominating_row`, `first_domination`, `certain_effort_rows` and the `KIND_*` words. The wizard, the benchmark page and `tier_proposal` read it; `tier_proposal`'s own `_beats` is gone (`carry.beats(..., cost="cost")`). `bench` keeps the wording (`carry_reason`) and display order, now grouped by `carry.model_of`, which asks the Lane's harness. `bench.model_group`, `bench.model_families` and `harnesses.slug_family` are gone; `discover.model_level` takes the harness. `resolve_effort_rows` moved to `published_names`. Verified: `make test` on 3.9 and 3.13.

- [x] One function decides whether two slugs are the same model, and it asks the harness.
- [x] The beats-on-score-for-no-more-cost predicate exists once in Python.
- [x] `make test` passes on 3.9 and 3.13.
