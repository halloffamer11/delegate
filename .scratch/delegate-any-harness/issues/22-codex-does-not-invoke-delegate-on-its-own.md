# 22 — Codex does not invoke delegate on its own

**What to build:** Codex runs `/delegate` without being asked. `disable-model-invocation: true`
is Claude Code frontmatter; Codex reads the same symlinked skill from `~/.agents/skills`
(Makefile `HARNESS_SKILL_DIRS`) and ignores the field. Codex has its own switch: an
`agents/openai.yaml` beside `SKILL.md` with

```yaml
policy:
  allow_implicit_invocation: false
```

after which only an explicit `$delegate` (or the `/skills` picker) runs it
(https://learn.chatgpt.com/docs/build-skills, read 2026-10-03). The file is data the skill
directory carries, so the symlink install picks it up with no Makefile change. This is the
per-harness half of ADR 0001's "user-invoked only" rule; ticket 09 is the prose half.

Kiro has no equivalent yet (kirodotdev/Kiro#10985), so on Kiro the description and body from
ticket 09 stay the only guard.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None. Lands cleanly beside 09 and 12; if 12 folds the wrappers into
`/delegate <harness>`, only the surviving skill directories need the file.

**Status:** ready-for-agent, raised by Orin 2026-10-03 after Codex invoked delegate unprompted.

- [ ] Every skill directory under `agents/skills/` that sets `disable-model-invocation: true`
      ships `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.
- [ ] A test fails when a skill sets one and lacks the other, so a new skill cannot miss it.
- [ ] ADR 0001's user-invoked line names both switches (Claude frontmatter, Codex `openai.yaml`)
      and says Kiro has none yet.
- [ ] Orin's box: in Codex, a prompt that would have triggered delegate no longer does, and
      `$delegate` still runs it.
