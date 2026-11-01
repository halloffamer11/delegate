#!/usr/bin/env python3
"""The benchmark page: the plot and tier matrix the setup wizard opens with `o`.

One person opens this from the tiers page, once every few months, to decide
which lanes to carry and what tier each deserves. It is one screen with no
scrolling: a score-against-cost plot of one board, one line per model through
its efforts, beside a resizable matrix of models by efforts that sets the
tiers. Hovering a cell lights its dot and a dot lights its cell.

`assets/bench_page.html` is the page; this module fills its data script with
`plot_data`. Every decision in the data (the kind of each point, the model a
lane belongs to, the pre-screen's proposals) is made here, from `bench`; the
page only draws it. The wizard serves it live through `page_link.py`; written
to a file it is a copy whose tier lines are pasted with the review page's `v`.
"""
import hashlib
import html
import json
import math
import os
from collections import defaultdict

import bench
import carry
from bench import carry_reason, effort_rank, lane_order
from harnesses import EFFORTS
import harnesses

# A published sweep runs the API's own enum, which starts below the lowest
# effort a lane can be set to. `none` is a real row and the cheapest one, so a
# model's sweep is drawn from it; the pre-screen still never lets it dominate.
EFFORT_ORDER = ("none",) + EFFORTS

NO_LANE = "no lane"
NOT_CARRIED = "<span class='quiet'>no</span>"

# Provenance the page must not let look like a verified figure. `uncertain`
# rows are excluded from the pre-screen's rule; `self-reported` rows are not,
# which is why both are drawn the same way and the legend says so.
WEAK_PROVENANCE = ("self-reported",)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
SOURCES_PATH = bench.SOURCES_PATH
BOARDS_PATH = bench.BOARDS_PATH
PAGE_PATH = os.path.join(ASSETS, "bench_page.html")
DATA_SLOT = "/*DATA*/null"

# Said in place of a description for a board `assets/boards.json` does not
# cover. A description is quoted from the source's own methodology page, never
# written from memory, so a board nobody has fetched a page for says so.
NO_ABOUT = ("No description on file for this board: nobody has fetched its source's "
            "methodology page into assets/boards.json.")
ABOUT_FIELDS = bench.ABOUT_FIELDS

# The four kinds of point on a plot. A lane is a thing the reader pays for
# and can dispatch to; the rest is context, and the distinction has to survive
# at a glance, so each kind has its own shape and fill, not just a colour.
LANE, LANE_OFF, OWN_OTHER, COMPARATOR = "lane", "lane_off", "own_other", "comparator"


# --- small formatting helpers ------------------------------------------------

def _esc(value):
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def _num(value):
    """A real number or None; bools are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return float(value)


def _fmt_score(score, unit=None):
    if score is None:
        return "—"
    text = f"{score:.1f}"
    return text + "%" if unit == "%" else text


def _fmt_delta(delta, unit=None):
    if delta is None:
        return "—"
    if abs(delta) < 0.05:
        return "0.0" + ("%" if unit == "%" else "")
    sign = "+" if delta > 0 else "−"
    return f"{sign}{abs(delta):.1f}" + ("%" if unit == "%" else "")


def _fmt_money(value):
    """$2,269 above a hundred, $19.1 above ten, $2.9 below: the precision a
    reader can use at each size, and never `1.56e+03`."""
    value = _num(value)
    if value is None:
        return "—"
    if abs(value) >= 100:
        return f"${value:,.0f}"
    if abs(value) >= 10:
        return f"${value:.1f}"
    return f"${value:.2f}".rstrip("0").rstrip(".")


def _fmt_money_delta(delta):
    if delta is None:
        return "—"
    if abs(delta) < 0.005:
        return "$0"
    sign = "+" if delta > 0 else "−"
    return sign + _fmt_money(abs(delta))


def _fmt_pct_change(old, new):
    if not old:
        return ""
    change = (new - old) / old * 100
    if abs(change) < 0.5:
        return "(same)"
    sign = "+" if change > 0 else "−"
    return f"({sign}{abs(change):.0f}%)"


def _effort_key(effort):
    try:
        return (EFFORT_ORDER.index(effort), effort)
    except ValueError:
        return (len(EFFORT_ORDER), str(effort))


def _effort_desc(effort):
    """Most effort first, a stranger last: the order every table lists a
    model's efforts in (ticket 26)."""
    try:
        return (0, -EFFORT_ORDER.index(effort), "")
    except ValueError:
        return (1, 0, str(effort))


