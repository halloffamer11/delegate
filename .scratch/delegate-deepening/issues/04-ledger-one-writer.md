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

**Status:** ready-for-agent

- [ ] `scripts/events.py` and `tests/test_events.py` are deleted; `grep -rn 'import events\|from events' agents/` finds nothing.
- [ ] test_runs: the Ledger lines a Run writes carry exactly the v1 keys in today's order, the same lines the C3 fixture reads.
- [ ] The guard case passes: only `runs.py` names `DELEGATE_LEDGER` or writes `dispatch.json` and `return.json`.
- [ ] `usage.py` no longer writes to the Ledger or imports `events`, and `test_usage_reset` passes with its meter-event assertions removed and nothing added.
- [ ] `CONTEXT.md`'s Outcome, Ledger and Running entries match what shipped; `references/architecture.md` and the `report.py` and `delegate.py` docstrings name `runs.py` as the Ledger's one writer.
- [ ] `make test` is green on 3.9 and 3.13.
