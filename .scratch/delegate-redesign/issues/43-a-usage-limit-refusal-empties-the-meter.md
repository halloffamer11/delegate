# 43 — A usage-limit refusal empties the Meter

**What to build:** when a harness refuses a run because its usage limit is reached,
delegate records that Meter's Remaining as 0 until its reset, so the Gate vetoes its
Lanes and ranking moves on. Today the probe's reading stands even when the harness has
just said no.

Seen 2026-10-04 on the Mac: `delegate status` showed the grok Meter at 100% left, then
grok refused a run in 3 s with "You've reached your free Grok Build usage limit for now"
(run `20261004T184209Z-grok47-high@grok-e3542c35`). The grok probe reads
`creditUsagePercent` from `_x.ai/billing` and writes the tier into the Meter note
(`tier=…`). On the free Grok Build tier that figure apparently does not cover the limit
that refused the run.

Notes:
- `Harness.blocked_reason(run_dir)` is the existing hook for a reason a completed relay
  hides; a limit refusal would be a second kind, read per harness from its events or
  final message.
- The reset time may not be in the refusal; without one, keep the Meter at 0 until the
  next successful probe that reads a later period.
- This makes the plan the harness is signed in on matter less (ticket 42): whatever the
  plan, a refusal is the truth.

**Blocked by:** None.

**Status:** ready-for-agent, raised 2026-10-04.

- [ ] A run refused for a usage limit sets its Meter's Remaining to 0 in the usage cache,
      and the next rank vetoes its Lanes at the Gate.
- [ ] grok's free-tier refusal is recognised (fixture from the 2026-10-04 run).
- [ ] The grok probe's reading on the free tier is checked on the Mac and fixed or
      documented.
