# 25 — Meter identity is explicit and checked

**What to build:** Each adapter declares the Meter names its probe reports. `delegate catalog check` refuses a Lane whose Meter no installed adapter reports, so a typo stops failing open. The usage row key `lane` becomes `meter` (old caches still read). Gate and Margin defaults come from merged routing only. The unused `probe` Meter field is dropped. The Rust monitor reads each Lane's Meter from `lanes.tsv` instead of re-deriving agy's split.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised in review of PR #3 2026-10-03

- [ ] A misspelled Meter in `lanes.json` fails `catalog check` with the names the adapters report.
- [ ] No module re-derives a Meter name from a probe's group name.
- [ ] `make test` passes on 3.9 and 3.13.
