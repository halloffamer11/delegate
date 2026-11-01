#!/usr/bin/env python3
"""Tests for bench_page.py. Run: python3 tests/test_bench_page.py

The page is assets/bench_page.html with JSON in its data script. The
decisions in that JSON are Python's and are tested here directly; the page's
script is checked to parse under node when node is on PATH. The drawing and
the live link are checked in a browser by hand (see the delegate-tui-polish
spec)."""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so that
# `catalog.find_git_root()` never finds the invoking checkout's own
# `.delegate/routing.json`. Every path this file needs comes from HERE.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
# the wizard reads and empties dispatch's model queue (ticket 29): never the real one
os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(_ISOLATED_CWD.name, "new-models.json")
os.environ["DELEGATE_MODEL_SCAN"] = "off"
DELEGATE_DIR = os.path.abspath(os.path.join(HERE, "..", "scripts"))
FIXTURE = os.path.join(HERE, "fixture", "bench-epoch.csv")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REAL_DATA = os.path.join(REPO, ".scratch", "delegate-redesign", "_data")
# A real catalog, frozen: the live one is machine-local and never in the repo
# (the user, 2026-09-29).
REAL_LANES = os.path.join(HERE, "fixtures", "refresh-2026-09-22", "lanes.json")
sys.path.insert(0, DELEGATE_DIR)

import bench
import bench_page
import catalog
import harnesses
import setup_tui

LANES = catalog.load_json(os.path.abspath(os.path.join(HERE, "..", "assets", "samples", "lanes.json")))
NODE = shutil.which("node")
fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def remote_resource(html):
    return re.search(r"""(?:src|href)\s*=\s*['"]https?://[^'"]*\.(?:js|css)""", html, re.I)


def data_of(html):
    """The JSON the plots draw, or None when the page carries none."""
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def board_named(data, benchmark):
    return next(b for b in data["boards"] if b["benchmark"] == benchmark)


EFFORT_ROWS = [
    {"source": "swerb", "url": "https://example.invalid/leaderboard/", "model": "gpt-5.6-sol",
     "effort": "high", "benchmark": "SWE Refactor Bench", "score": 19.0, "cost_usd": 9.1,
     "observed": "2026-09-10", "provenance": "unlabelled", "uncertain": False},
    {"source": "aa", "url": "https://example.invalid/models/", "model": "gpt-5.6-sol",
     "effort": "low", "benchmark": "SWE-Bench verified", "score": 4.0, "cost_usd": 1.2,
     "observed": "2026-09-10", "provenance": "unlabelled", "uncertain": True},
]

# The catalog with the astra sweep the wizard's own test uses, and a sweep of
# published rows in which exactly one lane is dominated, plus comparators.
ASTRA = copy.deepcopy(LANES)
for effort in ("low", "medium", "high", "xhigh", "max"):
    lane = copy.deepcopy(ASTRA["lanes"]["sol-high@codex"])
    lane["model"] = "gpt-6-astra"
    lane["effort"] = effort
    ASTRA["lanes"][f"astra-{effort}@codex"] = lane
SWEEP = []
for effort, score, cost in (("low", 50.61, 1557.3), ("medium", 54.24, 1914.8),
                            ("high", 57.88, 2269.42), ("xhigh", 57.88, 2350.51),
                            ("max", 58.18, 3267.18)):
    SWEEP.append({"source": "tbench", "model": "GPT-6 Astra", "effort": effort,
                  "benchmark": "Terminal-Bench 4.0", "score": score, "score_unit": "%",
                  "cost_usd": cost, "uncertain": False, "observed": "2026-09-03",
                  "provenance": "unlabelled"})
SWEEP += [
    {"source": "tbench", "model": "GLM-5.3", "effort": "max", "benchmark": "Terminal-Bench 4.0",
     "score": 41.82, "score_unit": "%", "cost_usd": 2727.63, "uncertain": False,
     "observed": "2026-08-14", "provenance": "unlabelled"},
    {"source": "tbench", "model": "Opus 5", "effort": "max", "benchmark": "Terminal-Bench 4.0",
     "score": 51.82, "score_unit": "%", "cost_usd": 5969.11, "uncertain": False,
     "observed": "2026-07-24", "provenance": "unlabelled"},
    # our model, at an effort no lane runs: context, not a lane's figure
    {"source": "tbench", "model": "GPT-5.6 Sol", "effort": "max", "benchmark": "Terminal-Bench 4.0",
     "score": 37.27, "score_unit": "%", "cost_usd": 2541.7, "uncertain": False,
     "observed": "2026-06-26", "provenance": "unlabelled"},
]


