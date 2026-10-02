# 13 — Orchestration is harness-agnostic

**What to build:** delegate makes no assumption about which harness is orchestrating. Today `ORCHESTRATOR="claude"` (`delegate.py:62`, `:762`, `:883`) is a constant, and native Lanes, the agent files in `~/.claude/agents` (`setup.py:31`, `:434-500`), the courier and the spawn instruction in `SKILL.md:86` all assume Claude Code. Do not replace that with a second hardcoded orchestrator; remove the special case.

- **One default path for every orchestrator.** Any harness that can run a shell and read files orchestrates the same way: `delegate run` relays the job, and the orchestrator reads the run directory. This path needs no knowledge of the caller, and it is what an unknown or new harness gets.
- **Native Lanes are an optional capability, declared as data.** An orchestrator profile says whether its harness can run a Lane in-process, where its agent files live, their template, and the one-line spawn instruction the skill prints. Claude Code is the first profile, not a code path. No orchestrator name appears in the scripts.
- **The orchestrator is detected, never assumed.** From the environment or a `--orchestrator` flag; anything unrecognised falls back to the default path.
- The courier and the statusline become optional extras that read the same run directory, not part of the core.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry; 12 The skill calls the `delegate` command, not ~/.claude paths.

**Status:** ready-for-agent, raised by Orin 2026-10-02; rescoped the same day from "orchestrated from Codex" after Orin's review: "Make the orchestration harness agnostic. Don't just build one for Codex."

- [ ] No script names an orchestrator; `ORCHESTRATOR` and the `@claude` native check are gone from the code.
- [ ] With no profile or an unknown orchestrator, `delegate run` relays every Lane, claude Lanes included, and a test proves it.
- [ ] Native Lanes come only from a profile file, and `setup.py` writes agent files only for a profile that declares them; adding a profile needs no code change.
- [ ] The same eval scenarios from ticket 10 pass when orchestrated from Claude Code and from two other harnesses (Codex and Kiro), each reviewed from its run directory (Orin's box for the live runs).
