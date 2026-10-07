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
use `rank.tier_leaders()`; it and the Class-facing `rank()` share `rank_range()`.
`usage.load_cached()` / `rank.load_cached_usage()` read observations without a vendor
probe or meter event. `usage.acquire()` is the refresh path. `usage.observations()`
owns cache validity (`rank.meter_observations()` re-exports it): valid envelope and
legacy map formats keep their behavior; any malformed observation makes the whole
document unknown. Envelope observations require a finite timestamp; raw Window/reset fields are
validated before display. `usage.eligible(observation, gate)` is the Gate predicate
(unknown Remaining never vetoes; Remaining equal to Gate is eligible). Every Meter
derives its combined figures through one arithmetic, `usage.combined()`: Remaining is
the lower Window fraction and Pace comes from the weekly Window. agy runs through it
like the Claude Meters, and its note says the combined figure is the lower Window, an
assumption, not a vendor bound (ticket 31, reversing modular ticket 13). A cache
written under that older rule holds the Windows beside a null Remaining and Pace, so a
read derives them (`usage._filled`) rather than probing again. This intentionally
replaces partial use of invalid documents.

## Scripts and assets

- `scripts/catalog.py`: the two configuration files (`~/.config/delegate/lanes.json`,
  `routing.json`, project overrides `.delegate/routing.json` and `.delegate/lanes.json`): load,
  validate and project the effective catalog, and nothing else (ticket 26). It imports no other
  delegate script but `harnesses` and `published_names`, so `rank` can import it with no cycle.
  The efforts a harness offers are its adapter's `efforts`, with the command or page that proved
  each list; `check` and `delegate.py --effort` refuse anything outside them (ticket 19).
- `scripts/catalog_edit.py`: revision-checked `set`/`range`/`order`. `edit_catalog()`
  previews cached Picks and resolved source paths, validates complete proposals, preserves stow
  symlinks, and rechecks source revisions before writing one document. `plan_edits()` is the one
  planning path (ticket 14). It takes the source documents already in hand and a list of the same
  `set`/`range`/`order` operations, plans each one onto the documents the one before it produced,
  and returns named fields: the four planned documents, the effective `catalog` they produce, and
  one `steps` entry per operation with its `dest` and `values`. It reads no Meter and writes
  nothing. `edit_catalog()` plans its one edit through it, and so does the dashboard's staged view,
  so there is no second planner to drift.
- `scripts/catalog_cli.py`: `delegate catalog` (`show`, `check`, `check-guide`, `fmt`, and the
  edits above). `scripts/class_guides.py`: the Class guide checks behind `check-guide`.
  `scripts/tier_lines.py`: bulk Tier lines for the wizard.
- `scripts/published_names.py`: the mapping from a benchmark source's printed model name to a
  lane model (`resolve_published_model`, the lane field `published_as`; a row's `effort` picks the
  member of an agy slug family); `bench.py`, `tier_proposal.py` and the setup pre-screen read it.
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
- `scripts/runs.py`: the run directory's one owner (ticket 24). A `Run` is created, finished or
  failed here, and only here are `dispatch.json` and `return.json` written; it spells and parses
  the finish and native lines. Run directories under `~/.cache/delegate/runs/`, never reused.
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
  A usage row is keyed by `meter`, the full Meter name (`usage.meter_name`), with `group` the
  probe's own word; a row cached before ticket 25 (`lane` the name, `meter` the group) is upgraded
  on read (`usage.row_meter`). Each adapter's `meter_names()`/`reports_meter()` say which Meters
  its probe reports, and `catalog check` refuses a Lane on any other (ticket 25).
  `scripts/events.py`: the ledger encoder (schema unchanged); the statusline reads the ledger.