# --- the basics ------------------------------------------------------------------
try:
    collected = bench.collect(LANES, epoch_csv=FIXTURE)
    html = bench_page.render(collected, LANES)
    record("page from epoch fixture",
           "<title>Delegate tiers</title>" in html and data_of(html) is not None
           and "claude-fable-5-1" in html and bench_page.DATA_SLOT not in html,
           html[:400])
    record("the page loads nothing remote, and its one script is inline",
           remote_resource(html) is None and "<style>" in html
           and not re.search(r"<script[^>]*\bsrc\s*=", html, re.I)
           and "<link" not in html.lower() and html.count("<script>") == 1,
           html[:200])
except Exception as e:
    record("page from epoch fixture", False, repr(e))


try:
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "bench.html")
        collected = bench.collect(LANES, epoch_csv=FIXTURE)
        returned = bench_page.write(path, collected, LANES, EFFORT_ROWS)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        record("write returns path and persists HTML",
               returned == path and os.path.isfile(path) and data_of(text)["boards"])
except Exception as e:
    record("write returns path and persists HTML", False, repr(e))

try:
    with open(bench_page.PAGE_PATH, encoding="utf-8") as f:
        template = f.read()
    record("light and dark are both defined, and the toggle wins both ways",
           "prefers-color-scheme: dark" in template
           and ':root:not([data-theme="light"])' in template
           and ':root[data-theme="dark"]' in template
           and template.count("--surface:") >= 3)
except Exception as e:
    record("light and dark are both defined, and the toggle wins both ways", False, repr(e))


try:
    hostile = dict(SWEEP[5], model='</script><script>alert(1)</script> & "GLM"')
    page = bench_page.render(None, ASTRA, [hostile])
    data = data_of(page)
    record("a model name from a benchmark page cannot end the data's script element",
           data is not None and data["boards"][0]["points"][0]["name"] == hostile["model"]
           and "<script>alert" not in page,
           page[page.find("bench-data"):][:300])
except Exception as e:
    record("a model name from a benchmark page cannot end the data's script element", False, repr(e))


# --- the plot data ------------------------------------------------------------------
try:
    rows = [
        {"source": "t", "model": "m-a", "effort": "low", "benchmark": "B1",
         "score": 10.0, "cost_usd": 1.0, "uncertain": False},
        {"source": "t", "model": "m-a", "effort": "high", "benchmark": "B1",
         "score": 20.0, "cost_usd": 2.0, "uncertain": False},
        {"source": "t", "model": "m-b", "effort": "low", "benchmark": "B2",
         "score": 5.0, "cost_usd": 3.0, "uncertain": False},
        {"source": "u", "model": "gpt-5.6-sol", "effort": "high", "benchmark": "B1",
         "score": 7.0, "cost_usd": 4.0, "uncertain": False},
        # weak: drawn dashed and hollow, and named weak in the table
        {"source": "t", "model": "m-c", "effort": "low", "benchmark": "B1",
         "score": 9.0, "cost_usd": 9.0, "uncertain": True},
        # cannot be placed on a log axis; listed as not drawn
        {"source": "t", "model": "m-d", "effort": "low", "benchmark": "B1",
         "score": 9.0, "cost_usd": 0, "uncertain": False},
    ]
    page = bench_page.render(None, LANES, rows)
    data = data_of(page)
    boards = {(r["source"], r["benchmark"]) for r in rows}
    seen = {(b["source"], b["benchmark"]) for b in data["boards"]}
    t_b1 = next(b for b in data["boards"] if (b["source"], b["benchmark"]) == ("t", "B1"))
    weak = [p for b in data["boards"] for p in b["points"] if p["weak"]]
    record("one board per source and benchmark, never two sources on one cost axis",
           len(data["boards"]) == len(boards) and seen == boards
           and t_b1["unplotted"] == ["m-d low"]
           and [p["plotted"] for p in t_b1["points"] if p["name"] == "m-d"] == [False]
           and [p["name"] for p in weak] == ["m-c"],
           f"boards={seen} unplotted={t_b1['unplotted']} weak={weak}")
except Exception as e:
    record("one board per source and benchmark, never two sources on one cost axis", False, repr(e))


