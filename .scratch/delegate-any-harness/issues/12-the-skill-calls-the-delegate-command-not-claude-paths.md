# 12 — The skill calls the `delegate` command, not ~/.claude paths

**What to build:** `SKILL.md`, the four `/delegate-<harness>` wrappers, `council` and the courier call `python3 ~/.claude/skills/delegate/scripts/...`. Make `bin/delegate` the contract (`delegate rank|run|status|setup`, JSON out) so any harness that can run a shell can use the skill. Generate the per-harness wrappers from the registry instead of four near-identical files.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] No skill or agent file under `agents/` names a `~/.claude` path.
- [ ] `delegate rank <class> --json` and `delegate run` cover what the skills call today.
- [ ] The wrappers are generated from one template per registry entry, and `make install` writes them.
- [ ] Ticket 10's evals pass at or above the baseline.
