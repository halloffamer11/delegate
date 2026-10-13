# Brief v2: rank lanes within each classification

Round 2 of the benchmark page prototypes. Read `brief.md` first for the data, the concepts and
the constraints; they all still hold. This file says what changed after the user saw round 1.

## What the user said about round 1

- Opus 5.5's visuals were better: the chips (hue for the model family, fill for the harness, a
  small shape for the model) and the compact format.
- Astra's layout made more sense: its Frontier matrix, where each row is a model on a harness and
  each column a classification, with the effort bars drawn in every cell.
- What the page must do: **compare scores across models and efforts, split by benchmark, so the
  user can decide how to rank models within each classification.** The overview pages are
  interesting, but the decision is the ranking within each classification.
- A classification can hold several benchmarks. Coding, for example, has more than one coding
  benchmark. Show them together in a focused way.

## Classifications

Group the boards in `sample-data.json` (`boards[].source` and `boards[].benchmark`) like this.
Match each benchmark by name prefix, because versions change.

| Classification | Boards |
|---|---|
| Coding | Terminal-Bench (aa), Terminal-Bench (tbench), SWE Refactor Bench (swerb) |
| Knowledge work | GDPval (aa), Omniscience (aa), AA-LCR (aa), GPQA Diamond (aa) |
| Automation | AutomationBench (aa), IFBench (aa) |
| Overall (reference only) | Artificial Analysis Intelligence Index (aa), a composite |

Put this grouping in one small data object at the top of your script, so it can be edited.

## What to build

1. **Layout from Astra, format from Opus.** Keep Astra's Frontier matrix: rows are models on
   harnesses and columns are classifications. Draw it with Opus's chips and density. Make the
   effort stacks big enough to count at a glance. Astra's size was about right; Opus's was too
   small.
2. **One page per classification. This is the main page.** It ranks every carried lane (model,
   harness and effort) within the classification, one column per benchmark. Each column shows
   the lane's score at its own effort. Also show the efforts the board measured that the lane
   does not run, so the user can see whether a cheaper or dearer effort of the same model would
   rank higher. Then:
   - Give a classification score that combines the benchmarks. Choose a simple, explainable rule,
     such as the mean percentile rank across the benchmarks that measured the lane, and say on
     the page what it is. Show how many of the classification's benchmarks measured each lane.
     A lane measured by one benchmark must not look as certain as one measured by four.
   - Cut the ranking into tiers 4 to 1, show the tier the lane holds now (`lanes[].tier`), and
     mark where the two differ.
   - Name the best lane, and the best per dollar, in each tier.
   - Let the user sort by the classification score, by any one benchmark, or by cost.
3. **The effort question.** For each model on a harness, show the effort the classification
   favours: the cheapest effort within a small margin of the model's best. Show it with the green
   slices of the effort stack.
4. Keep the tabs flat: Frontier, one tab per classification, nothing nested.

## Deliverable

Write `.scratch/delegate-benchmark-views/prototypes/<your-model>-v2.html`. Keep the `<section>` of
at most eight bullets at the top, saying what you tried and why.
