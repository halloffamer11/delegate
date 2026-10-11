# Delegate deepening: eight deep modules

Designed on 2026-10-11 against main at `67b1c33` (after #30), with this effort's research
note on top (`b268352`). The 2026-10-06 review
(`.scratch/delegate-deepening/research/2026-10-06-architecture-review.md`) carded eight
deepening candidates, A to H, and the user chose all eight on 2026-10-11. Each candidate
was designed on its own, then all eight were cross-checked against each other; the
sections below are the designs with that cross-check applied.

Paths are under `agents/skills/delegate/scripts/` unless stated otherwise, and line
numbers are as of `b268352`. Vocabulary is the `codebase-design` skill's (module,
interface, depth, seam, adapter, leverage, locality) and `CONTEXT.md`'s, which gained this
effort's terms with this spec. Ticket labels A1 to H3 name each candidate's tickets in
build order; the Build plan maps them to the numbered files in `issues/`.

## Decisions taken

Each design left open choices. Every one was taken on the option its design recommended,
so the work could proceed. The user can reverse any of them; a reversal changes the
candidate's section and the tickets it names. Decisions that would add a line to ADR 0001
or start a new ADR wait for the user's word before any ADR file changes (see ADR edits
under Build plan).

### A. Lane evidence

1. **How the benchmark page draws a point that Lanes on two Harnesses share when carry
   gives them different verdicts.** Chosen: strike the point only when every Lane on it
   is proposed off. Otherwise draw it as a kept Lane, and name each proposed-off Lane with
   its own reason in the tooltip, the tables and the board's finding. Why: `carry.py`
   promises that the page never draws a verdict the wizard did not reach, and striking the
   shared Opus point at high draws agy's kept Lane off (verified by running). The page
   already uses the same every-Lane rule for its own page-set offs (`pointOff` in
   `bench_page.js`).
2. **Whether the page keeps "X beats it on most of this source" for points no Lane runs
   and for Lanes carry did not propose off.** Chosen: no. "Beaten by" shows only on a
   proposed-off Lane's point, and only on boards from the source carry decided on. Why:
   ADR 0001 makes the carry rule the only thing that proposes a Lane off and calls the
   page's frontier a display aid. `carry.dominating_row` was public only so the page could
   apply the rule again, and for a row that two Harnesses share the rule gives two
   answers. The sweep table's delta-score and delta-cost columns still show whether a
   dearer effort buys anything.
3. **Whether a Lane is dominated only by efforts its own Harness runs.** Chosen: yes, on
   every Harness, including an agy family with one member and grok's high-only Lane. Why:
   ticket 31 settled that "a lane is off only when another effort its own harness runs
   beats it" (the `carry.families` docstring), but today the rule holds only when agy
   carries two or more efforts of a family: with only `claude-opus-5-5-high` on agy, the
   agy Lane is proposed off by xhigh (verified). The real AA rows publish Grok 4.6 at low,
   medium and xhigh, which the grok CLI cannot run. This reading of ADR 0001's carry rule
   is a candidate line for ADR 0001.
4. **Whether a row with no stated effort that names an agy family is unresolved or
   belongs to the Model.** Chosen: it names the Model, and no Lane claims it. Why:
   identity is the Model, not the member slug. `collect` already shows such figures as
   the Model's context ("at an unstated effort"), and attribution still needs an effort,
   so ticket 19's guard holds: no Lane takes an effortless row.
5. **What name the page and inspection show for an agy-only Model.** Chosen: the harness
   family base (`gemini-3.8-flash`). A Model that some Lane runs under its whole name
   keeps that name (`claude-opus-5-5`). Why: grouping by member slug splits one Model's
   efforts into separate sweeps, so the finding for a dominated agy effort loses its
   arithmetic (verified). Discovery already reports agy models under the family base.

### B. Meters

1. **Which weekly figure a Model meter shows.** Chosen: the lower of the model's own week
   and the harness's week for all models, which is the probe row's `remaining_weekly`,
   defined as the Weekly figure. Why: CONTEXT's Remaining is the lower of a Meter's Window
   fractions, and a Model meter shares its harness's Windows. The probe already treats the
   all-models week as binding the model (`harnesses/claude.py`: `wk = min(fw, fm)`). Pace,
   the Gate and the ✗ printed beside the weekly cell are all computed from this figure,
   and so are the popup's "= W ÷ L" and the `delegate status` table. The statusline is
   the one outlier, and it already falls back to this figure when the probe row lacks the
   model's own week (test_report: the renamed-meter case prints 46%), so today the
   statusline cell changes meaning from one row to the next. The model's own week stays
   in `delegate status --json` and in the Meter's note. This reverses one acceptance box
   of redesign ticket 23 ("The fable row shows remaining_weekly_model"), so it is a
   candidate line for ADR 0001.
2. **Whether a named dispatch still forces a probe before its relay.** Chosen: it reads
   FRESH, probing only when the reading is older than ten minutes, and reads FORCED after
   the relay. Why: nothing consumes the pre-relay reading. A named dispatch skips the
   Gate, and meter events have had no reader since ec09a9a. The claude probe spends the
   quota it measures. Giving dispatch the same rule as `run` is what lets both share one
   probe without the `probed` flag; the snapshot knows its own age.
3. **Whether the module lives in a new `meters.py` or stays in `usage.py`.** Chosen:
   `usage.py`. Why: `delegate status --json` runs `usage.py`, and every machine's catalog
   names it in each Meter's `probe` field. `meters` is also the parameter name in
   `rank_range`, `catalog_edit` and `evals`, so a module of that name would be shadowed
   inside them.
4. **Whether `usage.py --pretty` is fixed or deleted (nothing calls it).** Chosen: fixed,
   rendered from Readouts. Why: it is the documented CLI flag in the module's usage text,
   and it is the only view that prints Pace, the binding Window and the probe note for
   each Meter. The fix is one function over Readout, and a test pins it.
5. **One probe bound for every read, or rank's 90 s beside dispatch's and report's
   180 s.** Chosen: one 180 s bound. Why: the child runs every harness probe in turn:
   claude alone allows 60 s and agy 90 s. A 90 s bound can cut a healthy probe short, and
   rank then falls back to a stale or empty reading, which the Gate never vetoes.

### C. Run lifecycle

1. **Which word a native Run records as its status in `dispatch.json` and the Ledger.**
   Chosen: `native`. Why: three places already use it: the native line
   (`delegate: native lane=...`), the `--json` object (`"native": true`) and CONTEXT's
   Native lane, so one word names it everywhere. Only one reader of the field changes:
   `report.py log --run`. It now logs `native` where it logged an invented `done`, and it
   still asks for `--secs`.
2. **Whether the Ledger keeps the meter events `usage.py` appends on every probe.**
   Chosen: drop them; the Ledger records Runs only. Why: their only reader was the
   delegate-mon monitor, removed in ec09a9a (2026-10-04). ADR 0001 rules out usage
   history in routing, and the usage cache already holds the latest reading. Dropping
   them also removes `usage.py`'s import of `events.py`, and with it the import cycle that
   would form once the Run module settles Meter holds through `usage.py`. B builds on this
   (its probes write no event), and it is a candidate line for ADR 0001.
3. **Whether a Ledger that cannot be written stops a Run.** Chosen: no. The Run runs and
   ends, and a note on stderr says which Ledger line was lost. Why: orchestrators read
   `dispatch.json`, `return.json` and the finish line. The Ledger feeds only the
   statusline glyph, and `running()` cross-checks `dispatch.json`, so a lost finish line
   cannot leave a phantom glyph.
4. **Where `running()` learns which Runs are running.** Chosen: the Ledger,
   cross-checked against each candidate Run's `dispatch.json`. Why: the Ledger is one file
   for every runs root. Tests, evals and `--runs-dir` each use their own root, and the
   statusline takes none. A directory scan would grow with every Run ever made and would
   read up to one file per Run on each 30-second refresh.
5. **What a Run does when its process gets SIGTERM.** Chosen: it ends blocked as
   "dispatch terminated (SIGTERM)", stops the relay, and exits 1, as every blocked Run
   does. Why: the claude profile's launch note records that `claude -p` SIGTERMs a
   background job at the end of its turn. Today such a Run keeps its glyph up to the
   Lane's timeout, its relay keeps spending the Meter, and its `dispatch.json` stays null.
6. **What secs a native Run records.** Chosen: null. Why: delegate never sees how long
   the agent ran. Leaving secs null keeps `delegate log --run` asking for `--secs`, which
   is what SKILL.md step 4 tells the orchestrator to pass for a native Lane.

### D. Catalog commit

