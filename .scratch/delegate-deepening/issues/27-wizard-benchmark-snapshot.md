# 27 — The wizard reads Epoch through the cache, and a fixture run reaches no URL

**What to build:** Candidate H, ticket H1 (lane bench-evidence, after all of A). Create
`agents/skills/delegate/scripts/bench_snapshot.py` with `snapshot()`, `web()`,
`fixture()`, `local()`, `load_effort_rows()`, `Snapshot` and `Origin`, and the one cache
directory policy: `aa/` as `effort.py aa` writes it, `epoch/eci_benchmarks.csv`, 24 hours
for both, renew refetches AA only, and an artifact is replaced only after it parsed. Move
the Epoch CSV parser out of `bench` (`bench` re-exports `EPOCH_URL` and
`EPOCH_BENCHMARKS`); its rows keep `model` and `slug` for A's attribution.

Split `effort.run_aa` into `effort.aa_accept(raw, url, out_dir, quiet)`, which the web
adapter calls, and the file-or-fetch front the `effort.py aa` CLI keeps.

Make `setup.scan` one `snapshot()` call on its fetch thread beside discovery, returning
`(discovered, discovery_data, snapshot)`; `setup.main` (launch, the `r` rescan, plain and
TUI), `collect_bench`, `show_bench` and `propose_generation` read it. Change only
`bench.collect`'s inputs, on top of A2's evidence-based body, to
`(lanes_doc, epoch_rows=None, effort_rows=None)`: when `epoch_rows` is None it keeps every
AA column and reports Epoch as skipped. `bench.run` passes `load_epoch`'s rows until H2.
Delete setup's AA cache code, its `load_effort_rows` and `scan`'s `fallback`.

Fix `case_the_refreshed_rows_reach_the_new_lanes` to pass `epoch_rows=None`, and make the
`make test` recipe point every proxy variable at a closed local port. The routing guard
test allows `lane_evidence`, which `catalog` imports for the `published_as` check, and
forbids `bench`, `bench_snapshot`, `bench_page` and `effort`. Add `bench_snapshot` to the
modules D2's "the scan imports no wizard module" finds absent.

The start page's rows line names both sources on one line. It is TUI text, so it goes to
a Claude Opus agent under `/frontend-design:frontend-design` (ADR 0001).

Rebase: this lane merges last. Rebase onto D's `setup.main` launch and rescan,
`propose_generation` (which D2 stopped from reading the queue) and start facts. Then run
the whole `make test` under the tripwire on 3.9 and 3.13 and fix any `setup.main` case
from the other lanes that still fetches.

Update `references/architecture.md`. `CONTEXT.md`'s Benchmark snapshot, Fetched source
and Accepted rows entries were added with the spec; keep them true to what ships.

Spec: `.scratch/delegate-deepening/spec.md` (H. Benchmark snapshot; decisions H.1, H.2 and H.4)

**Blocked by:** 25 An Epoch row reaches the same Lane in every benchmark view (the evidence-based `collect`); 26 One published name names one Model on every Harness that runs it (lane order: all of A before H)

**Status:** landed 2026-10-11 (71072e7; review fixes in "delegate-deepening H: review fixes"). `bench_snapshot.py` is the one place benchmark rows are acquired: the wizard's launch and `r` read one snapshot on the scan thread through a 24-hour cache, `bench.collect` takes rows, and `make test` runs behind a closed proxy; `case_a_rescan_opens_the_epoch_url_once`, `case_a_fixture_run_reaches_no_url`, the 15 cases of `tests/test_bench_snapshot.py` and test_setup_tui 63e verify it. One box stays open, not the user's to do: the start page box waits for a review under `/frontend-design:frontend-design`, which this session did not offer. The merge onto run-and-relay, catalog-write and meters-and-preview ("delegate-deepening: merge the bench-evidence lane") closed the other two: `setup.main` reads the Benchmark snapshot beside D's Catalog read (`benchmarks` beside `snap`), a focused screen still proposes no generation, and test_model_queue 14 finds `bench_snapshot` absent.

