# 18 — A job reads the Meters once, by freshness, with no probed flag

**What to build:** Candidate B, ticket B3 (lane meters-and-preview). `read` gains FRESH
and FORCED.
- FRESH probes when the reading is older than `max_age_min` (default 10) or absent.
- FORCED probes now.
- Both probe only when the routing's `meters` switch is on, or when routing is None (a
  person's own `delegate status --refresh`).
- The probe runs in the `usage.py` child process with `--cache PATH`, so it writes the
  read's own path, under one 180 s bound. It writes nothing to the Ledger (decision C.2);
  remove `usage.py`'s `events` import if C4 left it. A failed or late probe falls back to
  the last reading only when that reading is fresh enough; otherwise the status is
  `stale`.

Migrate:
- `rank.py` `main`: FRESH for a Class; CACHED for `tiers` or `--meters`.
- `rank_range`, `rank` and `tier_leaders` then take only a Snapshot. `rank_range` builds
  `readouts = {meter: snap.readout(meter, cat)}` and hands that map to a private ranking
  core, so E's what-if can replace one Readout and rerun the core without a second read.
  A Snapshot is never hashed: give its internal maps `field(compare=False, hash=False)`,
  or make it `eq=False`, so `hash(snapshot)` cannot raise.
- `delegate run`: FRESH; CACHED with `--meters` or `--no-probe`.
- dispatch: inside the relayed work that `runs.execute` calls, in this order: the
  preflight, `usage.read(routing, FRESH)`, `relay.run(job, run.path)`,
  `usage.read(routing, FORCED)`, return the Finish. It reads nothing with `--no-probe`.
- `report.py limits`: FRESH with `--max-age-min`; `read(None, FORCED)` with `--refresh`.
- The statusline: CACHED.
- `evals.ping_lane`: `usage.read(cat['routing'], CACHED, path=sandbox.meters)` beside
  G2's `OfflineWorld`, and `Snapshot.of` for the Gate eval.

Tests wrap their documents with `usage.Snapshot.of`; Model meter fixtures keep the
`cycle_left` row key, which the Readout calls `week_left`. test_usage counts probes
through the internal seam that runs the probe child process. test_dispatch 34 to 34d
count probes with a logging agy stub installed through G2's `world.stub`, which appends a
line when called with `/usage`; the fake relay's `hold=` directive separates the probe
before the relay from the one after it.

Delete: `rank.meter_observations`, `run_usage`, `load_cached_usage` and `load_usage`;
`report.usage_doc`; `delegate.probe_meters` and the `probed` parameter of `run`,
`dispatch` and the relayed work, with its comment; and usage's `acquire`, `probe`,
`load_cache`, `load_cached`, `observations` and `eligible` as public names.

Rebase: run-and-relay merges before this lane. If this ticket is built before that
merge, make the dispatch change in `relay_and_map` and the probe-counting change with the
old test world, and move both onto the relayed work and `OfflineWorld` at the rebase.

Spec: `.scratch/delegate-deepening/spec.md` (B. Meters; decisions B.2 and B.5)

**Blocked by:** 16 Every reader of the Meters sees a usage-limit hold, the dashboard included; 17 Every display shows one weekly figure and one Gate per Meter

**Status:** landed 2026-10-11 (e775d2b). `usage.read` reads CACHED, FRESH or FORCED, and probes in the usage.py child with `--cache PATH` under one 180 s bound, writing nothing to the Ledger; `delegate run`, dispatch, `rank.py`, `report.py limits` and `evals.ping_lane` read the Meters through it, so a run probes once before its relay with no `probed` flag, and rank ranks a Snapshot over a map of Readouts. test_usage 9a to 11d, test_dispatch 34 to 34d and test_rank 31 verify it. No box is left open; the dispatch reads moved into the relayed work and the probe counting onto `OfflineWorld` at the merge onto run-and-relay.

