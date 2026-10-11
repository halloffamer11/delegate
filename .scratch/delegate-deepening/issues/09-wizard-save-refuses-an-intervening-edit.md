# 09 — A wizard save never overwrites a catalog change made while it was open

**What to build:** Candidate D, ticket D1 (lane catalog-write, its first ticket). Add
`scripts/catalog_commit.py` with `read()` and `commit()`, the `CatalogRead` and
`Committed` value types, and the `CatalogChanged` error.

The read side: move `catalog_edit`'s source snapshot into `read()`: source description,
revision hash, strict JSON and validation. Add the dangling-link refusal. On Python 3.9 a
dangling link is one where `os.path.lexists` holds and `os.path.exists` does not, and a
loop is `os.stat` raising `OSError` with `ELOOP`; do not use
`os.path.realpath(strict=True)` (3.10). `catalog_edit`'s preview and apply read through
`read()`, and its JSON output is unchanged. `catalog_revision` is deleted in favour of
`read().revision`.

The commit side: `commit()` validates with the read-side validators. It refuses an
Intervening edit with `CatalogChanged`, skips unchanged documents, backs up each replaced
global document into `<config dir>/backups` (stamped with `datetime.timezone.utc`, newest
20 per document), writes atomically through links, and restores what it already wrote
when a later write fails. Callers print `Committed.lines` to stderr.

The link rule: `catalog.write_json` writes through a link to an existing file and refuses
a dangling one or a loop. `_write_preserving_link` is deleted, and its three callers call
`write_json` in the interim. The scan and the focused screen move onto the commit in
later tickets.

The wizard: it reads its catalog with `read()` at launch. The sample proposal stays for a
first run, and `load_or_propose` stops reading files. The full TUI save and the `--plain`
save commit through that read. On `CatalogChanged` the wizard prints which document
changed and that nothing was written, and exits 1. `setup.main`'s focused branch takes
its revision from the launch `CatalogRead`'s `.revision` instead of
`catalog_edit.catalog_revision`, and keeps `write_focused` until D3. Agent files and the
queue are still handled after a successful commit as today; D2 moves them.

Every new test that runs `setup.main` passes `--no-bench`, plus `--no-discover` or
`--fixture-dir`, under a temporary `HOME`, so none fetches the Epoch CSV.

Spec: `.scratch/delegate-deepening/spec.md` (D. Catalog commit; decisions D.1, D.3, D.5 and D.8)

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-11 (ed45ae9). `scripts/catalog_commit.py` adds `read()` and `commit()`, and the wizard's full and `--plain` saves commit through the read taken at launch, so a catalog set or a Model swap made while the wizard is open is refused, not overwritten; `catalog.write_json` carries the link rule. Verified by the nine `test_catalog_commit.py` cases, four new test_setup cases and test_catalog 10.14, each red on the base first; no box is open.

- [x] `tests/test_catalog_commit.py` passes these cases: unchanged documents keep bytes and mtime; an intervening edit or a retargeted link raises `CatalogChanged` naming the document and writes nothing; an invalid document writes nothing; a link to an existing file is written through and kept; a dangling link is refused at read and at commit and its target is never created; a replaced global document is backed up and only the newest 20 per document are kept; a failed second write restores the first; a first run commits onto absent documents.
- [x] test_setup.py "a catalog set made while the wizard is open survives its save" fails before this ticket (exit 0, tier reverted). After the change it passes: exit 1, stderr names `lanes.json`, and the set's tier is on disk.
- [x] test_setup.py "a model swap made while the wizard is open survives its save" (newer-codex fixtures, `model_queue.scan` run inside the `run_curses` stub) fails before this ticket and passes after: the successor Lane stays in `lanes.json`.
- [x] test_setup.py "the full save writes through a linked catalog" fails before this ticket (link replaced) and passes after.
- [x] test_setup.py "the plain save refuses a catalog changed while it asked" passes.
- [x] test_catalog.py "a project set refuses a dangling link and creates nothing outside the project" fails before this ticket (the outside file is created) and passes after.
- [x] `catalog_edit.py` has none of `_write_preserving_link`, `_source_snapshot`, `_describe_source`, `_hash_source`, `_source_public`, `_loads_strict`, `_load_docs_from_snapshot` or `catalog_revision`, and `setup.py` calls no `catalog_edit.catalog_revision`. Existing test_catalog cases pass, changed only from `catalog_revision` to `read().revision`.
- [x] Every new test_setup case passes `--no-bench` and runs under a temporary `HOME`.
- [x] `tools/delegate-dashboard/test_dashboard.py` passes unchanged; the intervening-edit mark is still in `catalog_edit`'s source.
- [x] `make test` passes with `PYTHON=$(uv python find 3.9)` and with `python3.13`.
- [x] `references/architecture.md` and `references/catalog.md` name `catalog_commit` as the write path and describe the link rule and the backups. `CONTEXT.md`'s Catalog, Catalog read, Catalog commit and Intervening edit entries (added with the spec) match what shipped.

