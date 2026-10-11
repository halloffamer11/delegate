#!/usr/bin/env python3
"""test_lane_evidence.py — which benchmark rows belong to which Lane.

The interface is the test surface: `LaneEvidence(lanes_doc, rows)` and its
queries. Run: python3 tests/test_lane_evidence.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))

from lane_evidence import LaneEvidence  # noqa: E402

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def row(model, effort, benchmark, score, cost, source="aa"):
    """A row as a source prints it: its own name for the model, the effort beside it."""
    return {"model": model, "effort": effort, "benchmark": benchmark, "score": score,
            "cost_usd": cost, "uncertain": False, "source": source}


def same(got, want):
    """The caller's own row objects, in input order: no copy, no re-keying."""
    return len(got) == len(want) and all(g is w for g, w in zip(got, want))


def shown(rows):
    return [(r.get("model"), r.get("effort"), r.get("benchmark")) for r in rows]


def lane(harness, model, effort, tier=3, meter="m", **extra):
    out = {"harness": harness, "model": model, "effort": effort, "tier": tier, "meter": meter}
    out.update(extra)
    return out


CLAUDE_OPUS = {f"opus55-{e}@claude": lane("claude", "claude-opus-5-5", e, meter="claude-general")
               for e in ("low", "medium", "high", "xhigh")}

# Claude Code runs Opus as one model string at low to xhigh; agy names each
# effort in the slug and runs low to high.
OPUS_TWO_HARNESSES = {
    "version": "delegate-lanes.v1",
    "lanes": {
        **CLAUDE_OPUS,
        **{f"opus55-{e}@agy": lane("agy", f"claude-opus-5-5-{e}", e, meter="agy-claude-gpt")
           for e in ("low", "medium", "high")},
    },
}

# The same, with one agy member only: a family of one is still agy's Opus.
OPUS_ONE_AGY = {
    "version": "delegate-lanes.v1",
    "lanes": {**CLAUDE_OPUS,
              "opus55-high@agy": lane("agy", "claude-opus-5-5-high", "high", meter="agy-claude-gpt")},
}

# Opus as Artificial Analysis prints it, on two boards, at four efforts.
OPUS_ROWS = [row("Claude Opus 5.5", e, b, s, c)
             for e, s, c in (("low", 0.40, 1.0), ("medium", 0.60, 0.9),
                             ("high", 0.70, 2.0), ("xhigh", 0.80, 1.5))
             for b in ("b1", "b2")]

AGY_CARRY_LANES = {
    "version": "delegate-lanes.v1",
    "lanes": {
        "flash-low@agy": lane("agy", "gemini-3.8-flash-low", "low", tier=1, meter="agy-gemini"),
        "flash-medium@agy": lane("agy", "gemini-3.8-flash-medium", "medium", tier=1,
                                 meter="agy-gemini"),
        "flash-high@agy": lane("agy", "gemini-3.8-flash-high", "high", tier=2, meter="agy-gemini"),
    },
}

# A codex slug that ends in an effort word is a Model of its own: the harness
# decides what a family is, never the spelling. grok runs high only.
GUARD_LANES = {
    "version": "delegate-lanes.v1",
    "lanes": {
        "edge-low@codex": lane("codex", "gpt-6-edge-low", "low", tier=1, meter="codex"),
        "edge-high@codex": lane("codex", "gpt-6-edge-high", "high", tier=1, meter="codex"),
        "grok46-high@grok": lane("grok", "grok-4.6", "high", tier=2, meter="grok"),
        "opus-high@claude": lane("claude", "claude-opus-5", "high", meter="claude"),
    },
}

# A published name on Claude Code's Opus Lane names the Model, so it reaches
# agy's Opus Lanes too.
PUBLISHED_AS_OPUS = {
    "version": "delegate-lanes.v1",
    "lanes": {
        "opus-high@claude": lane("claude", "claude-opus-5-5", "high", meter="claude-general",
                                 published_as=["Opus 5.5 Thinking"]),
        "opus-high@agy": lane("agy", "claude-opus-5-5-high", "high", meter="agy-claude-gpt"),
        "opus-low@agy": lane("agy", "claude-opus-5-5-low", "low", tier=2, meter="agy-claude-gpt"),
    },
}


def at(rows, effort):
    return [r for r in rows if r["effort"] == effort]


