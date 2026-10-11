#!/usr/bin/env python3
"""lane_evidence.py — which benchmark rows belong to which Lane.

The catalog keys on slugs; a leaderboard prints a slug or a display name. This
is the one reconciliation of the two, used by `catalog.validate_lanes` (a
`published_as` entry may not name another lane's model) and by every
benchmark reader through `LaneEvidence`: carry, the Tier proposal, the wizard,
the report, model inspection and the benchmark page. Split out of catalog.py
(ticket 26) as `published_names`. It imports only `harnesses`, which decides
what one Model is and which efforts it runs, never the spelling.
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnesses  # noqa: E402

# Benchmark sources print a model however they please: some publish the slug a
# harness accepts (`gpt-5.6-luna`), some a display name (`GPT-6 Astra`,
# `Fable 5.1`). The catalog keys on slugs, so a consumer of published rows has
# to reconcile the two. That mapping is local knowledge — which published name
# denotes which of our lane models — so it lives here, beside the lane, where a
# human can read and correct it: the optional lane field `published_as`.
NORM_SEP = re.compile(r"[-_. ]+")
# Longest first, so `-xhigh` is not read as `-high`. Every effort in EFFORTS
# belongs here, so the list is made from it: a source names a row
# `gpt-6-astra-max` as readily as `gpt-6-astra-high`, and while `-max` and
# `-ultra` were missing such a row matched no lane model at all and the figure
# was dropped (ticket 17).
MODEL_EFFORT_SUFFIXES = tuple((f"-{effort}", effort) for effort in harnesses.EFFORTS_LONGEST_FIRST)


def normalize_name(value):
    """Lower-case, with the -_. and space separators collapsed to one hyphen."""
    if value is None:
        return ""
    return NORM_SEP.sub("-", str(value).strip().lower()).strip("-")


def strip_effort_suffix(model):
    """Splits a trailing effort off a model slug: gemini-3.8-flash-high -> (base, 'high')."""
    for suffix, effort in MODEL_EFFORT_SUFFIXES:
        if model.endswith(suffix):
            return model[: -len(suffix)], effort
    return model, None


def published_as_map(lanes_doc):
    """{normalized published name: lane model} from every lane's published_as."""
    out = {}
    for lane in (lanes_doc.get("lanes") or {}).values():
        if not isinstance(lane, dict):
            continue
        for name in lane.get("published_as") or []:
            key = normalize_name(name)
            if key:
                out[key] = lane.get("model")
    return out


# A source that did not state an effort has not said which Lane it measured.
# `unknown` is the key such a row's effort gets, so it is never dropped for
# being unlabelled, and it matches no Lane, so it is never attributed for it.
UNKNOWN_EFFORT = "unknown"
UNSTATED_EFFORTS = (None, "", UNKNOWN_EFFORT)
EMPTY_NAME, NO_MODEL, CONFLICT = "empty published name", "no catalog model", "conflicting identity"


def _stated_effort(row):
    """The effort a row (or a Lane) states, or None when it states none."""
    effort = row.get("effort")
    return None if effort in UNSTATED_EFFORTS else str(effort)


def _model_identity(lane):
    """What "one Model" means across harnesses: the harness's family base,
    normalized, so agy's `claude-opus-5-5-high` and Claude Code's
    `claude-opus-5-5` are one Model, and a codex slug ending in an effort word
    is a Model of its own."""
    lane = lane or {}
    return normalize_name(harnesses.family(lane.get("harness"), lane.get("model") or "")[0])


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
        lanes = {name: lane for name, lane in ((lanes_doc or {}).get("lanes") or {}).items()
                 if isinstance(lane, dict) and isinstance(lane.get("model"), str)
                 and lane["model"].strip()}
        model_of = {name: (lane.get("harness"), _model_identity(lane)) for name, lane in lanes.items()}
        # Each Model's display name: a Lane's model string that is the Model's
        # whole name (`claude-opus-5-5`, the exact spelling first), else the
        # harness family base (`gemini-3.8-flash`). It never depends on a row's
        # effort, so one Model draws as one sweep.
        self._display, self._spellings = {}, {}
        for name, lane in lanes.items():
            model = model_of[name][1]
            self._spellings.setdefault(model, set()).add(lane["model"])
        for model in self._spellings:
            members = [lanes[n] for n in lanes if model_of[n][1] == model]
            whole = ([m["model"] for m in members if m["model"] == model]
                     + [m["model"] for m in members if normalize_name(m["model"]) == model])
            self._display[model] = whole[0] if whole else harnesses.family(
                members[0].get("harness"), members[0]["model"])[0]
        # A printed name names a Model when, normalized, it is a `published_as`
        # entry (the Model of the Lane carrying it), a Lane's Model identity or
        # its model string. A name two Models answer to names neither.
        self._names = {}
        for name, lane in lanes.items():
            spellings = [model_of[name][1], lane["model"]] + [
                entry for entry in lane.get("published_as") or () if isinstance(entry, str)]
            for key in filter(None, map(normalize_name, spellings)):
                self._names.setdefault(key, set()).add(model_of[name][1])
        claimed, identified, self._unmatched = {}, [], []
        for row in rows or ():
            if not isinstance(row, dict):
                continue
            ident = self._identify(_printed_names(row))
            identified.append((row, ident))
            if ident["model_key"] is not None:
                claimed.setdefault(ident["model_key"], []).append(row)
            elif ident["identity_reason"] != EMPTY_NAME and ident["published"] not in self._unmatched:
                self._unmatched.append(ident["published"])
        self._model_rows, self._lane_rows, shared = {}, {}, {}
        for name, lane in lanes.items():
            if model_of[name] not in shared:
                harness, model = model_of[name]
                slugs = [lanes[n]["model"] for n in lanes if model_of[n] == model_of[name]]
                shared[model_of[name]] = [row for row in claimed.get(model, ())
                                          if _runs(harness, slugs, _stated_effort(row))]
            self._model_rows[name] = shared[model_of[name]]
            effort = _stated_effort(lane)
            self._lane_rows[name] = [row for row in shared[model_of[name]]
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
            key = normalize_name(name) if isinstance(name, str) else ""
            if not key:
                continue
            found = self._names.get(key) or set()
            if len(found) == 1:
                model = next(iter(found))
                return {"published": name, "key": key, "identity": "resolved",
                        "identity_reason": None, "candidates": [self._display[model]],
                        "model_key": model, "lane_model": self._display[model],
                        "lane_models": sorted(self._spellings[model])}
            first = first or (name, key, NO_MODEL, [])
            if found and conflict is None:
                conflict = (name, key, CONFLICT, sorted(self._display[m] for m in found))
        name, key, reason, candidates = conflict or first or (
            next((n for n in printed if n is not None), None), "", EMPTY_NAME, [])
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
