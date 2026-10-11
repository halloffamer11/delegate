# 20 — The deck codes every Lane by the cause rank gives it

**What to build:** Candidate E, ticket E1 (lane meters-and-preview, after B3). Make
`rank_range` write a machine-readable `cause` on every row, from B3's private ranking
core. The values are pick, steal (the Pick that took the job by the Margin, in either
quota unit), eligible, unknown (no value to rank by), and the veto kinds disabled, floor,
ceiling, gate and cli. Keep the `reason` text as display only, and add the Cause
vocabulary to `rank.py`'s docstring.

The dashboard model copies `cause` into each state row, and `_build_state` and
`_fresh_carried_lane_names` filter disabled Lanes on `cause` instead of parsing `reason`.
`deck.reason_code` maps `cause` to its code through a table, with VETO for an unknown
cause, and never reads `reason`. The STEAL and NOMTR descriptions become unit-neutral.
With Meters off, a Lane with no reading follows rank's cause (ELIG), not NOMTR.

This fixes the deck's plan-dollars steal shown as ELIG (and the aid's "no Tier it can
take" for the Meter that holds the Tier) and its CLI veto shown as NOMTR when the Meter
has no reading. `CONTEXT.md`'s Cause entry was added with the spec; keep it true to what
ships, and name `cause` in `references/routing.md`. Test fixtures that rank pass
`usage.Snapshot.of` documents.

Spec: `.scratch/delegate-deepening/spec.md` (E. Routing preview; decision E.3)

**Blocked by:** 18 A job reads the Meters once, by freshness, with no probed flag (rank takes a Snapshot and ranks over a map of Readouts)

**Status:** landed 2026-10-11 (f08b47b). Every row from `rank_range`, `rank` and `tier_leaders` carries one `cause` from `rank.CAUSES`, the dashboard copies it into its state and filters disabled Lanes on it, and `deck.reason_code` maps it to a code through `CAUSE_CODES`, so a plan-dollars steal reads STEAL and a Lane with no CLI and no reading reads CLI. test_rank case 32 (the spec's case 30, renumbered) and test_dashboard `test_a_plan_dollars_steal_reads_as_a_steal`, `test_a_lane_without_its_cli_or_a_reading_reads_as_cli` and `test_with_meters_off_a_lane_without_a_reading_follows_rank` verify it. No box is left open.

- [x] test_dashboard `test_a_plan_dollars_steal_reads_as_a_steal` (`quota_unit` plan_dollars, `write_meters` a_pace=0.5, b_pace=0.65) fails before this ticket with ELIG and "no Tier it can take" for codex-b, and passes with STEAL and "holds the Pick in T2".
- [x] test_dashboard `test_a_lane_without_its_cli_or_a_reading_reads_as_cli` (present without grok, no grok row in the meters document) fails before this ticket with NOMTR and passes with CLI.
- [x] test_rank case 30 (shipped as case 32): every row from `rank_range`, `rank` and `tier_leaders` carries a cause from `CAUSES`; on the case 20, 13, sample impl and 29b fixtures the causes are steal, eligible, gate, unknown, cli, disabled, floor, ceiling and plan-dollars steal as specified.
- [x] On every row, `eligible` is true exactly for pick, steal, eligible and unknown, and `pick` is true exactly for pick and steal.
- [x] `deck.py` and `model.py` contain no `startswith` on a reason string (grep for `vetoed:` and `stolen by` finds nothing outside `rank.py` and tests).
- [x] The case 12 key set and the `test_four_tiers` row key set include `cause`.
- [x] `CONTEXT.md`'s Cause entry matches what shipped; `references/routing.md` names the `cause` field.
- [x] `make test` is green on Python 3.9 and 3.13.

## Landed, 2026-10-11

Commit: f08b47b.

`rank.py` has `CAUSES = ("pick", "steal", "eligible", "unknown", "disabled", "floor",
"ceiling", "gate", "cli")`, and its docstring gives the Cause vocabulary and, separately,
the reason text for each cause. The ranking core `_rank_readouts` sets each row's `cause`:
- a vetoed row gets its veto, in the old precedence;
- the Pick gets pick, or steal when it took the job by the Margin, in either quota unit;
- an eligible row with no value to rank by (Meters on, Pace or plan price unknown) gets
  unknown;
- every other eligible row gets eligible.

`eligible` and `pick` on an eligible row are set from the cause, and `reason` is built
from the cause and the numbers. `veto` stays beside `cause` until ticket 22 (E3) removes
it. `rank --json` rows therefore gain `cause`, and nothing else in them changes.

The dashboard model copies `cause` into each state row. `_build_state` and
`_fresh_carried_lane_names` drop rows whose `cause` is disabled. `deck.reason_code` maps
`cause` to a code through `deck.CAUSE_CODES` and reads VETO for a cause the table lacks.
It reads neither `reason` nor `remaining`, so with Meters off a Lane with no reading
reads ELIG (decision E.3). The STEAL and NOMTR descriptions no longer name Pace.
`steal_thresholds` now sees the plan-dollars Pick, so the aid says codex-b "holds the
Pick in T2".

Verified, red first:
- test_dashboard `test_a_plan_dollars_steal_reads_as_a_steal` read ELIG for sol-high@codex,
  and the aid said "no Tier it can take" for codex-b.
- `test_a_lane_without_its_cli_or_a_reading_reads_as_cli` read NOMTR.
- `test_with_meters_off_a_lane_without_a_reading_follows_rank` read NOMTR.
- `test_four_tiers_show_carried_lanes_in_effective_order` lacked `cause` in its row
  keys, and test_rank case 12's key set lacked `cause`.
- test_rank 32a found no `CAUSES`, and 32b and 32c found no `cause` on any row.

All of them pass now:
- test_rank 32a checks the nine causes.
- 32b checks the cause on each named fixture: case 20's steal, eligible, gate, unknown
  and cli; case 13's disabled and pick; the sample impl rank's pick, floor and ceiling;
  case 29b's plan-dollars steal; case 6's unknown; and eligible with Meters off and no
  reading.
- 32c checks every row of those rankings, the other cases' rankings and a direct
  `rank_range` call: each has a cause from `CAUSES`, `eligible` exactly for pick, steal,
  eligible and unknown, and `pick` exactly for pick and steal.

`deck.py` and `model.py` contain no `startswith`. `grep -rn 'vetoed:\|stolen by'` finds
nothing outside `rank.py` and tests. `make test` passes on Python 3.9 and 3.13 with the
proxy pointed at a closed port.

Deviations:
- The rank case is case 32, not case 30. Ticket 16's hold case already holds 30 and
  ticket 18's Snapshot cases hold 31a to 31c on this branch. Tickets 21 and 23 name
  cases 31 and 32 for E2 and E4, so they take the next free numbers.
- Added test_dashboard `test_with_meters_off_a_lane_without_a_reading_follows_rank` for
  decision E.3, which the ticket states but no box tests.
- `disabled` has no deck code of its own. The model never shows a disabled Lane, so it
  reads VETO like any cause the table lacks, as `vetoed:disabled` did before.
- A prose comment in `report.handover` matched the `vetoed:` grep. It now reads "is
  vetoed, so the rest of the Tier decides". E4 deletes that function.
- `references/routing.md` names `cause` and its values under "The rule".
  `references/architecture.md` and `tools/delegate-dashboard/CLAUDE.md` each gained a
  sentence on the cause and the deck's table. `CONTEXT.md`'s Cause entry already matched
  what shipped, so it is unchanged.
