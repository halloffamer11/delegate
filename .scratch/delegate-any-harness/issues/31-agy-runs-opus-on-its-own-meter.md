# 31 — agy runs Opus on its own Meter

**What to build:** Antigravity now serves Opus 5.5, and Orin wants it as a Lane: discovery
finds it, and its Remaining is read from its own usage limit, not from Claude Code's and
not from agy's Gemini pool (Orin, 2026-10-03: "we should make sure that we're scanning
for the Opus lane there, and that's a separate usage limit and everything").

This reverses part of an earlier ruling. Redesign ticket 33 hides other vendors' models on
agy; Orin, 2026-09-22, on the `agy-claude-gpt` pool: "ignore the Gemini Claude pool". The
reversal covers Opus only. Sonnet and GPT-OSS on agy stay hidden.

What the code does today, and what stops an agy Opus Lane:

1. **Discovery drops it.** `agy models` already lists Claude models
   (`tests/fixtures/discover/agy-models.txt`: `claude-opus-4-6-thinking`). `discover.own_vendor`
   asks `Harness.owns`, which is true only for the `vendor` prefix (`gemini` on agy), so
   the refresh never proposes the Lane and `map_lanes` never names it as missing.
2. **Its family may split.** `Agy.family` strips only an effort suffix. A `-thinking`
   suffix, as on `claude-opus-4-6-thinking`, makes a family of its own, and the level is
   read from the slug with the effort stripped. How agy names Opus 5.5 (one slug, a
   `-thinking` twin, effort suffixes) is unverified.
3. **The probe folds every non-Gemini group into one Meter.** `Agy.read_meters` maps a
   `/usage` group to `gemini` when its name contains "gemini" and to `claude-gpt`
   otherwise. If agy reports Opus as a group of its own, two rows both named
   `agy-claude-gpt` come back and one hides the other. If Opus sits inside the Claude and
   GPT group, the limit is not separate, and the Lane rides `agy-claude-gpt`.
4. **`catalog check` refuses a new Meter name.** `Agy.meter_names` is the fixed
   `("agy-gemini", "agy-claude-gpt")`, and `reports_meter` checks against it, so an
   `agy-opus` Meter in lanes.json fails the check until the adapter declares it.

The precedent for a per-model limit is Claude's: `claude-<model>` Meters named by
`model_meter_name`, and `"model_meter": true` in lanes.json, which the report reads as
"shares the harness's 5h Window, has its own weekly one". Whether agy's Opus limit has
that shape or two Windows of its own decides whether `model_meter` applies here.

Spec: `.scratch/delegate-any-harness/spec.md`

**Blocked by:** Orin's two outputs below. The ticket is written against the checked-in fixture;
nothing here has seen a live listing with Opus 5.5 in it.

**Status:** needs-info. Orin pastes, from any folder on a Mac with agy signed in:

```sh
agy models
agy --print /usage --output-format json
```

- [ ] Orin's box: the two outputs above, pasted into this ticket.
- [ ] `agy models` with Opus 5.5 in it becomes the fixture (`tests/fixtures/discover/agy-models.txt`).
- [ ] The refresh proposes an agy Lane on Opus and on no other non-Gemini model; Sonnet and
      GPT-OSS stay hidden as ticket 33 rules. The exception lives in the adapter
      (`Agy.owns` or its own rule), not as a special case in `discover.py`.
- [ ] agy's Opus slugs form one family whatever suffixes agy uses, so the carry rule and
      the wizard see one model.
- [ ] `Agy.read_meters` gives each `/usage` group its own Meter by name, so no two rows share
      one; an Opus group becomes `agy-opus`, and an unknown group gets a name of its own
      instead of falling into `claude-gpt`.
- [ ] `Agy.meter_names` / `reports_meter` accept the Opus Meter, so `delegate catalog check`
      passes on a lanes.json that has it and still refuses a misspelling.
- [ ] If the Opus limit shares a Window with another group, its Meter row says so the way
      Claude's model Meters do (`model_meter`, `remaining_weekly_model`); if not, it is an
      ordinary two-Window Meter.
- [ ] `assets/samples/lanes.json` and `references/catalog.md` name the new Meter.
- [ ] Orin's box: one `delegate global` run proposes the Lane, `delegate catalog check`
      passes, and `delegate status` shows the Opus Meter with real figures.
