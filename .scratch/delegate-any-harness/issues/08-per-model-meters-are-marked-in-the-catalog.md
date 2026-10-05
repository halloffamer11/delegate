# 08 — Per-model Meters are marked in the catalog

**What to build:** the statusline special-cases the Meter name `"claude-fable"` to decide a per-model Meter shares the claude 5h Window (`scripts/report.py:640`). A renamed Fable Meter, or a Sonnet per-model Meter whose cached row lacks `remaining_weekly_model`, draws the wrong row.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** closed 2026-10-05. The open review or one-run box below is closed as moot: the user has run the wizard, the dashboard and the evals since, and asked to close out open work. Reopen the ticket to revisit it. Earlier status: landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). Both boxes done. One step is the user's: add `"model_meter": true` to the `claude-fable` meter in each machine's `~/.config/delegate/lanes.json` (machine-local, so not in this commit).

- [x] A Meter's per-model nature comes from the catalog or the probe row, not from its name.
- [x] No Meter name is hardcoded in `report.py`; a test renames the Fable Meter and gets the same row.
- [ ] The user marks the Fable meter `"model_meter": true` in `~/.config/delegate/lanes.json` on the Mac and on omarchy.

## Landed, 2026-10-02

A meter may carry `"model_meter": true` (catalog validates it as a boolean; the sample
catalog marks `claude-fable`). The statusline leaves 5h blank for a meter so marked, or
whose probe row carries `remaining_weekly_model`; the `"claude-fable"` name check is
gone, and `report.py` names no Meter. `CONTEXT.md` defines **Model meter**.

Until a machine's catalog has the flag, its Fable row still draws right whenever the
cached probe row carries `remaining_weekly_model`, which `probe_claude` always writes for
a per-model meter. Only a row without it (no probe yet, or a failed one) loses the blank
5h until the flag is added.

Verified: `test_report.py` renames the meter to `claude-amber` in catalog and cache and
gets the same row, and drops the cached per-model figure and still gets a blank 5h; the
second check fails on the old `report.py`. `make test` passes on 3.9 and 3.13 and with
no harness CLI on PATH.
