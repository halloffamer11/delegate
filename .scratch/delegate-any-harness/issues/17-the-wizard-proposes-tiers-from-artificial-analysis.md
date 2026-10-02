# 17 — The wizard proposes Tiers from benchmark bands

**What to build:** semi-automated Tier picking. For each carried Lane the wizard proposes a Tier, marked as a proposal on the Tier page; nothing is written until Orin confirms. ADR 0001 and the 2026-09-15 consultation say the human sets Tier and the board assists; a proposal Orin confirms stays inside that rule. The rules below are Orin's, from review on 2026-10-02.

- **Capability bands slice horizontally.** Each Tier has a threshold on one chosen benchmark score, and a Lane's proposed Tier is the highest band it clears. The Artificial Analysis index is the default because it scores every model quickly. The benchmark is a setting, not a constant: Terminal-Bench and the other accepted sources can be chosen instead, because which benchmark fits depends on the work.
- **Cost per task is a second axis.** It informs the proposal and the Order inside a Tier, and the cost frontier inside a band is shown as a hint. It is never a filter on its own.
- **Harness diversity.** A Tier keeps at least one representative Lane from every harness that has a Lane clearing that Tier's threshold, even when that Lane is not on the cost frontier. One model beating the others on score and cost (for example a Claude model beating Astra) does not push the other harnesses out.
- **Out of scope for now:** per-domain fit (a model good at knowledge work but weak at coding). The bands are one scale for all Classes until there is a good routing technique for domains; the multi-domain proposal (`.scratch/delegate-modular/research/2026-09-15-multi-domain-tiers-scope.md`, M6-M11) is where that goes later.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02; banding, cost and diversity rules set by Orin in review the same day.

- [ ] The benchmark, the Tier thresholds and the diversity rule are catalog data with a validator, not constants in code.
- [ ] Each Lane with a score shows its proposed Tier, the score and benchmark behind it, and its cost per task; a Lane without a score shows no proposal.
- [ ] A test proves the diversity rule: a harness whose best Lane clears a threshold but sits off the cost frontier still gets a proposal in that Tier.
- [ ] Switching the benchmark (AA index to Terminal-Bench) recomputes the proposals with no code change.
- [ ] Confirming writes the Tier; quitting writes nothing; a test proves both.
- [ ] Orin runs it once on the current generation and keeps or adjusts the thresholds (Orin's box).
