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

**Status:** ready-for-agent

- [ ] Failing first, then green: test_dispatch 29 asserts the native Run's `dispatch.json` has status `native` and a `finished_at` (null on the code before this ticket).
- [ ] test_runs "a hand-off ends the Run at once as native": no `return.json`, Ledger start and finish with status `native`, a held Meter stays held, `text()` is the native line then the spawn line, `text(as_json=True)` is the native object, `exit_code` 0.
- [ ] test_runs 7 parses a native line built by `Ended.text`, not by `runs.native_line`.
- [ ] test_dispatch 29a, 29b, 29c, 30 and 31e pass unchanged; the courier still gets `"native": true` and no `"return"`.
- [ ] `delegate log --run` on a native Run without `--secs` still asks for `--secs`.
- [ ] `make test` is green on 3.9 and 3.13.
