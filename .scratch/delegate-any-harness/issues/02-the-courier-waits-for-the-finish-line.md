# 02 — The courier waits for the finish line

**What to build:** `agents/agents/courier.md:15` takes the first log line starting `delegate:` as the result. Dispatch writes earlier `delegate:` lines (the agy effort-override warning) and the native-lane line has no `run=`. The courier then `cat`s a missing return.json and replies while the worker runs.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] The courier keys on a line only dispatch's finish writes (a distinct prefix or `run=` with a status), never on the first `delegate:` line.
- [ ] A native-lane line is reported as "spawn the native agent", not as a result.
- [ ] A test covers an agy run with an effort override and a native lane.