## Landed, 2026-10-11

Commit: `ed45ae9` ("delegate-deepening 09: A wizard save never overwrites a catalog change
made while it was open").

What shipped:

- `scripts/catalog_commit.py`: `DOCUMENTS`, `CatalogRead`, `Committed`, `CatalogChanged`,
  `read(config_dir=None, *, project_dir=None)` and `commit(read, documents)`. `read()` holds
  the source description, the revision hash (the same scheme `catalog_edit` used, so `catalog
  set`'s JSON is unchanged), strict JSON and validation, and refuses a dangling link or a
  loop. `commit()` validates, refuses an Intervening edit naming each changed document's path,
  skips documents equal to their read, backs up each replaced global document to
  `<config dir>/backups/<name>-<UTC stamp>.json` (newest 20 kept, project documents never),
  writes through links, and puts back what it already wrote when a later write fails.
- `catalog.link_target()` and `catalog.write_json`: a link to an existing file is written
  through and stays; a dangling link or a loop raises `CatalogError` naming the link and its
  target. `_write_preserving_link` is gone; `edit_catalog`, `write_focused` and
  `model_queue._write_applied` call `write_json`.
- `catalog_edit`: preview and apply read through `catalog_commit.read()`; the six source
  helpers and `catalog_revision` are deleted. The intervening-edit text is now the one
  constant `INTERVENING_EDIT`, still literal in the source for the dashboard's mark check.
- `setup`: one `catalog_commit.read()` at launch; `load_or_propose(snap, discovered)` reads no
  file of the catalog (the first-run sample proposal stays); `confirm_and_write(snap, ...)` and
  the full TUI save commit through it and print `wrote <path>` for each document written
  (`nothing changed; nothing written` when none), `Committed.lines` to stderr. On
  `CatalogChanged` setup prints the changed path and "nothing written" and exits 1. The
  focused branch takes `snap.revision` and keeps `write_focused` (D3). Agent files and the
  queue are still handled after a successful commit (D2).

Verified, each red on `5cdc8cc` first (the new tests run against an export of the base tree):

- `tests/test_catalog_commit.py`: "a commit writes only the documents that changed", "an
  intervening edit is refused and nothing is written", "a link retargeted since the read is
  refused", "an invalid document is refused and nothing is written", "a commit writes through
  a link to an existing file and keeps the link", "a dangling link is refused at read and at
  commit, and its target is never created", "a commit backs up what it replaces and keeps the
  newest twenty", "a write that fails puts back what the commit already wrote", "a first run
  commits onto absent documents".
- `tests/test_setup.py`: "a catalog set made while the wizard is open survives its save" (base:
  exit 0, tier 2), "a model swap made while the wizard is open survives its save" (base: the
  successor gone), "the full save writes through a linked catalog" (base: both links
  replaced), "the plain save refuses a catalog changed while it asked" (base: exit 0, the edit
  overwritten). Each runs `setup.main` in process with `--no-discover --no-bench` under a
  temporary `HOME` and its own model queue.
- `tests/test_catalog.py` 10.14 "a project set refuses a dangling link and creates nothing
  outside the project" (base: the outside file created).
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and 3.13:
  every file ok, the dashboard test included.

Deviations:

- `read()` takes no `queue` argument yet and `Committed.lines` is always empty: the queue and
  the Agent files are D2's, and nothing in D1 produces a line.
- `CONTEXT.md`'s Catalog commit entry drops "keeps the Agent files in step and forgets the
  Model queue entries its read returned" until D2 moves those into the commit; D2 restores
  the clause.
- test_setup's "the refreshed rows reach the new lanes" reached the Epoch URL and failed on
  the base under the proxy tripwire; it now passes the repo's Epoch fixture to
  `bench.collect`, as the spec's rule asks of any case that calls it.
- Reads now validate at once, so a stale `--expect` over an invalid document reports the
  validation error rather than "intervening edit"; apply's recheck counts a source that no
  longer reads as an intervening edit.
- The wizard's save prints only the paths it wrote; a save that changed nothing prints
  `nothing changed; nothing written`.