1. **Which link rule applies to catalog documents.** Chosen: catalog documents are
   written through a link to an existing file, and the link stays. A dangling link or a
   loop is refused at read and at commit, so its target is never created.
   `catalog.write_json` carries the rule, so `catalog fmt` follows it too. Why: since
   36f09b1 (2026-09-29, ADR 0001's machine-local ruling), nothing installs a link in
   `~/.config/delegate`: `stow/delegate` was removed, and delegate's Makefile links
   nothing there. A link there is the user's own placement of a machine-local file.
   Redesign ticket 22 recorded link replacement as a bug and named realpath-before-write
   as the fix. The focused screen and `catalog set` already write through, and
   `catalog.md` says "Apply preserves stow links". Verified: today's write-through follows
   a dangling `.delegate/routing.json` link and creates a file outside the project, so the
   dangling case must be refused. This is the proposed ADR 0002.
2. **Whether the Agent-file rule differs from the catalog rule.** Chosen: yes. A link at
   a Lane's agent path is always replaced with a plain file and never written through, and
   the link's target is left untouched. Why: `~/.claude/agents` is an install target that
   holds links into repositories: the dotfiles repo stows its agents package there per
   file, and delegate's `make install` links the courier there. A link at a Lane's path is
   therefore a repository's file. Writing through it would put a machine-local Lane agent
   into a public repository, which 36f09b1 added the replacement to prevent.
   `case_the_real_layout_saves_the_agent_files` pins this. It belongs in ADR 0002 with
   decision D.1.
3. **What a wizard save does when the catalog changed since launch.** Chosen: it writes
   nothing, names the changed document, and exits 1. There is no merge and no automatic
   retry. Why: the race is rare: the scan runs at most once a day, and `catalog set` is
   explicit. Rebasing the session onto the newer catalog would place Lanes the human never
   screened, and ADR 0001 says Tiers are what the user sets. Printing `--tiers-from` lines
   to recover the session would turn off a swapped-in Lane, because `--tiers-from` turns
   off any carried Lane no line names.
4. **Which Model queue entries a save forgets.** Chosen: the full wizard (TUI and
   `--plain`) reads the queue with the catalog and names it on the start page whether or
   not the refresh ran. Its commit forgets exactly those entries. Focused screens, the
   scan and `catalog set` read no queue and forget nothing. Why: this makes "saw" mean
   "was shown", with no plan threaded through setup. The refresh proposes again every
   model its harness lists, so forgetting a shown entry loses nothing. It replaces redesign
   ticket 29's "a run whose refresh did not run keeps the queue", which tied forgetting to
   the refresh plan and caused bug 2: an entry noted during the session was removed
   unseen. Record the change in ticket 29, not in an ADR.
5. **Which writes are backed up, where, and how many are kept.** Chosen: every commit
   that replaces a global document copies its read bytes to
   `<config dir>/backups/<name>-<UTC stamp>.json`, and the newest 20 per document are
   kept. Project documents are not backed up. Why: the review puts backup inside the one
   save, and today the full wizard save rewrites the whole catalog with no undo. Backups
   beside the catalog keep tests and throwaway catalogs self-contained with no environment
   setup, and keep the live catalog's backups machine-local (ADR 0001). The scan's old
   folder beside the queue is retired.
6. **Whether a focused screen applies the generation refresh.** Chosen: no. A focused
   screen proposes no generation; it starts from the catalog as read and saves only its
   own change. Why: verified: one toggle on `--screen tier3` wrote 20 added and 17 removed
   Lanes the screen never showed. `Wizard._load` says a focused screen "never applies
   carry proposals the operator has not seen", and `catalog.md` says its confirm lists
   only the changes made. F's decision F.4 is the same choice; D3 owns the change.
7. **Whether Agent files cover every native Lane in the catalog or only the Lanes a save
   added.** Chosen: every native Lane in the catalog after a commit that writes the
   global lanes document has its Agent file, so a missing one is written; every native
   Lane the commit removed loses its file. Why: this is derived from the documents, not
   from a plan, and it fixes the race in which the old Lane's deleted file is not
   recreated. Dispatch needs the file to spawn a native Lane, so a native Lane without one
   is broken.
8. **What shape the interface takes.** Chosen: `read()` then `commit(read, documents)`,
   not `update(config_dir, change)` with retries and not a stateful session object. Why:
   every caller needs a read that outlives a call: the wizard's session, `catalog set`'s
   `--expect` across two processes, and the dashboard's staging. `update()` cannot replay
   a human session onto a newer catalog without placing unscreened Lanes.

### E. Routing preview

1. **Whether `cause` replaces `veto` in `delegate rank --json` rows or sits beside it.**
   Chosen: replace it (E3). Why: two fields that must agree are the drift this candidate
   removes. A grep shows that only `report.tier_block`, `rank.gate_only_stop` and tests
   read `veto`. `references/routing.md` documents `eligible`, `weight` and `overflow`,
   never `veto`, and no skill or orchestrator profile reads it.
2. **What the popup says when a rival's Pace to lead lies past its axis.** Chosen: show
   the real Pace to lead, with the dot clamped at the axis edge. Say "cannot lead on Pace"
   only when no Pace a Meter can read (`usage.MAX_PACE`, 1 ÷ cycle floor = 50) makes it
   lead. Why: verified on the sample catalog with plan dollars and sol in Tier 4: the axis
   top is 4.0 and the popup says "cannot lead on Pace", yet codex leads at Pace 4.26,
   which a Meter can read. The axis top is a drawing limit, not a routing fact.
3. **Whether, with `routing.meters` off, the deck still marks a Lane with no Meter
   reading NOMTR ("ranking sorts it last").** Chosen: no. Follow rank's cause, which is
   `eligible` (ELIG) when Meters are off. Why: under "Metering off", `references/routing.md`
   says that with Meters off ranking uses tier, order and lane name, so an unread Lane is
   not sorted last. The deck's remaining-is-None test was what caused the NOMTR-over-CLI
   bug.
4. **Where the Steal threshold is shown, given that it is in plan dollars under
   `plan_dollars` while the popup and deck axes are in Pace.** Chosen: in
   `rank tiers --json` and in the deck aid's rule sentence for the active unit. The
   popup's ┊ mark and the deck's Pace-bar mark draw the Pace to lead. Why: the Pace to
   lead is on the Pace axis in both units, and the popup's legend already defines ┊ as
   "the Pace that Meter needs to lead the Tier". A plan-dollar value drawn on a Pace axis
   is the unit error the deck has today.

### F. Catalog draft

1. **Which tie-break numbers Lanes that have no Order.** Chosen: lane name, applied by
   `catalog.carried_in_tier` and used by the draft, `catalog set` and `catalog order`, and
   Project order. Why: it is the only rule every path can compute without data.
   `catalog set`, the dispatch Model swap and routing's Project order projection have no
   benchmark rows, and benchmark data stays out of routing. Rank already tries unordered
   Lanes by name when Meters are off, and ADR 0001 names lane name as the deterministic
   tie-break. Benchmark order also moves whenever rows are refetched. The benchmark-order
   start was an implementation choice recorded in ticket 28's "What shipped", not a box
   the user ticked. The user's own answer to ordering inside a Tier is ticket 17's
   proposal, taken with `p` (ticket 37, 2026-10-04). Decisions F.1 to F.3 together are the
   proposed ADR 0003, "One rule places a Lane inside its Tier".
2. **Where a Lane goes when it joins a Tier it did not start in.** Chosen: to the end of
   that Tier; a Lane returning to its start Tier takes back its starting place. Why: the
   review page's 1-4 key, the focused tier unmark (test 61) and `catalog set`'s
   `_append_order_in_tier` already put such a Lane at the end. Exact undo is required by
   test 75, where switching a Lane off and on with `x x` leaves `r` as a rescan, and by
   focused no-ops (test 59).
3. **Whether save numbers every carried Lane or only the Tiers that changed.** Chosen:
   `whole=True` for the full wizard numbers every carried Lane; `whole=False` for focused
   screens and `--plain` writes only changed fields, and numbers a Tier only when its
   sequence changed. Why: this keeps ticket 28's contract that the review page's numbers
   are what is written and what ranking reads. It also keeps the focused screens' "Only
   the listed changes will be written" (tests 59 and 61, `references/architecture.md`)
   and `--plain`'s byte-identical sample (`case_all_harnesses_write_canonical_samples`).
   The `--plain` stale Order gets fixed as a side effect.
4. **Whether a focused screen applies the in-memory generation refresh.** Chosen: no. A
   focused screen starts from the catalog as read and applies no refresh. Why:
   `setup_tui` says a focused screen "starts from the catalog as it stands and never
   applies carry proposals the operator has not seen". `architecture.md` says focused
   setup "restores current choices and shows only changed fields". A focused screen has no
   start page that states the refresh. Its save writes no agent files and leaves the
   queue, so a refresh written there orphans native agent files (verified on the
   refresh-2026-09-22 fixtures). This is decision D.6; D3 makes the change.
5. **Which Tier an off Lane keeps.** Chosen: switching a Lane off returns it to its start
   Tier; only a `--plain` prompt can set an off Lane's Tier. Why: this keeps both of
   today's behaviours: the TUI's `_final_tier` ("a lane not carried keeps its catalog
   tier", as the review legend says) and `--plain`, which writes the tier typed for an off
   Lane. It also keeps undo exact.
6. **How tier-page ticks work without pending marks.** Chosen: a tick places the Lane at
   once. An untick returns it to its start Tier when that Tier is lower; otherwise the
   Lane is unplaced in the full wizard, or moved one Tier down in a focused screen.
   Entering page 1 places every unplaced Lane. Why: this removes `_marks` while keeping
   the pinned flows: 1a, 3, 5, 8, 8b (edits survive back and forward), 16, 17, 18, 39b,
   44b's fall-through, and 75's refusal after an untick.
7. **Whether routing edits count as a choice that refuses a rescan.** Chosen: yes;
   `is_settled` covers routing. Why: "a rescan never discards a choice" (the user,
   2026-09-24), and routing now lives in the draft that a rescan replaces. Today a rescan
   after a routing edit keeps the edit only because `routing_doc` sat outside `_load`. No
   test or ticket relies on that.

### G. Relay seam

1. **Whether the harness preflight (codex inside a nested Seatbelt) moves into the
   Relay's check, so that it refuses before a Run starts with exit 2.** Chosen: no. It
   stays a blocked Run, asked in the relayed work after the Run starts and before the
   Meter probe. The Relay's check covers only the relay layer: node, the pin and the relay
   scripts. Why: ef6e12d, four days old, made it a blocked Run on purpose ("return blocked
   with the reason, so the run spends no Meter"). It placed the check before the probe
   because `claude -p /usage` can spend the quota it measures, and test 12g asserts the
   Ledger start and finish. Moving it would change an exit code that callers read.
2. **Whether `dispatch.json` keeps the relay's raw `usage` record or records normalized
   Token counts.** Chosen: rename the key to `tokens`, holding
   `{in, out, cache_read, cache_write}`, in the same `DISPATCH_FIELDS` position, together
   with the same rename on `runs.Finish`. The raw record stays in the relay's own
   `result.json`. Why: a grep shows that `report.py` is the key's only reader; the
   dashboard and the courier never read it. Keying the counts like the Lane's price record
   removes every relay spelling from the report. Run directories from before the change
   read as unmeasured, while `runs.jsonl` keeps the cost of every Run already logged
   (`cmd_log` stores `rec['cost']`).
3. **Where the one offline world lives.** Chosen: in `scripts/evals.py`, as
   `evals.OfflineWorld`. Why: the offline eval is shipped and must keep running end to
   end. `evals.py` already reaches into `tests/fake-ads` for the fake relay, and the tests
   already import `evals` (`test_evals.test_not_installed_is_skip`). A helper module in
   `tests/` would not match the `tests/test_*.py` glob in the Makefile, and the shipped
   eval would have to import it across directories.
4. **Whether `Ads.check` reimplements the pin check in Python or keeps `ads.sh check`.**
   Chosen: keep `ads.sh check`, and call it with `ADS_DIR` set explicitly. A test guards
   that `relays.DEFAULT_DIR` matches `ads.sh`'s default. Why: `make runtime` and
   `references/maintenance.md` run `ads.sh check`, so a Python copy would be a second pin
   check that could drift. The only duplication left is one default path, and a test pins
   it, the same way `test_dispatch` already reads `ADS_COMMIT` from `ads.sh`.
5. **Whether the fake adapter is scripted with what a relay says (Report) or with the
   settled Finish.** Chosen: with the Report. Why: scripting the Report means settling
   runs under every fake. The settling table is then tested through the interface, and
   C's Run tests receive Finishes that a relay could really produce.
6. **Whether `Ads.run` catches KeyboardInterrupt and waits for the relay's aborted
   result.** Chosen: no. It propagates, and `runs.execute` ends the Run as "dispatch
   interrupted", as dispatch does today. Why: `subprocess.run` kills the relay 0.25 s
   after the interrupt, before the relay writes its touched files. Fixing that means
   changing how the process is waited on, which risks an orphaned worker and has no test
   harness yet. The seam makes it a one-place change in `Ads._launch` later.

### H. Benchmark snapshot

1. **How long a cached Epoch fetch stays fresh.** Chosen: 24 hours, the same as
   Artificial Analysis. Why: the cache then has one rule. The CSV is about 360 KB
   (measured 2026-10-11), and Epoch serves it with `max-age=0` and an ETag, so there is no
   publishing schedule to match. The `r` key deliberately does not renew Epoch, so the TTL
   is the only way new Epoch rows arrive; a week would hide a new model's first Epoch
   figures through the days the user is screening it. A candidate line for ADR 0001.
2. **Which rows the snapshot keeps when a fetch fails and an older copy is cached.**
   Chosen: the cached copy, with its age in the note, ahead of the repo rows named with
   `--effort-rows`. Why: the cache is this machine's last read and is normally newer than
   the committed rows. It gives Epoch, which has no repo rows, any fallback at all. A
   failed `r` then keeps exactly the rows launch read, which lets setup drop its list of
   fallback paths. With an empty cache, the repo rows still stand as today. A candidate
   line for ADR 0001.
3. **What `bench.py` (the report) does when Epoch cannot be fetched.** Chosen: it writes
   the report with Epoch skipped and the reason on Epoch's source line, and exits 0. A
   named file that cannot be read still exits 1. Why: this follows the wizard's rule that
   a source that is down is a note, never a stop. The Artificial Analysis rows alone are
   still evidence, and today's exit 1 throws them away.
4. **Whether offline runs (`--no-discover`, `bench.py model`) read the cache.** Chosen:
   no. They read only named files, and Epoch is skipped unless `--epoch-csv` names a file.
   Why: `--no-discover` promises to skip every live acquisition, and `bench.py model`
   promises never to fetch. A cache read would make a test's output depend on what this
   machine has cached.
5. **Whether `bench.py` (the report) fetches Artificial Analysis too.** Chosen: no. AA
   still comes only from `--effort-rows`, and only Epoch goes through the cache. Why: this
   keeps the report's documented contract and its tests offline. The wizard stays the one
   command that refreshes AA.

## Build plan

### Lanes

Four lanes. Each lane is one builder working its two candidates in order, on its own
branch `worktree/delegate-deepening-<lane>`, based on the effort branch and merged back
into it (`docs/agents/worktrees.md`). Lanes may build at the same time. They merge in the
order below, and a lane that merges later rebases onto the lanes merged before it, as
the rebase notes say. The effort branch then goes to main as one PR.

| Lane | Candidates, in order | Tickets | Why these two together |
|---|---|---|---|
| run-and-relay | C, then G | 01-04 (C1-C4), 05-08 (G1-G4) | Both change `delegate.dispatch`, `runs.py` (`Finish`, `DISPATCH_FIELDS`), `test_dispatch`, `test_runs` and the offline world. C1 comes first, so G's `Relay.run` returns C's `runs.Finish` into the work `runs.execute` calls, with no second outcome type and no throwaway wiring. The lane touches no catalog, setup or bench file. |
| catalog-write | D, then F | 09-12 (D1-D4), 13-15 (F1-F3) | Both change `setup.main`'s save branches, `confirm_and_write`, `write_focused`, `catalog_edit`, `catalog.py` and `test_setup`. D first gives F's draft a commit to hand its documents to, and D3 owns the focused-screen fix that F3 would otherwise repeat. |
| meters-and-preview | B, then E | 16-19 (B1-B4), 20-23 (E1-E4) | E stands on B: rank takes a Meter snapshot, `readout(spend=)` feeds the Handover, and `usage.MAX_PACE` caps the Pace to lead. Both rewrite `rank.rank_range`, `report.py`'s popup, and the dashboard's `model.py` and `deck.meter_verdict`. |
| bench-evidence | A, then H | 24-26 (A1-A3), 27-29 (H1-H3) | Both change `bench.collect`, `epoch_records`, `inspect_model`, `bench_page.render` and `write`, `test_bench` and `test_bench_page`. A first fixes the evidence-based signatures, so H changes only how rows are acquired. |

Merge order:

1. **run-and-relay.** It shares no file region with the catalog lanes, and B's Meter
   reads go inside the relayed work it shapes.
2. **catalog-write.** It is the largest `setup` and `setup_tui` rewrite, so it merges
   before the bench lane's smaller setup edits.
3. **meters-and-preview.**
4. **bench-evidence.** It merges last, so H1's network tripwire in `make test` then guards
   every lane's tests.

Within a lane, tickets build in number order. A ticket's `**Blocked by:**` line names
every ticket that must land first; the first ticket of a lane's second candidate also
names the first candidate's last tickets.

### Rebases at merge

- **meters-and-preview onto run-and-relay.** The Meter hold is one private function in
  `runs.py` (C1); B1 swaps its `usage.mark_limited` and `clear_limited` calls for
  `usage.hold` and `usage.release`, and checks `held_until` in C's test_runs usage-limit
  case and C1's dispatch wiring case (test_dispatch 36 went with C1). B3 puts its FRESH
  and FORCED reads inside the relayed work `runs.execute` calls, in this order: the
  preflight, `usage.read(routing, FRESH)`, `relay.run(job, run.path)`,
  `usage.read(routing, FORCED)`, return the Finish; it drops `probed` from `run` and
  `dispatch` next to G3's `relay` parameter. B3's probe-counting tests use G2's
  `OfflineWorld` and its `world.stub` hook. `evals.ping_lane`'s `rank.load_usage` call
  becomes `usage.read(cat['routing'], CACHED, path=sandbox.meters)` beside
  `OfflineWorld`.
- **meters-and-preview onto catalog-write.** B1 changes `catalog_edit`'s `meters`
  parameter and `_observations_report`, and B4 changes `model_queue.path()`; D rewrote
  `catalog_edit`'s read side and the `model_queue` scan. The regions do not overlap.
- **bench-evidence onto catalog-write.** A1 builds its one `LaneEvidence` in F2's new
  `Wizard._load`, and converts F2's rewritten test reads (`published_names` and
  `carry.decisions(L, rows)`) to `LaneEvidence`. H1 rebases its `setup.main` launch and
  rescan, `propose_generation` and start-facts changes onto D's. H3 adds its `epoch_rows`
  Wizard argument on top of F2, which absorbs it.
- **bench-evidence, last.** After its rebase, H1 runs the whole `make test` under the
  proxy tripwire on 3.9 and 3.13 and fixes any `setup.main` case that still fetches.

### Contracts between candidates

- **One type for how relayed work ended: `runs.Finish` (C1).** G's `Relay.run` and
  `_settle` return it, and relays.py defines no outcome type of its own. Every Finish
  field except `returned` is a `DISPATCH_FIELDS` key. G4 renames `Finish.usage` and the
  `DISPATCH_FIELDS` entry `usage` to `tokens` in one change, and C's test_runs key-order
  case follows.
- **The Ledger records Runs only.** No probe writes a meter event (decision C.2). C4
  deletes `events.py` and the meter event in `usage.write_cache`; B3 adds the test_usage
  case "a probe writes nothing to the Ledger".
- **Termination passes through every adapter.** C's SIGTERM conversion raises a private
  subclass of `BaseException`, as `KeyboardInterrupt` is. G's `Ads` catches only
  `OSError` and `ValueError` around the spawn and the file reads, and B's `usage.read`
  catches at most `Exception`.
- **One Meter hold call site.** It is one private function in `runs.py` (C1); B1 changes
  only that function.
- **`usage.MAX_PACE`.** B4 exports `MAX_PACE = 1 / CYCLE_FLOOR` (50 today) as a public
  name, and E2 reads it. `WEEK_DAYS` and `DAYS_PER_MONTH` become private in `usage.py`.
- **The Handover belongs to E4.** B2 adds `Snapshot.readout(spend=)` and builds the
  popup's Meter rows from Readouts, and leaves `report.handover`'s loop alone. E4 moves
  the loop into rank on `readout(spend=)`.
- **Rank ranks over a map of Readouts.** B3 shapes `rank_range` as
  `readouts = {meter: snap.readout(meter, cat)}` followed by a private ranking core over
  that map. E's what-if replaces one entry (`dataclasses.replace(readout, pace=p)`, or
  `snap.readout(m, cat, spend=x)`) and reruns the core, with no second Snapshot read.
- **D3 owns the focused screen's start.** A focused screen proposes no generation (D3).
  F3 adds only that its confirm rows equal `draft.changes()`.
- **The draft hands documents to the commit.** `CatalogDraft` is built from the
  `CatalogRead`'s dicts, and `documents()` returns `{"lanes": ..., "routing": ...}`, keyed
  by `catalog_commit.DOCUMENTS` names. The full wizard commits both documents; a focused
  screen commits only the documents `draft.changes()` touches, so default Classes the
  screen never listed are never written.
- **Agent files follow the global lanes document.** A commit syncs Agent files only when
  its documents include the live catalog's global `lanes` document, never on a
  project-scope `catalog set` (the dashboard's only write). Callers print
  `Committed.lines` to stderr, so `catalog set`'s JSON stdout stays byte-identical.
- **A owns attribution; H owns acquisition.** `epoch_records(evidence)`,
  `evidence_records(evidence)` and the evidence-based body of `collect` are A's; H changes
  `collect`'s inputs to `(lanes_doc, epoch_rows=None, effort_rows=None)` and
  `inspect_model`'s to rows, and lists `LaneEvidence(lanes_doc, epoch_rows).records()` on
  the page. H's Epoch rows keep `model` and `slug`.

### Rules for every ticket

- **Python 3.9 is the floor.** Use `from __future__ import annotations`,
  `typing.Optional` and `NamedTuple`; no runtime `X | Y`, including inside `isinstance`
  and in the dashboard; no `match`. Also none of these: `os.path.realpath(strict=True)`
  (3.10; find a dangling link with `os.path.lexists` against `os.path.exists`, and a loop
  with `os.stat` raising `OSError` with `ELOOP`), `datetime.UTC` (3.11; use
  `datetime.timezone.utc`), `bisect` with `key=`, `zip(strict=)`, `itertools.pairwise`,
  `dataclass(slots=, kw_only=)`, `enum.StrEnum`, `contextlib.chdir`, and
  `TemporaryDirectory(ignore_cleanup_errors=)`. Never hash B's `Snapshot` or F's
  `CatalogDraft` (its `__eq__` sets `__hash__` to None).
- **Tests never reach the web.** Every new test that runs `setup.main` passes
  `--no-bench` (or `--epoch-csv tests/fixture/bench-epoch.csv`), plus `--no-discover` or
  `--fixture-dir`, under a temporary `HOME`. Every new case that calls `bench.collect`
  passes the Epoch fixture until H1 makes it take rows. Each lane runs `make test` with
  the proxy variables pointed at a closed local port before it merges.
- **The statusline's CLI is a contract.** The dotfiles statusline script, the Herdr popup
  and Hammerspoon run `report.py statusline`, `statusline --popup` and
  `statusline toggle|on|off`. B2, C3 and E3 each assert that these still exit 0 with
  output, and every ticket keeps them byte-stable.
- **TUI text goes to a Claude Opus agent under `/frontend-design:frontend-design`**
  (ADR 0001): D2's start-page queue lines, F2 and F3, and H1's start-page rows line.
- **Shared docs stay additive.** `CONTEXT.md` gained every term of this effort with this
  spec, in the matching section. A ticket that names a term keeps its entry true to what
  ships, and sharpens it minimally if the build changed it. Each lane rebases
  `CONTEXT.md` and `references/architecture.md` at merge rather than rewriting
  neighbouring entries.

### ADR edits

No lane ticket edits `docs/adr/`. After all four lanes merge, and only for the decisions
the user confirms, one change:

- adds one line each to ADR 0001 for decisions A.3 (a Lane is dominated only by efforts
  its own Harness runs), B.1 (a Model meter's Weekly figure), C.2 (the Ledger records
  Runs only; the latest Meter reading lives in the usage cache), H.1 and H.2 (Epoch's
  24-hour cache, and a stale cache before the repo rows);
- adds ADR 0002 for decisions D.1 and D.2: catalog documents are written through links
  and a dangling link is refused; Agent files are plain files and a link at a Lane's path
  is replaced;
- adds ADR 0003, "One rule places a Lane inside its Tier", for decisions F.1 to F.3.

### Ticket map

| No. | Label | Title | Blocked by |
|---|---|---|---|
| 01 | C1 | A started Run always finishes | None |
| 02 | C2 | A native Run ends as handed to its agent | 01 |
| 03 | C3 | The statusline counts running Runs through the Run module | 01 |
| 04 | C4 | Only the Run module writes the Ledger | 02, 03 |
| 05 | G1 | A relay that crashes before writing its result says why | 01, 04 |
| 06 | G2 | The offline eval and the dispatch tests share one world that the host's Seatbelt never reaches | 05 |
| 07 | G3 | Only the ADS adapter knows node, the pin and the relay argv | 05, 06 |
| 08 | G4 | The report prices a Run from Token counts, not relay key spellings | 05 |
| 09 | D1 | A wizard save never overwrites a catalog change made while it was open | None |
| 10 | D2 | Agent files and the model queue follow every catalog commit | 09 |
| 11 | D3 | A focused setup screen saves only the change made on it | 09 |
| 12 | D4 | catalog set and the dashboard write through the one commit | 09 |
| 13 | F1 | The plain wizard writes the Order it prints | 10, 11, 12 |
| 14 | F2 | The setup wizard keeps every decision in one draft | 13 |
| 15 | F3 | The confirm page lists exactly what save writes | 14, 11 |
| 16 | B1 | Every reader of the Meters sees a usage-limit hold, the dashboard included | None |
| 17 | B2 | Every display shows one weekly figure and one Gate per Meter | 16 |
| 18 | B3 | A job reads the Meters once, by freshness, with no probed flag | 16, 17 |
| 19 | B4 | Harness probes hand the Meters module their Windows, and usage.py exposes only its interface | 18 |
| 20 | E1 | The deck codes every Lane by the cause rank gives it | 18 |
| 21 | E2 | The deck's aid marks the Pace rank says each Meter needs to lead | 20, 19 |
| 22 | E3 | The popup shows the Pace to lead rank gives, even past its axis | 21 |
| 23 | E4 | Only rank replays its own Pick, and the popup's handover comes from rank in quota points | 22, 17 |
| 24 | A1 | The benchmark page and the wizard reach the same verdict for every Lane | None |
| 25 | A2 | An Epoch row reaches the same Lane in every benchmark view | 24 |
| 26 | A3 | One published name names one Model on every Harness that runs it | 25 |
| 27 | H1 | The wizard reads Epoch through the cache, and a fixture run reaches no URL | 25, 26 |
| 28 | H2 | The benchmark report and model inspection read the same snapshot as the wizard | 27 |
| 29 | H3 | The benchmark page lists the Epoch rows beside the accepted rows | 27 |

### Left for a follow-up

- `delegate.resolve()` exits 14 ways and repeats rank's request checks (`delegate.py`
  `resolve` against `rank.py` `main`), and `run` loads the catalog and the orchestrator
  profile twice. Both touch the dispatch path C and G reshape, so they wait until
  run-and-relay has merged.
- `setup_tui.Wizard` still takes 18 constructor parameters. F2 replaces its internal
  state but keeps the constructor, and H3 adds one more (`epoch_rows`). This is not a live
  bug; F2 records it as a known leftover.

## A. Lane evidence

One module owns which benchmark rows belong to a Lane.

Tickets: 24 (A1), 25 (A2), 26 (A3). Lane: bench-evidence, before H.

### Problem

About twenty-five functions in seven modules decide which benchmark rows belong to which
Lane, and they use at least four rule variants: a per-harness fan-out
(`resolve_published_models`), a whole-catalog pool (`resolve_published_model`), a slug
strip that ignores the harness (`bench.model_matches_slug`), and the carry rule's family
map (`carry.families`). Each reader works the answer out again, so the readers disagree.
The benchmark page strikes agy's Opus at high while the wizard keeps it. A `published_as`
entry reaches one Harness only. Epoch rows match one way in the scores table and another
way in `bench.py model`. Carry and the Tier proposal claim different rows for the same
Lane. One wizard session also resolves the same rows against the same catalog about
seven times.

### Interface

`scripts/published_names.py` moves to `scripts/lane_evidence.py` with `git mv`, so its
history stays with it. It imports only `harnesses`.

```python
from __future__ import annotations
from typing import List, Optional, Sequence, Tuple

class LaneEvidence:
    """Which benchmark rows belong to which Lanes, for one catalog and one row set."""
    def __init__(self, lanes_doc: dict, rows: Optional[Sequence[dict]]) -> None: ...
    @property
    def available(self) -> bool: ...                     # rows was not None
    def lane_rows(self, lane: str) -> List[dict]: ...     # this Lane's evidence
    def model_rows(self, lane: str) -> List[dict]: ...    # its Model on its Harness
    def records(self) -> List[dict]: ...                  # one per row, for display
    def identify(self, name: Optional[str]) -> dict: ...  # the Model a printed name names
    def unmatched(self) -> List[str]: ...                 # printed names no Model answers to

def model_identity(lane: dict) -> str: ...                # the key "one Model" means across harnesses
def published_as_conflict(lanes: dict) -> Optional[Tuple[str, str]]: ...  # (lane, message) or None
```

Invariants:
- The constructor attributes every row once, and every method after that is a lookup.
  Methods return the caller's own row objects unchanged and in input order. No row is
  copied, re-keyed or mutated, and the catalog is read but never written. Whether a row
  counts (uncertain, composite, score shape) is decided by the reader, not by this
  module.
- A row's printed names are its `model`, then its `slug` when it has one (an Epoch row).
  The first printed name that names a Model decides the row.
- A printed name names a Model when, lower-cased with the `-_. ` separators collapsed, it
  equals one of three things: a `published_as` entry (which names the Model of the Lane
  carrying it), a Lane's Model identity, or a Lane's own model string. The Model identity
  is the harness's family base, normalized, so agy's `claude-opus-5-5-high`, kiro's
  `claude-opus-5.5` and Claude Code's `claude-opus-5-5` are one Model. The harness decides
  what a family is, never the spelling, so a codex slug that ends in `-low` is a Model of
  its own. A name that matches two Models is unresolved ("conflicting identity").
- `model_rows(lane)` holds the rows that name the Lane's Model and either state no effort
  or state one that the Lane's Harness runs for that Model. The Harness runs an effort
  when the adapter's `offers_effort` says so for any of the Model's Lanes on that
  Harness. A harness with no adapter runs every effort. All Lanes on one Harness and
  Model get the same list. A published name reaches every Harness that runs its Model.
- `lane_rows(lane)` is the part of `model_rows(lane)` measured at the Lane's own effort.
  This is the one effort attribution rule. An unstated effort (None, empty, or `unknown`)
  matches no Lane.
- `records()[i]` describes the i-th dict row and has these fields: `row`, `published`,
  `key`, `effort`, `identity` (`resolved` or `unresolved`), `identity_reason` (`empty
  published name`, `no catalog model` or `conflicting identity`), `candidates`,
  `model_key`, `lane_model`, `lane_models`, `model_lanes`, `lanes` and `attributed`.
  `lane_model` is the Model's display name: a Lane's model string that equals the
  identity (`claude-opus-5-5`), or else the harness family base (`gemini-3.8-flash`). It
  never depends on the row's effort. `model_lanes` lists the Lanes whose `model_rows`
  hold the row. `lanes` lists exactly the Lanes whose `lane_rows` hold it, and
  `attributed` is `bool(lanes)`.
- `identify(name)` returns the identity part of the record that a row printing `name`
  would get.
- `unmatched()` lists the printed names of unresolved rows, each once, in the order first
  seen.
- The evidence describes the catalog it was built from. A caller that changes a Lane's
  model, harness, effort or `published_as` builds a new one. Changes to `enabled`, `tier`
  and `order` do not need a new one, so the wizard's current lanes can reuse it.

Error modes: none of the methods raises because of what a row contains. Rows that are not
dicts are skipped. When `rows` is None, `available` is False and every query returns an
empty result. A lane name the catalog lacks gets `[]`. A catalog lane with no model owns
nothing. `published_as_conflict` returns `(lane name, message)` for the first entry that
would make one name denote two Models. That covers an entry naming another Model's
identity or slug, and one name used on Lanes of two Models. One name on the Lanes of one
Model across several Harnesses is allowed. The checks that `published_as` is a non-empty
list of non-empty strings stay in `catalog`.

What it hides: name normalization, the `published_as` map and its fan-out, harness
families and agy's effort-in-slug members, the per-harness fan-out, which efforts each
Harness runs, Epoch's second printed name, the `unknown` effort key, the attribution
equality, the Model's display name and grouping key, conflict detection, and the list of
unmatched names.

What stays outside: `harnesses/claude.py`'s `PUBLISHED_NAME`, the rule by which
`generation()` reads a published `Claude <Level> <version>` as `claude-<level>-<n>`,
stays in the claude adapter. It names a Model that no Lane carries yet, for discovery,
so it is not Lane attribution, and A3's "no module outside `lane_evidence` normalizes a
printed name" does not count it.

Dependency category: in-process. The module reads `harnesses.family`, `harnesses.get`
and `offers_effort`. It adds no port, because nothing varies across the seam: there is
one adapter and it is a pure function of the catalog and the rows.

### Design it twice

- **Shape 1, chosen: an evidence object that callers query by Lane.** Carry, the Tier
  proposal and collect each ask one question: what are this Lane's rows, or its Model's
  rows on its Harness? Display code reads `records()` and `identify()`. The seam sits at
  the Lane, which is the unit that carry and ranking decide on.
- **Shape 2: an attribution table.**
  `attribute(lanes_doc, rows) -> [{row, model_key, harness_models, runnable_harnesses, lanes}]`,
  and each caller filters it. This is easy to serialize, but every caller has to learn
  the record and write its own "same Model on my Harness at an effort it runs" filter.
  Ticket 31 fixed that filter in three places and missed three more. A change to the
  rule, such as the efforts each Harness runs or the `published_as` fan-out, would be
  split between the builder and four filters.
- **Comparison.** Shape 1 has more depth, because the per-Lane questions hide the index.
  It has better locality, because one file holds the rule. Its seam is placed where the
  domain decides. The advantage of shape 2, JSON-ready data, survives in shape 1 as
  `records()`. Patching `published_names` in place, by adding the `published_as` fan-out
  only, was also rejected: it would leave all four rule variants alive.

### Callers migrated

- `carry.decisions(lanes_doc, evidence)` reads `model_rows` and `lane_rows`.
  `dominating_effort` and `first_domination` take the Lane's own rows and no longer take
  a model or a family map. `evidence_unavailable(evidence, decided)` reads `available`.
  (`carry.py:98-251`)
- `tier_proposal.propose(lanes_doc, evidence, settings, names=None)`: `lane_scores` reads
  `lane_rows`. (`tier_proposal.py:47-118`)
- `setup_tui.Wizard._load` builds one `LaneEvidence` per scrub, at launch and on each
  rescan. `_unmatched`, `_proposals` and `tier_proposals` read it.
  (`setup_tui.py:376-377, 713-718`) catalog-write merges first, so this lands in F2's
  rewritten `_load`, and F2's test reads (`published_names.resolve_effort_rows`,
  `carry.decisions(L, rows)`) become `LaneEvidence(...).unmatched()` and
  `carry.decisions(L, LaneEvidence(L, rows))`.
- `bench_page.render`, `plot_data` and `write` keep the signature
  `(bench, lanes_doc, effort_rows)`. Render builds one evidence, asks carry once for the
  verdicts with no try/except, and annotates the records once. Each point lists its
  Lanes, and each Lane carries its own verdict (`off`, `kind`, `source`, `competitor`). A
  point is `lane_off` only when every Lane on it is proposed off. A point gets `beatenBy`
  only from an off verdict whose source is the board's own. The finding names only the
  Lanes that are off. Points are grouped by the Model's display name. `_figure_cell` reads
  the owning Lanes from collect. (`bench_page.py:164-287, 954-979, 1069-1090, 1378`)
- `assets/bench_page.js` shows each Lane's own verdict in the tooltip and in the evidence
  table (`:630-631, 907-909`). It also fixes three stale citations: `setup_tui._beats`
  becomes `carry.beats`, `setup_tui.group_lanes` becomes `bench.group_lanes`, and
  `setup_tui.parse_tier_lines` becomes `tier_lines.parse_tier_lines` (`:268, 292, 316`).
- `bench.collect` builds one evidence for the Epoch rows and one for the effort rows. Its
  signature stays `collect(lanes_doc, epoch_csv=None, effort_rows=None)`; H1 later swaps
  `epoch_csv` for `epoch_rows`. The model view takes records with the model's
  `model_key`, which is context at any effort. The lane section uses `lane_rows`. Each
  model figure names the Lanes that claim it. `bench.evidence_records(evidence)`,
  `bench.epoch_records(evidence)` and `bench.inspect_model` read `records`, `identify` and
  `lane_rows`, and H keeps these signatures. (`bench.py:139-1500`)
- `bench.group_lanes`, `bench.bench_order_key` and `bench_page._lane_list` group by
  `model_identity`. (`bench.py:747-781`)
- `catalog.validate_lanes` calls `published_as_conflict` and keeps only the shape checks.
  (`catalog.py:213-225, 332-361`)
- `harnesses/agy.py` drops its unused `import published_names`, which closed an import
  cycle through `harnesses`, and A3 fixes its comment that cites
  `published_names.strip_effort_suffix`. `effort.py`'s docstring names `lane_evidence`.

### Deleted

- A1: `carry.families`, `carry.family_of` and `carry.dominating_row`.
  `resolve_effort_rows`. `bench_page._proposals` (it swallowed every exception),
  `_decision_for`, the dead `_lane_at`, and the re-keying block in `_annotate`. The unused
  `from published_names import resolve_published_model` in `bench.py`.
- A2: `lane_evidence.resolve_published_model` (the unused singular resolver) and
  `resolve_published_models`. From `bench`: `model_matches_slug`, `match_epoch_rows`,
  `aa_component_rows`, `effort_attributes`, `lane_figure`, `_canonical_model`,
  `identity_of`, `inspect_targets`, `_ident_models`, `_lanes_at`, `_attributed`,
  `_record_matches_query`, and the slug fallback in `_record_from_epoch_row`.
