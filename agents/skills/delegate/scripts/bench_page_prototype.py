#!/usr/bin/env python3
"""PROTOTYPE, throwaway: the benchmark page and TUI tier screens, six ways.

Answers one question before the redesign is built: what should the tier
selection surface look like? Three page variants (A, B, C) and three TUI
nesting variants (T1, T2, T3), switched with ?variant= and a bottom bar.

    python3 agents/skills/delegate/scripts/bench_page_prototype.py [--no-open]

Reads this machine's catalog (never writes it) through the same steps the
wizard runs, and writes the page to ~/.cache/delegate/bench-prototype.html.
The page holds machine-local catalog data, so it is never committed.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bench_page  # noqa: E402
import setup  # noqa: E402

CHECKOUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ROWS = [os.path.join(CHECKOUT, ".scratch", "delegate-redesign", "_data", n)
        for n in ("aa-accepted.json", "tbench-accepted.json")]
TEMPLATE = os.path.join(HERE, "..", "assets", "bench_page_prototype.html")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config-dir", default="~/.config/delegate")
    parser.add_argument("--out", default="~/.cache/delegate/bench-prototype.html")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    config_dir = os.path.expanduser(args.config_dir)
    ns = argparse.Namespace(config_dir=config_dir, ads_dir=None, discover_json=None, plain=False,
                            bench_report=None, no_bench=False, epoch_csv=None,
                            effort_rows=[p for p in ROWS if os.path.isfile(p)], tiers_from=None,
                            no_discover=False, fixture_dir=None, screen="start")
    lanes_doc, _routing, _lp, _rp = setup.load_or_propose(config_dir, set(setup.HARNESSES))
    _found, discovery, rows, _note, _paths = setup.scan(ns, lanes_doc)
    lanes_doc, _refresh, discovery = setup.propose_generation(lanes_doc, discovery, rows)
    effort_rows, _msg = rows
    bench, _m = setup.collect_bench(ns, lanes_doc, effort_rows)
    data = bench_page.plot_data(effort_rows, lanes_doc, None, bench)
    installed = sorted(h for h, d in ((discovery or {}).get("harnesses") or {}).items()
                       if isinstance(d, dict) and d.get("installed", d.get("found")))
    data["installed"] = installed
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read().replace("/*DATA*/null", bench_page._json_for_script(data))
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(out)
    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", out], check=False)


if __name__ == "__main__":
    main()