def _short_model(published, lane_model):
    """The name a point wears. Our models wear the slug the wizard shows;
    a comparator wears the name the source printed."""
    return lane_model or published or "?"


# --- reading the catalog -----------------------------------------------------

def _lanes(lanes_doc):
    lanes = (lanes_doc or {}).get("lanes") or {}
    return {name: lane for name, lane in lanes.items() if isinstance(lane, dict)}


def _lane_at(lanes_doc, model, effort):
    """The lane names running this model at this effort, sorted."""
    return sorted(name for name, lane in _lanes(lanes_doc).items()
                  if lane.get("model") == model and lane.get("effort") == effort)


def _lanes_of_model(lanes_doc, model):
    return sorted(name for name, lane in _lanes(lanes_doc).items()
                  if lane.get("model") == model)


def _proposals(lanes_doc, effort_rows):
    """The wizard's own pre-screen verdicts, so the page marks exactly what
    the wizard marks. Two implementations of one rule would eventually
    disagree in front of the person checking the arithmetic.

    Returns {name: carry.decision}. `effort_rows is None` (unavailable evidence)
    is distinct from an empty proposal.
    """
    if not _lanes(lanes_doc):
        return {}
    try:
        return carry.decisions(lanes_doc, effort_rows)
    except Exception:
        return {}


def _proposed_off(proposals):
    """{lane name: display reason} for lanes the pre-screen would switch off on
    the strength of the data, not lanes already recorded off or never carried."""
    return {name: carry_reason(decision) for name, decision in (proposals or {}).items()
            if decision.get("kind") == carry.KIND_DOMINATED}


def _decision_for(proposals, names):
    """The first dominated decision among `names`, else None."""
    for name in names or ():
        decision = (proposals or {}).get(name)
        if decision and decision.get("kind") == carry.KIND_DOMINATED:
            return decision
    return None


def _load_sources():
    return bench.load_sources()


def _load_boards():
    return bench.load_boards()


def board_about(source, benchmark, boards=None):
    """What one board measures, quoted from its source's methodology page."""
    return bench.board_about(source, benchmark, boards=boards)


def _cost_basis(source_meta):
    """What a dollar on this source's axis is. Costs are not comparable
    across sources, so every plot says what its own cost is."""
    cost = (source_meta or {}).get("cost") or ""
    if cost == "usd_per_task":
        return "cost per task"
    if cost:
        return "cost of the whole run"
    return "cost as published"


# --- annotating rows ---------------------------------------------------------

