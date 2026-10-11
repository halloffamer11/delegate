# 07 — Only the ADS adapter knows node, the pin and the relay argv

**What to build:** Candidate G, ticket G3 (lane run-and-relay). Add `Relay.check`:
`Ads.check` runs `sh ads.sh check` with `ADS_DIR` set to the adapter's resolved directory
and returns the first line it printed on failure, or None. `Scripted.check` returns its
`ready`. Add `relays.DEFAULT_DIR` and resolve the directory once in `Ads` (the argument,
else `$ADS_DIR`, else the default). `resolve()` asks the relay's check for a relayed Lane
in place of its own subprocess, and `resolved['ads_dir']` goes away.

`delegate.dispatch` and `delegate.run` take `relay=None`, which defaults to
`relays.Ads(ads_dir)`, so a caller can hand in a `Scripted` fake in-process; C's
in-process Run tests can use it. Add a one-line comment in `ads.sh` pointing to
`relays.DEFAULT_DIR`.

In test_relay, test `check` against the world with the right pin, a wrong pin
(`ADS_FAKE_GIT_SHA`), node missing, and a missing relay script. Test argv and env per
harness through `Ads.run` with the fake relay's `argv.json` and `env.json`; these replace
test_dispatch 9a to 9h, 9a2, the argv half of 24, and 31f. Add a test that `DEFAULT_DIR`
equals `ads.sh`'s `ADS_DIR` default. In test_dispatch, add one in-process case that runs
dispatch with `relay=Scripted(...)` and asserts the Job the fake received (harness,
model, an `--effort` override, write and cwd); it replaces 9b. Keep 12c and 12d as
end-to-end wiring.

Spec: `.scratch/delegate-deepening/spec.md` (G. Relay seam; decision G.4)

**Blocked by:** 05 A relay that crashes before writing its result says why; 06 The offline eval and the dispatch tests share one world that the host's Seatbelt never reaches

**Status:** landed 2026-10-11 (72598af). `relays.Ads.check` runs `ads.sh check` on the adapter's resolved directory (the argument, else `$ADS_DIR`, else `relays.DEFAULT_DIR`), `Scripted.check` answers its `ready`, and `delegate.resolve` asks the relay's check in place of its own subprocess; `dispatch` and `run` take `relay=None`. test_relay s12, a6 (argv and env per harness), a7 (check) and a8 (the default directory), and test_dispatch 9 (the Job through `dispatch(relay=Scripted(...))`), verify it. No box is open.

- [x] `delegate.py` runs no `sh ads.sh` and names no ADS directory.
- [x] `relays.Ads.check` returns None on the pinned world, and one line naming the cause for a wrong pin, a missing node and a missing relay script.
- [x] A dispatch whose relay check refuses exits 2 with no run directory and no Ledger start (12c and 12d still pass end to end).
- [x] The argv and env cases run through `relays.Ads` in test_relay, and 9a to 9h, 9a2, the argv half of 24 and 31f are deleted from test_dispatch.
- [x] `delegate.dispatch(..., relay=relays.Scripted(...))` runs in-process with no node, and a test reads the Job the fake received.
- [x] A test asserts that `relays.DEFAULT_DIR` equals the `ADS_DIR` default in `ads.sh`.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

**Commits.** `72598af` (delegate-deepening 07: Only the ADS adapter knows node, the pin and the relay argv).

**What shipped.**
- `scripts/relays.py`: `Relay.check()`, `relays.DEFAULT_DIR` and `Scripted(*script, ready=None)`.
  `Ads(ads_dir=None, env=None)` resolves its directory once: the argument, else the env's
  `$ADS_DIR`, else `DEFAULT_DIR`. `Ads.check` runs `sh ads.sh check` with `ADS_DIR` set to that
  directory and returns None, or the first line the check printed. `Scripted.check` returns
  `ready`.
- `scripts/delegate.py`: `resolve()` takes the relay and asks `relay.check()` for a relayed Lane
  (a refusal prints its line and exits 2 before a Run starts); `resolved["ads_dir"]`, the
  `sh ads.sh check` subprocess, the repeated default and the `subprocess` import are gone.
  `dispatch` and `run` take `relay=None`, which defaults to `relays.Ads(ads_dir)`, and
  `relay_work` runs `relay.run(job, run.path)`. `--ads-dir` still reaches `relays.Ads`.