- [x] `case_a_rescan_opens_the_epoch_url_once` (test_setup.py; subprocess driver with `HOME` a temp dir, a fake `urlopen` serving `tests/fixtures/real_aa_model_page_sample.html` and `tests/fixture/bench-epoch.csv`, `run_curses` pressing enter then `r`) fails on the parent commit with the Epoch URL opened twice and passes with it opened once and the AA URL twice.
- [x] `case_a_fixture_run_reaches_no_url` (test_setup.py; `setup.py --plain` with `--fixture-dir tests/fixtures/refresh-2026-09-22`, and again with `--no-discover` and a saved discovery, both with `--effort-rows` that fixture's `aa-accepted.json` and every proxy variable at a closed local port) fails on the parent commit with "bench: cannot read Epoch CSV" and no AA table, and passes with exit 0, the AA table, "Epoch AI: skipped" and the reason in the start facts.
- [x] `bench_snapshot.snapshot()` never raises for a source; named-file failures are in `errors` and fetch failures in `Origin.failure`; `fixture()` and `local()` open no URL and never touch the cache.
- [x] `tests/test_bench_snapshot.py` covers fresh reuse, stale refetch, renew fetching AA only, the newest copy kept on a failed fetch with its age, named AA rows kept when nothing is cached, a bad fetched CSV never replacing the cache, named files combining in order and a bad one refusing all, fetched AA rows replacing only named AA rows, fixture reads, a bad named Epoch CSV being an error, and routing importing no benchmark module (`lane_evidence` allowed).
- [x] test_model_queue's "the scan imports no wizard module" also finds `bench_snapshot` absent.
- [x] `setup.refresh_effort_rows`, `aa_rows_path`, `_with_aa_rows`, `load_effort_rows`, `AA_CACHE_DIR`, `AA_MAX_AGE`, `AA_FIXTURE` and `scan`'s `fallback` are gone, with the five cache cases and the several-files case in test_setup.py.
- [x] `bench.collect(lanes_doc, epoch_rows=None, effort_rows=...)` acquires nothing and keeps every AA column; every `bench.collect(..., epoch_csv=...)` call in the tests passes `epoch_rows` instead.
- [x] `effort.py aa` behaves as before, and its CLI case in `test_effort.py` passes unchanged.
- [x] `make test` sets `http_proxy`, `https_proxy`, `HTTP_PROXY` and `HTTPS_PROXY` to `http://127.0.0.1:9`, with `no_proxy` and `NO_PROXY` set to `127.0.0.1,localhost`, and after the rebase onto the three earlier lanes it passes on Python 3.9 and 3.13.
- [ ] The start page's rows line names both sources on one line, with no page layout change, built under `/frontend-design:frontend-design`.
- [x] `CONTEXT.md`'s Benchmark snapshot, Fetched source and Accepted rows entries match what shipped; `references/architecture.md` describes the snapshot and the cache instead of `refresh_effort_rows`.

## Landed, 2026-10-11

**Commits.** 71072e7 (this ticket), then the review fixes in "delegate-deepening H: review fixes".

**What shipped.**
- `scripts/bench_snapshot.py`: `snapshot(row_files, aa=, epoch=, renew=)`, the `web()`, `fixture()`
  and `local()` adapters, `load_effort_rows`, `Snapshot`, `Origin` and `Fetched` (what an adapter
  returns; its `error` tells a named input that cannot be read from a note). The cache is
  `~/.cache/delegate/bench/`: `aa/` exactly as `effort.py aa` writes it and
  `epoch/eci_benchmarks.csv` as served, both fresh for 24 hours after the artifact's mtime. A fetch
  writes into a temporary directory beside the source's directory and moves the artifact in last,
  only after it parsed; a failed fetch keeps the newest copy on hand with its age, then the named AA
  rows; `renew` refetches AA only. The Epoch CSV parser moved here (private), and `bench`
  re-exports `EPOCH_URL` and `EPOCH_BENCHMARKS`; its rows keep `model` and `slug`.
- `effort.run_aa` is the `effort.py aa` front (a saved page or a fetch), and `effort.aa_accept(raw,
  url, out_dir, quiet)` extracts, writes and checks; the web adapter calls it.
- `setup.scan(args, lanes_doc, force)` returns `(discovered, discovery_data, snapshot)` from one
  `setup.read_benchmarks` on its thread; launch, the `r` rescan, plain and TUI, `show_bench`,
  `collect_bench` and `propose_generation(lanes_doc, discovery_data, effort_rows)` read it.
  `refresh_effort_rows`, `aa_rows_path`, `_with_aa_rows`, `load_effort_rows`, `AA_CACHE_DIR`,
  `AA_MAX_AGE`, `AA_FIXTURE`, `scan`'s `fallback` and the `effort_row_paths` threading are gone.
- `bench.collect(lanes_doc, epoch_rows=None, effort_rows=None)` acquires nothing; with no Epoch
  rows it keeps every AA column, sets `epoch_skipped` and the report says "Epoch AI: skipped (no
  Epoch CSV read)". `bench.run` passes `load_epoch`'s rows until H2.
- The start page's rows line is the snapshot's `note`, both sources on one line:
  `Benchmark rows: AA fetched 3h ago, Epoch fetched 3h ago`, and after a failure
  `...; AA and Epoch: cannot fetch: <reason>`. Its `errors` join the TUI's first message and print
  under `--plain`.
- `make test` points `http_proxy`, `https_proxy`, `HTTP_PROXY` and `HTTPS_PROXY` at
  `http://127.0.0.1:9`, with `no_proxy` and `NO_PROXY` at `127.0.0.1,localhost`.
