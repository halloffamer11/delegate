# 25 — Meter identity is explicit and checked

**What to build:** Each adapter declares the Meter names its probe reports. `delegate catalog check` refuses a Lane whose Meter no installed adapter reports, so a typo stops failing open. The usage row key `lane` becomes `meter` (old caches still read). Gate and Margin defaults come from merged routing only. The unused `probe` Meter field is dropped. The Rust monitor reads each Lane's Meter from `lanes.tsv` instead of re-deriving agy's split.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed in delegate#6 2026-10-03. Adapters declare `meter_groups`, `meter_names()` and `reports_meter()`; `catalog check` (not every load, so an older catalog keeps routing) refuses a Lane on a Meter its probe does not report and names the ones it does. Usage rows are keyed `meter` with the probe word under `group`; old rows upgrade on read in Python and in the Rust monitor. Gate and Margin come from merged routing only; `probe` is dropped from the samples and the starter (still accepted on read). The Rust monitor reads each Lane's Meter from `lanes.json` rather than `lanes.tsv`, which carried no Meter column. Verified: `make test` on 3.9 and 3.13, `cargo test` in `tools/delegate-mon`, a new typo case in `test_catalog`.

- [x] A misspelled Meter in `lanes.json` fails `catalog check` with the names the adapters report.
- [x] No module re-derives a Meter name from a probe's group name.
- [x] `make test` passes on 3.9 and 3.13.
