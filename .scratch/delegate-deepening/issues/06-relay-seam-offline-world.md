# 06 — The offline eval and the dispatch tests share one world that the host's Seatbelt never reaches

**What to build:** Candidate G, ticket G2 (lane run-and-relay). Collapse
`test_dispatch.setup_env` and `evals.Sandbox._build_offline_world` into one
`evals.OfflineWorld(root)`.
- The world holds the sample catalog and a fake ADS tree with the fake `relay.mjs` for
  each registry relay.
- Its bin directory holds a `git` stub that answers the pin read from `ads.sh` (with the
  `ADS_FAKE_GIT_SHA` override that case 12c uses), one stub per harness binary, a
  `sandbox-exec` stub that nests, and node, sh and python3 symlinks. It also creates a
  runs directory.
- It exposes `world.stub(name, body)`, moved from today's `Sandbox._stub`, so a test can
  replace one CLI: B3's logging agy probe stub and C's SIGTERM cases use it.
- Its env sets `PATH`, `DELEGATE_LEDGER`, `DELEGATE_CACHE`, `DELEGATE_MODEL_SCAN=off`,
  `ADS_DIR`, `DELEGATE_CODEX_HOME` and `DELEGATE_ORCHESTRATORS_DIR` (an empty directory
  in the world), and drops `DELEGATE_ORCHESTRATOR` and every profile's `detect_env`
  marker.

`evals.Sandbox(offline=True)` builds on the world and adds the meters fixture and the pong
final message. test_dispatch uses the world plus its worktree directory and
`DELEGATE_ORCHESTRATOR=claude`. test_relay's Ads cases use the world's `ads_dir` and env.
Change `evals.RUN_FILES` to the Run's own files (`dispatch.json`, `prompt.md`,
`return.json`), so the eval names no relay file.

Work red first: add the test_evals case "eval 1 offline: the host's Seatbelt never reaches
the offline world". It places a `sandbox-exec` stub that prints
`sandbox-exec: sandbox_apply: Operation not permitted` and exits 71 in a host directory
after the world's bin directory on the world's PATH, then expects
`evals.ping_one(world, 'codex')` to pass. It fails before this ticket. The offline evals
still run end to end through node, the fake relay and the real Ads path.

Spec: `.scratch/delegate-deepening/spec.md` (G. Relay seam; decision G.3)

**Blocked by:** 05 A relay that crashes before writing its result says why

**Status:** landed 2026-10-11 (c14e16e). `evals.OfflineWorld(root)` is the one offline world: the offline evals' `Sandbox`, test_dispatch and test_relay's Ads cases build on it, and its `sandbox-exec` that nests keeps the host's Seatbelt out. test_evals "eval 1 offline: the host's Seatbelt never reaches the offline world", "the offline world: no host orchestrator, marker or Ledger reaches its env, and a stub replaces a link" and "eval 3: Runs are equivalent by the Run's own files, with no relay file named" verify it, with test_dispatch's 50 cases unchanged. No box is open.

- [x] `evals.py`, `tests/test_dispatch.py` and `tests/test_relay.py` build the fake ADS tree, the pin answer, the CLI stubs and the env through `evals.OfflineWorld`, and `test_dispatch.py` has no `setup_env` world and no `pinned_ads_commit` of its own.
- [x] `evals.OfflineWorld` exposes `world.stub(name, body)`, and `evals.py` keeps no second stub writer.
- [x] The test_evals case with a refusing `sandbox-exec` after the world's bin directory passes, and it failed first with "codex cannot start its sandbox inside this shell's sandbox".
- [x] `evals.py ping --offline` and `orchestrate --offline` still run end to end through node and the fake relay, and every relayed harness passes.
- [x] `evals.RUN_FILES` names no relay file (no `result.json`, `relay.stdout` or `relay.stderr`).
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

