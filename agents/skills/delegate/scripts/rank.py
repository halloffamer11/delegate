#!/usr/bin/env python3
"""rank.py — deterministic Meter-aware lane ranking for delegate.

Ranks execution lanes from the JSON catalog (lanes.json and routing.json)
over an inclusive Tier range, taking into account subscription meter gate
thresholds, harness CLI availability, and pacing.  The Class-facing ``rank``
wrapper resolves its range from routing classes before calling that rule.

The selection rule:
  1. Filter eligible lanes in the supplied Tier range:
       enabled is True (defaults to True if absent),
       floor <= tier <= ceiling,
       meter gate passed: the Meter snapshot's Readout is not `gated`
         (Remaining unknown, or Remaining >= routing.gate, or routing.meters off),
       harness CLI is present (found in PATH or specified via --harnesses).
     Vetoed lanes fail one or more conditions (reported in precedence order:
     disabled, floor, ceiling, gate, cli).
  2. Sort eligible lanes by:
       tier ascending,
       order ascending (the lane's `order`, its place inside its tier that
         The user sets in the setup wizard; a lane without `order` sorts after
         every lane with one),
       pace descending,
       lane name ascending,
       lanes with unknown pace (None) sorted last.
     Two lanes alike on tier, order and pace are equivalent, so the tie falls
     to lane name: an arbitrary factor, chosen only to make the pick
     deterministic. A catalog with no `order` field ranks as it did before
     ticket 28: every lane sorts as unordered, so tier and pace decide.
  3. Initial pick is eligible[0].
  4. Steal rule: evaluate remaining eligible lanes in sorted order. If a lane's
     pace exceeds the current pick's pace by at least routing.margin, it steals
     the pick:
       for L in eligible[1:]:
           if pace(L) >= pace(pick) + routing.margin: pick = L
     Lanes with unknown pace never steal and are never stolen from. Because
     `order` sorts ahead of pace, a steal can happen inside a tier: a lane
     lower in the user's order runs when its meter is well ahead of the pick's.
     That is the load balance (ticket 28).
  With routing.quota_unit "plan_dollars" (ticket 39) steps 2 and 4 compare
  Pace times the Meter's plan dollars per week (`score`), and a steal needs
  value(L) >= value(pick) * (1 + routing.margin).
  5. Overflow (ticket 29, Class ranking only). If nothing is eligible and only
     subscription usage stands in the way — at least one carried lane in the
     Range is under the gate, and every veto there is gate or cli — admit the
     tier above the ceiling and rank it by the same rule. A cli-absent lane
     counts like a lane switched off: the catalog is shared across machines and
     this one cannot run that lane. Step one tier at a time while the admitted
     tier is also stopped that way; never past tier 3, which keeps tier 4
     named-only; never below the floor. The pick then carries
     `overflow: {from, to, why}` and the header says so. Any other veto in the
     Range, a Range with no carried lane, a Range whose carried lanes are all
     cli-absent with no gate veto among them, `routing.meters` off (no gate
     vetoes exist) or `routing.overflow` false all keep the stop.

Cause vocabulary (``CAUSES``; exactly one per row, in its `cause` field):
  - pick: the Pick, eligible[0], which nothing took the job from (also when
    every Meter is unknown, or Meters are off)
  - steal: the Pick, a Lane after eligible[0] that took the job by the Margin,
    in either quota unit
  - eligible: any other eligible Lane
  - unknown: an eligible Lane with no value to rank by (Meters on, and its
    Pace or plan price unknown); it sorts last. With Meters off nothing ranks
    by value, so a Lane with no reading is `eligible`.
  - disabled, floor, ceiling, gate, cli: the veto that stopped the Lane, in
    that precedence
  A row's `eligible` is true exactly for pick, steal, eligible and unknown,
  and its `pick` exactly for pick and steal. Callers read `cause`; the
  `reason` text below is display only, built from the cause and the numbers,
  and no caller parses it.

Reason text, one per cause:
  - pick: pick
  - steal: stolen by pace: <pace> >= <pick0 pace> + <margin>
           stolen by plan dollars: <value> >= <pick0 value> x (1 + <margin>)
  - eligible: eligible
  - unknown: unknown meter, sorted last
  - disabled: vetoed:disabled, <lane>
  - floor: vetoed:floor, <lane> (tier t) < <class> floor (tier f)
  - ceiling: vetoed:ceiling, <lane> (tier t) > <class> ceiling (tier c)
  - gate: vetoed:gate, <lane>: <meter> meter N% left < gate G%
  - cli: vetoed:cli, <lane>: <harness> not on PATH

Tier preview (``tier_leaders``, and ``rank.py tiers --json``): each exact
Tier's rows and leader, the Steal threshold in routing's quota unit, and each
other Meter's Pace to lead, which rank finds by rerunning its ranking core with
that Meter's Readout at a trial Pace (ticket 21).

CLI forms:
  rank.py <class> [--tier N] [--cwd DIR] [--config-dir DIR] [--meters FILE] [--harnesses a,b,c] [--json]
  rank.py tiers [--cwd DIR] [--config-dir DIR] [--meters FILE] [--harnesses a,b,c] [--json]
"""
import argparse
import dataclasses
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import catalog
import harnesses
from catalog import CatalogError, CLASSES, load_catalog
import usage

