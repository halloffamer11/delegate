# 31 — agy runs Opus on its own Meter

**What to build:** Antigravity now serves Opus 5.5, and Orin wants it as a Lane: discovery
finds it, and its Remaining is read from agy's own limit, not from Claude Code's (Orin,
2026-10-03: "we should make sure that we're scanning for the Opus lane there, and that's
a separate usage limit and everything").

This reverses part of an earlier ruling. Redesign ticket 33 hides other vendors' models on
agy; Orin, 2026-09-22, on the `agy-claude-gpt` pool: "ignore the Gemini Claude pool". The
reversal covers Opus only. Sonnet and GPT-OSS on agy stay hidden.

**What agy reports (Orin's Mac, 2026-10-03).** `agy models` now lists Opus and Sonnet 5.5
with the effort in the slug, like Gemini, and no `Fetching available models...` line:

```text
claude-opus-5-5-low       Claude Opus 5.5 (Low)
claude-opus-5-5-medium    Claude Opus 5.5 (Medium)
claude-opus-5-5-high      Claude Opus 5.5 (High)
claude-sonnet-5-5-low     Claude Sonnet 5.5 (Low)
claude-sonnet-5-5-medium  Claude Sonnet 5.5 (Medium)
claude-sonnet-5-5-high    Claude Sonnet 5.5 (High)
gpt-oss-120b-medium       GPT-OSS 120B (Medium)
```

`agy --print /usage --output-format json` still reports two groups, each with a `weekly`
and a `5h` bucket. Opus has no limit of its own on agy: it shares one with Sonnet and
GPT-OSS. agy's own text: "Within each group, models share a weekly limit and a 5-hour
limit. Quota is consumed proportionally to the cost of the tokens."

```text
Gemini Models          Models within this group: Gemini Flash, Gemini Pro
Claude and GPT models  Models within this group: Claude Opus, Claude Sonnet, GPT-OSS
```

So the separate limit is the existing `agy-claude-gpt` Meter. It is separate from Claude
Code's Meters and from agy's Gemini pool, and `Agy.read_meters` already reads it
(non-Gemini group → `claude-gpt`) with a 5h and a weekly Window. `catalog check` already
accepts the name. No new Meter and no `model_meter` are needed; an `agy-opus` Meter would
be wrong, because Sonnet or GPT-OSS use drains the same pool.

**What blocks the Lane today:**

1. **Discovery drops it.** `discover.own_vendor` asks `Harness.owns`, true only for the
   `gemini` prefix on agy, so the refresh never proposes an Opus Lane on agy.
2. **The fixture is stale.** `tests/fixtures/discover/agy-models.txt` still has
   `claude-opus-4-6-thinking`. The new slugs group cleanly: `Agy.family` makes
   `claude-opus-5-5` with efforts low, medium, high, and `discover.model_level` reads level
   `claude-opus` at (5, 5).
3. **No sample or starter names the Meter.** `assets/samples/lanes.json` has only
   `agy-gemini`, so a first `delegate global` has no `agy-claude-gpt` Meter record to put
   the Lane on.
4. **The same model on two harnesses.** The agy family key `claude-opus-5-5` is the same
   string as the claude harness's Lane model. `carry.families` keys by model string, so the
   carry rule may treat agy Opus and Claude Code Opus as one model across two Meters.
   Unverified; check it before building.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** None.

**Status:** ready-for-human. Built 2026-10-04; Orin's box is the last one.

- [x] Orin's 2026-10-03 `agy models` output becomes the fixture
      (`tests/fixtures/discover/agy-models.txt`). His paste showed only the
      non-Gemini lines, so the Gemini lines stay as they were; the
      `Fetching available models...` header is gone, and a separate test keeps
      the parser skipping it for an older agy.
- [x] The refresh proposes an agy Lane on Opus and on no other non-Gemini model; Sonnet and
      GPT-OSS stay hidden as ticket 33 rules. `Agy.owns` holds the exception
      (`other_vendor_prefixes = ("claude-opus-",)`).
- [x] The Opus Lane goes on the `agy-claude-gpt` Meter, which the refresh creates when the
      catalog lacks it. The adapter names a model's Meter (`Harness.lane_meter`;
      agy answers by group), the refresh prefers a donor on that Meter, and a
      Meter it adds copies the plan and price of the donor's (`_add_meter`). A
      test feeds `read_meters` the two-group output and gets `agy-gemini` and
      `agy-claude-gpt` with both Windows filled.
- [x] `references/catalog.md` shows an agy Opus Lane on `agy-claude-gpt` and says that
      Meter is shared with Sonnet and GPT-OSS. **Deviation:** `assets/samples/lanes.json`
      is unchanged. A Meter with no Lane shows as an empty row in every new
      user's status line and in `limits`, and an Opus Lane in the sample changes
      every wizard test built on it; the refresh adding the Meter with the first
      Opus Lane is what item 3 of "What blocks the Lane" needed.
- [x] The carry rule compares agy Opus only with agy Opus (item 4). It was a real
      conflation, and worse than suspected: `resolve_published_model` sent every
      published Opus row at low, medium or high to the agy member, so Claude
      Code's Opus Lanes lost their rows at those efforts. Now
      `published_names.resolve_published_models` resolves a row once per harness
      and every harness that runs the model gets it (`resolve_effort_rows`,
      `tier_proposal.lane_scores`), and `carry.families` keys on
      `(harness, family)`. Tests: one row reaches both harnesses; Claude Code's
      Opus at high is dominated by its xhigh while agy's high is not; agy's low
      is still dominated by agy's medium. Both fail on the old code.
- [ ] Orin's box: one `delegate global` run proposes the Lane, `delegate catalog check`
      passes, and `delegate status` shows `agy-claude-gpt` with real figures.

Left as is: the benchmark page's evidence table (`bench.evidence_records`) and
the AA board rows (`bench.py`) still resolve a printed name to one lane model,
so a published Opus point is drawn under agy's Opus where both harnesses run it.
That is display only; the carry and Tier verdicts read the per-harness rows.
