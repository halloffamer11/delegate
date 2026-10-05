# 02 — Claude workers can use a disposable browser

**What to build:** A claude worker can use the Playwright server in the user's own Claude config.

This ticket was written before ticket 22 and its premise no longer holds. It targets the claude relay in our ADS fork, which blocks MCP in four ways. Since ticket 22 a claude lane dispatched from a Claude session is **native**: `delegate.py` prints a spawn line and starts no relay at all, so a native worker never meets those four blocks. It inherits this session's tools instead. Lifting the relay's MCP block would change nothing on the path the user actually uses.

The ticket is therefore rescoped to the native path. The relay work is kept only as a note, for the day a claude lane is dispatched from a non-Claude orchestrator.

Facts and setup rules: `../research/2026-09-10-browser-routes.md`.

**Blocked by:** 01 — Browser probes, proven on agy with a disposable browser.

**Status:** ready-for-human; rescoped 2026-09-12 after ticket 22. Raised by the user 2026-09-10. Proven on the Mac 2026-10-04. The user chose an allowlist the same day: built. 2026-10-05: the Mac's lane files carry it; the probe rerun is blocked by the session's auto mode, so the user reruns the probe from a session that is not in auto mode.

- [x] Setup on both machines: a `playwright` server in Claude's user config that follows the setup rules. The user added it 2026-09-12 with `claude mcp add -s user playwright -- npx -y @playwright/mcp@latest --isolated --headless --output-dir ~/.cache/playwright-mcp`; `claude mcp list` shows it Connected on the Mac and on omarchy.
- [x] A session must restart before its native workers see a new MCP server. Restart, then confirm the session itself has the Playwright tools. Done 2026-10-04: a fresh Remote Control session on the Mac had `mcp__playwright__*`.
- [x] Every other MCP server the session exposes to a native worker is listed here. On the Mac today that is `context7` plus the claude.ai connectors Gmail, Google Drive and Google Calendar. A native worker inherits them. The worker preamble forbids messages, but that is an instruction, not a block — decide whether that is acceptable, or whether native lanes need a narrower tool set.
      Listed 2026-10-04 from a native worker's own tool list, in a desktop-app Remote
      Control session: playwright, context7 (twice), DaVinci Resolve (twice), the
      claude.ai connectors (Gmail, Google Drive, Google Calendar, Todoist, Strava,
      Vanguard, Claude Docs), a visualizer, and the desktop app's own servers
      (claude-in-chrome, computer-use, claude-code-remote, scheduled-tasks, the ccd_*
      set and others), about 30 in all. A worker can send mail, write Todoist, drive
      the signed-in Chrome and message other sessions; only the brief stops it. A plain
      terminal `claude` would lack the desktop-app set (not tested).
      The user's call, 2026-10-04: an allowlist. Claude's native template now writes
      `tools: Read, Grep, Glob, Bash, Edit, Write, WebFetch, WebSearch, mcp__playwright`,
      and the wizard's save rewrites any placed lane file that differs from the template.
      Checked on the Mac 2026-10-05 (claude 2.1.289, delegate main cfea3ac, after
      `make install`): the wizard save of that morning wrote `lanes.json`, `routing.json`
      and all 16 `lane-*.md` files, and each carries the `tools:` line above. The probe
      worker, `lane-opus55-medium` spawned from a desktop-app Remote Control session,
      listed its own tools as Read, Bash, Edit, Write, WebFetch, WebSearch and the
      `mcp__playwright__*` set, and nothing else: no context7, no claude.ai connectors,
      no desktop-app servers. Grep and Glob, which the line names, did not appear in its
      list (not checked further).
- [ ] Rerun the disposable probe with the allowlist. 2026-10-05 from the same session:
      Playwright opened example.com and read the title `Example Domain`, but Claude Code's
      auto-mode classifier refused `browser_type` into httpbin's "Customer name" field
      ("Browser Input Exfil"), so the form was not submitted and the run returned
      `BROWSER-PROBE FAIL`. The allowlist did its job; the block is the session's
      permission mode. The user reruns it from a session not in auto mode, or allows
      Playwright input to httpbin.org.
- [x] Proof on the Mac: the claude row of the baseline table passes the disposable probe. The runner marks the row `NATIVE`, so dispatch the lane with the probe brief and spawn the agent the native line names, then check the pass against Playwright's page snapshot. Passed 2026-10-04: claude 2.1.288, `lane-opus55-medium` returned `BROWSER-PROBE PASS title=Example Domain` with the nonce, and `~/.cache/playwright-mcp` holds that run's example.com page and the httpbin post carrying the nonce.
- [x] The delegate skill's `CLAUDE.md` names the current ADS pin and describes agy read-only as it now works. Done 2026-09-11 during session close; update the pin line again if ticket 04 pins a new commit.
- [ ] Note, not work for now: the relay still denies MCP to a claude worker through its tool allowlist, `--strict-mcp-config` and `--disallowedTools "mcp__*"`, and read-only runs use plan mode. That matters only for a claude lane dispatched from a non-Claude orchestrator. Raise a new ticket if that case appears.

## Why the claude rows failed in the 2026-09-11 baseline

Both native workers reached for Claude in Chrome, which had no connected browser, and the session had no Playwright server at all. The lead confirmed `list_connected_browsers` returned `[]` from the session itself. The first half is now fixed by the setup above; the agent-profile half waits on ticket 06.
