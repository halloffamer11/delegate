# 03 — A relay that cannot start still finishes its run

**What to build:** `scripts/delegate.py:478` starts `node` after `ledger_start`. A missing `node`, or any exception there, leaves no `dispatch.finish`, no return.json and a phantom running glyph in the statusline until the timeout. `ads.sh check` checks only that relay files exist.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done.

- [x] `ads.sh check` (or dispatch) reports a missing `node` before the ledger records a start.
- [x] Any exception after `ledger_start` writes a finish event with a failed status and a return.json saying why.
- [x] A test with `node` absent from PATH proves both.

## Landed, 2026-10-02

`ads.sh check` now fails first with `ads: node is not on PATH; the relays need Node.js`,
so dispatch exits 2 before it makes a run directory or a ledger start. Past the start,
dispatch runs steps 5-7 (probe, relay, probe, map) inside one `try`; any exception,
or Ctrl-C, writes a blocked return.json and dispatch.json naming the cause (a missing
`node` reads `node is not on PATH; the relay needs Node.js`), then the ledger finish and
the usual finish line, exit 1.

The finish status is `blocked`, not a new `failed`: return.json and the ledger use
`done`/`partial`/`blocked`, and a relay that fails is already recorded as blocked. The
finish event's `rc` is 1.

A native lane also passes through `ads.sh check`, so it too now needs `node` on PATH.

Verified: `test_dispatch.py` 12d (node absent: exit 2, no run dir, no ledger line) and
12e (node removed after the check: start and finish in the ledger, blocked return.json
naming node). 12e fails on the old `delegate.py`. Passes on 3.9 and 3.13.