# Every row's `cause` (see the module docstring): the two causes a Pick has,
# the two other eligible ones, then the vetoes in precedence order.
CAUSES = ("pick", "steal", "eligible", "unknown",
          "disabled", "floor", "ceiling", "gate", "cli")
_ELIGIBLE_CAUSES = frozenset(CAUSES[:4])
_PICK_CAUSES = frozenset(CAUSES[:2])


def restrict_to_harness(cat, harness):
    """A copy of the catalog holding only this harness's Lanes, so ranking,
    the Gate, overflow and the Margin all run inside the constraint."""
    out = dict(cat)
    out["lanes"] = {name: lane for name, lane in (cat.get("lanes") or {}).items()
                    if lane.get("harness") == harness}
    return out


def score(item):
    """What ranking compares: the Pace, or with `quota_unit` plan_dollars
    (ticket 39) the Pace times the row's `weight`, its plan dollars per week.
    None when either is unknown. A caller that changes `pace` on a row (the
    usage popup's trials) gets the value rescaled with it."""
    pace = item.get("pace")
    if pace is None or "weight" not in item:
        return pace
    weight = item["weight"]
    return None if weight is None else pace * weight


def eligible_order(item, metering):
    """The order eligible Lanes are tried in: Tier, then Order, then (with
    Meters on) the higher value (`score`), a Lane with an unknown one last."""
    t = item["tier"] if item["tier"] is not None else 99
    unordered = 1 if item["order"] is None else 0
    o = item["order"] if item["order"] is not None else 0
    if not metering:
        return (t, unordered, o, item["lane"])
    v = score(item)
    unknown = 1 if v is None else 0
    return (unknown, t, unordered, o, -(v if v is not None else 0.0), item["lane"])


def steals(row, pick_row, margin):
    """True when `row` takes the job from `pick_row` by the Margin: Pace ahead
    by the Margin, or with plan dollars a value ahead by the Margin's fraction
    of the Pick's (a fixed amount of dollars would mean nothing across plans)."""
    v, p = score(row), score(pick_row)
    if v is None or p is None:
        return False
    if "weight" in pick_row:
        return v >= p * (1 + margin)
    return v >= p + margin


def choose(eligible_rows, margin, metering):
    """(the Pick, the value it stole from or None) among rows already in
    `eligible_order`: the first row, unless a later one's value reaches the
    current Pick's by the Margin. The usage popup replays this rule to say
    when a Tier hands over (ticket 40), so it lives in one place."""
    pick_row = eligible_rows[0]
    beaten = None
    if metering:
        for r in eligible_rows[1:]:
            if steals(r, pick_row, margin):
                beaten = score(pick_row)
                pick_row = r
    return pick_row, beaten


