# Brief v3: benchmark plots are the main interface

Round 3 of the benchmark page prototypes. Read `brief.md` for the data, the concepts and the
constraints, and `brief-v2.md` for the classifications and the ranking rules; they all still
hold unless this file says otherwise. This file says what changed after the user saw round 2.

## What the user said about round 2

> The UI for decision making on each plot should be the frontier at the effort level with a
> connected dot plot color coded to each harness. Prototype this interface. I favor the style of
> Claude but it is too busy looking. I like the use of dot and whisker plots for the model cards,
> but the main interface should be the benchmark plots with a more consolidated comparison for
> each classification.

"The style of Claude" is the Opus 5.5 round 2 prototype: its chips, its type and its colours.

## What to build

1. **The benchmark plot is the main interface.** On each classification tab, draw one plot per
   benchmark of the classification, side by side where the width allows. Each plot is score
   against cost. Each model on a harness is one connected line: one dot per effort the board
   measured, joined in effort order from low to max. Colour the line and its dots by harness,
   and pair the colour with a dot shape or a line style, because colour is never the only
   signal. Draw the frontier (the lanes that no other lane beats on both score and cost) so it
   stands out from the dominated dots. Mark the efforts the user's carried lanes run so they
   differ from efforts that are measured only. Label the lines directly where there is room.
   Choose the cost scale (linear or log) that keeps the cheap lanes apart, and say which.
2. **One consolidated comparison per classification.** Above or beside the plots, give one
   compact view that combines the benchmarks of the classification, so the user can decide the
   ranking without reading every plot. Use a dot and whisker mark for it: the dot is the
   classification score of the lane and the whisker is the spread between the benchmarks. Keep
   the count of benchmarks that measured the lane visible. Show the tier the ranking suggests
   against the tier the lane holds now.
3. **Plots and comparison work together.** Pointing at or selecting a lane in one place marks
   the same lane in every plot and in the comparison. Selecting a model shows a small model
   card with its dot and whisker marks per benchmark and its favoured effort.
4. **Less busy.** Keep the Opus 5.5 style, and cut what the user must read at once. One idea per
   section. Put legends, rules and secondary tables in collapsed sections. Prefer one clear
   mark to three small ones. A first screen at 1440px must show the tabs, the consolidated
   comparison and at least the top of the plots.
5. Keep the tabs flat: Frontier, then one tab per classification. The Frontier tab may be a small
   overview that links to the classification tabs; the classification tabs carry the decision.

Draw the plots with inline SVG or canvas written by hand. Use no chart library and no network
request.

## Deliverable

Write `.scratch/delegate-benchmark-views/prototypes/<your-model>-v3.html`. Keep the `<section>` of
at most eight bullets at the top, saying what you tried and why.
