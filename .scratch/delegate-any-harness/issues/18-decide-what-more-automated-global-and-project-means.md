# 18 — Decide what "more automated" means for `delegate global` and `delegate project`

**What to decide:** Orin wants the global/project model kept but more automated (2026-10-02). Candidates: dispatch notices a model the catalog lacks and queues it for the next wizard run; `delegate global` runs on a schedule or after `make install`; a project picks up new Lanes without a manual Order. Pick which, then split into build tickets.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** needs-info, raised by Orin 2026-10-02

- [ ] Orin names the behaviours he wants.
- [ ] Build tickets exist for each, and this ticket closes.