def rank_range(cat, meters, present, floor=None, ceiling=None, *, reason_label="tier"):
    """Apply the canonical selection rule to an inclusive Tier range.

    ``floor`` and ``ceiling`` are range bounds, not a Class lookup.  The
    optional ``reason_label`` keeps the existing Class-facing veto text while
    allowing another caller to describe the same range in its own terms.

    cat: dict from catalog.load_catalog
    meters: a usage.Snapshot (usage.read, or usage.Snapshot.of for a document
        in memory); anything else raises TypeError
    present: set of harness names

    Every Meter fact a row carries comes from the Snapshot's Readout for this
    catalog: Remaining, Pace, the Weekly figure, whether the Gate vetoes it
    (`gated`, which honours routing.meters) and the plan price per week. The
    Readouts are read once into a map, Meter to Readout, and the ranking core
    ranks over that map, so a what-if can replace one Readout and rank again
    without a second read.
    """
    if floor is not None and ceiling is not None and floor > ceiling:
        raise ValueError(f"invalid tier range [{floor}, {ceiling}]")
    return _rank_readouts(cat, _readouts(cat, meters), present, floor, ceiling, reason_label)


def _readouts(cat, meters):
    """Meter to Readout for every Lane's Meter, each read once from the
    Snapshot `meters`; anything but a Snapshot raises TypeError."""
    if not isinstance(meters, usage.Snapshot):
        raise TypeError(f"rank takes a usage.Snapshot, not {type(meters).__name__}; "
                        "wrap a usage document with usage.Snapshot.of")
    readouts = {}
    for lane_def in (cat.get("lanes") or {}).values():
        meter = lane_def.get("meter")
        if meter not in readouts:
            readouts[meter] = meters.readout(meter, cat)
    return readouts


