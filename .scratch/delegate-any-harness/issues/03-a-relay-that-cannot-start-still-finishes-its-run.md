# 03 — A relay that cannot start still finishes its run

**What to build:** `scripts/delegate.py:478` starts `node` after `ledger_start`. A missing `node`, or any exception there, leaves no `dispatch.finish`, no return.json and a phantom running glyph in the statusline until the timeout. `ads.sh check` checks only that relay files exist.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] `ads.sh check` (or dispatch) reports a missing `node` before the ledger records a start.
- [ ] Any exception after `ledger_start` writes a finish event with a failed status and a return.json saying why.
- [ ] A test with `node` absent from PATH proves both.