- A3: `carry.model_of`. `lane_evidence.strip_effort_suffix`, `MODEL_EFFORT_SUFFIXES` and
  `published_as_map`. `normalize_name` becomes private. Catalog's `owners` and `claimed`
  block.

### Tests

New: `tests/test_lane_evidence.py`. The interface is the test surface.
- A1: "one published Opus row is evidence for both harnesses' Lanes at its effort"
  (OPUS_TWO_HARNESSES). "agy's Model rows hold only efforts agy runs" (OPUS_ONE_AGY). "a
  codex slug ending in an effort word is a Model of its own" (GUARD_LANES). "an agy
  family's rows at one effort belong to the Lane whose slug carries it"
  (AGY_CARRY_LANES). "a row that states no effort belongs to the Model and to no Lane".
  "a published_as name reaches every Harness that runs the Model" (PUBLISHED_AS_OPUS).
  "None is unavailable; an empty list is available and empty". "a Lane the catalog lacks
  has no rows".
- A2: a port of test_catalog cases 7.5 to 7.9 to `identify` and `lane_rows`, keeping the
  same printed names. "an Epoch row names its Model by display name, then by slug". "a
  record's lanes are exactly the Lanes whose lane_rows hold its row" (over every
  fixture). "an agy Model's display name is its family, whatever the row's effort".
  "unmatched lists each unnamed printed name once, first seen first".
- A3: "kiro's claude-opus-5.5, Claude Code's claude-opus-5-5 and agy's
  claude-opus-5-5-high are one Model; codex gpt-6-edge-low and gpt-6-edge-high are two".
  "published_as_conflict allows one name on one Model's Lanes across harnesses and
  refuses it across Models".

Every new `test_bench` and `test_bench_page` case that calls `collect` passes the Epoch
fixture `tests/fixture/bench-epoch.csv`, so no A test reaches the web before H1's
tripwire.

Replaced:
- test_bench "every harness but agy keys the carry rule on the model string"
  (`carry.families`) is replaced by the guard test in test_lane_evidence. Its carry
  verdict assertions stay, built on an evidence.
- test_bench "one published Opus row reaches the lanes of both harnesses"
  (`resolve_effort_rows`) is replaced by test_lane_evidence.
- test_bench "an evidence record names the lanes of every harness" and "an AA component
  row reaches both harnesses' Opus" become a records test and a check of collect's lane
  section.
- test_bench's collect test stops calling `build_epoch_section`/`match_epoch_rows` and
  calls `collect` only.
- test_bench inspection: "conflicting family identity without an effort stays
  unresolved" becomes "a row without an effort names the agy Model and no Lane claims
  it". "canonical Model query retains unresolved candidate evidence" becomes "a member
  slug's query shows its Model's unattributed rows".
- test_catalog 7.5, 7.6, 7.6b, the 7.7 resolve case, the 7.8 suffix-on-published-side
  case and 7.9 are replaced by test_lane_evidence (A2). test_setup_tui case 30 becomes
  `identify` and `unmatched` (A2).
- `carry.decisions(L, rows)` becomes `carry.decisions(L, LaneEvidence(L, rows))` in
  test_bench (10 calls), test_bench_page (1), test_discover (1), and the test_setup_tui
  reads F2 rewrote. test_tier_proposal's 6 `propose` calls pass an evidence.
  `carry.model_of` becomes `lane_evidence.model_identity` in test_setup_tui (4) and
  test_bench_page (1).

Deleted: test_bench "dominating_row gives the agy competitor's point on the row's own
board" (the existing agy struck-point test in test_bench_page covers the drawn result).
test_catalog 7.8 `strip_effort_suffix` and 20.1 `MODEL_EFFORT_SUFFIXES` (the agy
adapter's family test in test_bench already covers every effort word, xhigh included).

### Live bugs fixed (red first, then green)

1. **The page strikes `opus55-high@agy` while the wizard keeps it** (verified by
   running). Test: test_bench_page "one Opus point both harnesses share strikes only the
   Lane carry proposes off" (A1). Fixture: OPUS_TWO_HARNESSES, which is Claude Code Opus
   at low/medium/high/xhigh and agy Opus at low/medium/high. Rows: OPUS_ROWS,
   `Claude Opus 5.5` on aa boards b1 and b2 at low 0.40/$1.0, medium 0.60/$0.9, high
   0.70/$2.0 and xhigh 0.80/$1.5. Red: the high point is `lane_off` with `beatenBy` xhigh.
   Green: the high point is `lane`; its `opus55-high@claude` entry has off "xhigh wins on
   aa" and its `opus55-high@agy` entry has off None; the low point is `lane_off` with
   `beatenBy` medium; the finding never names `opus55-high@agy`.
2. **agy's only Opus Lane is proposed off by an effort agy does not run.** This was found
   while designing this candidate and verified in-process: with one agy member, the
   single-candidate rule gives it every Opus row. Test: test_bench "agy's only Opus Lane
   is not proposed off by an effort agy does not run" (A1). Fixture: OPUS_ONE_AGY, which
   is Claude Code Opus at low..xhigh plus agy `claude-opus-5-5-high` only, with OPUS_ROWS.
   Red: dominated, competitor xhigh. Green: `not_dominated`, while `opus55-high@claude`
   stays dominated by xhigh.
3. **`published_as` reaches one Harness only** (verified). Tests: test_tier_proposal "a
   published_as name on Claude Code's Opus Lane scores agy's Opus Lanes too" (A1).
   Fixture: PUBLISHED_AS_OPUS, which is `opus-high@claude` on `claude-opus-5-5` with
   `published_as: ["Opus 5.5 Thinking"]` plus agy `claude-opus-5-5-high` and `-low`, with
   rows printed `Opus 5.5 Thinking` on the sample's tier benchmark at high (52.0, $2.0)
   and low (35.0, $0.5). Red: only the Claude Code Lane is scored. Green: all three Lanes
   are scored. Also test_catalog "7.10 one published name on Lanes of one Model on two
   harnesses is accepted" (A3). Red: refused with "names the same model". Green: accepted,
   while 7.3 and 7.7 still refuse a name used across two Models.
4. **Carry and the Tier proposal claim different rows for one Lane** (verified). Test:
   test_tier_proposal "carry and the Tier proposal claim the same rows for a Lane" (A1).
   Fixture: PUBLISHED_AS_FLASH, which is agy flash at low/medium/high with
   `published_as: ["Gemini Flash 3.8 Preview"]` on `flash-high@agy`, and one row printed
   that name at low on the tier benchmark (35.0, $0.2). Red: carry gives `flash-low@agy`
   `not_dominated` (it has rows) while `propose` scores no Lane. Green: both claim the row
   for `flash-low@agy` only. After this change carry has no effort comparison of its own.
5. **Epoch rows are matched two ways** (verified). Test: test_bench "an Epoch row reaches
   a Lane in the scores table and in model inspection alike" (A2). Fixture:
   `fable-high@claude` on `claude-fable-5-1` at high, and one Epoch CSV row with model
   `Claude Fable 5.1`, model_version `claude-fable-5-1-20260901_high`, DeepSWE 0.61. A
   second case has `published_as: ["Fable 5.1"]` and display `Fable 5.1`. Red: `collect`
   lane cells are `{}` while `inspect_model` attributes the row. Green: both give 0.61.
6. **`_proposals` swallows every exception.** Test: test_bench_page "a pre-screen failure
   stops the page instead of drawing no verdicts" (A1). The test monkeypatches
   `carry.decisions` to raise RuntimeError. Red: render returns a page with no verdicts.
   Green: render raises. The wizard calls the same function first, so this adds no new
   crash path.
7. **Stale citations in bench_page.js.** Test: test_bench_page "every Python function
   bench_page.js cites lives where it says" (A1). It reads each `module.name` in the
   script's comments and asserts that the module defines that name itself. Red:
   `setup_tui._beats` does not exist, and `setup_tui.group_lanes` and
   `setup_tui.parse_tier_lines` live elsewhere.
8. **An agy Model's efforts are drawn as separate models** (verified: the finding lacks
   its arithmetic). Test: test_bench_page "an agy Model's efforts are one sweep, so its
   finding shows the arithmetic" (A2). Fixture: AGY_LANES and AGY_SWEEP. Green: both
   points' model is `gemini-3.8-flash`, and the finding contains "high scores 0.1 less
   than medium and costs $1 more (+100%)".

### Behaviour changes the user will see

- Fewer Lanes are proposed off: an agy family with one member, and grok (the real AA rows
  publish Grok 4.6 at low, medium and xhigh, which the grok CLI cannot run).
- The page has no "beaten by" on points that no Lane runs. A shared point is struck only
  when every Lane on it is off.
- An agy Model shows under its family name (`gemini-3.8-flash`) and draws as one sweep.
- A row with no stated effort on an agy family is resolved and unattributed, where it
  used to read "conflicting identity".
- `bench.py model <agy member slug>` shows the whole Model.
- Kiro's Opus groups with Claude Code's Opus on the tier pages, as agy's Opus already
  did.
- `bench.py model --json` records gain `model_key`, `key` and `model_lanes`.

### ADR notes

- ADR 0001's carry rule is unchanged: another effort of the same Model, for no more
  money, beats the Lane on more than half the benchmarks one source scored both on, and
  the composite is never counted (`carry.certain_effort_rows` stays). "The same Model" is
  read as ticket 31 reads it: the same Model on the Lane's own Harness, at an effort that
  Harness runs.
- ADR 0001 says the frontier is a display aid and the carry rule is the only thing that
  proposes a Lane off. After this change the page draws only carry's per-Lane verdicts
  and no longer applies the rule itself.
- The catalog stays machine-local: tests use fixtures. No model names are hardcoded:
  efforts and families come from the harness adapters. Effort stays fixed per Lane, and
  attribution is by the Lane's effort.
- `catalog` imports `lane_evidence` the way it imported `published_names`, so routing
  gains no benchmark code; H's routing guard test allows `lane_evidence` for that reason.
- If the user confirms decision A.3, its line goes into the one ADR change made after all
  lanes merge (Build plan, ADR edits).

### Risks

- A and H share the bench-evidence lane, A first. A fixes the evidence-based signatures
  of `collect`, `epoch_records`, `evidence_records` and `inspect_model`, and H changes
  only how rows are acquired. H's Epoch rows must keep `model` and `slug`, which
  `load_epoch_csv_text` already writes and H moves unchanged.
- F (catalog-write) merges before this lane and rewrites `Wizard._load` and
  `tier_proposals`; A1 rebases onto it, as Callers migrated says.
- The real-data label-layout test, which runs under node, may shift once agy points
  group into one sweep.
- `bench_page.js` changes three comments and two display lines. ADR 0001 routes TUI work,
  and this page is not the TUI, but say so in the PR.
- `lane_evidence` must never import `bench`, `catalog` or `carry`, so that rank's import
  chain stays free of cycles.

## B. Meters

One Meter snapshot answers Remaining and Pace for every caller.

Tickets: 16 (B1), 17 (B2), 18 (B3), 19 (B4). Lane: meters-and-preview, before E.

### Problem

The Remaining a Meter has right now depends on which path a caller takes. `usage.py`
exposes about 20 names, and rank, report, delegate, catalog_edit, evals and the dashboard
each use a different mix of `acquire`, `load_cached`, `observations`, `eligible` and raw
JSON. Each of them also re-derives part of a Meter for display. That spread has produced
live drift, all verified on `b268352`:
- The dashboard ranks a held Meter at its probed Remaining.
- The statusline and the popup print different weekly figures for a Model meter: 59%
  against "46% ÷ 57%" on the same cache.
- `cache_path` reaches the usage document but not the hold file beside it.
- `usage.py --pretty` crashes.
- `run` and `dispatch` share one probe only through a `probed` flag that the caller has
  to pass along.

### Chosen interface

The module stays in `scripts/usage.py` (decision B.3). Python 3.9 is the floor
(`from __future__ import annotations`, `typing.Optional`).

```python
CACHED = "cached"   # the document as it is; never probes
FRESH = "fresh"     # probe when the reading is older than max_age_min (default 10) or absent
FORCED = "forced"   # probe now
MAX_PACE = 1 / CYCLE_FLOOR   # the highest Pace a Meter can read, 50 today (public from B4, for E)

def read(routing: Optional[dict], freshness: str, *, path: Optional[str] = None,
         max_age_min: Optional[float] = None) -> Snapshot: ...
def hold(meter: str, reason: str, *, path: Optional[str] = None, now: Optional[float] = None) -> float: ...
def release(meter: str, *, path: Optional[str] = None) -> None: ...
def cache_path(path: Optional[str] = None) -> str: ...

@dataclass(frozen=True)
class Readout:
    meter: str
    harness: Optional[str]
    group: Optional[str]
    remaining: Optional[float]     # Remaining, with any usage-limit hold applied
    pace: Optional[float]
    weekly: Optional[float]        # the Weekly figure: Pace's numerator and what every display shows
    five_h: Optional[float]
    shares_five_h: bool            # a Model meter: its 5h cell belongs to the harness row
    reset_weekly: Optional[float]
    reset_5h: Optional[float]
    week_left: Optional[float]     # share of the week left at the reading: Pace's divisor
    gated: bool                    # routing.meters on and Remaining under the Gate
    week_dollars: Optional[float]  # the catalog Meter's plan price per week
    held_until: Optional[float]    # a usage-limit hold in force, or None
    note: Optional[str]

@dataclass(frozen=True)
class Snapshot:
    path: Optional[str]            # the document read; None for Snapshot.of
    status: str                    # ok | missing | unreadable | malformed | stale
    detail: Optional[str]          # plain words for any status but ok
    taken_at: Optional[float]      # when the probe read it; None for a legacy bare map or no reading
    signature: tuple               # equal for two reads that would rank alike
    @classmethod
    def of(cls, document) -> Snapshot: ...      # an in-memory document with no holds (fixtures, evals)
    def names(self) -> Tuple[str, ...]: ...     # the Meters with a reading, in document order
    def readout(self, meter: Optional[str], cat: Optional[dict], *, spend: float = 0.0) -> Readout: ...
```

`read` takes the routing because the metering switch decides whether FRESH and FORCED may
probe. `readout` takes the catalog because the Gate, the metering switch, the
`model_meter` flag and the plan price belong to whichever catalog the caller is ranking.

**Invariants**
1. `remaining` is the lower of `five_h` and `weekly`. It is 0.0 while a hold is in force,
   and None only when no Window was read.
2. `pace` is the probe's own figure. A row written without one gets
   `round(weekly / week_left, 3)`, computed at `taken_at`, so the popup's
   "weekly ÷ left" always matches the Pace it prints.
3. `gated` is True exactly when the catalog's `routing.meters` is on, `remaining` is
   known, and `remaining < routing.gate`. An unknown Remaining never vetoes, and a
   Remaining equal to the Gate passes. With `cat=None` there is no Gate, so `gated` is
   False.
4. `weekly` is the Weekly figure. For a Model meter it is the lower of the model's own
   week and the harness's week for all models (the probe row's `remaining_weekly`), never
   the model's own week alone. `shares_five_h` is True when the catalog marks the Meter
   `model_meter` or the probe row carries `remaining_weekly_model`.
5. `readout(m, cat, spend=x)` spends x of the Weekly figure only:
   - weekly' = max(0, weekly − x)
   - remaining' = min(five_h, weekly')
   - pace' = weekly' ÷ week_left
   - `gated` is computed again.
   A held Meter stays at 0, and `spend=0` returns the reading itself.
6. Holds come from `limits.json` beside the document that was read, and they are fixed
   when it is read. `hold` reads that same document's weekly reset. `Snapshot.of` carries
   no holds.
7. A CACHED read writes nothing. A probe writes the document at the read's own path, and
   nothing to the Ledger (decision C.2: the Ledger records Runs only).
8. When `routing["meters"]` is off, FRESH and FORCED read as CACHED. `routing=None` means
   no switch applies; it is used for a person's own `delegate status --refresh`, which
   routing.md says probes on request.
9. A Snapshot is never hashed. Its internal maps are `field(compare=False, hash=False)`
   (or the class is `eq=False`), so `hash(snapshot)` cannot raise. `Snapshot.of` reads a
   row's `cycle_left` into `Readout.week_left`, and fixtures keep that key.

**Error modes**
- `read` never raises for I/O, JSON, validation or probe failure. Any of these gives a
  Snapshot whose Meters are unknown, and `status` and `detail` say why. It catches at most
  `Exception`, never `BaseException`, so the Run's SIGTERM termination (C) passes through
  a probe.
- A probe that fails or takes longer than its single 180 s bound falls back to the last
  reading only when that reading is fresh enough; otherwise the status is `stale`.
- An unknown freshness string raises ValueError.
- `readout` of an unknown or None Meter returns an unknown Readout. A `spend` outside
  0..1 raises ValueError.
- `hold` and `release` raise OSError when the hold file cannot be written. The Run (C)
  catches it as a note and keeps its Outcome.

**What it hides**
- Path resolution: the explicit path, else `$DELEGATE_CACHE`, else `$CONSULT_CACHE`, else
  `~/.cache/delegate/usage.json`.
- Strict JSON parsing and validation: finite numbers, fractions in 0..1, the envelope
  timestamp. One bad row makes the whole document unknown.
- The legacy `lane` rows and the legacy bare map.
- Derived figures for rows that lack them, and note renames.
- The combined Window arithmetic: the lower Window, Pace from the week, the cycle floor,
  the 7-day week.
- The hold file and its expiry: the reset, 24 hours, or a reset that changed.
- The probe child process and its bound, and the 10-minute TTL.
- The Model meter's weekly rule.
- The plan price per week. `_WEEK_DAYS` and `_DAYS_PER_MONTH` are defined only here, as
  private constants.
- How the metering switch applies to probes and to the Gate.

The harness port changes shape. `harnesses/base.py` gains `Windows` (meter, group,
five_h, weekly, reset_5h, reset_weekly, note, weekly_model), `Harness.windows(group, ...)`,
`Harness.meter_name(group)`, and the probe helpers `run_cli` and `iso_time`. Adapters
return Windows, and `usage.py` builds the rows, so no adapter imports usage. This removes
the import cycle. The seam is real: five adapters plus `Snapshot.of` for fixture
documents.

**Dependency category.** Storage is local-substitutable: the cache and hold files sit
under an env-overridable path, and tests use temporary directories. Probes follow ports
and adapters at the harness seam. The probe child process is an internal seam; its bound
has one test that patches `usage.subprocess.run`, and test_usage counts probes there.

### Design it twice

**Shape A (chosen): the reading is joined to policy when a question is asked.** `read`
returns a Snapshot that knows nothing of the catalog, and `readout(meter, cat)` joins one
reading with a given catalog's Gate, metering switch, Model meter flag and plan price.

**Shape B: a board bound to one catalog.** `usage.board(cat, freshness, path) ->
Mapping[str, Readout]` returns Readouts that are already joined, so rank only needs
`board[meter].gated`, and `board.spent(meter, x)` answers the what-if.

How they compare:
- **Depth.** B has the smaller call surface: one call, then lookups. A asks for one more
  argument per question. Both hide the same implementation.
- **Locality.** B fails the callers that rank one reading under several catalogs.
  `catalog_edit.edit_catalog` ranks the before and after catalogs on one reading
  (`catalog_edit.py:845-847`), and the dashboard ranks staged catalogs against the cached
  reading. Under B each would build two boards, which means two reads of the cache. A
  probe can land between those reads, and the preview would then blame the edit for a
  Meter change.
- **Seam placement.** A puts the seam between the reading (probes, cache and holds: slow
  and stateful) and policy (the catalog, which changes with every staged edit). Those two
  vary independently, so that is the right place.

A third shape was also rejected: keep the 17-key row dict as the currency and add pure
helpers (`eligible(row, gate)`, `display(row, meter_def)`). Every caller would still need
to know to apply the hold, honour the metering switch and pick the Model meter's week,
and that is exactly today's drift.

### Callers migrated
- **rank.py**
  - `rank_range`, `rank` and `tier_leaders` take a Snapshot. `rank_range` first builds
    `readouts = {meter: snap.readout(meter, cat)}` and hands that map to a private
    ranking core, so E's what-if can replace one Readout and rerun the core without a
    second read. The core reads r, pace, `remaining_weekly`, `meter_status`, the gate
    veto, and the plan-dollars weight from `week_dollars`.
  - `main` reads FRESH for a Class and CACHED for `tiers` or `--meters`.
- **delegate.py**
  - `run` reads FRESH, or CACHED with `--meters` or `--no-probe`.
  - `dispatch` reads FRESH before the relay and FORCED after it, and reads nothing with
    `--no-probe`. Both reads sit inside the relayed work that `runs.execute` calls (C1),
    in this order: the preflight, `usage.read(routing, FRESH)`,
    `relay.run(job, run.path)`, `usage.read(routing, FORCED)`, return the Finish.
  - The Meter hold is one private function in `runs.py` (C1); it calls `hold` and
    `release`.
- **report.py**
  - `cmd_limits`: FRESH, or `read(None, FORCED)` with `--refresh`. It covers the table,
    plan consumption, `--eligible`, Meters with no probe row, and a new line for each
    held Meter.
  - `cmd_statusline`, `popup_meters`, `popup_lines` and `lane_lines` read Readouts.
    `handover` keeps its own loop until E4 moves it into rank on `readout(spend=)`.
- **catalog_edit.py**: the `meters` parameter is a Snapshot (default
  `read(None, CACHED)`), and `_observations_report` reads `status` and `names()`.