def _rank_readouts(cat, readouts, present, floor, ceiling, reason_label):
    """The ranking core: the selection rule over `readouts`, Meter to Readout,
    holding an entry for every Lane's Meter."""
    routing = cat.get("routing", {})
    # merged routing always carries both (`catalog.load_catalog`); no second
    # default lives here
    margin = routing["margin"]
    gate = routing["gate"]
    metering = catalog.meters_enabled(routing)
    dollars = catalog.quota_unit(routing) == "plan_dollars"
    reason_label = reason_label or "tier"

    present_set = set(present) if present else set()
    lanes = cat.get("lanes", {})

    eligible_rows = []
    vetoed_rows = []

    for lane_name, lane_def in lanes.items():
        meter_name = lane_def.get("meter")
        reading = readouts[meter_name]
        r = reading.remaining
        pace = reading.pace
        remaining_weekly = reading.weekly
        if r is None:
            meter_status = "unknown"
        elif reading.gated:
            meter_status = "unavailable"
        else:
            meter_status = "ok"

        lane_tier = lane_def.get("tier")
        harness = lane_def.get("harness")
        model = lane_def.get("model")
        lane_effort = lane_def.get("effort")

        # One veto per lane, in this precedence: disabled, floor, ceiling,
        # gate, cli. The order is load-bearing for overflow: a lane failing
        # both the Gate and the CLI check is recorded `gate`, and
        # `gate_only_stop` accepts either kind, so neither reading changes
        # what it decides (ticket 29).
        veto_kind = None
        veto_reason = None
        if not lane_def.get("enabled", True):
            veto_kind = "disabled"
            veto_reason = f"vetoed:disabled, {lane_name}"
        elif lane_tier is not None and floor is not None and lane_tier < floor:
            veto_kind = "floor"
            veto_reason = f"vetoed:floor, {lane_name} (tier {lane_tier}) < {reason_label} floor (tier {floor})"
        elif lane_tier is not None and ceiling is not None and lane_tier > ceiling:
            veto_kind = "ceiling"
            veto_reason = f"vetoed:ceiling, {lane_name} (tier {lane_tier}) > {reason_label} ceiling (tier {ceiling})"
        elif reading.gated:
            veto_kind = "gate"
            r_pct = f"{int(round(r * 100)):d}%"
            gate_pct = f"{int(round(gate * 100)):d}%"
            veto_reason = f"vetoed:gate, {lane_name}: {meter_name} meter {r_pct} left < gate {gate_pct}"
        elif harness not in present_set:
            veto_kind = "cli"
            veto_reason = f"vetoed:cli, {lane_name}: {harness} not on PATH"

        row = {
            "lane": lane_name,
            "harness": harness,
            "model": model,
            "effort": lane_effort,
            "tier": lane_tier,
            "order": lane_def.get("order"),
            "meter": meter_name,
            "pace": pace,
            "r": r,
            "remaining_weekly": remaining_weekly,
            "meter_status": meter_status,
            "eligible": veto_reason is None,
            # one of CAUSES: the veto, or for an eligible row the cause set
            # below once the Pick is known. It replaced the `veto` field
            # (ticket 22).
            "cause": veto_kind,
            "pick": False,
            # only a Pick admitted past its Ceiling carries a record here
            "overflow": None,
            "reason": veto_reason or "",
        }
        if dollars:
            # plan dollars per week; Pace times this is what ranks (ticket 39)
            row["weight"] = reading.week_dollars

        if veto_reason is None:
            eligible_rows.append(row)
        else:
            vetoed_rows.append(row)

    eligible_rows.sort(key=lambda item: eligible_order(item, metering))

    if eligible_rows:
        pick_row, beaten_pace = choose(eligible_rows, margin, metering)

        for r in eligible_rows:
            if r is pick_row:
                r["cause"] = "pick" if beaten_pace is None else "steal"
            elif metering and score(r) is None:
                r["cause"] = "unknown"
            else:
                r["cause"] = "eligible"
            r["eligible"] = r["cause"] in _ELIGIBLE_CAUSES
            r["pick"] = r["cause"] in _PICK_CAUSES
            # the display text for the cause; nothing parses it
            if r["cause"] == "steal" and dollars:
                r["reason"] = (f"stolen by plan dollars: {score(r):.2f} >= "
                               f"{beaten_pace:.2f} x (1 + {margin})")
            elif r["cause"] == "steal":
                r["reason"] = f"stolen by pace: {r['pace']} >= {beaten_pace} + {margin}"
            elif r["cause"] == "unknown":
                r["reason"] = "unknown meter, sorted last"
            else:
                r["reason"] = r["cause"]

        ordered_eligible = [pick_row] + [r for r in eligible_rows if r is not pick_row]
    else:
        ordered_eligible = []

    return ordered_eligible + vetoed_rows


# Overflow never admits Tier 4: the frontier Tier is reached by naming a Lane,
# never by an automatic rule (ticket 29).
OVERFLOW_TOP_TIER = 3
OVERFLOW_WHY = "all in-Range Lanes under Gate"


def gate_only_stop(rows, floor, ceiling):
    """True when subscription usage is the only thing stopping [floor, ceiling].

    Among the carried Lanes in the Range, at least one has to be under the Gate
    and every veto has to be `gate` or `cli`. A Lane whose Harness CLI is absent
    counts like a Lane switched off: the catalog is shared across machines, and
    a Lane this machine cannot run is not a Lane the Range still has. So it
    neither creates the outage nor blocks the answer to one.

    Everything else stops as it did before ticket 29: a Range with no carried
    Lane, a Range whose carried Lanes are every one of them cli-absent with no
    Gate veto among them, and any other veto kind. With ``routing.meters`` off
    no row can carry a Gate veto, so this is never true.
    """
    in_range = [
        row for row in rows
        if row["cause"] != "disabled"
        and row["tier"] is not None
        and (floor is None or row["tier"] >= floor)
        and (ceiling is None or row["tier"] <= ceiling)
    ]
    if not any(row["cause"] == "gate" for row in in_range):
        return False
    return all(row["cause"] in ("gate", "cli") for row in in_range)