- `references/architecture.md` describes the snapshot and the cache in place of
  `refresh_effort_rows`; `references/maintenance.md` names the tripwire. `CONTEXT.md`'s Benchmark
  snapshot, Fetched source and Accepted rows entries already matched and are unchanged.

**How verified.** Red on the parent commit: `case_a_rescan_opens_the_epoch_url_once` saw the Epoch
URL opened twice (AA twice); `case_a_fixture_run_reaches_no_url` printed "bench: cannot read Epoch
CSV: <urlopen error [Errno 111] Connection refused>" and no AA table. Both pass after, the second
with "Epoch AI: skipped", the AA table and the reason on the rows line, and the temp `HOME` left
empty. `tests/test_bench_snapshot.py` (new, 14 cases) covers every case the spec lists, plus no rows
and no note when nothing is named, a fetch reason with its URL left out, and a source with no
adapter named on the rows line. test_setup_tui "63e the start page names both benchmark sources on
one rows line, at 80 columns" checks the line fits and the page keeps its layout. The test_setup
readers of the scan (`case_plain_prints_the_start_facts`, `case_scan_and_propose_are_the_launch_steps`,
the rescan-save case, `case_plain_collects_bench_in_process`) read the snapshot, and every
`bench.collect(..., epoch_csv=...)` in test_bench, test_bench_page and test_setup_tui passes
`epoch_rows=snapshot((), epoch=local(FIXTURE)).epoch_rows`. test_effort's CLI case is unchanged.
`make test` passes on Python 3.9 and on `python3.13`, with the proxy pointed at a closed port and
also with only the recipe's own tripwire.

**Deviations.**
- Rebase not done here: this step may not rebase, and catalog-write, meters-and-preview and
  run-and-relay are not on this branch. At merge, rebase `setup.main`'s launch and rescan,
  `propose_generation` (D2 stops it reading the queue) and the start facts onto D, add
  `bench_snapshot` to D2's "14. the scan imports no wizard module" in test_model_queue, and run
  `make test` on 3.9 and 3.13 again.
- `/frontend-design:frontend-design` was not offered in this session, so the rows line was built by
  this Claude Opus agent without it. It names the sources "AA" and "Epoch", the wizard's own column
  names ("AA mean rank", "Epoch mean rank"), and puts both statuses before the reasons, merging a
  reason both share, so both sources stay in sight at 80 columns after a failed fetch; reasons leave
  out the URL `effort.fetch_page` puts in front. The Markdown report keeps the full names.
- The note is "" only when nothing was named and no source had an adapter (the spec: "" when no
  source had an adapter). An offline run with `--effort-rows` names both sources and says Epoch
  needs `--epoch-csv`, which the fixture-run case's "reason in the start facts" needs.
- `--no-bench` read no Epoch at first. The review reverted that to the spec's usage (Epoch comes
  from where AA does), because the rows line then told a `--no-bench` run to name `--epoch-csv`.
- The web adapter treats an AA page whose check accepts no row as unparsed, so it never replaces
  the cache with an empty list.
- `bench.load_epoch` stays until H2 and reads through the snapshot: a named CSV through `local`,
  else `web()` over a throwaway cache with `get=fetch_bytes`, so the report still fetches on every
  run and test_bench's in-process `fetch_bytes` patches keep their meaning until H2 deletes them.
- `collect_bench` returns the data or None, no message: it cannot fail for a source. The plain
  report no longer stops at an unreadable rows file; it prints the error line and renders the
  report with AA skipped, as an unreadable Epoch file leaves AA standing.
- `collect` drops the "absent from Epoch AI" notes when Epoch is skipped, and test_setup_tui's
  "collect returns documented keys" gains `epoch_skipped`. test_setup_tui's older cases that pass a
  literal `rows_note` keep their strings; they test that the page shows the line it is given.

**Review fixes (code-review on both axes, red first).**
- `setup.read_benchmarks` passes Epoch the adapter AA gets unless `--epoch-csv` names a file, as
  the spec's usage does; test_setup "no-bench reads Epoch where the run reads its rows" was red
  with "Epoch: no --epoch-csv" on a fixture run that held `epoch.csv`.
- The web adapter fetches before it touches the cache, so a failed fetch with nothing cached
  leaves no empty `aa/` or `epoch/` directory; test_bench_snapshot "a failed fetch with nothing
  cached leaves no cache directory behind" was red with both.
- One private `_epoch_file` reads a saved CSV for both the cached and the named copy, and the BOM
  check is spelled `"\ufeff"` instead of a literal invisible character.
- `references/catalog.md` says the wizard fetches Epoch through the 24-hour cache too, and that `r`
  fetches AA again.