- **catalog.py**: the week constants and `week_dollars` move to usage.
- **evals.py**: `ping_lane`'s pick does `usage.read(cat['routing'], CACHED,
  path=sandbox.meters)` beside G2's `OfflineWorld`, and the Gate eval uses `Snapshot.of`.
- **model_queue.py**: `path()` uses `usage.cache_path()`.
- **Dashboard `model.py`**:
  - Reads `usage.read(None, CACHED, path=...)`.
  - Reports `status`, `detail` and `taken_at`.
  - Its watch compares `signature`, so a hold written or lifted beside the cache reloads
    the view.
  - Passes the Snapshot to rank and catalog_edit.
  - Each state row gains `gated` from the readout.
- **Dashboard `deck.py`**: `remaining_color` and `meter_verdict` read `gated`.
- **Harness adapters** (claude, codex, agy, grok) return Windows.
- **bin/delegate** is unchanged, and so is `report.py`'s statusline CLI (`statusline`,
  `--popup`, `toggle|on|off`), which the dotfiles statusline script, the Herdr popup and
  Hammerspoon call.

### Deleted
- **usage.py**: `get_cache_path` (replaced by `cache_path`), `CACHE`, `combined`,
  `row_meter`, `_upgraded`, `_filled`, `limits_path`, `read_limits`, `_write_limits`,
  `mark_limited`, `clear_limited`, `_limited`, `_fill_document`, `observations`,
  `eligible`, `load_cached`, `load_cache`, `write_cache`, `probe`, `acquire`, `run`,
  `remaining`, `meter_name`, `meter_row`, `iso`, and `TTL_MIN_DEFAULT` as public names,
  and the `events` import if C4 left it. The public names left are CACHED, FRESH,
  FORCED, MAX_PACE, read, hold, release, cache_path, Snapshot, Readout and main.
- **rank.py**: `meter_observations`, `run_usage`, `load_cached_usage`, `load_usage`.
- **report.py**: `usage_doc`, `CACHE`, `WEEK_DAYS`, `DAYS_PER_MONTH`, both `shares5`
  derivations, the swap to `remaining_weekly_model`, and the `left` recomputation.
  Handover's Remaining and Pace arithmetic goes with E4.
- **catalog.py**: `WEEK_DAYS`, `DAYS_PER_MONTH`, `week_dollars`.
- **delegate.py**: `probe_meters`, and the `probed` parameter of `run`, `dispatch` and
  the relayed work, with its comment.
- **The dashboard**: its own `DELEGATE_CACHE`/`CONSULT_CACHE` lookup, `_load_meters`,
  `_cached_meters_doc`, and deck's two `remaining < gate` comparisons.
- **Harness adapters**: every lazy `import usage`.
- **Tests**: `tests/test_usage_reset.py`.

### Tests

**New**
- `tests/test_usage.py`, all at the new interface:
  - A hold lives beside the document it overlays.
  - Validity, legacy rows and the bare map.
  - Figures derived from rows that carry only Windows.
  - Each Readout invariant above: the lower Window; equal-to-Gate passes; unknown never
    gated; metering off never gated; the Model meter's Weekly figure and
    `shares_five_h` from the flag or from the row; `week_dollars`; `spend`.
  - The freshness cases, counting probes through the internal seam that runs the probe
    child process, with no harness CLI on PATH.
  - A probe writes nothing to the Ledger.
  - The probe bound, through the internal seam.
  - `--pretty`.
  - An overspent Window, through `usage.main([...])` in-process with a patched adapter.
- `test_dashboard`: the hold and metering-off cases below.
- `test_report`: weekly agreement, the held line, and the statusline CLI (`statusline`,
  `statusline --popup`, `statusline toggle`) still exiting 0 with output.
- `test_dispatch` 34d.
- `test_harnesses`: Windows without usage.

**Replaced**
- `test_usage_reset.py`. Its eligible, observations, load_cached, load_cache, probe,
  acquire, meter_row and ticket-43 hold blocks become test_usage cases, and the claude
  reset parsing moves to test_harnesses.
- `test_rank`: "rank.meter_observations re-exports usage.observations",
  "load_cached_usage uses usage.get_cache_path", case 24 and case 25c are deleted;
  test_usage's freshness cases cover them.
- `test_dispatch`:
  - 34, 34b and 34c count probes with a logging agy stub on the offline world's PATH
    (G2's `world.stub`), which appends a line when called with `/usage`, instead of
    monkeypatching `usage.acquire`. The fake relay's `hold=` directive separates the
    probe before the relay from the one after it.
  - C's test_runs usage-limit case and C1's dispatch wiring case read the hold through
    `readout(...).held_until` instead of `limits.json` (test_dispatch 36 went with C1).
- `test_report`: "statusline fable shows remaining_weekly_model" becomes "statusline
  fable shows its Weekly figure" (46%·4d), and the popup legend check reads "weekly
  figure".
- `test_harnesses` and `test_catalog` 18 read Windows fields instead of row dicts.
- The about 93 rank calls in test_rank, test_catalog, test_evals and test_dashboard that
  pass documents wrap them with `usage.Snapshot.of`.

### Live bugs fixed and the proving tests

Each test fails on the code before its ticket first, then passes.
1. **The hold is skipped on the dashboard path.**
   `test_dashboard.test_a_held_meter_is_vetoed_and_its_release_reloads`.
   - Fixture: ProjectFixture's `usage.json` with grok at r 0.9, plus
     `usage.hold("grok", ..., path=self.meters)`.
   - Expected: Tier 4's leader is None and grok46-high@grok reads 0% with `vetoed:gate`.
     After `usage.release(...)`, `refresh_if_changed()` is True and the lane leads again
     at 90%.
2. **`cache_path` is half-honoured.** test_usage "a hold lives beside the document it
   overlays".
   - Fixture: temporary directories A, B and C, each with a `usage.json` holding codex
     (A's weekly reset is an hour away, B's and C's two hours), and `DELEGATE_CACHE`
     pointing at C.
   - Expected: `hold(path=A)` ends at A's reset, A alone reads 0%, and `release(path=A)`
     lifts it.
   - The same fixture through today's `usage.load_cached(A)` shows codex unheld (checked
     in the review).
3. **The statusline and the popup disagree on a Model meter.** test_report "statusline
   and popup print one weekly figure per Meter".
   - Fixture: `pp_usage.json`, where claude-fable has `remaining_weekly` 0.46 and
     `remaining_weekly_model` 0.59.
   - Expected: for every Meter, the statusline percentage equals the popup's `= W ÷ L`
     numerator. Today that is 59% against 46%.
4. **`delegate status` does not note a hold, though routing.md says it does.**
   test_report "status names a held Meter and when its hold ends".
   - Fixture: a fresh cache plus `usage.hold("grok", ...)` beside it.
5. **The deck draws "under the Gate" with metering off.**
   `test_dashboard.test_meters_off_draws_no_meter_under_the_gate`.
   - Fixture: routing `meters` false and codex-a at 5%.
   - Expected: `deck.meter_verdict` does not say "under the Gate".
6. **`run --no-probe` still probes in order to rank.** This was noted in any-harness
   ticket 05. test_dispatch 34d "run --no-probe --dry-run writes no cache and starts no
   probe".
   - Fixture: the offline world with the logging agy stub, no cache.
7. **`usage.py --pretty` raises `KeyError: 'lane'`.** test_usage "usage.py --pretty
   prints one line per Meter".
   - Fixture: a fresh cache with rows in the current shape, run with
     `--max-age-min 60`, so no probe happens.
8. **The harnesses and usage import each other.** test_harnesses "a probe hands back
   Windows without importing usage".
   - Fixture: a fake `agy` CLI on PATH that prints the two-group `/usage` JSON.
   - Run in a subprocess. Expected: `Windows` named agy-gemini and agy-claude-gpt, and
     `usage` absent from `sys.modules`.

### ADR notes

This stays within ADR 0001:
- Routing reads the Meters as they are when a job is sent. FRESH's 10-minute window is
  unchanged, and there is no history and no burn rate: no probe writes a meter event,
  the hold is ticket 43's existing state, and `signature` only detects change.
- Routing stays plan-agnostic. `week_dollars` feeds only the opt-in `plan_dollars`, and
  `quota_unit` keeps its `pace` default.
- No model name is coded. A Model meter is known by the catalog flag or the probe row.

The Model meter's Weekly figure (decision B.1) reverses one acceptance box of redesign
ticket 23 ("The fable row shows remaining_weekly_model"). Once the user confirms it, its
line goes into the one ADR change made after all lanes merge.

### Risks
- **The Model meter row loses the model's own figure.** The statusline row for a Model
  meter now shows the lower week, for example 46% where it showed 59%. The model's own
  week remains in `delegate status --json` and in the Meter's note.
- **Behaviour changes:**
  - A named dispatch with a reading younger than ten minutes no longer probes before its
    relay.
  - `delegate rank`'s probe bound grows from 90 s to 180 s.
  - `--meters FILE` now honours a `limits.json` beside FILE. The repo's fixtures have
    none.
- **Overlap with other lanes.** run-and-relay merges first: B1 swaps `runs.py`'s one
  private hold function to `hold` and `release`, and B3 puts its reads inside the relayed
  work around `relay.run`. B2 builds the popup's Meter rows from Readouts and leaves the
  handover to E4. B1 changes `catalog_edit`'s read side (the `meters` parameter and
  `_observations_report`) and B4 changes `model_queue.path()`; D owns `catalog_edit`'s
  writes and the scan, and the regions do not overlap.
- **Test churn.** Wrapping the documents in about 93 rank test calls is mechanical but
  wide.
- **Dashboard cost.** The dashboard watch now parses the small cache JSON on each pass.

## C. Run lifecycle

A started Run always finishes.

Tickets: 01 (C1), 02 (C2), 03 (C3), 04 (C4). Lane: run-and-relay, before G.

### Problem

A Run has three records. The run directory holds `dispatch.json` and `return.json`. The
Ledger holds a start line and a finish line, which the statusline reads. The finish line,
or the `--json` object, is what the orchestrator reads. Three modules write these
records: `runs.py`, `events.py` (called from `delegate.py`), and `delegate.py` itself.
Nothing in any module keeps them consistent. Only the statement order in
`delegate.dispatch()` (`delegate.py:661-774`) does that: create, native exit, ledger
start, try relay and map / except `fail_run`, `note_usage_limit`, ledger finish, print
and `sys.exit`. Each past fix (7f7d020, 4ec88b5, 905a0ab, d560945) went into that order
and not into a module.

The order still has gaps. A Ledger that cannot be written leaves a Run started and never
ended. So does a `return.json` that cannot be written, and so does a SIGTERM. A Run on a
Native lane never gets an outcome at all. The statusline keeps its own parser of the
Ledger format (`report.py:632-665`). The tests reach the invariant only through `main()`,
using `python -c` monkeypatch strings.

### Chosen interface

The Run module runs a Run from its start to its Outcome. The caller supplies only the
work. Python 3.9: `typing.NamedTuple` with defaults and `typing.Optional`; no runtime
PEP 604 unions.

```python
# agents/skills/delegate/scripts/runs.py
from typing import Callable, List, NamedTuple, Optional, Tuple, Union

class Request(NamedTuple):
    """What dispatch asks for: the request half of dispatch.json."""
    lane: str
    harness: str
    model: str
    effort: str
    timeout: str                     # the Lane's timeout, ^[0-9]+[smh]$ (catalog check holds it)
    class_name: Optional[str]
    cwd: str
    write: Optional[str]
    brief: str
    leash: bool = True
    orchestrator: Optional[str] = None
    meter: Optional[str] = None      # the Lane's Meter; the Outcome holds or releases it (not recorded)

class Finish(NamedTuple):
    """How relayed work ended, normalized. The one type for it: G's Relay.run returns it.
    Every field except `returned` is a DISPATCH_FIELDS outcome key."""
    returned: dict                   # the five RETURN_FIELDS
    relay_status: Optional[str] = None
    relay_exit: Optional[int] = None
    secs: Optional[int] = None       # None: the Run records how long the work took
    reason: Optional[str] = None
    session_id: Optional[str] = None
    usage: Optional[dict] = None     # G4 renames it `tokens`, here and in DISPATCH_FIELDS
    touched_files: Optional[list] = None
    read_only_violation: Optional[bool] = None

def blocked(reason: str, secs: Optional[int] = None) -> Finish
    """A Run that did no work: status blocked, deliverable 'blocked: <reason>'."""

class HandOff(NamedTuple):
    agent: str                       # the orchestrator's agent that runs the Lane
    spawn: str                       # the profile's spawn instruction

class Run:
    """A handle on one run directory: path, prompt_path, return_path, read()."""

class Ended:
    run: str                         # the run directory
    lane: str
    status: str                      # done | partial | blocked | native
    exit_code: int                   # 0 for done, partial and native; else 1
    notes: Tuple[str, ...]           # one line each for stderr
    def text(self, as_json: bool = False) -> str   # what dispatch prints on stdout

class StartError(Exception):
    """The run directory could not be made. Nothing started."""

def execute(request: Request, prompt: bytes,
            work: Callable[[Run], Union[Finish, HandOff]],
            runs_dir: Optional[str] = None) -> Ended

class Running(NamedTuple):
    lane: str
    run: Optional[str]
    started: float
    deadline: float

def running(now: Optional[float] = None) -> List[Running]

def root(runs_dir: Optional[str] = None) -> str           # unchanged
def parse_finish_line(text: str) -> Optional[dict]        # unchanged
def parse_native_line(text: str) -> Optional[dict]        # unchanged
DISPATCH_FIELDS, RETURN_FIELDS                            # unchanged record contracts (G4 renames usage)
```

Invariants of `execute`:

1. It either raises `StartError` before the Ledger has a start, or it returns an `Ended`.
   It never raises after the start. Anything that stops `work` becomes `blocked(...)` with
   one of these reasons:
   - any `Exception`: `dispatch failed: <Type>: <message>`
   - `KeyboardInterrupt`: `dispatch interrupted`
   - SIGTERM: `dispatch terminated (SIGTERM)`
   - any other `BaseException`: the `dispatch failed` form.
2. The writes happen in this order:
   - before the work: the run directory, `prompt.md` (the bytes verbatim),
     `dispatch.json` with the request and a null outcome, and the Ledger start;
   - after the work: `return.json` (relayed only), the outcome in `dispatch.json`, the
     Meter settle, and the Ledger finish.

   Every write after the start is attempted even when an earlier one failed. A failed
   write becomes a note. When `return.json` fails, the recorded status becomes blocked,
   with reason `could not write return.json: ...`. The worker's answer stays in
   `result.json` and `final.txt`.
3. The Outcome comes from the work's result:
   - a `Finish` records the return's status;
   - a `HandOff` records `native`, with reason `handed to <agent>`, secs null and no
     `return.json`.

   A `Finish` whose return lacks a field ends blocked.
4. The Meter settle happens exactly once and never raises:
   - A blocked Outcome whose reason or deliverable carries the harness's `usage_limit`
     words holds the Meter. Its note reads `<meter> meter held at 0% left until <stamp>:
     <line>`.
   - A done or partial Outcome releases the Meter.
   - A `HandOff` or any other blocked Outcome leaves the Meter untouched.

   The settle is one private function in `runs.py`. It calls `usage.mark_limited` and
   `clear_limited`; B1 swaps that one function to `usage.hold` and `usage.release`.
5. The SIGTERM handler is installed only while `work` runs, and only on the main thread.
   Afterwards the previous handler is restored. The handler raises a private subclass of
   `BaseException`, as `KeyboardInterrupt` is, so no `except Exception` inside the work
   (G's relay adapter, B's Meter read) can swallow it. Because `subprocess.run` kills its
   child on any exception, the relay stops with the Run.
6. `text()` is byte-identical to today's output:
   - a relayed Run prints `delegate: <lane> status=<s> secs=<n> run=<dir>`, then
     `delegate-metrics: thread=<t> status=<s> class=<c or -> secs=<n> rc=<rc or None>`;
   - a native Run prints `delegate: native lane=... agent=... prompt=...`, then
     `delegate: spawn: ...`;
   - `as_json` gives the same summary and native objects, with `indent=2`;
   - the exit codes are unchanged.

Invariants of `running`: a Run is running when all four hold:
- the Ledger has its start;
- the Ledger has no finish for it;
- its `dispatch.json` has no `finished_at`;
- now is within its start plus its timeout.

It reads lines that any earlier delegate wrote (v1). It skips lines that are not JSON
objects. It never raises: a Ledger that cannot be read means no running Runs.

What the module hides:
- the run directory's name and the thread id;
- the field order of `dispatch.json` and the five fields of `return.json`;
- the Ledger's path (`$DELEGATE_LEDGER`), its v1 line format, and timeout parsing;
- the mapping from exceptions to reasons, and the SIGTERM conversion;
- the order of the writes and what happens when one fails;
- the Meter hold and the harness's words for it;
- the spelling of the finish, metrics and native lines, and of the `--json` objects;
- how starts and finishes are paired, and the cross-check against `dispatch.json`.

Deletion test: delete `execute`, and every caller has to repeat the create → ledger → try
→ fail → hold → ledger → print order. Delete `running`, and the statusline needs its own
Ledger parser again.

### Considered alternative: a handle with terminal verbs

```python
with runs.start(request, prompt) as run:   # dir, prompt, dispatch.json, Ledger start
    if native: run.hand_off(agent, spawn)
    else: run.finish(finish)                # or run.fail(reason)
ended = run.ended   # __exit__ ends an unended Run blocked and swallows the exception
```

The two designs compare as follows:

- **Depth.** The chosen shape has one entry point and no ordering rule. The handle adds
  three verbs and three rules: exactly one terminal call, a block that swallows
  exceptions, and `ended` read after the block. Each rule is a way to get the order
  wrong, and every bug in this history was an ordering bug.
- **Locality.** Both designs put the writes in `runs.py`. With the handle, the caller
  still decides which verb to call and when, so the exception mapping drifts back into
  `delegate.py`.
- **Seam.** The chosen `work` callable is a real seam. It has three adapters today (the
  relay work, the hand-off, the tests' fakes), and G's Relay adapter becomes the fourth.
  The handle has no seam: a test writes code inside a `with` block.

The handle's one advantage is linear caller code. That is not worth a context manager
that swallows exceptions, which Python readers do not expect.

### Callers migrated

- `delegate.dispatch` builds a `Request` and picks the work, then calls `execute` once.
  It prints the notes (`delegate: <note>`) to stderr and `text(as_json)` to stdout, then
  exits with `exit_code`. A `StartError` prints one line and exits 2.
  - **Relayed work** is today's `relay_and_map`, with two changes. A preflight reason
    returns `blocked(reason)`. A `FileNotFoundError` for `node` returns
    `blocked("node is not on PATH; the relay needs Node.js")`. It still calls
    `run_relay` by that name, so test 34c keeps working until B3 rewrites it. G1 then
    moves the relay behind `relays.Ads`, and the work ends with
    `return relay.run(job, run.path)`.
  - **Native work** is
    `lambda run: HandOff(agent_name(profile, lane), spawn_line(profile, lane, run.prompt_path))`.
- `delegate.map_result` returns a `Finish` and writes nothing. That moves it toward G's
  pure settling.
- `report.cmd_statusline` counts `Counter(r.lane for r in runs.running(now))`.
- `usage.write_cache` stops writing to the Ledger (C4).
- These readers keep working unchanged:
  - `courier.md` (the finish JSON, `"native": true`);
  - `SKILL.md` (the finish line, `return.json`);
  - `evals.py` (`Run(path).read()`, `parse_native_line`, `RUN_FILES`);
  - `browser_probes.py` (`parse_finish_line`, `return.json`);
  - council, through the `delegate` command;
  - the statusline CLI (`report.py statusline`, `--popup`, `toggle|on|off`), which the
    dotfiles statusline script, the Herdr popup and Hammerspoon call.
- One reader changes. `report.py log --run` on a native Run now reads status `native`. It
  used to read null and default to `done`. Secs stay null, so it still asks for `--secs`,
  as SKILL.md step 4 says.

### Deleted

- From `delegate.py`: `ledger_start`, `ledger_finish`, `fail_run`, `start_failure`,
  `note_usage_limit`, `print_and_exit`, `Preflight`, `relay_and_map` (it becomes the
  work) and `import events`. `parse_timeout_s` moves into `runs.py` as a private
  function.
- From the public surface of `runs.py`: `Run.create`, `Run.finish`, `Run.fail`,
  `Run.thread_id`, `finish_line`, `native_line`, `summary` and `native_summary`. They
  become private, or move inside `execute` and `Ended`.
- `events.py` (109 lines, with its CLI) and `tests/test_events.py` (241 lines).
- `report.py:632-665`, the statusline's Ledger parser.
- In `usage.py`: the `events` import and the meter event appended in `write_cache`.

### Tests

New tests in `test_runs.py` run in-process. Each uses a temp run root, a temp
`$DELEGATE_LEDGER` and a temp `$DELEGATE_CACHE`, with no `python -c` and no
monkeypatching:

1. A Run that returns ends with that return in every record: the five fields, the
   outcome and its key order, the session under both names, the Ledger start and finish
   with one thread and `timeout_s`, the exact finish and metrics lines, and exit 0. G4's
   rename of `usage` to `tokens` updates the key order here.
2. Work that raises (`RuntimeError`, `KeyboardInterrupt`) ends the Run blocked with why.
   `rc` is `None`, and secs are measured by the Run.
3. SIGTERM during work ends the Run blocked as terminated, and the previous handler comes
   back.
4. A `return.json` that cannot be written still ends `dispatch.json` and the Ledger.
5. A Ledger that cannot be written never stops a Run ending.
6. A usage-limit refusal holds the Lane's Meter. A done or partial Run releases it. A
   timeout leaves it alone. Another harness's Meter is never held by the grok wording.
7. A runs root that cannot be made starts nothing.
8. A hand-off ends the Run at once as native.
9. `running` lists a Run while its work runs, and not after.
10. A start past its timeout is not running (`now` injected). Neither is a start whose
    `dispatch.json` has ended.
11. `running` reads a Ledger that an earlier delegate wrote, and skips lines that are not
    objects.
12. The Ledger lines keep their v1 keys, in order.
13. No script but `runs.py` names `DELEGATE_LEDGER` or writes `dispatch.json` or
    `return.json`.

The parse cases (today's 6 and 7) build their lines from `Ended.text`. Case 8 (`root`)
stays.

New tests in other files:
- **test_dispatch 12i.** A dispatch terminated by SIGTERM still ends its Run and stops
  its relay.
- **test_dispatch "a relayed Run refused for its usage limit holds that Lane's Meter".**
  A grok lane whose fake relay fails with grok's usage-limit words; afterwards
  `limits.json` beside `$DELEGATE_CACHE` holds `grok` (after B1,
  `usage.read(None, usage.CACHED).readout("grok", None).held_until` is set). test_runs 6
  proves that `execute` settles the hold; this case proves that dispatch hands the
  Lane's meter to it. It must fail when the Request leaves `meter` out.
- **test_dispatch 12e, rewritten in-process.** Delegate's relay work names `node` when
  `node` is gone after the check. The test calls the work with `PATH` lacking node. G1
  later moves this case to test_relay as Ads node-missing.
- **test_dispatch 29.** It also asserts the native outcome.
- **test_report.** The statusline shows a Run's glyph while the Run runs and none after.
  The statusline is run from inside the work. `statusline`, `statusline --popup` and
  `statusline toggle` still exit 0 with output.
- **test_report.** A Ledger line that is not an object never blanks the statusline.

Tests these replace:
- test_runs 1-5, which drove `create`, `finish`, `fail` and `summary`;
- test_dispatch 11 (the Ledger through the CLI);
- 12e and 12f (`python -c` strings);
- 36 (`note_usage_limit` called directly);
- test_report's hand-written running, stale and finished glyph checks;
- test_dispatch 28a-28c, which now assert on the `Finish` that `map_result` returns, not
  on the files it used to write.

Tests deleted outright:
- `test_events.py`;
- test_usage_reset's meter-event Ledger assertions. C4 adds nothing to
  `test_usage_reset.py`, which B4 deletes; B3 adds "a probe writes nothing to the Ledger"
  to test_usage.

These stay as the end-to-end contract and pass unchanged: test_dispatch 1-10b, 12, 12d,
12g, 12h, 13-27c, 29a-29d and 30-33. Cases 34-34c belong to B.

### Live bugs fixed

Each proving test fails on the code before its ticket and passes after the change.

1. **A Ledger write that fails leaves a started Run unended.** `delegate.py:725` calls
   `ledger_start` outside the `try`, and `events.append` raises. The Run keeps a null
   outcome, gets no `return.json`, prints no finish line, and exits with a traceback. At
   `:753` the same failure hits a done Run: `return.json` is written, but the finish line
   is never printed, so the courier finds an empty JSON file.
   - Proof: test_runs 5.
   - Fixture: `$DELEGATE_LEDGER=<tmp>/blocker/ledger.jsonl`, where `blocker` is a regular
     file, plus a work that swaps the Ledger for a directory mid-run.
2. **A `return.json` that cannot be written leaves the outcome in `dispatch.json` null.**
   `runs.py:155-158` returns before it updates `dispatch.json`. Today's 12f checks only
   the Ledger.
   - Proof: test_runs 4.
   - Fixture: a work that makes `return.json` a directory and returns a done `Finish`. It
     asserts status blocked, a reason naming `return.json`, and `finished_at` set.
3. **SIGTERM kills dispatch between the Ledger start and the finish.** The claude
   profile's launch note says `claude -p` SIGTERMs a background job at the end of its
   turn. Today the node relay is orphaned and keeps spending the Meter. The glyph stays up
   to the Lane's timeout (1500 s for the sample's `terra-high@codex`), and
   `dispatch.json` stays null.
   - Proof: test_runs 3, where the work signals its own pid.
   - Proof: test_dispatch 12i. Fixture: a fake relay brief with `hold=<tmp>/never`,
     started with `Popen`, sent SIGTERM once the start is in the Ledger. It asserts exit
     1, a blocked `dispatch.json`, a Ledger finish, and no `result.json` after the hold
     file is created.
4. **A native Run's outcome stays null forever.**
   - Proof: test_dispatch 29 asserts status `native` and `finished_at`. test_runs 8 also
     covers it.
5. **One Ledger line that is valid JSON but not an object blanks every Meter row of the
   statusline.** `report.py:634-665` wraps the parser in `except Exception: return`,
   which returns before anything is printed.
   - Proof: test_report "a Ledger line that is not an object never blanks the
     statusline". Fixture: a Ledger holding `[1]` and one open start.
   - Proof: test_runs 11.

Dispatch already settles the Meter hold today, but no test proves that it does. With this
design the hold lives inside `execute`, so no caller can skip it, and the dispatch wiring
case proves that dispatch passes the Lane's meter.

### ADR notes

The design stays inside ADR 0001. It adds no history and no burn rate, and it hardcodes
no lanes or models. Dropping the Ledger's meter events (decision C.2) agrees with the rule
that routing reads Meters as they are and keeps no usage history. If the user confirms
it, its line ("the Ledger records Runs only; the latest Meter reading lives in the usage
cache") goes into the one ADR change made after all lanes merge.

### Risks

- **The harness CLI may outlive the relay.** `subprocess.run` kills node, and a harness
  CLI that the relay started may survive it. A process-group kill belongs in G's Ads
  adapter.
- **Some deaths still leave a start without an Outcome.** SIGKILL, an interpreter crash,
  or a power loss do. `running` bounds such a Run by the Lane's timeout, as today.
- **Signal handlers need the main thread.** A Run in another thread is guarded against
  exceptions only.
- **The after-probe still runs inside the work, because B owns probes.** A SIGTERM during
  it ends the Run blocked even though the relay finished; `result.json` and `final.txt`
  keep the answer.
- **Cross-candidate order.**
  - C1's private hold function calls `usage.mark_limited` and `clear_limited`.
    run-and-relay merges first, so B1 moves that one function to `hold` and `release`.
  - G builds after all of C in this lane, and its `Relay.run` returns `runs.Finish` into
    the work `execute` calls.
  - C4 removes `usage.py`'s `events` import and its meter event. B3 rewrites `usage.py`
    later and keeps it free of the Ledger.
- **The Ledger is still read whole on every statusline refresh and never rotated.** This
  design leaves that as it is.

## D. Catalog commit

One save owns every guarantee.

Tickets: 09 (D1), 10 (D2), 11 (D3), 12 (D4). Lane: catalog-write, before F.

### Problem

Five paths write catalog documents, and each one makes its own guarantees. The full
wizard save (`setup.py:755-777`) and the `--plain` save (`confirm_and_write`,
`setup.py:580-600`) validate and then write with `catalog.write_json`. They do not check
whether the files changed since launch, and they replace a link with a plain file. The
focused screen (`write_focused`, `:603-618`) and `catalog set` (`catalog_edit.py:870-879`)
recheck a revision and write through links. The dispatch-time model swap
(`model_queue._write_applied`, `model_queue.py:194-209`) compares raw bytes, makes its own
backup, imports the private `catalog_edit._write_preserving_link`, and imports `setup`
(which pulls in `setup_tui`, `bench`, `bench_page` and `effort`) to write agent files from
a plan it makes up. Agent files follow whichever plan dict the caller threads through,
and the model queue is emptied wholesale.

Each of these was run against temp copies of `b268352`, and each one happened:

1. A `catalog set` made while the wizard is open is lost. The set wrote tier 1 for
   `terra-high@codex`, the wizard then saved tier 2, and the wizard exited 0. A
   dispatch-time model swap is reverted by the same code path.
2. A model that dispatch notes while the wizard is open is removed from the queue unseen,
   because the save calls `model_queue.clear()`.
3. On a catalog whose `lanes.json` is a link, the full save replaces the link with a
   plain file.
4. On a focused screen (`--screen tier3`), a one-Lane toggle writes a generation refresh
   that the screen never showed: 20 Lanes added and 17 removed, with no agent files and
   the queue left untouched. `main()` calls `propose_generation` for focused screens too,
   and the focused Wizard's `_original_lanes` is the refreshed document.
5. `catalog set --scope project` follows a dangling `.delegate/routing.json` link and
   creates the missing target outside the project.

### Chosen interface

```python
# agents/skills/delegate/scripts/catalog_commit.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