def rank(cls, cat, meters, present, tier=None):
    """Rank catalog lanes for a given class.

    cat: dict from catalog.load_catalog
    meters: a usage.Snapshot (see rank_range)
    present: set of harness names
    tier: optional floor override (must be between class floor and ceiling)

    When the Range stops and every carried Lane in it is under the Gate, the
    next Tier above the Ceiling is admitted and ranked by the normal rule, one
    Tier at a time and never Tier 4 (ticket 29). The Pick then carries an
    ``overflow`` record saying which Ceiling was raised, to which Tier and why;
    no other row carries one. ``routing.overflow`` false keeps the stop.
    """
    routing = cat.get("routing", {})
    classes = routing.get("classes", {})
    if cls not in classes:
        raise ValueError(f"unknown class '{cls}'; must be one of {', '.join(catalog.class_names(routing))}")

    cls_config = classes.get(cls, {})
    floor = cls_config.get("floor")
    ceiling = cls_config.get("ceiling")

    if tier is not None:
        if floor is not None and ceiling is not None and (tier < floor or tier > ceiling):
            raise ValueError(f"tier {tier} outside [{floor}, {ceiling}] for class '{cls}'")
        floor = tier

    rows = rank_range(
        cat,
        meters,
        present,
        floor=floor,
        ceiling=ceiling,
        reason_label=cls,
    )
    # What the Pick is, and what it is not (the user, 2026-09-22; ticket 36). A Lane
    # is one model at one effort, so the effort is fixed by the Lane the catalog
    # holds: this returns a Lane, never an effort, and nothing here chooses one.
    # If an orchestrator is ever trusted to choose an effort, one path already
    # exists and needs no new rule:
    #   delegate.py dispatch --lane sol6-high@codex --effort xhigh --class impl
    # overrides the effort for that one named job. An effort the harness does not
    # offer is refused, and agy ignores the override, because agy carries the
    # effort in the model name. A standing Class-to-effort rule, were one ever
    # wanted, belongs in `assets/classes.md` beside the Class judgment, not here:
    # ranking would still pick the Lane.
    if rows and rows[0]["pick"]:
        return rows
    if ceiling is None or not catalog.overflow_enabled(routing):
        return rows

    # The Range's own rows are what a stop reports, so keep them: a widened
    # range that also fails would otherwise explain the stop against a Ceiling
    # the Class does not have.
    stopped = rows
    admitted = ceiling
    while admitted < OVERFLOW_TOP_TIER and gate_only_stop(rows, floor, admitted):
        admitted += 1
        rows = rank_range(
            cat,
            meters,
            present,
            floor=floor,
            ceiling=admitted,
            reason_label=cls,
        )
        if rows and rows[0]["pick"]:
            rows[0]["overflow"] = {
                "from": ceiling,
                "to": admitted,
                "why": OVERFLOW_WHY,
            }
            return rows
    return stopped


