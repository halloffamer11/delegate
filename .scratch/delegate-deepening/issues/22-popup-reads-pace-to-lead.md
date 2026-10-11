# 22 — The popup shows the Pace to lead rank gives, even past its axis

**What to build:** Candidate E, ticket E3 (lane meters-and-preview). `report.popup_lines`
and `tier_block` read each Tier's `pace_to_lead` and each row's `cause` from
`tier_leaders`, and scale the axis from Meter Paces and Paces to lead instead of the
leader's Pace plus the Margin. A Pace to lead past the axis is shown as its value, with
the dot clamped at the axis edge. Delete `report.pace_to_lead` and the popup's `steals`
list. "cannot lead on Pace" now means only that no readable Pace (up to
`usage.MAX_PACE`) leads.

Replace the row field `veto` with `cause` everywhere: `rank_range` stops writing `veto`,
`gate_only_stop` and `report.tier_block` read `cause`, and the test assertions on `veto`
in test_rank and test_evals read `cause`. Document `cause` in place of `veto` in
`references/routing.md`. The statusline's CLI (`statusline`, `statusline --popup`,
`statusline toggle|on|off`) keeps its invocations.

Spec: `.scratch/delegate-deepening/spec.md` (E. Routing preview; decisions E.1 and E.2)

**Blocked by:** 21 The deck's aid marks the Pace rank says each Meter needs to lead

**Status:** landed 2026-10-11 (db5716b; its last box closed with ticket 23 in bec3ba5). The popup reads each Tier's `pace_to_lead` and each row's `cause` from `tier_leaders`, scales its Pace axis from Meter Paces and Paces to lead, and prints a Pace to lead past the axis as its value; ranked rows carry `cause` and no `veto`. test_report's popup checks "with plan dollars gives a rival past the Meters' axis its Pace to lead", "scales its axis to reach the Paces to lead" and "shows a Pace to lead past the axis as its value, its mark at the edge", and test_rank case 12, verify it. Ticket 23 closed its last box when it deleted `report.handover` and the `eligible_order` import.

- [x] A new test_report popup check (copy of the samples with `quota_unit` plan_dollars and sol-high@codex at Tier 4, existing `pp_cache`) fails before this ticket with "cannot lead on Pace" on the Tier 4 codex row and passes with `needs {v:.2f}`, where v is `tier_leaders(...)[3]['pace_to_lead']['codex']` and lies above the axis top.
- [x] The existing popup checks "needs 0.96 (+0.26)" and "→ luna-low@codex leads after agy drops 18.5 pts" pass unchanged.
- [x] `report.py statusline`, `statusline --popup` and `statusline toggle` still exit 0 with output.
- [x] `report.py` defines no `pace_to_lead` and imports no `eligible_order`; the two test_report `pace_to_lead` unit checks are deleted (case 31 covers them).
- [x] No ranked row carries `veto`; the case 12 key set has `cause` and not `veto`; `gate_only_stop` reads `cause`; test_rank cases 23, 26k, 26l, 26m, 26o and 27 and test_evals assert on `cause`.
- [x] `make test` is green on Python 3.9 and 3.13.

## Landed, 2026-10-11

Commits: db5716b, and bec3ba5 (ticket 23) for the last box.

Review, 2026-10-11: the commit "delegate-deepening E: review fixes" renames
`report.track`'s `steal` argument to `need`, since the ┊ it draws is the Pace to lead.

`report.popup_lines` scales the Pace axis from each Meter's Pace and every Pace to lead
the Tier previews give, up to `pace_axis`'s cap of 8. The popup's `steals` list (the
leader's Pace plus the Margin) is gone. `tier_block` filters and marks rows by `cause`:
it keeps every row but disabled, floor and ceiling, and draws gate and cli as before.
Each other Meter's row reads its Pace to lead from the preview's `pace_to_lead`. It says
"needs X (+d)" for a value, and "cannot lead on Pace" only for None, where no Pace up to
`usage.MAX_PACE` leads. A Meter with no key (the leader's, or one with an unknown Pace)
gets no note. A Pace to lead past the cap keeps its value in the note, and its ┊ mark
sits on the axis's last cell, because the axis's cell function clamps. `report.pace_to_lead`
is deleted, along with the two test_report unit checks that called it; test_rank case 33
(the spec's case 31) covers the Pace to lead.

`rank_range` no longer writes `veto`. `cause` carries the veto kind, and `gate_only_stop`
reads it. test_rank case 12's key set drops `veto`. Cases 23b, 26k, 26l, 26m, 26o and
27 and test_evals' Gate check assert on `cause`. `references/routing.md` says rows carry
no `veto` field because `cause` replaced it, and that the popup prints a Pace to lead
past its axis as it is. `references/architecture.md` says the usage popup draws the
preview's facts too.

Verified, red first. With a copy of the samples under plan dollars, sol-high@codex at
Tier 4 and the existing `pp_cache`, the Tier 4 codex row read "cannot lead on Pace" on
an axis that ended at 3, while rank's preview gives codex 4.03. It now reads
"needs 4.03 (+3.33)", and the axis runs to 5. With fable's Weekly figure at 90% and
three days left, codex needs 10.51. The row read "cannot lead on Pace"; it now reads
"needs 10.51" with the ┊ on the last cell of an axis that ends at 8. test_rank case 12
failed on the `veto` key before `rank_range` dropped it; the other `cause` assertions
already held, because ticket 20 put the veto kind in `cause`. The checks "needs 0.96
(+0.26)", "→ luna-low@codex leads after agy drops 18.5 pts" and the statusline CLI check
(`statusline`, `--popup`, `toggle`) pass unchanged. On the shipped samples with the popup
fixture, `statusline` and `statusline --popup` (no colour at 118 and 90 columns, and
colour at 118) print the same bytes as before this ticket. `make test` passes on Python
3.9 and 3.13 with the proxy pointed at a closed port.

Deviations:
- The box's fixture gives codex a Pace to lead of 4.03. That lies above the axis top
  before this ticket (3), not above the new one. The new axis reaches the Paces to lead,
  as the ticket asks, so its top is 5. Two more checks cover the rest of the box. One
  shows that the axis reaches the Pace to lead. The other moves the Pace to lead past
  the axis's cap (fable at 90% with three days left), so it lies above the axis top as
  drawn: it is printed as its value, with its mark on the edge.
- `report.py` still imports `eligible_order`, which the spec lists among E4's
  deletions. `report.handover` sorts its trial rows with it and has no other way to
  replay rank's order. Ticket 23 deletes `report.handover`, so its text now names the
  `eligible_order` import beside `choose`. The fourth box stays open until then. Its
  other two parts are met: `report.py` defines no `pace_to_lead`, and the two unit
  checks are deleted.
- The remaining handover unit checks' `lane_row` fixture carries `cause: eligible` in
  place of `veto: None`. `report.handover` reads neither.
- `CONTEXT.md` is unchanged. Its Tier preview entry says the popup only draws the
  preview. That now holds for the Cause and the Pace to lead. The Handover is still
  computed in `report.py` until ticket 23.
