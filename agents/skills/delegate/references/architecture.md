# Delegate architecture

What each script and asset owns. This file is the implementation authority for
the scripts; `SKILL.md` is the authority for how a session routes.

## Contents

- [Project routing](#project-routing)
- [Scripts and assets](#scripts-and-assets)
- [Read-only per harness](#read-only-per-harness)
- [Browser use per harness](#browser-use-per-harness)
- [Benchmark data](#benchmark-data)

## Project routing

Project routing changes go through `catalog.load_catalog()`: a flat `project_order`
projects carried lanes within their effective Tiers and preserves Order provenance. A
carried Lane it does not name takes its place by global Order (`_place_by_global_order`,
ticket 30), so a successor the wizard gave its predecessor's `order` lands where the
predecessor sat.
Validate complete save proposals with `catalog.validate_project_routing()` against
the original global documents, not projected lane records. A project may also set a
Lane's Tier in `<git-root>/.delegate/lanes.json`, that field and nothing else
(`catalog.validate_project_lanes()`, ticket 32). `_effective_lanes()` applies it
before the Order projection, so every Tier reader sees the effective Tier and a moved
Lane loses its global place in the Tier it left; `catalog.project_tier_changes()`
names the Lanes in effect for `show` and the rank header, and `edit_catalog(op="set",
field="lanes.<lane>.tier", scope="project")` writes that one file, with the same
preview, `--expect` revision and apply sequence as `project_order`. For exact-Tier previews,
use `rank.tier_leaders()`; it and the Class-facing `rank()` share the ranking core.
`usage.read(routing, freshness, path=...)` returns the Meter snapshot, with the
usage-limit holds in `limits.json` beside the document it read (`usage.hold`,
`usage.release`); `Snapshot.of(document)` reads an in-memory document, which carries no
hold. CACHED never probes or writes; FRESH probes when the reading is older than
`max_age_min` (10) or absent; FORCED probes now. Either probes only with
`routing.meters` on, or with routing None (`delegate status --refresh`), in the usage.py
child process (`--refresh --cache PATH`, so it writes the read's own path) under one
180 s bound, and writes nothing to the Ledger; a probe that fails or runs late gives the
last reading when it is fresh enough, else status `stale` (ticket 18). `rank.py` reads
FRESH for a Class and CACHED for `tiers` or `--meters`; `delegate run` reads FRESH
(CACHED with `--meters` or `--no-probe`), and its dispatch reads FRESH before the relay
and FORCED after it, so a run probes once before its relay and a named dispatch over a
fresh reading does not; `--no-probe` reads nothing; `report.py limits` reads FRESH, or
FORCED with `--refresh`. `Snapshot.readout(meter, cat)` joins one Meter with a
catalog: Remaining, Pace, the Weekly figure, `gated` (the Gate predicate: unknown
Remaining never vetoes, Remaining equal to Gate passes, and nothing is gated with
`routing.meters` off), `week_dollars` and `held_until`; `readout(meter, cat, spend=x)`
is the same Meter with x more of its week spent (the Weekly figure falls by x, Pace and
`gated` follow, and a held Meter stays at 0). `rank_range`, `rank` and `tier_leaders`
take only a snapshot: `rank_range` reads each Lane's Meter once into a map, Meter to
Readout, and a private core ranks over that map, so a what-if replaces one Readout and
ranks again with no second read (ticket 18); the dashboard and `catalog_edit` hand it
the snapshot they read (ticket 16). Every row carries one `cause` from `rank.CAUSES`
(pick, steal, eligible, unknown, or the veto: disabled, floor, ceiling, gate, cli);
`eligible` and `pick` follow from it, the `reason` text is its display, and the
dashboard and the deck read `cause`, never the text (ticket 20). `tier_leaders` reads
the snapshot once and gives each Tier its `steal_threshold` (`{unit, value}` in the quota
unit) and `pace_to_lead` (`{meter: pace or None}`): it reruns the core with one Readout's
Pace replaced (`dataclasses.replace`) at 0 and at the first two 0.01 steps at or above
each value where that Meter's Lanes cross a rival in the sort or a steal, up to
`usage.MAX_PACE`, and the deck's aid and the usage popup draw those (tickets 21 and 22).
Each Tier also carries its `handover` (`{points, to}` or None): rank reruns the core with
the leader's Readout replaced by `snapshot.readout(meter, cat, spend=x)` in half-point
steps, at most 200, until another Lane leads or the Meter falls under the Gate, and
reports quota points, never a time; the popup only renders it (ticket 23). Rank's sort
key, steal test and choice are private, so nothing outside rank replays its Pick.
The statusline, the popup's Meter rows, `report.py limits` and the deck's Gate draw each
Meter's Readout, so every display shows one Weekly figure and one Gate per Meter (ticket 17).
One validity rule serves every reader: valid envelope and legacy map formats keep their
behavior; any malformed observation makes the whole document unknown. Envelope observations require a finite
timestamp; raw Window/reset fields are validated before display. Every Meter
derives its combined figures through one private arithmetic in `usage.py`: Remaining is
the lower Window fraction and Pace comes from the weekly Window. agy runs through it
like the Claude Meters, and its note says the combined figure is the lower Window, an
assumption, not a vendor bound (ticket 31, reversing modular ticket 13). A cache
written under that older rule holds the Windows beside a null Remaining and Pace, so a
read derives them rather than probing again. This intentionally
replaces partial use of invalid documents. `usage.py`'s public names are its interface:
CACHED, FRESH, FORCED, `MAX_PACE` (one over the cycle floor, 50: the highest Pace a Meter can
read), `read`, `hold`, `release`, `cache_path`, `Snapshot`, `Readout` and `main`, and
`usage.py --pretty` prints one line per Meter from its Readout (ticket 19).

## Scripts and assets

- `scripts/catalog.py`: the two configuration files (`~/.config/delegate/lanes.json`,
  `routing.json`, project overrides `.delegate/routing.json` and `.delegate/lanes.json`): load,
  validate and project the effective catalog, and nothing else (ticket 26). It imports no other
  delegate script but `harnesses` and `lane_evidence`, so `rank` can import it with no cycle.
  `write_json` carries the link rule for every catalog document, `catalog fmt` included: a link to
  an existing file is written through and stays, and a dangling link or a loop is refused
  (`link_target`; deepening decision D.1).
  The efforts a harness offers are its adapter's `efforts`, with the command or page that proved
  each list; `check` and `delegate.py --effort` refuse anything outside them (ticket 19).
- `scripts/catalog_commit.py`: the write path for catalog documents (deepening D). `read()` is the
  Catalog read: the global pair, and the project pair when given a directory under a Git root, each
  file's bytes, link and resolved path, and one revision over them all; it parses strict JSON,
  validates, and refuses a dangling link or a loop. `commit(read, documents)` validates with the
  same validators, refuses an Intervening edit (`CatalogChanged`, naming each changed document),
  skips a document equal to its read, copies each global document it replaces to
  `<config dir>/backups/<name>-<UTC stamp>.json` (the newest 20 per document kept; project
  documents are not backed up), writes through links, and puts back what it already wrote when a
  later write fails. A commit whose documents include the live catalog's global lanes (the config
  dir resolves to `catalog.CONFIG_DIR`) then gives every native Lane its Agent file and removes the
  file of each native Lane it took out; another catalog, or project documents alone, write none.
  Last it forgets the Model queue entries its read returned (`read(queue=True)`). A failure in
  either step is a line in `Committed.lines`, which callers print to stderr. The wizard's saves
  commit through the read taken at launch, and dispatch's scan and `edit_catalog`'s apply commit
  through theirs. No other script writes a catalog document, except `catalog fmt`, which formats
  one named file through `catalog.write_json`.
- `scripts/catalog_edit.py`: revision-checked `set`/`range`/`order`. `edit_catalog()`
  previews cached Picks and resolved source paths from `catalog_commit.read()` and validates
  complete proposals. An apply checks `--expect` against that read's revision, then commits its one
  document with `catalog_commit.commit(read, {dest: doc})`; a `CatalogChanged` there is the same
  "intervening edit" refusal, and `Committed.lines` go to stderr, so `catalog set`'s JSON stdout is
  only the result. A global apply backs up the document it replaces, and one that writes the live
  catalog's `lanes.json` keeps the Agent files in step; a project apply, the dashboard's only
  write, does neither. An empty customization over an absent file is a noop and commits nothing.
  `plan_edits()` is the one planning path (ticket 14). It takes the source documents already in hand and a list of the same
  `set`/`range`/`order` operations, plans each one onto the documents the one before it produced,
  and returns named fields: the four planned documents, the effective `catalog` they produce, and
  one `steps` entry per operation with its `dest` and `values`. It reads no Meter and writes
  nothing. `edit_catalog()` plans its one edit through it, and so does the dashboard's staged view,
  so there is no second planner to drift.
- `scripts/catalog_draft.py`: the Draft (deepening F). `CatalogDraft(lanes_doc, routing_doc,
  whole=)` holds the catalog setup started from and every decision made since: verbs `carry`,
  `place` (with `at` a place, clamped, or `"end"`), `apply` (tier lines with `unnamed="off"`, the
  tier proposal with `"keep"`), `set_routing` and `settle`; answers `is_settled`, `lane`,
  `tier_lanes`, `documents()` and `changes()`. `documents()` is `{"lanes", "routing"}`, keyed by
  `catalog_commit.DOCUMENTS` names, so `catalog_commit.commit(read, draft.documents())` takes it
  whole; `changes()` is its field diff against the documents as given. It owns the rules for placing
  a Lane in its Tier: a Tier as given is numbered by `catalog.carried_in_tier` (Order, a Lane
  without one after every Lane with one, then lane name, the one tie-break that `catalog set`,
  `catalog order` and Project order also use); a Lane joining another Tier goes to its end; a Lane
  returning to its start Tier takes back its starting place, so undo is exact. It owns both save
  scopes: `whole=True` numbers every carried Lane 1 to n and writes `enabled: false` only on off
  Lanes; `whole=False` writes only changed fields and numbers a Tier only when its sequence changed
  or lines or a proposal set it. It owns the meters-on rule too (no key where the catalog had none).
  It never mutates what it is given and validates nothing; the commit does. A draft compares by
  value and is never hashed. `setup.py --plain` decides on one with `whole=False`, and
  `setup_tui.Wizard` keeps one as `self.draft`: `whole=True` in the full wizard, `whole=False` on a
  focused screen.
- `scripts/catalog_cli.py`: `delegate catalog` (`show`, `check`, `check-guide`, `fmt`, and the
  edits above). `scripts/class_guides.py`: the Class guide checks behind `check-guide`.
  `scripts/tier_lines.py`: the parser and summary line for bulk Tier lines; the Draft applies them.
- `scripts/lane_evidence.py`: which benchmark rows belong to which
  Lane. `LaneEvidence(lanes_doc, rows)` attributes every row once, by the Model its printed name
  names (the lane field `published_as` names the Model, so it reaches every Harness that runs it)
  and the effort it states; a row's printed names are its `model`, then its `slug` (an Epoch
  row). `lane_rows`, `model_rows`, `available`, `unmatched`, `records` (one per row: its identity,
  `model_key`, the Model's display name `lane_model`, `model_lanes` and exactly the `lanes` whose
  `lane_rows` hold it) and `identify(name)` are lookups. The carry pre-screen, the Tier proposal,
  the wizard, the report, model inspection and the benchmark page read one. `model_identity(lane)`
  is the key "one Model" means across Harnesses (kiro's `claude-opus-5.5`, agy's
  `claude-opus-5-5-high` and Claude Code's `claude-opus-5-5` are one), which the pages group Lanes
  by. `published_as_conflict(lanes)` is `catalog.validate_lanes`'s check that one published name
  denotes one Model: one name may sit on the Lanes of one Model on several Harnesses, never on two
  Models, and no entry may be another Model's name. It is the one place a printed name is
  normalized for Lane attribution, and it imports only `harnesses`.
- `catalog.single_meter_tiers`/`meter_dependency_lines` name each Tier whose carried Lanes all drain one
  Meter; `check` prints them to stderr as warnings and the wizard's review page as legend lines,
  neither failing nor judging the Tier (ticket 29). `assets/samples/`: the starting catalog from the
  spec.
Classes are data (ticket 16). `CLASSES` names the five shipped Classes; their default Ranges are the
ones in `assets/samples/routing.json` (`default_class_ranges`). `merge_routing` lays the defaults
under the global document, so a catalog that writes no `classes` ranks exactly as one that writes
the sample's, a catalog's Range for a shipped Class replaces the default, and a Class it adds (a
name matching `CLASS_NAME`, with both floor and ceiling once merged) sorts after the five
(`class_names`). Its guide section lives in an overlay, `<CONFIG_DIR>/classes.md` or
`.delegate/classes.md` (`guide_files`); `check_class_guides` validates every guide together, naming
a Class with a Range and no section, or a section with no Range. `check` on a routing file and
`check-guide` with no file run it.
- `scripts/rank.py`: the selection rule over the catalog and the live meters (class floor and
  ceiling, gate; sort by tier, then the lane's `order` inside its tier, then pace, then lane name;
  pace margin). A catalog with no `order` ranks as before ticket 28. Optional `routing.meters`
  defaults on; off bypasses Gate/Margin and Pace, leaving Tier/Order/name selection. Optional
  `routing.overflow` defaults on: when at least one carried Lane in a Class Range is under the Gate
  and every veto there is `gate` or `cli`, `rank()` admits the Tier above the Ceiling and ranks it
  by the same rule, one Tier at a time and never Tier 4 (`gate_only_stop`, `OVERFLOW_TOP_TIER`;
  ticket 29). A cli-absent Lane counts like a disabled one — the catalog is shared across machines
  and this one cannot run that Lane — so it neither causes the outage nor blocks the answer to one;
  the veto precedence in `rank_range` records a Lane failing both Gate and CLI as `gate`, and either
  reading decides the same. The Pick carries the `overflow` record, the header prints it as a second
  line, and every other veto kind, plus a Range with no gated Lane in it, keeps the stop. Automatic
  acquisition callers honor the effective project override; explicit limits refresh still works.
- `scripts/delegate.py`: one run through a pinned ADS relay (`dispatch`), and rank-then-dispatch
  (`run`); a Lane whose harness is the orchestrator's, under a profile that declares native Lanes,
  prints the native line and the profile's spawn line instead of starting a relay. `dispatch.json`
  records the orchestrator. `--json` on either prints one object in place of the finish and
  metrics lines (`run --json` sends the ranking to stderr); the courier, the evals and the
  browser probes read that or `runs.parse_finish_line`, never a regex of their own.
- `scripts/runs.py`: the Run module (ticket 24; delegate-deepening 01 to 04). `execute(request,
  prompt, work)` runs every Run from its start to its Outcome: the run directory, `prompt.md`,
  `dispatch.json` and the Ledger start, then the work, then `return.json`, the outcome, the
  Usage-limit hold (`usage.hold` and `usage.release`, beside the cache every reader reads) and the
  Ledger finish. Relayed work (`delegate.relay_work`) runs, in order, the preflight,
  `usage.read(routing, FRESH)`, the relay through `relay.run(job, run.path)`, which returns the
  `Finish`, and `usage.read(routing, FORCED)` (no read with `--no-probe`); the relay is
  `relays.Ads(ads_dir)` unless the caller hands one to `dispatch(relay=...)` or `run(relay=...)`.
  A native Run ends as a hand-off: its work returns a `HandOff` (the agent and the spawn line), and
  the Run ends at once with status `native`, reason `handed to <agent>`, secs null, no
  `return.json` and the Meter left as it is; `report.py log --run` reads status `native` for it and
  still asks for `--secs`. Anything that stops the work, SIGTERM included, ends the Run blocked
  with why; a write that fails becomes a note and never stops the Run ending. Only here are
  `dispatch.json`, `return.json` and the Ledger written; `Ended.text` spells the finish lines,
  or the native and spawn lines, and `parse_finish_line` and `parse_native_line` read them.
  `running(now)` lists the Runs still running: a Ledger start with no finish, whose
  `dispatch.json` has not ended, within its Lane's timeout. It skips a Ledger line it cannot read
  and never raises, and `report.py statusline` counts its glyphs from it. Run directories under
  `~/.cache/delegate/runs/`, never reused.
- `scripts/relays.py`: the Relay seam (delegate-deepening 05, 07 and 08). `Relay.check()` says in
  one line why relays cannot run here, or None; `delegate.resolve` asks it for a relayed Lane before
  a Run starts, and a refusal exits 2 with nothing started. `Relay.run(job, run_dir)` runs one
  relayed `Job` and returns a `runs.Finish`; the module defines no outcome type of its own. The
  `Ads` adapter alone knows the ADS directory (the argument, else `$ADS_DIR`, else
  `relays.DEFAULT_DIR`, which a test holds equal to `ads.sh`'s default), `ads.sh check` (run with
  `ADS_DIR` set to that directory), node, the relay path, the argv (`--brief --cd --out-dir --model`
  plus `Harness.run_args`) and env overrides, `relay.stdout` and `relay.stderr`, every `result.json`
  key (each usage spelling it normalizes into Token counts `{in, out, cache_read, cache_write}`,
  keyed like a Lane's price record, or None when the relay reported neither input nor output; the
  raw record stays in `result.json`), the form of node's crash output (the `<Name>Error: ...` line,
  never the `Node.js v...` trailer) and, through `Harness.blocked_reason`, `events.jsonl`. It
  returns a blocked `Finish` for every way a relay fails (node missing at spawn, no `result.json`,
  one that does not parse or is not an object) and catches only `OSError` and `ValueError` (and
  `RecursionError` from a `result.json` nested too deep to parse), so Ctrl-C and SIGTERM reach
  `runs.execute`. Settling is the private pure `_settle(report, job)`: the status table in the
  module docstring, the return-block scan, the caps and the read-only tripwire. `Scripted` is the
  in-process fake, scripted with `Report`s (its check answers `ready`), so `tests/test_relay.py`
  tests settling with no node, and `dispatch(relay=Scripted(...))` runs in-process. Its `Ads` cases,
  `tests/test_dispatch.py` and `evals.py --offline` share one `evals.OfflineWorld`
  (delegate-deepening 06): the sample catalog, the fake relay in a fake ADS tree, a `git` that
  answers the pin, stub CLIs, a `sandbox-exec` that nests and an env that keeps the host's CLIs,
  Ledger, Meters, codex home and orchestrator out; `world.stub(name, body)` replaces one CLI and
  `world.path_without(name)` hides one.
- `scripts/ads.sh`: installs and checks the relay layer, **halloffamer11/delegate-skills** (our fork
  of amElnagdy) at commit `b6ec937700174947234f4f46e4d793d78270545b` (branch
  `claude/delegate-any-harness-next-v75vlw`), in `~/.local/share/delegate/ads`. `ads.sh install` is
  reproducible from that constant. The fork carries the grok and agy read-only fixes (redesign
  ticket 14; upstream PRs #119 and #120) and the `kiro-delegate` relay (any-harness ticket 14, not
  yet offered upstream).
- `scripts/orchestrators.py`: orchestrator profiles, data not code paths (ticket 13). A profile
  (`assets/orchestrators/<name>.json`, or a machine's own in `~/.config/delegate/orchestrators/`,
  which overrides a shipped one) names its harness, the env vars that detect it, its headless
  `launch` for eval 3, and optionally `native`: its agents directory, agent name and file, the agent
  file template and the spawn line. `resolve()` takes `--orchestrator`, then
  `$DELEGATE_ORCHESTRATOR`, then detection; `none`, an unknown name or nothing detected is the
  default path, where every Lane is relayed. No other script names an orchestrator
  (`tests/test_orchestrators.py` greps for it). A profile's optional `agents` lists agent files only
  that orchestrator uses, kept beside it and linked by `make install` (`orchestrators.py agents`):
  Claude's `claude/courier.md`, the glue a Claude Workflow script needs because it has no shell.
- `scripts/harnesses/`: the harness registry, one module per harness behind one interface
  (`base.Harness`). Callers ask the adapter's verbs and branch on no harness flag (ticket 23):
  `installed()`, `meters()` (the absent and failed rows live there once; each adapter's
  `read_meters` reads the rest), `models()` and `generation()` (the Claude adapter's catalog plus
  benchmark-names strategy), `owns(slug)`, `effort_for(lane, override)`, `blocked_reason(run_dir)`
  (grok's gate cancel), `starter()`, and the relay flags. Every other script iterates the registry;
  adding a harness is one module and one `REGISTRY` entry. `kiro.py` (ticket 15) is the first
  harness whose binary is not its name (`kiro-cli`) and that serves every vendor's models (its
  `owns` is always true): the refresh offers all its current models, and its first Lanes, with no
  Lane on the harness to copy from, start from the adapter's `starter()` (plan and price assumed,
  Remaining unknown, so the Gate never vetoes it).
  Its listing's JSON field names are not documented, so `parse_models` reads the plausible
  spellings; `tests/fixtures/kiro/kiro-models.json` is an assumed shape until a real listing
  replaces it.
- `scripts/usage.py`: cached subscription-meter probes; each harness's probe is in its adapter.
  An adapter's `read_meters` hands back `harnesses.base.Windows` (meter, group, five_h, weekly,
  reset_5h, reset_weekly, note, weekly_model) through `Harness.windows(group, ...)`, with the
  probe helpers `run_cli` and `iso_time` beside them in `base.py`, and imports no usage;
  `usage.py` builds each row from them, holding fractions to 0..1, taking a Model meter's lower
  week as its Weekly figure and deriving the combined figures (ticket 19). A usage row is keyed
  by `meter`, the full Meter name (`Harness.meter_name(group)`), with `group` the probe's own
  word; a row cached before ticket 25 (`lane` the name, `meter` the group) is upgraded on read.
  Each adapter's `meter_names()`/`reports_meter()` say which Meters its probe reports, and
  `catalog check` refuses a Lane on any other (ticket 25).
  A probe writes nothing to the Ledger, which records Runs only; the latest Meter reading lives
  in the usage cache. `runs.py` owns the Ledger: its v1 start and finish lines (schema unchanged;
  a native Run's finish has `secs` null and `rc` 0), `$DELEGATE_LEDGER` (`runs.LEDGER_ENV`, which
  the offline world sets), and `running`, through which the statusline reads it.
- `scripts/model_queue.py`: models the catalog lacks, queued for the next `delegate global`
  (ticket 29). At most once a day, dispatch starts a detached scan that runs the wizard's own
  `discover` and `refresh_catalog` against the global lanes and queues each model no Lane runs.
  `dispatch --model` naming such a model queues it too. The queue is `new-models.json` beside the
  meter cache. The full wizard reads it with the catalog (`catalog_commit.read(queue=True)`) and
  its start facts name it ("Dispatch noticed") whether or not the refresh ran; its save forgets
  exactly the entries those facts named and keeps any noted since (deepening D.4, which replaces
  any-harness ticket 29's "the wizard's confirm write empties the queue" and the rule that a run
  whose refresh did not run keeps it). Focused screens read no queue and forget nothing.
  `$DELEGATE_MODEL_SCAN=off` stops the scan. A newer version of a model the catalog already runs
  is not queued but applied (ticket 44 of the redesign): the scan swaps each Lane the refresh
  replaces with its successor into lanes.json, keeping Tier, Order and an off Lane off, through a
  Catalog commit, so the old lanes.json is backed up to `<config dir>/backups` and the Agent files
  follow. A catalog that changed while the scan listed models (`CatalogChanged`) is left to that
  writer, and the newer version is queued instead. The scan imports `catalog_commit`, never
  `setup` or `catalog_edit`. The wizard names the swaps ("Dispatch swapped in").
  `$DELEGATE_MODEL_APPLY=off` keeps the scan to queueing.
- `scripts/report.py`: limits, runs, and the lead's run ledger. `log --run` and `cost` price a Run
  from `dispatch.json`'s `tokens` and the Lane's price record (`compute_cost(tokens, lane, catalog)`,
  delegate-deepening 08); null tokens, or a Run directory from before them, are unmeasured, never
  $0. `scripts/bench.py`: the human-only benchmark ranking under `~/.cache/delegate/bench/`; no
  routing code reads it. Artificial Analysis
  comes only from the rows `effort.py aa` accepted, passed as `--effort-rows` (no API, no key;
  ticket 19): the AA columns are the component benchmarks some lane has a figure for, with cost per
  task beside them and the composite never a column. `collect()` returns two views of the same
  figures, from one `LaneEvidence` for the Epoch rows and one for the accepted rows: `models` (the
  records of each catalog model's `model_key`, its Model at any effort, for comparing against
  models nobody runs; each figure names the Lanes that claim it) and `lanes` (each Lane's
  `lane_rows`, with `mean`/`n` over those). `collect(lanes_doc, epoch_rows=None, effort_rows=None)`
  takes rows and acquires nothing; with no Epoch rows it keeps every AA column and reports Epoch
  skipped (`epoch_skipped`). The report reads one Benchmark snapshot (`read_snapshot`): Epoch from
  `--epoch-csv`, else from the web through the snapshot's 24-hour cache, and AA only from
  `--effort-rows`. An Epoch that cannot be fetched is skipped with the reason on its line and the
  report is still written; a named file that cannot be read exits 1 with "bench: <reason>".
- `scripts/bench_snapshot.py`: the Benchmark snapshot, the one place benchmark rows are acquired.
  `snapshot(row_files, aa=, epoch=, renew=)` takes one adapter per source: `web()` (the web through
  the cache), `fixture(dir)` (`aa-accepted.json` and `epoch.csv`) or `local(path)` (one named file).
  It returns the accepted rows, with the AA adapter's rows in place of the named AA rows, the Epoch
  rows (each keeping `model` and `slug` for `LaneEvidence`), each source's `Origin` (fetched, cache,
  file, rows or none, with its age and why it is not fresh), `errors` (one line per named input that
  could not be read; a bad accepted-rows input refuses every accepted row) and `note`, the start
  page's rows line. It never raises for a source, and `load_effort_rows` is the one accepted-rows
  reader. The cache is `~/.cache/delegate/bench/`: `aa/` exactly as `effort.py aa` writes it and
  `epoch/eci_benchmarks.csv` as served. Each artifact is fresh for 24 hours after its mtime; a fetch
  writes into a temporary directory beside the source's and moves the artifact in last, only after
  it parsed (`effort.aa_accept` extracted and checked it, or the CSV's header matched); a failed
  fetch keeps the newest copy on hand, whatever its age, before the named rows. `renew` (the `r`
  key) refetches AA only. `fixture` and `local` open no URL and never touch the cache. It imports
  `effort` and nothing that routes; `effort.fetch_page` is still the one function that opens a URL.
  Display order lives beside `collect` (`group_lanes`,
  `lane_order`), and so does the carry wording (`carry_reason`); the carry policy itself is
  `scripts/carry.py` (ticket 27): `beats()` and `decisions(lanes_doc, evidence)`, which returns
  structured decisions `{lane, enabled, kind, source, competitor}`; renderers own the wording.
  `format_collection(data, snapshot, date)` turns a `collect()` result into the Markdown report, and
  each source's line says where its rows came from by its `Origin`: "fetched <date of the fetch>",
  "read from <file>" or "skipped (<why>)". `bench.py model MODEL` reads only the named accepted
  rows and Epoch CSV, never the cache, and never fetches: `inspect_model(query, lanes_doc,
  effort_rows, epoch_rows)` takes rows and builds its `LaneEvidence`. The query names a Model as a
  printed name does (`identify`), so a member slug shows the whole Model, and each of its Lanes
  lists its `lane_rows`. `evidence_records(evidence)` and `epoch_records(evidence)` turn an
  evidence's `records` into display records with board/version standing, cost basis and
  uncertainty, shared with HTML. Model evidence at any effort stays separate from exact-effort
  Lane attribution; a name no Model or two Models answer to stays visible as unresolved.
- `scripts/setup.py`, `scripts/setup_tui.py`: interactive catalog wizard (TUI on a TTY,
  prompt-driven under `--plain` or pipes). Each page makes one decision per line: with the same
  `[x]`/`[ ]` box, the carry page selects a model at an effort and the four tier pages assign a
  tier; the review page after tier 1 orders the carried lanes inside each tier (ticket 28). It lists
  them in sections tier 4 to 1, each numbered in its current order; j/k moves the cursor, J/K or
  shift-up/down moves the lane inside its tier, 1-4 moves it to the end of that tier, and the
  confirm write gives each carried lane `order`, its place from 1 (`catalog.py check` takes `order`
  as a whole number from 1). The confirm page lists each lane as `y` writes it, from the Draft's
  `documents()`: `tier N, order M`, or `tier N` for a lane off (`setup_tui.placement_text`, which
  `--plain`'s confirm listing prints too); its cursor runs over the rows the page draws, as the
  routing page's runs over its settings. The starting order is the Draft's: the Order as read, then lane name;
  lines and `p` put the lanes they name first in their tier, in their order; a lane that joins a
  tier, by a tick or by 1-4, joins it at its end; and undo restores the starting place, so a lane
  ticked back, or switched off and on, returns to its place. Tier pages restore the current catalog
  as their editable defaults: lanes at the current tier are marked, lanes at a lower tier are
  visible and unmarked, and lanes taken by a higher tier or not carried are hidden. A tick places
  the lane at once; an untick returns it to its start tier when that tier is lower, and otherwise
  leaves it for a lower page (on a focused screen, one tier down); entering tier 1 places every lane
  still unplaced, in lane-name order. Enter decides nothing: without edits it keeps the current
  tiers and order, and a lane not carried keeps the tier it started with. Lines applied by `v` or
  `--tiers-from` become the same editable defaults. The routing page explains the setting
  under the cursor in a panel beside the table. The start page, and `--plain` from the same
  `setup_tui.start_facts`, states only facts: the two files, the benchmark page, the discovery
  notices. Setup discovery is one `discover.discover` result; `--no-discover` skips every probe;
  `discover.mjs` is not on the default path. `--plain` calls `bench.collect` and `format_collection`
  in process. `view(width)` fits prose to the terminal; `layout_lines` places a frame and `overlay`
  composes it into the grid a terminal shows. The trail of steps is the top row of every page, the
  title two rows under it, and the bottom is three zones with a blank row between each: the rows,
  the legend, the keys. How each piece looks is decided in one table, `setup_tui.STYLES`, as a role
  name to (attributes, colour); `layout_lines` names the pieces drawn in a style of their own as
  spans (a ticked box, the current step, a key, a reason the data gave) and `_palette` resolves the
  table for the terminal at hand, colour only when it has colours on its own background, weight
  alone otherwise. The legend zone is three things read three ways (`_legend_zone`): `defs`, a
  definition list (`setup_tui.definition`: term, value, meaning, aligned in columns; the carry page
  defines only the reasons on it, the confirm page each routing term with the value it will write),
  then `legend` lines, then `warnings` (the single-Meter Tier lines, drawn as warnings). The routing
  page groups each class under a heading with its first sentence from `assets/classes.md`
  (`class_descriptions`, quoted, never paraphrased; fitted to the room the panel needs), then
  `ranking` for margin, gate and meters; the cursor lands only on a setting. The harnesses page
  shows what the launch scrub found — per harness its status, models listed, and the Lanes the
  refresh adds and removes — with the rows note, and `r` runs the scrub again through `setup.scan`,
  `setup.propose_generation` and `setup.collect_bench` (the callback `main` passes as `rescan`,
  renewing the Artificial Analysis rows past the 24 h cache and reading Epoch from it), after
  which `Wizard._load` builds a new Draft and a new Lane evidence, and the `--tiers-from` lines are
  applied again; it is offered on that page only, before any decision, and a failure is a message.
  It writes this machine's catalog, `~/.config/delegate`,
  which is never in the repo: each machine keeps its own (the user, 2026-09-29). `make delegate-wizard`
  at the repo root runs it with the accepted AA and Terminal-Bench rows (`DELEGATE_ROWS` in the
  Makefile; `WIZARD_ARGS` adds flags). `scripts/bench_page.py`: the HTML board the wizard's `o` key
  opens, which reads its lane order (`bench.lane_order`, `group_lanes`) from `bench.py`, its
  records (`bench.evidence_records`, read once per render and drawn by the plots, the boards and
  the rows tables) and each point's Lanes from one `LaneEvidence`, and the wizard's own verdicts
  (`carry.decisions` on that evidence, asked once per render, never caught) rather than deciding
  any of them again. Its rows table also lists the Benchmark snapshot's Epoch rows (`write` and
  `render` take `epoch_rows`), as `bench.epoch_records` over their own `LaneEvidence`, in the same
  columns; no plot, board or verdict reads them. Points group by the Model's display name, so an
  agy Model's efforts are one sweep; the scores table names the Lanes `collect` says claim each
  figure. Each Lane on a point carries its own verdict, a point is struck only when
  every Lane on it is proposed off, and "beaten by" comes only from an off verdict on the board's
  own source; two off Lanes on one point that lose to different efforts each get their own
  arithmetic in the finding and their own competitor in the rows table. A point no Lane runs takes
  its colour from the evidence's `model_lanes`, the Lanes on the Harnesses that run its effort.
  HTML carries kind/source/competitor; reason prose is display-only. It embeds its
  plot data as inline JSON; `assets/bench_page.js`, inlined beside it, draws one
  score-against-cost plot per panel with its own filters and the frontier of what is shown, and
  only lays out what Python decided. Each
  board shows what it measures, quoted from its source's methodology page with the URL beside it
  (`assets/boards.json`; a board with no entry says so and is never described from memory); an open
  table under the plots compares every board, and every evidence table sits collapsed below that.
  The wheel zooms a plot about the pointer, a drag pans once zoomed, and the reset button is always
  on screen. The page is where tiers are drawn (ticket 26): colour is the harness; three draggable
  horizontal tier lines per benchmark cut its score axis into bands and immediately assign carried
  lanes, preserving hand-set tiers until cleared; a click on a dot and a digit, or the boxes in the
  tier panel beside the plots, give a lane a tier; the panel counts lanes per harness per tier and
  lists them grouped as the wizard does; the panel, the counts and "Copy as lines" read
  `placeable(data.lanes)` — every lane a board draws, whether or not the catalog carries it, plus a
  carried lane with no rows, and never an `ultra` lane, which `parse_tier_lines` refuses (ticket
  35); an uncarried lane says "not carried" on its row, and a band still assigns only the carried
  lanes, so drawing a line never carries one; "Reset every tier" asks once and then clears
  everything the page holds for this catalog — every tier and off drawn, every manual mark and every
  board's tier lines — keeping only the tier view toggle (`page.resetAll`, ticket 36); "Price per
  model" below the plots is one row per model with the vendor's list price in and out on one shared
  log axis, efforts collapsed because every effort of a model is charged the same and an agy model's
  slugs joined through `harnesses.family` (`bench_page.price_rows`, `drawPrices`): an open dot for
  input, a filled one for output, colour the meter, the value beside each dot, a model with no
  published price saying so and drawing nothing, two efforts that disagree drawing the range, and
  the same figures in a table under it; a tier view puts the digit in each dot; the page's tiers
  live in the browser's `localStorage` under the catalog's key and are written nowhere else, and
  "Copy as lines" gives them as `lane tier` in the review page's order. Panel hover and selection
  reveal the exact lane dot and its label; dot selection marks its panel row. The plot fills the
  height beside its settings. Groups without Epoch figures use their best AA mean rank in the
  wizard. Every table lists a model's efforts most to least. The page is the first input (ticket
  27): each lane line offers `off` beside `4 3 2 1` (and `o` on a selected dot), off lanes have
  their own heading and count, and "Copy as lines" writes `<lane> <1-4|off>` for every decided lane;
  the review page's `v` reads those lines from `pbpaste` (only on `v`; a missing or failing
  `pbpaste` changes nothing), and `setup.py --tiers-from <file>` applies them at start, both through
  `tier_lines.parse_tier_lines` and one summary line
  (`tier_lines_summary`). A carried lane the lines do not name goes off, and the summary counts it
  (ticket 28); lines that name no lane in the catalog change nothing. Under `--plain` the lines'
  order inside a tier is the `order` written, and a prompt that moves a carried lane to another tier
  puts it at that tier's end and numbers the tiers it left and joined (the Draft). Colour is the
  meter: `bench_page.meter_shades` gives each meter its harness colour, and a second meter on one
  harness (`claude-fable`) a shade of it (`--h-<harness>-1`); the panel counts per meter. Under the
  plots a sensitivity table gives, per placed lane, the tier each board alone would give it at the
  page's tier proportions, with the composite shown and never counted; a lane another carried lane
  beats on score for no more cost on a board shown says "beaten by" in its tooltip and panel line.
  Both are display aids computed in the script (`sensitivity`, `beatenByLane`); the carry rule is
  unchanged. `--effort-rows` may be repeated to put several sources on one page.
  The page is one flat row of tabs (benchmark-views ticket 05): one tab per View from
  `assets/views.json` (Coding, Knowledge work, Automation, then Overall marked reference), then All
  boards (the free plots, the tier panel and the sensitivity table), Prices and Numbers. Python makes
  the data decisions: `load_views` and `view_boards` (each [source, benchmark] pair a View lists
  plots the newest version of its board), each Lane's `label` from `display_name` (the Model's name
  with its version, read from the id), each catalog row's `group` (its `model_identity`) and, for a
  model no Lane runs, a `ref` name from `reference_keys` so one model printed two ways is one
  Reference model. The script's `makeViews` draws each View as one zoomable plot per board (log
  cost against score; a box drag or Ctrl/Cmd-wheel zooms, markers shrink and effort labels appear
  as it zooms) with each Model on a Harness as one line through its efforts (`viewSeries`), the
  frontier as a soft band, and a range table under them. Clicking a Model or an effort shows only
  it; shift-click adds or removes. `viewTiers` ranks the held Lanes by their mean percentile across
  the View's boards and cuts that ranking with `cutRanked`, the cut `cutBoard` uses for the
  sensitivity table; `favouredEffort` is the lowest effort within five points of a Model's best.
  All of it is display: nothing a View shows is saved or written. Every string from a benchmark
  page is set as text, never markup. The page opens light; the theme toggle is kept in this
  browser (`delegate-bench-page:theme`), and `#theme=dark` overrides it. The tab is kept in the
  hash (`#tab=<id>`) and with the page's own state.
