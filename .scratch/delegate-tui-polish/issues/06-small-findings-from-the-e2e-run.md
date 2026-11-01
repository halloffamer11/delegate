# 06 — Small findings from the end-to-end run

**What to build:** The 2026-10-30 run found these, none blocking:

- `delegate global --plain` exits 130 on end of input, as if interrupted.
- The start page's facts contradict each other: "current generation" beside three retired lanes.
- The Epoch mean rank puts a model measured once (n=1) first.
- The AA source URL in `sources.json` names one model's page.
- Every kiro lane warns when the kiro CLI is missing (35 warnings).

**Blocked by:** None — can start immediately.

**Status:** needs-triage

- [ ] Each finding is fixed or closed with a reason.
