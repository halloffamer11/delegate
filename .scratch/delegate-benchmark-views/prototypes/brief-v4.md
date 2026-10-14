# Brief v4: make the plots work first

Round 4 of the benchmark page prototypes. Read `brief.md` for the data, the concepts and the
constraints, `brief-v2.md` for the classifications, and `brief-v3.md` for the plot and the
comparison; they all still hold unless this file says otherwise. This file says what changed
after the user saw round 3.

## What the user said about round 3

- The direction is right and the result is not yet acceptable. Interaction on the chart is the
  right way.
- Astra's Coding tab has the better plot interface. Opus 5.5's Coding tab has the better table.
- The page must be minimalist, and the lines must be easy to tell apart. The colour scheme is
  too red, yellow and green; it needs a designed palette.
- The plots come first, and they must work better. They must zoom. When the user zooms in, the
  markers get smaller relative to the data, so the labels and the separation between lines
  become clearer.
- The table's error bars must not be ranking (percentile) error bars. They must be
  quantitative: the range of real score values across the effort levels, and the user can
  interact with it.

## What to build

1. **Plots first.** Start from Astra's round 3 plot: score against cost, one connected line per
   model on a harness, one dot per measured effort. Spend most of the work here. A plot must be
   large enough to read: at 1440px, at most two plots in a row, and a control that opens one
   plot at full width.
2. **Zoom and pan.** Wheel or pinch zooms about the pointer; drag pans; a double click or a
   Reset button returns to the full view; a drag on an axis or a box-zoom is welcome. Axis ticks
   update to round values at every zoom level. Markers and line widths keep a constant size on
   screen, so they take less of the data area as the user zooms in. Labels are placed again
   after each zoom: at the full view, label only what fits without overlap; as the user zooms
   in, label every visible line and then every visible effort dot. No label may cover another
   label or a marker.
3. **A designed colour scheme.** Choose one categorical palette for the harnesses that works in
   light and dark, stays distinct for the common forms of colour blindness, and has no
   traffic-light reading: do not use red, yellow and green as neighbours, and keep green and red
   free of any good or bad meaning. Within a harness, tell models apart by marker shape and line
   style, not by more hues. Dim every line the user is not pointing at or has not selected. Say
   in the ideas section which palette you chose and why.
4. **Minimalist.** One plot area, one table, one small legend. No card borders inside cards, no
   badges that repeat a column, no more than two text sizes in a plot. Everything else is
   collapsed or removed.
5. **The table, quantitative.** Start from Opus 5.5's round 3 table. One row per model on a
   harness. For each benchmark of the classification, draw a range mark on that benchmark's real
   score axis: one dot per measured effort, joined by a line from the lowest score to the
   highest. Mark the efforts the carried lanes run. Show the numbers of the two ends. Do not draw
   percentile or rank spread as an error bar. A separate plain column may give the rank.
6. **Table and plot work together.** Pointing at a row marks that line in every plot. Pointing at
   an effort dot in the table marks the same dot in the plot, and the reverse. Selecting keeps the
   mark. Selecting an effort in the table can filter the plots to that effort.

Draw the plots with inline SVG or canvas written by hand. Use no chart library and no network
request. The zoom must work with a mouse, a trackpad and touch.

## Deliverable

Write `.scratch/delegate-benchmark-views/prototypes/<your-model>-v4.html`. Keep the `<section>` of
at most eight bullets at the top, saying what you tried and why.