try:
    data = bench_page.plot_data(SWEEP, ASTRA)
    points = board_named(data, "Terminal-Bench 4.0")["points"]
    kinds = {}
    for p in points:
        kinds.setdefault(p["kind"], []).append(p)
    lane = next(p for p in points if p["kind"] == "lane")
    page = bench_page.render(None, ASTRA, SWEEP)
    record("a lane, a proposed-off lane, our model at another effort and a comparator "
           "are each their own kind, and a lane point carries its harness and tier",
           {k: len(v) for k, v in kinds.items()} == {"lane": 4, "lane_off": 1, "own_other": 1, "comparator": 2}
           and lane["harness"] == ["codex"] and lane["tier"] == ASTRA["lanes"][lane["lanes"][0]["name"]]["tier"]
           and all(p["harness"] == [] and not p["ours"] for p in kinds["comparator"])
           and kinds["own_other"][0]["harness"] == ["codex"] and kinds["own_other"][0]["lanes"] == []
           and data["harnesses"] == sorted({l["harness"] for l in ASTRA["lanes"].values()})
           and bench_page.NO_LANE in page,
           f"kinds={ {k: len(v) for k, v in kinds.items()} } lane={lane}")
except Exception as e:
    record("a lane, a proposed-off lane, our model at another effort and a comparator "
           "are each their own kind, and a lane point carries its harness and tier", False, repr(e))

# --- the page is the evidence for the pre-screen, so it has to say the same -----

# ticket 30: a dominated agy point is marked exactly as a dominated codex one is
AGY_LANES = {
    "version": "delegate-lanes.v1",
    "lanes": {
        "flash-medium@agy": {"harness": "agy", "model": "gemini-3.8-flash-medium",
                             "effort": "medium", "tier": 1, "meter": "agy-gemini"},
        "flash-high@agy": {"harness": "agy", "model": "gemini-3.8-flash-high", "effort": "high",
                           "tier": 2, "meter": "agy-gemini"},
    },
}
AGY_SWEEP = [
    {"source": "aa", "model": "gemini-3.8-flash", "effort": e, "benchmark": "B",
     "score": s, "cost_usd": c, "uncertain": False}
    for e, s, c in (("medium", 0.60, 1.0), ("high", 0.50, 2.0))
]

try:
    data = bench_page.plot_data(AGY_SWEEP, AGY_LANES)
    points = board_named(data, "B")["points"]
    struck = [p for p in points if p["kind"] == "lane_off"]
    record("the page marks a dominated agy effort the way it marks a codex one",
           len(struck) == 1 and struck[0]["effort"] == "high"
           and struck[0]["beatenBy"] == "medium" and struck[0]["carryKind"] == "dominated"
           and struck[0]["off"] == "medium wins on aa" and struck[0]["source"] == "aa"
           and struck[0]["competitor"] == "medium"
           and [p["kind"] for p in points if p["effort"] == "medium"] == ["lane"],
           f"points={[(p['effort'], p['kind'], p.get('beatenBy')) for p in points]}")
except Exception as e:
    record("the page marks a dominated agy effort the way it marks a codex one", False, repr(e))


try:
    # One source, three benchmarks off the same runs. medium beats high on two
    # of the three, so the wizard switches high off over the source, and the page
    # has to say so on every one of that source's boards — including b3, where
    # high happens to score more.
    luna = copy.deepcopy(LANES)
    for effort in ("low", "medium", "high"):
        lane = copy.deepcopy(LANES["lanes"]["sol-high@codex"])
        lane["model"] = "gpt-5.6-luna"
        lane["effort"] = effort
        luna["lanes"][f"luna-{effort}@codex"] = lane
    board = []
    for bench_name, points in (("b1", (0.6, 0.5)), ("b2", (0.6, 0.5)), ("b3", (0.4, 0.5))):
        for effort, score, cost in (("medium", points[0], 1.0), ("high", points[1], 2.0)):
            board.append({"source": "aa", "model": "gpt-5.6-luna", "effort": effort,
                          "benchmark": bench_name, "score": score, "cost_usd": cost,
                          "uncertain": False, "provenance": "unlabelled"})
    every = [p for b in bench_page.plot_data(board, luna)["boards"] for p in b["points"]]
    struck = [p for p in every if p["kind"] == "lane_off"]
    kept = [p for p in every if p["kind"] == "lane"]
    record("a lane dominated over its source is struck on every board of that source",
           len(struck) == 3 and all(p["beatenBy"] == "medium" and p["effort"] == "high" for p in struck)
           and len(kept) == 3 and not any(p["beatenBy"] for p in kept),
           f"struck={struck} kept={kept}")
