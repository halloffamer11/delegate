# How a lane is picked

`delegate run` ranks the lanes for a class and dispatches the first. This file
is the rule, for explaining a pick or a stop, and what to do with constraints
the user states in prose.

## Contents

- [The rule](#the-rule)
- [Overflow](#overflow)
- [Metering off](#metering-off)
- [Native lanes and the orchestrator](#native-lanes-and-the-orchestrator)
- [Constraints from the request](#constraints-from-the-request)

## The rule

Each class has a floor and a ceiling in `routing.json`: its range. A lane is
eligible when it is enabled, its tier is inside the range, its meter's
remaining usage is at or above the `gate`, and its harness CLI is on PATH.

Eligible lanes sort by:

1. tier, lowest first;
2. `order`, the lane's place inside its tier (a lane with no `order` sorts
   after every lane with one);
3. pace, highest first;
4. lane name, to break a tie.

The first is the pick, unless a later lane's pace beats the pick's by
`margin`: that lane steals the job. Because `order` sorts ahead of pace, a
steal can happen inside a tier; a lane lower in the order runs when its meter
is well ahead, which balances the load. In a catalog with no `order`, pace
orders each tier and a steal only crosses tiers.

A meter whose probe is unknown sorts last and never blocks. A meter whose
harness refused a run for its usage limit reads 0% left, so the gate vetoes
it, until its reset, a new reset read by a probe, a finished run on it, or 24
hours, whichever comes first. The hold lives in `limits.json` beside the usage
cache; `delegate status` notes it on the meter. With `meters` on
(the default), meters are probed when a run starts and when it finishes.

`--tier <n>` raises the floor for one job. It never admits a tier outside the
range; only overflow reaches past the ceiling.

When nothing is eligible the command prints `STOP: no lane eligible for
<class>` with the reasons, exits 1, and starts nothing.

## Plan dollars

Pace is a ratio, so by default 1% of one plan's week counts the same as 1% of
another's. With `"quota_unit": "plan_dollars"` in `routing.json` ranking
compares Pace times the meter's plan price per week
(`price_month × 7/30.4375`) instead, so spare quota on a pricier plan counts
for more. The margin then becomes a fraction: a lane steals when its value is
at least the pick's times `1 + margin`. A plan change needs only its meter's
`price_month` changed. `--json` rows carry the weekly price as `weight`, and
the usage popup's handover points follow the same rule.

    delegate catalog set routing.quota_unit '"plan_dollars"' --scope global

## Overflow

Overflow is the one path past a ceiling. It applies when usage is the only
thing stopping the range: at least one carried lane in it is under the gate,
and every other veto there is the gate or an absent CLI. Ranking then admits
the tier above the ceiling and ranks it by the same rule, one tier at a time,
never into tier 4.

A lane whose CLI is absent counts as switched off: the catalog is shared
across machines, and this one cannot run it.

The header shows a second line, and `--json` carries the same record at
`overflow`:

    # overflow: ceiling 2 -> 3, all in-Range Lanes under Gate

The `ceiling=` on the first line stays the class's own. Treat an overflowed pick
as costing more usage than the class asked for.

These keep the stop instead: any other veto in the range, a range with no
carried lane, a range whose carried lanes are all CLI-absent, `meters` off, or
`overflow` false.

## Metering off

With `routing.meters` false there are no automatic probes, gate vetoes or
margin steals; ranking uses tier, order and lane name, and the range and
harness checks still apply. The gate and margin stay stored. Cached usage may
still show, marked as metering off. `delegate status --refresh` probes on
request.

## Native lanes and the orchestrator

Delegate works out which harness is orchestrating: `--orchestrator <name>`,
else `$DELEGATE_ORCHESTRATOR`, else the environment the harness sets (Claude
Code sets `CLAUDECODE`). An unknown name, `none`, or nothing detected relays
every lane. Only an orchestrator whose profile declares native lanes runs a
lane of its own harness in-process: dispatch prints `delegate: native …` and
the profile's `delegate: spawn: …` line instead of starting a relay. Profiles
ship in `assets/orchestrators/`; a machine adds its own in
`~/.config/delegate/orchestrators/`.

## Constraints from the request

**A harness.** Only the user sets one: `/delegate agy <task>`, or a standing
instruction such as "use agy for all delegated work". Pass `--harness agy` to
`delegate run` (or `delegate rank`); ranking then uses that harness's lanes
only, with range, gate, pace and margin unchanged. An unknown or uninstalled
harness is refused with the list of installed ones: show the user that list.

**Anything else** (models to exclude, an effort cap):

1. Run `delegate rank <class> --json`, with `--harness` if the user named one.
2. Drop the rows the constraints exclude, and keep only `eligible: true`.
   An effort cap such as "at most medium" filters on each row's `effort`
   (`low < medium < high < xhigh < max`); never pass `--effort` to get under it.
3. State the pick and the reason in one line.
4. Dispatch the top survivor:

       delegate dispatch --lane <name> --class <class> --brief </abs/brief.md> --cwd </abs/project>

If the constraints remove every lane, stop and name the constraint that did
it; never fall back to a lane the user excluded. `--harnesses` declares which
CLIs are present; it is not a filter.