DOCUMENTS = ("lanes", "routing", "project", "project_lanes")

class CatalogChanged(catalog.CatalogError):
    """An Intervening edit: a document the read saw differs on disk."""
    changed: Tuple[str, ...]   # names from DOCUMENTS, in that order

@dataclass(frozen=True)
class CatalogRead:
    lanes: Optional[dict]          # None when lanes.json is absent (a first run)
    routing: Optional[dict]
    project: Optional[dict]        # None when absent, or when no project was read
    project_lanes: Optional[dict]
    files: Mapping[str, Optional[str]]     # each document's path as named
    sources: Mapping[str, Optional[dict]]  # {file, resolved, symlink, exists}, as previews print them
    git_root: Optional[str]
    revision: str                  # one sha256 over every document read: path, resolved path, link, presence, bytes
    queued: Tuple[dict, ...] = ()  # models dispatch noticed, only when read with queue=True
    applied: Tuple[dict, ...] = () # Model swaps the scan applied, only when read with queue=True
    # privately: the bytes read for each document, and the config dir

def read(config_dir: Optional[str] = None, *, project_dir: Optional[str] = None,
         queue: bool = False) -> CatalogRead: ...

@dataclass(frozen=True)
class Committed:
    written: Tuple[str, ...]   # paths of the documents written, in DOCUMENTS order; () when none changed
    lines: Tuple[str, ...]     # one line per agent file written, updated or removed, and each note

def commit(read: CatalogRead, documents: Mapping[str, dict]) -> Committed: ...
```

Invariants of `read`:

- `read` always reads the global pair from `config_dir`, which defaults to
  `catalog.CONFIG_DIR`.
- It reads the project pair (`<git root>/.delegate/routing.json` and `lanes.json`) only
  when `project_dir` is given and a Git root is found above it.
- An absent document reads as `None`. Every document that is present must be strict JSON
  and pass the existing validators. Project documents are validated against the globals.
- A link at a document's path is followed to an existing file. A dangling link or a link
  loop raises `CatalogError`, and the message names the link and its target. On Python
  3.9 a dangling link is one where `os.path.lexists` holds and `os.path.exists` does not,
  and a loop is `os.stat` raising `OSError` with `ELOOP`; `os.path.realpath(strict=True)`
  is 3.10 and is not used.
- `queue=True` also reads the Model queue. A queue that cannot be read counts as empty.
- The dicts on a `CatalogRead` belong to the caller and may be changed. The commit
  compares against the bytes it read, never against those dicts.

Invariants of `commit`. `documents` maps names from `DOCUMENTS` to whole documents to
write. A name that is left out keeps its file, and a project name needs a read that found
a Git root. The commit runs these steps in this order:

1. **Validate.** It validates every document it will write together with the as-read
   ones, using the read-side validators, so it is no stricter than today. A failure
   raises `CatalogError` and nothing is written.
2. **Check for an Intervening edit.** Every document the read saw is described again:
   bytes, link, resolved path and presence. Any difference raises `CatalogChanged` and
   nothing is written.
3. **Skip unchanged documents.** A document equal to its as-read value is not written, so
   it keeps its bytes and mtime.
4. **Back up.** Before a global document is replaced, its read bytes are copied to
   `<config dir>/backups/<name>-<UTC stamp>.json`, stamped with `datetime.timezone.utc`.
   The newest 20 backups are kept per document. Project documents are not backed up.
5. **Write.** Each changed document is written atomically where its path resolves,
   through a link to an existing file, and the link stays.
6. **Roll back on failure.** If a later write fails, the documents this commit already
   wrote are restored from the read bytes, and a `CatalogError` names both the failure
   and what was restored.
7. **Sync agent files.** This step runs only when `documents` includes the global `lanes`
   document of the live catalog, meaning the config dir resolves to
   `catalog.CONFIG_DIR`. A commit of project documents alone, such as the dashboard's
   project-scope `catalog set`, never touches `~/.claude/agents`. For each orchestrator
   profile with native Lanes, every Lane in the catalog after the commit gets an Agent
   file: a plain file in the template's current text. Every native Lane that was in the
   read but is not in the result loses its file. A link at a Lane's path is replaced,
   never written through. A catalog that is not the live one gets one note line instead.
8. **Forget the queue entries the read returned.** Entries added since the read stay. A
   failure in step 7 or 8 becomes a note line, never an error, because the catalog is
   already written.

Callers print `Committed.lines` to stderr, so `catalog set`'s JSON stdout stays
byte-identical.

What the module hides: the source description and revision hash; strict JSON; document
validation; the recheck; the link rule and the dangling-link refusal; atomic writes;
backups and pruning; rollback; the live-catalog rule; profile agents directories and
templates; the queue file format.

Two limits remain. This is not a filesystem lock, so a writer outside delegate can still
race the final rename, as it can today. After a commit that wrote something, a second
commit with the same read raises `CatalogChanged`.

Usage:

```python
# the wizard (setup.main, start screen and --plain)
snap = catalog_commit.read(config_dir, queue=True)
...  # the session
done = catalog_commit.commit(snap, {"lanes": result_lanes, "routing": result_routing})

# the dispatch scan (model_queue.scan)
snap = catalog_commit.read(base)
doc, swaps = apply_successors(snap.lanes, refreshed, plan)
catalog_commit.commit(snap, {"lanes": doc})   # CatalogChanged: a wizard or catalog set in between wins

# catalog set (catalog_edit.edit_catalog --apply)
snap = catalog_commit.read(config_dir, project_dir=cwd or os.getcwd())
catalog_commit.commit(snap, {dest: planned[dest]})  # CatalogChanged becomes the existing "intervening edit: ... preview again"
```

The dependency category is local-substitutable. Tests use a temp config dir, a temp
`HOME` (for `~/.config/delegate` and `~/.claude/agents`) and `DELEGATE_MODEL_QUEUE`. There
is no port, because the filesystem is the only adapter. `catalog_commit` imports
`catalog`, `harnesses`, `orchestrators` and `model_queue`. It never imports `rank`,
`catalog_edit`, `setup` or `discover`. `model_queue.scan` imports `catalog_commit` inside
the function, as it already does for `catalog` and `discover`, which keeps dispatch's
import light.

The deletion test: deleting `catalog_commit` would push validation, the recheck, the link
rule, backup, agent files and the queue back into four callers. That is today's bug
surface, so the module earns its keep.

### Design it twice

**Shape 1, read then commit (chosen).** The interface is two functions, two frozen value
types and one error. A read can outlive a call, which every caller needs:

- the wizard holds its read through a session that lasts minutes;
- `catalog set` previews and applies in two processes joined by the `--expect` revision;
- the dashboard pins documents when it stages a change.

The seam sits at the filesystem.

**Shape 2, `update(config_dir, change, *, project_dir=None, attempts=3) -> Committed`.**
This shape runs `change(documents) -> documents` between a read and a check-then-write,
and retries on a conflict. Per call it is deeper for the scan and for `catalog set`,
whose changes are pure (`apply_successors`, `plan_edits`), and it narrows the race window
to the time `change` takes. It cannot serve the other callers:

- The wizard's change is a human session. Replaying it onto a newer catalog would place
  Lanes the human never screened, and ADR 0001 says Tiers are what the user sets.
- The two-process `--expect` contract needs a token that outlives a call.

Shape 2 would therefore need Shape 1 underneath it: two interfaces where one does the
job.

**A stateful `CatalogSession.open().save()`** offers the same guarantees as Shape 1 plus
lifecycle states (open, saved, stale) to learn, and adds no leverage.

Shape 1 wins on depth, because one small interface serves all five paths. It wins on
locality, because every write guarantee is in one file. Its seam is at the one place
every path already touches.

### The link rule

**Catalog documents** (`lanes.json`, `routing.json` and a project's `.delegate` pair) are
written through a link to an existing file, and the link stays. A dangling link or a loop
is refused at read and at commit, so its target is never created. `catalog.write_json`
carries this rule, which means `delegate catalog fmt` follows it too, and
`_write_preserving_link` goes away. The evidence:

- Since 36f09b1 (2026-09-29, ADR 0001's machine-local ruling), nothing installs a link in
  `~/.config/delegate`. That commit removed `stow/delegate`, and delegate's `Makefile`
  links nothing there. A link there is the user's own placement of a machine-local file.
- Redesign ticket 22 recorded link replacement as a bug: "The fix is to resolve the path
  with realpath before writing".
- Three of the five paths already write through, and `references/catalog.md` says "Apply
  preserves stow links".
- Bug 5 above shows why a dangling link must be refused rather than followed.

**Agent files** follow a different rule: a link at a Lane's path is always replaced with a
plain file and never written through. `~/.claude/agents` is an install target that holds
links into repositories. The dotfiles repo stows its agents package there per file, and
delegate's `make install` links the courier there. A link at a Lane's path is therefore a
repository's file. Writing through it would put a machine-local Lane agent into a public
repository, which 36f09b1 added the replacement to prevent (pinned by
`case_the_real_layout_saves_the_agent_files`).

The dashboard's own refusal of any link inside its pinned project is a rule about where
the pinned project may write. It stays in the dashboard, unchanged.

### Callers migrated

- **The wizard's full TUI save and `--plain` save.** Both read at launch with
  `queue=True`. The sample proposal stays for a first run. Both commit at the end. On
  `CatalogChanged` the wizard names the changed document, writes nothing and exits 1.
  Ticket D1 moves the documents; ticket D2 moves the agent files and the queue. F1 later
  hands the commit `draft.documents()` from `confirm_and_write(draft, read)`.
- **The start page and `--plain`.** They name the read's queue whether or not the refresh
  ran, and `propose_generation` stops reading `model_queue` (D2).
- **The dispatch scan.** It reads and commits, and it imports neither `setup` nor
  `catalog_edit`. D1 removes the private link writer; D2 removes the rest.
- **The focused screen.** D1 takes its revision from the launch `CatalogRead`'s
  `.revision` instead of `catalog_edit.catalog_revision`, which D1 deletes, and keeps
  `write_focused` until D3. D3 owns the focused screen's start: it proposes no generation
  and commits a read taken without the queue. A focused commit passes only the documents
  whose content the screen changed: setup applies `catalog.with_default_classes` to the
  routing it shows, and committing that routing would write a file the confirm page never
  listed.
- **`catalog_edit.edit_catalog`.** Its preview and apply read through `read()` (D1), and
  its apply commits (D4). The dashboard is unchanged in code, because it calls
  `edit_catalog`, and a project-scope set never syncs Agent files.

### Deleted

| Module | Deleted | Ticket |
|---|---|---|
| `setup.py` | `write_focused`, `focused_revision` | D3 |
| `setup.py` | `clear_queue`, `native_agent_text`, `native_agents_dir`, `native_targets`, `save_native_agents`, `save_all_native_agents`; `wizard.refresh` as an input to any writer | D2 |
| `setup.py` | the `write_json` import; `load_or_propose`'s file reading; `catalog_edit.catalog_revision` for the focused revision | D1 |
| `catalog_edit.py` | `_write_preserving_link`, `_describe_source`, `_source_public`, `_hash_source`, `_source_snapshot`, `catalog_revision`, `_loads_strict`, `_load_docs_from_snapshot` (moved into `read`) | D1 |
| `catalog_edit.py` | `edit_catalog`'s second recheck and its direct write | D4 |
| `model_queue.py` | `_backup`, `_write_applied`, `clear`, the made-up `{"new", "removed"}` plan, and the imports of `setup` and `catalog_edit` | D1, D2 |
| `discover.py` | `model_takes_effort`, whose only caller was `setup.native_agent_text` | D2 |

### Tests

**New file `tests/test_catalog_commit.py`.** Fixtures: a temp config dir copied from
`assets/samples`; a temp `HOME` holding `.config/delegate` and `.claude/agents` for
live-catalog cases; `tests/fixtures/refresh-2026-09-22` for native claude Lanes; and
`DELEGATE_MODEL_QUEUE` set to a temp path.

Cases added in D1:
- "a commit writes only the documents that changed"
- "an intervening edit is refused and nothing is written"
- "a link retargeted since the read is refused"
- "an invalid document is refused and nothing is written"
- "a commit writes through a link to an existing file and keeps the link"
- "a dangling link is refused at read and at commit, and its target is never created"
- "a commit backs up what it replaces and keeps the newest twenty"
- "a write that fails puts back what the commit already wrote" (`catalog.write_json`
  patched to raise on `routing.json`)
- "a first run commits onto absent documents"

Cases added in D2:
- "native Lanes added and removed gain and lose their agent files"
- "a link at a Lane's agent path is replaced and its target is untouched"
- "a template change reaches the Lanes already placed"
- "a catalog that is not the live one gets no agent file and a note"
- "a commit of project documents alone writes no agent file"
- "a commit forgets exactly the queue entries its read returned"
- "a read without the queue leaves the queue alone"

Every new test that runs `setup.main` passes `--no-bench`, plus `--no-discover` or
`--fixture-dir`, under a temporary `HOME`. Without `--no-bench`, `collect_bench` fetches
the Epoch CSV, which fails under H1's tripwire.

**Replaced:**
- In `test_setup.py`, the agent-file cases at the `setup` seam move to the commit:
  `native_agent_files_follow_the_claude_lanes`, `a_catalog_elsewhere_gets_no_agent_file`,
  `the_live_catalog_gets_the_agent_files`, `the_real_layout_saves_the_agent_files` and
  `a_template_change_reaches_the_placed_lanes`.
- `case_the_save_after_a_rescan_uses_the_rescans_plan` becomes "the save after a rescan
  writes the agent files of the Lanes it saved". It runs under a temp `HOME` and no
  longer monkeypatches `native_targets` or `catalog.CONFIG_DIR`.
- `test_model_queue.py` case 13 becomes "a scan whose catalog changed while it listed
  models writes nothing and still queues".
- `test_model_queue.py` case 9 finds its backup under `<cfg>/backups`.
- `test_catalog.py` uses `catalog_commit.read(...).revision` where it used
  `catalog_revision`.

**Deleted:**
- The `test_setup.py` tail block "focused writes preserve stow and revisions", now
  covered at the commit.
- `test_model_queue.py` cases 7 and 9c, which tested `setup.clear_queue`; the queue cases
  above replace them.

**Kept unchanged as proof that `catalog set` keeps its contract:** `test_catalog.py`
10.3, 10.3b, 10.3c and 11.7, the intervening-write case, and
`tools/delegate-dashboard/test_dashboard.py` (its mark check still finds the exact text in
`catalog_edit`).

### Live bugs fixed and the tests that prove them (each red on main first)

| Bug | Test | Fixture and expected result | Ticket |
|---|---|---|---|
| 1, catalog set | `test_setup.py` "a catalog set made while the wizard is open survives its save" | The sample catalog. The `run_curses` stub calls `catalog_edit.edit_catalog` to apply a tier change, then confirms. Expect exit 1, stderr names `lanes.json`, and the set's tier is on disk. | D1 |
| 1, model swap | `test_setup.py` "a model swap made while the wizard is open survives its save" | The stub runs `model_queue.scan` on the newer-codex fixtures from `test_model_queue.newer_fixtures`. Expect the successor Lane to stay. | D1 |
| 3 | `test_setup.py` "the full save writes through a linked catalog" | The config dir holds links to real files. Expect the links kept and the targets updated. | D1 |
| (none) | `test_setup.py` "the plain save refuses a catalog changed while it asked" | A stdin stub writes the catalog on its first read. Expect a refusal. | D1 |
| 5 | `test_catalog.py` "a project set refuses a dangling link and creates nothing outside the project" | `make_edit_fixture` plus `.delegate/routing.json` linking to a missing path outside the repository. Expect a refusal and nothing created. | D1 |
| 2 | `test_setup.py` "a model noticed while the wizard is open stays queued" | `--fixture-dir` refresh-2026-09-22 and `--no-bench`. The stub calls `model_queue.note`. Expect the entry to stay queued. | D2 |
| agent files out of step | `test_setup.py` "a save gives every native Lane in the catalog its agent file" | A temp `HOME` live layout with claude Lanes and no files, run with `--no-discover` and `--no-bench`. Expect a file for every native Lane. | D2 |
| scan imports setup | `test_model_queue.py` "the scan imports no wizard module" | A subprocess runs a fixture scan. Expect `setup`, `setup_tui`, `bench`, `bench_page` and `effort` absent from `sys.modules`; H1 adds `bench_snapshot` to the list. | D2 |
| 4 | `test_setup.py` "a focused tier screen saves only the change made on it" | The frozen refresh-2026-09-22 `lanes.json`, `--fixture-dir`, `--no-bench`, `--screen tier3`, one Lane toggled. Expect the Lane names unchanged. | D3 |

### ADR notes

ADR 0001 is kept, and its machine-local ruling (2026-09-29) is the reason for the
agent-file rule. If the user confirms the link rule (decisions D.1 and D.2), it becomes
ADR 0002 in the one ADR change made after all lanes merge: catalog documents are written
through links and a dangling link is refused; Agent files are plain files and a link at a
Lane's path is replaced. That ADR would not edit 0001. The queue change (decision D.4)
replaces redesign ticket 29's sentence "a run whose refresh did not run keeps the queue";
record the change in that ticket, not in an ADR. No change here touches routing, quota
units, Meters, model names or which Lanes are carried.

### Risks

- A refused wizard save loses the session's choices. The race is rare: the scan runs at
  most once a day, and `catalog set` is explicit.
- Agent files are now reconciled on any commit that writes the live catalog's global
  lanes document, a global `catalog set` included, so an Agent file that someone deleted
  by hand comes back. Dispatch needs that file to spawn a native Lane anyway.
- Backups add up to 40 files under `~/.config/delegate/backups`.
- Reads now refuse dangling links. A global preview run inside a project whose
  `.delegate/` holds a dangling link now fails with a clear message, where before it
  treated the file as absent.
- `delegate catalog fmt` now writes through a link instead of replacing it.
- The start page's queue lines are TUI text. Under ADR 0001 that work goes to a Claude
  Opus agent under `/frontend-design:frontend-design`; H1's change to the start page's
  rows line goes the same way.
- The queue file is still a read-modify-write without a lock, as today.
- The last check and the rename are still not a lock.
- Python 3.9: use `from __future__ import annotations` and `typing`, and nothing newer;
  see the read invariants for links and step 4 for the backup stamp.

## E. Routing preview

Rank explains its own Pick.

Tickets: 20 (E1), 21 (E2), 22 (E3), 23 (E4). Lane: meters-and-preview, after B.

### Problem

Rank decides the Pick, but two display modules work out why it was picked and what would
change it. They do this by replaying `choose`, `steals`, `score` and `eligible_order`,
which b1ae58a made public for the popup, or by parsing the reason text. `report.py`
(`handover`, `pace_to_lead`) replays the rule correctly but stops at its own axis.
`deck.py` parses the reason text and hard-codes `Pace + Margin`, and it has drifted:
ticket 39 (plan dollars) changed `rank.py` and `test_report` but not `deck.py`. Rank's
interface also carries an invariant that exists only for the popup (`score`'s docstring:
"a caller that changes `pace` on a row ... gets the value rescaled").

Live bugs, each verified in-process on `b268352`:

1. **A plan-dollars steal reads as ELIG on the deck.** The setup is the sample catalog,
   `tests/fixture/meters.json`, `quota_unit` set to `plan_dollars`, terra at order 1 and
   grok at order 2 in Tier 2. Rank picks `grok46-high@grok` with "stolen by plan dollars:
   6.21 >= 3.45 x (1 + 0.2)", and `deck.reason_code` returns ELIG. `steal_thresholds` then
   has no entry for Tier 2, so the aid tells the grok Meter "no Tier it can take" even
   though it holds the Pick there.
2. **A lane with no CLI and no Meter reading reads as NOMTR, not CLI.** `reason_code`
   tests `row["remaining"] is None` before it tests `vetoed:cli`. A harness that is not
   installed is also not probed, so this is the usual case for a CLI veto.
3. **The deck's threshold is wrong whenever a rival shares the Pick's place in the
   Order.** In the sample catalog's Tier 2 both lanes are unordered and grok's Pace is
   0.90. Codex leads at 0.91, which is what the popup's replay says, but the deck says
   "needs 1.10×". Under plan dollars the deck's Pace + Margin is the wrong unit as well.
4. **The popup says "cannot lead on Pace" when a rival can lead.** `pace_to_lead` stops
   at the axis top. In the sample catalog with plan dollars and `sol-high@codex` moved
   beside `fable-xhigh@claude` in Tier 4, the axis top is 4.0, the popup gives None, and
   codex leads at Pace 4.26. A Meter can read a Pace of up to 1 ÷ `CYCLE_FLOOR` = 50.
5. Stale text: `deck.steal_thresholds`'s docstring cites "rank.py lines 177-183", and
   `tools/delegate-dashboard/CLAUDE.md` cites `rank.py:177-183`.

### Chosen interface: the facts go on the Tier preview

The deepened module is rank's selection rule together with its what-if. It has one entry
point for previews. `rank()` and `rank_range()` keep their signatures.

```python
# rank.py
CAUSES = ("pick", "steal", "eligible", "unknown",
          "disabled", "floor", "ceiling", "gate", "cli")

