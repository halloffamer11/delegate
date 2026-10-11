#!/usr/bin/env python3
"""tier_lines.py — bulk Tier lines: the benchmark page's decisions, pasted into
the wizard (ticket 27 of the redesign). The parser and the summary line, for
the wizard (`setup_tui`) and `setup.py --plain --tiers-from`; applying the
lines is the Draft's (`catalog_draft.CatalogDraft.apply`, deepening F). Split
out of catalog.py (ticket 26).
"""

TIER_LINE_VALUES = {"1": 1, "2": 2, "3": 3, "4": 4, "off": "off"}


def parse_tier_lines(text, lanes_doc):
    """Read `<lane> <1-4|off>` lines, as the benchmark page's "Copy as lines"
    writes them. The one parser for the review page's `v` and for
    `setup.py --tiers-from`.

    Returns a dict: `decided` {lane: tier or "off"} in the order first named,
    where the last line for a lane wins; `repeated`, the lanes named more than
    once; `unknown`, names that are no lane in this catalog; `bad`, the line
    numbers that are not a name and one of 1-4 or off; and `refused`, ultra
    lanes a line tried to carry, since an ultra lane is never carried
    (ticket 15). Blank lines are skipped.
    """
    lanes = (lanes_doc or {}).get("lanes") or {}
    out = {"decided": {}, "repeated": [], "unknown": [], "bad": [], "refused": []}
    for number, raw in enumerate((text or "").splitlines(), 1):
        parts = raw.split()
        if not parts:
            continue
        if len(parts) != 2 or parts[1].lower() not in TIER_LINE_VALUES:
            out["bad"].append(number)
            continue
        name, value = parts[0], TIER_LINE_VALUES[parts[1].lower()]
        if name not in lanes:
            if name not in out["unknown"]:
                out["unknown"].append(name)
            continue
        if value != "off" and (lanes[name] or {}).get("effort") == "ultra":
            if name not in out["refused"]:
                out["refused"].append(name)
            continue
        if name in out["decided"] and name not in out["repeated"]:
            out["repeated"].append(name)
        out["decided"][name] = value
    return out


def unnamed_carried(parsed, carried):
    """The carried lanes a set of lines does not name. They go off: "if it's not
    in the tier list, it's not used" (the user, 2026-09-12; ticket 28).

    Lines that name no lane in the catalog decide nothing, so they switch nothing
    off: a clipboard holding the wrong text must not empty the catalog."""
    if not parsed["decided"]:
        return []
    return [name for name in carried if name not in parsed["decided"]]


def tier_lines_summary(parsed, dropped=()):
    """The one line that says what a set of tier lines did: how many lanes took
    a tier, how many went off by a line, how many carried lanes went off because
    no line named them (`dropped`), then any lane named twice, any name the
    catalog does not know, and any line not read."""
    decided = parsed["decided"]
    tiers = sum(1 for value in decided.values() if value != "off")
    if decided:
        parts = [f"{tiers} took a tier", f"{len(decided) - tiers} went off",
                 f"{len(dropped)} not named, so off"]
    else:
        parts = ["no line names a lane in this catalog, so nothing changed"]
    if parsed["repeated"]:
        parts.append("named twice, last line kept: " + ", ".join(parsed["repeated"]))
    if parsed["unknown"]:
        parts.append("unknown, ignored: " + ", ".join(parsed["unknown"]))
    if parsed["refused"]:
        parts.append("ultra, never carried, ignored: " + ", ".join(parsed["refused"]))
    if parsed["bad"]:
        parts.append("not <lane> <1-4|off>, ignored: line " + ", ".join(str(n) for n in parsed["bad"]))
    return "Lines: " + "; ".join(parts) + "."
