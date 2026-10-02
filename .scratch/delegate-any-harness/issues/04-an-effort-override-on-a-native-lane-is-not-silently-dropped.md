# 04 — An effort override on a native lane is not silently dropped

**What to build:** `delegate.py dispatch --lane X@claude --effort low` passes validation and records `effort=low` in dispatch.json, but the native agent's effort is fixed in its file, so the worker runs at the lane's effort (`scripts/delegate.py:763`).

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] A native lane either refuses an override that differs from its effort or warns like the agy path does, and dispatch.json records the effort actually used.
- [ ] A test covers both the matching and the differing override.
