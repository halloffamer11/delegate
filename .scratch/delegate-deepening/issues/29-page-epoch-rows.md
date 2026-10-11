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

**Status:** ready-for-agent

- [ ] `case_the_page_lists_the_epoch_rows` (test_setup.py; `setup.main` with `--no-discover`, a saved discovery of every harness, `--epoch-csv tests/fixture/bench-epoch.csv` and `--effort-rows tests/fixtures/refresh-2026-09-22/aa-accepted.json`; `run_curses` reads `wizard.bench_page_path`) fails on the parent commit with no epoch row in the rows table and passes with the fixture's Epoch rows listed.
- [ ] `bench_page` defines no `_epoch_items`; the Epoch rows come from `LaneEvidence(...).records()`.
- [ ] A test_bench_page case asserts that `plot_data`'s boards and the carry proposals are identical with and without `epoch_rows`.
- [ ] After `r`, `rewrite_bench_page` writes the rescan's Epoch rows.
- [ ] No new page layout; the rows go into the existing table, and any layout change goes to a Claude Opus agent under `/frontend-design:frontend-design` (ADR 0001).
- [ ] `make test` passes on Python 3.9 and 3.13.
