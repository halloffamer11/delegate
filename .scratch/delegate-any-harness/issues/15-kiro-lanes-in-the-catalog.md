# 15 — Kiro Lanes in the catalog

**What to build:** a Kiro module in the registry: discovery from `--list-models --format json`, a Meter whose Remaining is unknown until a usage source exists (an unknown Remaining never vetoes), effort mapping if Kiro's `--effort` applies headless, and the wizard offering Kiro Lanes for Tiers.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** 11 One harness registry; 14 A Kiro relay in the delegate-skills fork.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] `delegate global` lists Kiro's current models as Lanes to screen.
- [ ] `delegate run` can dispatch a Kiro Lane through the relay, with a fixture test offline.
- [ ] Orin places the Kiro Lanes he wants in a wizard run (Orin's box).
