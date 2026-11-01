# Delegate TUI and benchmark page polish

The user asked on 2026-10-30 for an end-to-end run of the delegate skill and a
redesign of tier selection: the benchmark page's plot should be the main way to
pick lanes, efforts must show on the plot and in the TUI, the side panel must not
move a row when a tier is picked, hovering a model must show in the plot, the
harnesses this machine uses should be preselected (no kiro here), and the TUI
should nest harness, model class and effort, with a provider's classes in order
(for example astra, sol, terra, luna).

Two prototype rounds came first. The round-2 Opus version won for both the page and
the TUI (2026-11-01). Prototypes and briefs are on the branch
`worktree/delegate-e2e-polish`, under `.scratch/delegate-tui-polish/prototypes/`.

## Decisions

- **One matrix.** The TUI's four tier pages become one tiers page: a row per model
  under its harness, a column per effort (`n L M H XH MX U`), each cell a lane's
  tier `T1`-`T4` or `off`. `○` marks an effort the board measures with no lane.
  Space steps the cursor lane through 1, 2, 3, 4 and off; 0-4 set it outright.
  The benchmark page draws the same matrix beside its plot (`tier_matrix.py`).
- **Class order from data.** Inside a harness, models are listed dearest first by
  the geometric mean of their cost per task on the composite board. A model with
  no price goes last. No list of model names.
- **Harnesses in use.** A harness with a carried lane in the machine-local
  `lanes.json` is shown, and the rest start hidden (`h` in the TUI, the chips on
  the page). Nothing about this goes in the repo.
- **Boards.** `[`/`]` in the TUI and `‹`/`›` or the list on the page step through
  the boards in one order: by `boards.json` category (Composite, Knowledge Work,
  Coding, Science, General). A label names the source when two boards share a name
  (two sources publish a Terminal-Bench 4.0).
- **Live link, not copy and paste.** `o` serves the page from 127.0.0.1 behind a
  random key (`page_link.py`). The page polls the wizard's tiers and board and
  posts each change it makes, so both stay the same. Opened as a file, the page is
  a copy whose tier lines still paste with the review page's `v`.
- **One screen.** The page has no scrolling and no evidence tables. The score axis
  fits each board (the round-2 prototype padded fractional boards by a whole point,
  which flattened AutomationBench and MMMU-Pro). A drag on the plot zooms into a
  box, and "Reset zoom" goes back. There are no keyboard shortcuts for zoom.
- **Kept from the Opus prototype:** the colour scheme, the slow hover, and the
  resizable side panel (its width is kept in `localStorage`).

## Out of scope

- The end-to-end findings that are not the TUI or the page are tickets 05 and 06.
- Benchmark views (delegate#32) still name legacy boards; that is the bench-refresh
  follow-up, not this effort.
