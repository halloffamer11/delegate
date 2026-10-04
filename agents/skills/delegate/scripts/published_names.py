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


def resolve_effort_rows(lanes_doc, effort_rows):
    """Returns (rows keyed by catalog model, published names that name no lane).

    A source prints a model however it pleases: `gpt-5.6-luna` from SWE Refactor
    Bench, `GPT-6 Astra` from Terminal-Bench and Artificial Analysis. Every
    comparison below is against `lane["model"]`, so each row is re-keyed to the
    lane model its printed name denotes, and the catalog owns that mapping
    (`published_names.resolve_published_model`). A row naming no lane model is dropped
    rather than reported per lane: the leaderboards carry GLM-5.3, Opus 4.8,
    Sonnet 5 and a dozen others that are nobody's lane, and one line naming them
    all is what a human needs to spot a `published_as` they still owe us.
    """
    resolved, unmatched = [], []
    for row in effort_rows or []:
        if not isinstance(row, dict):
            continue
        models = resolve_published_models(row.get("model"), lanes_doc, effort=row.get("effort"))
        if not models:
            name = row.get("model")
            if isinstance(name, str) and name.strip() and name not in unmatched:
                unmatched.append(name)
            continue
        for model in models:
            if model == row.get("model"):
                resolved.append(row)
            else:
                copied = dict(row)
                copied["model"] = model
                resolved.append(copied)
    return resolved, unmatched
