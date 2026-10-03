# 10 — Evals for the delegate skill

**What to build:** three evals that prove delegate works end to end, as Orin set them out in review on 2026-10-02. They are the baseline that tickets 12, 13 and 19 must keep passing. The delegate skill has none today (`council` has `evals.md`).

1. **Ping-pong on every detected harness.** For each harness whose CLI is installed, `delegate run` sends a trivial job ("reply pong") on one of its Lanes, and it comes back with a valid `return.json`. A harness that is not installed is reported as skipped, not failed.
2. **Gate and load balancing, on simulated usage.** Fixture Meters at chosen Remaining percentages drive `rank`: a Lane under the Gate is vetoed, Pace picks between Lanes in a Tier, and Margin decides when a Lane steals the Pick. Each case states the expected Pick. Offline and deterministic: no vendor probe.
3. **Orchestration from any harness.** The same ping-pong job, sent through the skill from Claude Code and from Codex (and any other detected harness that can orchestrate), produces an equivalent run directory and `return.json`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-any-harness-next-v75vlw`); the first three boxes are done. Waiting on Orin for the last box: run `make eval-ping` and `make eval-orchestrate` once on the Mac. The orchestrator commands in `scripts/evals.py` (`claude -p "/delegate …"`, `codex exec …`) are the documented headless forms and are unverified until that run. Raised by Orin 2026-10-02; scenarios set by Orin in review the same day.

What landed: `scripts/evals.py` (`ping`, `orchestrate`, each with `--offline`), `make eval-ping` and `make eval-orchestrate`, and `tests/test_evals.py`, which runs eval 2 (six routing cases) and evals 1 and 3 offline in `make test`. A run directory now also honours `$DELEGATE_RUNS_DIR`, so an orchestrator started by the eval writes where the eval looks. Until ticket 13 a claude Lane is native, so eval 1 reports it as skipped. Verified with `make test` on Python 3.9 and 3.13.

- [x] Eval 2 runs offline in `make test` (fixture Meters, no network) and covers Gate veto, Pace order and a Margin steal.
- [x] Evals 1 and 3 have one command each (`make eval-ping`, `make eval-orchestrate` or similar) that runs on whatever harnesses the machine has and prints one pass, skip or fail line per harness.
- [x] Evals 1 and 3 also run offline against the fake ADS relay (`tests/fake-ads/`), so a machine with no CLIs still exercises the path.
- [ ] Orin runs evals 1 and 3 once on the Mac and records the result here (Orin's box).
