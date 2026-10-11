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

**Status:** ready-for-agent

- [ ] test_rank case 32: with a@x on mx (weekly 0.5, `cycle_left` 0.5, order 1), b@y on my (Pace 0.9, order 2), Margin 0.2 and Gate 0.05, handover is points ≈ 0.15 to b@y; a lone leader gives ≈ 0.45 to None; plan dollars with weights 20 and 10 gives ≈ 0.3125 to b@y; Meters off gives None (tolerance 0.006).
- [ ] The popup CLI checks in test_report pass unchanged, including "→ luna-low@codex leads after agy drops 18.5 pts".
- [ ] `report.py` has no handover function, no `HANDOVER_STEP`, no `eligible_order` or `choose` import and no Window arithmetic for the handover; rank reads the leader's Meter after a spend only through `Snapshot.readout(spend=)`.
- [ ] `rank.py` exposes no public `score`, `eligible_order`, `steals` or `choose` (grep in `scripts/` and `tools/` finds no caller).
- [ ] The replacement for case 29c passes through `rank()`: on equally priced Meters, 1.2 against 1.0 steals at Margin 0.2, 1.19 does not, and an unpriced Meter never steals.
- [ ] The three test_report handover unit checks are deleted.
- [ ] `CONTEXT.md`'s Handover entry matches what shipped.
- [ ] `make test` is green on Python 3.9 and 3.13.