def _annotate(effort_rows, lanes_doc, proposals):
    """Every row, with the lane model its printed name denotes, the kind of
    point it makes, the lane it belongs to (if one runs that model at that
    effort), whether its provenance is weak, and which effort dominates it.

    Identity, standing, cost basis and version come from `bench.evidence_records`
    so the HTML table is the same records model inspection prints.
    """
    off = _proposed_off(proposals)
    annotated = []
    for rec in bench.evidence_records(effort_rows, lanes_doc):
        row = rec.get("row") if isinstance(rec.get("row"), dict) else {}
        item = dict(row)
        lane_model = rec.get("lane_model")
        item["_lane_model"] = lane_model
        # every harness's lanes of the model, not only the grouping one's
        item["_model_lanes"] = sorted({name for model in rec.get("lane_models") or ()
                                       for name in _lanes_of_model(lanes_doc, model)})
        item["_lanes"] = list(rec.get("lanes") or [])
        item["_weak"] = bool(row.get("uncertain")) or row.get("provenance") in WEAK_PROVENANCE
        item["_score"] = _num(row.get("score"))
        item["_cost"] = _num(row.get("cost_usd"))
        item["_identity"] = rec.get("identity")
        item["_identity_reason"] = rec.get("identity_reason")
        item["_version"] = rec.get("version")
        item["_standing"] = rec.get("standing")
        item["_cost_basis"] = rec.get("cost_basis")
        item["_direction"] = rec.get("direction")
        item["_attributed"] = rec.get("attributed")
        if item["_lanes"]:
            item["_kind"] = LANE_OFF if any(name in off for name in item["_lanes"]) else LANE
        elif lane_model:
            item["_kind"] = OWN_OTHER
        else:
            item["_kind"] = COMPARATOR
        decision = _decision_for(proposals, item["_lanes"])
        item["_off_reason"] = carry_reason(decision) if decision else None
        item["_off_kind"] = decision.get("kind") if decision else None
        item["_off_source"] = decision.get("source") if decision else None
        item["_off_competitor"] = decision.get("competitor") if decision else None
        annotated.append(item)
    # Domination is judged on the lane model, exactly as the pre-screen judges
    # it, so two printed names for one lane model compare against each other.
    keyed = []
    for item in annotated:
        row = dict(item)
        row["model"] = item["_lane_model"] or item.get("model")
        keyed.append(row)
    certain = carry.certain_effort_rows(keyed)
    families = carry.families(lanes_doc)
    comparable = {id(row) for row in certain}
    for item, row in zip(annotated, keyed):
        other = carry.dominating_row(row, certain, families) if id(row) in comparable else None
        item["_dominated_by"] = other["effort"] if other else None
    return annotated


def _model_key(item):
    return item["_lane_model"] or item.get("model") or "?"


def _group_by_model(items):
    groups = defaultdict(list)
    for item in items:
        groups[_model_key(item)].append(item)
    for rows in groups.values():
        rows.sort(key=lambda r: _effort_desc(r.get("effort")))
    return groups


def _ordered_models(groups):
    """Our models first, then comparators, each by best score, high first."""
    def key(model):
        rows = groups[model]
        ours = any(r["_lane_model"] for r in rows)
        best = max((r["_score"] for r in rows if r["_score"] is not None), default=-1.0)
        return (0 if ours else 1, -best, model)
    return sorted(groups, key=key)


def _plotted(item):
    return item["_score"] is not None and item["_cost"] is not None and item["_cost"] > 0


# --- the header glyphs ---------------------------------------------------------

# The same marks the script draws, for the verdict line, which has to read with
# the script off. A CSS variable keeps each theme-aware; the fallback keeps it
# legible out of the page.
GROUND = "var(--surface, #ffffff)"
ACCENT = "var(--accent, #2b5fc4)"
OFF = "var(--off, #c63d33)"


def _finding(groups, order, off_points, unit):
    """The sentence a sighted reader takes from the shape, for the caption
    and the image label: the board's top, the best lane you carry, and every
    lane the pre-screen would switch off, with its arithmetic."""
    every = [r for rows in groups.values() for r in rows]
    if not every:
        return "Nothing to compare."
    top = max(every, key=lambda r: (r["_score"], -r["_cost"]))
    sentences = [f"Top of the board: {_short_model(top.get('model'), top['_lane_model'])} "
                 f"{top.get('effort')} at {_fmt_score(top['_score'], unit)} for {_fmt_money(top['_cost'])}."]
    carried = [r for r in every if r["_kind"] in (LANE, LANE_OFF)]
    if carried:
        best = max(carried, key=lambda r: (r["_score"], -r["_cost"]))
        if best is not top:
            sentences.append(f"Best lane you carry: {', '.join(best['_lanes'])} at "
                             f"{_fmt_score(best['_score'], unit)} for {_fmt_money(best['_cost'])}.")
        else:
            sentences.append(f"That is your lane {', '.join(best['_lanes'])}.")
    else:
        sentences.append("No lane you carry is measured on this board at the effort it runs.")
    for r in off_points:
        model = _model_key(r)
        other = next((o for o in groups[model] if o.get("effort") == r["_dominated_by"]), None)
        if other is None:
            sentences.append(f"Proposed off: {', '.join(r['_lanes'])}, {r['_off_reason']}.")
            continue
        ds = r["_score"] - other["_score"]
        dc = r["_cost"] - other["_cost"]
        if abs(ds) < 0.05:
            scores = f"scores the same as {other.get('effort')}"
        else:
            scores = f"scores {_fmt_score(abs(ds), unit)} less than {other.get('effort')}"
        if abs(dc) < 0.005:
            costs = "costs the same"
        else:
            costs = f"costs {_fmt_money(abs(dc))} more {_fmt_pct_change(other['_cost'], r['_cost'])}"
        sentences.append(f"Proposed off: {', '.join(r['_lanes'])}. {r.get('effort')} {scores} and {costs}.")
    return " ".join(sentences)


