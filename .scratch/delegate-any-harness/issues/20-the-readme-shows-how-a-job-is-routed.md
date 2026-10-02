# 20 — The README shows how a job is routed

**What to build:** a visual in `README.md` that shows how delegate turns a request into a Pick and a run, and which file owns each step. The chain is Class (`assets/classes.md`, project overlay) → Range from Floor and Ceiling (`routing.json`) → effective Tier and Order per Lane (`lanes.json`, project `lanes.json`) → Meters and the Gate → Pace and Margin → Pick → relay or native run → run directory and `return.json`. Raised by Orin in review 2026-10-02.

Format, to settle in the first box. Mermaid renders natively in a GitHub README and diffs as text, with no build step. D2 (or a D3 render) gives a richer picture but needs a rendered SVG committed beside its source. The default is a Mermaid flowchart for the routing chain, plus a second diagram for which file owns which concept; an SVG is added only if the Mermaid version cannot show it clearly.

Orin asked for this to be built by a Codex Lane, which can render and check images. Send it with a named dispatch to a codex Lane.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent, raised by Orin 2026-10-02

- [ ] The format is chosen and the reason recorded here (Mermaid by default).
- [ ] The README shows the routing chain with each step's owning file, in the glossary's terms from `CONTEXT.md`.
- [ ] The diagram renders on github.com (checked on the PR page) and in light and dark themes.
- [ ] Any rendered image is committed with its source and a one-line command that rebuilds it.
