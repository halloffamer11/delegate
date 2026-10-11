# 05 — A relay that crashes before writing its result says why

**What to build:** Candidate G, ticket G1 (lane run-and-relay, after all of C). Add
`agents/skills/delegate/scripts/relays.py` with `Job`, `Report`, `Relay.run`, the `Ads`
adapter and the `Scripted` fake; `check` comes in G3. `Relay.run` and the private
`_settle(report, job)` return C's `runs.Finish`; `relays.py` defines no outcome type of
its own.

`Ads` takes over `run_relay`: node, the relay path, the common flags plus
`Harness.run_args`, the env overrides, `relay.stdout` and `relay.stderr`, and the timing.
It also takes over the reading half of `map_result`: the `result.json` keys, the stderr
line when there is no result, and `Harness.blocked_reason` for a completed job.
- A spawn failure returns a blocked Finish reading
  "node is not on PATH; the relay needs Node.js", with `relay_exit` None.
- When no `result.json` was written, the reason takes the line where node names the
  uncaught error (`<Name>Error: ...`), else the last nonblank stderr line, and never
  node's `Node.js v...` trailer.
- A `result.json` that does not parse or is not an object reads as failed with
  "corrupt result.json: ..." and keeps the relay's exit.
- `Ads` catches only `OSError` and `ValueError` around the spawn and the result, stderr
  and events reads, never bare `Exception` or `BaseException`, so `KeyboardInterrupt` and
  the Run's SIGTERM termination pass through to `runs.execute`.

Settling becomes the private pure function `_settle(report, job)`, which absorbs the old
status table and `find_return_block`. In `delegate.dispatch`, the relayed work that
`runs.execute` calls keeps the preflight and both probes and ends with
`return relays.Ads(ads_dir).run(job, run.path)`; `runs.execute` records the Finish, the
Ledger and the Meter hold. Until G4 the Finish carries `usage`, the relay's raw record.

Extend `tests/fake-ads/relay.mjs` with `crash=<message>` (throw before `result.json`) and
`replay=<dir>` (copy a run directory's relay files into `--out-dir` and exit with its
`exitCode`), and add both words to the error directive's lookahead.

Work red first. Add test_dispatch cases 6b (crash) and 6c (a staged replay whose
`result.json` is `[]` with exit 0) and see both fail against the code before this
ticket. Then land the module, then move both cases into the new `tests/test_relay.py` as
Ads cases. Until G2, `tests/test_relay.py` takes its fake ADS tree from
`evals.Sandbox(offline=True)`.

Also:
- Move the settling table from test_dispatch into test_relay through `Scripted`, and
  replay the grok gate-cancel fixture through `Ads` in place of calling `map_result`.
- Move C1's in-process node-missing case (which replaced 12e) to test_relay as Ads
  node-missing, and delete the relayed work's own node branch.
- Retarget 34c's patch from `delegate.run_relay` to `relays.Ads._launch`, unless B3 has
  already rewritten 34c to count probes without patching. (C1 deleted 12f.)
- Add a test_runs case: SIGTERM delivered inside a relay adapter's `run` (a test-only
  `Scripted` subclass that signals its own pid there) ends the Run "dispatch terminated
  (SIGTERM)".
- Move the status-table docstring to `relays.py`, and update `references/architecture.md`
  where it names `map_result` and `run_relay`.

Spec: `.scratch/delegate-deepening/spec.md` (G. Relay seam; decisions G.5 and G.6)

**Blocked by:** 01 A started Run always finishes (`runs.Finish`, `runs.execute`); 04 Only the Run module writes the Ledger (lane order: all of C before G)

**Status:** ready-for-agent

- [ ] `relays.Ads(...).run` and `relays.Scripted(...).run` each return a `runs.Finish`; `relays.py` defines no outcome type; `delegate.py` no longer defines `run_relay`, `map_result` or `find_return_block`.
- [ ] Every settling row is tested through `Scripted` in `tests/test_relay.py` with no subprocess and no node: done, partial, prose, empty, timeout, failed, aborted, unavailable, nothing reported, stopped short, and the tripwire.
- [ ] A relay that throws before `result.json` yields "blocked: relay wrote no result (exit 1): Error: <message>"; case 6b failed first against the "Node.js v" line.
- [ ] A `result.json` that is not an object yields a blocked Finish with `relay_exit` kept and no `AttributeError` in the reason; case 6c failed first.
- [ ] The grok gate-cancel fixture and its two variants (no cancelled tool, empty final message) are replayed through `Ads`, and nothing calls a mapping function directly.
- [ ] Node missing at spawn returns a blocked Finish with `relay_exit` None and raises nothing, tested in test_relay; no test patches node away with `python -c`.
- [ ] test_relay asserts that every Finish field except `returned` is in `runs.DISPATCH_FIELDS` and that `returned` has exactly `runs.RETURN_FIELDS`.
- [ ] test_runs: SIGTERM delivered inside a relay adapter's `run` ends the Run "dispatch terminated (SIGTERM)"; `Ads` has no bare `except Exception` or `except BaseException`.
- [ ] `make test` passes on Python 3.9 and 3.13.