- [x] test_dispatch 34d "run --no-probe --dry-run writes no cache and starts no probe" (the offline world with the logging agy stub, no cache) fails on the code before this ticket (rank's acquisition probes) and passes.
- [x] test_dispatch 34c is rewritten on the logging agy stub: one run probes once before its relay; a dispatch right after it probes only after its relay; a dispatch over a reading an hour old probes before and after.
- [x] test_dispatch 34 and 34b are rewritten: with `routing.meters` off, run, dispatch and rank start no probe and write no cache; `--no-probe` starts no probe.
- [x] test_usage freshness cases pass, counted through the internal seam: CACHED never probes; FRESH within its age probes nothing and past it probes once; FORCED with meters off probes nothing and with routing None probes; a FORCED read with `path=P` writes P and not `DELEGATE_CACHE`; a probe past its bound (patched `usage.subprocess.run`) gives the fresh-enough reading or status `stale`.
- [x] test_usage "a probe writes nothing to the Ledger" passes, and `usage.py` does not import `events`.
- [x] `rank_range` ranks over a map of Readouts through a private core, and `hash(usage.Snapshot.of(doc))` does not raise.
- [x] test_rank's re-export, `load_cached_usage`, case 24 and case 25c are deleted.
- [x] `delegate.py` has no `probed` parameter, and grep finds no `load_usage`, `meter_observations`, `usage_doc` or `usage.acquire`.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

Commit: `e775d2b`. The review of candidate B followed in "delegate-deepening B: review
fixes", the next commit on this branch. It made `catalog_edit` take only a Snapshot for
`meters` and gave `read` and the probe child one age rule (`usage._young`).

`usage.read(routing, freshness, path=..., max_age_min=...)` takes CACHED, FRESH and
FORCED. CACHED reads the document as it is. FRESH probes when the reading is older
than `max_age_min` (10) or absent; FORCED probes now. Either probes only when the
routing's `meters` switch is on or the routing is None, and otherwise reads as CACHED.
A probe runs `usage.py --refresh --cache PATH` in a child process (the private seam
`usage._probe`) under one 180 s bound, so it writes the read's own path. A probe that
fails or runs late gives the last reading when that is within `max_age_min`, and
otherwise a Snapshot with status `stale` and every Meter unknown. `usage.py` no longer
imports `events`, and `write_cache` writes nothing to the Ledger. `acquire`, `probe`,
`load_cache`, `load_cached`, `observations` and `eligible` are gone. `usage.main` takes
`argv` and `--cache PATH`, and its JSON (`delegate status --json`) is unchanged.

`rank.rank_range`, `rank` and `tier_leaders` take only a Snapshot and raise TypeError
for a plain document. `rank_range` builds `readouts = {meter: snap.readout(meter, cat)}`
once per Meter and hands it to the private core `_rank_readouts`, which E's what-if can
rerun with one Readout replaced. `rank.py main` reads FRESH for a Class and CACHED for
`tiers` or `--meters`. `meter_observations`, `run_usage`, `load_cached_usage` and
`load_usage` are gone. `delegate run` reads FRESH, or CACHED with `--meters` or
`--no-probe`. `relay_and_map` reads, in order: the preflight, `usage.read(routing,
FRESH)`, the relay, `usage.read(routing, FORCED)`, the mapping. It reads nothing with
`--no-probe`. `probe_meters` and the `probed` parameter of `run`, `dispatch` and
`relay_and_map` are gone. `report.py limits` reads FRESH with `--max-age-min`, and
`read(None, FORCED)` with `--refresh`; `usage_doc` and `meter_snapshot` are gone.
`evals.ping_lane` reads `usage.read(cat['routing'], CACHED, path=sandbox.meters)`.

Verified, red first:
- On the code before this ticket, test_dispatch 34d probed once and wrote the cache,
  and 34c's dispatch right after a run probed before its relay (1/1, not 0/1).
- test_usage's freshness cases failed because there was no probe seam.
- test_rank 31a, which refuses a plain document, and 31c, which reads one Readout per
  Meter and reranks a replaced one through the core, failed on the old `rank_range`.

All of them pass now:
- test_usage 9a to 9i (freshness, counted through `usage._probe` with no harness CLI
  on PATH), 10a (a probe writes nothing to the Ledger), 10b (`usage.py` does not
  import `events`), and 11a to 11d (the bound, through a patched
  `usage.subprocess.run`).
- test_dispatch 34 to 34d, which count probes with a logging agy stub and use the
  fake relay's `hold=`.
- test_rank 31a to 31c, with test_usage 5i for hashing.

`make test` passes on Python 3.9 and 3.13 with the proxy pointed at a closed port.

Deviations:
- run-and-relay has not merged, so the dispatch reads sit in `delegate.relay_and_map`.
  The probe counting uses this file's old test world, with the logging agy stub
  written into its `fake_bin`. `evals.ping_lane` reads beside the old `Sandbox`. All
  three move onto the relayed work, `OfflineWorld` and `world.stub` at the rebase.
- C4 has not merged either. `events.py` keeps `meter_event` and its test_events case
  until C4 deletes them; only `usage.py` stopped writing meter events.
- test_rank case 25d sat in case 25c's block and tested `rank.load_usage` with an
  explicit file, so it went with 25c. The `--meters FILE` CLI cases still cover that
  path.
- test_usage_reset's blocks over the deleted names became test_usage cases or pointers
  to them: 3j, 3k (validity), 4b (a probed figure is never recomputed), 5d2 (a row's
  status never vetoes), 9 (freshness) and 11 (the bound). Its `write_cache` case now
  checks that the write reaches no Ledger. test_usage case 1 lost its `load_cached`
  contrast. What remains is B4's: claude reset parsing, `meter_row`, `write_cache` and
  `get_cache_path`.
- `write_cache` writes through a temporary file and `os.replace`, so a read beside a
  probe never sees half a document.
- `TTL_MIN_DEFAULT` became the private `_MAX_AGE_MIN`; nothing outside `usage.py` used
  it.
- `report.py limits --refresh` hands `--max-age-min` to the FORCED read as the age its
  fallback accepts.
- test_catalog's `EMPTY_METERS` is now `usage.Snapshot.of({})`, and every rank call
  in test_rank, test_catalog, test_evals and test_dashboard that passed a document now
  wraps it with `usage.Snapshot.of`. `catalog_edit` still accepted a plain document for
  `meters`, as ticket 16 left it, until the review made it refuse one.
- `references/routing.md` says a run reads the Meters fresh and probes after it
  finishes, and `references/architecture.md` describes the freshness reads and rank's
  Readout map. `CONTEXT.md` is unchanged: its Freshness and Meter snapshot entries
  match what shipped.

## Merged onto run-and-relay, 2026-10-11

The merge commit "delegate-deepening: merge the meters-and-preview lane" put the reads
inside the relayed work that `runs.execute` calls: `delegate.relay_work` runs the
preflight, `usage.read(routing, FRESH)`, `relay.run(job, run.path)`,
`usage.read(routing, FORCED)` and returns the Finish, and reads nothing with
`--no-probe`. `relay_work` and `dispatch` lost `probed` beside G3's `relay` parameter,
and `probe_meters` is gone. test_dispatch 34 to 34d run in G2's `OfflineWorld`, with the
logging agy stub installed through `world.stub` and put back after 34d. Reading FORCED
before the relay turns 34c red. `evals.ping_lane` reads
`usage.read(cat['routing'], CACHED, path=sandbox.meters)` beside `OfflineWorld`.