- `scripts/model_queue.py`: models the catalog lacks, queued for the next `delegate global`
  (ticket 29). At most once a day, dispatch starts a detached scan that runs the wizard's own
  `discover` and `refresh_catalog` against the global lanes and queues each model no Lane runs.
  `dispatch --model` naming such a model queues it too. The queue is `new-models.json` beside the
  meter cache. The wizard's start facts name it ("Dispatch noticed") and its write empties it.
  `$DELEGATE_MODEL_SCAN=off` stops the scan. A newer version of a model the catalog already runs
  is not queued but applied (ticket 44 of the redesign): the scan swaps each Lane the refresh
  replaces with its successor into lanes.json, keeping Tier, Order and an off Lane off, after
  copying lanes.json to `lanes-backups/` beside the queue. The wizard names the swaps ("Dispatch
  swapped in"). `$DELEGATE_MODEL_APPLY=off` keeps the scan to queueing.
- `scripts/report.py`: limits, runs, and the lead's run ledger. `scripts/bench.py`: the human-only
  benchmark ranking under `~/.cache/delegate/bench/`; no routing code reads it. Artificial Analysis
  comes only from the rows `effort.py aa` accepted, passed as `--effort-rows` (no API, no key;
  ticket 19): the AA columns are the component benchmarks some lane has a figure for, with cost per
  task beside them and the composite never a column. `collect()` returns two views of the same
  figures: `models` (one figure per benchmark, for comparing against models nobody runs) and `lanes`
  (only the figures measured at that lane's own effort, with `mean`/`n` over those).
  `effort_attributes(measured, lane_effort)` is the whole attribution rule and the wizard and the
  page both read it from there. Display order lives beside `collect` (`group_lanes`,
  `lane_order`), and so does the carry wording (`carry_reason`); the carry policy itself is
  `scripts/carry.py` (ticket 27): `families()`, `beats()` and `decisions()`, which returns
  structured decisions `{lane, enabled, kind, source, competitor}`; renderers own the wording.
  `format_collection` turns a `collect()` result into the Markdown report. `bench.py model MODEL`
  reads accepted rows and optional local Epoch CSV without fetching. `evidence_records()` shares
  identity, board/version standing, cost basis and uncertainty with HTML. Family evidence stays
  separate from exact-effort Lane attribution; ambiguous candidates remain visible.
- `scripts/setup.py`, `scripts/setup_tui.py`: interactive catalog wizard (TUI on a TTY,
  prompt-driven under `--plain` or pipes). Each page makes one decision per line: with the same
  `[x]`/`[ ]` box, the carry page selects a model at an effort and the four tier pages assign a
  tier; the review page after tier 1 orders the carried lanes inside each tier (ticket 28). It lists
  them in sections tier 4 to 1, each numbered in its current order; j/k moves the cursor, J/K or
  shift-up/down moves the lane inside its tier, 1-4 moves it to the end of that tier, and the
  confirm write gives each carried lane `order`, its place from 1 (`catalog.py check` takes `order`
  as a whole number from 1). The starting order is the applied lines' order, then an `order` the
  catalog already has at that tier, then benchmark order. Tier pages restore the current catalog as
  their editable defaults: lanes at the current tier are marked, lanes at a lower tier are visible
  and unmarked, and lanes taken by a higher tier or not carried are hidden. Enter without edits
  preserves the current tiers and order; a lane not carried keeps its catalog tier. Lines applied by
  `v` or `--tiers-from` become the same editable defaults. The routing page explains the setting
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
  forcing the rows fetch past the 24 h cache), after which `Wizard._load` derives every later page
  again and the `--tiers-from` lines are applied again; it is offered on that page only, before any
  decision, and a failure is a message. It writes this machine's catalog, `~/.config/delegate`,
  which is never in the repo: each machine keeps its own (the user, 2026-09-29). `make delegate-wizard`
  at the repo root runs it with the accepted AA and Terminal-Bench rows (`DELEGATE_ROWS` in the
  Makefile; `WIZARD_ARGS` adds flags). `scripts/bench_page.py`: the HTML board the wizard's `o` key
  opens, which reads its attribution and its lane order (`bench.lane_order`, `group_lanes`) from
  `bench.py` and its domination rule (`carry.decisions`, `carry.dominating_row`) from `carry.py`
  rather than deciding any of them again. HTML
  carries kind/source/competitor; reason prose is display-only. It embeds its plot data as inline
  JSON; `assets/bench_page.js`, inlined beside it, draws one score-against-cost plot per panel with
  its own filters and the frontier of what is shown, and only lays out what Python decided. Each
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
  order inside a tier is the `order` written. Colour is the meter: `bench_page.meter_shades` gives
  each meter its harness colour, and a second meter on one harness (`claude-fable`) a shade of it
  (`--h-<harness>-1`); the panel counts per meter. Under the plots a sensitivity table gives, per
  placed lane, the tier each board alone would give it at the page's tier proportions, with the
  composite shown and never counted; a lane another carried lane beats on score for no more cost on
  a board shown says "beaten by" in its tooltip and panel line. Both are display aids computed in
  the script (`sensitivity`, `beatenByLane`); the carry rule is unchanged. `--effort-rows` may be
  repeated to put several sources on one page.
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
`setup.refresh_effort_rows` fetches the Artificial Analysis rows in process through
`effort.run_aa` into `~/.cache/delegate/bench/aa/`, reuses a fetch under 24 hours
old, and on a failure keeps the repo's rows with the reason in the line it returns;
the fetched file replaces the AA file in the `--effort-rows` list, Terminal-Bench
stays on the repo's rows, and `--fixture-dir` reads `aa-accepted.json` beside the
harness fixtures instead, so a test touches no network and no cache. The fetch runs
in a thread beside the harness probes. `discover.refresh_catalog` then proposes the
current generation in memory and `setup_tui.refresh_lines` states it on the start
page, one line per model. The save writes the agent file of each new native lane, for every profile
that
declares native Lanes, and removes each superseded one (`setup.save_native_agents`,
`setup.native_agent_text`, from the profile's template); `setup.native_agents_dir` returns the
profile's agents directory only
when the catalog being written is the live `~/.config/delegate`, so a catalog in a
temp directory gets a note instead of a file. The agent files are machine-local like
the catalog, and a stow link left at a lane's path is removed before the write, so the
write never lands in the repo. Prices are never proposed.
A project file that names a lane the refresh removed warns on stderr and is ignored
(`catalog.warn_stale_lane`); the next project save drops it. A lane the wizard turned
off is the same case (`catalog.warn_off_lane`, ticket 36): on the read it warns and
takes no place in its Tier, and only a save refuses it —
`validate_project_routing(proposal=True)`, which the dashboard's save boundary passes.
A new lane starts carried, `ultra` apart, so every effort of every current model
reaches the screening page; `enabled` is the one field a successor does not inherit,
because a predecessor switched off at an effort judged that model, not this one
(ticket 35, changing ticket 33). `o` writes the page again before opening it, from
`Wizard.current_lanes()` — the document the session started from, with the carry and
Tier decisions made so far — so a lane carried on the carry page reaches the page
(`Wizard.rewrite_bench_page`). The page's catalog key is its lane names, which no
screen changes, so tiers already drawn in the browser survive the rewrite.
Focused setup uses `--screen carry|tier1|tier2|tier3|tier4|review|routing` on a TTY.
It restores current choices and shows only changed fields before confirmation.
Untouched records and documents retain their bytes; changed sources use a revision
check and symlink-preserving writes. The full `start` wizard keeps its bulk save
behavior. Catalog owns the bulk tier-line parser/application/order helpers;
`setup_tui` keeps aliases. The routing screen exposes metering with `[x]`/`[ ]`,
space/x or +/-. Legacy absence stays absent on a no-op. Focused Tier unmark moves
down one Tier; Tier 1 requires Carry to switch off.

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
  Rows flagged `composite` (the AA Intelligence Index) are shown, never counted. "The same model" is
  a family key, not the model string (ticket 30): `carry.families(lanes_doc)` keys every
  harness but agy on the model itself, and an agy lane on its slug with the trailing effort removed,
  because agy names each effort as its own model. The harness decides, never the spelling. That
  family rule has one implementation, the adapter's `family` (`harnesses/agy.py`, reached through
  `harnesses.family`, and per Lane through `carry.model_of`, which also groups the pages' rows),
  which the agy adapter's `group` also groups its model listing with. `dominating_effort`,
  `dominating_row` and `first_domination` take the map; without one every model is its own family.
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
- `tests/`: one test file per script, stdlib only, no network; `tests/fake-ads/relay.mjs` stands in
  for the relays. Each script first moves to a fresh temporary directory with no Git root above it,
  so the invoking checkout's own `.delegate/routing.json` never reaches a test.
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
follow-up); the relay code is what runs. If a gate cancels a tool anyway, `map_result` returns
`blocked` with reason `permission gate cancelled the run at <tool>` rather than `partial`; the
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
nothing to do. **codex**: works, through a home of delegate's own — `run_relay` sets `CODEX_HOME` to
`~/.local/share/delegate/codex-home` when it exists and then drops `--ignore-user-config`, so the
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
