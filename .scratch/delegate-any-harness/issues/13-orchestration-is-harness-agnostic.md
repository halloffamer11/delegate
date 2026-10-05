# 13 — Orchestration is harness-agnostic

**What to build:** delegate makes no assumption about which harness is orchestrating. Today `ORCHESTRATOR="claude"` (`delegate.py:62`, `:762`, `:883`) is a constant, and native Lanes, the agent files in `~/.claude/agents` (`setup.py:31`, `:434-500`), the courier and the spawn instruction in `SKILL.md:86` all assume Claude Code. Do not replace that with a second hardcoded orchestrator; remove the special case.

- **One default path for every orchestrator.** Any harness that can run a shell and read files orchestrates the same way: `delegate run` relays the job, and the orchestrator reads the run directory. This path needs no knowledge of the caller, and it is what an unknown or new harness gets.
- **Native Lanes are an optional capability, declared as data.** An orchestrator profile says whether its harness can run a Lane in-process, where its agent files live, their template, and the one-line spawn instruction the skill prints. Claude Code is the first profile, not a code path. No orchestrator name appears in the scripts.
- **The orchestrator is detected, never assumed.** From the environment or a `--orchestrator` flag; anything unrecognised falls back to the default path.
- The courier and the statusline become optional extras that read the same run directory, not part of the core.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry; 12 One /delegate skill on the `delegate` command, with a harness constraint.

**Status:** done 2026-10-05, raised by the user 2026-10-02; rescoped the same day from "orchestrated from Codex" after the user's review: "Make the orchestration harness agnostic. Don't just build one for Codex." Built 2026-10-02: profiles in `assets/orchestrators/` (claude, codex), `scripts/orchestrators.py`, `--orchestrator` on `run`/`dispatch`, `tests/test_orchestrators.py`, dispatch cases 31b-31e, and the offline orchestrate eval runs each profile with its own env. Kiro's profile came with ticket 15. Live runs on the user's Mac 2026-10-04 (`evals.py orchestrate --harness <h> --keep`, each dispatched to `grok47-high@grok`): Codex and Kiro passed. Claude failed: `claude -p` ran `delegate run` in the background, as the skill said, and its exit SIGTERMed the relay mid-answer (relay exit 143, no `return.json`). Fixed: SKILL.md says a headless session runs it in the foreground, and Claude's launch prompt asks for that. Waits on the user: the Claude rerun. 2026-10-04 evening: the Mac pulled to current main and reinstalled, but the permission check refused to start the headless `claude -p` session from Remote Control, so the user runs `python3 scripts/evals.py orchestrate --harness claude --keep` from `~/projects/delegate/agents/skills/delegate` by hand. 2026-10-05: the user ran it by hand on the Mac at current main (cfea3ac) and it passed: `pass orchestrate claude: equivalent run`, dispatched to `flash-high@agy`.

- [x] No script names an orchestrator; `ORCHESTRATOR` and the `@claude` native check are gone from the code.
- [x] With no profile or an unknown orchestrator, `delegate run` relays every Lane, claude Lanes included, and a test proves it.
- [x] Native Lanes come only from a profile file, and `setup.py` writes agent files only for a profile that declares them; adding a profile needs no code change.
- [x] The same eval scenarios from ticket 10 pass when orchestrated from Claude Code and from two other harnesses (Codex and Kiro), each reviewed from its run directory (the user's box for the live runs). Codex and Kiro pass; Claude passed on the rerun after the foreground fix (2026-10-05).
