# 11 — One harness registry

**What to build:** one module per harness under `scripts/harnesses/` behind one interface — binary name, efforts (and effort-in-slug for agy), `discover()`, `probe()`, `run_args()`, optional event parsing — and one registry every script iterates. Today the harness list exists four times (`catalog.py:39`, `browser_probes.py:32`, `ads.sh:17`, `discover.py:124`), `shutil.which(<harness>)` five times, and per-harness if/elif chains in `discover.py:461`, `usage.py:219-400`, `delegate.py:441-473` and `catalog.py:56`. Pure moves first: no behaviour change.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** 01 Scripts run on the Python every entry point calls; 07 One way to ask whether a harness CLI is installed.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] Adding a harness means adding one module and one registry entry; no other script names a harness.
- [ ] `ads.sh` reads the harness list from the registry (or a file it generates).
- [ ] The binary name comes from the adapter, so a harness whose CLI is not named after it (Kiro: `kiro-cli`) works.
- [ ] `make test` passes before and after with no fixture changes beyond imports.
