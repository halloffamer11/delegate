# 43 — A usage-limit refusal empties the Meter; the grok Meter reads full on the free tier

**What happened:** on 2026-10-04 `delegate status` showed the grok Meter at 100% left, then
grok refused a run in 3 s with "You've reached your free Grok Build usage limit for now"
(run `20261004T184209Z-grok47-high@grok-e3542c35`). Two defects:

1. Delegate kept ranking grok as full after grok had said no.
2. The probe in `harnesses/grok.py` reads `creditUsagePercent` from `_x.ai/billing` and
   turns a missing value into 0% used (`float(pct or 0)`). On the free Grok Build tier that
   field is probably absent, so the Meter reads full (inferred, not tested).

**Status:** in progress. The user chose to build part 1 on 2026-10-05 ("Build 43"). Part 2
waits on a free-tier billing reply captured on a machine with grok signed in.

**Built (part 1).** A harness lists the wording of its own limit refusal
(`Harness.limit_patterns`; grok's is the one seen above). When a run is blocked with that
wording, dispatch writes a hold for the Lane's Meter to `limits.json` beside the usage
cache, and every read of the cache shows that Meter at 0% left, so the Gate vetoes its
Lanes. The hold ends at the earliest of: the Meter's weekly reset as the probe read it
when the run was refused, 24 hours, a probe that reads a different reset (the vendor
started a new period early), or a run on that Meter that finishes. The probe's own
reading is never changed. Which Lanes are on is each machine's own setting, not this
repo's.

- [x] A run refused for a usage limit makes its Meter read 0% left, and the Gate vetoes
      its Lanes until the hold ends.
- [x] grok's free-tier refusal is recognised.
- [ ] A billing reply with no `creditUsagePercent` gives the grok Meter an unknown
      Remaining, with a test from a free-tier reply captured on a machine.
