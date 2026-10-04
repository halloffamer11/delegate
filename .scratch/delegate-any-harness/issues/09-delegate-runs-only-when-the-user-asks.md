# 09 — Delegate runs only when the user asks for it

**What to build:** delegate is user-invoked only, and every surface says so. Today `SKILL.md` sets `disable-model-invocation: true` (the user, 2026-09-25), but its description tells the model to use it "before any Agent, Workflow, or teammate spawn" and the body calls `/delegate` the model-invocable entry point. The frontmatter field is read only by Claude Code, so on another orchestrator (ticket 13) the description and body are the only guard: they must say plainly that delegate runs only on an explicit request.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-any-harness-next-v75vlw`). All boxes done; the ADR line was already in place. Raised by the user 2026-10-02. Decided by the user the same day in review: "It needs to be user invoked only. I don't want delegate to be used unless it's being explicitly requested."

- [x] The description says what delegate does and that it runs only when the user explicitly asks for delegation; it no longer tells the model when to route on its own.
- [x] The body drops "model-invocable" and any instruction to delegate unprompted; the four `/delegate-<harness>` wrappers and `council` agree.
- [x] `disable-model-invocation: true` stays on every delegate skill.
- [x] The rule is one line in `docs/adr/0001-settled-delegate-decisions.md`.
