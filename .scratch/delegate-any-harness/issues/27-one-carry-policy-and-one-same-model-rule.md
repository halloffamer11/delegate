# 27 — One carry policy and one same-model rule

**What to build:** A `carry.py` module owns `families()`, `decisions()` (structured `{kind, source, competitor}`) and `beats()`, used by the wizard, the bench page and `tier_proposal`; renderers keep their wording. `bench.model_group` and `harnesses.slug_family` go, leaving the adapter's `family` as the one rule for which slugs are the same model.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised in review of PR #3 2026-10-03

- [ ] One function decides whether two slugs are the same model, and it asks the harness.
- [ ] The beats-on-score-for-no-more-cost predicate exists once in Python.
- [ ] `make test` passes on 3.9 and 3.13.