- `scripts/ads.sh`: a one-line comment at the `ADS_DIR` default names `relays.DEFAULT_DIR` and the
  test that holds the two equal.
- `references/architecture.md`: the `runs.py` and `relays.py` entries name the check, the default
  directory, `dispatch(relay=...)` and `Scripted`'s `ready`. CONTEXT.md's Relay and ADS entries
  stay true as written.

**How it was verified.**
- Red first: test_relay s12 failed with `Scripted.__init__() got an unexpected keyword argument
  'ready'`, a7 with `'Ads' object has no attribute 'check'`, a8 with `module 'relays' has no
  attribute 'DEFAULT_DIR'`, and test_dispatch 9 with `dispatch() got an unexpected keyword
  argument 'relay'`. a6 passed at once, as moved cases of the existing argv should.
- test_relay, new: s12 (Scripted's check answers None or its line and runs nothing); a6 (the exact
  flag set and `CODEX_HOME` Ads hands each harness's relay, read from the fake relay's
  `argv.json` and `env.json`: codex read-only, write and with a codex home of delegate's own,
  agy read-only under an effort override and write, claude, grok and kiro, and no argv with
  `--lane`, `--max-turns` or `--max-budget-usd`); a7 (check is None on the pinned world, and one
  line naming a wrong pin, no node, and a missing grok relay in a torn copy of the tree that the
  env's `$ADS_DIR` does not name); a8 (`DEFAULT_DIR` equals what `sh ads.sh path` prints with
  `ADS_DIR` unset, and Ads resolves the argument, else `$ADS_DIR`, else the default).
- test_dispatch 9, in-process with no node on PATH: `dispatch(relay=Scripted(...))` with
  `--effort low` and `--write` hands the fake exactly `Job(codex, gpt-5.6-terra, low, 25m,
  <run>/prompt.md, cwd=<worktree>, write=<worktree>)` and the Run's `return.json` is the scripted
  return; a `Scripted(ready=...)` refusal exits 2 with its line on stderr, no run directory, no
  Ledger line and no job. 12c and 12d pass end to end through `Ads.check`.
- Deleted from test_dispatch: 9a to 9h, 9a2, the argv half of 24 and 31f. The PASS lines differ
  from before only there.
- A mutation check turned each new case red: the Job's `write` dropped (9), the refusal's
  `sys.exit(2)` dropped (9, 12c and 12d), `ADS_DIR` not set for the check (a7), the codex env
  override dropped (a6), a different `DEFAULT_DIR` (a8), and a multi-line check answer (a7).
- `evals.py ping --offline` still passes claude, codex, agy and grok through node and the fake
  relay. `make test` is green with every proxy variable pointed at a closed port, on Python 3.9
  and 3.13.

**Deviations.**
- `Ads.check` also answers when `sh` cannot start (`ads: cannot run ads.sh check: <error>`) or
  the check fails having printed nothing (`ads: ads.sh check failed (exit <n>)`), so a refusal
  always has a line.
- `Ads` makes `$ADS_DIR` absolute too; `resolve` used to leave the env's value as given.
- `resolve(..., relay, ...)` takes the relay where it took `ads_dir`, and `relay_work` takes the
  relay where it took `ads_dir`.
- 24 keeps its stderr half ("24. agy --effort ignored"), and 33, which read 9e's agy write prompt,
  dispatches its own agy write Run.
- Case 9 also refuses through `Scripted(ready=...)` in-process, beside 12c and 12d end to end.
- `Harness.run_args` reads codex's home from this process's environment, not from the env handed
  to `Ads`; under the CLI the two are one. a6 therefore sets `DELEGATE_CODEX_HOME` in the test
  process for each row (`process_env`), and hands Ads an env with no `CODEX_HOME`.
- a6 compares each harness's whole flag set, order aside, so 9h's forbidden flags are covered by
  equality as well as by their own check.
