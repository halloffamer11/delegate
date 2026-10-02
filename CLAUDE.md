# Delegate

Routes worker jobs to external or native models by capability and remaining
subscription usage. Split out of `halloffamer11/dotfiles` on 2026-10-01 with its
history. The repo is public.

## Start here

- Read `Makefile` before you change installation.
- Read `CONTEXT.md` for the domain vocabulary.
- `agents/skills/delegate/CLAUDE.md` owns the skill's detail. Each directory under
  `tools/` owns its own `CLAUDE.md`.

## Layout

- `agents/skills/`: the `delegate` skill, the typed-only `delegate-<harness>` skills,
  and `council`, which calls delegate's scripts.
- `agents/agents/courier.md`: the one shipped agent.
- `bin/delegate`: the `delegate global|project` command.
- `tools/delegate-dashboard/` (Herdr plugin) and `tools/delegate-mon/` (Rust monitor).

## Where state lives

- Redesign: spec `docs/superpowers/specs/2026-09-08-delegate-redesign.md`, tickets
  `.scratch/delegate-redesign/issues/`.
- Dashboard: spec `docs/superpowers/specs/2026-09-13-delegate-dashboard-plugin.md`,
  tickets `.scratch/delegate-dashboard-plugin/issues/`.
- Browser setup and parity: `.scratch/delegate-browser/issues/`.
- Any-harness refactor (Kiro, registry, review fixes): spec
  `docs/superpowers/specs/2026-10-02-delegate-any-harness.md`, tickets
  `.scratch/delegate-any-harness/issues/`.
- Modular (complete): `.scratch/delegate-modular/CLAUDE.md`.
- A ticket's `**Status:**` line names each open box that waits on Orin.
- Settled decisions: `docs/adr/`. Do not reopen one.
- Specs and tickets written before the split name dotfiles paths
  (`stow/delegate/`, `~/dotfiles`). Read them as history.

## Standing rules

- `~/.config/delegate/{lanes,routing}.json` and the `lane-*.md` agents in
  `~/.claude/agents` are machine-local, never in the repo. Edit them with
  `make delegate-wizard`.
- A project's `.delegate/` policy never goes to main.
- Never commit `~/.config/delegate/aa-key`.
- Preserve unrelated working-tree changes.
- Validate the smallest affected surface before committing; `make test` runs all.

## Agent skills

### Issue tracker

Local markdown: tickets in `.scratch/<effort>/issues/`, specs in
`docs/superpowers/specs/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles, written as a waiting ticket's `**Status:**` value. See
`docs/agents/triage-labels.md`.

### Worktrees

One slug names the `.scratch/` effort, the `worktree/<slug>` branch and the Herdr
checkout under `~/.herdr/worktrees/`; never `/tmp`. See `docs/agents/worktrees.md`.

### Domain docs

Single-context: the glossary is the root `CONTEXT.md`, and decisions are in
`docs/adr/`. See `docs/agents/domain.md`.
