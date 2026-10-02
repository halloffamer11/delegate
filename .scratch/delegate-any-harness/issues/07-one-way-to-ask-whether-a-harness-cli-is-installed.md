# 07 — One way to ask whether a harness CLI is installed

**What to build:** `usage.which()` (`scripts/usage.py:200`) has a dead `if False` branch and accepts directories and empty PATH entries, while rank and statusline use `shutil.which`. A probe can say "failed" where ranking says "absent". The statusline tests (`tests/test_report.py:302`) never stub PATH, so 9-10 of 107 checks fail on any host without all four CLIs; with stubs all pass.

Spec: `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] One helper answers "is this harness's CLI installed" and every caller uses it (ticket 11 later moves it behind the adapter).
- [ ] The statusline and popup tests put stub `claude`, `codex`, `agy` and `grok` on a temporary PATH, and `make test` passes on a host with none of them.
