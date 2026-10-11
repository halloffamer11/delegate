# 04 — Only the Run module writes the Ledger

**What to build:** Candidate C, ticket C4 (lane run-and-relay, the last C ticket). Move
the encoding of the start and finish lines into `runs.py` as private functions. Keep the
keys and order byte-identical: `v`, `kind`, `ts`, `thread_id`, `lane`, `class`, ... .

Delete `events.py`, its CLI and `tests/test_events.py`. Remove `usage.py`'s `events`
import and stop appending meter events in `usage.write_cache` (decision C.2: the Ledger
records Runs only); if B's lane already removed them, there is nothing to do there.
Delete test_usage_reset's meter-event Ledger assertions and add nothing to that file,
which B4 deletes; B3 adds "a probe writes nothing to the Ledger" to test_usage.

Add a guard case to test_runs: no script under `scripts/` except `runs.py` names
`DELEGATE_LEDGER`, or writes `dispatch.json` or `return.json`.

Update these docs:
- the `report.py` docstring: `ledger.jsonl` holds one line when each Run starts and one
  when it ends, written by `runs.py`;
- the `delegate.py` docstring;
- `references/architecture.md`: the `events.py` entry becomes "runs.py owns the Ledger";
- `CONTEXT.md`: its Outcome, Ledger and Running entries were added with the spec; keep
  them true to what shipped, with a native Run folded into Outcome (there is no separate
  Hand-off term).

Spec: `.scratch/delegate-deepening/spec.md` (C. Run lifecycle; decision C.2)

**Blocked by:** 02 A native Run ends as handed to its agent; 03 The statusline counts running Runs through the Run module

**Status:** landed 2026-10-11 (0563f5e). `runs.py` writes the Ledger's v1 start and finish lines through private encoders, `events.py` and `tests/test_events.py` are deleted, and `usage.py` appends no meter event; test_runs 12 (the lines a Run writes equal the v1 fixture lines byte for byte) and 13 (the guard) verify it. No box is open.

- [x] `scripts/events.py` and `tests/test_events.py` are deleted; `grep -rn 'import events\|from events' agents/` finds nothing.
- [x] test_runs: the Ledger lines a Run writes carry exactly the v1 keys in today's order, the same lines the C3 fixture reads.
- [x] The guard case passes: only `runs.py` names `DELEGATE_LEDGER` or writes `dispatch.json` and `return.json`.
- [x] `usage.py` no longer writes to the Ledger or imports `events`, and `test_usage_reset` passes with its meter-event assertions removed and nothing added.
- [x] `CONTEXT.md`'s Outcome, Ledger and Running entries match what shipped; `references/architecture.md` and the `report.py` and `delegate.py` docstrings name `runs.py` as the Ledger's one writer.
- [x] `make test` is green on 3.9 and 3.13.

## Landed, 2026-10-11

**Commits.** `0563f5e` (delegate-deepening 04: Only the Run module writes the Ledger), then the review fixes in "delegate-deepening C: review fixes".

**What shipped.**
- `runs.py` owns the Ledger. The private `_start_line` and `_finish_line` build the v1 lines
  with today's keys in today's order, `_append` writes one, and `_ledger_path` resolves
  `$DELEGATE_LEDGER`, else `~/.cache/delegate/ledger.jsonl`. `execute` writes through them, and
  `running` reads the same path. `runs.py` no longer imports `events`.
- `scripts/events.py`, its CLI and `tests/test_events.py` are deleted. Nothing under `agents/`
  imports `events`.
- `usage.write_cache` writes only the usage cache. `usage.py` no longer imports `events`, and its
  docstrings no longer promise "no meter event". The Ledger records Runs only (decision C.2).
- `runs.LEDGER_ENV` names the variable that moves the Ledger. The offline evals set it for their
  sandbox, so no script but `runs.py` spells `DELEGATE_LEDGER`.
- Docs: the `runs.py`, `report.py` and `delegate.py` docstrings, and `references/architecture.md`,
  name `runs.py` as the Ledger's one writer. The `events.py` entry there is now "`runs.py` owns
  the Ledger", next to the line that probes write nothing to it. `CONTEXT.md` is unchanged: its
  Outcome (a native Run folded in), Ledger and Running entries already say what shipped.

**How it was verified.**
- test_runs 12, "the Ledger lines a Run writes keep their v1 keys, in order", runs three Runs: a
  done Run with a Class, a blocked Run with a worktree and no Class, and a hand-off. It compares
  each raw start and finish line, byte for byte, with the lines case 11's fixture builders
  (`v1_start`, `v1_finish`, lifted from case 11) spell. Only `ts` and the thread are taken from
  the written line. The case passed on the code before this ticket, through the `events.py`
  encoders, and passes after the move, so the encoding did not change. A mutant that swapped
  `effort` and `timeout_s` in the old encoder turned it red.
- test_runs 13, "no script but runs.py names DELEGATE_LEDGER or writes dispatch.json or
  return.json", was red first: `events.py` and `evals.py` named `DELEGATE_LEDGER`. It is green
  after this ticket. The scan also proves it is live: with `runs.py` not exempt it flags
  `runs.py`'s own writes, and in a temp directory it flags a planted Python writer and a planted
  shell script.
- test_usage_reset failed after the meter event went (`ledger file not found`). It passes with its
  meter-event Ledger assertions deleted and nothing added.
- `make test` is green with every proxy variable pointed at a closed port, on Python 3.9.25 and
  3.13.

**Deviations.**
- `evals.py` named `DELEGATE_LEDGER`, which the spec did not foresee: its offline sandbox points
  the Ledger at a temp file. The smallest change that keeps that isolation and the guard was the
  public constant `runs.LEDGER_ENV`. `evals.py` sets `self.env[runs.LEDGER_ENV]`.
- The guard is a static scan of `scripts/`, so "writes" has a definition. In one function or
  lambda, the scan looks for two things together:
  - a Run record's name: the string `dispatch.json` or `return.json`, or the attribute
    `dispatch_path` or `return_path`;
  - a write: `open` in a write mode, a call named for writing or dumping, `os.replace`, `rename`,
    `link` or `symlink`, or any `shutil` call.

  The return contract's schema (`assets/schemas/return.json`, joined with `"schemas"`) is not a Run
  record: `delegate.build_prompt` reads it. A script that is not Python may not name a Run record
  at all.
- The private encoders turn an empty class, write or session into null with `or None`. The deleted
  `events.opt_val` also turned `"-"` and `"null"` into null, but those were spellings of the
  deleted CLI, and no Python caller passes them. The lines are identical for every value dispatch
  passes.
- test_usage_reset: the clock check's `patch.object(usage, "append")` only silenced the old Ledger
  append, so it went with the meter event. The `$DELEGATE_LEDGER` temp setting stays as isolation.
- test_runs case 11 now builds its starts and its finish with `v1_start` and `v1_finish`. The
  strings are unchanged. Its comment now says that earlier delegates' probes wrote the meter
  event.
- Waiting on the user, outside this ticket: the ADR 0001 line for decision C.2 ("the Ledger
  records Runs only; the latest Meter reading lives in the usage cache") goes into the one ADR
  change after all lanes merge (Build plan, ADR edits).

**Review fixes.** `references/architecture.md` no longer says the cached usage read writes
no "meter event": no probe writes one now.
