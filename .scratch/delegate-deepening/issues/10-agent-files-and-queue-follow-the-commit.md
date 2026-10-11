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

**Status:** landed 2026-10-11. `catalog_commit.commit` now keeps the Agent files in step with the live catalog's lanes and forgets exactly the Model queue entries a `read(queue=True)` returned, and the wizard, its start facts and dispatch's scan go through it; setup and the scan write no Agent file and empty no queue themselves. Verified by seven new `test_catalog_commit.py` cases, two new test_setup cases and the rewritten rescan case, and test_model_queue cases 9, 13 and 14, each new or changed one red on the base first; no box is open.

- [x] `test_catalog_commit.py` passes these cases: native Lanes added and removed gain and lose their files under a temp `HOME`; a link at a Lane's path is replaced and its target is untouched; a template change reaches the Lanes already placed; a non-live catalog gets a note and no file; a commit of project documents alone writes no Agent file; a commit forgets exactly the entries its read returned; a read without the queue leaves the queue alone.
- [x] test_setup.py "a model noticed while the wizard is open stays queued" (`--fixture-dir` refresh-2026-09-22, `--no-bench`, `model_queue.note` inside the `run_curses` stub) fails before this ticket and passes after.
- [x] test_setup.py "a save gives every native Lane in the catalog its agent file" (temp `HOME` live layout, `--no-discover`, `--no-bench`, claude Lanes with no files) fails before this ticket and passes after.
- [x] The rescan case in test_setup.py checks the agent files of the Lanes saved, without monkeypatching `native_targets` or `catalog.CONFIG_DIR`.
- [x] test_model_queue.py "the scan imports no wizard module" passes: after a fixture scan in a subprocess, `setup`, `setup_tui`, `bench`, `bench_page` and `effort` are absent from `sys.modules` (H1 later adds `bench_snapshot` to the list).
- [x] test_model_queue.py "a scan whose catalog changed while it listed models writes nothing and still queues" replaces case 13. Case 9 finds its backup under `<cfg>/backups`. Cases 7 and 9c are deleted.
- [x] No script but `catalog_commit` writes or removes an Agent file, and `setup.py` and `model_queue.py` no longer contain the names listed above.
- [x] `CONTEXT.md`'s Agent file, Model swap and Model queue entries (added with the spec) match what shipped.
- [x] `make test` passes on 3.9 and 3.13. `references/architecture.md` and `model_queue`'s docstring state the new queue rule (forget what the start page named) and where backups live, and redesign ticket 29 records that its queue sentence was replaced.

## Landed, 2026-10-11

What shipped:

- `catalog_commit`: `read(..., queue=True)` also returns `queued` (the models dispatch
  noticed) and `applied` (the Model swaps its scan applied); a queue that cannot be read is
  empty. After a successful write, `commit` runs two more steps. When `documents` holds the
  global `lanes` document and the config dir resolves to `catalog.CONFIG_DIR`, every Lane on a
  native profile's harness gets a plain Agent file in the template's current text (`wrote`,
  `updated`, or nothing when it already matches), a link at a Lane's path is removed and
  replaced, never written through, and every native Lane the read had that the commit took out
  loses its file (`removed`). Another catalog gets one note line, and a commit of project
  documents alone touches no Agent file. Then it forgets exactly the entries its read returned
  (`model_queue.forget`), keeping entries added since and the last scan time. A failure in
  either step is a note line in `Committed.lines`.
- `setup`: the full wizard (TUI and `--plain`) reads with `queue=True`; focused screens read
  none. The start facts take `queued` and `applied` from the read
  (`setup_tui.start_facts`/`refresh_lines`, and the `Wizard` keeps them across a rescan), so
  "Dispatch noticed" and "Dispatch swapped in" show whether or not the refresh ran.
  `propose_generation` no longer reads `model_queue`. Both saves print `Committed.lines` to
  stderr. Deleted: `native_agent_text`, `native_agents_dir`, `native_targets`,
  `save_native_agents`, `save_all_native_agents`, `clear_queue`, and setup's imports of
  `model_queue`, `orchestrators` and `harnesses`.
