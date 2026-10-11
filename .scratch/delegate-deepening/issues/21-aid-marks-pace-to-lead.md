# 21 — The deck's aid marks the Pace rank says each Meter needs to lead

**What to build:** Candidate E, ticket E2 (lane meters-and-preview). Each `tier_leaders`
preview gains `steal_threshold` `{unit, value}` in routing's quota unit and
`pace_to_lead` `{meter: Pace or None}`. Rank computes `pace_to_lead` privately by
replaying its own Pick at the candidate Paces where a comparison can flip, on the 0.01
grid, up to `usage.MAX_PACE` (B4). The replay replaces one entry of B3's Readout map with
`dataclasses.replace(readout, pace=p)` and reruns the private ranking core; it never
reads the Snapshot twice. The search runs on Python 3.9, so it uses no `bisect` `key=`,
`zip(strict=)` or `itertools.pairwise`.

The dashboard model copies both into each state tier. In `deck.py`, delete
`steal_thresholds` together with its stale "rank.py lines 177-183" docstring.
`meter_verdict` says "holds the Pick in Tn" from the tier's leader Meter and "needs X to
take Tn" from the lowest Pace to lead, and its "takes the Pick" branch is removed.
`aid_lines` draws the Pace to lead as the mark and words the rule for the active unit
(decision E.4). Update `tools/delegate-dashboard/CLAUDE.md` so it no longer cites
`rank.py:177-183`. `CONTEXT.md`'s Tier preview, Steal threshold and Pace to lead entries
were added with the spec; keep them true to what ships. Case 31's documents are wrapped
with `usage.Snapshot.of`. Measure the preview's cost on 3.9.

Spec: `.scratch/delegate-deepening/spec.md` (E. Routing preview; decisions E.2 and E.4)

**Blocked by:** 20 The deck codes every Lane by the cause rank gives it; 19 Harness probes hand the Meters module their Windows, and usage.py exposes only its interface (`usage.MAX_PACE`)

**Status:** landed 2026-10-11. Each `tier_leaders` preview carries `steal_threshold` in routing's quota unit and each other Meter's `pace_to_lead`, found by rerunning rank's core with one Readout's Pace replaced; the dashboard copies both into its tiers and the deck's aid reads them. test_rank case 33 (the spec's case 31, renumbered) and test_dashboard `test_the_aid_marks_the_pace_rank_says_a_meter_needs` verify it. No box is left open.

- [x] test_dashboard `test_the_aid_marks_the_pace_rank_says_a_meter_needs` (terra and sol unordered, `write_meters` a_pace=0.6, b_pace=0.5) fails before this ticket with "needs 0.80× to take T2" for codex-b and passes with "needs 0.60× to take T2".
- [x] test_rank case 31a: sample catalog with fixture `meters.json`, Tier 2 `pace_to_lead == {'codex': 0.91}` and `steal_threshold == {'unit': 'pace', 'value': 1.1}` within 1e-9.
- [x] test_rank case 31b and 31c: with grok at order 1 and terra at order 2, codex needs 1.1 by Pace; with plan dollars the unit is plan_dollars, the value is 0.9 x grok's weight x 1.2, and codex's Pace to lead is the first 0.01 step at or above that value divided by codex's weight.
- [x] test_rank case 31d: for every Pace to lead in 31a-c, a meters document with that Meter at that Pace puts one of its Lanes in the lead through `tier_leaders`, and the same document at the Pace minus 0.01 does not.
- [x] test_rank case 31e: Meters off gives an empty `pace_to_lead` and a None `steal_threshold` value; a gated Meter and an unknown Meter have no key; a Meter priced at 1 against 100 under plan dollars reads None.
- [x] Rank reads the highest readable Pace only as `usage.MAX_PACE`, and the what-if substitutes Readouts without a second Snapshot read.
- [x] Previews pass `json.dumps(allow_nan=False)`, and `rank tiers --json` carries `steal_threshold` and `pace_to_lead`.
- [x] `deck.py` has no `steal_thresholds` and no "rank.py lines"; `tools/delegate-dashboard/CLAUDE.md` has no "rank.py:177-183".
- [x] `CONTEXT.md`'s Tier preview, Steal threshold and Pace to lead entries match what shipped.
- [x] `make test` is green on Python 3.9 and 3.13.

## Landed, 2026-10-11

`rank.tier_leaders` reads the Snapshot once into the Meter-to-Readout map (`_readouts`,
which `rank_range` shares) and ranks each exact Tier over it with the private core.
Each preview gains:
- `steal_threshold`, `{unit, value}`: the unit is `routing.quota_unit`; the value is the
  leader's Pace plus the Margin, or with plan dollars its value times (1 + Margin), and
  None with no leader, an unknown leader value or Meters off;
- `pace_to_lead`, `{meter: Pace or None}`: for every other Meter with an eligible Lane of
  known Pace in the Tier, the lowest Pace on the 0.01 grid at which a Lane on it leads.

