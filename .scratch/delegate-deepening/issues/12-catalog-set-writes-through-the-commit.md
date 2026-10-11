# 12 — catalog set and the dashboard write through the one commit

**What to build:** Candidate D, ticket D4 (lane catalog-write). `edit_catalog`'s apply
commits its one planned document with `catalog_commit.commit(read, {dest: doc})`, instead
of rechecking the revision and writing itself. The first check (`expect` against
`read().revision`) keeps its exact text. A `CatalogChanged` from the commit becomes the
same `CatalogError`, "intervening edit: source documents or resolved paths changed;
preview again", so the dashboard's conflict handling and its source check hold. The noop
rule (an empty customization over an absent file writes nothing) stays in
`catalog_edit`.

A global `catalog set` that writes `lanes.json` on the live catalog gains backups and the
Agent-file sync. A project-scope set, the dashboard's only write, is not backed up and
never touches `~/.claude/agents`. `Committed.lines` go to stderr, so `catalog set`'s JSON
stdout stays byte-identical. After this ticket, no script writes a catalog document
except `catalog_commit`, plus `catalog fmt`, which formats one named file through
`catalog.write_json` and follows the same link rule.

Spec: `.scratch/delegate-deepening/spec.md` (D. Catalog commit; decisions D.1 and D.5)

**Blocked by:** 09 A wizard save never overwrites a catalog change made while it was open

**Status:** ready-for-agent

- [ ] test_catalog.py cases 10.3, 10.3b, 10.3c and 11.7 and the intervening-write case pass unchanged.
- [ ] `tools/delegate-dashboard/test_dashboard.py` passes unchanged.
- [ ] A new test_catalog case, "a global set backs up lanes.json beside the catalog", passes.
- [ ] A project-scope `catalog set` on a live layout under a temp `HOME` writes no Agent file, and `catalog set`'s stdout JSON is unchanged, with any note on stderr.
- [ ] `catalog_edit.py` calls no writer but `catalog_commit.commit` and has no second revision recheck.
- [ ] `make test` passes on 3.9 and 3.13. `references/catalog.md` says apply writes through links and refuses a dangling one.
