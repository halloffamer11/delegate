# 38 — The Claude Meter probe hangs inside this project

**Blocked by:** None — can start immediately.

**What to find:** moved verbatim from the root `CLAUDE.md` on 2026-09-23.

- **The Claude Meter probe hangs inside this project.** `claude -p ... /usage` did not
  return within 45 s from a dotfiles checkout, and takes about 3 s from `~`. The probe
  runs from `~` (`fb845e3`), and the cause is not known.

**Status:** wontfix, triaged 2026-10-04: no longer reproduces.

On Orin's Mac (claude 2.1.288, delegate `b5825b8`), with stdin closed and a 60 s
limit, from inside a Claude Code session:

| command | ~/dotfiles | ~/projects/delegate | ~ |
|---|---|---|---|
| `claude -p /usage` | 3.4 s | 2.8 s | 3.9 s |
| the probe, `claude -p --permission-mode plan --output-format json /usage` | 2.8, 3.2, 3.0, 2.9 s | 2.9 s | 3.6 s |

Every run returned `is_error: false` with the usage text, and `Claude().read_meters()`
returned both Meters in 3.0 s. The 2026-09-18 hang's cause cannot be recovered; a CLI
fixed since, or a one-time trust or hook state, are the likely ones. The probe keeps
running from `~` (`fb845e3`), which is harmless.

- [x] The cause inside the project is known, or Orin closes this ticket: it no longer
      reproduces (above). Reopen with a new reading if a probe hangs again.
