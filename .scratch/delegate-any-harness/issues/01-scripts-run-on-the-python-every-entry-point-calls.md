# 01 — Scripts run on the Python every entry point calls

**What to build:** Every script parses on the Python that `python3` resolves to on Orin's machines, or the entry points name the interpreter they need. Today `scripts/delegate.py:172-232` and `scripts/bench_page.py:695` put a string literal with the same quote inside f-string braces, which only Python 3.12+ accepts, and 17 call sites run plain `python3`. Checked 2026-10-02: on 3.10 and 3.11 only those two files fail to compile.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-review-fixes-t6aitx`). All boxes done.

- [x] The supported minimum Python is stated once (README and `make test`), and it is no newer than the oldest `python3` on the Mac or omarchy.
- [x] Every script and `tools/delegate-dashboard/*.py` compiles on that minimum (`python3.X -m py_compile`).
- [x] `make test` fails fast with a clear message on an older interpreter instead of a SyntaxError traceback.

## Landed, 2026-10-02

The minimum is Python 3.9, macOS's `/usr/bin/python3`; omarchy's Arch `python3` is
newer. Six f-strings blocked it: the five `", "` literals in `scripts/delegate.py`, the
backslash quote in `scripts/bench_page.py` (now the `NOT_CARRIED` constant) and two in
the tests (`test_bench_page.py`, `test_discover.py`), which the ticket's 3.10/3.11 check
missed because it compiled scripts only. Nothing else needed 3.10+: the dashboard's
`X | None` annotations sit behind `from __future__ import annotations`.

Codex's review of PR #2 found one runtime gap that compiling misses:
`tools/delegate-dashboard/open.py` imported `tomllib` (3.11+), so it failed on 3.9 even
for `--help`. It now uses `tomllib` when present and otherwise reads the two ids it
needs from the manifest itself (`_read_manifest_ids`).

The README states the minimum. `make test` takes `PYTHON=` and stops first with
`make test: delegate needs Python 3.9 or newer; … is 3.8.20` on an older one.

Verified: every script, test and `tools/delegate-dashboard/*.py` passes
`python3.9 -m py_compile` (3.9.23), and every script and dashboard module imports on
3.9; `test_dashboard.py` `OpenManifestTest` reads the manifest through `open.py`; `make test PYTHON=python3.9` gives the same result
as 3.13 (all ok except `test_report.py`, ticket 07); `make test PYTHON=python3.8` stops
with the message above.
