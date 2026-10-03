# 26 — catalog.py splits along its seams

**What to build:** Move the edit engine (`catalog.py:1595-2486`) to `catalog_edit.py`, which removes the lazy import cycle with `rank`; give the class-guide checker its own module; move tier-lines next to the wizard and published-name identity next to bench; delete the registry facade (`catalog.py:46-92`). `catalog.py` keeps one job: load, validate and project the effective catalog.

From the module-depth review of PR #3: `.scratch/delegate-any-harness/research/2026-10-03-review-of-pr-3.md`.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed in delegate#6 2026-10-03. `catalog.py` (2668 lines) now loads, validates and projects only (1125 lines) and imports no delegate script but `harnesses` and `published_names`. Moved out: `catalog_edit.py` (the edit engine, which imports `rank` at load; the lazy `_rank_mod` is gone), `class_guides.py`, `tier_lines.py` (the wizard's one caller is `setup_tui`/`setup`), `published_names.py` (bench's name reconciliation), and `catalog_cli.py`, the `delegate catalog` command, since a CLI living in `catalog.py` would have to import the modules that import it. The registry facade is gone: callers ask `harnesses.NAMES`, `harnesses.EFFORTS`, `harnesses.get(h).efforts`, `harnesses.installed()` and `harnesses.constraint_error()`, and `restrict_to_harness` lives in `rank`. No shims re-export the moved names. Verified: `make test` on 3.9 and 3.13, and `delegate catalog check` on the sample catalog.

- [x] No import cycle between `catalog` and `rank`.
- [x] Callers import the new modules directly; no re-export shims remain.
- [x] `make test` passes on 3.9 and 3.13 with no behaviour change.
