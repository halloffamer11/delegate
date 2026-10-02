"""The harness registry: one adapter per harness, and the one list of them.

Adding a harness means adding one module here (see `base.Harness`) and one
entry in REGISTRY. Everything else in delegate iterates the registry or asks
`get(name)`, and no other script names a harness.
"""
import shutil

from .base import EFFORTS, Harness  # noqa: F401
from . import agy, claude, codex, grok

REGISTRY = (claude.HARNESS, codex.HARNESS, agy.HARNESS, grok.HARNESS)
NAMES = tuple(h.name for h in REGISTRY)
_BY_NAME = {h.name: h for h in REGISTRY}


def get(name):
    """The adapter for a harness name, or None for a name no module defines."""
    return _BY_NAME.get(name)


def cli_installed(name):
    """Whether this harness's CLI is on PATH, by the binary its adapter names."""
    h = get(name)
    return h is not None and shutil.which(h.binary) is not None


def discovery_order():
    """Harnesses with a model list first, then those whose models the catalog
    names, each group in registry order."""
    return tuple(h.name for h in sorted(REGISTRY, key=lambda h: h.catalog_models))


def family(harness, slug):
    """(base, effort) for a slug on a harness; (slug, None) for a harness
    whose effort is not part of the slug or a name no module defines."""
    h = get(harness)
    return h.family(slug) if h is not None else (slug or "", None)


def slug_family(slug):
    """(base, effort) for a slug of unknown harness: the first family any
    effort-in-slug harness finds in it, else (slug, None)."""
    for h in REGISTRY:
        if h.effort_in_slug:
            base, effort = h.family(slug)
            if effort is not None:
                return base, effort
    return slug or "", None
