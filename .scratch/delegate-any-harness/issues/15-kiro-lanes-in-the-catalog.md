# 15 — Kiro Lanes in the catalog

**What to build:** a Kiro module in the registry: discovery from `--list-models --format json`, a Meter whose Remaining is unknown until a usage source exists (an unknown Remaining never vetoes), effort mapping if Kiro's `--effort` applies headless, and the wizard offering Kiro Lanes for Tiers.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 11 One harness registry; 14 A Kiro relay in the delegate-skills fork.

**Status:** done 2026-10-04, raised by the user 2026-10-02. Built 2026-10-03: `scripts/harnesses/kiro.py` (binary `kiro-cli`, efforts low to max, `any_vendor`), so the refresh offers every current Kiro model except the `auto` router as Lanes; the first Kiro Lanes start from the adapter's starter Lane and add a `kiro` Meter (Kiro Pro, $20 assumed, Remaining unknown, which the Gate never vetoes). `--effort` and `--model` pass through to the relay. The listing's JSON shape is undocumented, so `tests/fixtures/kiro/kiro-models.json` is an assumed shape until a real listing replaces it. Dispatch case 31f runs a Kiro Lane through the fake relay. `assets/orchestrators/kiro.json` is Kiro's orchestrator profile (the one ticket 13 deferred here): relayed, never auto-detected because Kiro documents no variable it sets, with a headless launch the offline orchestrate eval passes. Checked on the user's Mac 2026-10-04: discovery reads kiro-cli 2.27.1's real listing (8 models; `auto` dropped; `claude-sonnet-4` unmapped, superseded by 4.5). The listing carries no effort field, so every Kiro model takes low to max; that is delegate's assumption. The real listing is now the fixture `kiro-models-2.27.1.json` beside the assumed one.

- [x] `delegate global` lists Kiro's current models as Lanes to screen.
- [x] `delegate run` can dispatch a Kiro Lane through the relay, with a fixture test offline.
- [x] The user places the Kiro Lanes he wants in a wizard run (the user's box). His catalog has 35 Kiro Lanes at Tier 1 (7 models, low to max); `glm5-high@kiro` is the one enabled.
