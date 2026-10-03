---
name: delegate
description: Sends one worker-shaped job (an implementation with a spec, a verification, a review, a scouting pass, or a mechanical transform) to an external or native model on one lane, picked by tier and remaining subscription usage, and reports what the worker returned and the usage left. Runs only when the user explicitly asks for delegation, for example by typing /delegate; never use it on your own initiative.
disable-model-invocation: true
---

# Delegate

The session plans, adjudicates and synthesizes; a worker does one job on one
**lane**, a (harness, model, effort) tuple that drains one subscription
**meter**. Every step is the `delegate` command on PATH (`make install` in the
delegate checkout links it), so any harness with a shell can drive it.

Delegate only when the user asks for it. Never start a worker because a task
looks worker-shaped, and never pick a harness or a lane to spend a quota.

The terms (harness, lane, meter, class, tier, floor, ceiling, range, pace,
gate, margin, native lane, and the rest) are defined in `CONTEXT.md` at the
root of the delegate checkout (`~/projects/delegate/CONTEXT.md` by default).
Read it once per session before the first run.

## Workflow

Copy this checklist and tick it off:

```
- [ ] 1. Pick the class
- [ ] 2. Write the brief
- [ ] 3. Run it
- [ ] 4. Verify the return and log it
```

### 1. Pick the class

This step is judgment. Read `assets/classes.md`, then
`~/.config/delegate/classes.md` and the git root's `.delegate/classes.md`
when they exist. A later file's `##` section replaces the matching one, and a
section for a class the skill guide lacks adds that class. Pick exactly one
class; when two fit, the counter-examples decide.

### 2. Write the brief

A Markdown file with exactly two headings, `# Objective` and
`# Definition of done`. Name every file the worker must read. Put the gate
commands the worker must run in the definition of done. Save it in the
session scratchpad and use its absolute path.

### 3. Run it

Run exactly this, in the background so the session keeps working:

    delegate run <class> --brief </abs/brief.md> --cwd </abs/project>

Add only what the job needs:

- `--write </abs/worktree>`: the only way a worker gets a shell and edits. The
  worktree is the blast radius; never pass a primary checkout.
- `--tier <n>`: raise the floor for a job that needs more judgment, inside the
  range the header prints (`floor=` `ceiling=`). `assets/classes.md` says when.
- `--no-leash`: drop the tool-call leash for a large job.
- `--harness <name>`: only when the user named a harness (`/delegate agy …`,
  or a standing "use agy for delegated work").

What comes back:

- `delegate: <lane> status=… secs=… run=<dir>` and a `delegate-metrics:` line.
  `<dir>/return.json` is the result.
- `delegate: native …` then `delegate: spawn: …`: this harness runs the lane
  itself. Follow the spawn line; the agent's final message is the return
  claim. Log it as in step 4 with `--lane --secs --status` instead of `--run`.
- `STOP: no lane eligible for <class>`: nothing started. Show the user the
  veto reasons and ask which they want: abort, a named lane
  (`delegate dispatch --lane <lane> …`), or a one-job exception they state.
  Wait for the answer.

When the user's request carries other constraints (a model to exclude, an
effort cap), or a harness constraint is refused, follow
[references/routing.md](references/routing.md#constraints-from-the-request).
That file also holds the ranking rule, for explaining a pick.

### 4. Verify the return and log it

`return.json` is a claim. Any `status` other than `done` is not a success;
`blocked` carries its reason in `deliverable`. Read the evidence, diff the
`changed_files`, and run the checks yourself. Then log the verdict:

    delegate log --work "<2-4 words>" --run <run-dir> --verdict clean|findings|partial|failed [--outcome "<phrase>"] --class <class>

## Other requests

- **Usage and history**: `delegate status` prints what each meter has left and
  `delegate runs` the recent dispatches; `delegate cost <run-dir>` prints one
  run's cost. Print these; never build the table by hand.
- **Setup**: `/delegate setup` runs `delegate setup`, the wizard that builds or
  revises this machine's catalog.
- **A focused catalog change** (a tier, an order, a range, the gate): see
  [references/catalog.md](references/catalog.md#focused-changes).
- **What the benchmarks say about a model**: see
  [references/catalog.md](references/catalog.md#model-evidence).
- **A Workflow script** has no shell. The optional `courier` agent runs the
  same `delegate dispatch` and relays `return.json`; nothing else needs it.

## References

- [references/routing.md](references/routing.md): how a lane is picked,
  overflow, metering off, harness and prose constraints.
- [references/catalog.md](references/catalog.md): the catalog files and class
  guides, focused changes, the wizard, model evidence.
- [references/maintenance.md](references/maintenance.md): tests, evals,
  browser probes and the pinned relays.
- [references/architecture.md](references/architecture.md): what each script
  owns, for changing delegate itself.
