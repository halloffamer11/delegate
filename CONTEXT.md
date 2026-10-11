# Delegate

Delegate is the routing of worker jobs to external or native models by capability and
remaining subscription usage.

## Delegate: who runs a job

**Harness**:
A CLI that runs models: `claude`, `codex`, `agy`, `grok`, or `kiro` (its CLI is `kiro-cli`, and it serves several vendors' models on one Meter).

**Orchestrator harness**:
The harness that runs the session that plans, dispatches, and checks results. Any harness that can run a shell and read files can be one; delegate detects it (or takes `--orchestrator`) and never assumes it.
_Avoid_: lead harness, parent

**Model**:
One vendor model, such as `gpt-5.6-luna` or `claude-opus-5`. Harnesses may spell one Model differently: agy carries the effort in the slug (`claude-opus-5-5-high`) and kiro writes `claude-opus-5.5`, and each is still Claude Code's `claude-opus-5-5`. The harness decides what a spelling means, never the spelling alone.
_Avoid_: slug (when you mean the Model a slug names), family (when you mean the Model)

**Effort**:
How hard a model reasons on one job: low, medium, high, xhigh, or max. Not every model accepts every level.

**Level**:
A model's slug with its version taken out: `gpt-6-sol` and `gpt-5.6-sol` are both level `gpt-sol`. One level is one line of models, at one version each.
_Avoid_: family (when you mean the level), tier

**Superseded**:
Said of a model that its harness replaces — codex names the replacement — or that another model of the same level, at a higher version, replaces. Its lanes leave the catalog at the next setup save.
_Avoid_: retired (which is a model the harness no longer lists at all), deprecated

**Generation**:
The models of a harness that are not superseded. The full setup wizard shows every current-generation model of every harness on the carry page, at every effort; a focused setup screen proposes none.

**Lane**:
One model at one effort on one harness, named `<model-effort>@<harness>`. It is the unit that gets a tier and that ranking picks.
_Avoid_: route, worker, model (when you mean the lane)

**Carried lane**:
A lane that setup keeps in ranking.
_Avoid_: active lane

**Dominated**:
Said of an effort when another effort of the same model scores at least as well at no more cost. Setup proposes a dominated effort off.

**Published name**:
The name a benchmark source prints for a model, when it differs from the model's own name. A lane's `published_as` lists them; each entry names the Model, so it reaches every Harness that runs that Model.
_Avoid_: alias, display name (when you mean the published name)

**Native lane**:
A lane that runs as a subagent inside the orchestrator harness.

**Relayed lane**:
A lane that runs as a separate CLI process through a relay.

**Relay**:
The program that runs one job on a harness CLI in a separate process and returns the result.

**ADS**:
The package that provides the relays: `amElnagdy/delegate-skills`, used through the fork `halloffamer11/delegate-skills` at a pinned commit. The letters are not spelled out anywhere.
_Avoid_: ADS as a name for the concept; say relay

## Delegate: capability

**Tier**:
A capability level from 1 (lowest) to 4 (frontier) that the user gives each lane in setup. It belongs to the lane, not the model. A project may set its own Tier for a lane, and everything that reads a Tier — the Class range, the Gate, Overflow, the Tier leaders — reads the effective one.

**Project tier**:
The Tier a project sets for a lane in `.delegate/lanes.json`, for jobs in that project only. It is the one lane field a project may set; every other field, `enabled` and Order included, stays global. A lane the project moves has no place in its new tier until Project order gives it one.

**Order**:
A lane's place inside its tier, from 1, that the user sets on the setup wizard's review page. Ranking sorts by tier, then order, then pace, then lane name; a lane without an order comes after every lane with one. Setup's Draft, `catalog set` and `catalog order` number lanes that have no order after every lane with one, by lane name, and put a lane that joins a tier at its end.
_Avoid_: priority, rank (when you mean the order)

**Project order**:
A project's preferred order for lanes inside their effective tiers. It overrides Order for jobs in that project. It does not change a lane's Tier; a Project tier does that.

**Tier leader**:
The lane ranking selects when selection is restricted to one Tier. It is a preview for that Tier, not the Pick for a Class range.

**Class**:
The kind of job. Five ship (scout, mechanical, impl, review, hard-impl) and every catalog has them; a catalog may add its own, each with a Range in `routing.json` and a section in a Class guide.
_Avoid_: task type, category

**Floor**:
The lowest tier a class accepts. It is the default for each job of that class.
_Avoid_: need, minimum tier

**Ceiling**:
The highest tier a class accepts. It is extra capability for when a job needs it, and the most the class can ever get.
_Avoid_: cap, max tier

**Range**:
The tiers from the floor to the ceiling of a class. It is the normal range of operation for that class.
_Avoid_: band

**Overflow**:
Admitting the tier above a class's ceiling for one job, when subscription usage
is the only thing stopping the range: at least one carried lane in it is under
the gate, and every veto there is a gate veto or an absent harness CLI. A lane
whose CLI is absent counts like a lane switched off, because the catalog is
shared across machines and this one cannot run that lane. Overflow steps one
tier at a time, never goes below the floor, and never reaches tier 4. Any other
veto in the range, and a range with no gated lane in it, stop the job instead.
The routing key `overflow` turns it off.
_Avoid_: fallback, escalation, exception

**Named dispatch**:
A job sent to a lane the caller chose. Ranking and the range are skipped.

## Delegate: the catalog

**Catalog**:
This machine's `lanes.json` and `routing.json` in `~/.config/delegate/`, with a project's `.delegate/routing.json` and `.delegate/lanes.json` layered on for jobs in that project. It is machine-local.
_Avoid_: config, registry, settings

**Catalog read**:
The catalog's documents as one session read them, with where each file resolved and one revision over them all. A Catalog commit checks against it.
_Avoid_: snapshot (alone), cache, revision (which is only its hash)

**Catalog commit**:
The one write of catalog documents. It refuses an Intervening edit, writes through links, backs up what it replaces, keeps the Agent files in step and forgets the Model queue entries its read returned.
_Avoid_: save (when you mean the write path), apply, flush

**Intervening edit**:
A change to a catalog document between a session's Catalog read and its Catalog commit. The commit refuses it and writes nothing.
_Avoid_: conflict (alone), race, stale write

**Draft**:
The catalog as setup holds it before the confirm page's `y`: the catalog the pages started from, plus the carry, Tier, Order and routing decisions made since. Every page reads it, the confirm page lists it, and save writes it and nothing else.
_Avoid_: working copy, session state, pending catalog, result

**Agent file**:
The file an orchestrator reads to run one Native lane, written from its profile's template into the profile's agents directory. It is machine-local, like the catalog, and always a plain file.
_Avoid_: lane file, subagent definition, lane agent

**Model swap**:
Dispatch's scan replacing a lane with the same lane at a newer version of its model, keeping its Tier, Order and Meter, and keeping it off if it was off.
_Avoid_: upgrade, migration, auto-update

**Model queue**:
The models dispatch noticed that no lane runs, and the Model swaps its scan applied. They are kept until a wizard run that named them on its start page saves.
_Avoid_: inbox, backlog, new-models list

## Delegate: benchmarks

**Accepted rows**:
The per-effort benchmark rows that `effort.py check` accepted against the page they were read from, one JSON list per file. They are the only way a per-effort figure reaches the wizard.
_Avoid_: scraped rows, raw rows, effort rows (in prose)

**Fetched source**:
A benchmark source delegate reads from the web itself: Artificial Analysis and Epoch AI. Each fetch is kept for 24 hours. Every other source arrives only as Accepted rows in a named file.
_Avoid_: live source, refreshed rows

**Benchmark snapshot**:
The benchmark rows that one wizard scrub, one report or one model inspection reads, taken once: the Accepted rows and the Epoch rows, with where each Fetched source's rows came from and how old they are. Routing never reads it.
_Avoid_: snapshot (alone), bench data, the cache (when you mean the rows), provenance (that is one row's verified, self-reported or unlabelled badge)

**Lane evidence**:
The benchmark rows that belong to one lane: published for the lane's Model and measured at the lane's effort. The carry rule compares them with the rows of the same Model at the other efforts the lane's Harness runs. A row at an effort that Harness does not run belongs to that Model as context and is no lane's evidence there.
_Avoid_: lane rows, matched rows, attributed rows (in prose), scores (when you mean the rows)

## Delegate: usage

**Meter**:
One subscription quota. Each lane uses exactly one meter, and many lanes can share a meter.
_Avoid_: quota (when you mean the meter)

**Meter weight**:
How much of its meter one job on a lane uses, compared with other lanes. It feeds the report, not the ranking.

**Window**:
One quota period of a meter: 5-hour or weekly.

**Model meter**:
A meter for one model's own weekly Window that shares its harness's other
Windows, such as Claude's Fable meter: the 5-hour Window and, where the harness
has one, its week for all models, which the model's jobs also spend. Its Weekly
figure is the lower of its own week and that shared week. The catalog marks it
with `"model_meter": true`, and a probe row that carries the model's own week
marks it too; displays read those, never the meter's name.
_Avoid_: per-model weekly (when you mean the Weekly figure)

**Remaining**:
The fraction of a Meter still unspent: the lower of its Window fractions, and the
one Window's fraction when a Meter has only one. Remaining is unknown only when no
Window was read. Where no vendor joins the two Windows, the lower one is an
assumption, and the Meter's note says so.
_Avoid_: r (in prose)

**Weekly figure**:
The weekly fraction of a Meter that Pace is computed from and that every display shows: the fraction of its weekly Window, and for a Model meter the lower of its own week and its harness's week for all models.
_Avoid_: weekly Remaining, remaining_weekly (in prose)

**Gate**:
The lowest remaining a meter may have and still take a job.

**Pace**:
The rate a meter can afford from now to its weekly reset, divided by the rate of an even spend across the whole week. It comes from one reading: 1.0 is on track, and above 1 means quota will expire unspent.
_Avoid_: velocity, speed, burn rate

**Burn rate**:
How fast a meter's remaining falls, measured across readings over time.

**Meter snapshot**:
Every Meter's Windows as the last probe read them, with any Usage-limit hold applied, read at one moment and knowing its age. Ranking a job and every display of the Meters read one, and none of them reads the usage cache itself.
_Avoid_: snapshot (alone), usage document (when you mean what a caller reads), observations, cache

**Freshness**:
How old a Meter snapshot may be when it is read: cached (as it is, never probed), fresh (probed when older than ten minutes), or forced (probed now). With `routing.meters` off no automatic read probes; only a person's own `delegate status --refresh` does.
_Avoid_: TTL (in prose), refresh flag, probed

**Usage-limit hold**:
A Meter held at nothing left because its harness refused a run for its usage limit. It ends at the earliest of the Meter's weekly reset, a probe that reads a different reset, a run on that Meter that finishes, or 24 hours, and it lives beside the usage cache it overlays.
_Avoid_: limited flag, lockout, block

**Margin**:
How much higher a lane's pace must be to take a job from the pick when it sorts after the pick: at a higher tier, or lower in the order of the same tier.

**Pick**:
The one lane ranking selects for a job: the first lane by tier, order, pace and lane name, unless a lane after it has a pace higher by the margin.

**Cause**:
The one reason a lane holds its place in a ranking, as a value: pick, steal, eligible, unknown, or the veto that stopped it (disabled, floor, ceiling, gate, cli). The reason text is its display.
_Avoid_: reason code, veto (for the whole set), status

**Steal threshold**:
The value a lane that sorts after the Pick must reach to take the job, in the quota unit routing uses: the Pick's Pace plus the Margin, or with plan dollars the Pick's value times one plus the Margin.
_Avoid_: steal line, Pace + Margin (under plan dollars)

**Pace to lead**:
The lowest Pace at which a lane on a Meter would lead a Tier, with every other Meter as it reads now. It can sit below the Steal threshold, because a lane in the same place in the Order as the Pick only has to sort ahead of it.
_Avoid_: threshold (when you mean this), target pace

**Handover**:
How far the Tier leader's Meter can fall, in quota points at today's readings, before another lane leads the Tier or the Meter falls under the Gate. It is never a time.
_Avoid_: runway, time left, ETA, burn, hand-off (a native Run's Outcome)

**Tier preview**:
The ranking of one exact Tier together with what would change its leader: each lane's Cause, the Steal threshold, each other Meter's Pace to lead and the Handover. Rank computes it; the popup and the deck only draw it.
_Avoid_: what-if, simulation, tier view

## Delegate: one job

**Brief**:
The task file the orchestrator writes for one job.

**Run**:
One dispatch of a brief and its directory, never reused.

**Outcome**:
How a Run ended. It is recorded once in the Run's `dispatch.json` and once in the Ledger. A relayed Run takes done, partial or blocked from its Return; a Run on a Native lane ends native at once, because delegate writes the prompt, names the orchestrator's agent and never sees what that agent hands back. Every Run that starts gets one, whatever stops it before the work is done.
_Avoid_: result (that is the relay's `result.json`), final status

**Return**:
The five fields a worker hands back for one Run, as `return.json` holds them: status (done, partial or blocked), deliverable, evidence, open questions and changed files. The return block is the JSON object a worker ends its final message with; delegate settles it, or the lack of one, into the Return.
_Avoid_: result (the relay's own `result.json`), response, child output, mapped

**Stopped short**:
Said of a relayed job when the relay calls it completed but the harness's own events show the worker did not finish, as when grok's permission gate cancels a tool. It is blocked, not partial.
_Avoid_: cancelled (alone), failed

**Token counts**:
The input, output, cache-read and cache-write tokens one Run used, keyed like a lane's price record. The report prices a Run from them; a Run whose relay reported none is unmeasured, never zero.
_Avoid_: usage (which is a Meter's subscription usage), token usage

**Ledger**:
The machine-local file `~/.cache/delegate/ledger.jsonl`. It holds one line when each Run starts and one when it ends. The statusline reads which Runs are Running from it, and only the Run module writes it.
_Avoid_: run ledger (that is `runs.jsonl`, the verdicts the orchestrator logs), event log

**Running**:
Said of a Run that has started and has no Outcome yet, within its lane's timeout. A Run that was killed outright stops counting as running once that timeout passes.
_Avoid_: active, in flight, open

## Delegate: browsers

**Disposable browser**:
A fresh browser that Playwright starts for one run, with no logins and no saved state. A worker may read and write in it.

**Agent profile**:
A browser profile kept only for workers and signed in to a few chosen accounts, reached through the Playwright extension. Workers never reach the human's personal profile; the extension is installed only in the agent profile.
_Avoid_: live browser, authenticated browser
