#!/usr/bin/env python3
"""Render the benchmark page on sample data, for the restyle prototypes.

Run from the repo root: python3 .scratch/delegate-benchmark-views/prototypes/render_sample.py OUT_DIR
Writes OUT_DIR/sample-page.html (the current page) and OUT_DIR/sample-data.json
(the page's own #bench-data JSON: boards, points, lanes, meters, coverage).
Sample data only: the repo's accepted rows and its frozen test catalog, plus
two Kiro lanes so one model shows on two harnesses. Never a machine's catalog.
"""
import copy
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SKILL = os.path.join(ROOT, "agents", "skills", "delegate")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import bench  # noqa: E402
import bench_page  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(out, exist_ok=True)
rows = []
for name in ("aa", "tbench", "swerb"):
    with open(os.path.join(ROOT, ".scratch", "delegate-redesign", "_data", f"{name}-accepted.json")) as f:
        doc = json.load(f)
    rows += doc["rows"] if isinstance(doc, dict) else doc
with open(os.path.join(SKILL, "tests", "fixtures", "refresh-2026-09-22", "lanes.json")) as f:
    lanes = json.load(f)
lanes = copy.deepcopy(lanes)
lanes["lanes"]["opus-high@kiro"] = {"harness": "kiro", "model": "claude-opus-5", "effort": "high",
                                    "tier": 3, "meter": "kiro-credits"}
lanes["lanes"]["sonnet-medium@kiro"] = {"harness": "kiro", "model": "claude-sonnet-5", "effort": "medium",
                                        "tier": 2, "meter": "kiro-credits"}
lanes["lanes"]["sonnet-medium@claude"].update({"enabled": True, "tier": 2})
page = bench_page.render(bench.collect(lanes, effort_rows=rows), lanes, rows)
with open(os.path.join(out, "sample-page.html"), "w", encoding="utf-8") as f:
    f.write(page)
data = re.search(r'<script type="application/json" id="bench-data">(.*?)</script>', page, re.S).group(1)
with open(os.path.join(out, "sample-data.json"), "w", encoding="utf-8") as f:
    json.dump(json.loads(data), f, indent=1)
print(os.path.join(out, "sample-page.html"))
