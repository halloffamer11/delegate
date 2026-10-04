# 17 — The wizard proposes Tiers from benchmark bands

**What to build:** semi-automated Tier picking. For each carried Lane the wizard proposes a Tier, marked as a proposal on the Tier page; nothing is written until the user confirms. ADR 0001 and the 2026-09-15 consultation say the human sets Tier and the board assists; a proposal the user confirms stays inside that rule. The rules below are the user's, from review on 2026-10-02.

- **Capability bands slice horizontally.** Each Tier has a threshold on one chosen benchmark score, and a Lane's proposed Tier is the highest band it clears. The Artificial Analysis index is the default because it scores every model quickly. The benchmark is a setting, not a constant: Terminal-Bench and the other accepted sources can be chosen instead, because which benchmark fits depends on the work.
- **Cost per task is a second axis.** It informs the proposal and the Order inside a Tier, and the cost frontier inside a band is shown as a hint. It is never a filter on its own.
- **Harness diversity.** A Tier keeps at least one representative Lane from every harness that has a Lane clearing that Tier's threshold, even when that Lane is not on the cost frontier. One model beating the others on score and cost (for example a Claude model beating Astra) does not push the other harnesses out.
- **Out of scope for now:** per-domain fit (a model good at knowledge work but weak at coding). The bands are one scale for all Classes until there is a good routing technique for domains; the multi-domain proposal (`.scratch/delegate-modular/research/2026-09-15-multi-domain-tiers-scope.md`, M6-M11) is where that goes later.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-human, raised by the user 2026-10-02; banding, cost and diversity rules set by the user in review the same day. Built 2026-10-03: `scripts/tier_proposal.py`, the `tier_proposal` rule in `routing.json` (sample default: AA Intelligence Index, Tier 2 ≥ 30, 3 ≥ 40, 4 ≥ 50, diversity on), the tier pages' `proposed` column and `p`, `tests/test_tier_proposal.py`. How cost informs the proposal: a Tier keeps its band's score-and-cost frontier plus each harness's best Lane; a Lane another beats on both falls a Tier. Waits on the user: the run on the current generation, which sets the thresholds.

Dry run on the user's real catalog, 2026-10-04 (AA Intelligence Index, thresholds 30/40/50, 756 accepted rows from 2026-10-03). Read it with one caveat: the run passed every Lane, enabled or not, while the wizard proposes only for carried Lanes (`setup_tui.tier_proposals`), so a disabled Lane there beat enabled ones it will not beat in the wizard.

- 40 Lanes scored; 31 of the proposals differ from today's Tier.
- Opus 5.5 rises: `opus55-high` to Tier 4 on both Claude Code and agy, `opus55-medium` to 3. `sol61-xhigh` goes to 4, `sol61-medium` to 3.
- Fable falls: `fable-high` 4 → 1, `fable-xhigh` and `fable-max` 4 → 3. Opus 5.5 scores higher at lower cost per task (e.g. `opus55-xhigh` 56.0 at $3.46 against `fable-xhigh` 53.2 at $5.98), so on this benchmark Fable sits off the frontier in every band. That is the benchmark's verdict, not a bug, and it is the first thing the user's box has to accept or override.
- 43 Lanes have no score, among them all 35 Kiro Lanes. Not yet traced; the likely cause is that the accepted AA rows predate the Kiro Lanes (`effort.py aa` fetches a page per Lane model) or that AA prints those models under names formatting cannot bridge (`published_as` fixes that). A fresh `effort.py aa` run in the wizard shows which.

- [x] The benchmark, the Tier thresholds and the diversity rule are catalog data with a validator, not constants in code.
- [x] Each Lane with a score shows its proposed Tier, the score and benchmark behind it, and its cost per task; a Lane without a score shows no proposal.
- [x] A test proves the diversity rule: a harness whose best Lane clears a threshold but sits off the cost frontier still gets a proposal in that Tier.
- [x] Switching the benchmark (AA index to Terminal-Bench) recomputes the proposals with no code change.
- [x] Confirming writes the Tier; quitting writes nothing; a test proves both.
- [ ] The user runs it once on the current generation and keeps or adjusts the thresholds (the user's box).
