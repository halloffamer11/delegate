# 23 — Harness adapters decide, callers stop branching on flags

**What to build:** Replace the `base.Harness` flags callers branch on with verbs the adapter implements: `installed()`, a base `meters()` template that owns the absent and failed rows, `owns(model)` in place of `vendor`/`any_vendor`, `effort_for(lane, override)`, `blocked_reason(run_dir)` (grok's event parsing out of `delegate.py`), and a `models()` strategy so the Claude adapter owns its catalog-plus-benchmark-names discovery now in `discover.py`. Call `family` and `lane_model` unconditionally. Delete the legacy `--efforts` path or route it through `refresh_catalog`.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised in review of PR #3 2026-10-03

- [ ] `discover.py` reads no harness flag; adding a harness with no list command is one module.
- [ ] The absent-CLI guard exists once, and `usage` no longer imports `catalog` to find a binary.
- [ ] `delegate.py` names no harness.
- [ ] `make test` passes on 3.9 and 3.13 with no behaviour change in the refresh fixtures.
