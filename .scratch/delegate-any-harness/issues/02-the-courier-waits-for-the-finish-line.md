# 02 — The courier waits for the finish line

**What to build:** `agents/agents/courier.md:15` takes the first log line starting `delegate:` as the result. Dispatch writes earlier `delegate:` lines (the agy effort-override warning) and the native-lane line has no `run=`. The courier then `cat`s a missing return.json and replies while the worker runs.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done; a live Workflow run through the courier is still Orin's to try.

- [x] The courier keys on a line only dispatch's finish writes (a distinct prefix or `run=` with a status), never on the first `delegate:` line.
- [x] A native-lane line is reported as "spawn the native agent", not as a result.
- [x] A test covers an agy run with an effort override and a native lane.

## Landed, 2026-10-02

The courier's background command now ends with `echo "courier-exit: $?"`, and it polls
for that marker instead of the first `delegate:` line. It then greps, in order, for the
finish line (`^delegate: [^ ]+ status=[^ ]+ secs=[^ ]+ run=`, written only by
`print_and_exit`) and the native-lane line, which it reports as
`courier: spawn the native agent` with the line. Neither: the last 20 log lines.
Dispatch's own output is unchanged.

Verified: `test_dispatch.py` 29b reads both greps out of `courier.md`, runs dispatch in
the courier's command shape for `flash-high@agy --effort low` (the warning is the log's
first line) and for `opus-high@claude`, and checks the courier takes the finish line in
the first and reports the native line in the second. Passes on 3.9 and 3.13.
