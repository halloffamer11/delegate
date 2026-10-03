"""The harness registry: one adapter per harness, and the one list of them.

Adding a harness means adding one module here (see `base.Harness`) and one
entry in REGISTRY. Everything else in delegate iterates the registry or asks
`get(name)`, and no other script names a harness. The Lane name
`<model-effort>@<harness>` is spelled and split here too (`lane_name`,
`split_lane`), the lowest module every script imports.
"""
from .base import EFFORTS, EFFORTS_LONGEST_FIRST, Harness  # noqa: F401
from . import agy, claude, codex, grok, kiro

REGISTRY = (claude.HARNESS, codex.HARNESS, agy.HARNESS, grok.HARNESS, kiro.HARNESS)
NAMES = tuple(h.name for h in REGISTRY)
_BY_NAME = {h.name: h for h in REGISTRY}


def get(name):
    """The adapter for a harness name, or None for a name no module defines."""
    return _BY_NAME.get(name)


def cli_installed(name):
    """Whether this harness's CLI is on PATH (`Harness.installed`); False for a
    name no module defines."""
    h = get(name)
    return h is not None and h.installed()


def installed(names=None):
    """The harnesses, of NAMES or the ones given, whose CLI is on PATH."""
    return {name for name in (NAMES if names is None else names) if cli_installed(name)}


def constraint_error(name):
    """Why a user's harness constraint cannot be applied, or None.

    The constraint (`/delegate agy <task>`, or a standing "use agy for all
    delegated work") restricts ranking to one harness's Lanes. Only the user
    states one; a harness that is unknown or whose CLI is not on PATH is
    refused, naming the installed ones.
    """
    if name in NAMES and cli_installed(name):
        return None
    present = ", ".join(sorted(installed())) or "none"
    why = "is not a harness" if name not in NAMES else "is not installed"
    return f"harness '{name}' {why}; installed: {present}"


def vendor_words():
    """The first words of the harnesses' own vendors' slugs: words that name a
    whole family of models rather than one (`gpt`, `gemini`)."""
    return tuple(h.vendor for h in REGISTRY if h.vendor)


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


def lane_name(stem, effort, harness):
    """`<stem>-<effort>@<harness>`: the one spelling of a Lane name. `effort`
    None means `stem` already carries it (`sol-high`)."""
    model_effort = stem if effort is None else f"{stem}-{effort}"
    return f"{model_effort}@{harness}"


def split_lane(name):
    """(model_effort, harness) for a Lane name: `("sol-high", "codex")` from
    `sol-high@codex`. The harness is what follows the last `@`, the suffix the
    catalog checks; a name with no `@` is (name, None)."""
    if "@" not in (name or ""):
        return name or "", None
    model_effort, harness = name.rsplit("@", 1)
    return model_effort, harness
