# 02 — A native Run ends as handed to its agent

**What to build:** Candidate C, ticket C2 (lane run-and-relay). Add `HandOff(agent,
spawn)` as a result that the work may return. For a `HandOff`, `execute` does the
following:
- records the outcome status `native`, reason `handed to <agent>`, a `finished_at`, and
  secs null;
- writes no `return.json`;
- appends the Ledger start and a finish with status `native`;
- never touches the Meter hold.

`Ended.text` gives the native line and the spawn line, byte-identical to today. With
`as_json` it gives today's native object. `exit_code` is 0.

Migrate the native branch of `delegate.dispatch` to `execute`. Its work is
`lambda run: HandOff(orchestrators.agent_name(profile, lane), orchestrators.spawn_line(profile, lane, run.prompt_path))`.
This removes the second `Run.create` call site.

Make `Run.create`, `Run.thread_id`, `native_line` and `native_summary` private;
`parse_native_line` stays public.

Update `references/architecture.md`: a native Run ends as a hand-off, and
`report.py log --run` reads status `native` for it.

Spec: `.scratch/delegate-deepening/spec.md` (C. Run lifecycle; decisions C.1 and C.6)

**Blocked by:** 01 A started Run always finishes

**Status:** landed 2026-10-11 (b8bac6d). `delegate.dispatch` now runs a native Lane through `runs.execute` with a `HandOff` work, so its Run ends at once with status `native` in `dispatch.json` and the Ledger; test_runs 8 and p7, test_dispatch 29 and the two native `log --run` checks in test_report verify it. No box is open.

- [x] Failing first, then green: test_dispatch 29 asserts the native Run's `dispatch.json` has status `native` and a `finished_at` (null on the code before this ticket).
- [x] test_runs "a hand-off ends the Run at once as native": no `return.json`, Ledger start and finish with status `native`, a held Meter stays held, `text()` is the native line then the spawn line, `text(as_json=True)` is the native object, `exit_code` 0.
- [x] test_runs 7 parses a native line built by `Ended.text`, not by `runs.native_line`.
- [x] test_dispatch 29a, 29b, 29c, 30 and 31e pass unchanged; the courier still gets `"native": true` and no `"return"`.
- [x] `delegate log --run` on a native Run without `--secs` still asks for `--secs`.
- [x] `make test` is green on 3.9 and 3.13.

## Landed, 2026-10-11

**Commits.** `b8bac6d` (delegate-deepening 02: A native Run ends as handed to its agent).

**What shipped.**
- `runs.HandOff(agent, spawn)` is the second result a work may return. For a `HandOff`,
  `execute` records status `native`, reason `handed to <agent>`, secs null and a
  `finished_at`. It writes no `return.json` and appends a Ledger finish with status
  `native`, secs null and rc 0. The Meter settle is still called, and it leaves the Meter
  alone for status `native`.
- `Ended` now holds its printed lines and its JSON object. `text()` gives the native line,
  then the spawn line; `text(as_json=True)` gives the native object. `exit_code` is 0.
- `delegate.dispatch` builds one `Request` for every Lane. A native Lane's work is a
  small function that returns
  `HandOff(orchestrators.agent_name(profile, lane), orchestrators.spawn_line(profile, lane, run.prompt_path))`,
  and a `StartError` now exits 2 with one line for a native Lane too.
- `Run.create` and `Run.thread_id` are gone: nothing called them once dispatch moved, and
  `_start` already makes the Run. `native_line` and `native_summary` are the private
  `_native_line` and `_native_summary`; the finish lines are built by the private
  `_finish_lines`. `parse_native_line` stays public.
- `references/architecture.md` says a native Run ends as a hand-off, and that
  `report.py log --run` reads status `native` for it and still asks for `--secs`.

**How it was verified.**
- Red first:
  - test_dispatch 29 now asserts status `native`, reason `handed to lane-opus-high`,
    secs null, a `finished_at` and no `return.json`. On the code before this ticket it
    failed with status, reason and `finished_at` all null.
  - test_runs 8, "a hand-off ends the Run at once as native", and p7 both failed before
    `HandOff` existed: the work raised and the Run ended blocked.
  - Case 8 also caught each of these mutants of `execute`: the hand-off releases the Meter;
    it writes `return.json`; it records secs 0; the spawn line loses its colon; its exit
    code is 1.
- test_runs p7 now parses the native line that `Ended.text` prints.
- test_dispatch 29a, 29b, 29c, 29d, 30 and 31b-31f pass unchanged, so the courier still
  gets `"native": true` and no `"return"`.
- test_report adds two checks. `log --run` on a native Run without `--secs` exits non-zero
  and asks for `--secs`. With `--secs 95` it logs status `native`, the secs and the
  thread.
- A direct run of the old and new `delegate dispatch` on a native Lane matched byte for byte
  on stdout, stderr and the exit code, with and without `--json`, with the run directory
  masked. The old code wrote no Ledger line; the new code writes a start and a native finish.
- `make test` is green with every proxy variable pointed at a closed port, on Python 3.9.25
  and 3.13.

**Deviations.**
- The native work is a nested `def work(run)` rather than a `lambda` bound to a name; the
  body is the ticket's.
- `Run.create` and `Run.thread_id` are deleted, not renamed, since nothing calls them.
- The Ledger's v1 finish keeps its keys. For a native Run, `secs` is null (decision C.6),
  so `events.finish_event` now accepts `secs=None`. `rc` is 0, the dispatch's exit code,
  because no relay ran and nothing failed. The statusline reads neither field. C4 moves
  these encoders into `runs.py`.
- `runs.root()` now always returns an absolute path; before, it skipped `abspath` for the
  default root. `run.prompt_path` is therefore absolute, so the native line and the spawn
  line keep the absolute prompt path that dispatch used to make with `os.path.abspath`.
- Behaviour that changed with no test asking for it:
  - A native Run now writes a Ledger start and finish. The finish comes at once, so the
    statusline shows no glyph for it, as before.
  - A runs root that cannot be made now exits 2 with one line for a native Lane. Before,
    it ended in a traceback.
  - A work that returns neither a `Finish` nor a `HandOff` ends blocked with a reason
    naming both types.
