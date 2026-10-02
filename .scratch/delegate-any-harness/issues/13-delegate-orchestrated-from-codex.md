# 13 — Delegate orchestrated from Codex

**What to build:** an orchestrator adapter replaces `ORCHESTRATOR="claude"` (`delegate.py:62`, `:762`, `:883`). It says whether native Lanes exist and how they are written and spawned: Claude keeps `~/.claude/agents/lane-*.md` and the Agent tool; Codex has none, so every Lane, claude Lanes included, is relayed. The orchestrator is detected (env or flag), not a constant. The courier and the statusline become Claude-only extras.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** 11 One harness registry; 12 The skill calls the `delegate` command, not ~/.claude paths.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] With the orchestrator set to codex, `delegate run` relays a claude Lane instead of printing a native-lane line.
- [ ] `setup.py` writes native agent files only for an orchestrator that has them.
- [ ] Proof: one real job sent from a Codex session through the skill, reviewed from its run directory (Orin's box).
