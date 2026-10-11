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

**Status:** ready-for-agent

- [ ] `evals.py`, `tests/test_dispatch.py` and `tests/test_relay.py` build the fake ADS tree, the pin answer, the CLI stubs and the env through `evals.OfflineWorld`, and `test_dispatch.py` has no `setup_env` world and no `pinned_ads_commit` of its own.
- [ ] `evals.OfflineWorld` exposes `world.stub(name, body)`, and `evals.py` keeps no second stub writer.
- [ ] The test_evals case with a refusing `sandbox-exec` after the world's bin directory passes, and it failed first with "codex cannot start its sandbox inside this shell's sandbox".
- [ ] `evals.py ping --offline` and `orchestrate --offline` still run end to end through node and the fake relay, and every relayed harness passes.
- [ ] `evals.RUN_FILES` names no relay file (no `result.json`, `relay.stdout` or `relay.stderr`).
- [ ] `make test` passes on Python 3.9 and 3.13.
