# 04 — The Mac runs the current delegate

**What to build:** The RC Mac's install is stale: `~/projects/delegate` was at a83496b on 2026-10-30, and `~/.claude/skills/delegate` is a copied directory rather than the link `make install` makes, so `make install` stops on it.

**Blocked by:** None — can start immediately.

**Status:** needs-info. Replacing the copied directory deletes it, so it waits for the user's yes.

- [ ] `~/projects/delegate` is on `main` after this effort merges.
- [ ] The copied `~/.claude/skills/delegate` is moved aside and `make install` links it.
- [ ] `make test` passes on the Mac.
