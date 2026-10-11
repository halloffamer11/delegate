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

**Status:** landed 2026-10-11. `edit_catalog`'s apply now commits its one document with `catalog_commit.commit`, so a global `catalog set` backs up what it replaces and, on the live catalog's `lanes.json`, keeps the Agent files in step, while a project set, the dashboard's only write, does neither; a `CatalogChanged` there is the dashboard's exact "intervening edit" text. Verified by test_catalog 10.15 to 10.18 (10.15 and 10.17 red on the base first) with 10.3, 10.3b, 10.3c, 11.7, 10.12 and the dashboard test unchanged; no box is open.

- [x] test_catalog.py cases 10.3, 10.3b, 10.3c and 11.7 and the intervening-write case pass unchanged.
- [x] `tools/delegate-dashboard/test_dashboard.py` passes unchanged.
- [x] A new test_catalog case, "a global set backs up lanes.json beside the catalog", passes.
- [x] A project-scope `catalog set` on a live layout under a temp `HOME` writes no Agent file, and `catalog set`'s stdout JSON is unchanged, with any note on stderr.
- [x] `catalog_edit.py` calls no writer but `catalog_commit.commit` and has no second revision recheck.
- [x] `make test` passes on 3.9 and 3.13. `references/catalog.md` says apply writes through links and refuses a dangling one.

## Landed, 2026-10-11

What shipped:

- `catalog_edit.edit_catalog`: an apply that is no noop commits `{dest: planned document}`
  with `catalog_commit.commit` through the read the edit was planned on. The first check
  (`--expect` against that read's revision) keeps its exact text, and a `CatalogChanged`
  from the commit is raised as the same `CatalogError(INTERVENING_EDIT)`. `Committed.lines`
  (Agent files written, updated or removed, and notes) go to stderr, so the JSON result on
  stdout is unchanged. `_unchanged_since`, the second revision recheck, and the direct
  `catalog.write_json` call are deleted. The noop rule (an empty customization over an
  absent file writes nothing) stays in `catalog_edit` and commits nothing.
- So a global set copies the global document it replaces to `<config dir>/backups/`, and
  one that writes the live catalog's `lanes.json` gives every native Lane its Agent file;
  a project set is not backed up and never touches `~/.claude/agents`. No script writes a
  catalog document except `catalog_commit`, plus `catalog fmt` through `catalog.write_json`.
- Docs: `references/catalog.md`'s Focused changes says apply writes through links, refuses
  a dangling one or a loop, backs up a global file and keeps the Agent files in step with
  notes on stderr; `references/architecture.md`'s `catalog_commit` and `catalog_edit`
  entries say the apply commits; `catalog_edit`'s docstring likewise. `CONTEXT.md`'s
  Catalog commit entry already matched.

Verified:

- `tests/test_catalog.py`, new cases: 10.15 "a global set backs up lanes.json beside the
  catalog" (base: no backups folder); 10.16 "a project set on the live catalog writes no
  agent file and prints only its JSON" (the CLI under a temp `HOME` whose
  `~/.config/delegate` holds the refresh-2026-09-22 lanes, sixteen claude Lanes without
  Agent files; stdout is one formatted result with the fourteen keys in their order,
  stderr is empty; it passes on the base too, as a guard); 10.17 "a global set on the live
  catalog gives every claude Lane its agent file, notes on stderr" (base: no Agent file;
  now sixteen files, one `wrote` line each on stderr, stdout the same one JSON result, one
  backup); 10.18 "an edit landing after the revision check is refused with the
  dashboard's text" (an edit lands while the apply ranks: the refusal equals the
  dashboard's mark, their edit stays, no backup; it passes on the base, whose recheck
  raised that text, and fails when the commit's own `CatalogChanged` message passes
  through).
- Unchanged and passing: test_catalog 10.3, 10.3b, 10.3c, 11.7 and 10.12 (the
  intervening write), and `tools/delegate-dashboard/test_dashboard.py`.
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and 3.13:
  every file ok, the dashboard test included.

Deviations:

- Two test_setup cases ("a catalog set made while the wizard is open survives its save"
  and "a focused save refuses a catalog changed since launch") asserted no backups folder
  after the refused save. The `catalog set` their stub runs now makes its own backup, so
  each now asserts that the folder holds only that one `lanes-` backup: the refused save
  still backs up nothing.
- The ticket names two new checks (10.15 and 10.16); 10.17 adds the global set on the live
  catalog, and 10.18 pins the conversion of a commit-time `CatalogChanged` to the
  dashboard's text, which no existing case reached.
- An in-process global set on a catalog that is not the live one prints the commit's
  one-line note ("... this catalog is not the live one, so none was written") to stderr
  when the catalog has native Lanes, as the spec's step 7 says; the test runs show it.
