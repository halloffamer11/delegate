# 18 — Decide what "more automated" means for `delegate global` and `delegate project`

**What to decide:** The user wants the global/project model kept but more automated (2026-10-02). Candidates: dispatch notices a model the catalog lacks and queues it for the next wizard run; `delegate global` runs on a schedule or after `make install`; a project picks up new Lanes without a manual Order. Pick which, then split into build tickets.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** closed 2026-10-03. The user picked "Queue + follow": dispatch queues models the catalog lacks for the next `delegate global` (ticket 29), and a project places new Lanes by global Order (ticket 30). Not picked: a catalog refresh on `make install` or `make update`.

- [x] The user names the behaviours he wants.
- [x] Build tickets exist for each, and this ticket closes.
