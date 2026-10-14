# Benchmark views on the delegate page

## Problem

More models are competitive across the harnesses the user runs, and they are getting better at
different kinds of work. A model can deserve Tier 4 for coding and Tier 3 for knowledge work, or
the reverse. The benchmark page the wizard opens with `o` already plots score against cost with a
board drop-down, and its sensitivity table already shows the tier each board alone would give.
But it is one long scroll, every board is reached through the same drop-down, and nothing shows
which models were measured on which board, or at which efforts.

The user's ask (2026-10-13): make the HTML page the place to pick a Lane. Give each benchmark that
matters its own view, put a front section that shows the frontier models and how complete their
measurements are, and keep the views flat rather than nested. Prototype rounds on 2026-10-13 and
14 moved the design to zoomable score-and-cost plots per kind of job, with the frontier tab folded
into each View (`prototypes/claude-v6.src.html` is the reference the build follows).

## Three characteristics of a choice

A choice is model, harness and effort.

- **Model and harness are one factor.** A benchmark scores a model, and a harness decides which of
  the model's efforts can run. Kiro is the exception that makes the harness separable: it runs
  models other harnesses also run, on its own meter. So the page shows one row per Model on a
  Harness, with the same measurements and that harness's own Lanes.
- **Effort is the second factor.** Boards often publish only `max`. A Model's line on a plot
  joins every effort the board measured, and the range table under the plots puts one dot per
  measured effort, filled where a carried Lane runs it, so "measured only at max" is visible
  before anyone trusts a figure for a medium Lane.

## The views

Four Views (ticket 05; ticket 01's six one-board Views and the Frontier tab are superseded). Each
View is one kind of job and the boards that speak to it, chosen for the decision it helps with.
They are data in `agents/skills/delegate/assets/views.json`, not code.

| View | Boards | Why |
|---|---|---|
| Coding | Terminal-Bench (AA's per-effort run and the tbench board), SWE Refactor Bench | An agent writing and operating code, end to end and across a whole repository. |
| Knowledge work | GDPval, Omniscience, AA-LCR, GPQA Diamond | Expert deliverables, knowing or saying it does not, long documents, hard science. |
| Automation | AutomationBench, IFBench | Multi-step workflows over APIs, and following precise instructions. Not GUI evidence. |
| Overall (reference) | Artificial Analysis Intelligence Index | One composite for a first cut. Drawn, never weighed as a kind of job. |

Left out: MMMU-Pro is narrower than a kind of job; DeepSWE and APEX-Agents have no accepted rows
(`.scratch/delegate-modular/research/2026-09-15-multi-domain-tiers-scope.md` covers why). Every
board is still reachable from All boards.

A View names a board without a version (`Terminal-Bench`) and draws the newest one, so a new
version of a board needs no edit. No model, harness or effort is named in `views.json`: which
Lanes a View lists is the catalog's, found at runtime.

## Layout

One flat row of tabs: each View, then All boards, Prices, Numbers. No tab holds another row of
tabs. The page opens light, with a toggle to dark kept in the browser.

- **Each View.** What the View is for; an effort filter and the Lanes grouped by Harness; then one
  plot per board, log cost against score:
  - one line per Model on a Harness through its measured efforts, coloured by the Harness and
    shaped by the Model; a filled marker is a carried Lane, a hollow one is measured, not carried;
  - the board's frontier as a soft band under the lines;
  - zoom by dragging a box or Ctrl/Cmd-wheel, back with a double-click or Reset; markers shrink
    and effort labels appear as it zooms;
  - click a Model (in the bar, the table or the plot) or an effort to show only it, shift-click to
    add or remove, Clear filters to show everything;
  - Reference models (no Lane) as grey dots, each one pinnable as a grey dashed line with its name.

  Under the plots, the range table: one row per Model on a Harness, one cell per board with a dot
  per measured effort on that board's own axis, then the mean percentile, the relative cost, the
  tier each held Lane has now and here, and the effort the View favours.
- **All boards.** The free plots, the tier panel and the sensitivity table, as before.

## How a View gives a tier

Each board ranks its rows by score; a row's percentile is the share of the other rows it beats,
ties counting half. A Lane's View score is its mean percentile over the View's boards that measured
it at the Lane's effort (n of N); fewer than half, or one of several, is thin and marked `?`. The
Lanes that hold a tier (the page's, else the catalog's when carried) are ranked by that mean, the
cheaper first on a tie, and the ranking is cut in the proportions of the tiers they hold, ties
taking the better tier: the same cut as the sensitivity table (ticket 27 of the redesign). A View's
favoured effort is the lowest whose mean is within five points of the Model's best.

This is the auto-classification by category the user described. It is a display aid: nothing
writes a View's tier, and a Lane still has one Tier in the catalog. Reference models never enter a
ranking or a cut.

## Not in this effort

- Per-domain Tiers in the catalog (option (b) of the 2026-09-15 scope note): ticket 02.
- An agreed rule for the effort a View recommends: ticket 03 (the favoured effort is a first cut).
- The tier panel starting from the catalog's tiers: ticket 04.
