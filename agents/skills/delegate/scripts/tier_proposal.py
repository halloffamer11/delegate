#!/usr/bin/env python3
"""tier_proposal.py — the Tier the wizard proposes for each carried Lane
(any-harness ticket 17).

Orin sets each Lane's Tier; this only proposes one, and the wizard writes
nothing until he confirms. The rule is data, `routing.json`'s `tier_proposal`
(the sample catalog's when a catalog has none, `catalog.tier_proposal_settings`):

  source, benchmark  the score bands slice: one accepted-rows source and the
                     benchmark it names (a name also matches a versioned one,
                     `Terminal-Bench` matching `Terminal-Bench 4.0`)
  thresholds         {"2": s, "3": s, "4": s}: a Lane clears Tier n when its
                     score is at least thresholds[n]; Tier 1 needs nothing
  diversity          true keeps, in each Tier, the best Lane of every harness
                     with a Lane clearing that Tier

A Lane's score is the row measured at its own model and effort
(`bench.effort_attributes`); a Lane with none gets no proposal. Cost per task
is the second axis, never a filter on its own. From Tier 4 down, the Lanes
clearing a Tier that no higher Tier took are its candidates; the Tier keeps the
candidates no other candidate beats on both score and cost (the cost frontier),
and, with diversity, each harness's best candidate when none of its Lanes is on
the frontier. The rest fall to the next Tier down, and Tier 1 keeps whatever
reaches it. Inside a Tier the proposal orders Lanes by cost, cheapest first,
then by score.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bench  # noqa: E402
import carry  # noqa: E402
import published_names  # noqa: E402

FRONTIER = "frontier"
DIVERSITY = "diversity"
FLOOR = "floor"


def benchmark_matches(name, wanted):
    return name == wanted or (isinstance(name, str) and name.startswith(wanted + " "))


def lane_scores(lanes_doc, effort_rows, settings, names=None):
    """{lane: {"score", "cost", "benchmark"}} for each Lane with a row on the
    chosen benchmark measured at its own effort."""
    lanes = (lanes_doc or {}).get("lanes") or {}
    names = list(lanes) if names is None else list(names)
    out = {}
    for row in effort_rows or []:
        if (not isinstance(row, dict) or row.get("source") != settings["source"]
                or row.get("uncertain")
                or not benchmark_matches(row.get("benchmark"), settings["benchmark"])):
            continue
        score = bench.as_number(row.get("score"))
        if score is None:
            continue
        model = published_names.resolve_published_model(row.get("model"), lanes_doc, effort=row.get("effort"))
        if model is None:
            continue
        for name in names:
            lane = lanes[name]
            if lane.get("model") != model or name in out:
                continue
            if bench.effort_attributes(row.get("effort"), lane.get("effort")):
                out[name] = {"score": score, "cost": bench.as_number(row.get("cost_usd")),
                             "benchmark": row.get("benchmark")}
    return out


def band(score, thresholds):
    """The highest Tier whose threshold the score clears; 1 when none."""
    cleared = [int(t) for t, floor in thresholds.items() if score >= floor]
    return max(cleared, default=1)


def propose(lanes_doc, effort_rows, settings, names=None):
    """{lane: proposal} for each scored Lane among `names` (default all).

    A proposal holds `tier`, `band` (the highest Tier its score clears),
    `score`, `cost`, `benchmark`, `why` (frontier, diversity or floor),
    `beaten_by` (a Lane that beat it in a higher Tier, or None) and `place`,
    its order inside the Tier from 1.
    """
    lanes = lanes_doc["lanes"]
    scores = lane_scores(lanes_doc, effort_rows, settings, names)
    thresholds = settings["thresholds"]
    out = {}
    beaten_by = {}
    for tier in (4, 3, 2, 1):
        floor = thresholds.get(str(tier))
        candidates = [name for name in scores if name not in out
                      and (tier == 1 or scores[name]["score"] >= floor)]
        keep = {}
        for name in candidates:
            beater = next((other for other in candidates
                           if other != name and carry.beats(scores[other], scores[name], cost="cost")), None)
            if beater is None:
                keep[name] = FRONTIER
            elif tier == 1:
                keep[name] = FLOOR
            else:
                beaten_by.setdefault(name, beater)
        if settings.get("diversity") and tier > 1:
            for harness in sorted({lanes[name]["harness"] for name in candidates}):
                own = [name for name in candidates if lanes[name]["harness"] == harness]
                if not any(name in keep for name in own):
                    best = max(own, key=lambda n: (scores[n]["score"],
                                                   -(scores[n]["cost"] or 0), n))
                    keep[best] = DIVERSITY
        order = sorted(keep, key=lambda n: (scores[n]["cost"] is None, scores[n]["cost"] or 0,
                                            -scores[n]["score"], n))
        for place, name in enumerate(order, 1):
            out[name] = dict(scores[name], tier=tier, band=band(scores[name]["score"], thresholds),
                             why=keep[name], beaten_by=beaten_by.get(name), place=place)
    return out


def ordered(proposals):
    """The proposed Lane names, highest Tier first, each Tier's in its order."""
    return sorted(proposals, key=lambda n: (-proposals[n]["tier"], proposals[n]["place"]))


def proposal_lines(proposals):
    """The proposals as `<lane> <tier>` lines, each Tier's Lanes in order."""
    return "".join(f"{name} {proposals[name]['tier']}\n" for name in ordered(proposals))


def describe(proposal):
    """One short cell: the proposed Tier, the score and the cost per task."""
    cost = "no cost" if proposal["cost"] is None else f"${proposal['cost']:.2f}"
    mark = "*" if proposal["why"] == DIVERSITY else ""
    return f"{proposal['tier']}{mark} {proposal['score']:.1f} {cost}"


def legend(settings, proposals=None):
    """The tier page's legend lines: the benchmark and its bands, then what a
    `*` means when a proposal on the page carries one."""
    t = settings["thresholds"]
    lines = [f"proposed: {settings['benchmark']} ≥ {t['4']:g}/{t['3']:g}/{t['2']:g} "
             "for T4/3/2; p: take"]
    if any(p["why"] == DIVERSITY for p in (proposals or {}).values()):
        lines.append("*: kept so every harness clearing the tier has a lane in it")
    return lines
