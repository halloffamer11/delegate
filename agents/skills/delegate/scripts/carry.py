#!/usr/bin/env python3
"""carry.py — the carry policy: which Lanes the pre-screen keeps on.

One rule, read by the wizard (`setup_tui`), the benchmark page (`bench_page`)
and the Tier proposal (`tier_proposal`), so the page never draws a verdict the
wizard did not reach (ticket 27):

- `beats(other, row)`: at least the score for no more money, and strictly
  better in one of the two. An unknown cost never beats and is never beaten.
- `decisions(lanes_doc, evidence)`: one structured decision per Lane,
  `{lane, enabled, kind, source, competitor}`. The wording is the renderers'
  (`bench.carry_reason`).

Which rows are a Lane's, and which are its Model's on its own Harness, is
`lane_evidence.LaneEvidence`'s question; the rule here compares efforts only
inside the rows it is handed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnesses  # noqa: E402

KIND_DOMINATED = "dominated"
KIND_RECORDED = "recorded"
KIND_ULTRA = "ultra"
KIND_UNAVAILABLE = "unavailable"
KIND_NO_ROWS = "no_rows"
KIND_NOT_DOMINATED = "not_dominated"


def decision(lane, enabled, kind, source=None, competitor=None):
    """One structured carry verdict. Renderers turn this into wording."""
    return {
        "lane": lane,
        "enabled": enabled,
        "kind": kind,
        "source": source,
        "competitor": competitor,
    }


def beats(other, row, cost="cost_usd"):
    """At least the score for no more money, and strictly better in one of the
    two. An unknown cost never beats and is never beaten. `cost` names the cost
    key: `cost_usd` on a benchmark row, `cost` on a Tier proposal's score."""
    if other.get(cost) is None or row.get(cost) is None:
        return False
    return (other["score"] >= row["score"] and other[cost] <= row[cost]
            and (other["score"] > row["score"] or other[cost] < row[cost]))


def evidence_unavailable(evidence, decided=None):
    """True when there was no per-effort evidence, as distinct from an empty proposal."""
    if not evidence.available:
        return True
    if not decided:
        return False
    return all(d.get("kind") == KIND_UNAVAILABLE for d in decided.values())


def certain_effort_rows(effort_rows):
    """Rows that may dominate. Uncertain rows inform nothing: they must not
    dominate another lane, and they are not evidence against the lane they name.

    A row at an effort no lane can select is dropped for the same reason. The
    benchmark harnesses drive the API enum, which runs `none` to `max`, so every
    published sweep carries a `none` row — and no lane can be configured at
    `none`. Letting one dominate would switch off a real lane on the strength of
    a setting that cannot be chosen, which is exactly what it did to
    luna-low@codex: equal score to `none` at a tenth of a cent more.

    A `composite` row is a reader's figure, not evidence: Artificial Analysis
    does not publish the weighting of its Intelligence Index, so it is shown and
    never counted.
    """
    certain = []
    for row in effort_rows or []:
        if not isinstance(row, dict) or row.get("uncertain") or row.get("composite"):
            continue
        if not row.get("model") or not row.get("effort"):
            continue
        if row["effort"] not in harnesses.EFFORTS:
            continue
        score, cost = row.get("score"), row.get("cost_usd")
        if isinstance(score, bool) or isinstance(cost, bool):
            continue
        if not isinstance(score, (int, float)) or not isinstance(cost, (int, float)):
            continue
        certain.append(row)
    return certain


def dominating_effort(own, rivals, source):
    """The effort that dominates the Lane inside one source, or None.

    `own` is the Lane's own certain rows and `rivals` the certain rows of its
    Model's other efforts on its own Harness (`LaneEvidence.model_rows` less
    `lane_rows`), so "the same model" is already settled when they arrive.

    Dominated means another effort of the same model beats it on more than half
    of the benchmarks that source scored both on. A source with one benchmark —
    Terminal-Bench, SWE Refactor Bench — comes down to that one comparison.
    Artificial Analysis scores eight components off the same runs, and losing
    one noisy component in eight is not reason enough to switch a lane off: on
    the live page of 2026-09-11 that reading proposed twelve lanes off, nine of
    them on a single component.
    """
    mine, theirs = {}, {}
    for row in own:
        if row.get("source") == source:
            mine.setdefault(row.get("benchmark"), row)
    for row in rivals:
        if row.get("source") == source:
            theirs.setdefault(row["effort"], {}).setdefault(row.get("benchmark"), row)
    for other_effort, board in theirs.items():
        shared = [benchmark for benchmark in mine if benchmark in board]
        wins = sum(1 for benchmark in shared if beats(board[benchmark], mine[benchmark]))
        if shared and 2 * wins > len(shared):
            return other_effort
    return None


def first_domination(own, rivals):
    """(effort, source) of the first source in which another effort dominates
    the Lane whose own rows are `own`, else None."""
    sources = []
    for row in own:
        if row.get("source") not in sources:
            sources.append(row.get("source"))
    for source in sources:
        other = dominating_effort(own, rivals, source)
        if other is not None:
            return other, source
    return None


def decisions(lanes_doc, evidence):
    """The carry pre-screen (ticket 15 of the redesign): {lane name: decision}.

    `evidence` is the `lane_evidence.LaneEvidence` for this catalog and the
    accepted rows. Each decision is `{lane, enabled, kind, source,
    competitor}`; the wizard, the benchmark page and the report word it
    themselves (`bench.carry_reason`) and never parse wording back."""
    out = {}
    for name, lane in lanes_doc["lanes"].items():
        if lane.get("effort") == "ultra":
            out[name] = decision(name, False, KIND_ULTRA)
            continue
        if "enabled" in lane:
            # An explicit `enabled` is a decision the human already recorded. The
            # pre-screen proposes for lanes that have no decision yet; it does not
            # undo one. Silently switching a lane back on would put it in front of
            # the ranker again without anyone saying so.
            enabled = bool(lane["enabled"])
            out[name] = decision(name, enabled, KIND_RECORDED)
            continue
        lane_rows = evidence.lane_rows(name)
        mine = {id(row) for row in lane_rows}
        certain = certain_effort_rows(evidence.model_rows(name))
        found = first_domination([row for row in certain if id(row) in mine],
                                 [row for row in certain if id(row) not in mine])
        if found is not None:
            other, source = found
            out[name] = decision(name, False, KIND_DOMINATED, source=source, competitor=other)
            continue
        if not evidence.available:
            out[name] = decision(name, True, KIND_UNAVAILABLE)
        elif not any(not row.get("uncertain") for row in lane_rows):
            out[name] = decision(name, True, KIND_NO_ROWS)
        else:
            out[name] = decision(name, True, KIND_NOT_DOMINATED)
    return out
