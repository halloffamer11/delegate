# 43 — The grok Meter reads full on the free tier

**What to fix:** on 2026-10-04 `delegate status` showed the grok Meter at 100% left, then
grok refused a run in 3 s with "You've reached your free Grok Build usage limit for now"
(run `20261004T184209Z-grok47-high@grok-e3542c35`). The probe in `harnesses/grok.py`
reads `creditUsagePercent` from `_x.ai/billing` and turns a missing value into 0% used
(`float(pct or 0)`). On the free Grok Build tier that field is probably absent, so the
Meter reads full (inferred, not tested). A missing figure should read as unknown, not
as full.

The user rejected holding a Meter at 0 after a refusal: the reading must stay stateless,
because a remembered "empty" would outlive a vendor's own reset.

**Blocked by:** None.

**Status:** backlog, raised 2026-10-04. The user leans to taking grok out of rotation
instead.

- [ ] A billing reply with no `creditUsagePercent` gives the grok Meter an unknown
      Remaining, with a test from a free-tier reply captured on the Mac.
