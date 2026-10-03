# 26 — catalog.py splits along its seams

**What to build:** Move the edit engine (`catalog.py:1595-2486`) to `catalog_edit.py`, which removes the lazy import cycle with `rank`; give the class-guide checker its own module; move tier-lines next to the wizard and published-name identity next to bench; delete the registry facade (`catalog.py:46-92`). `catalog.py` keeps one job: load, validate and project the effective catalog.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised in review of PR #3 2026-10-03

- [ ] No import cycle between `catalog` and `rank`.
- [ ] Callers import the new modules directly; no re-export shims remain.
- [ ] `make test` passes on 3.9 and 3.13 with no behaviour change.
