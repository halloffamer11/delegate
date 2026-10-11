#!/usr/bin/env python3
"""lane_evidence.py — which benchmark rows belong to which Lane.

The catalog keys on slugs; a leaderboard prints a slug or a display name. This
is the one reconciliation of the two, used by `catalog.validate_lanes`
(`published_as_conflict`: one published name denotes one Model), by the pages
that group Lanes by Model (`model_identity`) and by every benchmark reader
through `LaneEvidence`: carry, the Tier proposal, the wizard, the report, model
inspection and the benchmark page. It imports only `harnesses`, which decides
what one Model is and which efforts it runs, never the spelling.
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnesses  # noqa: E402

# Benchmark sources print a model however they please: some publish the slug a
# harness accepts (`gpt-5.6-luna`), some a display name (`GPT-6 Astra`,
# `Fable 5.1`). The catalog keys on slugs, so a consumer of published rows has
# to reconcile the two. That mapping is local knowledge — which published name
# denotes which Model — so it lives beside the lane, where a human can read and
# correct it: the optional lane field `published_as`. An entry names the Model,
# so it reaches every Harness that runs that Model.
_NORM_SEP = re.compile(r"[-_. ]+")


def _normalize_name(value):
    """Lower-case, with the -_. and space separators collapsed to one hyphen."""
    if value is None:
        return ""
    return _NORM_SEP.sub("-", str(value).strip().lower()).strip("-")


# A source that did not state an effort has not said which Lane it measured.
# `unknown` is the key such a row's effort gets, so it is never dropped for
# being unlabelled, and it matches no Lane, so it is never attributed for it.
UNKNOWN_EFFORT = "unknown"
_UNSTATED_EFFORTS = (None, "", UNKNOWN_EFFORT)
_EMPTY_NAME, _NO_MODEL, _CONFLICT = "empty published name", "no catalog model", "conflicting identity"


def _stated_effort(row):
    """The effort a row (or a Lane) states, or None when it states none."""
    effort = row.get("effort")
    return None if effort in _UNSTATED_EFFORTS else str(effort)


def model_identity(lane: Optional[dict]) -> str:
    """The key "one Model" means across harnesses: the harness's family base,
    normalized, so kiro's `claude-opus-5.5`, agy's `claude-opus-5-5-high` and
    Claude Code's `claude-opus-5-5` are one Model, and a codex slug ending in
    an effort word is a Model of its own. "" for a Lane with no model."""
    lane = lane or {}
    return _normalize_name(harnesses.family(lane.get("harness"), lane.get("model") or "")[0])


def _model_lanes(lanes):
    """The Lanes of a `{name: lane}` mapping that carry a model string; a Lane
    with none names no Model and owns nothing."""
    return {name: lane for name, lane in (lanes or {}).items()
            if isinstance(lane, dict) and isinstance(lane.get("model"), str)
            and lane["model"].strip()}


def _own_names(lane):
    """The normalized names a Lane's Model answers to with no `published_as`
    entry: its Model identity and the Lane's own model string."""
    return [key for key in (model_identity(lane), _normalize_name(lane["model"])) if key]


def _published_as(lane):
    """A Lane's `published_as` entries that are strings, as written."""
    names = lane.get("published_as")
    if not isinstance(names, (list, tuple)):
        return []
    return [entry for entry in names if isinstance(entry, str)]


