# 06 — An unpriced Lane is not reported as zero cost

**What to build:** `compute_cost` treats a `null` price as $0 and marks the run measured (`scripts/report.py:251`). The wizard creates every new Lane with a `null` price, so new Lanes under-report spend.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done.

- [x] A run on an unpriced Lane shows as unpriced in `report.py log` and is excluded from the measured total, which names how many runs were unpriced.
- [x] A test covers a run with a `null` input price.

## Landed, 2026-10-02

`compute_cost` returns `measured: false, unpriced: true` with the token counts when the
Lane has no `in` or `out` price. `report.py log` ends its line with `unpriced`, `cost`
prints `unpriced: unpriced lane <lane>: no in price`, `runs` shows `unpriced` in the Cost
column, and the roll-up reads `$X measured across N runs, U unpriced, M unmeasured`
(the `U unpriced` part only when there is one). A null cache price still adds $0 with
the "unpublished price" note: codex publishes no cache-write price.

Verified: `test_report.py` logs a run on `luna-low@codex` with its `in` price nulled
and checks the log line, the stored cost, `cost`, the `runs` cell and the roll-up.
Passes on 3.9 and 3.13.
