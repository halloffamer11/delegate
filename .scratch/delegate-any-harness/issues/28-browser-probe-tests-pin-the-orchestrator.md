# 28 — The browser probe tests pin their orchestrator

**What to build:** `tests/test_browser_probes.py` case 7 passes only when the test runs inside
Claude Code. The case copies the host environment (`test_env = dict(os.environ)`, line 151) and
expects native rows for `fable-xhigh@claude`. A Lane is native only when `orchestrators.resolve()`
detects Claude Code, and the `claude` profile detects it from `CLAUDECODE`. From a plain shell,
nothing is detected, the claude Lane relays, and the case fails with
`native_ok=False non_agy_ok=False`. The code under test is correct; the test reads the host.

`tests/test_dispatch.py` (lines 129–134) already has the fix: it removes `CLAUDECODE`, sets
`DELEGATE_ORCHESTRATOR=claude`, and points `DELEGATE_ORCHESTRATORS_DIR` at the test's own
profiles, so "the host's own markers and profiles never reach them." Give `test_env` in
`test_browser_probes.py` the same pinning.

Found 2026-10-02 on omarchy after `git pull` to `885518e` and `make install`: `make test` failed
only `tests/test_browser_probes.py`. The same commit on the Mac passed inside Claude Code and
failed with `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT`, with the same output as omarchy.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02 after `make test` failed on omarchy.

- [ ] `test_browser_probes.py` pins the orchestrator the way `test_dispatch.py` does: no
      `CLAUDECODE` from the host, `DELEGATE_ORCHESTRATOR=claude`, and its own
      `DELEGATE_ORCHESTRATORS_DIR`.
- [ ] `make test` gives the same result from a plain shell, from inside Claude Code, and with
      `DELEGATE_ORCHESTRATOR=codex` set in the host.
- [ ] No other test under `agents/skills/delegate/tests/` or `tools/` copies `os.environ` into a
      run that resolves an orchestrator without pinning it; fix each one found.
- [ ] `make test` passes on 3.9 and 3.13.
