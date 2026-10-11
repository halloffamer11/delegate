# 19 — Harness probes hand the Meters module their Windows, and usage.py exposes only its interface

**What to build:** Candidate B, ticket B4 (lane meters-and-preview, the last B ticket).
`harnesses/base.py` gains `Windows` (meter, group, five_h, weekly, reset_5h,
reset_weekly, note, weekly_model), `Harness.windows(group, ...)`,
`Harness.meter_name(group)`, and the probe helpers `run_cli` and `iso_time`, moved from
usage's `run` and `iso`. Every adapter's `read_meters` (claude, codex, agy, grok, and the
base absent and no-source rows) returns Windows, and no adapter imports usage.
`usage.py` builds the rows from Windows: it holds fractions to 0..1 and derives the
combined figures. `usage.py --pretty` prints one line per Meter from Readouts (decision
B.4). `model_queue.path()` uses `usage.cache_path()`.

Export `usage.MAX_PACE = 1 / CYCLE_FLOOR` (50 today), the highest Pace a Meter can read,
as a public name; E2 reads it. Delete usage's `meter_row`, `meter_name`, `row_meter`,
`remaining`, `run`, `iso`, `combined` and `write_cache` as public names, and `CACHE`.
Delete `tests/test_usage_reset.py`: claude reset parsing moves to `test_harnesses.py`, and
everything else is already in `test_usage.py`. Update the usage section of
`references/architecture.md`.

Spec: `.scratch/delegate-deepening/spec.md` (B. Meters; decision B.4)

**Blocked by:** 18 A job reads the Meters once, by freshness, with no probed flag

**Status:** ready-for-agent

- [ ] test_harnesses "a probe hands back Windows without importing usage" (a fake agy CLI on PATH printing the two-group `/usage` JSON, run in a subprocess) fails on the code before this ticket and passes: Windows named agy-gemini and agy-claude-gpt, and `usage` absent from `sys.modules`.
- [ ] test_usage "usage.py --pretty prints one line per Meter" (a fresh cache with rows in the current shape, `--max-age-min 60`) fails on the code before this ticket with `KeyError: 'lane'` and passes.
- [ ] test_usage "an overspent Window reads as nothing left" (in-process `usage.main(['--refresh', '--cache', p])` with the claude adapter patched to return `Windows(five_h=-0.04, weekly_model=1.2)`) passes.
- [ ] `grep -rn 'import usage'` finds nothing under `scripts/harnesses`.
- [ ] `usage.py`'s public names are exactly CACHED, FRESH, FORCED, MAX_PACE, read, hold, release, cache_path, Snapshot, Readout and main; `usage.MAX_PACE` is 50 with today's cycle floor; `tests/test_usage_reset.py` is gone.
- [ ] `make test` passes on Python 3.9 and 3.13.
