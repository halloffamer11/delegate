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
measurements are, and keep the views flat rather than nested.

## Three characteristics of a choice

A choice is model, harness and effort.

- **Model and harness are one factor.** A benchmark scores a model, and a harness decides which of
  the model's efforts can run. Kiro is the exception that makes the harness separable: it runs
  models other harnesses also run, on its own meter. So the page shows one row per Model on a
  Harness, with the same measurements and that harness's own Lanes.
- **Effort is the second factor.** Boards often publish only `max`. A coverage cell shows every
  effort measured and rings the efforts a carried Lane runs, so "measured only at max" is visible
  before anyone trusts a figure for a medium Lane.

## The views

Six Views, plus the Frontier tab in front. Each View is one kind of job and one board, chosen for
the decision it helps with. They are data in `agents/skills/delegate/assets/views.json`, not code.

| View | Board | Why |
|---|---|---|
| Overall | Artificial Analysis Intelligence Index | The top-level cut the user already uses. Composite: shown, never counted in the net. |
| Coding agent | Terminal-Bench (AA's per-effort run, then the tbench board) | The closest board to a delegated coding job, measured at every effort. |
| Whole-repo coding | SWE Refactor Bench | Long-horizon, many-file work checked by tests. Few models, but the ones that matter for big jobs. |
| Knowledge work | GDPval | Professional deliverables graded against experts. |
| Factual reliability | Omniscience | Knows or says it does not; penalises confident wrong answers. Research and review jobs. |
| Automation | AutomationBench | Multi-step business workflows over REST APIs. Not GUI evidence. |

Left out: AA-LCR, GPQA Diamond, MMMU-Pro and IFBench are narrower than a kind of job; DeepSWE and
APEX-Agents have no accepted rows (`.scratch/delegate-modular/research/2026-09-15-multi-domain-tiers-scope.md`
covers why). A board is still reachable from All boards and from every View's drop-down.

A View names its board without a version (`Terminal-Bench`), so a new version of a board needs no
edit. No model, harness or effort is named in `views.json`: which Lanes a View lists is the
catalog's, found at runtime.

## Layout

One flat row of tabs: Frontier, the six Views, All boards, Prices, Numbers. No tab holds another
row of tabs.

- **Frontier.** The coverage matrix (rows: each Model on each Harness the catalog runs, then the
  Models it does not run behind a button; columns: the Views; cells: five effort pips, the best
  score at an effort a carried Lane runs, else the board's best in grey). Under it, the tier each
  View alone would give each carried Lane, and the Net tier.
- **Each View.** What the View is for, then its board as four tier columns, each Lane ranked best
  first with its score and cost, "yours N" where the Lane holds another tier, and the cheapest in
  each tier marked. Under that, the same plot panel as All boards, opened on the View's board.
- **All boards.** The free plots and the sensitivity table, as before.

The tier panel beside the plots stays where it was and works on every View, so a dot clicked on a
View's plot takes a tier the same way.

## How a View gives a tier

The same rule as the sensitivity table (ticket 27 of the redesign): rank the Lanes that hold a
tier by their best plotted score on the board, at the effort they run, and cut the ranking in the
proportions of the tiers they hold, ties taking the better tier. A Lane holds the tier drawn on the
page, else the catalog's. The Net tier is the median of the non-composite Views that measured the
Lane, the lower middle on a split, so a split never nets a Lane up.

This is the auto-classification by category and net score the user described. It is a display
aid: nothing writes a View's tier, and a Lane still has one Tier in the catalog.

## Not in this effort

- Per-domain Tiers in the catalog (option (b) of the 2026-09-15 scope note): ticket 02.
- An effort recommendation per View: ticket 03.
- The tier panel starting from the catalog's tiers: ticket 04.
