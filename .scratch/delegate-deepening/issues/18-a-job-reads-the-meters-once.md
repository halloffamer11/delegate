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

**Status:** ready-for-agent

- [ ] test_dispatch 34d "run --no-probe --dry-run writes no cache and starts no probe" (the offline world with the logging agy stub, no cache) fails on the code before this ticket (rank's acquisition probes) and passes.
- [ ] test_dispatch 34c is rewritten on the logging agy stub: one run probes once before its relay; a dispatch right after it probes only after its relay; a dispatch over a reading an hour old probes before and after.
- [ ] test_dispatch 34 and 34b are rewritten: with `routing.meters` off, run, dispatch and rank start no probe and write no cache; `--no-probe` starts no probe.
- [ ] test_usage freshness cases pass, counted through the internal seam: CACHED never probes; FRESH within its age probes nothing and past it probes once; FORCED with meters off probes nothing and with routing None probes; a FORCED read with `path=P` writes P and not `DELEGATE_CACHE`; a probe past its bound (patched `usage.subprocess.run`) gives the fresh-enough reading or status `stale`.
- [ ] test_usage "a probe writes nothing to the Ledger" passes, and `usage.py` does not import `events`.
- [ ] `rank_range` ranks over a map of Readouts through a private core, and `hash(usage.Snapshot.of(doc))` does not raise.
- [ ] test_rank's re-export, `load_cached_usage`, case 24 and case 25c are deleted.
- [ ] `delegate.py` has no `probed` parameter, and grep finds no `load_usage`, `meter_observations`, `usage_doc` or `usage.acquire`.
- [ ] `make test` passes on Python 3.9 and 3.13.