The tier pages propose a Tier for each carried Lane with a score (ticket 17,
`scripts/tier_proposal.py`): the rule is `routing.json`'s `tier_proposal` (source, benchmark,
thresholds for Tiers 2-4, diversity; the sample catalog's when a catalog has none,
`catalog.tier_proposal_settings`, validated by `validate_tier_proposal`, global only). The score is
the accepted row on that benchmark at the Lane's own effort; cost per task is the second axis. From
Tier 4 down, a Tier keeps its candidates on the score-and-cost frontier and, with diversity, each
harness's best candidate; the rest fall a Tier. A `proposed` column shows tier, score and cost, the
legend names the benchmark and its bands, and `p` takes every proposal into the page's marks and the
review order; nothing is written before the confirm page's `y`. Switching the benchmark is a
`routing.json` edit.

At start the wizard refreshes itself, so one command is one command (ticket 33).
`setup.scan` reads one Benchmark snapshot (`setup.read_benchmarks`) on a thread beside the harness
probes and returns `(discovered, discovery_data, snapshot)`; launch, the `r` rescan, the plain
report (`show_bench`), `collect_bench` and `propose_generation` read it. A live run reads both
sources through the cache (`web()`); `--fixture-dir` reads `aa-accepted.json` and `epoch.csv`
beside the harness fixtures; `--no-discover` reads only named files; `--epoch-csv` names Epoch's
file, else Epoch comes from where AA does. The fetched AA rows replace only the named AA rows, so
Terminal-Bench stays on the repo's rows. `r` renews AA and reads Epoch from the cache launch
wrote, and a renew that fails keeps the rows launch read. The start page's rows line is the
snapshot's `note`: both sources on one line, where each came from, then why either is not
fresh; its `errors` join the TUI's first message, and `--plain` prints them.
`discover.refresh_catalog` then proposes the
current generation in memory and `setup_tui.refresh_lines` states it on the start
page, one line per model. The save's Catalog commit gives every native lane in the
catalog its agent file, for every profile that declares native Lanes, in the profile's
template, and removes the file of each lane it took out (`catalog_commit`, deepening
D.7). It does so only when the catalog being written is the live `~/.config/delegate`,
so a catalog in a temp directory gets a note instead of a file. The agent files are
machine-local like the catalog, and a stow link left at a lane's path is replaced by a
plain file, never written through, so the write never lands in the repo. Prices are
never proposed.
A project file that names a lane the refresh removed warns on stderr and is ignored
(`catalog.warn_stale_lane`); the next project save drops it. A lane the wizard turned
off is the same case (`catalog.warn_off_lane`, ticket 36): on the read it warns and
takes no place in its Tier, and only a save refuses it —
`validate_project_routing(proposal=True)`, which the dashboard's save boundary passes.
A new lane starts carried, `ultra` apart, so every effort of every current model
reaches the screening page; `enabled` is the one field a successor does not inherit,
because a predecessor switched off at an effort judged that model, not this one
(ticket 35, changing ticket 33). `o` writes the page again before opening it, from the
Draft's `documents()["lanes"]` — the document the session started from, with the carry
and Tier decisions made so far — so a lane carried on the carry page reaches the page
(`Wizard.rewrite_bench_page`), with the snapshot's Epoch rows, the rescan's after `r`.
The page's catalog key is its lane names, which no
screen changes, so tiers already drawn in the browser survive the rewrite.
Focused setup uses `--screen carry|tier1|tier2|tier3|tier4|review|routing` on a TTY.
It starts from the catalog as read and proposes no generation (deepening D.6): it has
no start page to state a refresh. It restores current choices and shows only changed
fields before confirmation: `draft.changes()`. Its save commits only the documents
those changes touch (`setup_tui.changed_documents`) through the Catalog read taken at
launch, which holds no Model queue: untouched
records and documents keep their bytes, a shipped Class the routing lacks is shown
but never written unless a routing field changed, and a save with no change writes
nothing. On a first run, with no catalog yet, a focused save that writes one document
writes the other as the screen showed it, so the catalog is never half written. The
full `start` wizard and `--plain` commit both documents through the Catalog read taken
at launch (`catalog_commit`). On every screen a document changed since launch, by
`catalog set` or by the scan's Model swap, stops the save, which names it, writes
nothing and exits 1. `tier_lines` owns the bulk tier-line parser and summary, and
the Draft applies the lines; `setup_tui` keeps aliases. The routing screen exposes
metering with `[x]`/`[ ]`, space/x or +/-. Legacy absence stays absent on a no-op.
Focused Tier unmark moves down one Tier, or back to the lower Tier a Lane ticked there
started in, at its starting place; Tier 1 requires Carry to switch off.