def rank(cls, cat, meters, present, tier=None) -> list  # rows gain "cause"; "veto" is gone (E3)

def tier_leaders(cat, meters, present) -> list:
    """The four exact-Tier previews, Tier 1 to 4. Each is a dict:
      tier             int
      leader           lane name, or None
      rows             the Tier's rows, Pick first, each with "cause"
      steal_threshold  {"unit": "pace" | "plan_dollars", "value": float | None}
      pace_to_lead     {meter: float | None}
      handover         {"points": float, "to": lane | None} | None   (E4)
    """
```

`meters` is B's Meter snapshot: E builds after B3, which makes rank take a `Snapshot`.

Invariants:
- Every row has exactly one `cause` from `CAUSES`. `eligible` is true exactly when
  `cause` is one of pick, steal, eligible or unknown. `pick` is true exactly when `cause`
  is pick or steal. The `reason` text is display only, built from the cause and the
  numbers. No caller parses it.
- `steal_threshold.unit` is always `routing.quota_unit`. `value` is the value a Lane that
  sorts after the leader must reach to take the Tier: the leader's Pace plus the Margin,
  or with plan dollars the leader's value times (1 + Margin). It is None when the Tier has
  no leader, when the leader's value is unknown, or when Meters are off.
- `pace_to_lead` has one key for every Meter that has an eligible Lane with a known Pace
  in the Tier, except the leader's Meter. Its value is the lowest Pace on the 0.01 grid
  at which a Lane on that Meter leads the Tier, with every other Meter as it reads now. It
  is None when no Pace a Meter can read makes it lead; the highest readable Pace is
  `usage.MAX_PACE` (1 ÷ the cycle floor, 50 today), which B4 exports. With Meters off the
  map is empty. Gated Meters, Meters with no CLI and Meters with an unknown Pace have no
  key.
- `handover` is the smallest spend on a half-point grid (0.005) of the leader's Meter,
  read through B's `readout(spend=)`, at which another Lane leads or the Meter falls under
  the Gate. `to` is the new leader, or None when nothing else is eligible. `points` is in
  quota points and is never a time (ADR 0001). It is None with no leader, with Meters
  off, or when the leader's Meter has no weekly figure.
- The preview is pure and deterministic. It does no I/O, no probe and no write, and its
  output is JSON-safe (`json.dumps(..., allow_nan=False)`).

How rank asks "what if": B3 shapes `rank_range` as
`readouts = {meter: snap.readout(meter, cat)}` followed by a private ranking core over
that map. The what-if replaces one entry, with `dataclasses.replace(readout, pace=p)` for
a Pace to lead or `snap.readout(m, cat, spend=x)` for a Handover, and reruns the core. It
never reads the Snapshot twice.

Error modes: there are none new. Malformed or missing readings become unknown causes and
missing `pace_to_lead` keys, through the validity rule B owns. The cost is bounded.
`pace_to_lead` evaluates the Pick at 0 and at the first and second 0.01 step at or above
each crossing, for each other Lane. The crossings are the rival's value, value ± Margin,
or value × (1 + Margin)^±1, divided by the Meter's weight. `handover` takes at most 200
steps per Tier. The search runs on Python 3.9, so it does not use `bisect` with `key=`,
`zip(strict=)` or `itertools.pairwise`.

What it hides: the value (`score`), the sort key, the steal comparison in both units, the
trial replay, the breakpoint candidates and the 0.01 grid, the highest readable Pace, the
half-point handover step, the Gate crossing, and which Meters get a Pace to lead.

A prototype of the breakpoint search ran in memory only. Across 3,000 random Tiers (two
to seven Lanes, both units, Margins from 0 to 0.35) it gave the same answer as the
popup's 0.01 scan wherever the scan's ceiling allowed an answer. It took about 1 ms per
Meter at 15 Lanes, where a scan that never finds a lead takes about 10 ms. That
difference matters because the dashboard rebuilds the preview on every reload and every
staged key.

### Considered alternatives

- **What-if query.** Rank would expose one pure function,
  `who_leads(preview, meter, pace=None, spend=None) -> lane`, and callers would search
  with it. The interface is small, but the search stays in the callers. The search covers
  the grid, the ceiling, which Meters to ask about, and the Gate crossing during a
  handover. The deck is a view over plain-dict state and cannot call rank, so `model.py`
  would run one copy of the search and `report.py` another. That is the drift this
  candidate removes. The deletion test shows the problem: delete `who_leads`, and almost
  nothing of value goes with it, because the search loops in the callers were the
  complexity.
- **A lazy Preview object** (`Preview(cat, snapshot, present)` with `.need(tier, meter)`
  and `.handover(tier)`). Laziness saves nothing. The dashboard's model has to
  materialize every fact into its JSON-able state for the view and for
  `dashboard.py --json`, and the popup draws every fact. A live object also cannot cross
  `rank tiers --json`.

The chosen design has the most leverage: one call answers the CLI JSON, the dashboard
state, the deck and the popup. Locality is also best, because the rule, the unit, the
search and the readable-Pace ceiling all sit in rank. Its seam is rank's returned data,
the same kind of data seam as `rank --json` and model → deck.

### Callers migrated

- `deck.reason_code` maps `cause` to a code through a table (E1). `deck.status_icon`
  follows it. `deck.meter_verdict` and `deck.aid_lines` read the tier's `leader`,
  `pace_to_lead` and `steal_threshold.unit` (E2). B keeps the Gate half of
  `meter_verdict`.
- `model._build_state` copies `cause` into each row, and `steal_threshold`,
  `pace_to_lead` and `handover` into each tier. It and `_fresh_carried_lane_names` filter
  on `cause != "disabled"` (E1, E2).
- `report.popup_lines`, `tier_block` and `handover_note` render `cause`, `pace_to_lead`
  and `handover`. The axis is scaled from Meter Paces and Paces to lead (E3, E4). The
  statusline CLI (`statusline`, `--popup`, `toggle|on|off`) keeps its invocations.
- `rank.gate_only_stop` reads `cause` (E3).
- `rank tiers --json` carries the new facts with no further change.
  `catalog_edit._rank_preview`, `report.lane_lines` and `evals` keep reading `leader` and
  `reason` unchanged.

### Deleted

- `rank.score`, `eligible_order`, `steals` and `choose` as public names. They become
  private, and `score`'s popup invariant goes with them (E4). The row field `veto` goes
  (E3).
- `report.pace_to_lead` (E3). `report.handover`, its Window arithmetic, `HANDOVER_STEP`
  and the `eligible_order`/`choose` imports (E4); B2 left them in place for this. The
  popup's `steals` axis list (E3).
- `deck.steal_thresholds` with its stale docstring, `reason_code`'s prose parsing, the
  `meter_verdict` branch "takes the Pick in Tn" (unreachable once the Pace to lead is
  exact), and the duplicate reachable-threshold code in `aid_lines` (E1, E2).
- `model.py`'s two `reason.startswith("vetoed:disabled")` filters (E1).
- The `rank.py:177-183` citation in `tools/delegate-dashboard/CLAUDE.md` (E2).

### Tests

New tests, all at the interface. Cases 31 and 32 wrap their documents with
`usage.Snapshot.of`, and their rows keep the `cycle_left` key, which the Readout calls
`week_left`.
- `test_rank` case 30 (E1): cause on every row. It uses case 20's `tier_cat` with
  `steal_meters20` (terra steal, grok eligible), `gate_meters20` (grok gate),
  `unknown_meters20` (grok unknown) and no claude (fable cli). It uses case 13 (grok
  disabled), the sample `impl` rank for floor (luna-low) and ceiling (fable), and case
  29b (fable steal under plan dollars). It also checks the eligible/pick invariants.
- `test_rank` case 31 (E2):
  - (a) Sample catalog, fixture `meters.json`, Tier 2 unordered:
    `pace_to_lead == {"codex": 0.91}` and
    `steal_threshold == {"unit": "pace", "value": 1.1}`.
  - (b) The case 20 layout (grok order 1, terra order 2): codex 1.1.
  - (c) (b) with plan dollars: the unit is plan_dollars, the value is 0.9 × grok's
    weight × 1.2, and codex's Pace to lead is the next 0.01 step at or above that value ÷
    codex's weight.
  - (d) A property, checked through `tier_leaders` only: a meters document with that
    Meter at its Pace to lead puts a Lane on it in the lead, and one at the Pace to lead −
    0.01 does not.
  - (e) Meters off gives an empty map and a None value. A gated Meter and an unknown
    Meter have no key. A Meter priced at 1 against 100 under plan dollars reads None.
- `test_rank` case 32 (E4): handover through `tier_leaders` on fixture rows that carry
  `cycle_left` 0.5. Leader a@x on mx (weekly 0.5, Pace 1.0, order 1) and b@y on my (Pace
  0.9, order 2), Margin 0.2, Gate 0.05, give points ≈ 0.15 and to b@y. A lone leader
  gives ≈ 0.45 and None. Plan dollars with weights 20 and 10 gives ≈ 0.3125 and b@y.
  Meters off gives None.
- `test_rank` case 29c is replaced (E4): through `rank()`, on equally priced Meters, 1.2
  against 1.0 steals at Margin 0.2, 1.19 does not, and an unpriced Meter never steals.
- `test_report` (E3): `statusline`, `statusline --popup` and `statusline toggle` still
  exit 0 with output.

Red first, then green (live bugs):
- `test_dashboard.test_a_plan_dollars_steal_reads_as_a_steal` (E1). `routing.json` gets
  `quota_unit` plan_dollars, and `write_meters(a_r=0.7, a_pace=0.5, b_r=0.7,
  b_pace=0.65)`, which steals by plan dollars and not by Pace. Before E1 the test sees
  ELIG and "no Tier it can take" for codex-b. After E1 it sees STEAL and "holds the Pick
  in T2".
- `test_dashboard.test_a_lane_without_its_cli_or_a_reading_reads_as_cli` (E1). The
  fixture is `present={"codex","claude"}` with a meters document that has no grok row.
  Before E1 Tier 4 grok reads NOMTR, and after E1 it reads CLI.
- `test_dashboard.test_the_aid_marks_the_pace_rank_says_a_meter_needs` (E2). Terra and
  sol lose their `order`, and `write_meters(a_r=0.7, a_pace=0.6, b_r=0.7, b_pace=0.5)` is
  written. Before E2 the codex-b verdict is "needs 0.80× to take T2". After E2 it is
  "needs 0.60× to take T2", because sol wins the name tie at 0.60.
- `test_report` popup check "with plan dollars a rival past the axis gets its Pace to
  lead" (E3). The fixture is a copy of the samples with `quota_unit` plan_dollars and sol
  at Tier 4, plus the existing `pp_cache`. The Tier 4 codex row must show `needs {v:.2f}`,
  where v is `tier_leaders(...)[3]["pace_to_lead"]["codex"]` and lies above the axis top.
  Before E3 the row says "cannot lead on Pace".

Replaced or deleted:
- `test_report` lines 624-656 go: the two `pace_to_lead` checks in E3 and the three
  `handover` checks in E4. They are covered by cases 31 and 32.
- `test_rank` case 12 changes its key set (adds `cause` in E1, drops `veto` in E3).
- The `veto` assertions in test_rank cases 23, 26k, 26l, 26m, 26o and 27, and in
  `test_evals` line 114, read `cause` (E3).
- `test_dashboard.test_four_tiers...` adds `cause` to its row key set (E1).
- The popup CLI checks ("needs 0.96 (+0.26)", "→ luna-low@codex leads after agy drops
  18.5 pts") stay as the end-to-end checks, across B2 and E4 alike.

### ADR notes

- ADR 0001 holds throughout. The sort stays tier, order, pace, lane name. A steal is by
  Margin, inside a Tier included. A Handover is quota points at today's readings, never a
  time, with no history and no burn rate. `quota_unit` stays `pace` by default, and plan
  dollars is followed wherever it is set. Fixtures carry their own tiers and never the
  user's. Lanes in rotation stay machine-local. No ADR is needed: replacing `veto` with
  `cause` is a JSON field change, and `references/routing.md` documents it.
- `CONTEXT.md` gained five terms with this spec: Tier preview, Cause, Steal threshold,
  Pace to lead and Handover. Handover's avoid list names hand-off, which is a native
  Run's Outcome (C).

### Risks

- **Overlap with B in `report.py` and `deck.py`.** B owns `popup_meters` and the readout
  (weekly shown, share of the week left, 5h sharing) and the Gate half of
  `meter_verdict`. E touches only the Pace half and `tier_block`. B2 leaves
  `report.handover` alone, and E4, blocked by B2, moves it into rank on
  `readout(spend=)`.
- B's spend draws on the Weekly figure only (B invariant 5); the popup's 18.5-point check
  pins the Handover's result across both tickets.
- Rounding on the 0.01 grid uses `ceil(round(b*100, 9))`. Property (d) covers it.
- Every `tier_leaders` caller now pays for the what-if (`catalog_edit` previews,
  dashboard reloads). It is bounded by the breakpoint search. Measure it on 3.9 in E2.
- A reader of `veto` outside the repo would break. None is documented, and grep finds
  only `report.tier_block`, `gate_only_stop` and tests.

## F. Catalog draft

One answer to what save writes.

Tickets: 13 (F1), 14 (F2), 15 (F3). Lane: catalog-write, after D.

### Problem

The setup wizard keeps its decisions in five parallel structures on `setup_tui.Wizard`
(`_enabled`, `_assigned`, `_marks`, `_tier_order`, `_line_order`, beside
`_original_lanes` and `_original_routing`). It builds "the catalog after save" in six
places that disagree. `current_lanes` has no Order. The `handle("y")` block writes Order,
but the confirm page shows only the Tier. `_focused_lanes` and `_start_key` number
unordered Lanes by benchmark order, while `catalog_edit._carried_in_tier` numbers them by
lane name. The `--plain` path applies the same decisions a second time, directly on the
documents (`tier_lines.apply_tier_lines_to_doc`, `write_order_from_lines`, and
`ask_lanes` mutating `tier`), and that copy has its own bug. Tests reach the decisions
through 62 reads of private Wizard state.

Dependency category: in-process. The draft is pure computation over two dicts. It
imports only `catalog.carried_in_tier` and has no port and no adapter, so tests call it
directly.

### Interface

```python
# agents/skills/delegate/scripts/catalog_draft.py
from __future__ import annotations
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Tuple, Union

class LaneDecision(NamedTuple):
    carried: bool
    tier: Optional[int]   # None only for a carried Lane the tier pages have not placed yet
    place: Optional[int]  # its place in its Tier, from 1; None when off or not placed
    start_tier: int       # its Tier when the draft last settled

class Change(NamedTuple):
    path: Tuple[str, ...]  # ("lanes", lane, "tier"|"order"|"enabled"), ("classes", cls, "floor"|"ceiling"), ("margin",), ("gate",), ("meters",)
    old: object            # None when the key is absent
    new: object

class CatalogDraft:
    def __init__(self, lanes_doc: dict, routing_doc: dict, *, whole: bool) -> None: ...
    # decisions
    def carry(self, lane: str, on: bool) -> None: ...
    def place(self, lane: str, tier: Optional[int], at: Union[None, int, str] = None) -> None: ...
    def apply(self, pairs: Union[Mapping[str, object], Iterable[Tuple[str, object]]], unnamed: str) -> List[str]: ...
    def set_routing(self, key: str, value: object, cls: Optional[str] = None) -> None: ...
    def settle(self) -> None: ...
    # answers
    def is_settled(self) -> bool: ...
    def lane(self, name: str) -> LaneDecision: ...
    def tier_lanes(self, tier: int) -> List[str]: ...
    def documents(self) -> Dict[str, dict]: ...   # {"lanes": ..., "routing": ...}
    def changes(self) -> List[Change]: ...
    def __eq__(self, other: object) -> bool: ...  # sets __hash__ to None: never a dict key or set member

# agents/skills/delegate/scripts/catalog.py: the one tie-break
def carried_in_tier(lanes: dict, tier: int) -> List[str]:
    """The carried Lanes at `tier`, by Order; a Lane without one comes after every
    Lane with one, and ties go by lane name. This is the order rank tries them in
    with Meters off."""
