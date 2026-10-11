# 23 — Only rank replays its own Pick, and the popup's handover comes from rank in quota points

**What to build:** Candidate E, ticket E4 (lane meters-and-preview, its last ticket).
This ticket owns the Handover; B2 left `report.handover` in place for it. Each
`tier_leaders` preview gains `handover` `{points, to}` or None. Rank computes it by
spending the leader's Meter in half-point steps through B's `snap.readout(m, cat,
spend=x)`, substituted into B3's Readout map, until another Lane leads or the Meter falls
under the Gate, and reports the result in quota points, never time. `report.handover_note`
only renders the preview's `handover`.

Delete `report.handover`, its Window arithmetic, `HANDOVER_STEP` and the `eligible_order`
and `choose` imports (ticket 22 left `eligible_order` for the handover).
Make rank's `score`, `eligible_order`, `steals` and `choose` private, and drop `score`'s
popup invariant. Replace test_rank case 29c, which called `rank.steals` directly, with a
test through `rank()`, and delete the three test_report handover unit checks. Case 32's
documents are wrapped with `usage.Snapshot.of` and keep the `cycle_left` row key.
`CONTEXT.md`'s Handover entry was added with the spec, with hand-off (a native Run's
Outcome) on its avoid list; keep it true to what ships.

Spec: `.scratch/delegate-deepening/spec.md` (E. Routing preview)

**Blocked by:** 22 The popup shows the Pace to lead rank gives, even past its axis; 17 Every display shows one weekly figure and one Gate per Meter (`Snapshot.readout(spend=)`)

**Status:** landed 2026-10-11. Each `tier_leaders` preview carries `handover` (`{points, to}` or None), which rank finds by spending the leader's Meter through `Snapshot.readout(spend=)` in half-point steps; the popup only renders it, `report.handover` is gone, and rank's `score`, `eligible_order`, `steals` and `choose` are private. test_rank cases 34a to 34h and the replaced 29c, test_dashboard `test_each_tier_carries_the_handover_rank_gives` and the unchanged popup checks in test_report verify it. No box is open.

- [x] test_rank case 32: with a@x on mx (weekly 0.5, `cycle_left` 0.5, order 1), b@y on my (Pace 0.9, order 2), Margin 0.2 and Gate 0.05, handover is points ≈ 0.15 to b@y; a lone leader gives ≈ 0.45 to None; plan dollars with weights 20 and 10 gives ≈ 0.3125 to b@y; Meters off gives None (tolerance 0.006).
- [x] The popup CLI checks in test_report pass unchanged, including "→ luna-low@codex leads after agy drops 18.5 pts".
- [x] `report.py` has no handover function, no `HANDOVER_STEP`, no `eligible_order` or `choose` import and no Window arithmetic for the handover; rank reads the leader's Meter after a spend only through `Snapshot.readout(spend=)`.
- [x] `rank.py` exposes no public `score`, `eligible_order`, `steals` or `choose` (grep in `scripts/` and `tools/` finds no caller).
- [x] The replacement for case 29c passes through `rank()`: on equally priced Meters, 1.2 against 1.0 steals at Margin 0.2, 1.19 does not, and an unpriced Meter never steals.
- [x] The three test_report handover unit checks are deleted.
- [x] `CONTEXT.md`'s Handover entry matches what shipped.
- [x] `make test` is green on Python 3.9 and 3.13.

## Landed, 2026-10-11

What shipped:
- `rank.tier_leaders` gives each Tier a `handover`. A private `_handover` reruns the
  ranking core over the Tier's Lanes, with the leader's Readout replaced by
  `snapshot.readout(meter, cat, spend=k/200)`, for k from 1 to at most 200. It stops at
  the first step where another Lane leads, or where none does: then the Meter is under
  the Gate with nothing else eligible. `points` is the spend in quota points, a fraction
  of the week, capped at the Weekly figure. `to` is the new leader, or None. The
  Snapshot is still read once per Meter, and spends are the only further readouts.
- `report.py` lost `handover`, `HANDOVER_STEP` and the `eligible_order` and `choose`
  imports. `handover_note` renders the preview's `handover` with the same words as
  before, and `tier_block` no longer takes the Margin or the Gate.
- `rank.py`'s `score`, `eligible_order`, `steals` and `choose` are now `_score`,
  `_eligible_order`, `_steals` and `_choose`. `score`'s popup invariant is dropped. A grep
  of `scripts/`, `tools/` and `bin/` finds no caller of the old names.