def tier_leaders(cat, meters, present):
    """The four exact-Tier previews, Tier 1 to 4. Each is a dict:
      tier             int
      leader           lane name, or None
      rows             the Tier's rows, Pick first, each with "cause"
      steal_threshold  {"unit": "pace" | "plan_dollars", "value": float | None}
      pace_to_lead     {meter: float | None}

    Each Tier is ranked by the selection rule with equal floor and ceiling,
    and rows from other Tiers are dropped. A leader is the exact-Tier
    preview, not the Pick for any Class range.

    `steal_threshold.unit` is routing's quota unit, and its value is what a
    Lane that sorts after the leader must reach to take the Tier: the
    leader's Pace plus the Margin, or with plan dollars the leader's value
    times (1 + Margin). None with no leader, an unknown leader value, or
    Meters off.

    `pace_to_lead` has a key for every Meter with an eligible Lane of known
    Pace in the Tier, except the leader's Meter: the lowest Pace on the 0.01
    grid at which a Lane on it leads the Tier, every other Meter as it reads
    now, or None when no Pace a Meter can read (up to usage.MAX_PACE) does.
    Empty with Meters off.

    The Snapshot is read once: every what-if replaces one Readout in that
    map and reranks it. The preview does no I/O and is JSON-safe.
    """
    readouts = _readouts(cat, meters)
    routing = cat.get("routing", {})
    previews = []
    for tier in range(1, 5):
        rows = _tier_rows(cat, readouts, present, tier)
        leader = next((row for row in rows if row["pick"]), None)
        previews.append({
            "tier": tier,
            "leader": leader["lane"] if leader else None,
            "rows": rows,
            "steal_threshold": _steal_threshold(routing, leader),
            "pace_to_lead": _paces_to_lead(cat, readouts, present, tier, rows, leader),
        })
    return previews


def _tier_rows(cat, readouts, present, tier):
    """The ranking of one exact Tier over `readouts`, its own rows only."""
    rows = _rank_readouts(cat, readouts, present, tier, tier, f"Tier {tier}")
    return [row for row in rows if row["tier"] == tier]


def _steal_threshold(routing, leader):
    """The value a Lane after `leader` must reach to take its Tier, in
    routing's quota unit."""
    unit = catalog.quota_unit(routing)
    value = score(leader) if leader is not None and catalog.meters_enabled(routing) else None
    if value is not None:
        margin = routing["margin"]
        value = value * (1 + margin) if unit == "plan_dollars" else value + margin
    return {"unit": unit, "value": value}


def _paces_to_lead(cat, readouts, present, tier, rows, leader):
    """Meter to its Pace to lead the Tier (see tier_leaders)."""
    if leader is None or not catalog.meters_enabled(cat.get("routing", {})):
        return {}
    # Every Lane has a Tier (catalog validation), so the Tier's rows are its
    # Lanes, and a replay ranks those alone.
    names = {row["lane"] for row in rows}
    tier_cat = dict(cat, lanes={name: lane for name, lane in (cat.get("lanes") or {}).items()
                                if name in names})
    out = {}
    for row in rows:
        meter = row["meter"]
        if (row["eligible"] and row["pace"] is not None
                and meter != leader["meter"] and meter not in out):
            out[meter] = _pace_to_lead(tier_cat, readouts, present, tier, rows, meter)
    return out


def _pace_to_lead(cat, readouts, present, tier, rows, meter):
    """The lowest Pace on the 0.01 grid, up to usage.MAX_PACE, at which a Lane
    on `meter` leads `tier`, or None.

    Who leads changes only where a Lane on `meter` crosses a rival's value in
    the sort or in a steal: at the rival's value, or that value plus or minus
    the Margin (with plan dollars, times or over 1 + Margin), each over the
    Meter's weight. Between crossings the outcome holds, so the Pick is replayed
    at 0 and at the first and second grid step at or above each crossing, in
    ascending order, and the first that leads is the answer. A step is in
    hundredths, so a Pace on the grid is exact.
    """
    routing = cat["routing"]
    margin = routing["margin"]
    dollars = catalog.quota_unit(routing) == "plan_dollars"
    weight = readouts[meter].week_dollars if dollars else 1.0
    crossings = [0.0]
    if weight:
        for row in rows:
            value = score(row)
            if not row["eligible"] or row["meter"] == meter or value is None:
                continue
            if dollars:
                crossings += [value, value * (1 + margin), value / (1 + margin)]
            else:
                crossings += [value, value + margin, value - margin]
        crossings = [c / weight for c in crossings]
    top = math.floor(round(usage.MAX_PACE * 100, 9))
    steps = set()
    for crossing in crossings:
        step = max(0, math.ceil(round(crossing * 100, 9)))
        steps.update(s for s in (step, step + 1) if s <= top)
    for step in sorted(steps):
        trial = dict(readouts)
        trial[meter] = dataclasses.replace(readouts[meter], pace=step / 100)
        pick = next((r for r in _tier_rows(cat, trial, present, tier) if r["pick"]), None)
        if pick is not None and pick["meter"] == meter:
            return step / 100
    return None