except Exception as e:
    record("a lane dominated over its source is struck on every board of that source",
           False, repr(e))


try:
    # self-reported rows still count in the wizard's rule; uncertain never do.
    # Either way the figure must not look verified.
    rows = [dict(SWEEP[2], provenance="self-reported"), dict(SWEEP[3])]
    page = bench_page.render(None, ASTRA, rows)
    weak = [p for p in data_of(page)["boards"][0]["points"] if p["weak"]]
    record("a weakly-sourced figure is marked weak",
           len(weak) == 1 and weak[0]["provenance"] == "self-reported" and weak[0]["kind"] == "lane",
           f"weak={weak}")
except Exception as e:
    record("a weakly-sourced figure is marked weak", False, repr(e))

try:
    # a board where a carried lane is measured at its own effort comes before
    # one that only has our models at efforts no lane runs, and the page opens
    # on it and on the best board from another source
    other = [{"source": "swerb", "model": "gpt-5.6-sol", "effort": e, "benchmark": "SWE Refactor Bench",
              "score": s, "cost_usd": c, "uncertain": False}
             for e, s, c in (("low", 7.0, 5.9), ("medium", 6.5, 6.0), ("xhigh", 9.5, 19.1), ("max", 28.5, 143.5))]
    page = bench_page.render(None, ASTRA, other + SWEEP)
    data = data_of(page)
    names = {b["id"]: b["benchmark"] for b in data["boards"]}
    record("the board with carried lanes measured at their effort comes first, and the page "
           "opens on it and on another source",
           [names[i] for i in data["defaults"]] == ["Terminal-Bench 4.0", "SWE Refactor Bench"],
           f"defaults={[names[i] for i in data['defaults']]}")
    # one source, two boards with the same lanes on them: the composite index
    # opens first, because it is the board that reads best at a glance
    index = [dict(r, benchmark="Index", composite=True, source="aa") for r in SWEEP[:5]]
    parts = [dict(r, benchmark="A part", source="aa") for r in SWEEP[:5]]
    data = bench_page.plot_data(parts + index, ASTRA)
    record("among boards that tie on lanes, the composite index opens first",
           [data["boards"][0]["benchmark"], data["boards"][0]["composite"]] == ["Index", True]
           and [b["benchmark"] for b in data["boards"]] == ["Index", "A part"]
           and data["defaults"] == ["b0", "b1"],
           f"boards={[b['benchmark'] for b in data['boards']]} defaults={data['defaults']}")
except Exception as e:
    record("the board with carried lanes measured at their effort comes first, and the page "
           "opens on it and on another source", False, repr(e))


# --- ticket 25: what each board measures --------------------------------
import effort  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")