- The dashboard state copies `handover` into each tier, beside `steal_threshold` and
  `pace_to_lead` (the spec's "Callers migrated").
- Docs: `references/routing.md` documents `handover` in `rank tiers --json`, and
  `references/architecture.md` and `tools/delegate-dashboard/CLAUDE.md` describe how
  rank computes it and that the state copies it. `CONTEXT.md`'s Handover entry already
  matched what shipped, so it is unchanged. Ticket 22's last box is ticked: `report.py`
  no longer imports `eligible_order`.

How verified:
- test_rank case 34 (the spec's case 32) runs through `tier_leaders` on rows that carry
  `cycle_left` 0.5, with Margin 0.2 and Gate 0.05. Each case below failed before the
  change: the preview had no `handover` key, and rank exposed all four names.
  - 34a: a@x on mx (weekly 0.5, Pace 1.0, order 1) and b@y on my (Pace 0.9, order 2)
    give about 0.15, to b@y.
  - 34b: a lone leader gives about 0.45, to None.
  - 34c: plan dollars at weights 20 and 10 give about 0.3125, to b@y.
  - 34d: Meters off gives None.
  - 34e: no leader, no Weekly figure and no share of the week left each give None.
  - 34f: a counting Snapshot shows one plain read per Meter, then spend reads of the
    leader's Meter alone, on the 0.005 grid, at most 200 of them.
  - 34g: the Handovers pass `json.dumps(allow_nan=False)`, and `rank tiers --json`
    carries `handover` on every Tier.
  - 34h: `rank` has no `score`, `eligible_order`, `steals` or `choose`.
  - The tolerance is 0.006 throughout.
- Case 29c now runs through `rank("impl")` on two Tier 2 Lanes of its own, both Meters
  priced at $20 under plan dollars. A Pace of 1.2 against 1.0 steals at Margin 0.2,
  1.19 does not, and a Meter with no price never steals at Pace 9.0. It passed from the
  start, because it replaces a direct check of a rule that already held.
- The three test_report `report.handover` unit checks are deleted. The popup checks pass
  unchanged, including "→ luna-low@codex leads after agy drops 18.5 pts" and "needs
  0.96 (+0.26)", as do the statusline CLI checks.
- test_dashboard `test_each_tier_carries_the_handover_rank_gives` failed with a KeyError
  until the model copied the field.
- Cost on Python 3.9, sample catalog with a popup-style cache: `tier_leaders` takes about
  3 to 5 ms, against 0.5 ms before.
- `make test` passes on Python 3.9 and 3.13 with the proxy pointed at a closed port.

Deviations:
- The spec's case 32 is test_rank case 34 here. Cases 32 (Cause) and 33 (Pace to lead)
  were taken on this branch by tickets 20 and 21.
- `handover` is also None in two cases beyond the spec's three (no leader, Meters off,
  no Weekly figure):
  - The leader's Meter has no Pace or no share of the week left. A spent Pace would be
    unknown, and the leader would sort last at the first step. The old popup returned
    nothing on `not meter["left"]` for the same reason.
  - The leader still leads with its whole week spent, which takes a Gate of 0. Without
    this case the search has no end.
- The dashboard's copy of `handover` is not in the ticket text. The spec's "Callers
  migrated" names it, and this was E's last ticket.
- At an exact tie the Handover can differ by one 0.005 step from the old popup loop. The
  old loop added 0.005 repeatedly, and its float drift settled ties its own way.
  `readout(spend=)` subtracts the spend in one step, and the spent Pace is not rounded,
  while a probe rounds Pace to 3 decimals. Two examples:
  - With all four CLIs present, the samples and the popup fixture's readings give Tier 2
    "→ grok46-high@grok leads after codex drops 15.5 pts", where the old loop gave
    15.0. At 15.0, codex's spent Pace ties grok's 0.35 to within float noise.
  - With a lone leader at weekly 0.5 and Gate 0.05, rank gives 0.45. Exact arithmetic
    gives 0.455, because a Remaining equal to the Gate is still eligible.

  An exact `Fraction` replay of the rule over each cache's own numbers ran on 3,200
  random Tiers with two-decimal readings. It matched 69% of Handovers to the step. Every
  other one was one step off, with the same new leader. Rounding the spent Weekly
  figure inside `readout(spend=)` raised the match to 98%. That change was
  not made: it alters B's arithmetic, and it shifts the popup's "only lane · ... pts
  above the Gate" figure by half a point at a tie. The ticket's 0.006 tolerance is that
  one step. A follow-up could have `readout(spend=)` give figures at probe precision.
