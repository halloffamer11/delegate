# 39 — A percent of one Meter is not a percent of another

**What to decide:** Pace compares fractions across Meters, as if 1% of Claude's week
were the same work as 1% of codex's or grok's. It is not, and a plan change moves it:
going from Codex Pro to Codex Plus shrinks what 100% of the codex Meter buys. The Meters
are different currencies and need a conversion factor, so that Pace, and the steal that
compares it, compare like with like. Raised by the user 2026-09-27: "Let's not add that in
now, but put that in the backlog."

What exists today:
- `meter_weight` is set on each Lane and is "a property of the plan, not the model"
  (`discover.py`). It is unmeasured on the generated Lanes (ticket 37, item 3), and
  `rank.py` does not read it.
- The codex probe already reports its plan in the Meter note (`plan=prolite`), a
  possible key for a factor per plan.

**Blocked by:** None — can start immediately.

**Status:** ready-for-human, triaged 2026-10-04. The user deferred the build on
2026-09-27; what is left for him is the choice below.

**Triage.** Pace is Remaining over the share of the Window left, so it is already a ratio
without units: a Pace of 1.3 on any Meter means "30% ahead of using it all by the reset".
What ranking does with it is spread load toward the Meter most likely to expire unused,
and quota that expires is lost whatever the plan's size. So comparing Pace across Meters
is right for that question. Where size does matter is how much work a steal moves: a
Margin of 0.2 on a $20 plan is a fifth as many dollars as on a $100 plan.

Recommended (no build): keep Pace as it is, and close this ticket. If the steal ever
needs to be size-aware, the common unit is plan dollars per week, which needs no new
data: each Meter already carries `price_month`, a plan change already updates it, and
`report.py` already turns a used share into dollars with it (`price_month × 7/30.4375 ×
share`). The alternative build is a steal that compares weekly dollars left instead of
Pace, with Margin in dollars.

- [ ] The user decides the common unit, and how each Meter's factor is set and updated when
      a plan changes.
- [ ] Ranking compares converted quota, and a plan change needs only its factor changed.
