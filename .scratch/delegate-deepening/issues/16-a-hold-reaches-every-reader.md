# 16 — Every reader of the Meters sees a usage-limit hold, the dashboard included

**What to build:** Candidate B, ticket B1 (lane meters-and-preview, its first ticket).
Add the read side of the Meters module to `usage.py`: `CACHED`,
`read(routing, CACHED, path=...)`, `Snapshot` (`of`, `path`, `status`, `detail`,
`taken_at`, `signature`, `names`, `readout(meter, cat)`), `Readout` (every field; the
`spend` argument comes in B2), `hold`, `release` and `cache_path`. Validation, the legacy
row upgrade, derived figures and the hold overlay move behind `read` and `Snapshot.of`.
`read` catches at most `Exception`, never `BaseException`. The hold file is always the
one beside the document that was read, and `hold` reads that document's weekly reset.
`load_cached` and `observations` remain over the same private overlay only until B3.

Move `catalog.py`'s `WEEK_DAYS`, `DAYS_PER_MONTH` and `week_dollars` into `usage.py`, the
constants as private `_WEEK_DAYS` and `_DAYS_PER_MONTH`, the price behind
`Readout.week_dollars`. `rank.rank_range` reads each Lane's Meter through
`Snapshot.readout`: Remaining, Pace, Weekly figure, `gated` and `week_dollars`. Until B3
it wraps a plain document with `Snapshot.of`.

The dashboard model reads `usage.read(None, usage.CACHED, path=...)`, reports its
`status`, `detail` and `taken_at`, watches `Snapshot.signature` so that a hold written or
lifted beside the cache reloads the view, and passes the Snapshot to `rank.tier_leaders`
and to `catalog_edit.edit_catalog`. `catalog_edit` accepts a Snapshot for `meters`.

The Meter hold's one call site calls `usage.hold` and `usage.release`. After
run-and-relay merges (it merges first) that call site is the one private hold function in
`runs.py` (C1); if this lane is built before that merge, change
`delegate.note_usage_limit` and move the change into `runs.py` at the rebase.

Start `tests/test_usage.py` with cases at the new interface. `CONTEXT.md`'s Meter snapshot
and Usage-limit hold entries were added with the spec; keep them true to what ships.

Spec: `.scratch/delegate-deepening/spec.md` (B. Meters; decision B.3)

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] test_dashboard `test_a_held_meter_is_vetoed_and_its_release_reloads` fails on the code before this ticket (grok46-high@grok reads 90% and leads Tier 4) and passes: `usage.hold` beside the fixture cache makes the lane read 0% with reason `vetoed:gate`, and `usage.release` makes `refresh_if_changed()` return True with the lane leading again.
- [ ] test_usage "a hold lives beside the document it overlays" (dirs A, B, C; `DELEGATE_CACHE` at C) passes: `hold(path=A)` ends at A's weekly reset, only A reads 0%, `release(path=A)` lifts it; the same fixture through the old `usage.load_cached(A)` shows codex unheld.
- [ ] C's test_runs usage-limit case and the test_dispatch usage-limit wiring case check the hold through `usage.read(None, usage.CACHED).readout('grok', None).held_until`, not `limits.json` or `read_limits`.
- [ ] `rank.py` calls neither `usage.eligible` nor `catalog.week_dollars`; every Meter fact in `rank_range` comes from `Snapshot.readout`.
- [ ] The dashboard has no `DELEGATE_CACHE` or `CONSULT_CACHE` lookup and does not parse the cache itself; `_load_meters` and `_cached_meters_doc` are gone.
- [ ] `usage.mark_limited`, `clear_limited`, `read_limits`, `limits_path` and `catalog.week_dollars` are gone, and nothing imports them.
- [ ] `CONTEXT.md`'s Meter snapshot and Usage-limit hold entries match what shipped.
- [ ] `make test` passes on Python 3.9 and 3.13.
