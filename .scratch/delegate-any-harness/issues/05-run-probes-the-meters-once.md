# 05 — `run` probes the Meters once

**What to build:** `run()` forces a full vendor probe to rank, then `dispatch()` forces a second one (`scripts/delegate.py:865`). That is two `claude -p /usage` calls per job, and that probe can spend the quota it measures.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done.

- [x] `run` ranks and dispatches on one probe; `dispatch` called alone still probes.
- [x] A test counts probe invocations for one `run`.

## Landed, 2026-10-02

`run` passes `probed=True` to `dispatch` when `rank.load_usage` has just acquired the
Meters (no `--meters` document, metering on), and dispatch then skips its pre-relay
probe. The post-relay probe is unchanged, so a `run` now acquires once before the relay
and once after, where it acquired twice before. `dispatch` called alone still forces a
probe before the relay.

The rank's acquisition is `usage.acquire()` without `refresh`, so a fresh cache serves
it and no vendor is probed at all; before this, dispatch's forced probe always ran.

Seen while here, not changed: `run --no-probe` still acquires for ranking unless
`--meters` is passed.

Verified: `test_dispatch.py` 34c logs each `usage.acquire` and the relay start for one
`run` (one acquisition before the relay) and one `dispatch` (one forced probe before
it). On the old code the run logged `cached, refresh, relay, refresh`. Passes on 3.9 and
3.13.