def every_known_row():
    """The AA rows off the fixture page, the Terminal-Bench fixture, and the
    swerb rows when the real data is present: one row set per approved source."""
    with open(os.path.join(FIXTURES, "real_aa_model_page_sample.html"), "rb") as f:
        _packet, rows = effort.aa_extract(f.read(), observed="2026-09-11")
    with open(os.path.join(FIXTURES, "tbench-accepted.json"), encoding="utf-8") as f:
        rows = rows + json.load(f)
    for name in ("aa-accepted.json", "tbench-accepted.json", "swerb-accepted.json"):
        path = os.path.join(REAL_DATA, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                rows = rows + json.load(f)
    return rows


try:
    rows = every_known_row()
    data = bench_page.plot_data(rows, catalog.load_json(REAL_LANES) if os.path.isfile(REAL_LANES) else LANES)
    missing = [(b["source"], b["benchmark"]) for b in data["boards"]
               if not b["about"] or not b["about"]["measures"] or not b["about"]["url"]
               or not b["about"]["url"].startswith("https://")]
    sources = {b["source"] for b in data["boards"]}
    record("every board on the page has a description and a source URL",
           not missing and {"aa", "tbench"} <= sources and len(data["boards"]) >= 10
           and all(b["aboutMissing"] is None for b in data["boards"]),
           f"missing={missing} sources={sources}")
    with open(bench_page.BOARDS_PATH, encoding="utf-8") as f:
        described = json.load(f)["boards"]
    cited = [(s, n) for s, boards in described.items() for n, e in boards.items()
             if not (e.get("url") and e.get("fetched") and e.get("measures") and e.get("score"))]
    record("every description on file names its page and the day it was fetched",
           not cited, repr(cited))
except Exception as e:
    record("every board on the page has a description and a source URL", False, repr(e))

try:
    page = bench_page.render(None, ASTRA, SWEEP + [dict(SWEEP[0], source="t", benchmark="Nobody's board")])
    data = data_of(page)
    tb = board_named(data, "Terminal-Bench 4.0")
    stranger = board_named(data, "Nobody's board")
    record("a board with no methodology page on file says so, and never borrows a description",
           tb["about"]["url"].startswith("https://") and "terminal" in tb["about"]["measures"]
           and stranger["about"] is None and stranger["aboutMissing"] == bench_page.NO_ABOUT
           and bench_page.board_about("t", "Nobody's board") is None,
           f"tb={tb['about']} stranger={stranger['about']}")
except Exception as e:
    record("a board with no methodology page on file says so, and never borrows a description",
           False, repr(e))


# --- ticket 26: the page lists every lane ------------------------------------
try:
    collected = bench.collect(copy.deepcopy(ASTRA), epoch_csv=FIXTURE)
    doc = copy.deepcopy(ASTRA)
    doc["lanes"]["astra-ultra@codex"] = dict(doc["lanes"]["astra-max@codex"], effort="ultra", enabled=False)
    page = bench_page.render(collected, doc, SWEEP)
    data = data_of(page)
    lanes = data["lanes"]
    by_name = {l["name"]: l for l in lanes}
    astra = [l["name"] for l in lanes if l["group"] == "gpt-6-astra"]
    groups = []
    for l in lanes:
        if not groups or groups[-1] != l["group"]:
            groups.append(l["group"])
    wizard = setup_tui.Wizard(copy.deepcopy(doc), {"classes": {}, "margin": 0, "gate": 0}, collected,
                              set(harnesses.NAMES), "/tmp/l", "/tmp/r", effort_rows=SWEEP)
    record("the page lists every lane in the tier page's order, grouped by model, efforts most to least, "
           "and says which are carried, proposed off, or drawn nowhere",
           [l["name"] for l in lanes] == setup_tui.lane_order(doc, collected)
           and [l["name"] for l in lanes if l["carried"]] == [n for n in setup_tui.lane_order(doc, collected)
                                                                if wizard._enabled[n] or n == "astra-xhigh@codex"]
           and astra == ["astra-ultra@codex", "astra-max@codex", "astra-xhigh@codex", "astra-high@codex",
                         "astra-medium@codex", "astra-low@codex"]
           and len(groups) == len(set(groups))
           and by_name["astra-ultra@codex"]["carried"] is False
           and by_name["astra-xhigh@codex"]["carried"] is True
           and by_name["astra-xhigh@codex"]["off"] == "high wins on tbench"
           and by_name["astra-xhigh@codex"]["kind"] == "dominated"
           and by_name["astra-xhigh@codex"]["source"] == "tbench"
           and by_name["astra-xhigh@codex"]["competitor"] == "high"
           and by_name["astra-high@codex"]["off"] is None
           and by_name["astra-high@codex"]["rows"] is True
           # fable is on no board of this sweep, so it can be no dot
           and by_name["fable-xhigh@claude"]["rows"] is False
           and by_name["fable-xhigh@claude"]["carried"] is True
           and by_name["astra-high@codex"]["harness"] == "codex"
           and by_name["astra-high@codex"]["tier"] == doc["lanes"]["astra-high@codex"]["tier"]
           # ticket 27 added the lane's meter, which colour is now drawn from
           and set(lanes[0]) == {"name", "harness", "meter", "model", "group", "effort", "tier",
                                "carried", "off", "rows", "kind", "source", "competitor"},
           repr(lanes[:3]))
    key = data["catalogKey"]
    other = copy.deepcopy(doc)
    other["lanes"]["extra-high@codex"] = copy.deepcopy(doc["lanes"]["astra-high@codex"])
    record("the page's data is keyed by the catalog",
           re.fullmatch(r"[0-9a-f]{12}", key) and bench_page.catalog_key(doc) == key
           and bench_page.catalog_key(other) != key,
           repr(key))
except Exception as e:
    record("the page lists every lane in the tier page's order, grouped by model, efforts most to least, "
           "and says which are carried, proposed off, or drawn nowhere", False, repr(e))


# --- ticket 12: the page uses the same evidence records ---------------------------
try:
    rows = [
        {"source": "aa", "model": "gpt-5.6-sol", "effort": "high",
         "benchmark": "Terminal-Bench 2.1", "score": 0.80, "cost_usd": 0.81,
         "uncertain": False, "observed": "2026-09-11", "provenance": "unlabelled",
         "url": "https://example.invalid/aa"},
        {"source": "tbench", "model": "GPT-5.6 Sol", "effort": "high",
         "benchmark": "Terminal-Bench 4.0", "score": 39.9, "score_unit": "%",
         "cost_usd": 100.0, "uncertain": False, "observed": "2026-09-03",
         "provenance": "unlabelled", "url": "https://example.invalid/tbench"},
        {"source": "aa", "model": "Grok 4.3", "effort": "none",
         "benchmark": "Omniscience", "score": 29.5, "cost_usd": 1.24,
         "uncertain": True, "observed": "2026-09-11", "provenance": "unlabelled"},
        {"source": "x", "model": "gpt-5.6-sol", "effort": "high",
         "benchmark": "Nobody's board", "score": 9.0, "cost_usd": 1.0,
         "uncertain": False, "observed": "2026-09-11", "provenance": "unlabelled"},
    ]
    records = bench.evidence_records(rows, LANES)
    page = bench_page.render(None, LANES, rows)
    about = bench.board_about("aa", "AutomationBench")
    tb = bench.board_about("tbench", "Terminal-Bench 4.0")
    index = bench.board_about("aa", "Artificial Analysis Intelligence Index")
    record(
        "evidence records carry shared standing, cost basis, version and unresolved identity",
        any(r["version"] == "2.1" and "Intelligence Index" in (r["cost_basis"] or "")
            for r in records)
        and any(r["version"] == "4.0" and "whole run" in (r["cost_basis"] or "")
                for r in records)
        and any(r["identity"] == "unresolved" and r["uncertain"] for r in records),
        repr(records[:2]),
    )
    record(
        "speaks_to names coding, knowledge and API-workflow relevance without new Classes",
        about is not None and "API-workflow relevance" in about["speaks_to"]
        and "not a routing Domain or Class" in about["speaks_to"]
        and "Knowledge relevance" in bench.board_about("aa", "Omniscience")["speaks_to"]
        and "Coding relevance" in tb["speaks_to"]
        and "composite across knowledge work, coding, science and general knowledge" in index["speaks_to"]
        and "knowledge-scout" not in about["speaks_to"]
        and about["measures"].startswith("It tests whether models can complete realistic SaaS")
        and about["fetched"] == "2026-11-01" and about["category"] == "Knowledge Work"
        and index["fetched"] == "2026-11-01"
        and index["score"].startswith("The Intelligence Index is calculated as a weighted average"),
        str({"auto": about["speaks_to"], "tb": tb["speaks_to"]}),
    )
    record(
        "quoted methodology is preserved and direction is labelled, never inferred",
        about["direction"] == "higher-is-better"
        and tb["direction"] == "higher-is-better"
        and bench.board_about("t", "Nobody's board") is None
        and bench.board_direction("t", "Nobody's board") == bench.DIRECTION_UNKNOWN
        and "higher-is-better" in page,
        str(about.get("direction")),
    )
except Exception as e:
    record("ticket 12 HTML shared evidence records", False, repr(e))


# Ticket 36: price per model — one row per model, two dots on one log axis.


try:
    lanes_doc = {
        "version": "delegate-lanes.v1",
        "meters": {
            "codex": {"harness": "codex", "plan": "p", "price_month": 20, "probe": "usage.py"},
            "agy-gemini": {"harness": "agy", "plan": "p", "price_month": 17, "probe": "usage.py"},
        },
        "lanes": {},
    }
    def price_lane(harness, model, effort, meter, price, enabled=None):
        lane = {"harness": harness, "model": model, "effort": effort, "meter": meter,
                "meter_weight": 1, "timeout": "10m", "tier": 1, "basis": "fixture",
                "price": price}
        if enabled is not None:
            lane["enabled"] = enabled
        return lane
    dear = {"in": 10.0, "cache_read": 1.0, "cache_write": None, "out": 50.0}
    cheap = {"in": 0.75, "cache_read": 0.075, "cache_write": None, "out": 3.75}
    none_price = {"in": None, "cache_read": None, "cache_write": None, "out": None}
    for effort in ("low", "medium", "high"):
        lanes_doc["lanes"][f"astra-{effort}@codex"] = price_lane(
            "codex", "gpt-6-astra", effort, "codex", dict(dear))
        lanes_doc["lanes"][f"flash-{effort}@agy"] = price_lane(
            "agy", f"gemini-3.8-flash-{effort}", effort, "agy-gemini", dict(cheap))
    lanes_doc["lanes"]["quiet-high@codex"] = price_lane(
        "codex", "gpt-quiet", "high", "codex", dict(none_price), enabled=False)
    # two efforts of one model that disagree, which should not happen
    lanes_doc["lanes"]["odd-low@codex"] = price_lane(
        "codex", "gpt-odd", "low", "codex", {"in": 1.0, "cache_read": None, "cache_write": None, "out": 9.0})
    lanes_doc["lanes"]["odd-high@codex"] = price_lane(
        "codex", "gpt-odd", "high", "codex", {"in": 2.0, "cache_read": None, "cache_write": None, "out": 9.0})
    catalog.validate_lanes(copy.deepcopy(lanes_doc), "price fixture")

    rows = bench_page.price_rows(lanes_doc)
    by_model = {r["model"]: r for r in rows}
    record("36.4 one row per model, not per effort, with the agy family collapsed",
           [r["model"] for r in rows] == ["gpt-6-astra", "gpt-odd", "gemini-3.8-flash", "gpt-quiet"]
           and by_model["gemini-3.8-flash"]["efforts"] == ["high", "medium", "low"]
           and by_model["gemini-3.8-flash"]["lanes"] == ["flash-high@agy", "flash-low@agy", "flash-medium@agy"]
           and by_model["gpt-6-astra"]["meter"] == "codex"
           and by_model["gpt-quiet"]["carried"] is False
           and by_model["gpt-6-astra"]["carried"] is True,
           repr([(r["model"], r["efforts"], r["out"]) for r in rows]))
    record("36.5 a model with no published price has no figure, and disagreeing efforts flag a range",
           by_model["gpt-quiet"]["in"] is None and by_model["gpt-quiet"]["out"] is None
           and by_model["gpt-quiet"]["disagree"] is False
           and by_model["gpt-odd"]["disagree"] is True
           and by_model["gpt-odd"]["in_range"] == [1.0, 2.0]
           and by_model["gpt-odd"]["out_range"] is None
           and by_model["gpt-odd"]["in"] == 2.0,
           repr(by_model["gpt-odd"]))
except Exception as e:
    record("36.4 price per model", False, repr(e))


# --- the one-screen page: plot and tier matrix, linked to the wizard ----------
try:
    page = bench_page.render(None, ASTRA, SWEEP, live=True, board="b0")
    data = data_of(page)
    plain = data_of(bench_page.render(None, ASTRA, SWEEP))
    record("the page carries the board the wizard is on and says it is served live",
           data["board"] == "b0" and data["live"] is True
           and plain["live"] is False and "board" not in plain
           and page.count(bench_page.DATA_SLOT) == 0
           and all(b.get("category") for b in data["boards"]),
           repr({k: data.get(k) for k in ("board", "live")}))
except Exception as e:
    record("the page carries the board the wizard is on", False, repr(e))

try:
    with open(bench_page.PAGE_PATH, encoding="utf-8") as f:
        template = f.read()
    script = template[template.index("<script>") + len("<script>"):template.rindex("</script>")]
    record("the template holds one data slot, polls the wizard only with its key, and has a zoom reset",
           template.count(bench_page.DATA_SLOT) == 1
           and '"/state?k="' in template and '"/set?k="' in template
           and 'id="zoomReset"' in template and 'id="board"' in template
           # the score axis margin is a share of the board's spread, never a whole point
           and "(y1 - y0) * 0.08, 1)" not in script,
           "")
    if not NODE:
        record("the page's script parses, under node", True, "(node not on PATH; skipped)")
    else:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "page.js")
            with open(path, "w", encoding="utf-8") as f:
                f.write(script)
            result = subprocess.run([NODE, "--check", path], capture_output=True, text=True, timeout=60)
        record("the page's script parses, under node", result.returncode == 0, result.stderr[-600:])
except Exception as e:
    record("the template holds one data slot", False, repr(e))


sys.exit(1 if fails else 0)
