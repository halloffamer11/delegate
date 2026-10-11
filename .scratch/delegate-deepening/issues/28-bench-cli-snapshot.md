# 28 — The benchmark report and model inspection read the same snapshot as the wizard

**What to build:** Candidate H, ticket H2 (lane bench-evidence). Move `bench.run` and
`bench.run_model` onto `bench_snapshot.snapshot()`. The report reads Epoch from
`local(--epoch-csv)`, or from `web()` through the 24-hour cache, and AA only from
`--effort-rows` (decision H.5). Model inspection reads named files only and never
fetches. A named input that cannot be read still exits 1 with "bench: <reason>". An Epoch
that cannot be fetched writes the report with Epoch skipped and the reason (decision
H.3).

`inspect_model(query, lanes_doc, effort_rows=None, epoch_rows=None)` takes rows and builds
`LaneEvidence` from them itself. `epoch_records(evidence)` and `evidence_records(evidence)`
keep A2's evidence-taking signatures; `run` and `run_model` build the evidence from the
snapshot's rows. `format_collection(data, snapshot, date)` prints each source's line from
its `Origin`: "fetched <date of the fetch>", "read from <file>" or "skipped (<why>)".

Delete `bench.fetch_bytes`, `load_epoch`, `load_effort_rows` and `read_text_file`, and the
`urllib`, `csv` and `io` imports in `bench`, together with the in-process `fetch_bytes`
patches in `test_bench.py`.

Spec: `.scratch/delegate-deepening/spec.md` (H. Benchmark snapshot; decisions H.3, H.4 and H.5)

**Blocked by:** 27 The wizard reads Epoch through the cache, and a fixture run reaches no URL

**Status:** ready-for-agent

- [ ] `case_the_report_names_the_epoch_file_it_read` (test_bench.py; `write_epoch_csv(fixture_rows())` with `--date 2026-09-09`) fails on the parent commit with "fetched 2026-09-09" and passes with "read from <file>".
- [ ] `case_an_epoch_outage_still_writes_the_report` (test_bench.py; `bench.py --effort-rows <aa rows>` with `HOME` a temp dir and the closed proxy) fails on the parent commit with exit 1 and passes with exit 0, the AA table and "Epoch AI: skipped".
- [ ] A CSV without the expected header and a rows file that is not a list still exit 1 with a "bench: " message.
- [ ] `bench.py model` reads named files only, reaches no URL under the tripwire, and keeps `fetched=False` in its JSON.
- [ ] `inspect_model(query, lanes_doc, effort_rows=None, epoch_rows=None)` takes rows and builds `LaneEvidence`; `epoch_records` and `evidence_records` keep A2's evidence signatures.
- [ ] grep finds `urlopen` only in `effort.fetch_page` and `load_effort_rows` defined only in `bench_snapshot.py`.
- [ ] `make test` passes on Python 3.9 and 3.13; `references/architecture.md` says the report reads Epoch through the cache.
