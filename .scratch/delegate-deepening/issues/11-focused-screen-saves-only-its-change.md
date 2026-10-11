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

**Status:** landed 2026-10-11 (454b5ea, with the review fixes in "delegate-deepening D: review fixes"). A focused setup screen now starts from the catalog as read with no generation proposed, and its save commits only the documents the screen changed through the launch `catalog_commit` read, so a one-Lane toggle writes that Lane and the Orders it moved, and an Intervening edit is refused naming the file; `write_focused` is gone. Verified by four new test_setup cases ("a focused tier screen saves only the change made on it" and "a focused save refuses a catalog changed since launch" red on the base first; the routing and no-change cases red against a commit of both documents); no box is open.

- [x] test_setup.py "a focused tier screen saves only the change made on it" (frozen refresh-2026-09-22 `lanes.json`, `--fixture-dir`, `--no-bench`, `--screen tier3`, one Lane toggled) fails before this ticket, where 20 Lanes are added and 17 removed. After the change it passes: the Lane names are unchanged, and only that Lane's tier and the Orders it moved differ.
- [x] A focused save whose screen changed no routing field leaves `routing.json`'s bytes and mtime unchanged, even when the catalog lacks a shipped Class.
- [x] A focused save refuses a catalog changed since launch: exit 1, nothing written.
- [x] The test_setup.py tail block "focused writes preserve stow and revisions" is deleted; its no-op, link and revision cases live in `test_catalog_commit.py`.
- [x] `setup.py` has no `write_focused` and no `catalog_revision` call.
- [x] `make test` passes on 3.9 and 3.13. The focused-setup paragraph in `references/architecture.md` says the screen proposes no generation.

## Landed, 2026-10-11

Commits: `454b5ea` ("delegate-deepening 11: A focused setup screen saves only the change made
on it"), then the review fixes in "delegate-deepening D: review fixes".

What shipped:

- `setup.main`: a focused screen (`--screen carry|tier1-4|review|routing`) skips
  `propose_generation`, so the Wizard starts from the catalog as read (refresh `None`), and
  the launch read is taken without the queue. The save hands `catalog_commit.commit` only
  the documents whose content differs from what the screen started with: the routing the
  screen shows carries every shipped Class (`catalog.with_default_classes`), so an unchanged
  routing is never passed and never written. A save with no change commits no document and
  prints `nothing changed; nothing written`; a catalog changed since launch raises
  `CatalogChanged`, and setup prints the changed path and "nothing written" and exits 1, as
  the full wizard does. A focused commit that writes the live catalog's lanes document also
  backs it up and keeps the Agent files in step, as every commit does.
- Deleted: `setup.write_focused`, the `focused_revision` local, and setup's now unused
  `validate_lanes`/`validate_routing` imports. `setup.py` makes no `catalog_revision` call.
- `test_setup.py`: `wizard_in_process` takes a `drive(wizard)` for the focused screens. The
  tail block "focused writes preserve stow and revisions" is deleted; its no-op, link and
  revision cases are `test_catalog_commit.py`'s "a commit writes only the documents that
  changed", "a commit writes through a link to an existing file and keeps the link" and "an
  intervening edit is refused and nothing is written", unchanged.
- Docs: the focused-setup paragraph of `references/architecture.md` says the screen proposes
  no generation and commits only what it changed; `references/catalog.md`'s Focused changes
  says the same and that a changed catalog stops the save; `CONTEXT.md`'s Generation entry
  says a focused screen proposes none; `setup_tui.Wizard._load`'s docstring likewise.

Verified (each new case runs `setup.main` in process with `--no-bench` and `--fixture-dir`
or `--no-discover` under a temporary `HOME`):

- "a focused tier screen saves only the change made on it": the frozen refresh-2026-09-22
  `lanes.json`, `--fixture-dir`, `--screen tier3`, space on the Lane under the cursor. On
  the base (`3b2956c`, run against an export of the base tree) it fails with 20 Lanes added
  and 17 removed; now the Lane names are unchanged, one Lane's Tier moved off or onto 3,
  every other change is an Order in one of those two Tiers, and routing.json is untouched.
- "a focused save refuses a catalog changed since launch": a `catalog set` lands while
  `--screen tier3` is open. On the base the refusal named no document; now exit 1, stderr
  names `lanes.json` and "nothing written", the set's bytes stay, no backup is made.
- "a focused save that changed no routing field leaves routing.json alone" (a routing
  without the shipped scout Class; a tier toggle writes lanes.json, routing.json keeps its
  bytes and mtime) and "a focused save with no change writes nothing" (carry, tier3, review
  and routing confirmed as opened: neither file's bytes or mtime change, no backups). Both
  pass on the base, whose `write_focused` compared against the shown routing; each fails
  when the focused branch commits both documents, the shape this ticket had to avoid.
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and
  3.13.16: every file ok, the dashboard test included.

Deviations:

- The ticket names one new test; four were added, one per behaviour the boxes name.
- A focused save on a first run (no `lanes.json`) compared against the sample it showed, as
  `write_focused` did, so a toggle there wrote `lanes.json` without `routing.json`, and the
  next setup run failed on the missing `routing.json`. Fixed in the review (below).

Review fixes ("delegate-deepening D: review fixes"):

- On a first run, a focused save that writes one document now also writes the other the read
  found absent, as the screen showed it, so the catalog is never left half written; a first
  run confirmed with no change still writes nothing. test_setup "a focused save on a first run
  writes the whole catalog" failed before the fix (only `lanes.json` written, the next run
  exited 1) and passes after. The focused-setup paragraph of `references/architecture.md`
  says so.
