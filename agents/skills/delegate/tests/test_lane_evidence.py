#!/usr/bin/env python3
"""test_lane_evidence.py — which benchmark rows belong to which Lane.

The interface is the test surface: `LaneEvidence(lanes_doc, rows)` and its
queries. Run: python3 tests/test_lane_evidence.py
"""
import copy
import json
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


# --- A2: one record per row, and the Model a printed name names ---------------
with open(os.path.join(HERE, "..", "assets", "samples", "lanes.json"), encoding="utf-8") as _f:
    SAMPLE = json.load(_f)


def ident(ev, name):
    """The display name a printed name resolves to, or None."""
    return ev.identify(name)["lane_model"]


# test_catalog 7.5, ported: the printed names a source prints, against the
# sample catalog with an astra Lane and Fable's published name.
try:
    astra = copy.deepcopy(SAMPLE)
    astra["lanes"]["astra-high@codex"] = dict(astra["lanes"]["sol-high@codex"], model="gpt-6-astra")
    astra["lanes"]["fable-xhigh@claude"]["published_as"] = ["Fable 5.1"]
    ev = LaneEvidence(astra, [])
    cases = (
        ("GPT-6 Astra", "gpt-6-astra", "a display name differing only in case and separators"),
        ("gpt-6-astra", "gpt-6-astra", "a slug already in catalog form"),
        ("GPT-5.6 Sol", "gpt-5.6-sol", "a display name whose dot is a separator"),
        # agy names the effort in the slug; the Model is its family
        ("Gemini 3.8 Flash", "gemini-3.8-flash", "a lane model carrying an effort suffix"),
        ("Fable 5.1", "claude-fable-5-1", "a published_as entry"),
        ("fable  5.1", "claude-fable-5-1", "a published_as entry, loosely typed"),
        ("GLM-5.3", None, "a model that is nobody's lane"),
        ("", None, "an empty name"),
        (None, None, "no name at all"),
    )
    wrong = {name: ident(ev, name) for name, want, _tag in cases if ident(ev, name) != want}
    reasons = {name: ev.identify(name)["identity_reason"] for name in ("GLM-5.3", "", None)}
    flash_row = row("Gemini 3.8 Flash", "high", "b1", 0.5, 2.0)
    flash = LaneEvidence(astra, [flash_row])
    record(
        "7.5 every printed name identifies the Model a Lane runs, and a stranger none",
        not wrong
        and reasons == {"GLM-5.3": "no catalog model", "": "empty published name",
                        None: "empty published name"}
        and ev.identify("GPT-6 Astra")["identity"] == "resolved"
        and ev.identify("GLM-5.3")["identity"] == "unresolved"
        and same(flash.lane_rows("flash-high@agy"), [flash_row]),
        f"wrong={wrong} reasons={reasons}",
    )
except Exception as e:
    record("7.5 every printed name identifies the Model a Lane runs, and a stranger none",
           False, repr(e))

# test_catalog 7.6 and 7.6b, ported: two agy members are one Model, and the
# row's effort decides which Lane's evidence it is.
try:
    two = copy.deepcopy(SAMPLE)
    two["lanes"]["flash-medium@agy"] = dict(two["lanes"]["flash-high@agy"], effort="medium",
                                            model="gemini-3.8-flash-medium")
    rows = [row("Gemini 3.8 Flash", e, "b1", 0.5, 1.0) for e in ("medium", "high", "low")]
    ev = LaneEvidence(two, rows)
    record(
        "7.6 a name two agy members carry names their one Model, and the effort picks the Lane",
        ident(ev, "Gemini 3.8 Flash") == "gemini-3.8-flash"
        and same(ev.lane_rows("flash-medium@agy"), [rows[0]])
        and same(ev.lane_rows("flash-high@agy"), [rows[1]])
        # agy runs low, so the low row is the Model's; no Lane runs it
        and same(ev.model_rows("flash-high@agy"), rows)
        and ev.records()[2]["lanes"] == [] and ev.unmatched() == [],
        f"medium={shown(ev.lane_rows('flash-medium@agy'))} high={shown(ev.lane_rows('flash-high@agy'))}",
    )
except Exception as e:
    record("7.6 a name two agy members carry names their one Model, and the effort picks the Lane",
           False, repr(e))

# test_catalog 7.7 and 7.8, ported: a published_as entry reaches what the
# derived rule cannot, and a suffix on the published side is not dropped.
try:
    fable = LaneEvidence({"lanes": {
        "a@codex": lane("codex", "gpt-6-astra", "high"),
        "b@claude": lane("claude", "claude-fable-5-1", "xhigh", published_as=["Fable 5.1"]),
    }}, [])
    astra_only = LaneEvidence({"lanes": {"a@codex": lane("codex", "gpt-6-astra", "high")}}, [])
    agy_only = LaneEvidence({"lanes": {"a@agy": lane("agy", "gemini-3.8-flash-high", "high")}}, [])
    record(
        "7.7 an entry the derived rule cannot reach still names its Model; 7.8 a published suffix is kept",
        ident(fable, "Fable 5.1") == "claude-fable-5-1"
        and ident(astra_only, "gpt-6-astra-max") is None
        and astra_only.identify("gpt-6-astra-max")["identity_reason"] == "no catalog model"
        and ident(agy_only, "Gemini 3.8 Flash") == "gemini-3.8-flash",
        str([ident(fable, "Fable 5.1"), ident(astra_only, "gpt-6-astra-max"),
             ident(agy_only, "Gemini 3.8 Flash")]),
    )
