# 06 — An unpriced Lane is not reported as zero cost

**What to build:** `compute_cost` treats a `null` price as $0 and marks the run measured (`scripts/report.py:251`). The wizard creates every new Lane with a `null` price, so new Lanes under-report spend.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] A run on an unpriced Lane shows as unpriced in `report.py log` and is excluded from the measured total, which names how many runs were unpriced.
- [ ] A test covers a run with a `null` input price.
