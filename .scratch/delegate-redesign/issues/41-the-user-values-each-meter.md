# 41 — The user sets what each Meter is worth

**What to build:** each Meter gets an optional value that the user sets, defaulting to
100 for every Meter, so that with no change all Meters count the same, as they do today.
Ranking would weight Pace by that value, the way `quota_unit: plan_dollars` (ticket 39)
weights it by the plan price. A Meter the user values low (the user's example: agy) has
its spare quota count for less, so the other Meters get spent first. Raised by the user
2026-10-04: plan price is not the right measure, because some plans give more per dollar
and the user values some plans differently. "Leave everything at a hundred-point value,
and then we can adjust those numbers later."

**Blocked by:** None. The user called it backlog and possibly too complicated.

**Status:** backlog, raised by the user 2026-10-04.

Notes:
- The ticket 39 machinery already carries a per-row `weight`; this would read the value
  from the Meter instead of `price_month`.
- Open question for the user: does a low value only move a Meter later in the order, or
  should it also stop a steal? The relative steal of ticket 39 does both.

- [ ] The user decides whether this is worth building.
