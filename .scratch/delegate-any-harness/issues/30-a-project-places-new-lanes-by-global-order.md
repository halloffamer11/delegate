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

**Status:** landed 2026-10-03. `catalog._place_by_global_order` numbers each Tier in
`_effective_lanes`. One behaviour changed: a hand-written partial `project_order` no
longer pins every unnamed Lane below the named ones; an unnamed Lane with a global Order
goes by it. Order edits through `delegate catalog order`, the wizard or the dashboard
always write the whole Tier, so for them only Lanes added later are unnamed. Two
test fixtures that relied on a partial list now name the Lanes they meant to pin.
Verified: `test_catalog` 8.6b, and `make test` on 3.9 and 3.13.

- [x] A successor Lane lands where its predecessor sat in a project's order.
- [x] `make test` passes on 3.9 and 3.13.
