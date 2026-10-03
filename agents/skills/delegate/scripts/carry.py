#!/usr/bin/env python3
"""carry.py — the carry policy: which Lanes the pre-screen keeps on.

One rule, read by the wizard (`setup_tui`), the benchmark page (`bench_page`)
and the Tier proposal (`tier_proposal`), so the page never draws a verdict the
wizard did not reach (ticket 27):

- `families(lanes_doc)`: what "the same model" means, asked of each Lane's
  harness (`harnesses.family`). agy names each effort as its own slug, so its
  efforts are one family; every other harness's model is its own.
- `beats(other, row)`: at least the score for no more money, and strictly
  better in one of the two. An unknown cost never beats and is never beaten.
- `decisions(lanes_doc, effort_rows)`: one structured decision per Lane,
  `{lane, enabled, kind, source, competitor}`. The wording is the renderers'
  (`bench.carry_reason`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnesses  # noqa: E402
import published_names  # noqa: E402

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


def model_of(lane):
    """The family key a Lane's model groups under, asked of its harness: an agy
    slug family (`gemini-3.8-flash-high`, `-low`) is one model at several
    efforts; on any other harness the model is its own."""
    lane = lane or {}
    return harnesses.family(lane.get("harness"), lane.get("model") or "")[0]


def families(lanes_doc):
    """{lane model: the family key "the same model" means for the carry rule}.

    On most harnesses a model is its own family, so the key is the model string.
    A harness that carries the effort in the slug (agy) names each effort as its
    own model (`gemini-3.8-flash-low`, `-medium`, `-high`); there the key is the
    slug with its trailing effort removed, the adapter's `family`, the same
    grouping discovery reports the harness's models under (ticket 30 of the
    redesign). The harness decides, never the spelling, so a slug on another
    harness that happens to end in an effort word is still one model of its own.
    """
    out = {}
    for lane in (lanes_doc.get("lanes") or {}).values():
        if not isinstance(lane, dict):
            continue
        model = lane.get("model")
        if not isinstance(model, str) or not model.strip():
            continue
        base = model_of(lane)
        if base != model or model not in out:
            out[model] = base
    return out


def family_of(model, families=None):
    """The family key a model compares under, or the model itself when the
    caller passed no map: without one every model is its own family, which is
    what every harness but agy does anyway."""
    return (families or {}).get(model, model)


def beats(other, row, cost="cost_usd"):
    """At least the score for no more money, and strictly better in one of the
    two. An unknown cost never beats and is never beaten. `cost` names the cost
    key: `cost_usd` on a benchmark row, `cost` on a Tier proposal's score."""
    if other.get(cost) is None or row.get(cost) is None:
        return False
    return (other["score"] >= row["score"] and other[cost] <= row[cost]
            and (other["score"] > row["score"] or other[cost] < row[cost]))


def evidence_unavailable(effort_rows, decided=None):
    """True when there was no per-effort evidence, as distinct from an empty proposal."""
    if effort_rows is None:
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


def dominating_effort(model, effort, source, certain, families=None):
    """The effort of `model` that dominates `effort` inside one source, or None.

    Dominated means another effort of the same model beats it on more than half
    of the benchmarks that source scored both on. A source with one benchmark —
    Terminal-Bench, SWE Refactor Bench — comes down to that one comparison.
    Artificial Analysis scores eight components off the same runs, and losing
    one noisy component in eight is not reason enough to switch a lane off: on
    the live page of 2026-09-11 that reading proposed twelve lanes off, nine of
    them on a single component.

    "The same model" is the family key `families` gives, so an agy slug family
    compares against itself; without a map every model is its own family.
    """
    family = family_of(model, families)
    mine, theirs = {}, {}
    for row in certain:
        if family_of(row.get("model"), families) != family or row.get("source") != source:
            continue
        if row.get("effort") == effort:
            mine.setdefault(row.get("benchmark"), row)
        else:
            theirs.setdefault(row["effort"], {}).setdefault(row.get("benchmark"), row)
    for other_effort, board in theirs.items():
        shared = [benchmark for benchmark in mine if benchmark in board]
        wins = sum(1 for benchmark in shared if beats(board[benchmark], mine[benchmark]))
        if shared and 2 * wins > len(shared):
            return other_effort
    return None


def dominating_row(row, certain, families=None):
    """The dominating effort's point on this row's own board, or None.

    The judgement belongs to the effort over its whole source
    (`dominating_effort`), so every point of a dominated effort is marked on
    every board of that source, including a board where it happens to score
    higher: the lane is off over the source, not over one chart.

    Public because the benchmark page draws this rule: a point it shows hollow
    has to be a point the pre-screen switched a lane off over, and two
    implementations of one rule would eventually disagree in front of a human
    trying to check the wizard's arithmetic. The page passes the same `families`
    the pre-screen uses, so an agy competitor is found under its own slug.
    """
    other = dominating_effort(row.get("model"), row.get("effort"), row.get("source"),
                              certain, families)
    if other is None:
        return None
    family = family_of(row.get("model"), families)
    board = (row.get("source"), row.get("benchmark"))
    return next((r for r in certain
                 if family_of(r.get("model"), families) == family and r.get("effort") == other
                 and (r.get("source"), r.get("benchmark")) == board), None)


def first_domination(lane, certain, families=None):
    """(effort, source) of the first source in which another effort dominates
    this lane, else None."""
    family = family_of(lane["model"], families)
    sources = []
    for row in certain:
        if (family_of(row.get("model"), families) == family
                and row.get("effort") == lane["effort"]):
            if row.get("source") not in sources:
                sources.append(row.get("source"))
    for source in sources:
        other = dominating_effort(lane["model"], lane["effort"], source, certain, families)
        if other is not None:
            return other, source
    return None


def decisions(lanes_doc, effort_rows):
    """The carry pre-screen (ticket 15 of the redesign): {lane name: decision}.

    Each decision is `{lane, enabled, kind, source, competitor}`; the wizard,
    the benchmark page and the report word it themselves (`bench.carry_reason`)
    and never parse wording back."""
    rows, _unmatched = published_names.resolve_effort_rows(lanes_doc, effort_rows)
    certain = certain_effort_rows(rows)
    fams = families(lanes_doc)
    supplied = effort_rows is not None
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
        found = first_domination(lane, certain, fams)
        if found is not None:
            other, source = found
            out[name] = decision(name, False, KIND_DOMINATED, source=source, competitor=other)
            continue
        if not supplied:
            out[name] = decision(name, True, KIND_UNAVAILABLE)
        elif not any(
            not row.get("uncertain")
            and family_of(row.get("model"), fams) == family_of(lane["model"], fams)
            and row.get("effort") == lane["effort"]
            for row in rows
        ):
            out[name] = decision(name, True, KIND_NO_ROWS)
        else:
            out[name] = decision(name, True, KIND_NOT_DOMINATED)
    return out