**Commits.** `c14e16e` (delegate-deepening 06: The offline eval and the dispatch tests share one world that the host's Seatbelt never reaches), then the review fixes in "delegate-deepening G: review fixes".

**What shipped.**
- `scripts/evals.py`: `OfflineWorld(root)`. Under a root its caller owns, it holds the sample
  catalog, a fake ADS tree with the fake `relay.mjs` for each registry relay, an empty orchestrator
  profile directory and a runs directory. Its bin directory holds a `git` that answers the pin read
  from `ads.sh` (`$ADS_FAKE_GIT_SHA`, when set, in its place), one stub per harness binary, a
  `sandbox-exec` that nests, and links to the real node, sh and python3. `env` sets `PATH`,
  `DELEGATE_LEDGER`, `DELEGATE_CACHE`, `DELEGATE_MODEL_SCAN=off`, `ADS_DIR`,
  `DELEGATE_CODEX_HOME`, `DELEGATE_ORCHESTRATORS_DIR` and `DELEGATE_RUNS_DIR`, and drops
  `DELEGATE_ORCHESTRATOR` and every `detect_env` marker of the profiles the world loads.
  `world.stub(name, body)` is the one stub writer.
- `evals.Sandbox(offline=True)` builds its `world` on the Sandbox's root and adds the fixture Meters
  and the pong final message; `Sandbox._build_offline_world`, `_stub` and `Sandbox.bin_dir` are
  gone. `RUN_FILES` is the Run's own files: `dispatch.json`, `prompt.md`, `return.json`.
- `tests/test_dispatch.py` runs in the world plus its `worktree` directory, with
  `DELEGATE_ORCHESTRATOR=claude`. `setup_env`, `pinned_ads_commit`, `write_stub` and `remove_stub`
  are gone; 12g swaps `sandbox-exec` and 17 restores the grok CLI through `world.stub`.
- `tests/test_relay.py`'s Ads cases take the world's `ads_dir` and `env`.
- `references/architecture.md` names the world under the `relays.py` entry, and
  `references/maintenance.md` under the offline evals. CONTEXT.md names no term this ticket
  changed.

**How it was verified.**
- Red first: test_evals "eval 1 offline: the host's Seatbelt never reaches the offline world" puts
  a `sandbox-exec` that prints `sandbox-exec: sandbox_apply: Operation not permitted` and exits 71
  in a host directory after the world's bin directory on its PATH, and pings codex. Before the
  world it failed with `fail luna-low@codex: status blocked: blocked: codex cannot start its
  sandbox inside this shell's sandbox (...)`; it passes now.
- Red first: test_evals "eval 3: Runs are equivalent by the Run's own files, with no relay file
  named" compares two run directories that hold only the Run's files and one that lost its return.
  Before the change it failed with `missing relay.stdout`.
- test_evals "the offline world: no host orchestrator, marker or Ledger reaches its env, and a stub
  replaces a link" was written after the world. A mutation check turned it red when the marker drop
  was removed, and turned the Seatbelt case red when the nesting stub was removed.
- test_dispatch passes the same 50 cases it passed before the move (the PASS lines compared), and
  test_relay's s1 to s11 and a1 to a5 pass in the world.
- `evals.py ping --offline` passes claude, codex, agy and grok through node and the fake relay
  (kiro skips: the sample catalog has no kiro Lane), and `orchestrate --offline` passes claude,
  codex and kiro.
- `make test` is green with every proxy variable pointed at a closed port, on Python 3.9 and 3.13.

**Deviations.**
- The world's env also sets `DELEGATE_RUNS_DIR` to its runs directory, which the ticket's list
  leaves out, so a Run in the world that is given no `--runs-dir` never writes the host's runs root.
  The Sandbox sets it only for a live eval.
- The marker drop reads the profiles the world loads (the shipped ones plus its empty directory),
  not the host's own profile directory, so a broken host profile cannot stop a world being built.
- `world.stub` removes what is at the name first, so stubbing a linked tool (node, sh, python3)
  never writes through to the real binary; it returns the stub's path.
- The ticket's `evals.ping_one(world, 'codex')` is `evals.ping_one(sandbox, "codex")` on an
  offline Sandbox: a ping needs the Sandbox's brief and working directory, and the offline
  Sandbox's `env` is its world's `env`, so the refusing stub sits on the world's PATH. The case
  was written red against `sandbox.bin_dir` and moved to `sandbox.world.bin_dir` with the world.
- The pin reader is the private `evals._pinned_ads_commit`, and the git stub execs the host's own
  `git` (as the eval's did) rather than `/usr/bin/git`.
- test_dispatch's `run_dispatch` and `run_run` share `run_delegate(world, command, args, ...,
  config_dir=)`, which replaces the copied `t_env` dicts cases 27a and 31f used for their own
  catalogs.

**Review fixes.** The G review found that test_dispatch and test_relay each built their own PATH
without node, a directory of links to the world's bin directory: a second copy of part of the
world, as the spec's problem names. `world.path_without(name)` now builds that PATH once, and
test_dispatch 9, 12d and 29c and test_relay a5 and a7 use it.
