# 03 — Each View proposes an effort per model

**Blocked by:** 01 The benchmark page is flat views with a Frontier tab.

**What to build:** on each View, per Model on a Harness, the effort that View's board says is
worth running: the cheapest effort on that model's own score-and-cost frontier within a set score
of its best. Mark it on the coverage cell, and say when the board measured only one effort, so a
figure at `max` is never read as evidence for a `medium` Lane.

**Status:** needs-triage. Ticket 05 shows a first cut in each View's Favours column: the lowest
effort whose mean percentile is within five points of the Model's best (`FAVOUR_MARGIN`).

- [ ] The rule for "worth running" is agreed (the gap below the model's best that still counts).
- [ ] Each coverage cell marks the proposed effort, or says the board measured one effort only.
