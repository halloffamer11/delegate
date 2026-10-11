# 11 — A focused setup screen saves only the change made on it

**What to build:** Candidate D, ticket D3 (lane catalog-write). This ticket owns the
focused screen's start for the whole effort; F3 builds on it.

`setup.main` stops proposing the generation on a focused screen
(`--screen carry|tier1-4|review|routing`). The screen starts from the catalog as read,
with no refresh, as `Wizard._load` already promises for carry proposals. The focused save
commits that read through `catalog_commit` without the queue.

A focused commit passes only the documents whose content the screen changed. Setup
applies `catalog.with_default_classes` to the routing it shows, and committing that
routing would write a file the confirm page never listed.

`write_focused` and the separate focused revision check go. A focused save with no change
writes nothing. A focused save after an Intervening edit prints which document changed
and exits 1.

The new test runs `setup.main` with `--no-bench` under a temporary `HOME`.

Spec: `.scratch/delegate-deepening/spec.md` (D. Catalog commit; decision D.6, which is also F.4)

**Blocked by:** 09 A wizard save never overwrites a catalog change made while it was open

**Status:** ready-for-agent

- [ ] test_setup.py "a focused tier screen saves only the change made on it" (frozen refresh-2026-09-22 `lanes.json`, `--fixture-dir`, `--no-bench`, `--screen tier3`, one Lane toggled) fails before this ticket, where 20 Lanes are added and 17 removed. After the change it passes: the Lane names are unchanged, and only that Lane's tier and the Orders it moved differ.
- [ ] A focused save whose screen changed no routing field leaves `routing.json`'s bytes and mtime unchanged, even when the catalog lacks a shipped Class.
- [ ] A focused save refuses a catalog changed since launch: exit 1, nothing written.
- [ ] The test_setup.py tail block "focused writes preserve stow and revisions" is deleted; its no-op, link and revision cases live in `test_catalog_commit.py`.
- [ ] `setup.py` has no `write_focused` and no `catalog_revision` call.
- [ ] `make test` passes on 3.9 and 3.13. The focused-setup paragraph in `references/architecture.md` says the screen proposes no generation.
