# 21 — A run can show in a Herdr pane

**What to build:** `delegate run` and `delegate dispatch` gain a Herdr mode that runs the
dispatch in a new Herdr pane instead of the caller's background shell, and returns when the
pane prints the finish line. The run directory, `return.json` and the `delegate:` lines stay
the contract, so the caller reads the result exactly as it does now. Raised by Orin in review
of PR #3, 2026-10-03: "Is the Courier model the right model, or is a herdr implementation
better? I think having herdr as a prerequisite is acceptable."

Why not replace the courier with this: the courier exists only because a Workflow script has
no shell. A Herdr mode still needs a shell to call `herdr`, so it cannot serve a Workflow
script on its own. What Herdr adds is for every orchestrator with a shell: the worker is
visible in a pane, survives a closed session, shows `working` or `blocked`, and the wait is
Herdr's (`pane wait-output`) instead of a polling loop each harness writes.

Herdr 0.9.3 primitives (herdr.dev agent-automation and CLI reference, read 2026-10-03):
`herdr pane split --current --direction right --no-focus` returns the new pane at
`.result.pane.pane_id`; `herdr pane run <pane> "<command>"` submits a command;
`herdr pane wait-output <pane> --regex '<re>' --timeout <ms>` returns the matched line.
Waits have no default timeout. `agent start --kind` covers codex, agy, grok, kiro and claude,
but drives interactive sessions, not the headless relay, so it is out of scope here.

Default where this forks: opt-in per run (`--herdr`, or `"herdr": true` in routing), with the
background shell as the fallback when `HERDR_PANE_ID` is unset, so delegate keeps working
outside Herdr. Orin may instead make Herdr required.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** wontfix, 2026-10-03. Orin narrowed the question to the courier, which is Claude
Workflow glue only, and asked whether Herdr inside the courier adds anything beyond visibility. It
does not: the Workflow dies with its session whatever pane the run is in, relays are headless so
Herdr's `blocked` state never fires, and the cost is a Herdr dependency nested inside a Haiku
subagent plus panes to clean up. Herdr stays available to a person, never required by delegate.
The courier moved under Claude's orchestrator profile instead.

- [ ] Orin picks opt-in or required (Orin's box).
- [ ] `delegate run --herdr` opens a pane, runs the dispatch there, and prints the same finish
      line and `delegate-metrics:` line as a background run; a native lane prints its spawn line
      without opening a pane.
- [ ] Outside Herdr the flag falls back to the background run with one warning line.
- [ ] A fake `herdr` on PATH tests the pane split, run and wait argv offline.
- [ ] One live run in a Herdr pane on the Mac (Orin's box).
