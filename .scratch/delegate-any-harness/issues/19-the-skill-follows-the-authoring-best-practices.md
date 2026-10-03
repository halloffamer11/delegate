# 19 — The skill follows the authoring best practices

**What to build:** a rewrite of `SKILL.md` and `references/` against Anthropic's skill authoring best practices. Dispatch becomes low freedom (one exact `delegate` command); Class judgment stays high freedom (`classes.md`); catalog-edit and wizard detail move to references one level deep; `references/architecture.md` (26 KB, one 8,163-character line) gets short lines and a table of contents; ticket numbers leave the skill text; the description says in the third person what it does and when.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 09 Delegate runs only when the user asks for it; 10 Evals for the delegate skill; 12 One /delegate skill on the `delegate` command, with a harness constraint.

**Status:** done, raised by Orin 2026-10-02; built 2026-10-03. `SKILL.md` is the four-step workflow with one exact `delegate run` command; the ranking rule, constraints and orchestrator detail are in `references/routing.md`, the catalog, overlays, focused edits, wizard and model evidence in `references/catalog.md`, and the checks in `references/maintenance.md`. `references/architecture.md` has a table of contents and lines of 100 characters at most; it keeps its ticket numbers as maintainer history. Offline evals pass as before (ping 4/4 relayed harnesses, orchestrate 2/2); the live evals stay ticket 10's box.

- [x] SKILL.md has no ticket or date references and no wizard internals.
- [x] Every reference over 100 lines opens with a table of contents.
- [x] Ticket 10's evals pass at or above the baseline.
