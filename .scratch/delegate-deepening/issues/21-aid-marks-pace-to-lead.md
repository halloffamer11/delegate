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

**Status:** ready-for-agent

- [ ] test_dashboard `test_the_aid_marks_the_pace_rank_says_a_meter_needs` (terra and sol unordered, `write_meters` a_pace=0.6, b_pace=0.5) fails before this ticket with "needs 0.80× to take T2" for codex-b and passes with "needs 0.60× to take T2".
- [ ] test_rank case 31a: sample catalog with fixture `meters.json`, Tier 2 `pace_to_lead == {'codex': 0.91}` and `steal_threshold == {'unit': 'pace', 'value': 1.1}` within 1e-9.
- [ ] test_rank case 31b and 31c: with grok at order 1 and terra at order 2, codex needs 1.1 by Pace; with plan dollars the unit is plan_dollars, the value is 0.9 x grok's weight x 1.2, and codex's Pace to lead is the first 0.01 step at or above that value divided by codex's weight.
- [ ] test_rank case 31d: for every Pace to lead in 31a-c, a meters document with that Meter at that Pace puts one of its Lanes in the lead through `tier_leaders`, and the same document at the Pace minus 0.01 does not.
- [ ] test_rank case 31e: Meters off gives an empty `pace_to_lead` and a None `steal_threshold` value; a gated Meter and an unknown Meter have no key; a Meter priced at 1 against 100 under plan dollars reads None.
- [ ] Rank reads the highest readable Pace only as `usage.MAX_PACE`, and the what-if substitutes Readouts without a second Snapshot read.
- [ ] Previews pass `json.dumps(allow_nan=False)`, and `rank tiers --json` carries `steal_threshold` and `pace_to_lead`.
- [ ] `deck.py` has no `steal_thresholds` and no "rank.py lines"; `tools/delegate-dashboard/CLAUDE.md` has no "rank.py:177-183".
- [ ] `CONTEXT.md`'s Tier preview, Steal threshold and Pace to lead entries match what shipped.
- [ ] `make test` is green on Python 3.9 and 3.13.
