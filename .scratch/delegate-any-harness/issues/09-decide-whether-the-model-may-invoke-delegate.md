# 09 — Decide whether the model may invoke /delegate

**What to decide:** `SKILL.md` sets `disable-model-invocation: true` (Orin, 2026-09-25), but its description tells the model to use it "before any Agent, Workflow, or teammate spawn" and the body calls `/delegate` the model-invocable entry point. Either the model may route on its own, or delegation is typed-only and the text says so. This also matters for ticket 13: a frontmatter field only Claude Code reads cannot be the portable switch.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-human, raised by Orin 2026-10-02

- [ ] Orin picks: model-invocable, or typed-only.
- [ ] The frontmatter, the description and the body agree with the choice.