`_pace_to_lead` gathers the crossings, each rival's value, value ± Margin (with plan
dollars, value × (1 + Margin) and value ÷ (1 + Margin)), over the Meter's weight. It
replays the core at 0 and at the first and second hundredth at or above each crossing,
in ascending order, up to `usage.MAX_PACE`, which it reads at call time. Each replay
swaps in `dataclasses.replace(readout, pace=step / 100)` and ranks only the Tier's Lanes.
Steps are whole hundredths, so a Pace to lead such as 0.91 is exact. The search uses no
3.10-only name.

The dashboard model copies `steal_threshold` and `pace_to_lead` into each state tier.
`deck.steal_thresholds` is deleted, along with its "rank.py lines 177-183" docstring,
the "takes the Pick" branch and the aid's reachable-threshold code. `meter_verdict(entry,
state)` drops its third argument. It says "holds the Pick in Tn" for the first Tier whose
leader runs on the Meter, and otherwise "needs X× to take Tn" from the lowest Pace to
lead any Tier gives it. `aid_lines` draws that Pace as the gold mark on the Pace bar.
The rule sentence reads per unit: Pace plus the Margin, or with plan dollars Pace times
plan dollars a week against the Pick's value times one plus the Margin. A legend line
says what the mark is.

Verified, red first:
- test_dashboard `test_the_aid_marks_the_pace_rank_says_a_meter_needs` read
  "needs 0.80× to take T2" for codex-b. It now reads "needs 0.60× to take T2", with the
  mark on cell 10 of the 34-cell bar.
- test_rank 33a to 33g found no `steal_threshold` or `pace_to_lead` on any preview.
- 33f counted four reads of each Meter per `tier_leaders` call.

All of them pass now:
- 33a: the sample catalog's Tier 2 gives `{"codex": 0.91}` and Pace 1.1.
- 33b: case 20's layout gives codex 1.1.
- 33c: plan dollars give 0.9 × grok's weight × 1.2 and codex 1.62, the first 0.01 step
  at or above that value over codex's weight.
- 33d: each of the six Paces to lead from 33a to 33c puts its Meter in the lead through
  `tier_leaders`, and 0.01 below it does not.
- 33e: Meters off gives an empty map and a None value. The gated grok and the unknown
  grok have no key, and codex priced at 1 against grok at 100 reads None. With
  `usage.MAX_PACE` raised to 200, that codex reads 108.0, so rank reads the ceiling from
  `usage.MAX_PACE`.
- 33f: one `tier_leaders` call reads each Meter of the Snapshot once.
- 33g: every preview passes `json.dumps(allow_nan=False)`, and `rank.py tiers --json`
  carries both facts.

The dashboard tests that called `meter_verdict` with `steal_thresholds` call it with
the state alone. A scratch comparison against a full 0.01 scan from 0 to 50 agreed on
1,549 Paces to lead across random Tiers of 2 to 7 Lanes, both units and Margins from 0
to 0.35. `make test` passes on Python 3.9 and 3.13 with the proxy pointed at a closed
port.

Cost, measured on Python 3.9 with `timeit`, per `tier_leaders` call, before and after:

| Catalog | Before | After |
| --- | --- | --- |
| sample catalog | 0.2 to 0.3 ms | 0.4 to 0.6 ms |
| 24 Lanes over four Tiers on 6 Meters | about 0.6 ms | about 21 to 28 ms |
| 15 Lanes on 15 Meters in one Tier | 0.5 to 1.0 ms | 48 to 65 ms |

The last row is the worst case: 14 searches, about 60 core runs each. The dashboard
rebuilds the preview on each reload and staged key. `catalog_edit` previews pay the
same cost. So does the popup's `lane_lines`, but the plain statusline does not.

Deviations:
- The rank case is case 33, not case 31: cases 31 and 32 already exist on this branch
  (tickets 18 and 20). Its parts are 33a to 33e as the spec's 31a to 31e, plus 33f (one
  Snapshot read) and 33g (JSON safety and `rank tiers --json`) for the two boxes the
  spec's case did not name.
- `tier_leaders` no longer calls `rank_range` per Tier. It reads the Readouts once and
  ranks each Tier with the core, so the Snapshot is read once per call, not four times.
  A replay ranks only the Tier's own Lanes (every Lane has a Tier, by catalog
  validation).
- With Meters off, the aid's Pace verdict says "Pace inactive" for a Meter that holds no
  Tier, beside the Remaining verdict's "Gate inactive". The map is empty then, so the
  verdict would otherwise say "no Tier it can take".
- A Meter that holds a Tier gets no mark on its Pace bar, so the mark always shows the
  Pace its verdict names. Before this ticket it drew the Pace plus the Margin of a Tier
  it might already hold.
- `deck.meter_rows` no longer keeps each Meter's Lanes, which only the deleted
  reachable-threshold code read.
- `CONTEXT.md` is unchanged: its Steal threshold and Pace to lead entries match what
  shipped. The Tier preview entry also names the Handover (ticket 23, E4) and says the
  popup only draws the preview, which ticket 22 (E3) delivers. `references/routing.md`
  documents the two facts under "The rule". `references/architecture.md` and
  `tools/delegate-dashboard/CLAUDE.md` describe the search and the aid, and the latter
  no longer cites `rank.py:177-183`.
