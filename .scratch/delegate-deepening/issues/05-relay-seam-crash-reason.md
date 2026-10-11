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

**Status:** landed 2026-10-11. `scripts/relays.py` holds the Relay seam (`Job`, `Report`, `Relay.run`, the `Ads` adapter, the `Scripted` fake and the private pure `_settle`), and the relayed work in `delegate.py` runs the relay through `relays.Ads(ads_dir).run(job, run.path)`; test_relay s1 to s11 (settling through Scripted) and a1 to a5 (Ads under node), and test_runs 3b, verify it. No box is open.

- [x] `relays.Ads(...).run` and `relays.Scripted(...).run` each return a `runs.Finish`; `relays.py` defines no outcome type; `delegate.py` no longer defines `run_relay`, `map_result` or `find_return_block`.
- [x] Every settling row is tested through `Scripted` in `tests/test_relay.py` with no subprocess and no node: done, partial, prose, empty, timeout, failed, aborted, unavailable, nothing reported, stopped short, and the tripwire.
- [x] A relay that throws before `result.json` yields "blocked: relay wrote no result (exit 1): Error: <message>"; case 6b failed first against the "Node.js v" line.
- [x] A `result.json` that is not an object yields a blocked Finish with `relay_exit` kept and no `AttributeError` in the reason; case 6c failed first.
- [x] The grok gate-cancel fixture and its two variants (no cancelled tool, empty final message) are replayed through `Ads`, and nothing calls a mapping function directly.
- [x] Node missing at spawn returns a blocked Finish with `relay_exit` None and raises nothing, tested in test_relay; no test patches node away with `python -c`.
- [x] test_relay asserts that every Finish field except `returned` is in `runs.DISPATCH_FIELDS` and that `returned` has exactly `runs.RETURN_FIELDS`.
- [x] test_runs: SIGTERM delivered inside a relay adapter's `run` ends the Run "dispatch terminated (SIGTERM)"; `Ads` has no bare `except Exception` or `except BaseException`.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

**What shipped.**
- `scripts/relays.py`: `Job`, `Report`, `Relay.run` (`_settle(self._launch(job, run_dir), job)`),
  `Ads(ads_dir, env=None)` and `Scripted(*script)` with `jobs`. Both adapters return a
  `runs.Finish`; the module defines no outcome type. `Ads` took over `run_relay` (node, the relay
  path, the common flags plus `Harness.run_args`, the env overrides, `relay.stdout`,
  `relay.stderr`, the timing) and the reading half of `map_result` (every `result.json` key, the
  stderr line when there is no result, `Harness.blocked_reason` for a completed job). Settling is
  the private pure `_settle(report, job)`, with the return-block scan, the caps, the tripwire and
  the status table, whose docstring moved here from `delegate.py`.
- `delegate.py` no longer defines `run_relay`, `map_result` or `find_return_block`, nor the
  relayed work's own node branch. The relayed work keeps the preflight and both probes and runs
  the relay through `relays.Ads(ads_dir).run(job, run.path)`; `runs.execute` records the Finish,
  the Ledger and the Meter hold. The Finish still carries `usage`, the relay's raw record (G4).
- The fake relay takes `crash=<message>` (throws before `result.json`) and `replay=<dir>`, and
  both words are in the error directive's lookahead.
- `references/architecture.md` has a `relays.py` entry, and no longer names `map_result` or
  `run_relay`. CONTEXT.md's Relay, Return and Stopped short entries stay true as written.

**How it was verified.**
- Red first: test_dispatch 6b failed with `blocked: relay wrote no result (exit 1): Node.js
  v22.22.0`, and 6c failed with `dispatch failed: AttributeError: 'list' object has no attribute
  'get'` and `relay_exit` None. Both passed through the new module, then moved to test_relay as
  a1 ("a relay that throws before result.json is blocked with node's error line"; it also checks
  that node's stderr did end with the `Node.js v` trailer) and a2 ("a result.json that is not an
  object is blocked and keeps the relay's exit", plus one that does not parse).
- test_relay, new: s1 to s9 settle every row through `Scripted` with no node and no subprocess
  (done within its caps, partial and blocked blocks, prose, empty, timeout naming the Lane's
  timeout, failed, aborted and unavailable, nothing reported and an unknown status, stopped short
  with a block winning over the stop, the tripwire on read-only jobs only). s10 covers Scripted
  raising what it was scripted to and failing on an exhausted script, and s11 checks that settling
  wrote nothing. a3 replays the grok gate-cancel fixture and its two variants through `Ads`. a4
  reads the session under each spelling, the error or stderr tail, and the other keys. a5 is node
  missing at spawn. Every case checks the Finish against `runs.DISPATCH_FIELDS` and
  `runs.RETURN_FIELDS`. A mutation check (evidence cap 13, the tripwire on write jobs, the first
  stderr line in place of node's error line) turned s1, s9 and a1 red.
- test_runs 3b: a test-only `Scripted` subclass signals its own pid inside `run`, and the Run
  ends "dispatch terminated (SIGTERM)". The same case scans `relays.py` for a bare `except` or one
  naming `Exception` or `BaseException`, and proves the scan finds each in a planted snippet.
- Moved out of test_dispatch: the settling table (2a to 2c, 3, 4a to 4c, 5, 6, 13), 6b and 6c,
  C1's in-process node-missing case 12e, and 28a to 28c with `stage_run` and `RUN_FIXTURES_DIR`.
  34c now patches `relays.Ads._launch` (B3 has not rewritten it in this lane).
- `make test` is green with every proxy variable pointed at a closed port, on Python 3.9 and
  3.13.

**Deviations.**
- The relayed work keeps its after-probe, so it runs `relays.Ads(ads_dir).run(job, run.path)`,
  probes, then returns that Finish. Ending on a literal `return relay.run(...)` would have dropped
  the probe the ticket keeps.
- `Ads` takes the directory `resolve()` already resolved; `relays.DEFAULT_DIR`, the default
  resolution and `Scripted(ready=)` come with `check` in G3.
- With nothing on stderr, the no-result reason drops the dangling colon: `relay wrote no result
  (exit 2)`, where `map_result` wrote `relay wrote no result (exit 2):`.
- A `result.json` that is not an object reads `corrupt result.json: a JSON list, not an object`.
  An OSError at spawn that is not node's own reads `relay could not start: <error>`.
- Node missing at spawn records `secs` 0, which Ads measured, where C1's branch left it null for
  the Run to measure.
- `Ads` asks `Harness.blocked_reason` for every completed relay, not only when the final message
  has no block. Settling prefers the block, so every outcome is unchanged.
- Inside settling, the return-block scan catches `ValueError` and `RecursionError` (a deeply
  nested final message), and the evidence conversion catches `TypeError`, `ValueError` and
  `OverflowError`; `map_result` caught `Exception` in both places. The broad-handler scan covers
  all of `relays.py`. A `result.json` nested too deep to parse raises `RecursionError`, which `Ads`
  does not catch (it catches only `OSError` and `ValueError`), so that Run ends "dispatch failed:
  RecursionError: ...".
- `replay=<dir>` copies `result.json`, `events.jsonl` and `final.txt`, and writes the staged
  `relay.stdout` and `relay.stderr` to its own streams, because dispatch holds those two files
  open. It exits with `exit=<n>` when given, else the staged result's `exitCode`, else 0.
