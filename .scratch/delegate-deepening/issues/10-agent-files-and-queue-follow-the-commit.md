# 10 — Agent files and the model queue follow every catalog commit

**What to build:** Candidate D, ticket D2 (lane catalog-write).

Agent files: `commit()` derives them from the Lanes as read and the Lanes after the
commit. The sync runs only when the commit's documents include the global `lanes`
document of the live catalog (the config dir resolves to `catalog.CONFIG_DIR`); a commit
of project documents alone, such as the dashboard's project-scope `catalog set`, never
touches `~/.claude/agents`. When it runs, every Lane on a native profile's harness has a
plain Agent file in the template's current text, and every native Lane the commit
removed loses its file. A link at a Lane's path is replaced, never written through.
Another catalog gets one note line. A failed agent write is a note line, not an error.
Callers print `Committed.lines` to stderr.

The queue: `read(queue=True)` returns the queued models and the applied Model swaps.
`commit` forgets exactly those after a successful write and leaves entries added since.

The wizard: the full wizard (TUI and `--plain`) reads with the queue, and its start facts
name the read's queue whether or not the refresh ran. `propose_generation` stops reading
`model_queue`. The start-page text goes to a Claude Opus agent under
`/frontend-design:frontend-design`, per ADR 0001.

The dispatch scan: it reads and commits through `catalog_commit` and imports neither
`setup` nor `catalog_edit`. Its byte check and backup go, and a `CatalogChanged` leaves
the catalog to the writer in between and still queues.

Deleted: `setup.native_agent_text`, `native_agents_dir`, `native_targets`,
`save_native_agents`, `save_all_native_agents` and `clear_queue`;
`model_queue._write_applied`, `_backup` and `clear`; `discover.model_takes_effort`.

Every new test that runs `setup.main` passes `--no-bench`, plus `--no-discover` or
`--fixture-dir`, under a temporary `HOME`.

Spec: `.scratch/delegate-deepening/spec.md` (D. Catalog commit; decisions D.2, D.4 and D.7)

**Blocked by:** 09 A wizard save never overwrites a catalog change made while it was open

**Status:** ready-for-agent

- [ ] `test_catalog_commit.py` passes these cases: native Lanes added and removed gain and lose their files under a temp `HOME`; a link at a Lane's path is replaced and its target is untouched; a template change reaches the Lanes already placed; a non-live catalog gets a note and no file; a commit of project documents alone writes no Agent file; a commit forgets exactly the entries its read returned; a read without the queue leaves the queue alone.
- [ ] test_setup.py "a model noticed while the wizard is open stays queued" (`--fixture-dir` refresh-2026-09-22, `--no-bench`, `model_queue.note` inside the `run_curses` stub) fails before this ticket and passes after.
- [ ] test_setup.py "a save gives every native Lane in the catalog its agent file" (temp `HOME` live layout, `--no-discover`, `--no-bench`, claude Lanes with no files) fails before this ticket and passes after.
- [ ] The rescan case in test_setup.py checks the agent files of the Lanes saved, without monkeypatching `native_targets` or `catalog.CONFIG_DIR`.
- [ ] test_model_queue.py "the scan imports no wizard module" passes: after a fixture scan in a subprocess, `setup`, `setup_tui`, `bench`, `bench_page` and `effort` are absent from `sys.modules` (H1 later adds `bench_snapshot` to the list).
- [ ] test_model_queue.py "a scan whose catalog changed while it listed models writes nothing and still queues" replaces case 13. Case 9 finds its backup under `<cfg>/backups`. Cases 7 and 9c are deleted.
- [ ] No script but `catalog_commit` writes or removes an Agent file, and `setup.py` and `model_queue.py` no longer contain the names listed above.
- [ ] `CONTEXT.md`'s Agent file, Model swap and Model queue entries (added with the spec) match what shipped.
- [ ] `make test` passes on 3.9 and 3.13. `references/architecture.md` and `model_queue`'s docstring state the new queue rule (forget what the start page named) and where backups live, and redesign ticket 29 records that its queue sentence was replaced.
