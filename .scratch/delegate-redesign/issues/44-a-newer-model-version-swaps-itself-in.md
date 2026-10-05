# 44 — A newer version of a model the catalog runs swaps itself in

**What happened:** on 2026-10-05 the user reported that, on machine deployments, refresh
did not pick up GPT-6.1-Sol in Codex. The expectation: any new model a harness offers
reaches the catalog without a model name in the skill.

**Findings.** Discovery was already name-agnostic: `discover.py` reads whatever
`codex debug models` lists and works out levels and versions from the slug. On a machine
with codex 0.160.0 the list has `gpt-6.1-sol`, the refresh replaces the Sol 6 Lanes, and
the catalog there already runs `sol61-*@codex`. So a machine that missed it either has a
codex CLI that does not list the model yet (discovery can only see what the harness
reports), or never ran `delegate global` after dispatch's scan (ticket 29 of any-harness)
queued it: the queue waited for the wizard.

**Built.** Dispatch's daily scan applies each newer version of a model the catalog
already runs (`model_queue.apply_successors`). Each Lane the refresh would replace with
its successor at the same effort is swapped in the global lanes.json, in its place, with
its Tier, Order, Meter, weight and timeout. An off Lane stays off, since nobody screens
the swap. The old lanes.json is copied to `lanes-backups/` beside the queue first, the
write is skipped when lanes.json changed since the scan read it, and native agent files
follow. A model new to its harness, a new effort, and a superseded Lane with no successor
at its effort still wait for the wizard, because the user sets those Tiers. The wizard's
start facts name the swaps ("Dispatch swapped in") and its write clears them.
`$DELEGATE_MODEL_APPLY=off` keeps the scan to queueing. The refresh plan now carries
`successors` (old Lane to new Lanes).

**Status:** in progress. Waits on the user for one check on a machine that missed it:
`codex --version && codex debug models | grep -c gpt-6.1-sol`. If codex there does not
list the model, the fix is updating that machine's codex CLI, not delegate.
