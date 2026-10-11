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

**Status:** ready-for-agent

- [ ] `tests/test_runs.py` drives `execute` in-process against a temp run root, a temp `$DELEGATE_LEDGER` and a temp `$DELEGATE_CACHE`; no case uses `python -c` or monkeypatches `delegate`.
- [ ] Failing first, then green: "a Ledger that cannot be written never stops a Run ending" (`$DELEGATE_LEDGER` under a regular file; and a work that swaps the Ledger for a directory mid-run): `Ended` is done, `return.json` and `dispatch.json` are finished, a note names the Ledger. On the code before this ticket the same fixture through `delegate dispatch` leaves `dispatch.json` status null and exits with a traceback.
- [ ] Failing first, then green: "a return.json that cannot be written still ends dispatch.json and the Ledger" (the work makes `return.json` a directory and returns a done `Finish`): `dispatch.json` status blocked, reason names `return.json`, `finished_at` set, Ledger finish blocked.
- [ ] Failing first, then green: test_runs "SIGTERM during work ends the Run blocked as terminated" (the work signals its own pid; the previous handler is restored), and test_dispatch 12i (fake relay `hold=<tmp>/never`, `Popen`, SIGTERM once the start is in the Ledger): exit 1, `dispatch.json` blocked, a Ledger finish, and no `result.json` after the hold file is created.
- [ ] The SIGTERM conversion raises a private `BaseException` subclass, not an `Exception`, and the Meter hold is one private function in `runs.py`.
- [ ] test_runs "a usage-limit refusal holds the Lane's Meter, and a done or partial Run releases it" replaces test_dispatch 36.
- [ ] test_dispatch "a relayed Run refused for its usage limit holds that Lane's Meter" passes, and fails when the `Request` leaves `meter` out.
- [ ] test_dispatch 11, 12e (`python -c`) and 12f (`python -c`) are deleted; 12e's node wording is proved in-process by calling delegate's relay work with `PATH` lacking node; 28a-28c assert on the `Finish` `map_result` returns.
- [ ] The finish line, the `delegate-metrics` line (including `rc=None`), the `--json` summary and the exit codes are byte-identical: test_dispatch 1-10b, 12, 12d, 12g, 12h, 13-27c and 29b, 29d pass unchanged.
- [ ] `delegate.py` defines none of `ledger_start`, `ledger_finish`, `fail_run`, `start_failure`, `note_usage_limit`, `print_and_exit`, `Preflight` or `relay_and_map`, and does not import `events`.
- [ ] `make test` is green on `$(uv python find 3.9)` and `python3.13`.