```

What each entry point does:

- `CatalogDraft(lanes_doc, routing_doc, whole=...)` takes the catalog the pages start
  from: the `lanes` and `routing` dicts of D's `CatalogRead`, as `catalog.validate_lanes`
  accepts them. The caller adds the default Classes to the routing first, as the Wizard
  does today. The draft deep-copies both documents and never mutates them. With
  `whole=True` (the full wizard), save writes the whole catalog as the pages show it.
  With `whole=False` (a focused screen or `--plain`), save writes only the fields a
  decision changed. The draft starts settled. Each Tier's sequence is
  `catalog.carried_in_tier` over the documents as given.
- `carry(lane, on)`. Off: the Lane leaves its Tier's sequence and goes back to its start
  Tier. On: the Lane returns to its start Tier at its starting place. Switching a Lane off
  and then on again therefore changes nothing. Calling either on a Lane already in that
  state does nothing.
- `place(lane, tier, at=None)` applies to a carried Lane. With `at=None`, a Lane already
  in `tier` stays where it is. A Lane returning to its start Tier takes back its starting
  place. Any other Lane goes to the end of `tier`. With an integer `at`, the Lane goes to
  that place in `tier`, clamped to the Tier's places, so J at the bottom moves nothing.
  With `at="end"`, the Lane goes last, even in its own Tier. `tier=None` takes a carried
  Lane out of its Tier without placing it; only the full wizard's tier pages do this. For
  an off Lane, `place` sets only its Tier; only `--plain` prompts do this.
- `apply(pairs, unnamed)` takes `(lane, 1-4 | "off")` pairs in order; a mapping's items
  count as pairs. Each named Lane takes its value, and the Lanes named for one Tier come
  first in that Tier, in the pairs' order. With `unnamed="off"` (tier lines), every
  carried Lane the pairs do not name goes off, and `apply` returns those Lanes for
  `tier_lines.tier_lines_summary`. With `unnamed="keep"` (the tier proposal's `p`), every
  Lane the pairs do not name keeps its Tier and follows the named ones in its current
  order. Pairs that name no Lane change nothing and return `[]`.
- `set_routing(key, value, cls=None)` takes `key` in `floor`, `ceiling` (both with
  `cls`), `margin`, `gate` or `meters`. `meters=True` removes the key when the routing as
  given had none. The caller does the clamping, as the keymap and the prompts do today.
  Validation happens at commit.
- `settle()` makes the decisions as they stand now the draft's start: start Tiers,
  starting places, and the reference `is_settled` compares against. The Wizard calls it
  after the carry proposals and again after the `--tiers-from` lines. `is_settled()` is
  False after any carry, Tier, Order or routing change that has not been undone.
- `lane(name)` and `tier_lanes(tier)` are the queries every page reads.
- `documents()` returns a new mapping `{"lanes": ..., "routing": ...}`, keyed by
  `catalog_commit.DOCUMENTS` names, so `catalog_commit.commit(read, draft.documents())`
  takes it whole. It never adds or removes a Lane, and it touches no lane key except
  `tier`, `order` and `enabled`, and no routing key except Class Ranges, `margin`, `gate`
  and `meters`.
  - `whole=True`: every carried Lane gets `order` equal to its place, 1 to n in each
    Tier, and loses any `enabled` key. Every off Lane gets `enabled: false` and loses
    `order`.
  - `whole=False`: `tier` changes only where a Lane's Tier changed. `enabled` changes
    only where carry changed; a Lane switched off also loses `order`. A Tier's places are
    written only when its sequence differs from its sequence as given. Every other byte
    of a record stays as given. For example, an unchanged `enabled: true` stays, and an
    unchanged Tier keeps its gaps.
  - A carried Lane not yet placed is written at its Tier as given, with no `order`.
- `changes()` is the field diff between the documents as given and `documents()`. It is
  the one source for the focused confirm page, and it decides which documents a focused
  save commits: only those it touches, so default Classes the screen never listed are
  never written.
- `__eq__` compares all state, so the Wizard's failed-rescan restore and `made_choice`
  are value comparisons. Python then sets `__hash__` to None, so a draft is never used as
  a dict key or set member.

Error modes: an unknown lane name raises `KeyError`. A Tier outside 1 to 4 and None
raises `ValueError`, as do an `at` other than None, an int or `"end"`, `tier=None` on an
off Lane, an `unnamed` other than `off` or `keep`, a pair value other than 1 to 4 or
`off`, and an unknown routing key. The draft does not police `ultra`, because
`tier_lines.parse_tier_lines` already refuses it, and it does not validate the catalog,
which is the commit's job. Each operation costs O(Lanes).

What it hides: the five structures and three copies of the marks rebuild; `_start_key`,
`_arrange_review`, `_choices` and `_final_tier`; the starting-place restore rule; the
sequence as read (the one tie-break); both save scopes; the meters default-key rule, now
in one place instead of two (`Wizard._set_meters`, `setup.ask_routing`); and the change
diff.

### Rules the draft settles (one place each)

1. **Tie-break.** A Tier as read is numbered by Order, and Lanes without an Order go
   after every Lane with one, by lane name (`catalog.carried_in_tier`). This replaces
   benchmark order in the wizard. `catalog_edit` and `catalog._effective_lanes` call the
   same function, which deletes `catalog_edit._carried_in_tier`.
2. **Joining a Tier.** A Lane that joins a Tier it did not start in goes to its end. This
   already holds for the review page's 1-4 key, a focused tier unmark (test 61) and
   `catalog set`'s `_append_order_in_tier`, and it now holds for tier-page ticks and
   `--plain` prompts.
3. **Undo is exact.** A Lane returning to its start Tier goes right after the last Lane
   now in that Tier that came before it when the draft settled. For a Lane that was off
   then, the reference is the documents as given.
4. **Lines and proposals are decisions, not tie-breaks.** Their order is the order
   written.

### Tier pages on the draft (TUI view logic, built under `/frontend-design:frontend-design`)

The box on tier page N reads `lane(name).tier == N`. A tick is `place(name, N)`. An
untick returns the Lane to its start Tier when that Tier is below N. Otherwise the Lane is
left unplaced (`None`) in the full wizard, or moved one Tier down in a focused screen,
where Tier 1 still refuses. Entering page 1 in the full wizard places every unplaced Lane
at Tier 1, in lane-name order. Enter commits nothing, because there are no pending marks.
With these rules tests 1a, 1b, 3, 4, 5, 8, 8b, 16, 17, 18 and 39b pass with the same keys
pressed. The tier, carry and routing views keep their layout. The visible changes are the
confirm page's Order line (ticket F3) and the review page's starting order for unordered
Lanes and for Lanes ticked onto another Tier (ticket F2).

### Design it twice

- **A, decision object (chosen).** The seam sits before the decisions. One mutable draft
  holds the documents as given plus carry, Tier and Order. Six verbs decide, five queries
  answer, and one bit chooses the save scope. Depth: every move rule, both scopes and the
  diff sit behind twelve entry points. Locality: the stale-Order bug in `--plain` and the
  review-page Order are fixed in one file. Deletion test: deleting the draft brings back
  five structures in the Wizard and a second copy of the line application in `setup.py`.
- **B, materializer only.** `lanes_after(lanes_as_read, decisions, whole)` and
  `changes(before, after)` over a `{carried, tier, order}` dict that each caller keeps.
  Its interface is two functions plus a shape whose invariants every caller must
  maintain: each carried Lane sits in exactly one order list, which matches its Tier, and
  off Lanes sit in none. B removes the six materialisations but leaves the move rules
  (lines, `p`, J/K, 1-4, ticks, undo, a prompt's Tier change) in both callers. The
  `--plain` bug is a move-rule bug, so B leaves its whole class alive. Tests at B's seam
  cover the output, never the rules. Rejected.
- **C, immutable value.** Same seam as A, but every verb returns a new draft. Rejected:
  every other module edits documents in place, every handler would have to reassign
  `self.draft`, and A already gets value equality from `__eq__`.

### Callers migrated

- `setup.py --plain` (F1): the draft is built from D's launch `CatalogRead` with
  `whole=False`. The `--tiers-from` branch calls `apply(parsed["decided"], "off")`.
  `ask_lanes(lanes_doc, draft)` places each Lane, defaulting to `lane(name).tier`, with
  the same prompts and prompt count. `ask_routing(draft)` calls `set_routing`.
  `show_bench` reads `documents()`. `confirm_and_write(draft, read)` prints each Lane from
  `documents()` and calls `catalog_commit.commit(read, draft.documents())`, with no
  `refresh` or `targets` parameters, since D's commit owns Agent files and the queue. F3
  moves the printed text into `setup_tui.placement_text`.
- `catalog_edit._plan_set` and `_plan_order`, and `catalog._effective_lanes` (F1): they
  call `catalog.carried_in_tier`.
- `setup_tui.Wizard` (F2): `self.draft` is public. `_load` builds it with
  `whole=not focus`, applies the carry proposals in the full wizard, then calls
  `settle()`. The carry page, tier pages, review page (J/K and 1-4 use `place` with `at`,
  `v` and start lines use `apply(..., "off")`, `p` uses `apply(..., "keep")`), routing
  page (`documents()["routing"]`), `made_choice`, `rewrite_bench_page` and the meter
  coverage warning (`documents()["lanes"]`), the focused confirm rows (`changes()`) and
  `result()` (`documents()`) all read the draft. The full wizard commits both documents,
  because writing every shipped Class is ticket 16's intent; a focused screen commits
  only the documents `changes()` touches.
- `setup.main`'s focused branch belongs to D3: a focused screen builds its Wizard on the
  catalog as read, with no generation refresh. F3 adds that the focused confirm page's
  rows equal `draft.changes()`.

### Deleted

- `tier_lines.apply_tier_lines_to_doc` and `write_order_from_lines` (F1), and
  `unnamed_carried` (F2). `tier_lines` keeps the parser and the summary.
- `catalog_edit._carried_in_tier` (F1).
- Wizard attributes `_enabled`, `_assigned`, `_marks`, `_tier_order`, `_line_order`,
  `_review_order`, `_original_lanes`, `_original_routing` and `_loaded`. Wizard methods
  `current_lanes`, `_choices`, `_settle`, `_final_tier`, `_meter_coverage`, `_start_key`,
  `_arrange_review`, `_flatten_review`, `_move_in_tier`, `_move_to_tier`, `_place`,
  `_focused_lanes`, `_toggle_enabled` and `_set_meters`. Also the `handle("y")`
  materialisation block (F2).
- The confirm-page and routing-page row counts inside `handle`, which are now taken from
  the row builders (F3).

### Tests

New, at the interface (`tests/test_catalog_draft.py`, picked up by `make test`):
- A draft with no decision writes back the catalog it read: `whole=False` writes it byte
  for byte, and `whole=True` writes it equal except for each carried Lane's place.
- A Tier as read is numbered by Order, then lane name, and gaps close. Fixture: orders 1
  and 7 plus two unordered Lanes.
- A Lane placed in another Tier goes to its end, and placed back it takes its starting
  place.
- Switching a Lane off and on gives it back its Tier and place.
- `at` moves a Lane inside its Tier and stops at either end; `end` puts it last.
- Lines carry, set the Tier of, and order the Lanes they name, switch the rest off, and
  return them. Lines that name no Lane change nothing.
- A proposal places the Lanes it names first and keeps the rest in their order.
- A focused save writes only the changed fields. An unchanged `enabled: true` and an
  unchanged Tier's gaps survive, and a Lane switched off loses `order`.
- A whole save writes every carried Lane's place, `enabled: false` on off Lanes, and no
  `enabled` key on carried ones.
- A Lane not placed yet is written at its Tier as given, with no place. An off Lane
  placed by a prompt keeps that Tier.
- `meters` off is written; `meters` on removes only a key the catalog did not have.
- `changes()` lists exactly the fields `documents()` changes, over several decision
  scripts.
- `settle` and `is_settled` notice a change and notice its undo.
- The draft never mutates the documents it was given.
- In `test_catalog.py`: `carried_in_tier` orders by Order, then lane name, and skips off
  Lanes.

Every new `setup.main` case passes `--no-bench` and `--no-discover` (or `--fixture-dir`)
under a temporary `HOME`, so none reaches the web.

Replaced:
- The written-document checks in `test_setup_tui.py` 20 and 21 move to the whole-save
  draft test; their key and view checks stay.
- 26 is deleted. It duplicates 2 and the draft's no-decision test.
- 53's gap-closing check moves to the draft test.
- 39, 44b and 53 assert the new starting order.
- 61 reads `catalog.carried_in_tier`.
- All 62 reads of private Wizard state (`_enabled`, `_assigned`, `_marks`,
  `_review_order`, `_lanes_at`, `_toggle_enabled`, `_enter_prescreen`, `_meters_on`,
  `_routing_settings`, `_routing_rows`, `__dict__`, and the evidence reads `_unmatched`,
  `_proposals`, `_reasons`) read `w.view()`, `w.draft`, or the then-current public
  evidence functions (`published_names` and `carry.decisions(L, rows)`) instead; A1's
  rebase converts the evidence reads to `LaneEvidence`.
- In `test_tier_proposal.py`, "taking the proposals keeps that order" reads
  `w.draft.tier_lanes`.
- `test_bench_page.py` 35.4 goes through `CatalogDraft.apply`.

### Live bugs fixed (red first, then green)

1. **`--plain` writes a stale Order.** Verified by running at `b268352`. Fixture: the
   sample catalog with every carried Lane numbered in its Tier (fable 4/1, sol 3/1, terra
   2/1, grok 2/2, luna 1/1, flash 1/2). The prompt answer moves `terra-high@codex` from
   Tier 2 to Tier 3. It was written with order 1, beside `sol-high@codex`'s order 1, and
   `grok46-high@grok` was left alone in Tier 2 at order 2. The confirm listing printed
   both `order 1` lines. The proving test is
   `test_setup.py::case_a_prompted_tier_change_moves_the_lane_to_the_end_of_its_new_tier`,
   which expects terra at 3/2, sol at 3/1 and grok at 2/1, and expects the printed line
   `terra-high@codex: tier 3, order 2` (F1).
2. **A focused screen writes a generation refresh its confirm page never listed.**
   Verified in-process on `tests/fixtures/refresh-2026-09-22` with `--screen tier3` and
   one Lane unticked. The confirm page listed 8 Tier and Order edits, while the save added
   20 Lanes and removed 17. D3 owns the fix and its failing-first test ("a focused tier
   screen saves only the change made on it"). F3 adds one assertion on top: on a focused
   screen, the confirm rows equal `draft.changes()`.
3. **The full confirm page shows Tier only, while `y` writes Order.** Found by reading
   the code. The proving test is `test_setup_tui.py` "81 the confirm page lists each
   carried Lane with the Order y writes". It walks the sample catalog with one J on the
   review page and expects each row's value `tier N, order M` to equal `result()` (F3).

### ADR notes

No settled decision is reopened. Ranking is untouched, and Order is still set on the
review page (ADR 0001). The lane-name tie-break extends ADR 0001's statement that lane
name is the deterministic tie-break. Every page keeps one decision per line. The confirm
page decides nothing, and each of its lines is one Lane as written. TUI tickets F2 and F3
go to a Claude Opus agent under `/frontend-design:frontend-design`. If the user confirms
decisions F.1 to F.3, they become ADR 0003, "One rule places a Lane inside its Tier" (D's
link rule takes 0002), in the one ADR change made after all lanes merge. Until then they
stay in this spec.

### Risks

- The review page's starting order changes visibly for unordered Lanes, which now go by
  lane name, and for a Lane ticked onto another Tier, which now goes to that Tier's end.
  `p` and J/K remain the ways to order a Tier, and `architecture.md` states the new rule.
- `--plain` now numbers a Tier whose prompts change it, even in a catalog with no Order,
  as focused screens and `catalog set` already do.
- A rescan after a routing edit now refuses instead of keeping the edit.
- Merge order: D builds first in this lane, so F hands `draft.documents()` to D's commit
  and never calls `write_json` or `write_focused`. bench-evidence merges after this lane:
  A1 rebases onto F2's `_load` and test reads, and H3 adds its `epoch_rows` Wizard
  argument on top of F2.
- The restore rule is the subtlest part of the draft, and the undo tests pin it.
- Python 3.9: the draft uses `Optional` and `NamedTuple`, with no `X | Y`, no `match`,
  no `zip(strict=)` and no `itertools.pairwise`.

## G. Relay seam

A Relay port with an in-process fake.

Tickets: 05 (G1), 06 (G2), 07 (G3), 08 (G4). Lane: run-and-relay, after C.

### Problem

Five modules know what a relay writes. `delegate.py` has three of them: `run_relay`
builds the node argv, `resolve` shells out to `ads.sh check` and repeats its ADS
directory default, and `map_result` reads ten `result.json` keys. `map_result` also
writes the Run, so it is not pure (C1 makes it return a `runs.Finish` and write nothing).
The other two are `harnesses/grok.py`, which reads `events.jsonl`, and `report.py`, which
keeps every relay's token key spellings. `evals.py` also lists `result.json` among a
Run's files. The only way to substitute a relay today is to rebuild a whole environment:
a fake ADS tree, a fake `git` that answers the pin, CLI stubs, node symlinks and seven
environment variables. That builder exists twice, in `tests/test_dispatch.py` and
`evals.py`, and the two copies have already drifted. Failure modes are tested by
monkeypatching `delegate.run_relay` inside `python -c` strings.

### Interface (chosen)

A new module, `agents/skills/delegate/scripts/relays.py`, holds a Relay port with two
operations and two adapters. It uses only the stdlib and runs on Python 3.9: it uses
`typing.NamedTuple` and `Optional`, with no PEP 604 unions. How relayed work ended is C's
`runs.Finish`; relays.py defines no outcome type of its own.

```python
class Job(NamedTuple):
    harness: str                  # registry name; its adapter names the relay dir and the flags
    model: str
    effort: str                   # the effort this Run takes, after any override
    timeout: str                  # the Lane's timeout, such as "25m"
    prompt: str                   # absolute path of the Run's prompt.md (passed as --brief)
    cwd: str                      # the worker's working directory
    write: Optional[str] = None   # the writable worktree; None is a read-only job

class Report(NamedTuple):         # what one relay said; an adapter builds it, the fake is scripted with it
    status: Optional[str] = None  # completed, timeout, failed, aborted, <harness>_unavailable, ...; None: nothing reported
    final_message: str = ""
    error: Optional[str] = None   # the relay's own account of a failure, or why nothing was reported
    exit: Optional[int] = None    # the relay process's exit code; None when no process ran
    secs: int = 0
    session_id: Optional[str] = None
    tokens: Optional[dict] = None # Token counts {"in","out","cache_read","cache_write"}, or None
    touched_files: Optional[list] = None
    read_only_violation: Optional[bool] = None
    stopped: Optional[str] = None # why a completed job stopped short (Harness.blocked_reason), or None

class Relay:
    def check(self) -> Optional[str]: ...                      # why relays cannot run on this machine now, in one line, or None
    def run(self, job: Job, run_dir: str) -> runs.Finish: ...  # _settle(self._launch(job, run_dir), job)

class Ads(Relay):
    def __init__(self, ads_dir: Optional[str] = None, env: Optional[dict] = None): ...

class Scripted(Relay):
    def __init__(self, *script, ready: Optional[str] = None): ...  # each item a Report, or an exception to raise
    jobs: list                    # the (job, run_dir) pairs it ran, in order
```

Until G4 lands, `Report` and `runs.Finish` carry `usage` (the relay's raw record) where
they will carry `tokens`. G4 renames `Finish.usage` and the `DISPATCH_FIELDS` entry
`usage` to `tokens` in one change.

Invariants:
- Every field of the Finish except `returned` is a `runs.DISPATCH_FIELDS` key, so
  `runs.execute` records it without renaming anything. The keys of `returned` are exactly
  `RETURN_FIELDS`, and its status is done, partial or blocked.
- `reason` is None for done and partial, and a string for blocked.
- `relay_exit` is None only when no relay process ran.
- A read-only job whose relay reports `read_only_violation` true gets the tripwire
  question. A write job never does.
- Settling caps evidence at 12 items, claims at 200 characters, block open questions at
  5, and a partial's deliverable at its first 60 lines.
- `check` is asked before a Run starts. `run` is asked with a run directory that already
  exists.

Error modes:
- `Ads.run` returns a Finish for every way a relay can fail. These are: node missing at
  spawn, no `result.json`, a `result.json` that does not parse or is not an object, an
  unreadable `relay.stderr`, and a missing `events.jsonl`. It catches only `OSError` and
  `ValueError` (a `json.JSONDecodeError` is one) around the spawn and the result, stderr
  and events reads, never bare `Exception` or `BaseException`. `KeyboardInterrupt` and the
  Run's SIGTERM termination therefore pass through, and `runs.execute` turns them into
  "dispatch interrupted" and "dispatch terminated (SIGTERM)".
- `Scripted.run` raises what it was scripted to raise, so a test can raise
  KeyboardInterrupt. It raises AssertionError when its script is exhausted, which is a
  test bug.
- `Ads.check` returns the first line `ads.sh check` printed when it fails.

What `Ads` hides:
- The `node` binary and the relay path `<ads>/skills/<Harness.relay>/scripts/relay.mjs`.
- The ADS directory: the argument, else `$ADS_DIR`, else `relays.DEFAULT_DIR`. A test
  guards that it matches `ads.sh`.
- `ads.sh check`, run with `ADS_DIR` set explicitly.
- The argv: `--brief --cd --out-dir --model` plus `Harness.run_args`, and the env
  overrides such as `CODEX_HOME`.
- The `relay.stdout` and `relay.stderr` capture, and the timing.
- Every `result.json` key: status, finalMessage, error, stderrTail, threadId, sessionId
  or conversationId, the usage key spellings, touchedFiles and readOnlyViolation.
- The form of node's crash output.
- `events.jsonl`, which it reads through the harness hook
  (`Harness.blocked_reason(run_dir)`).

What settling hides: the return-block scan (`find_return_block`), the status table that
is in `delegate.py`'s docstring today, the caps and the tripwire. Settling is a private
pure function `_settle(report, job) -> runs.Finish`. It reads only `job.timeout` and
`job.write`.

Where the harness preflight sits: the preflight (codex inside a nested Seatbelt) stays a
harness hook that the relayed work asks after the Run starts and before the Meter probe.
It is not part of `check` (decision G.1).

### Considered alternative

The alternative places the seam at the run directory. Adapters would leave ADS-format
files (`result.json`, `events.jsonl`, `relay.stderr`) in the run directory, and one
reader, `read(run_dir, job, exit, secs) -> Finish`, would settle them. The fake would
write those files in-process.

The chosen shape is deeper. Callers learn one call, `run(job, run_dir)`, while the
alternative needs `launch`, then `read`, plus the file format the fake must write.

It also has better locality. ADS's key spellings and node's crash output live in one
adapter, while the alternative spreads them into the reader, the fake's writer and every
test that scripts a case.

The seam itself sits better too. A Report in memory can express "node is missing" and
"the relay threw before writing", which leave no files. A file seam pins every test to a
third-party format. The alternative's one real advantage is that it tests exactly what
production reads. The chosen shape keeps that for the Ads adapter through the fake
relay's new `replay=<dir>` directive, which replays real run directories such as
`tests/fixtures/dispatch/grok-gate-cancel`.

A variant that scripts the fake at the Finish was also rejected. It would skip settling,
so C's Run tests would see Finishes no relay can produce (decision G.5).

Deletion test: without `relays.py`, the argv, the result reading and the settling would
reappear in `dispatch`, and every failure case would go back to an environment-level
world. The module earns its keep. There are two adapters, Ads in production and Scripted
in `tests/test_relay.py` and C's in-process Run tests, so the seam is real.

### Callers migrated

- `delegate.dispatch`: the relayed work that `runs.execute` calls (C1) keeps the
  preflight and the two probes and ends with `return relay.run(job, run.path)`.
  `runs.execute` records the Finish, the Ledger and the Meter hold.
- `delegate.resolve` calls `relay.check()` for a relayed Lane.
- `dispatch` and `run` take `relay=None`, which defaults to `relays.Ads(ads_dir)`.
- `report.compute_cost`, `cmd_log` and `cmd_cost` read `dispatch.json["tokens"]`.
- `evals.Sandbox` builds on the one offline world, and `RUN_FILES` names the Run's own
  files.
- `tests/test_dispatch.py` uses the same world.

### Deleted

- From `delegate.py`: `run_relay`, `map_result`, `find_return_block` (moved into
  `relays.py` as private code), the status-table docstring, the `sh ads.sh check`
  subprocess, `resolved["ads_dir"]` with its repeated default, and the relayed work's own
  node branch (C1's `blocked("node is not on PATH; the relay needs Node.js")`), because
  Ads returns that Finish.
- From `report.py`: `INPUT_KEYS`, `OUTPUT_KEYS`, `CACHE_READ_KEYS`, `CACHE_WRITE_KEYS` and
  the raw-usage use of `_first_present`.
- From `tests/test_dispatch.py`: `setup_env`'s world, `pinned_ads_commit` and
  `stage_run`.
- From `evals.py`: `Sandbox._build_offline_world` and `_stub`, which move into one
  `evals.OfflineWorld` with a public `world.stub(name, body)` hook.

### Tests

New: `tests/test_relay.py`, a standalone script like the others.
- Settling through `Scripted`, with no node and no subprocess. It covers a done block
  (with the caps), prose with no block, an empty final message, a timeout naming the
  Lane's timeout, a failed, aborted or unavailable relay with its error or status, a
  relay that reported nothing, a job that stopped short (and a block winning over the
  stop), and the tripwire on read-only jobs only. Every case asserts the Finish field
  invariants against `runs.DISPATCH_FIELDS` and `RETURN_FIELDS`.
- `Ads` through the fake `relay.mjs`. It covers a crash before `result.json`, a
  non-object `result.json`, the grok gate-cancel replay with its two variants, session id
  spellings, node missing at spawn, argv and env per harness, `check` (pin, node, relay
  script), the default directory, and Token counts for each key spelling.
- `test_runs` gains a case: SIGTERM delivered inside a relay adapter's `run` (a test-only
  `Scripted` subclass that signals its own pid there) ends the Run "dispatch terminated
  (SIGTERM)". test_dispatch 12i keeps proving the same through Ads and the fake relay.
- `test_evals.py` gains a case that keeps the host's Seatbelt out of the offline world.
- `test_dispatch.py` gains one case that builds the Job in-process through
  `dispatch(relay=Scripted(...))`.

Replaced:
- `test_dispatch` cases 2a, 2b, 2c, 3, 4a to 4c, 5, 6 and 13 move to settling through
  Scripted.
- Cases 28a to 28c, which call `delegate.map_result` directly (C1 made them assert on the
  Finish it returns), move to an Ads replay of the fixture.
- C1's in-process node-missing case, which replaced 12e, moves to test_relay as Ads
  node-missing.
- Cases 9a to 9h, 9a2, the argv half of 24, and 31f move to Ads argv and env.
- 9b moves to the in-process Job case.
- The key-alias cases in `test_report` move to the Ads token table. `test_report` keeps
  its dollar cases on canonical `tokens` fixtures.

Kept as wiring: dispatch cases 1, 7, 8, 10, 10b, 12, 12c, 12d, 12g, 12h, 12i and 14
onward (C1 deleted 11, 12e, 12f and 36). Case 34c retargets its patch from
`delegate.run_relay` to `relays.Ads._launch`, unless B3 has already rewritten it to count
probes without patching.

### Live bugs fixed

1. **A relay that crashes before writing `result.json` is reported with the Node version,
   not the error.** Node ends an uncaught exception with a `Node.js v22.22.0` trailer, and
   `map_result` takes the last stderr line. This was reproduced: the reason reads
   `relay wrote no result (exit 1): Node.js v22.22.0`.
   - Red first: `test_dispatch` case 6b, "a relay that crashes before its result is
     blocked with its error, not the Node version". Its fixture is the brief directive
     `fake-relay: crash=relay blew up before result.json`, which is a new `crash=`
     directive in `tests/fake-ads/relay.mjs`. It expects
     `blocked: relay wrote no result (exit 1): Error: relay blew up before result.json`.
   - Green: the same case moves to `test_relay` as "Ads: a relay that throws before
     result.json is blocked with node's error line".
2. **A `result.json` that is not a JSON object raises inside `map_result`.** The Run then
   reads `dispatch failed: AttributeError: 'list' object has no attribute 'get'` and loses
   the relay's exit, so the Ledger shows rc 1. This was reproduced.
   - Red first: `test_dispatch` case 6c, using `fake-relay: replay=<dir>` on a staged run
     directory whose `result.json` is `[]` and whose exit is 0. It expects `relay_exit` 0
     in `dispatch.json` and no `AttributeError` in the reason.
   - Green: the case moves to `test_relay` as "Ads: a result.json that is not an object is
     blocked and keeps the relay's exit".
3. **The offline eval's world lets the host's `sandbox-exec` reach codex's preflight.**
   #30 gave `test_dispatch`'s world a nesting stub but not `evals.py`'s. As a result,
   `make test` fails `test_evals` on a Mac whose shell runs inside a Seatbelt. This was
   reproduced by putting a refusing stub after the world's bin directory: codex's ping
   fails with `codex cannot start its sandbox inside this shell's sandbox`.
   - Red first: `test_evals` case "eval 1 offline: the host's Seatbelt never reaches the
     offline world". Its fixture is a `sandbox-exec` stub that prints
     `sandbox-exec: sandbox_apply: Operation not permitted` and exits 71, placed in a host
     directory after the world's bin directory on its PATH. It expects
     `evals.ping_one(world, "codex")` to pass.
   - Green once the one offline world carries the nesting stub.

### ADR notes

The design stays inside ADR 0001.
- The catalog and the `lane-*.md` agents stay machine-local, and the test world copies
  `assets/samples`.
- No model name is coded: `relays.py` takes the model from the Job, and tests use the
  sample catalog's Lanes.
- Routing and Meters are untouched. The probes stay where the relayed work puts them, and
  the preflight still runs before the probe, as #30 placed it.
- Nothing adds ACP.
- No new ADR is needed. Decisions G.1 and G.2 are the ones a reader would otherwise ask
  about.

