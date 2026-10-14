# Brief: restyle the benchmark page's Frontier and view tabs

You are one of three designers making a prototype of the same page. Each of you works on your
own. Be creative: this is an exploration, not a final build.

## What exists

`python3 .scratch/delegate-benchmark-views/prototypes/render_sample.py OUT` (run it from the repo
root) writes two files:

- `OUT/sample-page.html` is the current page. Open it and look at the **Frontier** tab and one
  view tab such as **Coding agent**.
- `OUT/sample-data.json` is the data that page draws. Its fields:
  - `coverage.views`: the six views (id, title, kind, board).
  - `coverage.rows`: one row per model on a harness. Each row has `name`, `harness`, `ours`,
    `lanes` (each with `name`, `effort`, `carried`, `tier`, `meter`) and `cells[viewId].efforts`,
    which maps an effort to `{score, cost}`.
  - `boards[].points`: every measured row on every board, with `score`, `cost`, `effort` and the
    `lanes` it is evidence for.
  - `lanes`: every lane, with `harness`, `meter`, `group` (its model), `effort`, `tier` and
    `carried`.
  - `meters`: each meter's harness and shade.

## Concepts

- A **lane** is a model, a harness and an effort, such as `opus-high@claude`. Its model and harness
  are one factor: the benchmark scores the model, and the harness decides which of its efforts
  can run. The same model can run on two harnesses: Claude Code and Kiro both run Opus, on
  different meters. Effort is the second factor: `none < low < medium < high < xhigh < max`.
- A **tier** runs from 1 to 4, where 4 is the best. Each view ranks lanes on its own board and gives
  each lane a tier. The **net tier** is the middle of the view tiers.
- The harnesses are claude, codex, agy, grok and kiro.

## What the user asked for

> Better visual representation of each model/harness and effort level. One thought is a stacked
> view of the effort level represented as a stack of horizontal arms, and the level is visually
> represented by the number of green slices. Also using chips or some better colour or shape
> grouping of the model, and perhaps a colour shade by harness. Get creative and produce
> prototypes.

Cover at least these:

1. **Effort as a stack.** Draw a lane's effort as a stack of horizontal bars, one per level from
   low to max, with the level shown by how many slices are filled green. Show which efforts a
   board measured, as distinct from the effort the lane runs. Measured but not run, run but not
   measured, and both must each look different.
2. **Model and harness identity.** Give each model on a harness a chip, or another shape or colour
   grouping. Shade the colour by harness so every Claude-family model reads as one family, and
   Opus on Claude Code and Opus on Kiro read as the same model on two harnesses.
3. **The Frontier tab, redesigned** with those marks: the coverage matrix, then the tier per view
   and the net tier.
4. **One view tab, redesigned**, such as Coding agent: its four tier columns, best first, using the
   same chips and effort stacks.

You may also invent anything else that helps someone pick the best lane in each tier for a kind
of job.

## Constraints

- One self-contained HTML file with inline CSS and JS, no network requests, and the sample data
  pasted inline. It is opened as a `file://` URL.
- It works in light and dark (`prefers-color-scheme`) and at widths from 1440px down to 390px.
- Colour is never the only signal. Pair it with shape, fill or text.
- Never hardcode model names into the logic: read everything from the data. Write no person's
  name and no organisation's name.

## Deliverable

Write `.scratch/delegate-benchmark-views/prototypes/<your-model>.html`. Above the prototype, put
a short `<section>` that names the ideas you tried and why, in at most eight bullet points.
