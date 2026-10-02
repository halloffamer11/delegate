# 10 — Evals for the delegate skill

**What to build:** the delegate skill has no evals (`council` has `evals.md`). The best-practices guide asks for at least three scenarios and a baseline before a rewrite, so tickets 12 and 19 can show they did not make routing worse. Scenarios to start from: classify and brief a worker-shaped task; dispatch on the ranked Lane and report the return; handle a failed or timed-out run without inventing a result.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] At least three scenarios with expected behaviour, in the format the `fresh-context` skill uses (`evals/evals.json` plus fixtures), runnable offline against the fake ADS relay.
- [ ] A baseline recorded for the current skill.
- [ ] One run on a Haiku-class and an Opus-class orchestrator, results recorded (Orin's box if it needs his machine).
