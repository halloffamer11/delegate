# Brief v5: selection, names and reference models

Round 5 of the benchmark page prototypes. Read `brief.md` for the data, the concepts and the
constraints, `brief-v2.md` for the classifications, and `brief-v3.md` and `brief-v4.md` for the
plots, the zoom and the range table; they all still hold unless this file says otherwise.

Start from `claude-v5.src.html`, the prototype the user saw last. Keep its plots, zoom and range
table, and change what this file asks for.

## What the user said

> It looks pretty good. I think I want it to default to light view with a toggle. And when we
> select a lane, it should just be that model, and then it shows all the different models. And
> then I think we should have a shift click to maybe select and unselect different effort levels
> within that classification.
>
> And then also the model labels need to have the model number. So like say Fable 5.1, Astra 6,
> or whatever, Opus 5.5. We need to have those numbers in there. The layout of the harness and
> model needs to be a bit more streamlined. And then similarly, being able to select multiple
> with shift, maybe having a clear button on the filters and the filters should have also the
> ability to show harnesses, models not in my availability but they're kind of not selectable in
> the same way. You can't accidentally add something that's not in there but I want to see for
> reference like Argon 4. Where is Argon 4 relative to what I have access to.

(The quote is from a dictated message; model names are corrected.)

## What to build

1. **Light by default.** The page opens in the light theme whatever the system setting is. A
   toggle switches to dark and back. Dark still works.
2. **Select a model.** A click on a line, a dot, a table row or a filter selects that model on
   that harness: the plots and the table show only it, with all its efforts. Shift-click adds or
   removes a model, so the user can compare several. With nothing selected, everything shows.
3. **Select efforts.** Inside a classification, Shift-click on an effort (in the effort filter, or
   on an effort dot) adds or removes that effort level, so the user can compare, for example,
   only high and xhigh across the selected models. A plain click selects one effort only.
4. **Clear.** Each filter group (models, efforts, harnesses) has a Clear control that returns it
   to all.
5. **Names with versions.** Every model label carries its version: "Fable 5.1", "Astra 6",
   "Opus 5", "Sol 5.6", "Grok 4.6". Take it from the data (`published`, `model`, or the lane's
   `group`), never from a hardcoded list. Keep labels short: the family word may drop where the
   harness or the chip already says it.
6. **Streamlined harness and model layout.** One compact label per line: model name with version,
   then the harness as a small tag or by its colour and a short suffix. No repeated badges.
7. **Reference models.** The filters also list models and harnesses the user does not carry (rows
   with `ours: false` in the boards). Show them in their own group, styled as reference (for
   example hollow, grey, or dashed), and draw them in the plots on request so the user can see
   where an outside model sits against the lanes they have. They cannot be selected as lanes
   and never appear in the ranking, the tiers or "best lane". A toggle shows or hides all of them.

## Deliverable

Write `.scratch/delegate-benchmark-views/prototypes/<your-model>-v5.html`. Keep the `<section>` of
at most eight bullets at the top, saying what you tried and why.
