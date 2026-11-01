# 05 — Claude read-only workers start in plan mode

**What to build:** On the 2026-10-30 end-to-end run, a Claude read-only lane started with `--permission-mode plan`, and the worker was told to write a plan file instead of answering. The relay that sets the mode is in `delegate-skills`.

**Blocked by:** None — can start immediately.

**Status:** needs-triage

- [ ] A read-only Claude worker answers in its final message, with no plan file.
- [ ] The relay's permission mode for read-only work is one a worker can finish in.
