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

**Status:** ready-for-agent

- [ ] test_runs: `running()` lists a Run when asked from inside its work, and is empty after `execute` returns.
- [ ] test_runs: a start past its timeout (`now` injected) is not running; a start whose `dispatch.json` is finished is not running even with no Ledger finish.
- [ ] test_runs: a Ledger fixture in today's exact v1 lines (open start, stale start, start/finish pair) reads as one running Run.
- [ ] Failing first, then green: test_report "a Ledger line that is not an object never blanks the statusline" (fixture Ledger with a `[1]` line and one open start): before this ticket the statusline prints nothing; after, every Meter row prints and the open start shows its glyph.
- [ ] test_report runs the statusline from inside a Run's work and sees the tier glyph on the agy row, and none after the Run ends; the hand-written running, stale and finished glyph checks are deleted.
- [ ] `report.py statusline`, `statusline --popup` and `statusline toggle` still exit 0 with output.
- [ ] `report.py` names neither `DELEGATE_LEDGER` nor `dispatch.start`.
- [ ] `make test` is green on 3.9 and 3.13.
