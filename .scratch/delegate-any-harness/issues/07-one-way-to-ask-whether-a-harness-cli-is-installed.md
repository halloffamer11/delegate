# 07 — One way to ask whether a harness CLI is installed

**What to build:** `usage.which()` (`scripts/usage.py:200`) has a dead `if False` branch and accepts directories and empty PATH entries, while rank and statusline use `shutil.which`. A probe can say "failed" where ranking says "absent". The statusline tests (`tests/test_report.py:302`) never stub PATH, so 9-10 of 107 checks fail on any host without all four CLIs; with stubs all pass.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done.

- [x] One helper answers "is this harness's CLI installed" and every caller uses it (ticket 11 later moves it behind the adapter).
- [x] The statusline and popup tests put stub `claude`, `codex`, `agy` and `grok` on a temporary PATH, and `make test` passes on a host with none of them.

## Landed, 2026-10-02

`catalog.cli_installed(harness)` is the one answer, with `catalog.installed_harnesses()`
for the set. `usage.which` is now that function (the `if False` branch and the
directory-accepting PATH walk are gone), and delegate, rank, report, discover,
browser_probes and the dashboard's `model.py` call it instead of `shutil.which`. The
CLI is still named after its harness; ticket 11 moves the helper behind the adapter.
`browser_probes.get_cli_version` keeps its own `shutil.which`, since it runs the CLI.

`test_report.py` now sets PATH to a directory holding only stub `claude`, `codex`, `agy`
and `grok` for every report run; the one test that wants none sets PATH itself.

Verified: `make test` passes with the four CLIs absent from PATH (node only), which
is where the 9 statusline and popup checks failed before. `test_catalog.py` 18 puts a
`codex` directory and an empty entry on PATH and checks catalog and usage both say only
`agy` is installed and the codex probe says "absent". Passes on 3.9 and 3.13.
