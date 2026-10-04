# Review of PR #3: release fragility and module depth

Two read-only checks run on 2026-10-03 at `1cac49b`, answering the user's review of PR #3:

- "are we hardcoding in too much? ... is it going to break when new models are released?"
  (on `harnesses/agy.py`);
- "make sure we have the right structure here that's modular and is following the right level
  of deep modules".

Paths are under `agents/skills/delegate/scripts/` unless noted. Line numbers are at `1cac49b`.

## 1. Does a model release break delegate?

**Verdict: not for a normal release; several edge cases failed silently.** A new version of a
level the catalog already runs needed no code on any harness. The refresh was driven on scratch
copies of `tests/fixtures/refresh-2026-09-22/` (`gpt-6.1-astra`, `gemini-3.9-flash`, Claude
Fable 5.2, `grok-5`): 14 successor lanes, each in its predecessor's place, validating clean.
History agrees: Opus 5.5 (`21d6291`) and Sonnet 5.5 (`6f01e53`) landed with 0 script lines; the
Fable 5.1 display name was one `published_as` entry (`d413a59`); Astra was tier and order only
(`dc8ad10`). The general work that made this so was ticket 33's refresh (`1923f3e`) and the
registry (`ccb2986`). The one time effort hardcoding bit was ticket 17 (`17df013`):
`MODEL_EFFORT_SUFFIXES` lacked `-max` and `-ultra`.

The edges, each reproduced, and each fixed with a regression test in the commit that adds this file:

| Case | Behaviour at `1cac49b` |
|---|---|
| agy lists `-xhigh` or `-max` | `agy.py:14` matches only `low|medium|high`, so the slug became a fake effortless family |
| codex lists effort `extreme` | The refresh proposed `sol61-extreme@codex`, then `validate_lanes` failed at the wizard confirm (`setup.py:726`), losing the session |
| A new level listed after its harness's only successor | No lanes: the only donors were leaving (`discover.py:679-683`); listing order decided the outcome |
| Claude Haiku 5 (no efforts) | `haiku-high@claude` removed, nothing added |
| Dated slug `gpt-6-sol-2026-11-01` | Parsed as version (6, 2026, 11, 1) and superseded a later `gpt-6.1-sol` |
| `/usage` shows `Current week (Fable 5.2)` | Meter `claude-fable 5.2` matched no catalog Meter; the Gate failed open |
| `/usage` shows `104% used` | Negative Remaining; `usage.observations()` returned None and the Gate turned off for every Meter |
| `Claude Nova 6`, `Claude 6 Fable`, `o5-pro` | Ignored with no notice (by design for a new level, but silent) |

The effort words were copied in about nine places (`base.py:10`, `catalog.py:123`,
`bench.py:51,57`, `effort.py:72,1158`, `delegate.py:221,242`, `agy.py:14,68`), and a new word was
either refused late or dropped without a trace. Already robust: codex efforts and `upgrade` read
from the CLI, supersession by level and version, successors taking tier, order and Meter, the
`claude --help` effort read, kiro's tolerant parser, probes failing to unknown, `published_as`.

## 2. Module depth

**Verdict: the PR moves the right way; its own centrepiece is the weak point.**

Well shaped: `rank.py` (three functions hide veto precedence, overflow and the margin steal),
`usage.combined`/`acquire`, `orchestrators.py` (data, enforced by a test), `tier_proposal.py`,
`effort.py`, `bench_page.py`, `catalog.plan_edits`, the registry as the one list of harnesses, and
`bin/delegate` (11 verbs, one routing table).

Findings:

1. **`base.Harness` is a bag of flags.** 15 data attributes and 9 hooks; callers outside the
   package read the attributes about 21 times, 16 in `discover.py` (`catalog_models` alone 8:
   `discover.py:293,313,346,461,629,931,977`, `setup_tui.py:1421`). The Claude "models from the
   catalog plus benchmark names" strategy lives in `discover.py:346-374,490-537,948-989`, so a
   second harness without a list command means editing `discover.py`. The absent-CLI guard is
   copied in five probes, through a three-hop cycle `usage.which` → `catalog.cli_installed` →
   `harnesses.cli_installed`. grok's event parsing sits in `delegate.py:468-502`.
2. **The run directory has no owner.** `dispatch.json` is read-modify-written in four places in
   `delegate.py` (`:410,633-652,706-713,743-756`), `return.json` is built twice (`:621,735`), and
   the finish line is parsed three ways (`evals.py:258`, `browser_probes.py:102`,
   `courier.md:18`). It is the contract every orchestrator reads.
3. **Lane names have no owner.** `<model-effort>@<harness>` is built or split at nine sites, and
   `discover.lane_stem` and `discover.derive_short_name` name the same model differently.
4. **Meter names are an implicit join key** between adapter suffixes, `usage.lane`
   (`usage.py:214`) and hand-written `lanes.json`; a typo leaves a Meter unknown, which never
   vetoes.
5. **Classes as data stop halfway.** The leash is chosen by class name (`delegate.py:288`), and
   edit previews iterate the five shipped classes (`catalog.py:1842`).
6. **Three "same model" rules** (`adapter.family`, `bench.model_group` by spelling at
   `bench.py:740`, `harnesses.slug_family`) disagree.
7. **Big files mix concerns.** `catalog.py` (2624 lines) holds seven, including a 900-line edit
   engine with a lazy import cycle to `rank`; `bench.py` exposes 43 names; `delegate.py` passes
   the same eight values through numbered step functions taking 7 to 15 parameters (a missing
   Run).

Ranked recommendations:

1. Turn the harness flags into adapter verbs (`installed()`, a `meters()` template, `owns()`,
   `effort_for()`, `blocked_reason()`, a `models()` strategy the Claude adapter implements).
   Size M. Ticket 23.
2. Give the run directory one owner, `runs.py`, with `delegate run|dispatch --json`. Size M.
   Ticket 24.
3. Finish the data abstractions where they leak: one lane-name pair, a per-class leash, previews
   over every class, tier_proposal's ordered names, doc drift. Size S. Done in PR #3.
4. Make Meter identity explicit and checked by `catalog check`. Size S-M. Ticket 25.
5. Split `catalog.py` along its seams (edit engine first). Size L, mechanical. Ticket 26.
6. One carry-policy module over `bench.py`, one "same model" rule. Size M-L. Ticket 27.