def format_rows(rows):
    if not rows:
        return []
    max_lane_w = max(len(r["lane"]) for r in rows)
    max_model_w = max(len(r["model"]) for r in rows)
    # the order column appears only when some lane has an order, so a catalog
    # without one prints exactly as before ticket 28
    show_order = any(r.get("order") is not None for r in rows)
    lines = []
    for idx, r in enumerate(rows, 1):
        pace_str = "   ?" if r["pace"] is None else f"{r['pace']:.2f}"
        r_str = "  ?" if r["r"] is None else f"{int(round(r['r'] * 100)):3d}%"
        status_str = f"{r['meter_status']:<8}"
        lane_padded = f"{r['lane']:<{max_lane_w}}"
        model_padded = f"{r['model']:<{max_model_w}}"
        line = (
            f"{idx}. {lane_padded} "
            f"tier={r['tier']} "
            + (f"order={'-' if r.get('order') is None else r['order']} " if show_order else "")
            + f"pace={pace_str} "
            f"r={r_str} "
            f"{status_str} "
            f"{model_padded}   "
            f"{r['reason']}"
        )
        lines.append(line)
    return lines


def print_rank_output(cls, cat, rows, tier=None):
    """Print the Class header (or STOP) and ranked rows. Returns whether a Pick exists."""
    has_pick = bool(rows and rows[0].get("pick"))
    if not has_pick:
        print(f"STOP: no lane eligible for {cls}")
        for line in format_rows(rows):
            print(line)
        return False
    routing = cat["routing"]
    cls_config = routing.get("classes", {}).get(cls, {})
    floor = tier if tier is not None else cls_config.get("floor")
    ceiling = cls_config.get("ceiling")
    margin = routing["margin"]
    gate = routing["gate"]
    project_file = cat.get("files", {}).get("project")
    override_str = project_file if project_file else "none"
    gate_pct = f"{int(round(gate * 100))}%"
    meters_bit = "" if catalog.meters_enabled(routing) else "  meters=off"
    print(f"# {cls}  floor={floor} ceiling={ceiling}{meters_bit}  margin={margin}  gate={gate_pct}  (routing: global; project override: {override_str})")
    # A project may set a Lane's Tier (ticket 32). The rows carry only the
    # effective Tier, so the header says which Lanes run on a project one.
    project_tiers = cat.get("project_tiers") or {}
    if project_tiers:
        moved = ", ".join(
            f"{name} {change['from']} -> {change['to']}"
            for name, change in sorted(project_tiers.items())
        )
        print(f"# project tier: {moved}  ({cat.get('files', {}).get('project_lanes')})")
    # The Ceiling above stays the Class's own, which is the value `--tier` is
    # bounded by; this second header line says the job went past it and why.
    overflow = rows[0].get("overflow")
    if overflow:
        print(f"# overflow: ceiling {overflow['from']} -> {overflow['to']}, {overflow['why']}")
    for line in format_rows(rows):
        print(line)
    return True


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="rank.py",
        description="Rank execution lanes for a Class or preview all four exact Tiers."
    )
    parser.add_argument("target", metavar="class|tiers", help=f"class to rank ({', '.join(CLASSES)}, or one the catalog adds) or tiers")
    parser.add_argument("--tier", type=int, default=None, help="override floor tier for this job")
    parser.add_argument("--cwd", default=None, help="working directory to find git root from")
    parser.add_argument("--config-dir", default=None, help="config directory containing lanes.json and routing.json")
    parser.add_argument("--meters", default=None, help="path to usage document JSON file")
    parser.add_argument("--harnesses", default=None, help="comma-separated list of present harnesses")
    parser.add_argument("--harness", default=None,
                        help="the user's harness constraint: rank this harness's Lanes only")
    parser.add_argument("--json", action="store_true", help="output as JSON")

    args = parser.parse_args(argv)
    tiers_mode = args.target == "tiers"

    if tiers_mode and args.tier is not None:
        parser.error("--tier is only valid with a Class")

    try:
        cat = load_catalog(cwd=args.cwd, config_dir=args.config_dir)
    except CatalogError as e:
        sys.stderr.write(f"rank: {e}\n")
        sys.exit(1)

    known_classes = catalog.class_names(cat["routing"])
    if not tiers_mode and args.target not in known_classes:
        sys.stderr.write(f"rank: unknown class '{args.target}'; must be one of {', '.join(known_classes)}\n")
        sys.exit(2)

    if args.harness is not None:
        error = harnesses.constraint_error(args.harness) if args.harnesses is None else (
            None if args.harness in args.harnesses.split(",") else
            f"harness '{args.harness}' is not installed; installed: {args.harnesses}")
        if error:
            sys.stderr.write(f"rank: {error}\n")
            sys.exit(2)
        cat = restrict_to_harness(cat, args.harness)

    # A Class reads the Meters FRESH, which probes only when the reading is
    # older than ten minutes and only with routing.meters on; the tiers
    # preview and an explicit --meters FILE read the document as it is.
    meters = usage.read(cat["routing"], usage.CACHED if (tiers_mode or args.meters) else usage.FRESH,
                        path=args.meters)

    if args.harnesses is not None:
        present = set(h.strip() for h in args.harnesses.split(",") if h.strip())
    else:
        present = harnesses.installed()

    if tiers_mode:
        previews = tier_leaders(cat, meters, present)
        routing = cat["routing"]
        margin = routing["margin"]
        gate = routing["gate"]
        metering = catalog.meters_enabled(routing)

        if args.json:
            out = {
                "margin": margin,
                "gate": gate,
                "meters": metering,
                "tiers": previews,
            }
            sys.stdout.write(json.dumps(out, indent=2) + "\n")
            sys.exit(0)

        gate_pct = f"{int(round(gate * 100))}%"
        meters_bit = "" if metering else "  meters=off"
        for preview in previews:
            leader = preview["leader"] or "none"
            print(
                f"# Tier {preview['tier']} preview; not a Class Pick  "
                f"leader={leader}{meters_bit}  margin={margin}  gate={gate_pct}"
            )
            for line in format_rows(preview["rows"]):
                print(line)
        sys.exit(0)

    try:
        rows = rank(args.target, cat, meters, present, tier=args.tier)
    except ValueError as e:
        sys.stderr.write(f"rank: {e}\n")
        sys.exit(2)
    has_pick = bool(rows and rows[0]["pick"])

    routing = cat["routing"]
    cls_config = routing.get("classes", {}).get(args.target, {})
    floor = args.tier if args.tier is not None else cls_config.get("floor")
    ceiling = cls_config.get("ceiling")
    margin = routing["margin"]
    gate = routing["gate"]
    metering = catalog.meters_enabled(routing)

    if args.json:
        out = {
            "class": args.target,
            "floor": floor,
            "ceiling": ceiling,
            "margin": margin,
            "gate": gate,
            "meters": metering,
            "overflow": rows[0].get("overflow") if has_pick else None,
            "pick": rows[0]["lane"] if has_pick else None,
            "rows": rows,
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
        sys.exit(0 if has_pick else 1)

    print_rank_output(args.target, cat, rows, tier=args.tier)
    sys.exit(0 if has_pick else 1)


if __name__ == "__main__":
    main()
