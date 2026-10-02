# 08 — Per-model Meters are marked in the catalog

**What to build:** the statusline special-cases the Meter name `"claude-fable"` to decide a per-model Meter shares the claude 5h Window (`scripts/report.py:640`). A renamed Fable Meter, or a Sonnet per-model Meter whose cached row lacks `remaining_weekly_model`, draws the wrong row.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] A Meter's per-model nature comes from the catalog or the probe row, not from its name.
- [ ] No Meter name is hardcoded in `report.py`; a test renames the Fable Meter and gets the same row.
