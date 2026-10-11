# 17 — Every display shows one weekly figure and one Gate per Meter

**What to build:** Candidate B, ticket B2 (lane meters-and-preview). Add `spend` to
`Snapshot.readout` and test it in test_usage. Render every display's Meter facts from
Readouts:
- The statusline and the popup: `popup_meters` and `popup_lines`. `report.handover` keeps
  its own stepping loop and arithmetic; E4 moves it into rank on `readout(spend=)`.
- `delegate status` (`report.py limits`): the table, plan consumption from
  `week_dollars`, `--eligible` from `gated`, the Meters with no probe row, and a new line
  naming each held Meter and when its hold ends.
- The deck: Remaining colour and the Gate/Margin aid read each state row's `gated`, which
  the dashboard model takes from the readout.

A Model meter's Weekly figure is the lower of its own week and the harness's week for all
models on every surface. The popup legend reads "weekly figure". The statusline's CLI
(`statusline`, `statusline --popup`, `statusline toggle|on|off`) keeps its invocations,
because the dotfiles statusline script, the Herdr popup and Hammerspoon call it.

Delete from `report.py`: `WEEK_DAYS`, `DAYS_PER_MONTH`, `CACHE`, both `shares5`
derivations, the swap to `remaining_weekly_model`, and the `left` recomputation. Delete
deck's two `remaining < gate` comparisons. `CONTEXT.md`'s sharpened Model meter entry and
its Weekly figure entry were added with the spec; keep them true to what ships. Update
the hold sentence in `references/routing.md` to name the line that `delegate status`
prints.

Spec: `.scratch/delegate-deepening/spec.md` (B. Meters; decision B.1)

**Blocked by:** 16 Every reader of the Meters sees a usage-limit hold, the dashboard included

**Status:** ready-for-agent

- [ ] test_report "statusline and popup print one weekly figure per Meter" (fixture `pp_usage.json`: claude-fable `remaining_weekly` 0.46, `remaining_weekly_model` 0.59) fails on the code before this ticket (59% against 46%) and passes, with every Meter's statusline percentage equal to its popup "= W ÷ L" numerator.
- [ ] The check "statusline fable shows remaining_weekly_model" is replaced by "statusline fable shows its Weekly figure" (46%·4d), and the renamed-meter checks still pass.
- [ ] test_report "status names a held Meter and when its hold ends" (a fresh cache plus `usage.hold('grok', ...)` beside it) fails on the code before this ticket and passes.
- [ ] test_dashboard `test_meters_off_draws_no_meter_under_the_gate` (routing `meters` false, codex-a at 5%) fails on the code before this ticket and passes: `deck.meter_verdict` does not say "under the Gate" and `remaining_color` is not the veto colour.
- [ ] test_usage covers `readout(spend=x)`: weekly and Remaining fall by x, Pace follows, `gated` is recomputed, and a held Meter stays at 0.
- [ ] The popup check "→ luna-low@codex leads after agy drops 18.5 pts" still passes, and `report.handover`'s loop is left for E4.
- [ ] `report.py statusline`, `statusline --popup` and `statusline toggle` still exit 0 with output.
- [ ] grep finds `WEEK_DAYS` and `DAYS_PER_MONTH` only in `usage.py`, as private names.
- [ ] `CONTEXT.md`'s Model meter and Weekly figure entries match what shipped.
- [ ] `make test` passes on Python 3.9 and 3.13.