except Exception as e:
    record("7.7 an entry the derived rule cannot reach still names its Model; "
           "7.8 a published suffix is kept", False, repr(e))

# test_catalog 7.9, ported (ticket 19): every Claude name an accepted rows file
# prints names the Model it denotes while a Lane runs it, and nothing once no
# Lane does. The catalog is machine-local, so these are its Claude Lanes as
# they stood that day, one effort each. A new Claude name in the rows fails
# here until someone decides which Model it is.
try:
    _data_dir = os.path.abspath(os.path.join(
        HERE, "..", "..", "..", "..", ".scratch", "delegate-redesign", "_data"))
    _denotes = {
        "Claude Fable 5.1": "claude-fable-5-1", "Fable 5.1": "claude-fable-5-1",
        "Claude Fable 5": "claude-fable-5", "Fable 5": "claude-fable-5",
        "Claude Opus 5": "claude-opus-5", "Opus 5": "claude-opus-5",
        "claude-opus-5": "claude-opus-5",
        # "Opus 5.5", the short form, is deliberately absent: the opus55 Lanes
        # carry no `published_as` for it. The check below fails the day a rows
        # file prints it, which is when someone has to decide.
        "Claude Opus 5.5": "claude-opus-5-5",
        "Claude Opus 4.8": "claude-opus-4-8", "Opus 4.8": "claude-opus-4-8",
        "Claude Sonnet 5": "claude-sonnet-5", "Sonnet 5": "claude-sonnet-5",
        "claude-sonnet-5": "claude-sonnet-5",
        "Claude Sonnet 4.6": "claude-sonnet-4-6",
        "Claude 4.5 Haiku": "claude-haiku-4-5-20251001",
    }
    claude_doc = {"lanes": {
        "fable-high@claude": lane("claude", "claude-fable-5-1", "high", published_as=["Fable 5.1"]),
        "haiku-high@claude": lane("claude", "claude-haiku-4-5-20251001", "high",
                                  published_as=["Claude 4.5 Haiku"]),
        "sonnet55-high@claude": lane("claude", "claude-sonnet-5-5", "high"),
        "opus55-high@claude": lane("claude", "claude-opus-5-5", "high"),
    }}
    models = {entry["model"] for entry in claude_doc["lanes"].values()}
    want = {name: (model if model in models else None) for name, model in _denotes.items()}
    seen = set()
    for name in ("aa-accepted.json", "tbench-accepted.json", "swerb-accepted.json"):
        path = os.path.join(_data_dir, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                seen |= {r["model"] for r in json.load(f)
                         if any(w in r["model"].lower()
                                for w in ("claude", "fable", "opus", "sonnet", "haiku"))}
    ev = LaneEvidence(claude_doc, [row(name, "high", "b", 1.0, 1.0) for name in sorted(want)])
    got = {name: ident(ev, name) for name in want}
    record(
        "7.9 every Claude name in the accepted rows names its Lane's Model, and other versions none",
        seen and seen <= set(want) and got == want
        and sorted(ev.unmatched()) == sorted(n for n, m in want.items() if m is None),
        f"unaccounted={sorted(seen - set(want))} wrong={ {n: g for n, g in got.items() if g != want[n]} }",
    )
except Exception as e:
    record("7.9 every Claude name in the accepted rows names its Lane's Model, and other versions none",
           False, repr(e))

try:
    fable = {"lanes": {"fable-high@claude": lane("claude", "claude-fable-5-1", "high")}}
    by_name = {"model": "Claude Fable 5.1", "slug": "claude-fable-5-1-20260901", "effort": "high",
               "benchmark": "DeepSWE", "performance": 0.61}
    by_slug = {"model": "Fable", "slug": "claude-fable-5-1", "effort": "high",
               "benchmark": "DeepSWE", "performance": 0.60}
    stranger = {"model": "Mystery", "slug": "mystery-1", "effort": "high",
                "benchmark": "DeepSWE", "performance": 0.10}
    ev = LaneEvidence(fable, [by_name, by_slug, stranger])
    recs = ev.records()
    record(
        "an Epoch row names its Model by display name, then by slug",
        same(ev.lane_rows("fable-high@claude"), [by_name, by_slug])
        and [r["published"] for r in recs] == ["Claude Fable 5.1", "claude-fable-5-1", "Mystery"]
        and [r["lane_model"] for r in recs] == ["claude-fable-5-1", "claude-fable-5-1", None]
        and [r["identity"] for r in recs] == ["resolved", "resolved", "unresolved"]
        and all(r["row"] is w for r, w in zip(recs, (by_name, by_slug, stranger)))
        and ev.unmatched() == ["Mystery"],
        repr([(r["published"], r["lane_model"], r["lanes"]) for r in recs]),
    )
except Exception as e:
    record("an Epoch row names its Model by display name, then by slug", False, repr(e))

try:
    edge = {"lanes": {
        "edge-high@codex": lane("codex", "gpt-6-edge-high", "high"),
        "edge-high@agy": lane("agy", "gpt-6-edge-high", "high"),
    }}
    flash_rows = [row("Gemini 3.8 Flash", e, "b1", 0.5, 1.0) for e in ("low", "high", None)]
    flash = LaneEvidence(AGY_CARRY_LANES, flash_rows)
    opus = LaneEvidence(OPUS_TWO_HARNESSES, OPUS_ROWS)
    clash = LaneEvidence(edge, []).identify("gpt-6-edge-high")
    record(
        "an agy Model's display name is its family, whatever the row's effort",
        [r["lane_model"] for r in flash.records()] == ["gemini-3.8-flash"] * 3
        and [r["effort"] for r in flash.records()] == ["low", "high", "unknown"]
        and len({r["model_key"] for r in flash.records()}) == 1
        and flash.records()[0]["lane_models"]
        == ["gemini-3.8-flash-high", "gemini-3.8-flash-low", "gemini-3.8-flash-medium"]
        and ident(flash, "gemini-3.8-flash-medium") == "gemini-3.8-flash"
        # a Model some Lane runs under its whole name keeps that name
        and {r["lane_model"] for r in opus.records()} == {"claude-opus-5-5"}
        and ident(opus, "claude-opus-5-5-high") == "claude-opus-5-5"
        # a name two Models answer to names neither
        and clash["identity"] == "unresolved" and clash["identity_reason"] == "conflicting identity"
        and clash["candidates"] == ["gpt-6-edge", "gpt-6-edge-high"],
        repr([(r["lane_model"], r["effort"], r["model_key"]) for r in flash.records()] + [clash]),
    )
except Exception as e:
    record("an agy Model's display name is its family, whatever the row's effort", False, repr(e))

try:
    rows = [row("GLM-5.3", "max", "b1", 0.5, 3.0), row("Grok 4.3", "high", "b1", 0.4, 1.0),
            row("GLM-5.3", "high", "b2", 0.4, 2.0), row("Claude Opus 5.5", "high", "b1", 0.7, 2.0),
            row("", "high", "b1", 0.1, 1.0),
            {"model": "", "slug": "zzz-1", "effort": "high", "benchmark": "DeepSWE", "performance": 0.2}]
    ev = LaneEvidence(OPUS_TWO_HARNESSES, rows)
    record(
        "unmatched lists each unnamed printed name once, first seen first",
        ev.unmatched() == ["GLM-5.3", "Grok 4.3", "zzz-1"]
        and ev.records()[4]["identity_reason"] == "empty published name",
        repr(ev.unmatched()),
    )
except Exception as e:
    record("unmatched lists each unnamed printed name once, first seen first", False, repr(e))

try:
    fixtures = [
        (OPUS_TWO_HARNESSES, OPUS_ROWS), (OPUS_ONE_AGY, OPUS_ROWS),
        (AGY_CARRY_LANES, [row("Gemini 3.8 Flash", e, "b1", 0.5, 1.0)
                           for e in ("low", "medium", "high", "xhigh", None, "unknown")]),
        (GUARD_LANES, [row(m, e, "b1", 0.5, 1.0) for m in ("gpt-6-edge-low", "gpt-6-edge-high",
                                                           "Grok 4.6", "gpt-6-edge")
                       for e in ("low", "high", "xhigh")]),
        (PUBLISHED_AS_OPUS, [row(m, e, "tier", 40.0, 1.0) for m in ("Opus 5.5 Thinking", "Claude Opus 5.5")
                             for e in ("low", "medium", "high")]),
    ]
    wrong = []
    for doc, rows in fixtures:
        ev = LaneEvidence(doc, rows + ["not a row"])
        recs = ev.records()
        if len(recs) != len(rows) or any(r["row"] is not w for r, w in zip(recs, rows)):
            wrong.append(("rows", [r["row"] for r in recs]))
            continue
        for rec in recs:
            holders = sorted(n for n in doc["lanes"] if any(r is rec["row"] for r in ev.lane_rows(n)))
            model = sorted(n for n in doc["lanes"] if any(r is rec["row"] for r in ev.model_rows(n)))
            if (rec["lanes"], rec["attributed"], rec["model_lanes"]) != (holders, bool(holders), model):
                wrong.append((rec["published"], rec["effort"], rec["lanes"], holders, rec["model_lanes"], model))
    record(
        "a record's lanes are exactly the Lanes whose lane_rows hold its row",
        not wrong,
        repr(wrong[:3]),
    )
except Exception as e:
    record("a record's lanes are exactly the Lanes whose lane_rows hold its row", False, repr(e))

sys.exit(1 if fails else 0)
