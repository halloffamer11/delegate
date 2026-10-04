# 20 — The README shows how a job is routed

**What to build:** a visual in `README.md` that shows how delegate turns a request into a Pick and a run, and which file owns each step. The chain is Class (`assets/classes.md`, project overlay) → Range from Floor and Ceiling (`routing.json`) → effective Tier and Order per Lane (`lanes.json`, project `lanes.json`) → Meters and the Gate → Pace and Margin → Pick → relay or native run → run directory and `return.json`. Raised by the user in review 2026-10-02.

Format, to settle in the first box. Mermaid renders natively in a GitHub README and diffs as text, with no build step. D2 (or a D3 render) gives a richer picture but needs a rendered SVG committed beside its source. The default is a Mermaid flowchart for the routing chain, plus a second diagram for which file owns which concept; an SVG is added only if the Mermaid version cannot show it clearly.

The user asked for this to be built by a Codex Lane, which can render and check images. Send it with a named dispatch to a codex Lane.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** landed 2026-10-04 on `worktree/delegate-any-harness-20` (PR #5), reworked after the user's review. All boxes done.

- [x] The format is chosen and the reason recorded here (Mermaid by default).
- [x] The README shows the routing chain with each step's owning file, in the glossary's terms from `CONTEXT.md`.
- [x] The diagram renders on github.com (checked on the PR page) and in light and dark themes.
- [x] Any rendered image is committed with its source and a one-line command that rebuilds it.

## Landed, 2026-10-03

Built by a named dispatch to `sol61-medium@codex`, then edited by the session so each
diagram step names its owning file. Format: Mermaid, one flowchart plus an ownership
table. It renders natively on github.com, diffs as text, and sets no colors, so GitHub's
light and dark themes both apply. No rendered image, so the last box needs nothing.

The table follows the code where the docs are loose: `rank.py` sorts an unknown Pace
last before Tier, Project order lives in `.delegate/routing.json` (`project_order`),
and a Native lane writes no `return.json`. No local Mermaid renderer was installed. The
render was checked on github.com on the branch's README, in light and dark themes.

## Reworked, 2026-10-04

The user's review on PR #5: the Mermaid chain hid the seams between the human, the models
and the scripts, and the first redraw was a design review, not an executive view.
`astra-xhigh@codex` drew three D2 options (swim lanes, layered, sequence); the user picked
the layered one and asked for symbolic labels. The README now shows that diagram as
two SVGs (light and dark through `<picture>`) from `docs/diagrams/routing.d2`, rebuilt
by `sh docs/diagrams/render.sh`, and a six-row ownership table. Format changed from
Mermaid to D2 because the zones, shapes and legend need D2's layout.
