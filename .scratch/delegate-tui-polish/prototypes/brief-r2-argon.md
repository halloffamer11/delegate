# Brief: lane-picker prototype, round 2

Build ONE self-contained, throwaway HTML prototype of delegate's tier-selection
surface: a benchmark page with a side panel, and a TUI mock in the same file.
This is a prototype, so it has no tests and needs no production polish. It must
look considered, though, because the user judges the design.

## Where things are

- Your write worktree is the directory you were given as `--write`. Write exactly
  one new file there: `.scratch/delegate-tui-polish/prototypes/r2-<you>.html`,
  where `<you>` is the name given at the end of this brief. Edit nothing else.
  Do not commit.
- The starting point is round 1: `agents/skills/delegate/assets/bench_page_prototype.html`
  (variants A and T2). Reuse its data handling: the `families()` grouping,
  `lanePoints()` and the hover wiring. Redesign everything else.
- The data: the page holds `<script type="application/json" id="data">/*DATA*/null</script>`.
  The generator replaces `/*DATA*/null` with the user's catalog data. Keep that
  placeholder exactly as written. Never paste real data into the file you write.
- To render with real data and check it, run this from your worktree:
  `python3 agents/skills/delegate/scripts/bench_page_prototype.py --template .scratch/delegate-tui-polish/prototypes/r2-<you>.html --out ~/.cache/delegate/prototypes-r2/r2-<you>.html --no-open`
  It only reads `~/.config/delegate`; never write there. Then extract the inline
  script and run `node --check` on it.

## The data contract (`D`, the parsed JSON)

- `D.boards[]`: `{id, source, sourceName, benchmark, composite (bool), unit, basis, points[]}`.
  Board `b0` is the composite board (Artificial Analysis Intelligence Index).
- `point`: `{model, name, published, effort, score, cost, kind, lanes[], harness[], meter[], tier}`.
  - `kind` is `"lane"` (the catalog has a lane at this model and effort), `"own_other"`
    (the board scores an effort of a catalog model, but no lane runs it) or
    `"comparator"` (a model outside the catalog).
  - `lanes[]` is `{name, harness, meter, tier}`.
  - `effort` is one of `none low medium high xhigh max`.
  - `cost` is USD per task (may be null) and `score` is the board's score.
- `D.lanes[]`: `{name, harness, meter, model, group, effort, tier (1-4 or null), carried (bool), off, rows}`.
  - `group` is the model family. Use it, not `model`: agy writes the effort into
    the model id (`gemini-4-argon-high`, `-medium`, `-low`), and `group`
    (`gemini-4-argon`) joins those into one model.
  - `carried` false means the lane is off.
  - Efforts can also be `ultra`. No board scores ultra.
- `D.harnesses` (all harnesses) and `D.meters[]` (`{name, harness, shade}`).

## What the user asked for (do all of it)

**Page**
1. A plot with a stable side panel. Plot score (up) against cost per task (log
   scale, left is cheaper). Show one line per model on each harness, through its
   efforts, with every dot labelled by its effort (n L M H XH MX). agy's
   effort-suffixed ids must join into ONE Argon line (and one Opus-on-agy line).
2. Refine the colours, the visual design and the layout; round 1 was rough.
   Use no red/yellow/green coding. Use a light theme by default with a dark
   toggle. A colour-blind reader must be able to tell the tier marks apart.
3. The side panel is on the right. It is narrower than round 1 and the reader
   can change its width with a drag handle. Remember the width in localStorage,
   and wrap every localStorage call in try/catch.
4. The side panel looks like the TUI matrix. Do NOT give each effort its own row
   with an off/1/2/3/4 button group.
   - The rows are the models, nested under a harness header.
   - The columns are the efforts: n L M H XH MX U.
   - Each cell is a compact tier mark: T1-T4 or off, a blank gap where no lane
     runs that effort, and a distinct mark for "measured but no lane"
     (`own_other`).
   - Click a cell, or press 1-4 or 0 while hovering it, to set its tier (0 = off).
     A row never moves when its tier changes.
5. Linked hover:
   - Hover a cell: its dot in the plot grows and the rest fades.
   - Hover a model name: its whole line lights.
   - Hover a dot: its cell lights and scrolls into view in the panel.
6. Efforts that a lane runs but this board has no row for appear on a
   "not measured here" strip under the plot. They must not vanish.
7. Preselect the harnesses that have at least one lane on (`carried`) in the
   catalog. The other harnesses are one click away (chips).
8. Order the models within a harness from the data, not from a list of names:
   by the geometric-mean cost per task of the model's points on the composite
   board, dearest first. A model with no points goes last.
9. Board tabs switch between `D.boards`.
10. Show the current state as the tier lines that the review page would paste
    (`<lane> <1-4|off>`, one per line) in a collapsible box.

**TUI view (second view in the same file)**
11. A mock of the TUI tier screen in the same matrix form: 80 columns,
    monospace, keyboard-driven. Use ↑/↓ for the model, ←/→ for the effort,
    1-4 and 0 to set the tier, and h to show the hidden harnesses. Put a footer
    with the keys and a legend for the marks. It shares tier state with the page.
12. Switch views with a toggle in the page header and with `?view=page` or
    `?view=tui` in the URL. Both must work, because screenshots are taken with
    the URL parameter.

## Constraints

- One file, with inline CSS and JS. Load nothing remote: it opens as `file://`
  and offline. Plain JS, no build step.
- Use no name of any organization, site or machine. Write no personal data into
  the file.
- Keep all state in memory, except the panel width.

## Report

In the result's deliverable, give:
- the path you wrote;
- the result of `node --check`;
- three to five lines on your design choices (layout, colour system, tier mark
  glyphs);
- anything in the brief you could not do.

## You

`<you>` = `argon`. Your file is `.scratch/delegate-tui-polish/prototypes/r2-argon.html`.
