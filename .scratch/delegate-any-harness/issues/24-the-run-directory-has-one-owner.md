# 24 — The run directory has one owner

**What to build:** A `runs.py` module owns the run directory: a Run with `create`, `finish`, `fail` and `read`, the `dispatch.json` and `return.json` schemas, and `finish_line` / `parse_finish_line`. `delegate.py` makes one native-or-relayed decision that yields a Run. `delegate run` and `delegate dispatch` gain `--json`, so `evals.py`, `browser_probes.py` and the courier stop parsing text three ways.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised in review of PR #3 2026-10-03

- [ ] `dispatch.json` and `return.json` are written only through `runs.py`.
- [ ] Every reader of the finish line uses `parse_finish_line` or `--json`.
- [ ] `make test` and the offline evals pass on 3.9 and 3.13.
