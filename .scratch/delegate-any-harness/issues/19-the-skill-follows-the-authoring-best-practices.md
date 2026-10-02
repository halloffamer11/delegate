# 19 — The skill follows the authoring best practices

**What to build:** a rewrite of `SKILL.md` and `references/` against Anthropic's skill authoring best practices. Dispatch becomes low freedom (one exact `delegate` command); Class judgment stays high freedom (`classes.md`); catalog-edit and wizard detail move to references one level deep; `references/architecture.md` (26 KB, one 8,163-character line) gets short lines and a table of contents; ticket numbers leave the skill text; the description says in the third person what it does and when.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 09 Delegate runs only when the user asks for it; 10 Evals for the delegate skill; 12 The skill calls the `delegate` command, not ~/.claude paths.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] SKILL.md has no ticket or date references and no wizard internals.
- [ ] Every reference over 100 lines opens with a table of contents.
- [ ] Ticket 10's evals pass at or above the baseline.
