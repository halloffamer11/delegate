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

**Status:** landed 2026-10-11. `bench.run` and `bench.run_model` read one Benchmark snapshot: the report reads Epoch from `--epoch-csv` or the web through the 24-hour cache, writes the report with Epoch skipped when the fetch fails, and names each source's origin; `inspect_model` takes rows. `case_the_report_names_the_epoch_file_it_read`, `case_an_epoch_outage_still_writes_the_report`, `case_the_report_dates_a_cached_epoch_fetch` and the model CLI case under the tripwire in test_bench.py verify it. No box is open.

- [x] `case_the_report_names_the_epoch_file_it_read` (test_bench.py; `write_epoch_csv(fixture_rows())` with `--date 2026-09-09`) fails on the parent commit with "fetched 2026-09-09" and passes with "read from <file>".
- [x] `case_an_epoch_outage_still_writes_the_report` (test_bench.py; `bench.py --effort-rows <aa rows>` with `HOME` a temp dir and the closed proxy) fails on the parent commit with exit 1 and passes with exit 0, the AA table and "Epoch AI: skipped".
- [x] A CSV without the expected header and a rows file that is not a list still exit 1 with a "bench: " message.
- [x] `bench.py model` reads named files only, reaches no URL under the tripwire, and keeps `fetched=False` in its JSON.
- [x] `inspect_model(query, lanes_doc, effort_rows=None, epoch_rows=None)` takes rows and builds `LaneEvidence`; `epoch_records` and `evidence_records` keep A2's evidence signatures.
- [x] grep finds `urlopen` only in `effort.fetch_page` and `load_effort_rows` defined only in `bench_snapshot.py`.
- [x] `make test` passes on Python 3.9 and 3.13; `references/architecture.md` says the report reads Epoch through the cache.

## Landed, 2026-10-11

**What shipped.**
- `bench.read_snapshot(effort_rows, epoch_csv, fetch)` is how both bench CLIs read the Benchmark
  snapshot: Artificial Analysis only from `--effort-rows` (decision H.5), Epoch from `local(--epoch-csv)`,
  else `web()` through the 24-hour cache when `fetch` (the report), else nothing (`bench.py model`,
  decision H.4). A named file that cannot be read raises `BenchError`, so it still exits 1 with
  "bench: <reason>"; a failed Epoch fetch is the Epoch `Origin`'s `failure`.
- `bench.run` writes the report from the snapshot's rows; an Epoch that cannot be fetched leaves the
  report written with "Epoch AI: skipped (<why>)" and the AA table, and exit 0 (decision H.3).
- `format_collection(data, snapshot=None, date=None)` prints each source's line from its `Origin`:
  "fetched <UTC date of the fetch>", "read from <file>" or "skipped (<why>)". `render_report` takes the
  two lines; `origin_phrase`, `skipped_line`, `epoch_source_line` and `aa_source_line` build them.
  setup's plain report passes its snapshot.
- `inspect_model(query, lanes_doc, effort_rows=None, epoch_rows=None)` takes rows and builds both
  `LaneEvidence`s itself; `epoch_records(evidence)` and `evidence_records(evidence)` are unchanged.
- Deleted from `bench`: `fetch_bytes`, `load_epoch`, `load_effort_rows`, `read_text_file` and the
  `urllib.request` and `tempfile` imports (`csv` and `io` left in H1). `urlopen` is now only in
  `effort.fetch_page`, and `load_effort_rows` is defined only in `bench_snapshot.py`.
- `references/architecture.md` says the report reads Epoch through the cache, what each source's line
  says, and that `bench.py model` reads named files only. `CONTEXT.md` already matched.

**How verified.** Red on the parent commit: `case_the_report_names_the_epoch_file_it_read` saw
"fetched 2026-09-09" for a named CSV; `case_an_epoch_outage_still_writes_the_report` exited 1 with
"bench: cannot read Epoch CSV: <urlopen error [Errno 111] Connection refused>";
`case_the_report_dates_a_cached_epoch_fetch` saw the report date for a cache 3 hours and 3 days old;
"bench acquires no rows itself" found `fetch_bytes`, `load_epoch`, `load_effort_rows`,
`read_text_file` and `urllib`; and the ticket 25 case "an Epoch row reaches a Lane in the scores table
and in model inspection alike" raised a TypeError on `epoch_rows=`. All pass after. The existing
header and not-a-list cases still exit 1 with "bench: ". The model CLI case runs under the closed
proxy and finds `fetched` False and the temp `HOME` empty. The two in-process `bench.fetch_bytes`
patches are gone, and every `run_bench` subprocess runs with every proxy variable at a closed port.
`grep` finds `urlopen` only in `effort.fetch_page` and one `def load_effort_rows`. `make test` passes
on Python 3.9 and on `python3.13`, with the proxy pointed at a closed port.

**Deviations.**
- A source's line says more than the three forms when its Origin does: a cached copy kept after a
  failed fetch reads "fetched <date> (a newer fetch failed: <why>)", AA rows the wizard fell back to
  read "read from --effort-rows (<why>)", and a skipped source names its Origin's failure in place of
  the generic reason. The report has no AA adapter, so its AA line keeps the page URLs and observed
  dates and adds nothing; the wizard's plain report adds AA's origin to the same line.
- `bench.py model --json` keeps its `inputs.epoch_csv` key, now true when Epoch rows were read, so the
  JSON stays stable.
- Several unreadable named files print one "bench: " line, joined with "; ". The messages are the
  snapshot's: "bench: effort-rows: <path>: expected a JSON list" and "bench: epoch-csv: <path>: Epoch
  CSV missing expected header".
- Added `case_the_report_dates_a_cached_epoch_fetch` and "bench acquires no rows itself" beyond the
  named cases, so the "fetched <date of the fetch>" line and the deletions have a test.