NOTHING_TO_DRAW = ("No row on this board carries both a score and a positive cost, so there is "
                   "nothing to draw. The rows are in its table.")


def _boards(items):
    """{(source, benchmark): rows}, ordered so the board where a decision can
    be made comes first: most carried lanes measured at the effort they run,
    then a composite index before its components, then most of our models."""
    boards = defaultdict(list)
    for r in items:
        boards[(r.get("source") or "?", r.get("benchmark") or "?")].append(r)

    def board_key(key):
        rows = boards[key]
        return (-sum(1 for r in rows if r["_kind"] in (LANE, LANE_OFF)),
                not any(r.get("composite") for r in rows),
                -sum(1 for r in rows if r["_lane_model"]), key)

    return [(key, boards[key]) for key in sorted(boards, key=board_key)]


def _board_facts(source, benchmark, items, source_meta):
    """What one board is and what it says, shared by the plot's data and its
    table in the evidence section."""
    plotted = [r for r in items if _plotted(r)]
    groups = _group_by_model(plotted)
    unit = next((r.get("score_unit") for r in items if r.get("score_unit")), None)
    observed = sorted({r.get("observed") for r in items if r.get("observed")})
    when = (observed[0] if len(observed) == 1 else f"{observed[0]} to {observed[-1]}") if observed else "date not stated"
    url = (source_meta or {}).get("url") or next((r.get("url") for r in items if r.get("url")), None)
    if plotted:
        off_points = [r for r in plotted if r["_kind"] == LANE_OFF]
        finding = _finding(groups, _ordered_models(groups), off_points, unit)
    else:
        finding = NOTHING_TO_DRAW
    unplotted = sorted({f"{_short_model(r.get('model'), r['_lane_model'])} {r.get('effort')}"
                        for r in items if not _plotted(r)})
    return {"source": source, "benchmark": benchmark,
            "composite": any(bool(r.get("composite")) for r in items),
            "basis": _cost_basis(source_meta), "url": url, "when": when, "unit": unit,
            "finding": finding, "rows": len(items),
            "models": len({_model_key(r) for r in items}), "unplotted": unplotted}


def _point(r, lanes):
    """One row as the script draws it."""
    at = [{"name": n, "harness": lanes[n].get("harness"), "meter": lanes[n].get("meter"),
           "tier": lanes[n].get("tier")}
          for n in r["_lanes"]]
    harness = sorted({lane["harness"] for lane in at if lane["harness"]}) or \
        sorted({lanes[n].get("harness") for n in r["_model_lanes"] if lanes[n].get("harness")})
    # colour is the meter (ticket 27): the lanes' own, else the model's lanes'
    meter = sorted({lane["meter"] for lane in at if lane["meter"]}) or \
        sorted({lanes[n].get("meter") for n in r["_model_lanes"] if lanes[n].get("meter")})
    tiers = [lane["tier"] for lane in at if isinstance(lane["tier"], int)]
    if r.get("uncertain"):
        provenance = "uncertain"
    else:
        provenance = str(r.get("provenance") or "unlabelled")
    return {"model": _model_key(r), "name": _short_model(r.get("model"), r["_lane_model"]),
            "published": r.get("model"), "ours": bool(r["_lane_model"]),
            "effort": r.get("effort") or "?", "score": r["_score"], "cost": r["_cost"],
            "plotted": _plotted(r), "kind": r["_kind"], "weak": r["_weak"], "lanes": at,
            "harness": harness, "meter": meter, "tier": min(tiers) if tiers else None,
            "off": r["_off_reason"], "beatenBy": r["_dominated_by"],
            "carryKind": r.get("_off_kind"), "source": r.get("_off_source"),
            "competitor": r.get("_off_competitor") or r["_dominated_by"],
            "provenance": provenance, "observed": r.get("observed")}


