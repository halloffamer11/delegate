# 17 — The wizard proposes Tiers from Artificial Analysis

**What to build:** semi-automated Tier picking. For a new or unplaced Lane the wizard proposes a Tier from its AA figures (bands Orin sets once), marked as a proposal on the Tier page; nothing is written until Orin confirms. ADR 0001 and the consultation say the human sets Tier and the board assists; a proposal Orin confirms stays inside that rule.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] The Tier bands are catalog data with a validator, not constants in code.
- [ ] A Lane with AA rows shows a proposed Tier and the figure behind it; a Lane without rows shows none.
- [ ] Confirming writes the Tier; quitting writes nothing; a test proves both.
- [ ] Orin runs it once on the current generation and keeps or adjusts the bands (Orin's box).
