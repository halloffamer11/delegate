# 42 — Detect the plan a harness is signed in on

**What to build:** the catalog states each Meter's plan and `price_month` by hand, and
nothing checks it. On 2026-10-04 the Mac's grok CLI ran on the free Grok Build tier
while the catalog priced it as SuperGrok ($30), and a day of test runs used up the free
quota. Delegate should read the plan from the harness where it can, say when it differs
from the catalog, and not depend on which plan the user holds. Raised by the user
2026-10-04: "It should detect it and be agnostic to it and just be able to map to the
right usage plan." The user called it a backlog feature.

What exists today:
- The codex probe already reports its plan in the Meter note (`plan=prolite`).
- grok says which tier it runs on only in its limit message, so far.

**Blocked by:** None.

**Status:** backlog, raised by the user 2026-10-04.

- [ ] Each harness that can tell its plan reports it, and `delegate status` flags a plan
      that differs from the catalog.
