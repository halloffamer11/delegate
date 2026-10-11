#!/usr/bin/env python3
"""lane_evidence.py — which benchmark rows belong to which Lane.

The catalog keys on slugs; a leaderboard prints a slug or a display name. This
is the one reconciliation of the two, used by `catalog.validate_lanes` (a
`published_as` entry may not name another lane's model) and by the benchmark
readers: `LaneEvidence` for carry, the Tier proposal, the wizard and the
benchmark page, the resolvers for `bench`. Split out of catalog.py (ticket 26)
as `published_names`. It imports only `harnesses`, which decides what one
Model is and which efforts it runs, never the spelling.
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


def resolve_published_model(published, lanes_doc, effort=None):
    """The lane model that a source's printed model name denotes, or None.

    A `published_as` entry is consulted first: it is the human's own correction,
    and it is the only way across a gap formatting cannot bridge
    (`Fable 5.1` -> `claude-fable-5-1`). It cannot contradict the derived rule,
    because `validate_lanes` refuses an entry that names a model another lane
    runs — an entry that could redirect one lane's rows onto another lane is a
    typo, never an intention.

    Failing an entry, the name has to differ from a lane model by formatting
    alone — case and the -_. separators — reaching past the effort suffix some
    of our slugs carry (`gemini-3.8-flash-high`). Anything looser would be a
    guess about which model a leaderboard meant, and a wrong guess switches a
    working lane off. A name that two lane models could equally denote therefore
    resolves to neither, and a name no lane runs resolves to None: the
    leaderboards are full of models that are nobody's lane.

    The one exception is a family of lane models that differ only by their
    effort suffix, which is how agy names one model at several efforts
    (`gemini-3.8-flash-high`, `gemini-3.8-flash-medium`). A row that states its
    `effort` resolves to the one family member carrying that effort; without
    an effort, or with an effort no member carries, it still resolves to
    neither (ticket 19).
    """
    key = normalize_name(published)
    if not key:
        return None
    explicit = published_as_map(lanes_doc)
    if key in explicit:
        return explicit[key]
    candidates = set()
    for lane in (lanes_doc.get("lanes") or {}).values():
        if not isinstance(lane, dict):
            continue
        model = lane.get("model")
        if not isinstance(model, str) or not model.strip():
            continue
        normalized = normalize_name(model)
        base, _effort = strip_effort_suffix(normalized)
        if key in (normalized, base):
            candidates.add(model)
    if len(candidates) == 1:
        return candidates.pop()
    if effort and len(candidates) > 1:
        at_effort = {m for m in candidates
                     if strip_effort_suffix(normalize_name(m))[1] == str(effort)}
        if len(at_effort) == 1:
            return at_effort.pop()
    return None


def resolve_published_models(published, lanes_doc, effort=None):
    """Every lane model a source's printed name denotes: one per harness.

    `resolve_published_model` answers for the catalog as one pool, so when two
    harnesses run one model it can name only one of them: with Opus on agy
    (`claude-opus-5-5-high`) beside Claude Code's (`claude-opus-5-5`), a row at
    effort high resolves to the agy member and Claude Code's lanes lose it. A
    published score is the model's, whichever harness runs it, so here the same
    rule is applied inside each harness and every harness that runs the model
    gets the row (any-harness ticket 31). An explicit `published_as` still
    names one model.
    """
    key = normalize_name(published)
    if not key:
        return []
    explicit = published_as_map(lanes_doc)
    if key in explicit:
        return [explicit[key]]
    by_harness = {}
    for name, lane in (lanes_doc.get("lanes") or {}).items():
        if isinstance(lane, dict):
            by_harness.setdefault(lane.get("harness"), {})[name] = lane
    out = []
    for lanes in by_harness.values():
        model = resolve_published_model(published, {"lanes": lanes}, effort=effort)
        if model is not None and model not in out:
            out.append(model)
    return out


# A source that did not state an effort has not said which Lane it measured.
UNSTATED_EFFORTS = (None, "", "unknown")


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
        # A printed name names a Model when, normalized, it is a `published_as`
        # entry (the Model of the Lane carrying it), a Lane's Model identity or
        # its model string. A name two Models answer to names neither.
        names = {}
        for name, lane in lanes.items():
            spellings = [model_of[name][1], lane["model"]] + [
                entry for entry in lane.get("published_as") or () if isinstance(entry, str)]
            for key in filter(None, map(normalize_name, spellings)):
                names.setdefault(key, set()).add(model_of[name][1])
        claimed, self._unmatched = {}, []
        for row in rows or ():
            if not isinstance(row, dict):
                continue
            printed = row.get("model")
            found = names.get(normalize_name(printed)) or set()
            if len(found) == 1:
                claimed.setdefault(next(iter(found)), []).append(row)
            elif isinstance(printed, str) and printed.strip() and printed not in self._unmatched:
                self._unmatched.append(printed)
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

    def unmatched(self) -> List[str]:
        """The printed names no Model answers to, each once, first seen first."""
        return list(self._unmatched)


def _runs(harness, models, effort):
    """Whether a Harness runs `effort` for a Model it carries as `models`; an
    unstated effort is the Model's context everywhere."""
    if effort is None:
        return True
    adapter = harnesses.get(harness)
    if adapter is None:
        return True
    return any(adapter.offers_effort(model, effort) for model in models)
