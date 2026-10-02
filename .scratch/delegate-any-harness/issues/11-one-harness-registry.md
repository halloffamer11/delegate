# 11 — One harness registry

**What to build:** one module per harness under `scripts/harnesses/` behind one interface — binary name, efforts (and effort-in-slug for agy), `discover()`, `probe()`, `run_args()`, optional event parsing — and one registry every script iterates. Today the harness list exists four times (`catalog.py:39`, `browser_probes.py:32`, `ads.sh:17`, `discover.py:124`), `shutil.which(<harness>)` five times, and per-harness if/elif chains in `discover.py:461`, `usage.py:219-400`, `delegate.py:441-473` and `catalog.py:56`. Pure moves first: no behaviour change.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 01 Scripts run on the Python every entry point calls; 07 One way to ask whether a harness CLI is installed.

**Status:** landed 2026-10-02 (this ticket's commit on `claude/delegate-any-harness-next-v75vlw`). All boxes done, with one boundary: the four places that name `claude` as the orchestrator (`ORCHESTRATOR` in `delegate.py`, the native agent files in `setup.py`, `report.ignored` and the eval's orchestrator commands) are ticket 13's, which removes them. Raised by Orin 2026-10-02.

What landed: `scripts/harnesses/` with `base.Harness` and one module per harness (`claude`, `codex`, `agy`, `grok`), holding each harness's binary, efforts, effort-in-slug, vendor, list command and parser, Meter probe, relay flags and prompt note. `catalog`, `discover`, `usage`, `delegate`, `bench`, `bench_page`, `browser_probes` and `setup_tui` iterate the registry; `ads.sh` reads the relay list from `python3 scripts/harnesses relays`. No behaviour changed. Fixture data is untouched; test code changed only where a function moved (the parsers, the probes, `agy_family`, `claude_reset`, the count legend). New: `tests/test_harnesses.py`, which also proves a CLI is found by its adapter's binary, not the harness name. Verified with `make test` on Python 3.9 and 3.13 and `make eval-ping EVAL_ARGS=--offline`.

- [x] Adding a harness means adding one module and one registry entry; no other script names a harness.
- [x] `ads.sh` reads the harness list from the registry (or a file it generates).
- [x] The binary name comes from the adapter, so a harness whose CLI is not named after it (Kiro: `kiro-cli`) works.
- [x] `make test` passes before and after with no fixture changes beyond imports.
