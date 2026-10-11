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

**Status:** ready-for-agent

- [ ] A new test_report popup check (copy of the samples with `quota_unit` plan_dollars and sol-high@codex at Tier 4, existing `pp_cache`) fails before this ticket with "cannot lead on Pace" on the Tier 4 codex row and passes with `needs {v:.2f}`, where v is `tier_leaders(...)[3]['pace_to_lead']['codex']` and lies above the axis top.
- [ ] The existing popup checks "needs 0.96 (+0.26)" and "→ luna-low@codex leads after agy drops 18.5 pts" pass unchanged.
- [ ] `report.py statusline`, `statusline --popup` and `statusline toggle` still exit 0 with output.
- [ ] `report.py` defines no `pace_to_lead` and imports no `eligible_order`; the two test_report `pace_to_lead` unit checks are deleted (case 31 covers them).
- [ ] No ranked row carries `veto`; the case 12 key set has `cause` and not `veto`; `gate_only_stop` reads `cause`; test_rank cases 23, 26k, 26l, 26m, 26o and 27 and test_evals assert on `cause`.
- [ ] `make test` is green on Python 3.9 and 3.13.
