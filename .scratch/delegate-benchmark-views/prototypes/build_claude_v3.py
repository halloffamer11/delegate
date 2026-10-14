#!/usr/bin/env python3
"""Build claude-v3.html: the plots-first prototype, on sample data.

Run from the repo root:
  python3 .scratch/delegate-benchmark-views/prototypes/build_claude_v3.py
It runs render_sample.py into a temporary folder, keeps the fields the prototype
draws, and pastes them into claude-v3.src.html.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run([sys.executable, os.path.join(HERE, "render_sample.py"), tmp], check=True,
                   stdout=subprocess.DEVNULL)
    with open(os.path.join(tmp, "sample-data.json")) as f:
        data = json.load(f)

POINT = ("model", "published", "ours", "effort", "score", "cost", "kind")
LANE = ("name", "harness", "meter", "model", "group", "effort", "tier", "carried", "off")
slim = {
    "harnesses": data["harnesses"],
    "efforts": data["efforts"],
    "boards": [{
        "id": b["id"], "source": b["source"], "benchmark": b["benchmark"], "basis": b["basis"],
        "unit": b["unit"], "when": b["when"], "composite": b["composite"],
        "points": [dict({k: p.get(k) for k in POINT}, lanes=[l["name"] for l in p.get("lanes") or []])
                   for p in b["points"] if p.get("plotted") and p.get("score") is not None],
    } for b in data["boards"]],
    "lanes": [{k: l.get(k) for k in LANE} for l in data["lanes"]],
}
with open(os.path.join(HERE, "claude-v3.src.html"), encoding="utf-8") as f:
    page = f.read()
blob = json.dumps(slim, separators=(",", ":")).replace("</", "<\\/")
with open(os.path.join(HERE, "claude-v3.html"), "w", encoding="utf-8") as f:
    f.write(page.replace("__SAMPLE_DATA_JSON__", blob))
print(os.path.join(HERE, "claude-v3.html"))