# --- A1: one rule decides which rows are a Lane's evidence -------------------
try:
    stranger = row("GLM-5.3", "max", "b1", 0.5, 3.0)
    rows = OPUS_ROWS + [stranger, "not a row", row("GLM-5.3", "high", "b2", 0.4, 2.0)]
    ev = LaneEvidence(OPUS_TWO_HARNESSES, rows)
    high = at(OPUS_ROWS, "high")
    record(
        "one published Opus row is evidence for both harnesses' Lanes at its effort",
        ev.available
        and same(ev.lane_rows("opus55-high@claude"), high)
        and same(ev.lane_rows("opus55-high@agy"), high)
        and same(ev.lane_rows("opus55-low@agy"), at(OPUS_ROWS, "low"))
        and same(ev.lane_rows("opus55-xhigh@claude"), at(OPUS_ROWS, "xhigh"))
        and same(ev.model_rows("opus55-high@claude"), OPUS_ROWS)
        and ev.unmatched() == ["GLM-5.3"],
        f"claude={shown(ev.lane_rows('opus55-high@claude'))} "
        f"agy={shown(ev.lane_rows('opus55-high@agy'))} unmatched={ev.unmatched()}",
    )
except Exception as e:
    record("one published Opus row is evidence for both harnesses' Lanes at its effort",
           False, repr(e))

try:
    two = LaneEvidence(OPUS_TWO_HARNESSES, OPUS_ROWS)
    one = LaneEvidence(OPUS_ONE_AGY, OPUS_ROWS)
    agy_runs = [r for r in OPUS_ROWS if r["effort"] != "xhigh"]
    record(
        "agy's Model rows hold only efforts agy runs",
        same(one.model_rows("opus55-high@agy"), agy_runs)
        and same(one.lane_rows("opus55-high@agy"), at(OPUS_ROWS, "high"))
        and same(one.model_rows("opus55-high@claude"), OPUS_ROWS)
        # every Lane on one Harness and Model gets the same list
        and all(same(two.model_rows(f"opus55-{e}@agy"), agy_runs) for e in ("low", "medium", "high"))
        and all(same(two.model_rows(f"opus55-{e}@claude"), OPUS_ROWS)
                for e in ("low", "medium", "high", "xhigh")),
        f"one={shown(one.model_rows('opus55-high@agy'))}",
    )
except Exception as e:
    record("agy's Model rows hold only efforts agy runs", False, repr(e))

try:
    edge_low = [row("gpt-6-edge-low", "low", b, 0.9, 0.5) for b in ("b1", "b2")]
    edge_high = [row("gpt-6-edge-high", "high", b, 0.5, 2.0) for b in ("b1", "b2")]
    # the real AA rows publish Grok 4.6 at efforts the grok CLI cannot run
    grok = [row("Grok 4.6", e, "b1", s, c)
            for e, s, c in (("low", 0.3, 0.2), ("high", 0.5, 1.0), ("xhigh", 0.6, 0.9))]
    family = row("gpt-6-edge", "high", "b1", 0.7, 1.0)
    ev = LaneEvidence(GUARD_LANES, edge_low + edge_high + grok + [family])
    record(
        "a codex slug ending in an effort word is a Model of its own",
        same(ev.model_rows("edge-low@codex"), edge_low)
        and same(ev.model_rows("edge-high@codex"), edge_high)
        and same(ev.lane_rows("edge-high@codex"), edge_high)
        and same(ev.model_rows("grok46-high@grok"), at(grok, "high"))
        and same(ev.lane_rows("grok46-high@grok"), at(grok, "high"))
        and ev.lane_rows("opus-high@claude") == []
        and ev.unmatched() == ["gpt-6-edge"],
        f"edge-high={shown(ev.model_rows('edge-high@codex'))} "
        f"grok={shown(ev.model_rows('grok46-high@grok'))} unmatched={ev.unmatched()}",
    )
except Exception as e:
    record("a codex slug ending in an effort word is a Model of its own", False, repr(e))

