# Architecture review, 2026-10-06: deepening candidates

Read on 2026-10-06 from main at `5ebffdb` (after #28) with the `improve-codebase-architecture`
and `codebase-design` skills. Three readers walked the hot code in parallel: the catalog and
setup wizard, the job path, and benchmarks with reporting. The report the user read is the
artifact "Delegate Deepening Review". The user chose all eight candidates on 2026-10-11.

Vocabulary is the `codebase-design` skill's: module, interface, implementation, depth,
seam, adapter, leverage, locality. Domain terms are `CONTEXT.md`'s. Paths are under
`agents/skills/delegate/scripts/` unless stated. Line numbers are as of `5ebffdb`; main
has moved since (#29 plugin install, #30 codex Seatbelt block), so re-read before relying
on one.

Already done before this review, not re-proposed: the harness registry (`harnesses/`,
any-harness tickets 11 and 23), the split of `catalog.py` (ticket 26), classes as data
(ticket 16), one carry policy (ticket 27), runs.py owning the run directory (ticket 24).

## Seams found

- **The harness seam is real.** Five adapters. Outside `harnesses/` no caller branches on
  a harness name; only `effort.py:76 DEFAULT_HARNESS="agy"`. Adapters override hooks:
  `run_args` (codex, agy), `blocked_reason` and `limit_patterns` (grok), `prompt_note`
  (agy). One leak: adapters build Meter rows through a lazy `import usage`
  (`harnesses/base.py:335`), while `usage` imports `harnesses`, a cycle; the row shape is
  owned by one module and built in another.
- **The relay seam is hypothetical at code level.** One adapter: `node
  <ads>/skills/<relay>/scripts/relay.mjs`. `tests/fake-ads` stands in at the filesystem and
  PATH level, not behind a callable seam.

## A. Lane evidence: one module owns which benchmark rows belong to a Lane (Strong)

Files: `published_names.py:59-170`, `bench.py:139` (`model_matches_slug`), `:274`
(`match_epoch_rows`), `:342` (`effort_attributes`), `:473` (`aa_component_rows`),
`:1087-1213` (`_canonical_model`, `identity_of`, `inspect_targets`, `_ident_models`,
`_lanes_at`, `_attributed`), `:1252` (Epoch slug fallback), `:1397`
(`_record_matches_query`), `carry.py:43-85` (`families`, `family_of`, `model_of`), `:245`,
`bench_page.py:164-173, 233-287, 506, 965`, `tier_proposal.py:47-70`,
`setup_tui.py:376-377`, `catalog.py:213-225, 355-361`, `harnesses/claude.py:87`
(`PUBLISHED_NAME`).

Problem:
- Model identity is decided in about 7 modules and about 25 functions, with at least 4 rule
  variants: per-harness fan-out (`resolve_published_models`); a whole-catalog pool
  (`resolve_published_model`, still imported unused at `bench.py:38`); a slug strip that
  ignores the harness (`model_matches_slug`, contradicting carry's "the harness decides,
  never the spelling"); and harness family (`carry.families`).
- The candidate loop comparing a normalized name and its effort-stripped base is copied
  three times: `published_names.py:91-100`, `bench.py:1123-1133`, `bench.py:1170-1178`.
- One wizard session resolves the same rows against the same catalog about 7 times
  (`setup_tui:376-377`, `tier_proposal`, `bench.collect`, `bench_page.render` calls
  `_annotate` three times at `:575, 813, 839`, `carry.decisions` once more).
- History: ticket 31 (041a150) fixed the identity rule in `published_names`, `carry`,
  `tier_proposal` and `discover`; it missed `bench.identity_of`, `aa_component_rows` and
  `bench_page._annotate`, which ff4f83f (#28) fixed the next day.
- `carry.decisions` compares raw `row.effort == lane.effort` (`carry.py:245`) while
  `tier_proposal` uses `effort_attributes`.

Live bugs:
- **The benchmark page draws an agy Lane off that the wizard keeps (verified by
  running).** `bench_page._annotate:274-286` re-keys each row to the single grouping model
  (`_canonical_model`) before `carry.dominating_row`. With Opus on both claude and agy,
  `carry.decisions` gives `opus-high@agy: not_dominated` and `opus-high@claude: dominated
  by xhigh`; the page draws one point with both Lanes `lane_off`, `beatenBy=xhigh`, and agy
  offers no xhigh. This breaks carry.py's promise "the page never draws a verdict the
  wizard did not reach". `test_bench_page.py` has no fixture with one model on two
  harnesses.
- **`published_as` reaches only one harness (verified).** `published_names.py:126-128`
  returns only the one model a `published_as` entry names, and `catalog.py:355-361`
  refuses the same name on a second model. The ticket-31 bug class returns for any model
  that needs a `published_as`.
- **Epoch rows are matched two ways.** `collect()` matches them by `model_matches_slug`,
  which ignores `published_as`; `epoch_records` matches by display name with
  `published_as`. The scores table and `bench.py model` can disagree.
- `bench_page._proposals:185-188` swallows every exception, so a carry bug draws no
  verdicts. `bench_page._lane_at` (`:164`) is dead. `bench_page.js:316` cites
  `setup_tui._beats`, now `carry.beats`.

Solution: grow `published_names` into one Lane evidence module that takes the catalog plus
the effort and Epoch rows once and answers: rows for a Lane; rows for a Model on a
Harness; Published names no Lane runs; display records with unresolved reasons. It hides
normalization, `published_as`, harness family, effort suffixes, per-harness fan-out,
effort attribution and the grouping key. The carry rule stays in `carry`; the page asks
carry for each Lane's verdict and never re-derives it.

Dependency category: in-process. Deletion test: deleting `published_names` pushes its
complexity into 5 callers, so it earns its keep, but its interface leaks.

## B. Meters: one snapshot answers Remaining and Pace (Strong)

Files: `usage.py` (about 20 public names: `acquire`, `probe`, `load_cached`, `load_cache`,
`observations`, `_fill_document`, `_filled`, `_limited`, `_upgraded`, `row_meter`,
`mark_limited`, `clear_limited`, `eligible`, `combined`, `meter_row`, ...),
`rank.py:85-86, 489-518` (wrappers and a `meter_observations` alias), `report.py:163-168`
(`usage_doc`), `:186` (weekly dollars, a copy of `catalog.week_dollars:806`), `:695-697`,
`:824-829`, `:858-863`, `delegate.py:374-377, 549-558, 801` (probe before and after; the
`probed` flag), `tools/delegate-dashboard/model.py:201-209, 330-360, 512-513`,
`tools/delegate-dashboard/deck.py:466, 945` (Gate comparison, a copy of `usage.eligible`).

Problem: the answer to "what Remaining does a Meter have now" depends on which path a
caller takes.

Live bugs:
- **The usage-limit hold is skipped on one path (verified in-process).** The ticket 43
  hold is applied in `_fill_document`, but `observations()`, the validity boundary
  `rank_range` uses, never applies it. The dashboard reads the raw cache file and calls
  `rank.tier_leaders` on it, so `delegate project` ranks a held Meter at its probed
  Remaining while `delegate run` sees 0%. `observations(doc)` gives r=0.9,
  `observations(_fill_document(doc))` gives r=0.0.
- **`usage.py --pretty` crashes** with `KeyError: 'lane'` on every row (`usage.py:428`).
  Ticket 25 (5c6f50b) renamed the key to `meter`; that rename touched 13 files.
- **The statusline and the popup show different weekly figures for a Model meter (read
  from code, not run).** The statusline's weekly gauge shows the model's own weekly
  (`remaining_weekly_model`); the popup shows `remaining_weekly` (min of all-models and
  model) and computes Pace from it.
- `cache_path` is half-honoured: `load_cached(path)` calls `_fill_document(doc)` without
  the path, and `_write_limits` ignores it.
- Three freshness policies: `run` uses `acquire()` with a TTL (a reading up to 10 minutes
  old) and then `probed=True` skips dispatch's pre-probe; `dispatch` uses
  `acquire(refresh=True)`; `report` has its own rule. The caller must remember the
  `probed` ordering (the d560945 fix). The dashboard copies the cache-path env lookup.
- One Meter is projected for display in about 8 places: `report.py:695-697` (`shares5`,
  the weekly swapped for the model's own), `:824-829` (`shares5` again, `left` recomputed
  with `WEEK_DAYS*86400`), `:858-863` (Remaining and Pace recomputed in `handover`),
  `deck.py:466, 945`. `report.py:53-54` and `catalog.py:795-796` both define `WEEK_DAYS`
  and `DAYS_PER_MONTH`.

Solution: one Meters module whose small interface returns a snapshot under a named
freshness policy (cached, fresh enough, forced) that already honours `routing.meters`. The
snapshot answers Remaining, Pace, eligibility and a display readout per Meter (the weekly
shown, whether it shares a 5h Window, the share of the week left, gated, weekly dollars,
the readout under a hypothetical spend), and the module takes hold and release. It hides
the cache file, TTL and timeout, legacy row upgrade, combined Window arithmetic, the
limits overlay, meter events and path resolution. `rank_range` takes a snapshot, never a
raw document. The `probed` flag goes away, because a snapshot knows its age.

Dependency category: ports and adapters (five harness probe adapters plus a fixture
document, `--meters`); storage local-substitutable. ADR 0001: routing reads the Meters as
they are when a job is sent; no history, no burn rate.

Before: about 26 call sites (report 9, rank 7, delegate 4, catalog_edit 3, dashboard 2,
evals 1), plus 12 adapter calls to `meter_row`; the row dict has 17 string keys.

## C. Run lifecycle: a started Run always finishes (Strong)

Files: `delegate.py:359-371` (`ledger_start`), `:589-647` (`note_usage_limit`,
`start_failure`, `fail_run`, `ledger_finish`, `print_and_exit`), `:650-763` (`dispatch`),
`runs.py:69-164`, `events.py`, `report.py:632-662` (the statusline's own ledger parser),
`usage.py:167-191`.

Problem: the Run has two records with two owners, the run directory (`runs.py`) and the
ledger (`events.py`). Only the statement order inside `dispatch()` keeps them consistent:
create, native exit, ledger start, try relay and map (which calls `Run.finish`) / except
`fail_run`, `note_usage_limit`, ledger finish, print and `sys.exit`. Every bug fix in the
history landed in that order, not in a module: 7f7d020 (a start with no finish left a
phantom running glyph), 4ec88b5 (`fail_run` raised, skipping the ledger finish), 905a0ab
(`note_usage_limit` wedged between fail and finish), d560945 (the `probed` flag threaded
run, dispatch, `relay_and_map`).
- `report.py:632` re-derives the ledger path that `events.ledger_path()` owns and
  hard-codes `"dispatch.start"`, `"dispatch.finish"`, `timeout_s` and `ts`.
- A native Run gets a `dispatch.json` whose outcome stays null forever, and no ledger
  events.
- Tests reach the invariant only through `main()`. Cases 12e, 12f and 34c monkeypatch
  `delegate.run_relay` and `usage.acquire` inside `python -c` strings, because
  `delegate.py` has 25 `sys.exit` calls. Test 36 calls `note_usage_limit` directly, so
  nothing tests that dispatch calls it.
- `events.py` is shallow: 3 dict builders and `append`; its CLI has no caller except
  `test_events.py` (241 lines testing a 109-line encoder). `ledger_start` and
  `ledger_finish` are pass-throughs. Since ec09a9a nothing reads `kind:"meter"` events.

Solution: one Run module owns start, finish, fail and "handed to a native agent" as
terminal states. It writes `return.json`, `dispatch.json` and the ledger event together,
never raises past the ledger finish, settles the Meter hold on finish, and offers the read
side: which Runs are running now, and the summary or finish line. Callers say "start this
request" and "finish with this outcome".

Dependency category: local-substitutable (run root and ledger are env-overridable files).

## D. Catalog commit: one save owns its guarantees (Strong)

Files: `setup.py:580-600` (`confirm_and_write`), `:603-618` (`write_focused`), `:755-777`
(full TUI save), `:443-533` (native agents), `:569` (`clear_queue`),
`model_queue.py:112, 194-209` (`_write_applied`), `catalog_edit.py:176, 869-877`,
`catalog.py:86` (`write_json`).

Problem: five write paths each make their own guarantees.

| Path | validate | changed since read? | symlink | agent files from | queue |
|---|---|---|---|---|---|
| wizard, full save | yes | none | replaces link | `wizard.refresh` | clears all |
| wizard, plain | yes | none | replaces link | launch plan | clears all |
| wizard, focused screen | yes | revision | writes through | none | untouched |
| dispatch model swap | lanes only | raw bytes + backup | writes through | made-up plan `{"new","removed"}` (`model_queue.py:207`) | n/a |
| `catalog_edit` (`catalog set`) | yes | revision | writes through | none | n/a |

- Past bug 70c9a8b: the save wrote agent files from launch's plan instead of the rescan's;
  the plan was held in two places.
- Seam leak 86ac8e5: the detached dispatch scan imports `setup`, which pulls in
  `setup_tui`, `bench`, `bench_page` and `effort`, and imports the private
  `catalog_edit._write_preserving_link`.
- **Latent race (read from code, not reproduced).** The full wizard save
  (`setup.py:766-777`) checks nothing. A dispatch-time model swap written while a wizard is
  open is reverted silently; `clear()` then wipes `applied`, the swap's only record. Agent
  files fall out of step: the new Lane's file is orphaned and the old Lane's deleted file
  is not recreated. A `catalog set` made during a wizard session is lost the same way.
- Hard to test: the only full-save test (`tests/test_setup.py:755`) monkeypatches
  `setup.scan`, `setup_tui.run_curses`, `setup.native_targets`, `catalog.CONFIG_DIR` and
  stdin/stdout.
- `save_all_native_agents`, `native_targets` and `clear_queue` are 3 to 5 line
  pass-throughs.

Solution: one module takes "the documents as read" and "the documents to write" and hides
validation, the changed-since-read check, one symlink rule, backup, the agent-file sync
worked out from the before/after Lanes (not a threaded plan), and clearing only the queue
entries this session saw.

Open choice: the agent writer replaces links (so nothing lands in a repo, per ADR 0001's
machine-local rule) while three catalog paths write through them. One module needs one
rule.

Dependency category: local-substitutable (config dir, agents dir and queue path are
injectable).

## E. Routing preview: rank explains its own Pick (Worth exploring)

Files: `rank.py:98-147` (`score`, `eligible_order`, `steals`, `choose`, made public by
b1ae58a for the popup), `rank.py:399`, `report.py:839-883` (`handover`, `pace_to_lead`),
`report.py:930`, `tools/delegate-dashboard/deck.py:421-441` (`reason_code` parses prose),
`:914-937` (`steal_thresholds = pace + margin`; its docstring cites "rank.py lines
177-183", stale), `:945`.

Problem: `report.py` replays `rank.choose`, but the what-if lives in two presentation
modules, and the dashboard copy has drifted. Ticket 39 (899ffdd) changed the steal to
`score >= p*(1+margin)` under `plan_dollars` and wrote the reason "stolen by plan
dollars..."; it touched `rank.py` and `test_report`, not `deck.py`. **Verified with the
sample catalog and `quota_unit=plan_dollars`:** the Pick `fable-xhigh@claude` ("stolen by
plan dollars: 23.00 >= 5.52 x (1 + 0.2)") maps to deck code ELIG, not STEAL, and
`deck.steal_thresholds` still computes Pace + Margin. Rank's interface now carries an
invariant written for the popup (`score`'s docstring: "a caller that changes `pace` on a
row... gets the value rescaled").

`plan_dollars` is opt-in; on 2026-10-04 the user kept `quota_unit` at `pace` (redesign
ticket 39). The feature stays; the deepening makes every surface follow whichever unit is
set.

Solution: rank's tier preview returns machine-readable facts: each row's cause (pick,
steal, eligible, unknown, or a veto kind), the per-tier threshold in the active quota unit,
pace needed to lead, and the handover distance. The popup and the deck only render these.
`choose` and `steals` go back inside rank.

Dependency category: in-process.

## F. Catalog draft: one answer to "what will save write" (Worth exploring)

Files: `setup_tui.py:354-404, 488-556, 606-740, 949-1011, 1566`, `tier_lines.py:80-114`,
`setup.py:253` (`ask_lanes`), `:701-713`, `catalog_edit.py:309-346`.

Problem:
- `Wizard` keeps decisions in five parallel structures (`_enabled`, `_assigned`, `_marks`,
  `_tier_order`, `_line_order`) next to `_original_lanes`, and takes 18 constructor
  parameters.
- "The catalog after save" is built in six places: `current_lanes` (no order), the
  `handle("y")` block (`:962`, with order), `_focused_lanes` (`:985`), `_meter_coverage`,
  `_final_tier`, and the confirm page view (`:1566`), which shows tier only, not the order
  `y` writes.
- The marks rebuild is copied three times (`:397, 689, 731`). Cursor bounds in `handle`
  repeat the view's row counts (`:910, 949`).
- The plain path re-implements tier lines on the documents
  (`tier_lines.apply_tier_lines_to_doc`, `write_order_from_lines`).
- Unordered Lanes break ties three ways: `catalog_edit._carried_in_tier` by name,
  `Wizard._start_key`/`_focused_lanes` by benchmark order, `write_order_from_lines` by line
  order.
- Tests read private state 24 times (`tests/test_setup_tui.py:603-2944`).

Solution: an in-process draft holds the catalog as read plus the decisions (carry, tier,
order). It applies lines and proposals, moves Lanes, and answers "Lanes to write",
"changes" and "Carried lanes in tier N". The TUI keeps the keymap and layout; `--plain`
uses the same draft. The draft's documents to write are what candidate D's commit takes.

ADR 0001: TUI work goes to a Claude Opus agent under `/frontend-design`, and pages keep one
decision per line.

## G. Relay seam with an in-process fake (Worth exploring)

Files: `delegate.py:249-260` (`sh ads.sh check` subprocess; repeats the ADS_DIR default
from `ads.sh:20`), `:380-407` (`run_relay` argv), `:410-546` (`map_result` reads 10
`result.json` keys and calls `Run.finish`, so it is not pure), `:76-117`,
`harnesses/grok.py:97-124` (parses `events.jsonl`), `report.py:256-279` (relay usage token
keys), `evals.py:73` (`RUN_FILES`), `tests/fake-ads/relay.mjs`.

Problem: knowledge of the relay's output format is spread across 5 modules. Tests
substitute the relay by rebuilding a whole environment, and that world-builder exists
twice: `tests/test_dispatch.py:64-140` and `evals.py:148-190` (a fake ADS tree per relay, a
fake `git` answering the pin from `ads.sh`, CLI stubs, node/sh/python3 symlinks, 7
environment variables). Failure modes (node missing, `return.json` unwritable) are tested
by monkeypatching `run_relay` in subprocesses.

Solution: a Relay seam with two operations: check that it is ready, and run one job into a
run directory, returning a typed outcome (status, final message, session, usage, touched
files, read-only violation, stopped-short reason, exit, secs). The ADS adapter hides node,
the pin, the argv, `result.json`, and `events.jsonl` via the harness hooks. A fake adapter
returns scripted outcomes. Mapping becomes pure normalization from outcome to the return
contract. The env-level fake still serves the offline eval, which deliberately runs end to
end.

Dependency category: ports and adapters (an external process and a third-party package).

## H. Benchmark snapshot behind one fetch port (Worth exploring)

Files: `bench.py:216, 258-270` (`load_epoch` fetches with urllib directly, no cache, no
injectable fetch), `bench.py:456` and `setup.py:536` (two `load_effort_rows`, one raises,
one returns `(rows, message)`), `setup.py:295-361` (AA's 24-hour cache, `fixture_dir`,
`fallback`, `_with_aa_rows`, which finds the AA file by scanning content for `source ==
aa`), `effort.py:1351-1385` (`fetch_page`, `run_aa`), `bench.py:1379` (`epoch_records`
never fetches).

Problem: `make delegate-wizard` passes no `--epoch-csv`, so every launch, and every `r`
rescan through `collect_bench`, fetches the Epoch CSV live on the main thread. AA is
fetched on a thread with a 24-hour cache. The page's evidence records never see Epoch rows
(they need a local path), while the scores table does. Acquisition policy is split across
effort, setup and bench.

Solution: one snapshot module returns the effort rows plus the Epoch rows, with
provenance notes and age, one cache directory policy and one fetch port. The live,
fixture and local-file adapters already exist, so the seam is real. Effort stays the AA
extractor behind the port. Benchmark data stays out of routing.

## Smaller findings, not carded

- `delegate.resolve()` exits 14 ways, returns a 9-key dict, and duplicates rank's request
  checks (`delegate.py:767-806` against `rank.py:551-570`); `run` loads the catalog and
  profile twice. Speculative; overlaps C.
- The wizard and dispatch each run their own generation scan with a 7-key plan dict
  (`setup.py:364-417`, `model_queue.py:212-237`); `propose_generation` mutates it with
  queue facts. Mostly absorbed by D.
