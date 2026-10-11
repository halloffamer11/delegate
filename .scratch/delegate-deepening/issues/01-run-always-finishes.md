# 01 — A started Run always finishes

**What to build:** Candidate C, ticket C1 (lane run-and-relay, its first ticket). In
`runs.py`, add the Run module's interface: `Request`, `Finish`, `blocked()`, `Ended`,
`StartError` and `execute(request, prompt, work, runs_dir)`. `Finish` is the one type for
how relayed work ended (G's `Relay.run` will return it), and every field of it but
`returned` is a `DISPATCH_FIELDS` outcome key.

`execute` does the following, in order:
- Creates the Run: the directory, `prompt.md` and `dispatch.json`.
- Appends the Ledger start through the existing `events.py` encoders, called only from
  `runs.py` (C4 moves them in).
- Installs a SIGTERM handler while `work` runs (main thread only) and calls `work(run)`.
  The handler raises a private subclass of `BaseException`, as `KeyboardInterrupt` is, so
  no `except Exception` inside the work can swallow it; the previous handler comes back
  afterwards.
- Turns any `BaseException` from the work into `blocked()` with its reason: dispatch
  failed / dispatch interrupted / dispatch terminated (SIGTERM).
- Writes `return.json`, then the outcome in `dispatch.json`. The outcome is written even
  when `return.json` fails; the status is then blocked with reason `could not write
  return.json`.
- Settles the Meter hold in one private function, moved here from
  `delegate.note_usage_limit`. It calls `usage.mark_limited`/`clear_limited`; B1 later
  swaps that one function to `usage.hold`/`release`.
- Appends the Ledger finish.
- Collects every failed write as a note and never raises after the start.

Migrate the relayed branch of `delegate.dispatch`:
- The work is today's `relay_and_map`.
  - A preflight reason returns `blocked(reason)`.
  - A `FileNotFoundError` for node returns
    `blocked("node is not on PATH; the relay needs Node.js")`.
  - It still calls `run_relay` by name, so test 34c keeps working until B3 rewrites it.
- `map_result` returns a `Finish` and writes nothing.
- `dispatch` prints the notes to stderr and `Ended.text(as_json)` to stdout, then exits
  with `exit_code`.
- A `StartError` exits 2.

Add the wiring test the review found missing: test_dispatch "a relayed Run refused for
its usage limit holds that Lane's Meter". A grok lane's fake relay fails with grok's
usage-limit words; afterwards `limits.json` beside `$DELEGATE_CACHE` holds `grok`. test_runs
proves that `execute` settles the hold; this case proves that dispatch hands it the Lane's
meter, so check once that it fails when the `Request` leaves `meter` out.

Delete these:
- `delegate.ledger_start`, `ledger_finish`, `fail_run`, `start_failure`,
  `note_usage_limit`, `print_and_exit`, `Preflight` and `relay_and_map`;
- `runs.Run.finish`, `Run.fail`, `summary` and `finish_line`.

The native branch stays as it is (C2).

Spec: `.scratch/delegate-deepening/spec.md` (C. Run lifecycle; decisions C.3 and C.5)

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-11. `runs.execute` now runs every relayed Run from its start to its Outcome, and `delegate.dispatch` hands it `delegate.relay_work`; test_runs 1-7 and test_dispatch 12e, 12i, 28a-28c and 37 verify it. No box is open.

- [x] `tests/test_runs.py` drives `execute` in-process against a temp run root, a temp `$DELEGATE_LEDGER` and a temp `$DELEGATE_CACHE`; no case uses `python -c` or monkeypatches `delegate`.
- [x] Failing first, then green: "a Ledger that cannot be written never stops a Run ending" (`$DELEGATE_LEDGER` under a regular file; and a work that swaps the Ledger for a directory mid-run): `Ended` is done, `return.json` and `dispatch.json` are finished, a note names the Ledger. On the code before this ticket the same fixture through `delegate dispatch` leaves `dispatch.json` status null and exits with a traceback.
- [x] Failing first, then green: "a return.json that cannot be written still ends dispatch.json and the Ledger" (the work makes `return.json` a directory and returns a done `Finish`): `dispatch.json` status blocked, reason names `return.json`, `finished_at` set, Ledger finish blocked.
- [x] Failing first, then green: test_runs "SIGTERM during work ends the Run blocked as terminated" (the work signals its own pid; the previous handler is restored), and test_dispatch 12i (fake relay `hold=<tmp>/never`, `Popen`, SIGTERM once the start is in the Ledger): exit 1, `dispatch.json` blocked, a Ledger finish, and no `result.json` after the hold file is created.
- [x] The SIGTERM conversion raises a private `BaseException` subclass, not an `Exception`, and the Meter hold is one private function in `runs.py`.
- [x] test_runs "a usage-limit refusal holds the Lane's Meter, and a done or partial Run releases it" replaces test_dispatch 36.
- [x] test_dispatch "a relayed Run refused for its usage limit holds that Lane's Meter" passes, and fails when the `Request` leaves `meter` out.
- [x] test_dispatch 11, 12e (`python -c`) and 12f (`python -c`) are deleted; 12e's node wording is proved in-process by calling delegate's relay work with `PATH` lacking node; 28a-28c assert on the `Finish` `map_result` returns.
- [x] The finish line, the `delegate-metrics` line (including `rc=None`), the `--json` summary and the exit codes are byte-identical: test_dispatch 1-10b, 12, 12d, 12g, 12h, 13-27c and 29b, 29d pass unchanged.
- [x] `delegate.py` defines none of `ledger_start`, `ledger_finish`, `fail_run`, `start_failure`, `note_usage_limit`, `print_and_exit`, `Preflight` or `relay_and_map`, and does not import `events`.
- [x] `make test` is green on `$(uv python find 3.9)` and `python3.13`.

## Landed, 2026-10-11

**What shipped.**
- `runs.py` is the Run module. It defines `Request`, `Finish`, `blocked()`, `Ended` and
  `StartError`, and `execute(request, prompt, work, runs_dir)` runs the writes in order:
  - before the work: the run directory, `prompt.md`, `dispatch.json` with a null outcome,
    and the Ledger start;
  - after it: `return.json`, the outcome, the Meter settle and the Ledger finish.

  Each write after the start that fails becomes a note.
- How the work stops decides the reason:
  - an `Exception` gives `dispatch failed: <Type>: <message>`;
  - a `KeyboardInterrupt` gives `dispatch interrupted`;
  - SIGTERM raises the private `BaseException` subclass `_Terminated`, which gives
    `dispatch terminated (SIGTERM)`. `subprocess.run` then kills the relay.
- A result that is not a `Finish`, or a return without the five fields and a known status,
  ends blocked with a reason that starts `dispatch failed:`.
- The Meter hold is the private `_settle_meter`. It calls `usage.mark_limited` and
  `clear_limited`.
- `parse_timeout_s` is now the private `runs._timeout_s`.
- `Run.finish`, `Run.fail`, `summary` and `finish_line` are gone.
- `delegate.dispatch` builds a `Request` that carries the Lane's meter and calls `execute`
  once. It prints the notes as `delegate: <note>` on stderr and `Ended.text(as_json)` on
  stdout, then exits with `exit_code`. A `StartError` prints one line and exits 2.
- The relayed work is `delegate.relay_work(...)`. It returns `blocked(reason)` for a
  preflight reason and `blocked("node is not on PATH; the relay needs Node.js")` when node is
  missing. It still calls `run_relay` by name, for 34c. `map_result` returns a `Finish` and
  writes nothing.
- `delegate.py` no longer defines `ledger_start`, `ledger_finish`, `fail_run`,
  `start_failure`, `note_usage_limit`, `print_and_exit`, `Preflight` or `relay_and_map`, and
  no longer imports `events`.
- The native branch is unchanged. `Run.create` and `Run.thread_id` stay public until 02, and
  so do `native_line` and `native_summary`; `Run.create` starts through the same private
  `_start` as `execute`. `references/architecture.md` describes the Run module.

**How it was verified.**
- New test_runs cases, all in-process:
  - 1: a Run that returns;
  - 2: work that raises;
  - 3: SIGTERM;
  - 4: a `return.json` that cannot be written;
  - 5: a Ledger that cannot be written;
  - 6: the usage-limit hold;
  - 7: a runs root that cannot be made.

  They went green with code written ahead of them. Each was then shown red by disabling its
  piece of `execute`, one at a time: the interrupt wording; the SIGTERM trap; `_Terminated`
  as an `Exception`; the handler restore; the return.json status change; each Ledger guard;
  the settle; `StartError`.
- Before this ticket, case 5's fixture through `delegate dispatch` (`$DELEGATE_LEDGER` under
  a regular file) left `dispatch.json` status null and exited 1 with a traceback.