try:
    flash = [row(name, e, b, s, c)
             for name in ("gemini-3.8-flash", "Gemini 3.8 Flash")
             for e, s, c in (("medium", 0.60, 1.0), ("high", 0.50, 2.0))
             for b in ("b1",)]
    ev = LaneEvidence(AGY_CARRY_LANES, flash)
    record(
        "an agy family's rows at one effort belong to the Lane whose slug carries it",
        same(ev.lane_rows("flash-medium@agy"), at(flash, "medium"))
        and same(ev.lane_rows("flash-high@agy"), at(flash, "high"))
        and ev.lane_rows("flash-low@agy") == []
        and all(same(ev.model_rows(name), flash) for name in AGY_CARRY_LANES["lanes"])
        and ev.unmatched() == [],
        f"medium={shown(ev.lane_rows('flash-medium@agy'))} high={shown(ev.lane_rows('flash-high@agy'))}",
    )
except Exception as e:
    record("an agy family's rows at one effort belong to the Lane whose slug carries it",
           False, repr(e))

try:
    stated = row("Gemini 3.8 Flash", "high", "b1", 0.5, 2.0)
    unstated = [row("Gemini 3.8 Flash", effort, "b1", 0.55, 1.5) for effort in (None, "", "unknown")]
    ev = LaneEvidence(AGY_CARRY_LANES, unstated + [stated])
    record(
        "a row that states no effort belongs to the Model and to no Lane",
        all(same(ev.model_rows(name), unstated + [stated]) for name in AGY_CARRY_LANES["lanes"])
        and same(ev.lane_rows("flash-high@agy"), [stated])
        and ev.lane_rows("flash-medium@agy") == [] and ev.lane_rows("flash-low@agy") == []
        and ev.unmatched() == [],
        f"model={shown(ev.model_rows('flash-high@agy'))} high={shown(ev.lane_rows('flash-high@agy'))} "
        f"unmatched={ev.unmatched()}",
    )
except Exception as e:
    record("a row that states no effort belongs to the Model and to no Lane", False, repr(e))

try:
    high = row("Opus 5.5 Thinking", "high", "tier", 52.0, 2.0)
    low = row("opus 5.5  thinking", "low", "tier", 35.0, 0.5)
    ev = LaneEvidence(PUBLISHED_AS_OPUS, [high, low])
    record(
        "a published_as name reaches every Harness that runs the Model",
        same(ev.lane_rows("opus-high@claude"), [high])
        and same(ev.lane_rows("opus-high@agy"), [high])
        and same(ev.lane_rows("opus-low@agy"), [low])
        and same(ev.model_rows("opus-high@agy"), [high, low])
        and ev.unmatched() == [],
        f"claude={shown(ev.lane_rows('opus-high@claude'))} agy-high={shown(ev.lane_rows('opus-high@agy'))} "
        f"agy-low={shown(ev.lane_rows('opus-low@agy'))} unmatched={ev.unmatched()}",
    )
except Exception as e:
    record("a published_as name reaches every Harness that runs the Model", False, repr(e))

try:
    none = LaneEvidence(OPUS_TWO_HARNESSES, None)
    empty = LaneEvidence(OPUS_TWO_HARNESSES, [])
    record(
        "None is unavailable; an empty list is available and empty",
        none.available is False and empty.available is True
        and none.lane_rows("opus55-high@claude") == [] and none.model_rows("opus55-high@claude") == []
        and none.unmatched() == []
        and empty.lane_rows("opus55-high@claude") == [] and empty.model_rows("opus55-high@agy") == []
        and empty.unmatched() == [],
        f"none={none.available} empty={empty.available}",
    )
except Exception as e:
    record("None is unavailable; an empty list is available and empty", False, repr(e))

try:
    ev = LaneEvidence(OPUS_TWO_HARNESSES, OPUS_ROWS)
    bare = LaneEvidence({"lanes": {"bare@codex": {"harness": "codex", "effort": "high"}}}, OPUS_ROWS)
    record(
        "a Lane the catalog lacks has no rows",
        ev.lane_rows("opus55-max@claude") == [] and ev.model_rows("opus55-max@claude") == []
        and ev.lane_rows("nope") == []
        # a catalog lane with no model owns nothing
        and bare.lane_rows("bare@codex") == [] and bare.model_rows("bare@codex") == [],
        f"max={ev.lane_rows('opus55-max@claude')}",
    )
except Exception as e:
    record("a Lane the catalog lacks has no rows", False, repr(e))

sys.exit(1 if fails else 0)
