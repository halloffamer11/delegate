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

**Status:** landed 2026-10-11. Every display draws each Meter from its Readout, so a Model meter shows one Weekly figure everywhere, `delegate status` names each held Meter, and the deck draws only the Gate rank applies; `Snapshot.readout` takes `spend=`. test_report "statusline and popup print one weekly figure per Meter" and "status names a held Meter and when its hold ends", test_dashboard `test_meters_off_draws_no_meter_under_the_gate` and test_usage case 8 verify it. No box is left open.

- [x] test_report "statusline and popup print one weekly figure per Meter" (fixture `pp_usage.json`: claude-fable `remaining_weekly` 0.46, `remaining_weekly_model` 0.59) fails on the code before this ticket (59% against 46%) and passes, with every Meter's statusline percentage equal to its popup "= W ÷ L" numerator.
- [x] The check "statusline fable shows remaining_weekly_model" is replaced by "statusline fable shows its Weekly figure" (46%·4d), and the renamed-meter checks still pass.
- [x] test_report "status names a held Meter and when its hold ends" (a fresh cache plus `usage.hold('grok', ...)` beside it) fails on the code before this ticket and passes.
- [x] test_dashboard `test_meters_off_draws_no_meter_under_the_gate` (routing `meters` false, codex-a at 5%) fails on the code before this ticket and passes: `deck.meter_verdict` does not say "under the Gate" and `remaining_color` is not the veto colour.
- [x] test_usage covers `readout(spend=x)`: weekly and Remaining fall by x, Pace follows, `gated` is recomputed, and a held Meter stays at 0.
- [x] The popup check "→ luna-low@codex leads after agy drops 18.5 pts" still passes, and `report.handover`'s loop is left for E4.
- [x] `report.py statusline`, `statusline --popup` and `statusline toggle` still exit 0 with output.
- [x] grep finds `WEEK_DAYS` and `DAYS_PER_MONTH` only in `usage.py`, as private names.
- [x] `CONTEXT.md`'s Model meter and Weekly figure entries match what shipped.
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

`usage.Snapshot.readout(meter, cat, spend=x)` answers what a Meter would read with x
more of its week spent: the Weekly figure falls by x (never below 0), Remaining is the
lower of the 5h Window and that, Pace is that over `week_left`, and `gated` is asked
again; a held Meter stays at 0, `spend=0` is the reading itself, and a spend outside
0..1 (or a bool or NaN) raises ValueError.

`report.py` draws every Meter fact from Readouts. The statusline reads
`usage.read(None, CACHED)` and ranks over that Snapshot; each row's 5h cell, weekly cell,
✗ and blank 5h for a Model meter come from `weekly`, `five_h`, `gated` and
`shares_five_h`, so the fable row shows its Weekly figure (46%, not the model's own 59%).
`popup_meters` builds the popup's Meter rows from the same Readouts, `week_left` included,
and the legend reads "Pace = weekly figure ÷ share of the week left". `report.handover`
keeps its loop and arithmetic for E4. `limits` (`delegate status`) lists the Meters of
the Snapshot: the table from `weekly`, `five_h` and the resets, `--eligible` from
`gated`, plan consumption from `week_dollars`, the Meters with no probe row from the
Readouts, and a new line, `Usage-limit hold: grok until Oct 12 06:25 (1d).`, naming
each held Meter and when its hold ends. Deleted from `report.py`: `WEEK_DAYS`,
`DAYS_PER_MONTH`, `CACHE`, both `shares5` derivations, the swap to
`remaining_weekly_model` and the `left` recomputation. The dashboard model gives each
state row `gated` from `meters.readout(meter, effective)`; `deck.remaining_color`,
`deck.meter_rows` and `deck.meter_verdict` read it, and deck's two `remaining < gate`
comparisons are gone.

Verified, red first: test_usage case 8 failed with `TypeError` on `spend`; test_report
"statusline and popup print one weekly figure per Meter" read fable 59% against the
popup's 46%, "statusline fable shows its Weekly figure" read 59%·4d, and "status names a
held Meter and when its hold ends" found no hold line; test_dashboard
`test_meters_off_draws_no_meter_under_the_gate` read "under the Gate" with metering off.
All pass now, with the popup's "→ luna-low@codex leads after agy drops 18.5 pts" and the
renamed-meter checks. A new test_report check runs `statusline`, `statusline --popup` and
`statusline toggle` and sees each exit 0 with output. `make test` passes on Python 3.9
and 3.13 with the proxy pointed at a closed port.

Deviations:
- `limits` still acquires through `report.usage_doc` until ticket 18 reads FRESH; a new
  `meter_snapshot` then reads the cache that acquisition left with
  `usage.read(None, CACHED)`, so the holds beside it come along. An acquisition that
  found nothing valid still reads as no Meters, as before.
- `readout(spend=)` leaves Pace unknown when the reading has no `week_left`, and does
  not round the Pace it computes.
- With metering off the deck's aid says "Gate inactive" (muted) for a Meter it used to
  draw under the Gate; the watch colour (Remaining under twice the Gate, or Pace under
  0.5) still applies.
- The statusline prints rows for any Snapshot whose status is ok, so a legacy bare-map
  cache, which no probe writes, now draws rows where it drew none.
- test_dashboard's row-keys check gains `gated`.
- `CONTEXT.md`'s Model meter entry now says a probe row that carries the model's own
  week marks a Model meter too, as `shares_five_h` reads it; the Weekly figure entry is
  unchanged. `references/routing.md` names the `Usage-limit hold:` line, and
  `references/architecture.md` and the dashboard's `CLAUDE.md` gained one sentence each.
- Decision B.1 reverses one acceptance box of redesign ticket 23; its ADR 0001 line
  still waits for the user's word in the one ADR change after all lanes merge.
