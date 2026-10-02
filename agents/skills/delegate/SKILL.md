---
name: delegate
description: Sends one worker-shaped job (implementation with a spec, verification, review, scouting, a mechanical transform) to an external or native worker on one lane, picked by tier and remaining subscription usage, and reports remaining usage. Runs only when the user explicitly asks for delegation (for example by typing /delegate); never use it on your own initiative.
disable-model-invocation: true
---

# Delegate

The session plans, adjudicates, and synthesizes. Worker-shaped work goes out on a **lane**: one (harness, model, effort) tuple that drains one subscription **meter**. `/delegate` reads meters and ranks lanes, and it runs only when the user explicitly asks for delegation: never delegate work on your own initiative, and never start it because a task looks worker-shaped. Every step runs the `delegate` command on PATH (`make install` in the delegate checkout links it), so any harness with a shell can drive it.

## Terms

Every term this skill uses (harness, lane, meter, class, tier, floor, ceiling, range, pace, gate, margin, native lane, disposable browser, agent profile, and the rest) is defined once in `CONTEXT.md` at the root of the delegate checkout (`~/projects/delegate/CONTEXT.md` by default). Read it before the first run in a session. Class intent, signals, examples, counter-examples, and when to raise live in `assets/classes.md`.

## Files

- `~/.config/delegate/lanes.json`: meters and lanes (harness, model, effort, meter, meter weight, timeout, price, tier, basis; optional `enabled`, and `published_as` — the names benchmark sources print for this lane's model, e.g. `"published_as": ["Fable 5.1"]` on a `claude-fable-5-1` lane, needed only where case and separators alone do not bridge the two).
- `<git-root>/.delegate/lanes.json`: a project's lane customization, beside its `routing.json`. One field, `tier`, 1 to 4, on a Lane the global catalog already has: `{"lanes": {"<lane>": {"tier": 2}}}`. Every other Lane field, `enabled` and `order` included, stays global, and it carries no `version`. The effective Tier is the project's where it names one, and the Class Range, the Gate, overflow and the Tier leaders all read the effective Tier. A Lane the project moves has no place in its new Tier, so it sorts after the Lanes that have one until `project_order` places it (ticket 32).
- `~/.config/delegate/routing.json`: `classes` (floor and ceiling per class), `margin`, `gate`, optional `meters` and `overflow` (booleans, default on). A project overrides any key at `<git-root>/.delegate/routing.json`; `classes` merges per class and per key. Floor and Ceiling stay here, never in the Class guide.
- `assets/classes.md`: Class judgment (intent, signals, examples, counter-examples, when to raise `--tier` inside the live Range). A project may overlay matching `##` Class sections at `<git-root>/.delegate/classes.md`; the overlay cannot add a Class or declare Floor or Ceiling. `delegate catalog check-guide [file] [--overlay]` validates headings against the closed Class set.
- Both JSON files are strict JSON, validated on read with a plain-language message naming the field and the rule, formatted on write, and accept `note` fields anywhere. `delegate catalog show` prints the effective catalog for the current directory; `delegate catalog check <file>` validates one file and warns on stderr, without failing, when one Meter serves every carried Lane of a Tier — that Meter under the Gate takes the whole Tier with it. The starting catalog ships in `assets/samples/`; `/delegate setup` is the wizard that builds or revises it (direct command: `delegate setup`). When the user's request asks for setup (e.g. `/delegate setup`), run `delegate setup`. Orin's two short commands are `delegate global`, the wizard on this machine's catalog, and `delegate project`, the dashboard for the current directory's Git project; both run out of the checkout the command itself lives in, and `make install` in that checkout links the command into `~/.local/bin` (ticket 34).

## Focused catalog changes

Use `delegate catalog set FIELD JSON_VALUE --scope global|project`,
`range CLASS FLOOR CEILING --scope global|project`, or
`order LANE POSITION --scope global|project`. Tier uses `lanes.<lane>.tier`:
`--scope global` edits the catalog, `--scope project` writes
`<git-root>/.delegate/lanes.json`, and a project Tier equal to the global one
removes the entry. Routing fields are `routing.gate`, `routing.margin`,
`routing.meters` and `routing.overflow`.
Order is one-based among carried Lanes in the same Tier. All accept `--cwd`
and `--config-dir`.

Each command first returns a JSON preview: source files and resolved targets,
changed fields, values, Picks and exact-Tier leaders using cached observations.
Apply the same operation with `--apply --expect REVISION` from that preview.
An explicit request for the desired value authorizes preview and apply; do not
ask again. A source change requires a fresh preview. Apply preserves stow links
and writes only the chosen source document. Focused edits preserve other choices;
bulk tier-line imports still turn omitted carried Lanes off.

`delegate setup --screen carry|tier1|tier2|tier3|tier4|review|routing` opens one terminal
screen on the current catalog. Confirm lists only chosen changes; no-op saves
write nothing and focused writes preserve stow links. `--screen start` keeps the
full wizard. On a focused Tier screen, unmarking moves a Lane down one Tier;
use Carry to turn a Tier 1 Lane off. Use the surgical CLI for non-TTY edits.

`make delegate-wizard` is the one command for a new model (ticket 33). At start
the wizard fetches the Artificial Analysis rows itself, into
`~/.cache/delegate/bench/aa/`, skipping a fetch under 24 hours old and falling
back to the repo's rows with the reason on the start page; the harness probes
run beside it. It then proposes, in memory, the current generation: a Lane for
every effort of every current-generation model of every harness, each new Lane
with a predecessor in that Lane's place and carrying its `enabled`, Tier, Order,
Meter, weight and timeout, an `UNMEASURED` note naming where those came from, a
`null` price and an `UNPRICED` note; a superseded model's Lanes leave. The start
page states each change, one line per model. Nothing is written until the
confirm, and quitting writes nothing. The save also writes the agent file of
each new native Lane where its orchestrator profile keeps agent files, and removes each superseded one.
The catalog and those agent files are machine-local, never in the repo. Prices are the one thing the refresh never
proposes: read them off the vendor's page.

## Model evidence

Use `scripts/bench.py model MODEL --effort-rows FILE` for a read-only inspection;
repeat `--effort-rows` for accepted datasets and use `--json` for the same records
as JSON. `--epoch-csv FILE` accepts a local snapshot. This command fetches nothing.
It separates Model-family evidence from rows attributable to a Lane’s exact
effort, shows unresolved identity and absent rows, and keeps board versions and
source cost bases separate. Standing is within the loaded snapshot. Research
links remain references until their rows pass the acceptance pipeline.

## 1. Classify and write the brief

Read CONTEXT.md terms if this session has not. Read `assets/classes.md`. If the git root has `.delegate/classes.md`, use each of its `##` Class sections in place of the matching section from the skill guide. Pick exactly one Class; when two seem to fit, the counter-examples decide. Named dispatch skips Range and still writes the Class on the prompt.

Write a Markdown brief with two headings, nothing else: `# Objective` and `# Definition of done`. Name every file the worker must read. Put the gate commands the worker must run in the definition of done. Save it under the session scratchpad with an absolute path.

## 2. Run

    delegate run <class> --brief </abs/brief.md> --cwd </abs/project> [--write </abs/worktree>] [--tier <n>] [--no-leash] [--dry-run]

Run it with `run_in_background` so the session keeps working; the notification carries the `delegate:` line with `run=<dir>`, and `<dir>/return.json` is the result. The command prints the ordered lanes with one reason each, then dispatches the pick. `--dry-run` stops after the print. `--tier <n>` raises the floor for this job (must stay within the class range); `dispatch` keeps `--effort`. `--no-leash` drops the tool-call leash in the prompt; set it when the job is large. `--write` is the only way a worker gets a shell and edits; the worktree is the blast radius, never a primary checkout.

Delegate works out which harness is orchestrating from the environment, `$DELEGATE_ORCHESTRATOR` or `--orchestrator <name>`; an unknown one, or `none`, relays every Lane. Only an orchestrator whose profile declares native Lanes (Claude Code ships one) gets a native pick: it prints `delegate: native …` and then `delegate: spawn: …`, the instruction for starting the named agent in this harness. Follow it; the agent's final message is the return claim; log it with `delegate log --lane <lane> --secs <s> --status <status> --work … --verdict … --class …`.

The rule: each class has a floor and a ceiling in `routing.json`. Eligible lanes are enabled, have `floor <= tier <= ceiling`, meter remaining at or above `gate`, and the harness CLI on PATH; sort by tier ascending, then `order` ascending (the lane's place inside its tier, which Orin sets on the setup wizard's review page; a lane without `order` sorts after every lane with one), then pace descending, then lane name ascending to break a tie; the first is the pick unless a later lane's pace beats the pick's pace by `margin`, which steals the job. Because `order` sorts ahead of pace, a steal can happen inside a tier: a lane lower in the order runs when its meter is well ahead of the pick's, which is the load balance. A catalog with no `order` ranks as before, where pace orders a tier and a steal only crosses tiers (ticket 28). A meter whose probe is unknown sorts last and never blocks. When nothing is eligible the command stops with the reasons and starts nothing. When the output starts with `STOP: no lane eligible for <class>`, the process has already exited 1. Show those veto reasons to the user and ask which to do: abort, named dispatch to a lane they name (`dispatch --lane`), or a one-job exception they state in prose. Wait for that answer before starting a worker. `--tier` only raises the floor inside the Range and never admits a tier the Range does not hold; overflow is the one rule that reaches past the ceiling, and it applies to a `--tier` job like any other.

Overflow is the one path past a Ceiling. When subscription usage is the only thing stopping the Range — at least one carried Lane in it is under the Gate, and every veto there is a Gate veto or an absent CLI — ranking admits the Tier above the Ceiling and ranks it by the same rule, one Tier at a time, never below the Floor and never into Tier 4. A Lane whose Harness CLI is absent counts like a Lane switched off, because the catalog is shared across machines and this one cannot run that Lane; it neither causes the outage nor blocks the answer to one. The header then carries a second line, `# overflow: ceiling 2 -> 3, all in-Range Lanes under Gate`, and `--json` carries the same record at `overflow`; the `ceiling=` in the first header line stays the Class's own, which is still what `--tier` is bounded by. Any other veto in the Range, a Range with no carried Lane at all, a Range whose carried Lanes are every one of them cli-absent with no Gate veto among them, `routing.meters` off, or `routing.overflow` false all keep the stop. Treat an overflowed Pick as the Tier it came from: it costs more usage than the Class asked for. The script does not prompt. With `routing.meters` on, Meters are probed at run start and run finish.
With it off, automatic probes, Gate vetoes and Margin steals are disabled;
ranking uses Tier, Order and Lane name. Class Range and Harness checks still
apply. Gate and Margin stay stored. Cached Remaining can still be shown, marked
as metering off; `delegate status --refresh` is an explicit refresh.

The floor is the default; pass `--tier <n>` when the job needs judgment, using a value inside the Range the rank header prints (`floor=` `ceiling=`). `assets/classes.md` says when to raise.

A harness constraint comes only from the user: `/delegate agy <task>`, or a standing instruction such as "use agy for all delegated work". Pass it as `--harness agy` to `delegate run` (or `delegate rank`); ranking then runs on that harness's Lanes only, with the Range, Gate, Pace and Margin unchanged inside it. An unknown or uninstalled harness is refused with the list of installed ones; show that to the user. Never choose a harness constraint yourself, for example to spend a quota.

Other prose constraints in the request (models to exclude, a ceiling on effort): read the `delegate rank <class> --json` rows (with `--harness` if one is stated), drop the ones the constraints exclude, consider only `eligible: true` rows, and dispatch the top survivor with `delegate dispatch --lane <name> --class <class> --brief </abs/brief.md> --cwd </abs/project>`. An effort cap like "maximum effort medium" filters on each row's `effort` (`low < medium < high < xhigh < max`); never pass `--effort` to get under it. State the pick and the reason in one line before dispatching. Do not use `--harnesses` as a filter: it declares which CLIs are present. If the constraints eliminate every lane, stop and name the constraint that did it; never fall back to a lane the user excluded.

## 3. Verify and log

`return.json` is a claim. `status` other than `done` is not a success; `blocked` carries its reason in `deliverable`. Read the evidence, diff `changed_files`, run the checks yourself. Then log the adjudication with the thread from the `delegate-metrics:` line:

    delegate log --work "<2-4 words>" --run <run-dir> --verdict clean|findings|partial|failed [--outcome "<phrase>"] --class <class>

`--run` takes lane, seconds, status, thread, and the token cost from the run directory; `delegate cost <run-dir>` prints one run's cost breakdown, or `unmeasured` when the relay reported no tokens (Codex today).

`delegate status` prints remaining quota per meter; `delegate runs` prints recent adjudicated dispatches. Print these, never a hand-built table.

## Workflow callers

A Workflow script has no shell primitive. The `courier` agent is an optional wrapper for that case only: it runs the same `delegate dispatch` command and relays `return.json`. Nothing on the main path needs it.

## Health

`python3 tests/test_catalog.py`, `tests/test_rank.py`, `tests/test_dispatch.py`, `tests/test_browser_probes.py`, `tests/test_events.py`, `tests/test_report.py`, `tests/test_usage_reset.py`, `tests/test_bench.py`, `tests/test_setup.py`, `tests/test_setup_tui.py`, `tests/test_delegate_command.py`, `tests/test_evals.py` after touching the matching file. `make eval-ping` and `make eval-orchestrate` run the end-to-end evals on this machine's harnesses; add `EVAL_ARGS=--offline` for the fake relay. `python3 scripts/browser_probes.py` runs the disposable and agent-profile browser probes across all harnesses (`--dry-run` to preview commands); live runs send real workers and spend quota. A native lane's rows read `NATIVE`: dispatch that lane with the probe brief yourself and spawn the agent its native line names. A pass counts only with evidence the browser was used, such as Playwright's page snapshots in the probe's working directory; the nonce alone can be copied from the brief. `sh scripts/ads.sh check` confirms the pinned relays; `sh scripts/ads.sh install` restores them. A model slug that stops resolving is edited in `lanes.json`; `agy models`, `codex debug models`, `grok models` list the current ones.
