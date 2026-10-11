# 03 — The statusline counts running Runs through the Run module

**What to build:** Candidate C, ticket C3 (lane run-and-relay). Add
`runs.running(now=None) -> list of Running(lane, run, started, deadline)`. It does the
following:
- reads the Ledger and pairs each start with its finish by thread;
- drops a start past its start plus its timeout;
- drops a start whose run's `dispatch.json` has a `finished_at`, so a lost Ledger finish
  leaves no phantom glyph;
- skips any line that is not a JSON object;
- returns `[]` when the Ledger cannot be read, and never raises.

In `report.cmd_statusline`, replace the inline Ledger parser (`report.py:632-665`) with a
`Counter` over `running(now)`. Delete that parser, its own copy of the Ledger path and its
hard-coded kind strings. The statusline's CLI (`statusline`, `statusline --popup`,
`statusline toggle|on|off`) stays byte-stable, because the dotfiles statusline script, the
Herdr popup and Hammerspoon call it.

Spec: `.scratch/delegate-deepening/spec.md` (C. Run lifecycle; decision C.4)

**Blocked by:** 01 A started Run always finishes

**Status:** landed 2026-10-11. `report.py statusline` now counts its glyphs from `runs.running(now)`, which pairs the Ledger's starts and finishes, bounds each start by its timeout and cross-checks the Run's `dispatch.json`; test_runs 9-11, test_report's in-Run glyph checks and "a Ledger line that is not an object never blanks the statusline" verify it. No box is open.

- [x] test_runs: `running()` lists a Run when asked from inside its work, and is empty after `execute` returns.
- [x] test_runs: a start past its timeout (`now` injected) is not running; a start whose `dispatch.json` is finished is not running even with no Ledger finish.
- [x] test_runs: a Ledger fixture in today's exact v1 lines (open start, stale start, start/finish pair) reads as one running Run.
- [x] Failing first, then green: test_report "a Ledger line that is not an object never blanks the statusline" (fixture Ledger with a `[1]` line and one open start): before this ticket the statusline prints nothing; after, every Meter row prints and the open start shows its glyph.
- [x] test_report runs the statusline from inside a Run's work and sees the tier glyph on the agy row, and none after the Run ends; the hand-written running, stale and finished glyph checks are deleted.
- [x] `report.py statusline`, `statusline --popup` and `statusline toggle` still exit 0 with output.
- [x] `report.py` names neither `DELEGATE_LEDGER` nor `dispatch.start`.
- [x] `make test` is green on 3.9 and 3.13.

## Landed, 2026-10-11

**What shipped.**
- `runs.Running(lane, run, started, deadline)` and `runs.running(now=None)`. `running` does
  the following:
  - reads every Ledger line that is a JSON object and pairs starts with finishes by thread;
  - drops a start once `now` is past its start plus its `timeout_s`;
  - drops a start whose run's `dispatch.json` has a `finished_at`.

  `run` is the directory of the start's `out` (its `return.json`), and `started` is the
  start's `ts` in epoch seconds. A Ledger that cannot be read gives `[]`, and nothing in it
  makes `running` raise.
- `report.cmd_statusline` counts `Counter(r.lane for r in runs.running(now))`. The inline
  parser is gone, with its copy of the Ledger path, its kind strings and the
  `except Exception: return` that blanked every row. `report.py` names neither
  `DELEGATE_LEDGER` nor `dispatch.start`.
- The `runs.py` docstring and `references/architecture.md` describe `running`. `CONTEXT.md`
  is unchanged: its Running and Ledger entries already say what shipped.

**How it was verified.**
- Red first, one slice at a time:
  - test_runs 9, "running lists a Run while its work runs, and not after", failed with no
    `runs.running`.
  - test_runs 10, "a start past its timeout is not running, nor one whose dispatch.json has
    ended", failed on a `running` without the `dispatch.json` cross-check: the Run whose
    Ledger finish was dropped was still listed.
  - test_runs 11, "running reads a Ledger an earlier delegate wrote, and skips lines that are
    not objects", failed on the `[1]` line with `AttributeError`. Its fixture has today's
    exact v1 lines: a meter event, an open start, a stale start and a start/finish pair. It
    also has lines that are not objects, starts with an unreadable `ts`, `timeout_s`, thread
    or lane, and then a missing and an unreadable Ledger. Only the open start is listed.
  - test_report "a Ledger line that is not an object never blanks the statusline" failed on
    the code before this ticket. The statusline exited 0 and printed nothing. Now it prints
    every Meter row, and the agy row carries the open start's ①.
- test_report runs `statusline` and `statusline --no-running` from inside the work of a real
  `flash-high@agy` Run. It sees ① on the agy row and no other running glyph. After the Run
  ends, `statusline` prints exactly the `--no-running` rows.
- Two mutants were each caught:
  - A statusline that counts nothing fails the in-Run glyph check and the `[1]` check.
  - A `running` that ignores finishes and `dispatch.json` fails "no glyph once the Run has
    ended", and test_runs 9-11.
- A direct comparison of the old and new `report.py` matched byte for byte on stdout, stderr
  and the exit code. The fixture Ledger had open, stale and paired starts. It covered
  `statusline` with and without color, `--no-running`, `--popup` with and without color,
  `status`, `toggle` both ways, rows and popup while off, and `on`.
- `make test` is green with every proxy variable pointed at a closed port, on Python 3.9.25
  and 3.13.

**Deviations.**
- `running` reads the Ledger path from `events.ledger_path()`, so the writer and the reader
  share one path. It keeps the two kind strings as private constants in `runs.py`.
  `events.py` still spells them in its encoders until 04 moves those encoders into `runs.py`.
- A start whose `out` is not a string has `run` None and gets no `dispatch.json` check. No
  delegate has written such a start.
- test_report:
  - the hand-written running, stale and finished checks and their Ledger fixture are
    deleted, and stale and finished are now test_runs 10 and 11;
  - `--no-running` now runs inside the work, so it still has a glyph to drop;
  - the toggle check also asserts exit 0;
  - `import runs` sits at the top, with the `sys.path` line moved up from the popup checks.
- Behaviour that changed with no test asking for it:
  - A start with a `timeout_s` that is not a number, or bytes in the Ledger that are not
    UTF-8, used to blank the statusline. Now that start, or that line, is skipped.
  - A pathologically nested line is skipped too.
