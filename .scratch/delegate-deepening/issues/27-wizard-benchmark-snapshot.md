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

**Status:** ready-for-agent

- [ ] `case_a_rescan_opens_the_epoch_url_once` (test_setup.py; subprocess driver with `HOME` a temp dir, a fake `urlopen` serving `tests/fixtures/real_aa_model_page_sample.html` and `tests/fixture/bench-epoch.csv`, `run_curses` pressing enter then `r`) fails on the parent commit with the Epoch URL opened twice and passes with it opened once and the AA URL twice.
- [ ] `case_a_fixture_run_reaches_no_url` (test_setup.py; `setup.py --plain` with `--fixture-dir tests/fixtures/refresh-2026-09-22`, and again with `--no-discover` and a saved discovery, both with `--effort-rows` that fixture's `aa-accepted.json` and every proxy variable at a closed local port) fails on the parent commit with "bench: cannot read Epoch CSV" and no AA table, and passes with exit 0, the AA table, "Epoch AI: skipped" and the reason in the start facts.
- [ ] `bench_snapshot.snapshot()` never raises for a source; named-file failures are in `errors` and fetch failures in `Origin.failure`; `fixture()` and `local()` open no URL and never touch the cache.
- [ ] `tests/test_bench_snapshot.py` covers fresh reuse, stale refetch, renew fetching AA only, the newest copy kept on a failed fetch with its age, named AA rows kept when nothing is cached, a bad fetched CSV never replacing the cache, named files combining in order and a bad one refusing all, fetched AA rows replacing only named AA rows, fixture reads, a bad named Epoch CSV being an error, and routing importing no benchmark module (`lane_evidence` allowed).
- [ ] test_model_queue's "the scan imports no wizard module" also finds `bench_snapshot` absent.
- [ ] `setup.refresh_effort_rows`, `aa_rows_path`, `_with_aa_rows`, `load_effort_rows`, `AA_CACHE_DIR`, `AA_MAX_AGE`, `AA_FIXTURE` and `scan`'s `fallback` are gone, with the five cache cases and the several-files case in test_setup.py.
- [ ] `bench.collect(lanes_doc, epoch_rows=None, effort_rows=...)` acquires nothing and keeps every AA column; every `bench.collect(..., epoch_csv=...)` call in the tests passes `epoch_rows` instead.
- [ ] `effort.py aa` behaves as before, and its CLI case in `test_effort.py` passes unchanged.
- [ ] `make test` sets `http_proxy`, `https_proxy`, `HTTP_PROXY` and `HTTPS_PROXY` to `http://127.0.0.1:9`, with `no_proxy` and `NO_PROXY` set to `127.0.0.1,localhost`, and after the rebase onto the three earlier lanes it passes on Python 3.9 and 3.13.
- [ ] The start page's rows line names both sources on one line, with no page layout change, built under `/frontend-design:frontend-design`.
- [ ] `CONTEXT.md`'s Benchmark snapshot, Fetched source and Accepted rows entries match what shipped; `references/architecture.md` describes the snapshot and the cache instead of `refresh_effort_rows`.