def published_as_conflict(lanes: dict) -> Optional[Tuple[str, str]]:
    """(lane name, message) for the first `published_as` entry that would make
    one name denote two Models, else None. `lanes` is a lanes document's
    `{name: lane}` mapping.

    An entry may not be another Model's identity or model string, and one name
    may not sit on Lanes of two Models. One name on the Lanes of one Model is
    allowed, whichever Harnesses run them: `Opus 5.5 Thinking` on Claude Code's
    `claude-opus-5-5` and on agy's `claude-opus-5-5-high` names one Model. Each
    message names both model strings. Whether `published_as` is a non-empty
    list of non-empty strings is the catalog's check, not this one.
    """
    lanes = _model_lanes(lanes)
    owners = {}
    for lane in lanes.values():
        for key in _own_names(lane):
            owners.setdefault(key, {}).setdefault(model_identity(lane), set()).add(lane["model"])
    claimed = {}
    for lane_name, lane in lanes.items():
        model = model_identity(lane)
        for name in _published_as(lane):
            key = _normalize_name(name)
            if not key:
                continue
            # the model string spelled as the entry first, so the message
            # names the slug the entry collides with
            foreign = sorted((spelling for other, spellings in owners.get(key, {}).items()
                              if other != model for spelling in spellings),
                             key=lambda spelling: (_normalize_name(spelling) != key, spelling))
            if foreign:
                return lane_name, (
                    f"published_as {name!r} already names model '{foreign[0]}', which another "
                    f"lane runs; that would read '{foreign[0]}' rows as '{lane['model']}'. Drop "
                    f"the entry, or put it on the lane that runs '{foreign[0]}'")
            first = claimed.setdefault(key, (name, lane_name, model, lane["model"]))
            if first[2] != model:
                return lane_name, (
                    f"published_as {name!r} names the same model as {first[0]!r} on lane "
                    f"'{first[1]}'; one published name denotes one model, but this would make "
                    f"it both '{first[3]}' and '{lane['model']}'")
    return None


def _printed_names(row):
    """A row's printed names, in the order they are read: its `model`, then
    its `slug` when it has one (an Epoch row)."""
    return [row.get("model"), row.get("slug")]