- `scripts/discover.py`: what each present harness offers — models, their lane or `none`, their
  efforts, each from the adapter's `models()`. Efforts come from
  `codex debug models`, `claude --help`, the agy slug suffix (one model per slug family) and the
  grok adapter's `efforts`; a Haiku model gets none. A harness whose list is not everything it runs
  (Claude Code) reports `complete: false`, and no Lane of it is reported retired. It is the only thing that may say
  an effort exists. The effort words are `harnesses.EFFORTS`, one list every script derives from;
  a word a harness lists that no lane on it may carry goes in the model's `unknown_efforts`
  (`Harness.split_efforts`). It also owns generation (ticket 33): `model_level` splits a slug into
  its level and version (`gpt-6-sol` and `gpt-5.6-sol` are both `gpt-sol`; the agy effort suffix
  comes off first, and a trailing date stamp such as `-2026-11-01` is no part of the version);
  `mark_generation` marks a model superseded when the harness says so (codex's `upgrade`) or
  when the same level is listed at a higher version, and every model entry carries `level`,
  `version` and `superseded`; `lane_stem` names a new lane (`sol6`, `opus55`, `grok47`, and
  `grok47fast` for a level that extends a current level). `refresh_catalog(lanes_doc, discovery,
  published_models)` returns the refreshed document and the plan, in memory and writing nothing: a
  lane for every effort of every current-generation model of the harness's own vendor, a successor
  in its predecessor's place, superseded lanes gone, every new lane `UNPRICED`, and `ultra` off.
  A successor that takes no effort (Haiku) gets one lane at its predecessor's effort; models with
  a predecessor are placed first, so a new level copies figures from them whatever the listing
  order; an unknown effort word gets no lane and a line in the plan's `notices` instead.
  Claude Code lists no model, so `claude_generation` reads a newer version of a level the catalog
  already runs out of the benchmark rows' published names. `map_lanes` recomputes the drift notices
  against the refreshed catalog, so the start page never calls a lane-less model one the wizard is
  about to give six lanes.
- `scripts/effort.py`: `pack`/`extract`/`check` over a benchmark page, and `aa`, which reads
  Artificial Analysis rows straight out of the dataset every `/models/<slug>` page embeds, with no
  worker. `check` is the trust boundary: it rejects any number that is not on the page, and no
  worker or parser may originate a number or an identifier.
- The carry page's domination rule is `carry.dominating_effort`: another effort of the same model,
  for no more money (`carry.beats`, which the Tier proposal's cost frontier also uses), beats the
  lane on more than half of the benchmarks one source scored both on.
  Rows flagged `composite` (the AA Intelligence Index) are shown, never counted. "The same model"
  is the Lane's Model on its own Harness, at an effort that Harness runs:
  `carry.decisions(lanes_doc, evidence)` compares a Lane's own rows (`LaneEvidence.lane_rows`)
  with the rest of `LaneEvidence.model_rows`, which holds only efforts the Harness offers
  (`offers_effort`), so Claude Code's Opus at xhigh switches off no agy Opus Lane and an effort
  the grok CLI cannot run switches off no grok Lane. Its no-rows check reads `lane_rows`, and it
  compares no efforts to attribute a row itself. The harness decides what one Model is, never the
  spelling (ticket 30): agy names each effort as its own slug, and the adapter's `family`
  (`harnesses/agy.py`, reached through `harnesses.family`) is the one implementation, which
  `lane_evidence.model_identity` names a Model with (and `bench.group_lanes`, `bench_order_key`
  and `bench_page._lane_list` group the pages' Lanes by), and the agy adapter's `group` groups its
  model listing with.
- `scripts/browser_probes.py`: browser capability probe runner across harnesses (`--only`,
  `--probe`, `--dry-run`).
- `assets/preamble.md`: brief preamble prepended to worker prompts.
- `assets/probes/`: capability probe briefs for disposable browser (`disposable.md`) and agent
  profile (`agent-profile.md`).
- `assets/codex-home/config.toml`: the template for delegate's own `CODEX_HOME`. `make
  delegate-codex-home` expands `@HOME@`, writes it to `~/.local/share/delegate/codex-home/`, and
  symlinks `~/.codex/auth.json` beside it. It holds one MCP server and `approvals_reviewer =
  "auto_review"`, which is required: `codex exec` runs at `approval_policy = "never"`, which would
  otherwise auto-reject the approval an MCP tool call raises.
- `assets/schemas/return.json`: the child return contract, requested in every prompt and parsed out
  of the relay's final message.
- `tests/`: one test file per script, stdlib only, no network (`make test` points every proxy
  variable at a closed local port, so a test that reaches the web fails); `tests/fake-ads/relay.mjs`
  stands in for the relays (its brief directive also crashes it with `crash=`, or replays a staged
  run directory with `replay=`). Each script first moves to a fresh temporary directory with no Git
  root above it, so the invoking checkout's own `.delegate/routing.json` never reaches a test.
- `bin/delegate` at the repo root: the command the skill, council and the courier call (`delegate
  rank|run|dispatch|status|log|runs|cost|catalog|setup`). A user's harness constraint is `--harness
  <h>` on `rank` and `run`; it replaced the four `delegate-<harness>` wrapper skills.

## Read-only per harness

`--read-only` is not one thing. The pinned relays map it per harness: codex gets a real read-only
sandbox and its tools work; claude gets `--permission-mode plan` with its tools cut to
`Read,Glob,Grep` (`--tools`), so no shell and no web — `Read` ran with no permission denial in both
real read-only claude runs (2026-09-09), and `Glob` and `Grep` are not yet exercised; **grok is
fixed as of the fork pin** — read-only is now `--sandbox read-only --always-approve`, which is
kernel-enforced (Seatbelt/Landlock) and strictly stronger than the advisory plan mode it replaced.
**agy is fixed as of the fork pin** — read-only runs under Antigravity's filesystem sandbox with
tool auto-approval inside it (`--sandbox --dangerously-skip-permissions`), confining the run to its
workspace. `--write` is no longer the workaround it was before 2026-09-10; do not reach for it to
get agy's tools working. Note the ADS skill docs for agy still describe the old plan mode (ticket 14
follow-up); the relay code is what runs. If a gate cancels a tool anyway, settling (`relays.py`)
returns `blocked` with reason `permission gate cancelled the run at <tool>` rather than `partial`; the
reason is the harness adapter's `blocked_reason`, which only grok's implements (fixture
`tests/fixtures/dispatch/grok-gate-cancel/`).

## Codex inside another sandbox

macOS Seatbelt profiles do not nest: under an outer profile with any real rule, a second
`sandbox_apply` fails with `Operation not permitted` and `sandbox-exec` exits 71 (reproduced on
macOS 27 with codex 0.160.1, 2026-10-07). Codex sandboxes every command it runs with Seatbelt, so
a codex lane started from a Claude Code session whose Bash sandbox is on cannot run a single
command. `Codex.preflight` probes for this (`harnesses.base.seatbelt_blocked`) and dispatch
returns `blocked` with the reason before the relay runs or a Meter is spent. Run such a lane from
a shell outside the outer sandbox, such as a Herdr pane: Herdr's server starts the process, not
the sandboxed shell. Turning off Codex's own sandbox instead would leave a read-only lane
unenforced, so delegate does not do it.

## Browser use per harness

Browser use per harness, as proven on the Mac on 2026-09-12. **agy**: works, disposable browser,
nothing to do. **codex**: works, through a home of delegate's own — the `Ads` adapter sets
`CODEX_HOME` to `~/.local/share/delegate/codex-home` when it exists and then drops `--ignore-user-config`, so the
worker reads one MCP server and nothing else in `~/.codex`; without that home a run keeps the old
isolation and has no browser (`codex_home()`, ticket 03). **grok**: works on a write run only. Its
built-in `read-only` sandbox kills every stdio MCP server on macOS, `context7` as well as
Playwright. A custom profile granting `~/.npm` restores the servers, but Chrome then crashes,
because macOS's sandbox blocks its crash reporter and its own sandbox, and no path grant reaches
either. So a browser job on grok goes as a write run (the user's call, ticket 04, 2026-10-04).
**claude**: lanes are native since ticket 22, so the relay's MCP block is not on the path the user uses;
a native worker gets only the file, shell and web tools and the Playwright server (the agent
template's `tools` line), and the session must restart before it sees a new server (ticket 02). The rest is open work in `.scratch/delegate-browser/issues/`.

## Benchmark data

`agents/skills/delegate/scripts/effort.py` is a `pack`/`extract`/`check` pipeline;
`check` is the trust boundary and rejects any number not on the page. Artificial
Analysis skips the worker: `effort.py aa` reads the rows out of the dataset every
`/models/<slug>` page embeds and checks them against that payload (ticket 18). Approved
sources and their cautions: `agents/skills/delegate/assets/sources.json`; the
provenance research behind that choice:
`.scratch/delegate-redesign/research/2026-09-09-effort-data-sources.md`. Accepted
rows and their packets are kept as evidence in `.scratch/delegate-redesign/_data/`.

Coverage is uneven and the three sources are not interchangeable:
- swerb reaches only `gpt-5.6-sol` and `gpt-5.6-luna`, but publishes slugs.
- Artificial Analysis and Terminal-Bench are wider, but publish display names
  (ticket 16).

Cost is per task on swerb and on Artificial Analysis, but Terminal-Bench's
`display_cost` is a whole-run figure. Even the two per-task numbers measure different
task sets, so never compare costs across sources. AA's cost per task is the
Intelligence Index's, one figure per variant. AA does not measure Haiku at a Lane's
effort (`sources.json` says why). Nothing reads `~/.config/delegate/aa-key`. If the file
still exists it must never be stowed or committed, because this repo is public.
