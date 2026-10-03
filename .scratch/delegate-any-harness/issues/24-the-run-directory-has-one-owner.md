# 24 — The run directory has one owner

**What to build:** A `runs.py` module owns the run directory: a Run with `create`, `finish`, `fail` and `read`, the `dispatch.json` and `return.json` schemas, and `finish_line` / `parse_finish_line`. `delegate.py` makes one native-or-relayed decision that yields a Run. `delegate run` and `delegate dispatch` gain `--json`, so `evals.py`, `browser_probes.py` and the courier stop parsing text three ways.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-03. `scripts/runs.py` owns the run directory: `Run.create`, `finish`, `fail`,
`read`, the `DISPATCH_FIELDS` and `RETURN_FIELDS` schemas, and `finish_line` / `parse_finish_line` (plus
the native line). `delegate dispatch` and `delegate run` take `--json`; `evals.py` reads it, the courier
writes it to `<brief>.json` and replies with that object, and `browser_probes.py` uses
`parse_finish_line`. Verified: new `tests/test_runs.py`, test_dispatch 20j (run --json) and 29b/29d (the
courier on JSON), the offline evals in `tests/test_evals.py`; `make test` green on 3.9 and 3.13.

- [x] `dispatch.json` and `return.json` are written only through `runs.py`.
- [x] Every reader of the finish line uses `parse_finish_line` or `--json`.
- [x] `make test` and the offline evals pass on 3.9 and 3.13.
