# 04 — Grok workers can use a disposable browser

**What to build:** A grok worker can use a Playwright server in grok's own config, on a read-only run as well as a write run.

The ticket expected no relay change. That expectation is wrong, and the cause is not what the ticket assumed. grok's built-in `read-only` sandbox breaks **every** stdio MCP server on macOS, not only Playwright: in the same failing run `context7` dies too. The relay maps a read-only run to `--sandbox read-only`, so no server survives, and `search_tool` correctly reports an empty catalog. Config alone cannot fix it, which is the condition this ticket set for changing the relay.

On macOS grok's sandbox does not block network, so a pass here says nothing about Linux. Ticket 05 tests that.

Facts and setup rules: `../research/2026-09-10-browser-routes.md`.

**Blocked by:** 01 — Browser probes, proven on agy with a disposable browser.

**Status:** ready-for-human. The user's call, 2026-10-04: a browser job on grok goes as a write run, and read-only browsing on grok is unsupported on macOS. The last box is a write-run probe on the Mac. Root cause found and the fix proven 2026-09-12. Raised by the user 2026-09-10. 2026-10-04 on the Mac (grok 1.0.46): the handshake needs only `~/.npm`, but browsing still fails under any read-only-based profile (below), so the relay change waits on a way past that.

- [x] Setup on the Mac: a `playwright` server in `~/.grok/config.toml` at user scope, with `--isolated --headless --output-dir ~/.cache/playwright-mcp`. Added by the user 2026-09-12 on the Mac and on omarchy. `grok mcp doctor` reports it healthy with 24 tools, and `grok inspect` lists it as `config`.
- [x] Root cause, from grok's own debug log (`RUST_LOG=debug GROK_LOG_FILE=…`): under `--sandbox read-only` both servers spawn and then fail with "handshake failed: connection closed: initialize response", alongside "Error killing MCP child process group: Operation not permitted (os error 1)". Under the default `workspace` sandbox the same session has `browser_navigate` and `browser_snapshot`. The output directory is not the cause: a temp output dir, which the read-only profile permits, fails the same way.
- [x] The fix is proven at the grok level. A custom profile in `.grok/sandbox.toml`, `[profiles.probe] extends = "read-only"` with `read_write` for `~/.npm`, `~/.cache/playwright-mcp` and `~/Library/Caches/ms-playwright`, makes both handshakes succeed: "MCP handshake succeeded server=playwright … tool_count=24" and "server=context7 … tool_count=2".
- [x] Narrow the grants. Three were granted together; find the smallest set that works, and write it into the setup rules. Each attempt costs one grok run. Done 2026-10-04: `read_write = ["~/.npm"]` alone gives both handshakes (playwright 25 tools, context7); with no grant both fail. The other two grants change nothing. `~/.grok/sandbox.toml` on the Mac had been empty since Sep 1; it now holds the `probe` profile with `~/.npm` only. A profile is chosen with `grok --sandbox probe` (or `GROK_SANDBOX=probe`).
- [x] Not needed (the user's call, 2026-10-04: write runs). Relay change on our ADS fork: a read-only grok run must be able to use a named sandbox profile. Today the relay's parser accepts only `--read-only` and `--full-access`, mapping to the fixed set `workspace-write | read-only | full-access` (`AUTONOMY_MODES`), so no profile name can reach grok. Pin the new commit in `ads.sh`, run `ads.sh check`, and offer the change upstream with the PR link recorded here.
- [x] Not needed (write runs). Setup on both machines, in conversation with the user: the profile in `~/.grok/sandbox.toml`, with the narrowed grants. The Mac's `probe` profile is harmless and can stay.
- [ ] Proof on the Mac: the grok row passes the disposable probe in a write run, checked against Playwright's page snapshot. (Read-only dropped, 2026-10-04.)

## Browsing under a read-only profile fails on macOS (2026-10-04)

With the handshake fixed, `browser_navigate` still fails, with `~/.npm` alone and with all
three grants. grok's own log shows Chrome dying under Seatbelt: "bootstrap_check_in
org.chromium.crashpad.child_port_handshake: Permission denied (1100)", Chrome failing to open
its `Crashpad/settings.dat`, then SIGSEGV. The crash reporter's check-in is a Mach lookup, not
a path, and `sandbox.toml` has no field for Mach or IPC, so no grant can fix it. Both follow-up runs failed on 2026-10-04 (grok 1.0.46; `~/.grok/config.toml` restored after):

- Crash reporter off (`--config` with `--disable-crash-reporter`, `--disable-crashpad-for-testing`,
  `--disable-breakpad`): the flags reached Chrome, which still crashed. A second cause shows in
  the log: "sandbox_extension_issue_file_to_process failed for /Applications/Google Chrome.app:
  Operation not permitted", Chrome's own sandbox failing inside grok's Seatbelt profile.
- Playwright's bundled browser (`--browser chromium`): Playwright maps it to chrome-for-testing,
  which is not installed (only chromium-1134 to 1234 are), so no browser started.

First write-run probe, 2026-10-04 evening (`~/tmp/grok-write-probe`, run
`20261004T184209Z-grok47-high@grok-e3542c35`): blocked after 3 s by grok's own limit, "You've
reached your free Grok Build usage limit". The grok CLI on the Mac runs on the free Grok Build
tier, while the catalog prices the meter as SuperGrok ($30), and the day's test runs used up
the free quota. The probe also showed `browser_probes.py --dry-run` printing `--effort low`,
which grok (high only) refuses; fixed: a probe keeps the Lane's effort on a harness that does
not offer low. Waits on the user: which account the grok CLI signs in with, then the rerun.

Two untested ways remain: Chrome with `--no-sandbox` (drops Chrome's own isolation; grok's
Seatbelt still wraps it), or installing chrome-for-testing (a download). Otherwise a grok
read-only run cannot browse on macOS, and a browser job on grok goes as a write run, which
works today.

## What a write run already gives, with no change at all

`autonomyFlags` maps a write run to `--always-approve --sandbox workspace`, and a workspace-sandbox session has the browser tools today. So a grok worker dispatched with `--write` can already use a disposable browser. Only the read-only path is blocked, which is the common path for scouts and probes.

## A worker's stated reason is still a claim

The 2026-09-12 probe run reported "Playwright MCP handshake failed". The failure was real this time, but the worker did not know that: both occurrences of the word in the run's events are streaming deltas of the model's own text, with no system message behind them. Its only sourced evidence was `search_tool` returning an empty catalog. Read the log, not the report.
