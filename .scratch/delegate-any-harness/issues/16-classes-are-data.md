# 16 — Classes are data

**What to build:** custom Classes. Today `catalog.py:62` closes the set at five and the 2026-09-15 refactoring consultation chose to keep it closed; the multi-domain proposal (M7) sketched opening it. A Class becomes an entry in `routing.json` (floor, ceiling) with its guide section in `classes.md` (global or the project overlay), validated together. This reopens a session decision, not ADR 0001.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] A project or global catalog can add a Class with a floor, a ceiling and a guide section, and `rank.py` accepts it.
- [ ] `catalog.py check` and `check-guide` reject a Class with no guide section or no range, naming which.
- [ ] The five built-in Classes keep their behaviour with no catalog change.