class LaneEvidence:
    """Which benchmark rows belong to which Lanes, for one catalog and one row set.

    The constructor attributes every row once; every query after it is a lookup
    that returns the caller's own row objects, unchanged and in input order.
    Whether a row counts (uncertain, composite, its score's shape) is the
    reader's question. A caller that changes a Lane's model, harness, effort or
    `published_as` builds a new one; `enabled`, `tier` and `order` are not read.
    """

    def __init__(self, lanes_doc: dict, rows: Optional[Sequence[dict]]) -> None:
        self._available = rows is not None
        lanes = _model_lanes((lanes_doc or {}).get("lanes"))
        harness_model = {name: (lane.get("harness"), model_identity(lane))
                         for name, lane in lanes.items()}
        # Each Model's display name: a Lane's model string that is the Model's
        # whole name (`claude-opus-5-5`, the exact spelling first), else the
        # harness family base (`gemini-3.8-flash`). It never depends on a row's
        # effort, so one Model draws as one sweep.
        self._display, self._spellings = {}, {}
        for name, lane in lanes.items():
            model = harness_model[name][1]
            self._spellings.setdefault(model, set()).add(lane["model"])
        for model in self._spellings:
            members = [lanes[n] for n in lanes if harness_model[n][1] == model]
            whole = ([m["model"] for m in members if m["model"] == model]
                     + [m["model"] for m in members if _normalize_name(m["model"]) == model])
            self._display[model] = whole[0] if whole else harnesses.family(
                members[0].get("harness"), members[0]["model"])[0]
        # A printed name names a Model when, normalized, it is a `published_as`
        # entry (the Model of the Lane carrying it), a Lane's Model identity or
        # its model string. A name two Models answer to names neither.
        self._names = {}
        for name, lane in lanes.items():
            published = filter(None, map(_normalize_name, _published_as(lane)))
            for key in _own_names(lane) + list(published):
                self._names.setdefault(key, set()).add(harness_model[name][1])
        claimed, identified, self._unmatched = {}, [], []
        for row in rows or ():
            if not isinstance(row, dict):
                continue
            ident = self._identify(_printed_names(row))
            identified.append((row, ident))
            if ident["model_key"] is not None:
                claimed.setdefault(ident["model_key"], []).append(row)
            elif ident["identity_reason"] != _EMPTY_NAME and ident["published"] not in self._unmatched:
                self._unmatched.append(ident["published"])
        self._model_rows, self._lane_rows, shared = {}, {}, {}
        for name, lane in lanes.items():
            if harness_model[name] not in shared:
                harness, model = harness_model[name]
                slugs = [lanes[n]["model"] for n in lanes
                         if harness_model[n] == harness_model[name]]
                shared[harness_model[name]] = [row for row in claimed.get(model, ())
                                               if _runs(harness, slugs, _stated_effort(row))]
            self._model_rows[name] = shared[harness_model[name]]
            effort = _stated_effort(lane)
            self._lane_rows[name] = [row for row in shared[harness_model[name]]
                                     if effort is not None and _stated_effort(row) == effort]
        model_lanes, lane_lanes = {}, {}
        for name in sorted(lanes):
            for row in self._model_rows[name]:
                model_lanes.setdefault(id(row), set()).add(name)
            for row in self._lane_rows[name]:
                lane_lanes.setdefault(id(row), set()).add(name)
        self._records = []
        for row, ident in identified:
            held = sorted(lane_lanes.get(id(row), ()))
            self._records.append(dict(
                ident, row=row, effort=_stated_effort(row) or UNKNOWN_EFFORT,
                model_lanes=sorted(model_lanes.get(id(row), ())), lanes=held, attributed=bool(held)))

    def __eq__(self, other):
        """Equal rows attributed alike: the wizard compares its state by value."""
        if not isinstance(other, LaneEvidence):
            return NotImplemented
        return ((self._available, self._model_rows, self._lane_rows, self._unmatched)
                == (other._available, other._model_rows, other._lane_rows, other._unmatched))

    @property
    def available(self) -> bool:
        """False for no rows at all (None), as distinct from none that matched."""
        return self._available

    def model_rows(self, lane: str) -> List[dict]:
        """This Lane's Model's rows that state no effort or one its Harness
        runs for that Model (`offers_effort`; no adapter runs every effort):
        Claude Code's Opus at xhigh is no row of agy's. [] for an unknown Lane."""
        return list(self._model_rows.get(lane, ()))

    def lane_rows(self, lane: str) -> List[dict]:
        """This Lane's evidence: the part of `model_rows` measured at its own
        effort, the one attribution rule. An unstated effort (None, empty or
        `unknown`) is no Lane's."""
        return list(self._lane_rows.get(lane, ()))

    def records(self) -> List[dict]:
        """One record per dict row, in input order, for display: the row, the
        identity its printed name gives it (`identify`), the effort it states
        (`unknown` for none), `model_lanes` (the Lanes whose `model_rows` hold
        it), `lanes` (exactly the Lanes whose `lane_rows` hold it) and
        `attributed` (whether any Lane does)."""
        return [dict(rec, candidates=list(rec["candidates"]), lane_models=list(rec["lane_models"]),
                     model_lanes=list(rec["model_lanes"]), lanes=list(rec["lanes"]))
                for rec in self._records]

    def identify(self, name: Optional[str]) -> dict:
        """The Model a printed name names: the identity part of the record a
        row printing `name` would get. `published` and `key` (the name and its
        normalized form), `identity` (`resolved` or `unresolved`),
        `identity_reason` (None, `empty published name`, `no catalog model` or
        `conflicting identity`), `candidates` (the display names it could
        mean), `model_key` (the Model, the key it is grouped by), `lane_model`
        (its display name) and `lane_models` (every Lane model string it is
        run as)."""
        return self._identify([name])

    def unmatched(self) -> List[str]:
        """The printed names no Model answers to, each once, first seen first."""
        return list(self._unmatched)

    def _identify(self, printed):
        """The first printed name that names one Model decides; failing that,
        the first that names two says why, and else the first name at all."""
        first = conflict = None
        for name in printed:
            key = _normalize_name(name) if isinstance(name, str) else ""
            if not key:
                continue
            found = self._names.get(key) or set()
            if len(found) == 1:
                model = next(iter(found))
                return {"published": name, "key": key, "identity": "resolved",
                        "identity_reason": None, "candidates": [self._display[model]],
                        "model_key": model, "lane_model": self._display[model],
                        "lane_models": sorted(self._spellings[model])}
            first = first or (name, key, _NO_MODEL, [])
            if found and conflict is None:
                conflict = (name, key, _CONFLICT, sorted(self._display[m] for m in found))
        name, key, reason, candidates = conflict or first or (
            next((n for n in printed if n is not None), None), "", _EMPTY_NAME, [])
        return {"published": name, "key": key, "identity": "unresolved",
                "identity_reason": reason, "candidates": candidates, "model_key": None,
                "lane_model": None, "lane_models": []}


def _runs(harness, models, effort):
    """Whether a Harness runs `effort` for a Model it carries as `models`; an
    unstated effort is the Model's context everywhere."""
    if effort is None:
        return True
    adapter = harnesses.get(harness)
    if adapter is None:
        return True
    return any(adapter.offers_effort(model, effort) for model in models)
