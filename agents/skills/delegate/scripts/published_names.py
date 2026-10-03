#!/usr/bin/env python3
"""published_names.py — which lane model a benchmark's printed name denotes.

The catalog keys on slugs; a leaderboard prints a slug or a display name. This
is the one reconciliation of the two, used by `catalog.validate_lanes` (a
`published_as` entry may not name another lane's model) and by the benchmark
readers (`bench`, `tier_proposal`). Split out of catalog.py (ticket 26).
"""
import os
import re
import sys

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