def _carried(lane):
    return lane.get("enabled", True) is not False and lane.get("effort") != "ultra"


def _lane_list(lanes_doc, bench, items, proposals):
    """Every lane the tier panel lists, in the tier pages' order (benchmark
    order, grouped by model, efforts most to least), with what the panel says
    of each: its harness, its group, whether the catalog carries it, the
    pre-screen's reason if it proposes it off, and whether any board draws it
    as a dot. A carried lane with no rows is still a lane that takes a tier,
    so it is listed rather than dropped (ticket 26)."""
    lanes = _lanes(lanes_doc)
    drawn = {name for r in items if _plotted(r) for name in r["_lanes"]}
    off = _proposed_off(proposals)
    out = []
    for name in lane_order({"lanes": lanes}, bench):
        lane = lanes[name]
        decision = (proposals or {}).get(name) or {}
        out.append({"name": name, "harness": lane.get("harness"), "meter": lane.get("meter"),
                    "model": lane.get("model"),
                    "group": carry.model_of(lane), "effort": lane.get("effort"),
                    "tier": lane.get("tier") if isinstance(lane.get("tier"), int) else None,
                    "carried": _carried(lane), "off": off.get(name), "rows": name in drawn,
                    "kind": decision.get("kind"), "source": decision.get("source"),
                    "competitor": decision.get("competitor")})
    return out


def meter_shades(lanes_doc):
    """Every meter the catalog's lanes use, with its harness and a shade of that
    harness's colour: the meter most of the harness's lanes use takes the
    harness colour itself (shade 0), the next shade 1, and so on, ties by name.
    Load balance is across quotas, so colour is the meter (ticket 27), and two
    meters on one harness (`claude-general`, `claude-fable`) read as kin. Listed
    harness by harness, each harness's meters by shade."""
    counts = defaultdict(lambda: defaultdict(int))
    for lane in _lanes(lanes_doc).values():
        if lane.get("harness") and lane.get("meter"):
            counts[lane["harness"]][lane["meter"]] += 1
    out = []
    for harness in sorted(counts):
        ranked = sorted(counts[harness], key=lambda m: (-counts[harness][m], m))
        out += [{"name": m, "harness": harness, "shade": i} for i, m in enumerate(ranked)]
    return out


def _price_of(lane, key):
    """One price key off a lane, or None when it is not a number."""
    price = lane.get("price") if isinstance(lane.get("price"), dict) else {}
    value = price.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def price_rows(lanes_doc):
    """One row per model for the price chart, efforts collapsed (ticket 36).

    Every effort of a model is charged at the same token price, so a row is a
    model and not a lane. An agy model names its effort in the slug, so its
    efforts join through `harnesses.family`, the family rule the rest of the
    page already uses. Each row carries the input and output list price in USD
    per 1M tokens, the meter its lanes drain, whether the catalog carries any of
    its lanes, and — when two efforts of one model disagree about a price, which
    they should not — the range they disagree over and a flag.

    Dearest output first; a model with no published price sorts last, by name,
    and has no figure to draw.
    """
    groups, order = {}, []
    for name, lane in _lanes(lanes_doc).items():
        model = lane.get("model")
        if not isinstance(model, str) or not model.strip():
            continue
        base = harnesses.family(lane.get("harness"), model)[0]
        row = groups.get(base)
        if row is None:
            row = groups[base] = {"model": base, "harness": lane.get("harness"),
                                  "lanes": [], "efforts": [], "carried": False,
                                  "_meters": [], "_in": [], "_out": []}
            order.append(base)
        row["lanes"].append(name)
        row["carried"] = row["carried"] or _carried(lane)
        if lane.get("effort"):
            row["efforts"].append(lane["effort"])
        if lane.get("meter"):
            row["_meters"].append(lane["meter"])
        for key in ("in", "out"):
            value = _price_of(lane, key)
            if value is not None:
                row[f"_{key}"].append(value)

    out = []
    for base in order:
        row = groups.pop(base)
        meters = row.pop("_meters")
        row["meter"] = (min(set(meters), key=lambda m: (-meters.count(m), m))
                        if meters else None)
        row["efforts"] = sorted(set(row["efforts"]), key=effort_rank)
        row["lanes"].sort()
        for key in ("in", "out"):
            values = sorted(set(row.pop(f"_{key}")))
            # the dearest of a disagreement is the one a run might be charged
            row[key] = values[-1] if values else None
            row[f"{key}_range"] = [values[0], values[-1]] if len(values) > 1 else None
        row["disagree"] = bool(row["in_range"] or row["out_range"])
        out.append(row)
    out.sort(key=lambda r: (r["out"] is None, -(r["out"] or 0), r["model"]))
    return out


