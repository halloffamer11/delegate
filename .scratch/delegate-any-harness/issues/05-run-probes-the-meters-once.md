# 05 — `run` probes the Meters once

**What to build:** `run()` forces a full vendor probe to rank, then `dispatch()` forces a second one (`scripts/delegate.py:865`). That is two `claude -p /usage` calls per job, and that probe can spend the quota it measures.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] `run` ranks and dispatches on one probe; `dispatch` called alone still probes.
- [ ] A test counts probe invocations for one `run`.
