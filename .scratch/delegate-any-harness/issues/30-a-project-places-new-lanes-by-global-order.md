# 30 — A project places new Lanes by global Order

**What to build:** A Lane a project's `project_order` does not name takes its place inside
its Tier by global Order: right after the last named Lane the global Order puts ahead of it.
Before, such Lanes sat after every named Lane, so a Lane the wizard added (a successor takes
its predecessor's global `order`) landed at the bottom of every project that had ordered
that Tier. A Lane with no global Order still goes last, by name. Named Lanes keep the
project's sequence.

From ticket 18: Orin picked "Queue + follow" on 2026-10-03.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A successor Lane lands where its predecessor sat in a project's order.
- [ ] `make test` passes on 3.9 and 3.13.