- Before this ticket, test_dispatch 12i got exit -15, a null `dispatch.json` and no Ledger
  finish, and the orphaned relay wrote `result.json` once the hold file appeared.
- test_dispatch 37, "a relayed Run refused for its usage limit holds that Lane's Meter",
  fails when the `Request` leaves `meter` out.
- A direct comparison of the old and new `delegate dispatch` output matched byte for byte,
  with run directories and threads masked. It covered stdout, stderr and the exit code for
  done, failed, the grok hold note, the agy override, and a preflight block (`rc=None`),
  each with and without `--json`.
- `make test` is green with every proxy variable pointed at a closed port, on Python
  3.9.25 and 3.13. test_runs and test_dispatch passed three times in a row on each.

**Deviations.**
- The SIGTERM trap is installed just before the Ledger start, not only while the work runs.
  The spec's window left a gap between the start and the work where a SIGTERM killed
  dispatch, and 12i sends its SIGTERM in that gap. The previous handler still comes back
  right after the work.
- test_runs numbering: the `execute` cases use the spec's numbers 1-7. Today's parse and root
  cases became p6, p7 and p8, so "test_runs 7" in ticket 02 means p7, the native-line parse.
  The dispatch wiring case is test_dispatch 37; 36 was deleted.
- 12d is unchanged except that its setup now assigns `ledger_path`, which the deleted 11
  used to set.
- `test_setup.py` `case_the_refreshed_rows_reach_the_new_lanes` now passes the Epoch fixture
  to `bench.collect`. On the base commit it fetched the live Epoch CSV, which is spec H live
  bug 3, so `make test` under the closed proxy failed on both interpreters before this
  ticket changed anything. Ticket 27 rewrites that same line to `epoch_rows=None`; the
  rebase is one line.
- Behaviour that changed with no test asking for it:
  - An unreadable Lane timeout used to raise from `ledger_start`. It is now a note about the
    Ledger start.
  - A failed Meter settle used to pass silently. It is now a note.
  - When `return.json` cannot be written, the `--json` object's `return` is null.
- `CONTEXT.md` is unchanged. Two of its entries describe this lane's later tickets:
  - Outcome's native Run becomes true with 02.
  - The Ledger's "only the Run module writes it" becomes true with 04, which removes
    `usage.py`'s meter events.
- Risk: a `KeyboardInterrupt` that lands in the few milliseconds of writes after the work is
  not caught, like SIGKILL.
