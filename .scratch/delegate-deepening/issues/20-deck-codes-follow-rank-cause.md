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

**Status:** ready-for-agent

- [ ] test_dashboard `test_a_plan_dollars_steal_reads_as_a_steal` (`quota_unit` plan_dollars, `write_meters` a_pace=0.5, b_pace=0.65) fails before this ticket with ELIG and "no Tier it can take" for codex-b, and passes with STEAL and "holds the Pick in T2".
- [ ] test_dashboard `test_a_lane_without_its_cli_or_a_reading_reads_as_cli` (present without grok, no grok row in the meters document) fails before this ticket with NOMTR and passes with CLI.
- [ ] test_rank case 30: every row from `rank_range`, `rank` and `tier_leaders` carries a cause from `CAUSES`; on the case 20, 13, sample impl and 29b fixtures the causes are steal, eligible, gate, unknown, cli, disabled, floor, ceiling and plan-dollars steal as specified.
- [ ] On every row, `eligible` is true exactly for pick, steal, eligible and unknown, and `pick` is true exactly for pick and steal.
- [ ] `deck.py` and `model.py` contain no `startswith` on a reason string (grep for `vetoed:` and `stolen by` finds nothing outside `rank.py` and tests).
- [ ] The case 12 key set and the `test_four_tiers` row key set include `cause`.
- [ ] `CONTEXT.md`'s Cause entry matches what shipped; `references/routing.md` names the `cause` field.
- [ ] `make test` is green on Python 3.9 and 3.13.