### Fit with the other candidates

- C (Run lifecycle) builds first in this lane. `Relay.run` returns C's `runs.Finish`, so
  `runs.execute` records it whole.
- `Scripted(KeyboardInterrupt())` passed through `dispatch(relay=...)` (G3) gives C an
  in-process test that a started Run always finishes, with no `python -c`.
- The Meter hold, one private function in `runs.py`, reads the Finish's returned status,
  its reason and `returned["deliverable"]`; B1 later points it at `usage.hold`.
- B3 puts its FRESH and FORCED reads around `relay.run` inside the relayed work, and its
  probe-counting tests use `world.stub` to install a logging agy stub.
- G touches no catalog, ranking or benchmark code.

### Risks

- C1 lands first in this lane, so G1 builds on `runs.execute` and `runs.Finish`; there is
  no throwaway `Run.finish` wiring. B3, in a later lane, edits the same relayed work and
  rebases onto it.
- Run directories written before G4 hold raw `usage`, so the report reads them as
  unmeasured. `runs.jsonl` keeps the cost of every Run already logged.
- Token semantics are unchanged. An OpenAI-style relay that counted cached tokens inside
  its input would still double-count them. No relay at the pin does: codex reports no
  usage and stays unmeasured, as redesign ticket 08 decided. The rule now lives in one
  adapter.
- `subprocess.run` kills the relay 0.25 s after Ctrl-C, before the relay writes its
  aborted result with its touched files. This is out of scope, but it becomes a one-place
  fix inside `Ads._launch`.
- The ADS default directory is written twice, once in shell and once in Python. A test
  guards that they match.
- The Ads cases need node, as `test_dispatch` already does.

## H. Benchmark snapshot

Benchmark rows behind one fetch port.

Tickets: 27 (H1), 28 (H2), 29 (H3). Lane: bench-evidence, after A.

### Problem

Getting benchmark data is split across `effort.py`, `setup.py` and `bench.py`, and each
follows its own policy.

- **AA in the wizard.** The wizard fetches Artificial Analysis (AA) on a thread through
  `setup.refresh_effort_rows`. That path has a 24-hour cache, a fixture directory, a list
  of fallback paths, and a scan of file contents to find the AA file.
- **Epoch in the wizard.** The wizard fetches the Epoch CSV through `bench.collect` →
  `bench.load_epoch` → `bench.fetch_bytes`. This runs on the main thread with no cache, at
  launch and again on every `r`. It also runs in `--fixture-dir` and `--no-discover` runs,
  which both promise no network.
- **Other gaps.** The two `load_effort_rows` functions handle errors differently. The
  page's evidence records never see Epoch rows. When Epoch cannot be read, `collect`
  raises, and the AA figures are lost with it.

### Chosen interface

The new module is `agents/skills/delegate/scripts/bench_snapshot.py`, the Benchmark
snapshot. It imports `effort` (the AA extractor) and nothing that routes. `bench` imports
it, never the other way round. Python 3.9 rules apply: `from __future__ import
annotations`, `typing.Optional`, `NamedTuple`, no `match`.

```python
MAX_AGE = 24 * 60 * 60                  # every fetched source (decision H.1)
CACHE_DIR = "~/.cache/delegate/bench"   # expanded when web() is called, never at import
EPOCH_URL = "https://epoch.ai/data/eci_benchmarks.csv"   # moved from bench; bench re-exports it
EPOCH_BENCHMARKS = (...)                                 # moved from bench; bench re-exports it

class Origin(NamedTuple):           # where one fetched source's rows came from
    how: str                        # "fetched", "cache", "file", "rows" or "none"
    path: Optional[str]             # the file the rows were read from
    age: Optional[float]            # seconds since the rows left the web, or since the file was written
    failure: Optional[str]          # why a fetch failed, when these rows are a fallback or there are none

class Snapshot(NamedTuple):
    effort_rows: Optional[List[dict]]   # every accepted row; None means no per-effort evidence
    epoch_rows: Optional[List[dict]]    # Epoch rows on EPOCH_BENCHMARKS; None means unavailable
    origins: Dict[str, Origin]          # "aa" and "epoch", one for each source given an adapter
    errors: tuple                       # one line per named input that could not be read
    note: str                           # the start page's line; "" when no source had an adapter

Fetch = Callable[[str, bool], "Fetched"]   # the port: (source id, renew) -> rows with their origin

def web(cache_dir: str = CACHE_DIR, get: Optional[Callable[[str], bytes]] = None,
        clock: Callable[[], float] = time.time) -> Fetch     # get=None means effort.fetch_page
def fixture(directory: str) -> Fetch    # <dir>/aa-accepted.json and <dir>/epoch.csv
def local(path: str) -> Fetch           # one named file, for whichever source it is passed as

def snapshot(row_files: Sequence[str] = (), aa: Optional[Fetch] = None,
             epoch: Optional[Fetch] = None, *, renew: bool = False) -> Snapshot

def load_effort_rows(paths) -> list     # the one accepted-rows reader; raises naming the file
```

**Invariants and error modes**

- **Never raises for a source.** A named input that cannot be read or parsed goes in
  `errors`. A named input is a `--effort-rows` file or a file given to `local`. A fetched
  source that cannot be read goes in its `Origin.failure`.
- **`effort_rows`.** These are the named files' rows in file order. The AA adapter's rows
  take the place of every named row whose `source` is `aa`, at the first one's position,
  or are appended if there is none. The value is `None` in two cases: no file was named
  and no AA adapter gave rows, or any named file failed (today's rule, so the pre-screen
  never judges a Lane on part of its evidence).
- **`epoch_rows`.** These are the CSV rows on `EPOCH_BENCHMARKS`, as
  `load_epoch_csv_text` gives them today, each keeping `model` and `slug` for A's
  attribution. The value is `None` when no Epoch adapter was given, or when it had no
  rows on hand.
- **`renew` (the wizard's `r`).** It fetches AA even when the cache is younger than
  `MAX_AGE`, because AA's rows are the only list of claude models the refresh reads
  (`setup.published_model_names`). Epoch is never renewed: no Epoch row names a model the
  refresh reads, and its cache is what keeps `r` off the web for it.
- **`web`.**
  - It reuses an artifact younger than `MAX_AGE`. Otherwise it fetches.
  - It replaces the artifact only after the new one has parsed. For AA,
    `effort.aa_accept` must have extracted and checked it. For Epoch, the header must
    match.
  - A failed fetch returns the newest artifact on hand, whatever its age, together with
    the failure (decision H.2).
  - With nothing on hand, the source falls back to the named AA rows (`how="rows"`) or
    to nothing (`how="none"`).
- **`fixture` and `local`.** They never open a URL and never read or write the cache. A
  file missing from a fixture directory is a note. A file given to `local` that cannot
  be read is an error.
- **No state.** `snapshot()` keeps no state, and ages are measured when it runs. A failed
  renew reads the cache that launch read or wrote, so `r` keeps the rows the pages already
  show, and setup no longer passes a list of fallback paths.
- **Threading.** It runs on setup's fetch thread beside discovery and touches only its
  arguments and the cache directory.

**What it hides:**
- both URLs (AA's comes from `assets/sources.json`)
- the HTTP GET (`effort.fetch_page` stays the one function that opens a URL)
- the cache layout and TTL, and which source renews
- AA extraction and check, which stay in `effort`
- Epoch parsing: the header check, `split_model_version` and the benchmark filter
- the fallback order and the merge of fetched AA rows into named rows
- ages and the note's wording

**Cache directory policy.** There is one directory, `~/.cache/delegate/bench/`.

- `aa/` holds `packet.txt`, `rows.json`, `accepted.json` and `rejected.json`, exactly as
  `effort.py aa` writes them, so an existing cache stays valid.
- `epoch/eci_benchmarks.csv` is the CSV as served, so a change to `EPOCH_BENCHMARKS`
  needs no refetch.
- Freshness is the artifact's mtime, and both sources keep a fetch for 24 hours.
- A fetch writes into a temporary directory beside its source's directory and moves the
  artifact (`accepted.json` or the CSV) in last.
- `bench.py`'s `<date>.md` reports stay beside these.
- Fixture, named-file and offline runs never touch this directory.

Usage:

```python
# setup.scan, at launch and on r
live = None if args.no_discover else (
    bench_snapshot.fixture(args.fixture_dir) if args.fixture_dir else bench_snapshot.web())
epoch = bench_snapshot.local(args.epoch_csv) if args.epoch_csv else live
snap = bench_snapshot.snapshot(args.effort_rows or (), aa=live, epoch=epoch, renew=force)

# bench.py (the report): AA still comes only from --effort-rows
snap = bench_snapshot.snapshot(args.effort_rows,
    epoch=bench_snapshot.local(args.epoch_csv) if args.epoch_csv else bench_snapshot.web())

# bench.py model: never fetches
snap = bench_snapshot.snapshot(args.effort_rows,
    epoch=bench_snapshot.local(args.epoch_csv) if args.epoch_csv else None)

# a test: a temp cache and no network
snap = bench_snapshot.snapshot([repo_aa], aa=bench_snapshot.web(cache_dir=td, get=served, clock=lambda: T))
```

**Seam.** The port is real. It has three adapters: the web, a fixture directory, and a
named file. The `get` a test passes to `web` is the web adapter's internal seam.

**Dependency categories.**
- The web is a true external, so tests pass `get`.
- The cache directory is local-substitutable: a temp directory.
- Parsing and merging are in-process.

**Deletion test.** Deleting the module pushes the cache, TTL, fallback, merge and note
back into setup's launch, rescan and plain paths and into both bench CLIs. So it earns
its keep.

### Design it twice

**A, chosen.** This is the function above. The port works at the artifact level, meaning
a source's accepted rows or its CSV, and the caller passes one adapter per source.

- The fixture directory and a named file are adapters of the same port as the web. They
  cannot touch the cache by construction, and the existing `aa-accepted.json` fixtures
  keep working.
- Freshness lives only in the web adapter. Fallback, merge and the note live in
  `snapshot()`.
- Callers state in one or two lines where each source comes from.

**B, rejected.** A session object, `BenchmarkData(row_files, transport, cache_dir,
fixture_dir, epoch_csv, offline)`, with `load()` and `rescan()` and a port at the
transport level (`url -> bytes`). It has more locality: every rule sits in one class. It
was rejected on seam placement and depth:
- A transport port cannot serve the fixture directories, which hold accepted AA rows,
  not pages. Fixtures would need a second mechanism inside the class.
- `cache_dir=None` becomes something a fixture caller must remember.
- `rescan()` before `load()` is an ordering constraint.
- Every snapshot test would have to run the AA page extractor.
- Its constructor flags are argparse moved, not hidden.

**A third shape, dropped.** A fixture directory as a read-only cache. The fixture layout
is not the cache layout, and "never write it" would be one more flag.

### Callers migrated

- **`setup`.** `setup.scan` returns `(discovered, discovery_data, snapshot)` from one
  `snapshot()` call on its thread. These read the snapshot:
  - `setup.main`, in launch, `rescan`, plain and TUI
  - `collect_bench(args, lanes_doc, snapshot)`
  - `show_bench(args, lanes_doc, routing_doc, snapshot)`, where F1's caller passes the
    draft's documents
  - `propose_generation(lanes_doc, discovery_data, effort_rows)`, which D2 already stopped
    from reading the queue

  `snapshot.errors` joins the TUI's first message, and the plain path prints it. H1
  rebases these changes onto D's `setup.main` launch and rescan and its start facts.
- **`bench.collect`.** `bench.collect(lanes_doc, epoch_rows=None, effort_rows=None)`
  takes rows and gets nothing itself; H1 changes only these inputs, on top of A2's
  evidence-based body. With `epoch_rows=None`, it treats Epoch as having no figures and
  sets `epoch_skipped`, and the report prints "Epoch AI: skipped (...)".
- **The bench CLIs.**
  - `bench.run` and `bench.run_model` read the snapshot.
  - `inspect_model(query, lanes_doc, effort_rows=None, epoch_rows=None)` takes rows and
    builds `LaneEvidence` from them itself.
  - `epoch_records(evidence)` and `evidence_records(evidence)` keep A2's evidence-taking
    signatures; their callers build the evidence from the snapshot's rows.
  - `format_collection(data, snapshot=None, date=None)` prints each source's line from
    its `Origin`.
- **`effort`.** `effort.run_aa` splits in two. `effort.aa_accept(raw, url, out_dir,
  quiet=False)` extracts, writes and checks, and the web adapter calls it. The rest is the
  read-a-file-or-fetch front that the `effort.py aa` CLI keeps.
- **The page and the wizard.** `bench_page.write/render(..., effort_rows=None,
  epoch_rows=None)` takes Epoch rows and lists `LaneEvidence(lanes_doc,
  epoch_rows).records()` in its rows table. `setup_tui.Wizard` takes `epoch_rows` (on top
  of F2) and passes it to `bench_page.write` in `rewrite_bench_page`, and the rescan dict
  carries it.

### Deleted

- **`setup`:**
  - `AA_CACHE_DIR`, `AA_MAX_AGE` and `AA_FIXTURE`
  - `aa_rows_path`, `_with_aa_rows`, `refresh_effort_rows` and `load_effort_rows`
  - `scan`'s `fallback` argument and its five-tuple
  - the `effort_row_paths` threading in `main`
- **`bench`:**
  - `fetch_bytes`, `load_epoch`, `load_effort_rows` and `read_text_file`
  - the `urllib.request`, `csv` and `io` imports
  - `load_epoch_csv_text`, `split_model_version`, `EXPECTED_HEADER` and
    `EXPECTED_FIELDS`, which move into the module as private parts

After the change, `urlopen` appears only in `effort.fetch_page`, and `load_effort_rows`
is defined once.

### Tests

**New: `tests/test_bench_snapshot.py`.** Stdlib only, no network. Each case uses
`web(cache_dir=<tmp>, get=<served>, clock=<fixed>)`, `fixture` or `local` over files in a
temp directory. The pages served are `tests/fixtures/real_aa_model_page_sample.html` and
`tests/fixture/bench-epoch.csv`. The cases:
- A fetch under 24 hours old is not fetched again, and the note gives its age.
- A fetch older than 24 hours is fetched again into the same directory.
- A renew fetches AA now and keeps Epoch's cache.
- A failed fetch keeps the newest copy on hand and says how old it is.
- A failed fetch with nothing cached keeps the named AA rows; Epoch is unavailable while
  the accepted rows stand.
- A fetched CSV without Epoch's header never replaces the cache.
- Named files combine in order, and a bad file refuses every accepted row and is named in
  `errors`.
- The fetched AA rows replace only the named AA rows, so a mixed-source file keeps its
  other rows.
- A fixture directory reads `aa-accepted.json` and `epoch.csv` and calls no `get`.
- A named Epoch CSV without the header is an error, not a note.
- Routing imports no benchmark module. A subprocess imports `rank`, `delegate`, `usage`
  and `report` and finds none of `bench`, `bench_snapshot`, `bench_page` or `effort` in
  `sys.modules`. `lane_evidence` is allowed, because `catalog` imports it for the
  `published_as` check (A).

H1 also adds `bench_snapshot` to the modules `test_model_queue.py`'s "the scan imports no
wizard module" (D2) finds absent.

**Replaced.**
- The five cache cases in `tests/test_setup.py` (`case_a_fresh_fetch_is_not_fetched_again`,
  `case_a_stale_fetch_is_fetched_again`, `case_a_failed_fetch_keeps_the_repo_rows`,
  `case_a_forced_fetch_passes_a_fresh_cache`,
  `case_a_failed_forced_fetch_keeps_the_launch_rows`) and
  `case_effort_rows_from_several_files_combine` become the cases above.
- These read the snapshot: `case_plain_prints_the_start_facts`,
  `case_scan_and_propose_are_the_launch_steps`, the rescan case D2 rewrote ("the save
  after a rescan writes the agent files of the Lanes it saved"; its fake `scan` drops
  `fallback`) and `case_plain_collects_bench_in_process`.
- Every `bench.collect(..., epoch_csv=FIXTURE)` in `test_bench.py`,
  `test_bench_page.py` and `test_setup_tui.py` passes
  `epoch_rows=snapshot((), epoch=local(FIXTURE)).epoch_rows`.
- `test_bench.py`'s `bench.load_epoch(csv_path)` reads through `local`.

**Deleted.** The two in-process `bench.fetch_bytes = boom` patches in `test_bench.py`.
`inspect_model` takes rows and cannot fetch, and the model-CLI subprocess case runs under
the network tripwire instead.

**Network tripwire.** The `make test` recipe points `http_proxy`, `https_proxy`,
`HTTP_PROXY` and `HTTPS_PROXY` at `http://127.0.0.1:9`, with `no_proxy` and `NO_PROXY` set
to `127.0.0.1,localhost`. Any test that reaches the web then fails on every machine, not
only on offline ones. After rebasing onto the other three lanes, H1 runs the whole
`make test` under the tripwire on 3.9 and 3.13 and fixes any `setup.main` case that still
fetches.

### Live bugs fixed and the tests that prove them

Each test fails on the parent commit (red) and passes after the change (green).

1. **Every `r` fetches Epoch live, on the main thread, with no cache.**
   - Test: `case_a_rescan_opens_the_epoch_url_once` in `test_setup.py`.
   - Setup: a driver runs in a subprocess with `HOME` set to a temp directory.
     - It replaces `urllib.request.urlopen` with a fake that serves
       `tests/fixtures/real_aa_model_page_sample.html` for the AA URL and
       `tests/fixture/bench-epoch.csv` for the Epoch URL, and records each URL.
     - It replaces `setup_tui.run_curses` with one that presses enter, then `r`, then
       returns `None`.
     - It runs `setup.main` with `--config-dir` (a copy of
       `tests/fixtures/refresh-2026-09-22/lanes.json`), `--discover-json` (that
       fixture's saved discovery) and `--effort-rows` (its `aa-accepted.json`).
   - Red: the Epoch URL is opened twice.
   - Green: the Epoch URL is opened once, at launch. The AA URL is opened twice.

2. **A `--fixture-dir` or `--no-discover` run reaches the web for Epoch, and an
   unreadable Epoch throws away the AA figures.** Both flags promise no network. When
   Epoch cannot be read, `collect` raises before it reaches AA, the TUI gets no benchmark
   data, and the plain path prints only "bench: cannot read Epoch CSV".
   - Test: `case_a_fixture_run_reaches_no_url` in `test_setup.py`. It runs
     `setup.py --plain` twice:
     - once with `--fixture-dir tests/fixtures/refresh-2026-09-22`;
     - once with `--no-discover` and a saved discovery.

     Both runs use `--effort-rows` (that fixture's `aa-accepted.json`), a copy of its
     `lanes.json`, and every proxy variable pointed at a closed local port.
   - Red: stdout has "bench: cannot read Epoch CSV" and no Artificial Analysis table.
   - Green: exit 0, the AA table renders, the report says "Epoch AI: skipped", and the
     start facts say why.

3. **`make test` reaches the web.** `case_the_refreshed_rows_reach_the_new_lanes` calls
   `bench.collect` with no Epoch CSV, so it downloads the live CSV. Checked on
   2026-10-11: with `urlopen` blocked, it raises "cannot read Epoch CSV".
   - Test: `make test` under the tripwire.
   - Red: `test_setup.py` fails.
   - Green: it passes, with the case passing `epoch_rows=None`.

4. **The page's evidence records never see Epoch rows.**
   - Test: `case_the_page_lists_the_epoch_rows` in `test_setup.py`. It runs `setup.main`
     in-process with `--no-discover`, a saved discovery of every harness,
     `--epoch-csv tests/fixture/bench-epoch.csv` and
     `--effort-rows tests/fixtures/refresh-2026-09-22/aa-accepted.json`. Its
     `run_curses` reads the page at `wizard.bench_page_path`.
   - Red: the "Every row, with its provenance" table has no row with source `epoch`.
   - Green: the table holds the fixture's Epoch rows, with standing and the Epoch cost
     basis.

5. **The report misstates Epoch's source and fails on an outage.** It says Epoch was
   "fetched <report date>" even when it read a local file. It also exits 1 when Epoch is
   down, though the AA rows are in hand. Two tests in `test_bench.py`:
   - `case_the_report_names_the_epoch_file_it_read`: the existing
     `write_epoch_csv(fixture_rows())` fixture with `--date 2026-09-09`. Red: the line
     says "fetched 2026-09-09". Green: it says "read from <file>".
   - `case_an_epoch_outage_still_writes_the_report`: `bench.py --effort-rows <aa rows>`
     with `HOME` set to a temp directory and the closed proxy. Red: exit 1. Green: exit
     0, with the AA table and "Epoch AI: skipped".

6. **Two latent bugs, found by reading the code.**
   - `_with_aa_rows` replaces the whole file that holds any AA row, so a mixed-source
     rows file loses its other sources when AA is fetched.
   - `AA_CACHE_DIR` is expanded at import, so a test that sets `HOME` after importing
     `setup` writes to the real cache.

   Both are gone by construction. The mixed-file case above proves the first.

### ADR notes

ADR 0001 is untouched.
- Routing reads no benchmark data, and a guard test checks it.
- The carry rule is still the only thing that proposes a Lane off. Epoch rows have no
  cost and never reach `carry.decisions`, and the page test asserts that the verdicts and
  plot data are the same with and without them.
- The snapshot names sources and URLs, never a model. It reads no catalog and writes only
  under `~/.cache/delegate/bench/`.
- If the user confirms decisions H.1 and H.2, their lines go into the one ADR change made
  after all lanes merge.

### Risks

- **A builds first in this lane.** A owns attribution and the evidence-based signatures
  of `collect`, `epoch_records`, `evidence_records` and `inspect_model`; H changes only
  their inputs, from paths to rows, and lists A's `records()` on the page, so it needs no
  page-only mapping of Epoch rows.
- **Overlap with F and D.**
  - F (Catalog draft) reshapes `Wizard`. H3 adds one constructor argument, `epoch_rows`,
    which F2 absorbs at H's rebase.
  - D (Catalog commit) cuts `model_queue`'s lazy import of `setup`, which would now also
    load `bench_snapshot` and `effort`. Nothing on the dispatch path calls `snapshot()`.
  - D2 and H1 both change `setup.main`'s launch and rescan, `propose_generation` and the
    start facts; H1 rebases onto D.
- **Start page text.** The rows line now names Epoch too. It stays one line, with no
  layout change. It is TUI text, so it goes to a Claude Opus agent under
  `/frontend-design:frontend-design` (ADR 0001), as D2's queue lines do.
- **User-visible behaviour changes.** These are recorded as decisions H.1 to H.4: the
  Epoch TTL, a stale cache coming before the repo rows, the report no longer exiting on
  an Epoch outage, and offline runs showing no Epoch unless `--epoch-csv` names a file.
- **Epoch URL redirect.** On 2026-10-11 the Epoch URL answered with a 301 to
  `processed_data_for_eci.csv`, and the header still matched. If that target changes
  format, the header check keeps the last good cache and the note says why.
- **Tripwire and local servers.** A future test that needs a local HTTP server must use
  127.0.0.1 or localhost, which the tripwire exempts.

## Verification

Each ticket, and the effort as a whole before its PR is marked ready, passes all three:

- **`make test` on Python 3.9 and 3.13.** Run it with `PYTHON=$(uv python find 3.9)` and
  with `python3.13`, with the proxy variables pointed at a closed local port (H1 makes
  that the recipe's default). Each lane runs it before it merges, and again after its
  rebase.
- **CI.** The PR's checks pass.
- **Review.** The `mattpocock-skills:code-review` skill reviews the effort branch against
  main on both axes, Standards (this repo's documented conventions: `CLAUDE.md`,
  `agents/skills/delegate/CLAUDE.md`, `CONTEXT.md`, ADR 0001) and Spec (this file and the
  tickets in `issues/`). Every finding is fixed or answered before the PR is marked
  ready.
