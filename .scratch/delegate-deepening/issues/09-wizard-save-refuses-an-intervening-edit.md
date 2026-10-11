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

**Status:** ready-for-agent

- [ ] `tests/test_catalog_commit.py` passes these cases: unchanged documents keep bytes and mtime; an intervening edit or a retargeted link raises `CatalogChanged` naming the document and writes nothing; an invalid document writes nothing; a link to an existing file is written through and kept; a dangling link is refused at read and at commit and its target is never created; a replaced global document is backed up and only the newest 20 per document are kept; a failed second write restores the first; a first run commits onto absent documents.
- [ ] test_setup.py "a catalog set made while the wizard is open survives its save" fails before this ticket (exit 0, tier reverted). After the change it passes: exit 1, stderr names `lanes.json`, and the set's tier is on disk.
- [ ] test_setup.py "a model swap made while the wizard is open survives its save" (newer-codex fixtures, `model_queue.scan` run inside the `run_curses` stub) fails before this ticket and passes after: the successor Lane stays in `lanes.json`.
- [ ] test_setup.py "the full save writes through a linked catalog" fails before this ticket (link replaced) and passes after.
- [ ] test_setup.py "the plain save refuses a catalog changed while it asked" passes.
- [ ] test_catalog.py "a project set refuses a dangling link and creates nothing outside the project" fails before this ticket (the outside file is created) and passes after.
- [ ] `catalog_edit.py` has none of `_write_preserving_link`, `_source_snapshot`, `_describe_source`, `_hash_source`, `_source_public`, `_loads_strict`, `_load_docs_from_snapshot` or `catalog_revision`, and `setup.py` calls no `catalog_edit.catalog_revision`. Existing test_catalog cases pass, changed only from `catalog_revision` to `read().revision`.
- [ ] Every new test_setup case passes `--no-bench` and runs under a temporary `HOME`.
- [ ] `tools/delegate-dashboard/test_dashboard.py` passes unchanged; the intervening-edit mark is still in `catalog_edit`'s source.
- [ ] `make test` passes with `PYTHON=$(uv python find 3.9)` and with `python3.13`.
- [ ] `references/architecture.md` and `references/catalog.md` name `catalog_commit` as the write path and describe the link rule and the backups. `CONTEXT.md`'s Catalog, Catalog read, Catalog commit and Intervening edit entries (added with the spec) match what shipped.
