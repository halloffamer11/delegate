# 04 — An effort override on a native lane is not silently dropped

**What to build:** `delegate.py dispatch --lane X@claude --effort low` passes validation and records `effort=low` in dispatch.json, but the native agent's effort is fixed in its file, so the worker runs at the lane's effort (`scripts/delegate.py:763`).

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done.

- [x] A native lane either refuses an override that differs from its effort or warns like the agy path does, and dispatch.json records the effort actually used.
- [x] A test covers both the matching and the differing override.

## Landed, 2026-10-02

It warns, like agy: an override that differs from a native lane's effort prints
`delegate: effort override ignored on <lane>; a native lane runs at its agent file's
effort, <effort>`, and dispatch.json records the lane's effort. A matching override is
quiet. "Native" is the same test dispatch already uses (`harness == ORCHESTRATOR`), so a
claude lane relayed under another orchestrator still takes the override.

Verified: `test_dispatch.py` 29a covers the matching and the differing override on
`opus-high@claude`, plus the relayed case under `ORCHESTRATOR=codex`. Passes on 3.9 and
3.13.
