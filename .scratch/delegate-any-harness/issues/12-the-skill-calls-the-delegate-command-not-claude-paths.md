# 12 — One /delegate skill on the `delegate` command, with a harness constraint

**What to build:** `SKILL.md`, the four `/delegate-<harness>` wrappers, `council` and the courier call `python3 ~/.claude/skills/delegate/scripts/...`. Make `bin/delegate` the contract (`delegate rank|run|status|setup`, JSON out) so any harness that can run a shell can use the skill. Fold the four `/delegate-<harness>` wrappers into `/delegate` itself (Orin, review 2026-10-02). What a wrapper gives today is a way to send work to one harness without opening every Lane, for example to use agy because its quota is high and should be spent. `/delegate` keeps that as an explicit harness constraint in the user's request: `/delegate agy <task>`, or a plain-language standing instruction such as "use agy for all delegated work". The constraint restricts ranking to that harness's Lanes, which is what `rank.py --harnesses` already does, so the rest of the ranking still applies inside it. It applies only when the user states it: delegate stays user-invoked only (ticket 09), and the model never picks a harness constraint on its own.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-any-harness-next-v75vlw`). All boxes done. Raised by Orin 2026-10-02; wrappers folded into `/delegate` per Orin's review the same day.

What landed: `bin/delegate` gained `rank`, `run`, `dispatch`, `status` (`--json` for the usage document), `log`, `runs`, `cost`, `catalog` and `setup`, each running its script out of the command's own checkout. `--harness <h>` on `rank` and `run` is the user's harness constraint: the catalog is cut to that harness's Lanes before ranking, so the Range, Gate, overflow and Margin all apply inside it, and an unknown or uninstalled harness is refused with the installed list. SKILL.md says the constraint comes only from the user and folds in the wrappers' exclusion and effort-cap rules. SKILL.md, council and the courier call `delegate ...` and name no `~/.claude` path. The four `delegate-<harness>` directories are gone, and `make install` removes a link into the checkout whose skill no longer exists (tried on a temp HOME: the stale link went, an unrelated broken link stayed). The evals now drive the `delegate` command and pass as before. Tests: `test_delegate_command.py` case 8, `test_rank.py` case 28, `test_dispatch.py` 27b and 27c. Verified with `make test` on Python 3.9 and 3.13.

Outside this repo: the dotfiles statusline and Hammerspoon config still call `~/.claude/skills/delegate/scripts/report.py`, and Orin's global `references/CLAUDE.md` still tells every session to read the delegate skill and run `rank.py` before choosing any model, which contradicts ticket 09's user-invoked-only rule. Neither is a skill or agent file here; both are Orin's to change.

- [x] No skill or agent file under `agents/` names a `~/.claude` path.
- [x] `delegate rank <class> --json` and `delegate run` cover what the skills call today.
- [x] `/delegate <harness> <task>` and a stated standing constraint both restrict ranking to that harness's Lanes; an unknown or uninstalled harness is refused with the list of installed ones.
- [x] The four `delegate-<harness>` skill directories are removed, and `make install` drops their stale links.
- [x] Ticket 10's evals pass at or above the baseline.