def catalog_key(lanes_doc):
    """A short key for this catalog's lane names, so the page's own tiers are
    kept apart from another catalog's in the same browser (ticket 26)."""
    names = "\n".join(sorted(_lanes(lanes_doc)))
    return hashlib.sha1(names.encode("utf-8")).hexdigest()[:12]


def plot_data(effort_rows, lanes_doc, proposals=None, bench=None):
    """Everything the plots draw, as one JSON-ready dict: every board with its
    points, the two boards the page opens on, the harnesses and efforts the
    settings offer, and the lanes the tier panel lists."""
    if proposals is None:
        proposals = _proposals(lanes_doc, effort_rows)
    items = _annotate(effort_rows, lanes_doc, proposals)
    sources = _load_sources()
    described = _load_boards()
    lanes = _lanes(lanes_doc)
    boards = []
    for i, ((source, benchmark), rows) in enumerate(_boards(items)):
        board = _board_facts(source, benchmark, rows, sources.get(source) or {})
        board["id"] = f"b{i}"
        board["sourceName"] = (sources.get(source) or {}).get("name") or source
        board["about"] = board_about(source, benchmark, described)
        board["aboutMissing"] = None if board["about"] else NO_ABOUT
        board["category"] = "Composite" if board["composite"] else (board["about"] or {}).get("category")
        board["points"] = [_point(r, lanes) for r in rows]
        boards.append(board)
    # Two plots to start: the board a decision is made on, and the best board
    # from another source if there is one, else the next board of this one.
    defaults = [b["id"] for b in boards[:1]]
    if boards:
        other = next((b for b in boards if b["source"] != boards[0]["source"]), None)
        other = other or (boards[1] if len(boards) > 1 else None)
        if other:
            defaults.append(other["id"])
    efforts = {r.get("effort") for r in items if r.get("effort")}
    return {"boards": boards, "defaults": defaults,
            "harnesses": sorted({lane.get("harness") for lane in lanes.values() if lane.get("harness")}),
            "meters": meter_shades(lanes_doc),
            "efforts": sorted(efforts, key=_effort_key),
            "lanes": _lane_list(lanes_doc, bench, items, proposals),
            "catalogKey": catalog_key(lanes_doc)}


def _json_for_script(data):
    """JSON that cannot end the script element it sits in, whatever a
    benchmark page printed as a model name."""
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render(bench, lanes_doc, effort_rows=None, live=False, board=None):
    """Return the page: `assets/bench_page.html` with this catalog's data in
    its data script. Self-contained, with no network resource.

    `board` is the board id to open on (the wizard's current board). `live`
    says the wizard serves the page through `page_link.py`; the page itself
    finds that out from its URL, so the flag only goes into the data."""
    data = plot_data(effort_rows or [], lanes_doc, bench=bench)
    if board is not None:
        data["board"] = board
    data["live"] = bool(live)
    return _template().replace(DATA_SLOT, _json_for_script(data), 1)


def _template():
    with open(PAGE_PATH, encoding="utf-8") as f:
        text = f.read()
    if text.count(DATA_SLOT) != 1:
        raise ValueError(f"{PAGE_PATH} must hold {DATA_SLOT} exactly once")
    return text


def write(path, bench, lanes_doc, effort_rows=None):
    """Write the rendered page to path and return path."""
    text = render(bench, lanes_doc, effort_rows)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
