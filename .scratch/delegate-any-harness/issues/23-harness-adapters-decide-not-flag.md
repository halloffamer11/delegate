# 23 — Harness adapters decide, callers stop branching on flags

**What to build:** Replace the `base.Harness` flags callers branch on with verbs the adapter implements: `installed()`, a base `meters()` template that owns the absent and failed rows, `owns(model)` in place of `vendor`/`any_vendor`, `effort_for(lane, override)`, `blocked_reason(run_dir)` (grok's event parsing out of `delegate.py`), and a `models()` strategy so the Claude adapter owns its catalog-plus-benchmark-names discovery now in `discover.py`. Call `family` and `lane_model` unconditionally. Delete the legacy `--efforts` path or route it through `refresh_catalog`.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-03. `base.Harness` gained `installed`, `present_in`, `models`, `generation`,
`owns`, `starter`, `meters` (with `read_meters` per adapter), `effort_for` and `blocked_reason`; the Claude
adapter owns the catalog-plus-benchmark-names strategy, grok owns its gate-cancel parsing, and `any_vendor`
and `no_effort_note` are gone. The legacy `discover.py --efforts` is deleted (the wizard's refresh proposes a
new model's Lanes). Discovery results carry `complete` per harness, which `map_lanes` and the setup page read.
`catalog_models` is read only by the registry, to order discovery. Verified: `make test` green on 3.9 and
3.13; the refresh fixtures' tests pass unchanged.

- [x] `discover.py` reads no harness flag; adding a harness with no list command is one module.
- [x] The absent-CLI guard exists once, and `usage` no longer imports `catalog` to find a binary.
- [x] `delegate.py` names no harness.
- [x] `make test` passes on 3.9 and 3.13 with no behaviour change in the refresh fixtures.
