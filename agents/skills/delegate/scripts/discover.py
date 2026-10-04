#!/usr/bin/env python3
"""discover.py — deterministic model discovery for delegate harnesses.

Queries installed harness CLIs to discover available models and detects
configuration drift against the lane catalog (lanes.json).

Harness behaviors:
  - codex: runs `codex debug models`, returns JSON. Only models with
    visibility == "list" are reported. Models with visibility == "hide"
    (e.g. gpt-reserve, codex-auto-review) are internal or automated and
    are not offered to a human; excluding them is deliberate.
  - agy: runs `agy models`, returns plain text. The header line
    'Fetching available models...' is skipped; subsequent lines are
    tab-delimited '<slug>\t<display name>'.
  - grok: runs `grok models`, returns plain text prose. Slugs are
    extracted from bullet lines under 'Available models:', stripping
    leading bullet markers ('*', '-') and ' (default)' suffix.
  - claude: has no list command. Claude models come from the catalog's
    claude lanes, one entry per model, with the stated reason that they are
    hand-named and undiscoverable. Claude models are never guessed. Their
    efforts come from `claude --help`, which prints the `--effort` values on
    the line after the flag; when that output lists none, the adapter's
    `efforts` stand in. A Haiku model gets no efforts: the Claude Code docs
    (https://code.claude.com/docs/en/model-config, checked 2026-09-12) say
    Haiku supports no effort level.

  Each of these is the harness adapter's `models` (scripts/harnesses/); this
  module asks it and branches on no harness.

Efforts per harness (ticket 19):
  - codex: per model, from `codex debug models`.
  - claude: from `claude --help`, as above.
  - agy: in the slug. `gemini-3.8-flash-high`, `-medium` and `-low` are one
    model family, `gemini-3.8-flash`, with efforts high, medium and low, and
    a stanza for one of them names the suffixed slug.
  - grok: the grok adapter's `efforts` (scripts/harnesses/grok.py, which
    the catalog checks lanes against); `grok --help` lists no values and the
    CLI accepts any, so only the effort a lane has run at is offered.

Drift detection:
  - Slugs with no lane: models offered by a present harness that have no
    corresponding lane in lanes.json.
  - Lanes with retired/missing models: lanes in lanes.json whose model
    is no longer returned by the harness (checked only for successfully
    queried harnesses; claude lanes are excluded).

Generation (ticket 33):
  - Every model carries its `level` (the slug with the version removed) and its
    `version`, and says whether it is `superseded`: by the harness itself
    (codex sets `upgrade` on a model it is retiring) or by another model of the
    same level at a higher version. The rest are the current generation.
  - `refresh_catalog` proposes, in memory, the catalog that holds a lane for
    every effort of every current-generation model, with the superseded models'
    lanes gone and each successor in its predecessor's place.

Exit status:
  Always exits 0. This script is a reporting tool, never a pipeline gate.
  Missing harness binaries or failing commands are reported inline.

--json schema:
  {
    "harnesses": {
      "<harness>": {
        "status": "ok" | "missing" | "error",
        "error": "<string>" | null,
        "discovered_count": <int>,
        "complete": <bool>    (when ok: the list is all the harness runs)
      }
    },
    "models": [
      {
        "harness": "<harness>",
        "slug": "<slug>",
        "display_name": "<string>" | null,
        "lane": "<lane_name>" | "none",
        "lanes": ["<lane_name>"],
        "efforts": ["<effort>"],
        "unknown_efforts": ["<effort word no lane on the harness may carry>"],
        "reason": "<string>" | null,
        "level": "<slug with the version removed>",
        "version": [<int>],
        "superseded": "<why>" | null,
        "members": {"<effort>": "<slug>"}
      }
    ],
    "unmapped": [
      {
        "harness": "<harness>",
        "slug": "<slug>",
        "display_name": "<string>" | null
      }
    ],
    "retired": [
      {
        "lane": "<lane_name>",
        "harness": "<harness>",
        "model": "<slug>"
      }
    ]
  }

Test seams:
  --config-dir: path to directory containing lanes.json and routing.json.
  --harnesses: comma-separated list of harnesses considered present on PATH.
  --fixture-dir: path to directory containing harness fixture files
    (codex-debug-models.json, agy-models.txt, grok-models.txt, claude-help.txt).
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import harnesses
from catalog import CatalogError, load_catalog
from harnesses import EFFORTS

# Harness evaluation order: harnesses with a model list first, then those whose
# models the catalog names by hand. Every per-harness fact below comes from the
# registry (scripts/harnesses/).
DISCOVER_HARNESSES = harnesses.discovery_order()

# A slug component that is a version: `6`, `5.6`, and the `5` `5` of
# `claude-opus-5-5`.
VERSION_PART = re.compile(r"^\d+(?:\.\d+)*$")
# A date stamp at the end of a slug, as one part (`20251001`) or three
# (`2026-11-01`). It dates a snapshot of a version and is no part of it, so
# `gpt-6-sol-2026-11-01` is `gpt-sol` at (6,), not (6, 2026, 11, 1).
DATE_PART = re.compile(r"^(?:19|20)\d\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$")
DATE_PARTS = (re.compile(r"^(?:19|20)\d\d$"), re.compile(r"^(?:0[1-9]|1[0-2])$"),
              re.compile(r"^(?:0[1-9]|[12]\d|3[01])$"))

# The words that name a whole family rather than one model. A new lane is named
# after the model, so `gpt-6-sol` gives `sol6`; where the family word is the
# model's own name, as grok's is, the name keeps it and gives `grok47`.
VENDOR_WORDS = harnesses.vendor_words()

# An ultra lane is generated off and says why: no source scores it, and its
# automatic task delegation contradicts the worker preamble (ticket 15).
ULTRA_BASIS = (
    "unscoreable: no published source reports ultra on any benchmark for any model; "
    "ultra is maximum reasoning with automatic task delegation, which contradicts worker preamble "
    "('Do not delegate, spawn subagents, or call other agents'); "
    "meter_weight is a property of the plan, not the model (no benchmark can supply it)"
)

def read_harness(harness, fixture_dir=None, runner=None):
    """The raw text a harness command prints, from a runner, a fixture, or the
    CLI itself. Returns (text, error_string)."""
    if runner is not None:
        try:
            raw = runner(harness)
        except Exception as e:
            return None, f"runner error: {e}"
    elif fixture_dir is not None:
        adapter = harnesses.get(harness)
        fname = adapter.fixture_file if adapter is not None else f"{harness}-models.txt"
        fpath = os.path.join(fixture_dir, fname)
        if not os.path.isfile(fpath):
            return None, f"fixture file missing: {fname}"
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            return None, f"cannot read fixture {fname}: {e}"
    else:
        adapter = harnesses.get(harness)
        cmd = list(adapter.list_command or ()) if adapter is not None else []
        if not cmd:
            return None, f"no discovery command for harness '{harness}'"
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode != 0:
                err_msg = res.stderr.strip() or f"exit code {res.returncode}"
                return None, f"command failed: {err_msg}"
            raw = res.stdout
        except subprocess.TimeoutExpired:
            return None, "command timed out (30s)"
        except Exception as e:
            return None, f"execution failed: {e}"
    return raw, None


def model_takes_effort(harness, slug):
    """False for a model its harness runs with no effort level at all."""
    adapter = harnesses.get(harness)
    return adapter is None or adapter.model_takes_effort(slug)


def model_level(slug, harness):
    """(level, version) for a model slug: the slug with its version taken out,
    and that version as a tuple of whole numbers.

    `gpt-6-sol` and `gpt-5.6-sol` are both level `gpt-sol`, at (6,) and (5, 6);
    `claude-opus-5-5` is `claude-opus` at (5, 5); a slug with no version is its
    own level, at (). The harness's own effort rule comes off first
    (`harnesses.family`), so one agy slug family has one level, and a trailing
    date stamp comes off next (`DATE_PART`):
    `claude-haiku-4-5-20251001` is `claude-haiku` at (4, 5).
    """
    base, _effort = harnesses.family(harness, slug or "")
    parts = base.split("-")
    if len(parts) > 1 and DATE_PART.match(parts[-1]):
        parts = parts[:-1]
    elif len(parts) > 3 and all(rule.match(part) for rule, part in zip(DATE_PARTS, parts[-3:])):
        parts = parts[:-3]
    words, version = [], []
    for part in parts:
        if VERSION_PART.match(part):
            version.extend(int(number) for number in part.split("."))
        else:
            words.append(part)
    return "-".join(words), tuple(version)


def mark_generation(models, harness):
    """Give each model its `level`, `version` and `superseded`, in place.

    A model is superseded when the harness says so — codex names the model that
    replaces one it is retiring — or when another model on the same harness has
    the same level at a higher version. The rest are the current generation.
    """
    newest = {}
    for item in models:
        level, version = model_level(item["slug"], harness)
        item["level"], item["version"] = level, list(version)
        item["superseded"] = None
        best = newest.get(level)
        if best is None or version > tuple(best["version"]):
            newest[level] = item
    for item in models:
        upgrade = item.get("upgrade")
        replacement = upgrade.get("model") if isinstance(upgrade, dict) else None
        if replacement:
            item["superseded"] = f"{harness} replaces it with {replacement}"
            continue
        best = newest[item["level"]]
        if best is not item:
            item["superseded"] = f"{best['slug']} is newer"
    return models


def lane_stem(level, version, levels=()):
    """The word a new lane's name starts with: the level's own word and the
    version's digits, so `gpt-sol` at (6,) gives `sol6`, `claude-opus` at (5, 5)
    gives `opus55` and `grok` at (4, 7) gives `grok47`.

    `levels` is the harness's current-generation levels. A level that extends
    one of them — `grok-build-fast` extends `grok` — takes that level's stem and
    the word that tells it apart, so `grok-4.7-build-fast` reads `grok47fast`
    beside `grok47`. A superseded level shapes no name: codex still lists
    `gpt-5.5`, whose level is the bare `gpt`, and `gpt-6-sol` is `sol6` all the
    same.
    """
    for other in sorted(levels, key=len, reverse=True):
        if other != level and level.startswith(other + "-"):
            tail = level[len(other) + 1:].split("-")[-1]
            return lane_stem(other, version) + tail
    digits = "".join(str(number) for number in version)
    words = [word for word in level.split("-") if word not in VENDOR_WORDS]
    return (words or level.split("-"))[-1] + digits


def discover(cat, present=None, fixture_dir=None, runner=None):
    """Discovers available models across harnesses and checks catalog drift.

    cat: dict containing 'lanes' (e.g. from catalog.load_catalog)
    present: set of harness names present on PATH (or None to detect)
    fixture_dir: path to directory containing harness fixtures (or None)
    runner: callable(harness) -> raw string (or None)
    """
    if present is None:
        if fixture_dir is not None:
            present = {h for h in DISCOVER_HARNESSES if harnesses.get(h).present_in(fixture_dir)}
        else:
            present = harnesses.installed(DISCOVER_HARNESSES)
    else:
        present = set(present)

    lanes_dict = cat.get("lanes", {}) if isinstance(cat, dict) else {}

    # Map (harness, model) -> list of lane names
    lane_map = {}
    for lane_name, lane_def in lanes_dict.items():
        if isinstance(lane_def, dict):
            h = lane_def.get("harness")
            m = lane_def.get("model")
            if h and m:
                lane_map.setdefault((h, m), []).append(lane_name)

    harnesses_doc = {}
    models_doc = []
    unmapped = []
    retired = []

    for harness in DISCOVER_HARNESSES:
        if harness not in present:
            harnesses_doc[harness] = {
                "status": "missing",
                "error": None,
                "discovered_count": 0,
            }
            continue

        adapter = harnesses.get(harness)
        raw, err = read_harness(harness, fixture_dir=fixture_dir, runner=runner)
        own_lanes = {name: lane for name, lane in lanes_dict.items()
                     if isinstance(lane, dict) and lane.get("harness") == harness}
        raw_models, err, complete = adapter.models(raw, err, own_lanes)
        if err is not None:
            harnesses_doc[harness] = {
                "status": "error",
                "error": err,
                "discovered_count": 0,
            }
            continue

        harnesses_doc[harness] = {
            "status": "ok",
            "error": None,
            "discovered_count": len(raw_models),
            "complete": complete,
        }

        discovered_slugs = set()
        mark_generation(raw_models, harness)
        for item in raw_models:
            # an effort word no Lane on this harness may carry is kept apart,
            # so the refresh names it instead of proposing a Lane for it
            efforts, unknown = adapter.split_efforts(item.get("efforts"))
            unknown += [w for w in item.get("unknown_efforts") or () if w not in unknown]
            slug = item["slug"]
            display_name = item.get("display_name")
            # an agy family answers for every slug in it: a lane on
            # gemini-3.8-flash-medium is a lane on gemini-3.8-flash
            members = set((item.get("members") or {}).values()) or {slug}
            discovered_slugs.update(members)

            matched_lanes = [
                name for m in sorted(members) for name in lane_map.get((harness, m), [])
            ]
            lane_str = ", ".join(matched_lanes) if matched_lanes else "none"

            models_doc.append({
                "harness": harness,
                "slug": slug,
                "display_name": display_name,
                "lane": lane_str,
                "lanes": matched_lanes,
                "efforts": efforts,
                "unknown_efforts": unknown,
                "reason": item.get("reason"),
                "level": item["level"],
                "version": item["version"],
                "superseded": item["superseded"],
                # agy names the effort in the slug, so a family says which slug
                # each effort takes; a family of one has no effort and no entry
                "members": {e: m for e, m in (item.get("members") or {}).items() if e},
            })

            if not matched_lanes:
                unmapped.append({
                    "harness": harness,
                    "slug": slug,
                    "display_name": display_name,
                })

        # Drift check: lanes pointing at models not in discovered list. Only a
        # complete list says a model is gone.
        if not complete:
            continue
        for lane_name, lane_def in lanes_dict.items():
            if isinstance(lane_def, dict) and lane_def.get("harness") == harness:
                m = lane_def.get("model")
                if m and m not in discovered_slugs:
                    retired.append({
                        "lane": lane_name,
                        "harness": harness,
                        "model": m,
                    })

    return {
        "harnesses": harnesses_doc,
        "models": models_doc,
        "unmapped": unmapped,
        "retired": retired,
    }


# --- the refresh: bring the catalog to the current generation (ticket 33) ----

# A price is local knowledge read off a vendor's page, so a new lane starts with
# none rather than with its predecessor's, which would be a wrong number that
# reads like a measured one.
UNPRICED_NOTE = (
    "UNPRICED: the price keys stay null until the vendor's page is read; a price is "
    "never copied from another model."
)

def lane_model(harness, model, effort):
    """The model string a lane on this model at this effort carries. A harness
    that names the effort in the slug says which slug an effort takes."""
    return harnesses.get(harness).lane_model(model, effort)


def model_slugs(model):
    """Every slug a model answers for: an agy family answers for each member."""
    return set((model.get("members") or {}).values()) or {model["slug"]}


def own_vendor(model):
    """True when the model is the harness's own vendor's: `gpt-*` on codex,
    `gemini-*` on agy, `grok-*` on grok, `claude-*` on claude.

    The refresh proposes lanes for these only, and nothing else names them
    either: the other vendors' models agy serves (`claude-sonnet-5-5-high`,
    `gpt-oss-120b-medium`) stay in the report, but a lane on somebody else's
    model through agy is not what this catalog is for (ticket 33). The adapter
    decides (`Harness.owns`): Kiro owns every vendor's models, and agy owns
    Opus as well as Gemini, on its own pool (any-harness ticket 31).
    """
    adapter = harnesses.get(model.get("harness"))
    return adapter is not None and bool(model.get("level")) and adapter.owns(model.get("slug"))


def _predecessor(model, models, lanes):
    """The superseded model whose lanes this model takes over: the same level on
    the same harness, at the highest version the catalog still runs."""
    best = None
    for item in models:
        if item is model or item["harness"] != model["harness"] or item["level"] != model["level"]:
            continue
        if not item.get("superseded"):
            continue
        slugs = model_slugs(item)
        if not any(lane.get("harness") == item["harness"] and lane.get("model") in slugs
                   for lane in lanes.values()):
            continue
        if best is None or tuple(item["version"]) > tuple(best["version"]):
            best = item
    return best


def _free_name(stem, effort, harness, *taken):
    """`<stem>-<effort>@<harness>`, kept clear of a lane another model runs.

    Two models of one harness deriving the same stem is the one way this name
    can collide; a counter after the stem is the smallest thing that separates
    them and stays the same on every run.
    """
    name = harnesses.lane_name(stem, effort, harness)
    counter = 1
    while any(name in names for names in taken):
        counter += 1
        name = harnesses.lane_name(f"{stem}{counter}", effort, harness)
    return name


def _donor(harness, effort, lanes, new_lanes, leaving, meter=None):
    """The lane a new lane copies its meter, weight and timeout from: the same
    harness's lane at the same effort.

    A lane this refresh removes is no use as the note's reference, so a lane it
    adds stands in; failing both, the harness's first lane at any effort does,
    because a figure from the same harness beats no figure at all. When the
    model decides its Meter (`Harness.lane_meter`), a lane on that Meter is
    tried first, since its weight was set against the same pool.
    """
    candidates = [(name, lane) for name, lane in lanes.items()
                  if lane.get("harness") == harness and name not in leaving]
    candidates += [(name, lane) for name, lane in new_lanes.items() if lane["harness"] == harness]
    if meter is not None:
        same = [(name, lane) for name, lane in candidates if lane.get("meter") == meter]
        candidates = same + [item for item in candidates if item not in same]
    for name, lane in candidates:
        if lane.get("effort") == effort:
            return name, lane
    return candidates[0] if candidates else (None, None)


def _add_meter(doc, harness, meter_name, like):
    """Adds the Meter a model decides (`Harness.lane_meter`) when the catalog
    lacks it, copying the plan and price of the Meter `like` names: on agy both
    pools come with one Google plan, as both Claude Meters come with one Max
    plan."""
    meters = doc.setdefault("meters", {})
    if meter_name in meters:
        return
    source = meters.get(like) or {}
    meters[meter_name] = {
        "harness": harness,
        "plan": source.get("plan", "unknown"),
        "price_month": source.get("price_month", 0),
        "note": (f"UNMEASURED: plan and price_month copied from {like}; "
                 f"the refresh added this Meter for a new lane"),
    }


def _starter(harness, doc):
    """(where the figures came from, a donor-shaped record) for the first Lane
    on a harness whose adapter declares a starter, adding its Meter to the
    document when the catalog has none; None for any other harness."""
    adapter = harnesses.get(harness)
    starter = adapter.starter() if adapter is not None else None
    if starter is None:
        return None
    meter_name, meter, lane = starter
    meters = doc.setdefault("meters", {})
    if meter_name not in meters:
        meters[meter_name] = {"harness": harness, **meter}
    return f"the {harness} adapter's starter", {"meter": meter_name, "tier": 1, **lane}


def _lane_stem_of(lane_name):
    """`sol` from `sol-high@codex`: what the start page prints as `sol-*@codex`."""
    return harnesses.split_lane(lane_name)[0].rsplit("-", 1)[0]


def refresh_catalog(lanes_doc, discovery, published_models=()):
    """(refreshed lanes document, the changes it proposes).

    The catalog the wizard then edits: a lane for every effort of every
    current-generation model of every harness, the superseded models' lanes
    gone, and every new lane with a predecessor in that predecessor's place.
    Each harness offers its own vendor's models only, and a model its harness
    hides never reaches here.

    A new lane starts carried, `ultra` apart, so every effort of every current
    model reaches the screening page (ticket 35). It takes its predecessor's
    Tier, Order, Meter, weight and timeout, and not its `enabled`.

    A model that takes no effort level (Claude's Haiku) still takes its
    predecessor's place, in one lane at the effort its predecessor's lane
    carries, which is how the catalog writes such a lane. An effort word the
    harness lists that no lane on it may carry gets no lane; the plan's
    `notices` name it instead, so the wizard can say so.

    Nothing is written: the wizard's confirm writes, and quitting writes
    nothing (ticket 33).
    """
    doc = copy.deepcopy(lanes_doc)
    lanes = doc.get("lanes") or {}
    found = [item for item in (discovery.get("models") or []) if isinstance(item, dict)]
    # each harness's adapter says which models the refresh works from: a
    # harness with no list adds the newer ones the benchmark rows name
    models = []
    for harness in DISCOVER_HARNESSES:
        models += harnesses.get(harness).generation(
            [item for item in found if item.get("harness") == harness], published_models)
    own = [item for item in models if own_vendor(item)]

    levels = {}
    for item in own:
        if not item.get("superseded"):
            levels.setdefault(item["harness"], set()).add(item["level"])

    by_key = {(lane.get("harness"), lane.get("model"), lane.get("effort")): name
              for name, lane in lanes.items()}
    leaving = {}
    for item in own:
        if not item.get("superseded"):
            continue
        slugs = model_slugs(item)
        for name, lane in lanes.items():
            if lane.get("harness") == item["harness"] and lane.get("model") in slugs:
                leaving[name] = item

    current = [item for item in own if not item.get("superseded")]
    predecessors = [_predecessor(item, own, lanes) for item in current]
    # A model that takes a predecessor's place goes first: its new lanes are
    # what a model new to the harness copies its figures from when every lane
    # the harness had is leaving, whatever order the harness lists them in.
    work = sorted(range(len(current)), key=lambda index: predecessors[index] is None)

    plan_by_index, new_by_index, successors, notices = {}, {}, {}, []
    new_lanes = {}
    for index in work:
        item, predecessor = current[index], predecessors[index]
        harness = item["harness"]
        adapter = harnesses.get(harness)
        stem = lane_stem(item["level"], tuple(item["version"]), levels[harness])
        efforts, unknown = adapter.split_efforts(item.get("efforts"))
        unknown += [word for word in item.get("unknown_efforts") or () if word not in unknown]
        for word in unknown:
            why = ("delegate does not know it yet" if word not in EFFORTS
                   else f"delegate does not run {harness} at it yet")
            notices.append(f"{harness} lists effort '{word}' for {item['slug']}; {why}")
        no_effort = not efforts and not unknown
        if no_effort and predecessor is not None:
            # one lane, at the effort the predecessor's lane carries: a carried
            # one if it has one
            own_lanes = [lane for lane in lanes.values()
                         if lane.get("harness") == harness and lane.get("model") in model_slugs(predecessor)]
            carried = [lane for lane in own_lanes if lane.get("enabled") is not False]
            efforts = [(carried or own_lanes)[0]["effort"]] if own_lanes else []
        added, replaced = [], []
        for effort in efforts:
            model_text = lane_model(harness, item, effort)
            if (harness, model_text, effort) in by_key:
                continue
            meter = adapter.lane_meter(model_text)
            name = _free_name(stem, effort, harness, lanes, new_lanes)
            pred_name = None
            if predecessor is not None:
                pred_name = by_key.get(
                    (harness, lane_model(harness, predecessor, effort), effort)
                )
            if pred_name:
                source_name, source = pred_name, lanes[pred_name]
                basis = (f"{item['slug']} supersedes {predecessor['slug']} on {harness}; "
                         f"takes the place of {pred_name}")
            else:
                source_name, source = _donor(harness, effort, lanes, new_lanes, set(leaving), meter)
                basis = f"{item['slug']} is new on {harness} at effort '{effort}'"
            if source is None:
                starter = _starter(harness, doc)
                if starter is None:
                    # nothing on this harness to copy a weight or a timeout from
                    continue
                source_name, source = starter
                basis = f"{item['slug']} is new on {harness} at effort '{effort}'"
            if meter is not None and meter != source["meter"]:
                _add_meter(doc, harness, meter, source["meter"])
            record = {
                "harness": harness,
                "model": model_text,
                "effort": effort,
                "meter": meter or source["meter"],
                "meter_weight": source["meter_weight"],
                "timeout": source["timeout"],
                "price": {"in": None, "cache_read": None, "cache_write": None, "out": None},
                # a lane with no predecessor is marked on no tier page, so it
                # lands on tier 1 unless the user marks it higher
                "tier": source["tier"] if pred_name else 1,
                "basis": ULTRA_BASIS if effort == "ultra" else basis,
                "note": (f"UNMEASURED: meter_weight and timeout copied from {source_name}. "
                         f"{UNPRICED_NOTE}"),
            }
            if pred_name and "order" in source:
                record["order"] = source["order"]
            if effort == "ultra":
                # A new lane starts carried, so every effort of a new model is on
                # the screening page: `enabled` is the one field a successor does
                # not inherit, because a predecessor switched off at an effort is
                # a verdict on that model, not on this one (ticket 35). `ultra`
                # is never carried (ticket 15).
                record["enabled"] = False
            new_lanes[name] = record
            new_by_index.setdefault(index, []).append(name)
            added.append(name)
            if pred_name:
                successors.setdefault(pred_name, []).append(name)
                replaced.append(pred_name)
        if added:
            plan_by_index[index] = {
                "harness": harness,
                "model": item["slug"],
                "predecessor": predecessor["slug"] if predecessor else None,
                "stem": stem,
                "predecessor_stem": _lane_stem_of(replaced[0]) if replaced else None,
                "new": added,
                "replaced": replaced,
            }

    # the plan and the new lanes read in the harnesses' own listing order, not
    # the order they were made in
    plan_models = [plan_by_index[index] for index in sorted(plan_by_index)]
    new_lanes = {lane_name: new_lanes[lane_name]
                 for index in sorted(new_by_index) for lane_name in new_by_index[index]}
    ordered = {}
    for name, lane in lanes.items():
        if name in leaving:
            for successor in successors.get(name, []):
                ordered[successor] = new_lanes[successor]
            continue
        ordered[name] = lane
    for name, record in new_lanes.items():
        ordered.setdefault(name, record)
    doc["lanes"] = ordered
    return doc, {
        "models": plan_models,
        "new": list(new_lanes),
        "removed": sorted(leaving),
        "notices": notices,
    }


def map_lanes(discovery, lanes_doc):
    """A discovery result whose lane mapping reads the given catalog.

    The refresh changes the catalog in memory, so the drift the start page
    states has to be drift against the catalog the wizard is about to write and
    not against the one it read (ticket 33).

    A model with no lane is worth naming only when the refresh would have given
    it one: a superseded model, another vendor's model that agy serves, and a
    model its harness hides are all not shown, so listing them as lanes missing
    would name exactly what the refresh has just decided not to propose. After
    a refresh that list is normally empty, and the line goes with it.
    """
    result = copy.deepcopy(discovery)
    lane_map = {}
    for lane_name, lane in (lanes_doc.get("lanes") or {}).items():
        if isinstance(lane, dict) and lane.get("harness") and lane.get("model"):
            lane_map.setdefault((lane["harness"], lane["model"]), []).append(lane_name)
    # a harness that answered is a harness whose listing is the whole list, so a
    # lane of its that is not on it is a lane on a retired model
    slugs = {
        name: set() for name, info in (result.get("harnesses") or {}).items()
        if isinstance(info, dict) and info.get("status") == "ok" and info.get("complete", True)
    }
    unmapped = []
    for item in result.get("models") or []:
        harness = item.get("harness")
        members = model_slugs(item)
        if harness in slugs:
            slugs[harness].update(members)
        matched = [name for slug in sorted(members) for name in lane_map.get((harness, slug), [])]
        item["lane"] = ", ".join(matched) if matched else "none"
        item["lanes"] = matched
        if (not matched and harness in slugs
                and own_vendor(item) and not item.get("superseded")):
            unmapped.append({
                "harness": harness,
                "slug": item.get("slug"),
                "display_name": item.get("display_name"),
            })
    retired = []
    for lane_name, lane in (lanes_doc.get("lanes") or {}).items():
        harness = lane.get("harness")
        if harness not in slugs:
            continue
        if lane.get("model") not in slugs[harness]:
            retired.append({"lane": lane_name, "harness": harness, "model": lane.get("model")})
    result["unmapped"], result["retired"] = unmapped, retired
    return result


def format_report(result):
    """Formats discovery results as plain text with aligned columns."""
    lines = []
    lines.append("# models")

    models = result.get("models", [])
    harnesses = result.get("harnesses", {})

    max_harness_w = max((len(h) for h in DISCOVER_HARNESSES), default=6)
    max_slug_w = max((len(m["slug"]) for m in models), default=10)
    max_lane_w = max((len(f"lane: {m['lane']}") for m in models), default=10)

    for harness in DISCOVER_HARNESSES:
        h_info = harnesses.get(harness, {})
        status = h_info.get("status")

        if status == "missing":
            lines.append(f"{harness:<{max_harness_w}}  missing")
            continue
        if status == "error":
            err = h_info.get("error", "unknown error")
            lines.append(f"{harness:<{max_harness_w}}  error: {err}")
            continue

        h_models = [m for m in models if m["harness"] == harness]
        for m in h_models:
            lane_col = f"lane: {m['lane']}"
            line = f"{harness:<{max_harness_w}}  {m['slug']:<{max_slug_w}}  {lane_col:<{max_lane_w}}"
            if m.get("reason"):
                line = f"{line}  ({m['reason']})"
            if m.get("efforts"):
                line = f"{line}  efforts: {', '.join(m['efforts'])}"
            lines.append(line.rstrip())

    lines.append("\n# slugs with no lane")
    unmapped = result.get("unmapped", [])
    if unmapped:
        for item in unmapped:
            lines.append(f"{item['harness']:<{max_harness_w}}  {item['slug']}")
    else:
        lines.append("none")

    lines.append("\n# lanes whose model no longer appears in harness")
    retired = result.get("retired", [])
    if retired:
        max_ret_lane_w = max((len(r["lane"]) for r in retired), default=10)
        for item in retired:
            lines.append(f"{item['lane']:<{max_ret_lane_w}}  model: {item['model']}")
    else:
        lines.append("none")

    return "\n".join(lines)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="discover.py",
        description="Deterministic model discovery for delegate harnesses."
    )
    parser.add_argument("--cwd", default=None, help="working directory to find git root from")
    parser.add_argument("--config-dir", default=None, help="config directory containing lanes.json and routing.json")
    parser.add_argument("--harnesses", default=None, help="comma-separated list of present harnesses")
    parser.add_argument("--fixture-dir", default=None, help="directory containing harness output fixtures")
    parser.add_argument("--json", action="store_true", help="output as JSON")

    args = parser.parse_args(argv)

    try:
        cat = load_catalog(cwd=args.cwd, config_dir=args.config_dir)
    except CatalogError as e:
        sys.stderr.write(f"discover: warning: catalog: {e}\n")
        cat = {"lanes": {}}

    if args.harnesses is not None:
        present = set(h.strip() for h in args.harnesses.split(",") if h.strip())
    else:
        present = None

    result = discover(
        cat,
        present=present,
        fixture_dir=args.fixture_dir,
    )

    if args.json:
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
    else:
        print(format_report(result))

    # A report, never a gate: drift is reported, never signalled by exit code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
