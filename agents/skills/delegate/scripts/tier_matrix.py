#!/usr/bin/env python3
"""The tier matrix: one row per model on a harness, one column per effort.

The wizard's tiers page and the benchmark page draw the same matrix, so both
read it from here: which models a harness runs (an agy slug family such as
`gemini-4-argon-high`, `-medium`, `-low` is one model), the order of the models
inside a harness, and what one board says of each cell.

The order comes from the data, never from a list of names: the geometric mean
of a model's cost per task on the composite board, dearest first, so a
provider's model classes run from its flagship down (Astra, Sol, Terra, Luna)
and a new model takes its place with no edit. A model the board does not price
goes last, by name.
"""
import math

from harnesses import EFFORTS

# `none` is a row a source may publish, below the lowest effort a lane takes
COLUMNS = ("none",) + tuple(EFFORTS)
SHORT = {"none": "n", "minimal": "mi", "low": "L", "medium": "M", "high": "H",
         "xhigh": "XH", "max": "MX", "ultra": "U"}


def _plottable(point):
    score, cost = (point or {}).get("score"), (point or {}).get("cost")
    return (isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
            and isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost)
            and cost > 0)


def family_key(lane):
    """`harness|group` for one lane of `bench_page.plot_data`'s lane list."""
    return f"{lane.get('harness')}|{lane.get('group') or lane.get('model')}"


def lane_points(board):
    """{lane name: the board's point for it}."""
    out = {}
    for point in board.get("points") or ():
        for lane in point.get("lanes") or ():
            out.setdefault(lane.get("name"), point)
    return out


def own_others(board, families):
    """{family key: {effort: point}}: efforts a board measures for a catalog
    model where no lane runs that effort."""
    by_key = {f["key"]: f for f in families}
    out = {}
    for point in board.get("points") or ():
        if point.get("kind") != "own_other" or point.get("lanes"):
            continue
        for harness in point.get("harness") or ():
            family = by_key.get(f"{harness}|{_base(point.get('model'))}")
            if family is None or point.get("effort") in family["by_effort"]:
                continue
            out.setdefault(family["key"], {}).setdefault(point.get("effort"), point)
    return out


def _base(model):
    text = str(model or "")
    for effort in sorted(COLUMNS + ("minimal",), key=len, reverse=True):
        if text.endswith("-" + effort):
            return text[: -len(effort) - 1]
    return text


def families(data):
    """[(harness, [family, ...]), ...] from `plot_data`: harnesses by name, and
    inside each its models dearest first. A family is
    {key, harness, group, lanes: [names, least effort first], by_effort, geo}."""
    found = {}
    for lane in data.get("lanes") or ():
        key = family_key(lane)
        family = found.setdefault(key, {"key": key, "harness": lane.get("harness"),
                                        "group": lane.get("group") or lane.get("model") or "?",
                                        "lanes": [], "by_effort": {}, "geo": None})
        family["lanes"].append(lane["name"])
        family["by_effort"].setdefault(lane.get("effort"), lane["name"])
    rank = {effort: i for i, effort in enumerate(COLUMNS)}
    lanes = {lane["name"]: lane for lane in data.get("lanes") or ()}
    for family in found.values():
        family["lanes"].sort(key=lambda n: rank.get(lanes[n].get("effort"), 99))
    boards = data.get("boards") or []
    composite = next((b for b in boards if b.get("composite")), boards[0] if boards else None)
    if composite is not None:
        points = lane_points(composite)
        extra = own_others(composite, list(found.values()))
        for family in found.values():
            costs = [points[n]["cost"] for n in family["lanes"] if _plottable(points.get(n))]
            costs += [p["cost"] for p in (extra.get(family["key"]) or {}).values() if _plottable(p)]
            if costs:
                family["geo"] = math.exp(sum(math.log(c) for c in costs) / len(costs))
    by_harness = {}
    for family in sorted(found.values(), key=lambda f: (f["geo"] is None, -(f["geo"] or 0), f["group"])):
        by_harness.setdefault(family["harness"], []).append(family)
    return sorted(by_harness.items(), key=lambda item: str(item[0]))


def used_harnesses(data):
    """The harnesses this machine uses: those with a lane carried in its
    catalog. The page and the tiers page show these first and keep the rest one
    key or click away. With no carried lane, every harness counts."""
    used = {lane.get("harness") for lane in data.get("lanes") or () if lane.get("carried")}
    return used or {lane.get("harness") for lane in data.get("lanes") or ()}


def board_category(board):
    if board.get("composite"):
        return "Composite"
    return board.get("category") or board.get("sourceName") or "Other"


def board_order(boards):
    """Indices of `boards` in the order both pickers step through them: by
    category (Composite, Knowledge Work, Coding, ...), each category where its
    first board stands, and inside it the boards' own order. The page's
    `CATS` groups the same way, so `]` here and `›` there go to the same board."""
    groups = {}
    for i, board in enumerate(boards):
        groups.setdefault(board_category(board), []).append(i)
    return [i for indices in groups.values() for i in indices]


def board_label(board):
    """The board's name, and its source's where they differ: two sources
    publish a Terminal-Bench 4.0, and only the source tells them apart."""
    name = board.get("benchmark") or board.get("sourceName") or board.get("id") or "?"
    source = board.get("sourceName")
    return f"{name} · {source}" if source and source != name else name
