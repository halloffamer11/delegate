# The catalog

Where routing reads its lanes, meters and classes, and how to change them.
The catalog is machine-local: each machine keeps its own, never in the repo.

## Contents

- [Files](#files)
- [Class guides](#class-guides)
- [Checking and showing](#checking-and-showing)
- [Focused changes](#focused-changes)
- [The wizard](#the-wizard)
- [Model evidence](#model-evidence)

## Files

- `~/.config/delegate/lanes.json`: meters and lanes. A lane has a harness,
  model, effort, meter, meter weight, timeout, price, tier and basis, and may
  have `enabled`, `order` and `published_as` (the names benchmark sources
  print for its model, such as `["Fable 5.1"]` on a `claude-fable-5-1` lane,
  needed only where case and separators do not bridge the two).
- `~/.config/delegate/routing.json`: `classes` (a floor and a ceiling per
  class), `margin`, `gate`, optional `meters` and `overflow` (booleans, on by
  default), and optional `tier_proposal` (the rule the wizard proposes tiers
  by). A catalog that writes no `classes` gets the five shipped classes with
  the ranges in `assets/samples/routing.json`. A class may also set `leash`
  (a boolean): false drops the preamble's leash sentence for its jobs.
  Shipped, impl and hard-impl set it false; a class without it inherits the
  shipped class's value, else keeps the leash. `--no-leash` drops it for one
  job.
- `<git-root>/.delegate/routing.json`: a project's override of any routing
  key; `classes` merges per class and per key. `project_order` places lanes
  inside a tier for this project.
- `<git-root>/.delegate/lanes.json`: a project's tier for a lane the global
  catalog has, and nothing else: `{"lanes": {"<lane>": {"tier": 2}}}`. The
  effective tier is the project's where it names one; range, gate, overflow
  and the tier leaders all read it. A lane the project moves sorts after the
  lanes with an order in its new tier until `project_order` places it.

Both JSON files are strict JSON, validated on read with a message naming the
field and the rule, formatted on write, and take `note` fields anywhere. The
starting catalog ships in `assets/samples/`. A project's `.delegate/` never
goes to the main branch.

## Class guides

`assets/classes.md` holds the judgment for the five shipped classes: intent,
signals, examples, counter-examples, and when to raise `--tier`. This machine
(`~/.config/delegate/classes.md`) and a project (`.delegate/classes.md`) may
overlay `##` class sections. A section for a shipped class replaces it; a
section for a class the catalog adds is that class's guide.

A class is added with both a floor and a ceiling in `routing.json` (global or
project) and a section in an overlay, never one without the other. A guide
never declares a floor or a ceiling.

## Checking and showing

- `delegate catalog show`: the effective catalog for the current directory,
  with where each value comes from.
- `delegate catalog check <file>`: validates one file. On stderr, without
  failing, it warns when one meter serves every carried lane of a tier, since
  that meter under the gate takes the whole tier with it.
- `delegate catalog check-guide`: validates every class guide together
  against the effective routing, naming a class with a range and no section,
  or a section with no range.

## Focused changes

One field at a time, previewed before it is written:

    delegate catalog set lanes.<lane>.tier <n> --scope global|project
    delegate catalog set routing.gate|routing.margin|routing.meters|routing.overflow <json> --scope global|project
    delegate catalog range <class> <floor> <ceiling> --scope global|project
    delegate catalog order <lane> <position> --scope global|project

All take `--cwd` and `--config-dir`. `--scope project` writes
`.delegate/lanes.json` for a tier (a project tier equal to the global one
removes the entry) and `.delegate/routing.json` otherwise. Order is one-based
among the carried lanes of the same tier.

Each command first prints a JSON preview: the source files and resolved
targets, the changed fields, and the picks and tier leaders before and after,
from cached meters. Apply the same operation with `--apply --expect
<revision>` from that preview. A request that states the value authorizes
both; do not ask again. If a source changed since the preview, preview again.
Apply preserves stow links and writes only the chosen document.

`delegate setup --screen carry|tier1|tier2|tier3|tier4|review|routing` opens
one wizard screen on the current catalog. Its confirm lists only the changes
made, and a save with none writes nothing. On a focused tier screen,
unmarking moves a lane down one tier; turn a tier 1 lane off on the carry
screen. Use the CLI commands above where there is no terminal.

## The wizard

`delegate setup` (also `delegate global`, or `make delegate-wizard` in the
checkout) builds or revises this machine's catalog. At start it fetches the
Artificial Analysis rows (cached for 24 hours) and asks each installed
harness for its models, then proposes the current generation in memory: a
lane for every effort of every current model, each new lane in its
predecessor's place with its tier, order, meter, weight and timeout, and a
superseded model's lanes removed. New lanes carry `UNMEASURED` and `UNPRICED`
notes: prices are never proposed, so read them off the vendor's page.

The pages then decide, in order: which lanes to carry, each lane's tier (the
tier pages show a proposed tier from the benchmark bands in `tier_proposal`;
`p` takes them), the order inside each tier, and the routing values. Nothing
is written until the confirm page, and quitting writes nothing. The save also
writes the agent file of each new native lane where the orchestrator profile
keeps them, and removes superseded ones.

`delegate project` opens the dashboard for the current directory's Git
project.

## Model evidence

    python3 scripts/bench.py model <model> --effort-rows <file> [--effort-rows <file> ...] [--epoch-csv <file>] [--json]

A read-only inspection that fetches nothing. It separates evidence about the
model family from rows measured at a lane's exact effort, shows unresolved
identities and absent rows, and keeps board versions and cost bases apart.
Standing is within the loaded snapshot. A research link is a reference until
its rows pass the acceptance pipeline.
