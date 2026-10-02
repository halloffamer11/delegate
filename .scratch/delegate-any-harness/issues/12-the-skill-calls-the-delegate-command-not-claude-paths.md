# 12 — One /delegate skill on the `delegate` command, with a harness constraint

**What to build:** `SKILL.md`, the four `/delegate-<harness>` wrappers, `council` and the courier call `python3 ~/.claude/skills/delegate/scripts/...`. Make `bin/delegate` the contract (`delegate rank|run|status|setup`, JSON out) so any harness that can run a shell can use the skill. Fold the four `/delegate-<harness>` wrappers into `/delegate` itself (Orin, review 2026-10-02). What a wrapper gives today is a way to send work to one harness without opening every Lane, for example to use agy because its quota is high and should be spent. `/delegate` keeps that as an explicit harness constraint in the user's request: `/delegate agy <task>`, or a plain-language standing instruction such as "use agy for all delegated work". The constraint restricts ranking to that harness's Lanes, which is what `rank.py --harnesses` already does, so the rest of the ranking still applies inside it. It applies only when the user states it: delegate stays user-invoked only (ticket 09), and the model never picks a harness constraint on its own.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry.

**Status:** ready-for-agent, raised by Orin 2026-10-02; wrappers folded into `/delegate` per Orin's review the same day

- [ ] No skill or agent file under `agents/` names a `~/.claude` path.
- [ ] `delegate rank <class> --json` and `delegate run` cover what the skills call today.
- [ ] `/delegate <harness> <task>` and a stated standing constraint both restrict ranking to that harness's Lanes; an unknown or uninstalled harness is refused with the list of installed ones.
- [ ] The four `delegate-<harness>` skill directories are removed, and `make install` drops their stale links.
- [ ] Ticket 10's evals pass at or above the baseline.
