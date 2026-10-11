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

**Status:** landed 2026-10-11. usage.py has the read side of the Meters module (`CACHED`, `read`, `Snapshot`, `Readout`, `hold`, `release`, `cache_path`), and rank, the dashboard and `catalog_edit` read each Meter through it, so a usage-limit hold reaches the dashboard and follows the document it overlays; test_usage cases 1 to 7, test_dashboard `test_a_held_meter_is_vetoed_and_its_release_reloads`, test_rank case 30, test_catalog 10.1c and test_dispatch 36 verify it. One box stays open for the lane's builder at the rebase onto run-and-relay: C's test_runs usage-limit case is not on this branch yet, so only the test_dispatch half of the held_until box is done.

- [x] test_dashboard `test_a_held_meter_is_vetoed_and_its_release_reloads` fails on the code before this ticket (grok46-high@grok reads 90% and leads Tier 4) and passes: `usage.hold` beside the fixture cache makes the lane read 0% with reason `vetoed:gate`, and `usage.release` makes `refresh_if_changed()` return True with the lane leading again.
- [x] test_usage "a hold lives beside the document it overlays" (dirs A, B, C; `DELEGATE_CACHE` at C) passes: `hold(path=A)` ends at A's weekly reset, only A reads 0%, `release(path=A)` lifts it; the same fixture through the old `usage.load_cached(A)` shows codex unheld.
- [ ] C's test_runs usage-limit case and the test_dispatch usage-limit wiring case check the hold through `usage.read(None, usage.CACHED).readout('grok', None).held_until`, not `limits.json` or `read_limits`.
- [x] `rank.py` calls neither `usage.eligible` nor `catalog.week_dollars`; every Meter fact in `rank_range` comes from `Snapshot.readout`.
- [x] The dashboard has no `DELEGATE_CACHE` or `CONSULT_CACHE` lookup and does not parse the cache itself; `_load_meters` and `_cached_meters_doc` are gone.
- [x] `usage.mark_limited`, `clear_limited`, `read_limits`, `limits_path` and `catalog.week_dollars` are gone, and nothing imports them.
- [x] `CONTEXT.md`'s Meter snapshot and Usage-limit hold entries match what shipped.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

`usage.py` gained the read side of the Meters module. `read(routing, CACHED, path=...)`
reads the document at `cache_path(path)` (the explicit path, else `$DELEGATE_CACHE`,
else `$CONSULT_CACHE`, else `~/.cache/delegate/usage.json`) with strict JSON, never
probes or writes, catches `Exception` only, and returns a frozen `Snapshot` (`path`,
`status` ok/missing/unreadable/malformed, `detail`, `taken_at`, `signature`, `names()`,
`readout(meter, cat)`); any other freshness raises ValueError. `Snapshot.of(document)`
reads an in-memory document with no holds. `readout` returns a frozen `Readout` with
every field the spec names (`spend` comes in B2): the hold sets Remaining, Pace and the
Weekly figure to 0 and fills `held_until`; `gated` is the Gate (metering on, Remaining
known and under the Gate); `shares_five_h` comes from the catalog flag or the row's
`remaining_weekly_model`; `week_dollars` is the catalog Meter's price per week, kept for
a Meter with no reading. Validation, the legacy `lane` rows, the bare map and the
derived figures sit behind `_parse` and `_filled`; a Snapshot derives a row's missing
figures at `taken_at`. `hold` and `release` write `limits.json` beside the document
read, and `hold` reads that document's weekly reset. `load_cached` and `observations`
stay over the same validity rule and hold overlay until B3. `_WEEK_DAYS`,
`_DAYS_PER_MONTH` and the price arithmetic moved here from `catalog.py`.

`rank.rank_range` takes a Snapshot (a plain document is wrapped with `Snapshot.of`
until B3) and reads Remaining, Pace, the Weekly figure, `gated` and `week_dollars` from
each Lane's Readout. The dashboard model reads `usage.read(None, CACHED, path=...)`,
reports its `status`, `detail` and `taken_at` (the state key stays `probed_at`), watches
its `signature`, and passes it to `rank.tier_leaders` and `catalog_edit.edit_catalog`.
`catalog_edit` takes a Snapshot for `meters` (default `read(None, CACHED)`), and
`_observations_report` reads its `status` and `names()`. `delegate.note_usage_limit`
calls `usage.hold` and `usage.release`.

Verified, red first: on the code before this ticket the dashboard case reads
grok46-high@grok at 90% leading Tier 4 with a hold beside the fixture cache, and
`load_cached(A)` reads codex unheld with a hold at A while `DELEGATE_CACHE` names C;
test_rank 30, test_catalog 10.1c and test_dispatch 36 failed on the old rank, the old
`_observations_report` and the removed `mark_limited`. test_usage covers the hold beside
its document, ticket 43's hold rules (moved out of test_usage_reset), validity, legacy
rows and the bare map, figures derived at `taken_at`, the Readout invariants, the
signature and `cache_path`. `make test` passes on 3.9 and 3.13 with the proxy pointed at
a closed port.

Deviations:
- run-and-relay has not merged, so the hold call site changed is
  `delegate.note_usage_limit`; it moves into `runs.py`'s private hold function at the
  rebase, and C's test_runs usage-limit case gets the `held_until` read then.
- A hold applies only to a Meter with a reading, as before; test_dispatch 36 now writes
  a cache with grok and codex rows so its hold has a row to overlay.
- `Snapshot.signature` is the status, `taken_at`, a digest of the rows and the holds in
  force, not the file bytes, so a hold that expires also reloads the dashboard.
- `catalog_edit` reports `observations: invalid` for a malformed or unreadable cache
  where it said `missing` before; a missing cache still reads `missing`.
- test_usage case 1 keeps the contrast the box names: `load_cached(A)` still reads the
  holds beside the default cache, until B3 deletes it.
- Outside the ticket: test_setup's "the refreshed rows reach the new lanes" called
  `bench.collect` without the Epoch fixture and failed under the closed proxy on the
  base commit; it now passes `tests/fixture/bench-epoch.csv`, as the rules require.
- `CONTEXT.md` is unchanged: its Meter snapshot and Usage-limit hold entries describe
  what shipped. The Meter snapshot entry's "every display reads one" holds in full once
  B2 and B3 move report.py and rank's CLI.
