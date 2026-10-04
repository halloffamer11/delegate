# 37 — Tier coverage and the Order inside a Tier

**Blocked by:** None — can start immediately.

**What to decide:** three open items, moved verbatim from the root `CLAUDE.md` on
2026-09-23. They are one decision space, the user's: which Lanes each Tier holds, in what
Order, and what cost figure would decide it.

1. **Tier 1 depends on codex alone.** It holds only `luna6-high@codex`, and
   `catalog.py check` warns about that. When codex is under the Gate, `scout` and
   `mechanical` overflow to Tier 3 (ticket 29). The coverage is the user's to set, in the
   wizard or per project.
2. **Order inside a Tier:** The user's open question (capability against cost), not yet a
   ticket. The session's position (2026-09-22):
   - capability belongs in the Tier boundaries, and inside a Tier the cheapest Lane
     comes first;
   - Pace and Margin then spread the load;
   - the real cost is `meter_weight`, which is not measured; the page's "Price per
     model" chart shows only list price, as a stand-in.
3. **Unmeasured figures:** `meter_weight` and `timeout` on the generated Lanes are
   copies, and each Lane's note says `UNMEASURED` and names the source Lane. The grok and
   agy cache-write prices are not published.

The new Lanes are priced from
`.scratch/delegate-redesign/research/2026-09-22-new-model-prices.md`. The exception is
`grok47fast-high`, which has no published price.

**Status:** ready-for-human

- [ ] The user sets Tier 1 coverage, in the wizard or per project. On the Mac's catalog,
      2026-10-04, Tier 1 is no longer codex alone: it holds `luna6-max@codex`, the three
      agy Opus 5.5 Lanes (low, medium, high, placed by ticket 31's wizard run) and
      `glm5-high@kiro`. The agy `opus55-high` at Tier 1 is likely an accident: its Claude
      Code twin sits at Tier 3 and ticket 17's proposal puts both at 4. Recommended: tick
      this box, and move `opus55-high@agy` (and `opus55-medium@agy`) up with `p` in the
      wizard.
- [ ] The user answers the Order question, or makes it a ticket of its own. Answered in
      code since: any-harness ticket 17's proposal orders each Tier cheapest first
      (cost per task, then score), and `p` on a tier page writes that Order. That is
      the session's 2026-09-22 position. Recommended: tick this box and keep it.
