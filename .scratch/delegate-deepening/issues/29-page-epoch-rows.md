# 29 — The benchmark page lists the Epoch rows beside the accepted rows

**What to build:** Candidate H, ticket H3 (lane bench-evidence, its last ticket). Give
`bench_page.write` and `render` an `epoch_rows` argument. The page's "Every row, with its
provenance" table and its header count list the Epoch rows through A's display records,
`LaneEvidence(lanes_doc, epoch_rows).records()`, each shown in the table's columns:
source epoch linked to `EPOCH_URL`, standing, and the Epoch cost basis. There is no
page-only mapping of Epoch rows. The plots, the boards and the carry verdicts never take
Epoch rows.

`Wizard` takes `epoch_rows` and passes it in `rewrite_bench_page`; `setup.main` passes
`snapshot.epoch_rows` at launch, and the rescan dict carries it. Rebase: F2 (catalog-write,
merged first) rewrote the Wizard; add the argument on top of it.

Spec: `.scratch/delegate-deepening/spec.md` (H. Benchmark snapshot)

**Blocked by:** 27 The wizard reads Epoch through the cache, and a fixture run reaches no URL

**Status:** landed 2026-10-11 (0789532; review fixes in "delegate-deepening H: review fixes"). `bench_page.write` and `render` take `epoch_rows`, and the page's "Every row, with its provenance" table lists them as `bench.epoch_records` over their own `LaneEvidence`; the wizard writes them at launch and again after `r`. `case_the_page_lists_the_epoch_rows` and `case_a_rescan_rewrites_the_page_with_its_epoch_rows` in test_setup.py and "the Epoch rows reach the rows table and never the plots, the boards or the verdicts" in test_bench_page.py verify it. No box is open.

- [x] `case_the_page_lists_the_epoch_rows` (test_setup.py; `setup.main` with `--no-discover`, a saved discovery of every harness, `--epoch-csv tests/fixture/bench-epoch.csv` and `--effort-rows tests/fixtures/refresh-2026-09-22/aa-accepted.json`; `run_curses` reads `wizard.bench_page_path`) fails on the parent commit with no epoch row in the rows table and passes with the fixture's Epoch rows listed.
- [x] `bench_page` defines no `_epoch_items`; the Epoch rows come from `LaneEvidence(...).records()`.
- [x] A test_bench_page case asserts that `plot_data`'s boards and the carry proposals are identical with and without `epoch_rows`.
- [x] After `r`, `rewrite_bench_page` writes the rescan's Epoch rows.
- [x] No new page layout; the rows go into the existing table, and any layout change goes to a Claude Opus agent under `/frontend-design:frontend-design` (ADR 0001).
- [x] `make test` passes on Python 3.9 and 3.13.

## Landed, 2026-10-11

**Commits.** 0789532 (this ticket). The H review changed nothing on the page; with its fix to
`setup.read_benchmarks` (ticket 27), a `--no-bench` wizard run's page lists the Epoch rows too.
That fix is in "delegate-deepening H: review fixes".

**What shipped.**
- `bench_page.write(path, bench, lanes_doc, effort_rows=None, epoch_rows=None)` and `render(...)`
  take the Benchmark snapshot's Epoch rows. Only the rows table reads them: `_rows_block` lists
  `bench.epoch_records(LaneEvidence(lanes_doc, epoch_rows))`, A's display records, beside the
  accepted rows, and its summary count counts them. An Epoch row shows `epoch` linked to
  `EPOCH_URL`, its standing and the Epoch cost basis in the table's existing columns, and carries no
  verdict note.
- The rows table now prints display records for every row. `_annotate` keeps each accepted row's
  record as `_record` and no longer copies seven of its fields (`_identity`, `_identity_reason`,
  `_version`, `_standing`, `_cost_basis`, `_direction`, `_attributed`) onto the item; carry's notes
  for an accepted row moved into `_verdict_notes`. `bench_page` defines no `_epoch_items`, and there
  is no page-only mapping of Epoch rows.
- `setup_tui.Wizard` takes `epoch_rows`, `_load` keeps it, the rescan dict's `epoch_rows` replaces it
  on `r`, and `rewrite_bench_page` passes it. `setup.main` writes the launch page and builds the
  Wizard with `snap.epoch_rows`, and its rescan returns `again.epoch_rows`.
- `references/architecture.md` says the rows table lists the snapshot's Epoch rows and that `o`
  rewrites them, the rescan's after `r`. `CONTEXT.md` already matched.

**How verified.** Red first. `case_the_page_lists_the_epoch_rows` (in process, `--no-discover`, a
saved discovery of every harness, the Epoch fixture and the refresh fixture's accepted rows, under a
temporary `HOME`) found "68 rows" and no `epoch` row; `case_a_rescan_rewrites_the_page_with_its_epoch_rows`
(the named CSV loses its Grok rows between launch and `r`) found no Epoch row at launch or after;
and the test_bench_page case raised a TypeError on `epoch_rows=`. Green: the launch page lists the
fixture's 25 Epoch rows by benchmark, published name and effort, each with the Epoch cost basis and
a standing cell, and counts 93 rows; the rewrite after `r` lists 20 with no Grok row; the page's
plot data (equal to `plot_data`'s), the boards block and the verdict lines are identical with and
without `epoch_rows`, while the rows count grows by 25. `HOME` stays empty in both setup cases.
`make test` passes on Python 3.9 and on `python3.13`, with the proxy pointed at a closed port.

**Deviations.**
- An Epoch score prints as the scores table prints it, a percentage to one decimal (0.98 is
  "98.0"); the rows table's one-decimal score format would print most Epoch figures as "1.0". It is
  the one source check in the table, and no layout changed.
- F2 (catalog-write) is not on this branch, so `epoch_rows` went onto the Wizard as it stands here;
  the merge adds it on top of F2's Wizard.
- The rows table reads an accepted row's source, benchmark, score and cost from its display record
  rather than the raw row. They differ only for a row with no source or benchmark ("?" where the
  table printed "—") or a numeric string score, which accepted rows do not carry.
