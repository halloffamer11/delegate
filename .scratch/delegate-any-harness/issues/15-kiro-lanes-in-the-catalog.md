# 15 — Kiro Lanes in the catalog

**What to build:** a Kiro module in the registry: discovery from `--list-models --format json`, a Meter whose Remaining is unknown until a usage source exists (an unknown Remaining never vetoes), effort mapping if Kiro's `--effort` applies headless, and the wizard offering Kiro Lanes for Tiers.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry; 14 A Kiro relay in the delegate-skills fork.

**Status:** ready-for-human, raised by Orin 2026-10-02. Built 2026-10-03: `scripts/harnesses/kiro.py` (binary `kiro-cli`, efforts low to max, `any_vendor`), so the refresh offers every current Kiro model except the `auto` router as Lanes; the first Kiro Lanes start from the adapter's starter Lane and add a `kiro` Meter (Kiro Pro, $20 assumed, Remaining unknown, which the Gate never vetoes). `--effort` and `--model` pass through to the relay. The listing's JSON shape is undocumented, so `tests/fixtures/kiro/kiro-models.json` is an assumed shape until a real listing replaces it. Dispatch case 31f runs a Kiro Lane through the fake relay. `assets/orchestrators/kiro.json` is Kiro's orchestrator profile (the one ticket 13 deferred here): relayed, never auto-detected because Kiro documents no variable it sets, with a headless launch the offline orchestrate eval passes. Waits on Orin: the wizard run in the last box, which also shows whether the parser reads the real listing.

- [x] `delegate global` lists Kiro's current models as Lanes to screen.
- [x] `delegate run` can dispatch a Kiro Lane through the relay, with a fixture test offline.
- [ ] Orin places the Kiro Lanes he wants in a wizard run (Orin's box).
