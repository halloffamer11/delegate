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

**Status:** landed 2026-10-11 (6b17a70). Each adapter's probe hands back `harnesses.base.Windows` and imports no usage, and `usage.py` builds the rows from them, prints `--pretty` from Readouts and exposes only its interface, `MAX_PACE` included. test_harnesses "a probe hands back Windows without importing usage" and "no adapter imports usage", and test_usage 12 (`--pretty`), 13a and 13b (rows from Windows) and 14a and 14b (the public names and `MAX_PACE`) verify it. No box is left open.

- [x] test_harnesses "a probe hands back Windows without importing usage" (a fake agy CLI on PATH printing the two-group `/usage` JSON, run in a subprocess) fails on the code before this ticket and passes: Windows named agy-gemini and agy-claude-gpt, and `usage` absent from `sys.modules`.
- [x] test_usage "usage.py --pretty prints one line per Meter" (a fresh cache with rows in the current shape, `--max-age-min 60`) fails on the code before this ticket with `KeyError: 'lane'` and passes.
- [x] test_usage "an overspent Window reads as nothing left" (in-process `usage.main(['--refresh', '--cache', p])` with the claude adapter patched to return `Windows(five_h=-0.04, weekly_model=1.2)`) passes.
- [x] `grep -rn 'import usage'` finds nothing under `scripts/harnesses`.
- [x] `usage.py`'s public names are exactly CACHED, FRESH, FORCED, MAX_PACE, read, hold, release, cache_path, Snapshot, Readout and main; `usage.MAX_PACE` is 50 with today's cycle floor; `tests/test_usage_reset.py` is gone.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

Commit: `6b17a70`. The review of candidate B followed in "delegate-deepening B: review
fixes", the next commit on this branch. It replaced the TTL wording in `usage.py`'s
usage text with the age in minutes.

`harnesses/base.py` has the harness port:
- `Windows`, a NamedTuple of meter, group, five_h, weekly, reset_5h, reset_weekly, note
  and weekly_model. Its figures are what the CLI reported, before any arithmetic.
- `Harness.windows(group, ...)` and `Harness.meter_name(group)`.
- The probe helpers `run_cli` and `iso_time`, moved from usage's `run` and `iso`.

`meters()`, the base `read_meters` and the claude, codex, agy and grok adapters return
Windows. That includes the `absent`, `probe failed` and `no usage source` cases. No
adapter imports usage, and agy's `lane_meter` uses `meter_name`.

`usage.py` builds each row from a Windows in `_row`. It holds each fraction to 0..1 and
derives the combined figures at the reading's `probed_at`. The rows keep the shape they
had, so `delegate status --json` is unchanged.

`usage.py --pretty` prints one line per Meter from its Readout: Pace, Remaining, the 5h
Window, the Weekly figure, the binding Window and its reset, a held, unknown or ok
state, and the note. The usage-limit hold is applied.

Public names and deletions:
- `usage.MAX_PACE = 1 / _CYCLE_FLOOR` (50) is public.
- `meter_row`, `meter_name`, `row_meter`, `remaining`, `run`, `iso`, `combined`,
  `write_cache`, `get_cache_path` and `CACHE` are gone as public names. The helpers that
  remain are private.
- `model_queue.path()` uses `usage.cache_path()`.
- `tests/test_usage_reset.py` is deleted.

Verified, red first:
- Before this ticket, test_harnesses "a probe hands back Windows without importing
  usage" failed. A fake agy CLI on PATH, run in a subprocess, gave row dicts and left
  `usage` in `sys.modules`. "no adapter imports usage" named agy, base, claude, codex
  and grok.
- test_usage 12 failed on the old `--pretty` with `KeyError: 'lane'`.
- test_usage 14a listed the 13 extra public names, and 14b found no `MAX_PACE`.
- test_usage 13a and 13b could not build Windows.

All of them pass now. So do test_harnesses `test_claude_reset` (moved from
test_usage_reset) and the agy note case. test_harnesses and test_catalog 18 now read
Windows fields where they read row dicts. `grep -rn 'import usage' scripts/harnesses`
finds nothing. `make test` passes on Python 3.9 and 3.13 with the proxy pointed at a
closed port.

Deviations:
- The overspent case builds its Windows with `claude.windows("fable", five_h=-0.04,
  weekly=0.7, weekly_model=1.2)`, beside a general and a second Model meter Windows.
  A Windows needs its meter and group; the box's `Windows(five_h=-0.04,
  weekly_model=1.2)` names only the figures. The case patches the claude adapter's
  `installed` and `read_meters`, with no other CLI on PATH.
- The Model meter's weekly rule moved from the claude adapter into `usage._row`, which
  the spec lists among what the Meters module hides. The adapter reports `weekly` as
  the week for all models and `weekly_model` as the model's own week. `usage.py`
  writes the lower of the two as `remaining_weekly` (decision B.1) and keeps the own
  week in `remaining_weekly_model`, so the rows do not change. test_usage 13b pins the
  rule, and test_harnesses pins what claude reports.
- `WEEK`, `CYCLE_FLOOR` and `ROLLOVER_MIN` became private, because the public names
  must be exactly the eleven. Nothing outside `usage.py` read them.
- A probe's rows take their combined figures at the one moment the document records as
  `probed_at`, not each at the moment its own row was built.
- `--pretty` drops the ROLLOVER-SOON flag: no probe ever set `rollover_soon`. The rows
  still carry it as false.
- test_usage_reset's other blocks were covered already: the cache path (test_usage 7),
  the Ledger (10a), the derived figures and one arithmetic for agy (4), and a row's
  status (5d2). Its overspent block is now test_usage 13a.
- Ticket 04 (C4, run-and-relay) still names test_usage_reset's meter-event assertions.
  Ticket 18 removed them, and the file is now gone, so C4 has nothing to remove there
  at the rebase.
- `references/architecture.md` describes the harness port, the rows built from Windows,
  usage's public names and `--pretty`. `CONTEXT.md` is unchanged: its Window, Model
  meter and Weekly figure entries match what shipped.