- `model_queue.scan` reads with `catalog_commit.read` and commits the swapped lanes with
  `catalog_commit.commit`, so the backup goes to `<config dir>/backups` and the Agent files
  follow; on `CatalogChanged` it writes nothing, leaves the catalog to the writer in between,
  and queues the newer version. Deleted: `clear`, `_backup`, `_write_applied` and its imports
  of `setup` and `catalog_edit`; added `forget`. `discover.model_takes_effort` is deleted
  (catalog_commit asks the harness adapter directly).
- Docs: `model_queue`'s docstring, `references/architecture.md` and `references/catalog.md`
  state the new queue rule and where backups live; `CONTEXT.md`'s Catalog commit entry gets back
  its Agent-file and queue clause and the Model queue entry says a run that named the entries
  and saved forgets them; the Makefile's `delegate-wizard` note says every native lane.

Verified, each new or changed case red on `ed45ae9` first (the new test files run against an
export of the base tree):

- `tests/test_catalog_commit.py`: "native Lanes added and removed gain and lose their agent
  files" (byte-for-byte text of `lane-opus55-high.md`), "a link at a Lane's agent path is
  replaced and its target is untouched", "a template change reaches the Lanes already placed",
  "a catalog that is not the live one gets no agent file and a note", "a commit of project
  documents alone writes no agent file", "a commit forgets exactly the queue entries its read
  returned" (and a refused commit forgets nothing), "a read without the queue leaves the queue
  alone". Red on the base: no Agent file written, and `read()` took no `queue`. The link,
  template, live and project rules were each also checked by breaking that rule in the code
  and seeing only its case fail.
- `tests/test_setup.py`: "a model noticed while the wizard is open stays queued" (base: the
  queue emptied), "a save gives every native Lane in the catalog its agent file" (base: no
  file), "the save after a rescan writes the agent files of the Lanes it saved" (base: only the
  five opus55 files; it now runs under a temp `HOME` with no monkeypatching of
  `native_targets` or `catalog.CONFIG_DIR`). Each runs `setup.main` with `--no-bench` and
  `--no-discover` or `--fixture-dir` under a temporary `HOME`.
- `tests/test_model_queue.py`: 9 finds its backup under `<cfg>/backups` (base: none there), 13
  "a scan whose catalog changed while it listed models writes nothing and still queues" (it
  passes on the base too: it restates the old byte check at the scan's interface), and 14 "the
  scan imports no wizard module" (base: all five loaded). Cases 7 and 9c are deleted.
- `make test` with the proxy variables pointed at a closed port, on Python 3.9.25 and 3.13:
  every file ok, the dashboard test included.

Deviations:

- The ticket and the spec name "redesign ticket 29"; the queue sentence is in the any-harness
  effort's ticket 29 (`.scratch/delegate-any-harness/issues/29-dispatch-queues-models-the-catalog-lacks.md`),
  and that ticket records the replacement. The redesign's ticket 44, which describes the old
  `lanes-backups/` folder, is left as history.
- The `frontend-design:frontend-design` skill was not available in the session that built
  this ticket. The start-page change was made by a Claude Opus agent and kept to the ticket's
  words: the same two lines ("Dispatch noticed", "Dispatch swapped in") now come from the read
  and show when the refresh did not run; no page shows anything else new, and the
  "every model is the current generation" line still appears only when the refresh ran and
  nothing at all is listed.
- The test_setup agent-file cases at the setup seam
  (`native_agent_files_follow_the_claude_lanes`, `a_catalog_elsewhere_gets_no_agent_file`,
  `the_live_catalog_gets_the_agent_files`, `the_real_layout_saves_the_agent_files`,
  `a_template_change_reaches_the_placed_lanes`) are deleted with the functions they called;
  the `test_catalog_commit.py` cases above replace them. Three test_setup assertions changed
  with the interface: "scan and propose are the launch steps" no longer pops `queued` and
  `applied` from the plan, "plain prints the refresh change lines" finds the agent-file note on
  stderr, and test_model_queue cases 6 and 9b read the start facts from a `read(queue=True)`.
  Case 8 gets a queue of its own, since case 7 no longer empties the one before it.
- A save that changed no document still forgets the queue entries it named, as the old
  confirm write emptied the queue on any `y`. The non-live note counts the native Lanes after
  the commit and says nothing when there are none.
- The scan prints its commit's lines to stderr; a scan that dispatch starts discards them.
