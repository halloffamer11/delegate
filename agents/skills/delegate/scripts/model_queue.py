#!/usr/bin/env python3
"""model_queue.py — models the catalog lacks, noted at dispatch for the next
wizard run (ticket 29).

A new model reaches the catalog only through the wizard (`delegate global`),
and the human still sets its Tier (ADR 0001). What changes is that nobody has
to remember to look: dispatch notes what it sees, and the wizard's start page
names it.

Two things put a model in the queue:

- `scan`: at most once a day, dispatch starts a detached scan that runs the
  same discovery and refresh the wizard runs (`discover.discover`,
  `discover.refresh_catalog`) against the global lanes, and queues every model
  the refresh would add a Lane for that no Lane runs yet. It never delays the dispatch that started
  it. A harness with no model list (Claude) adds nothing here; the wizard
  still finds its models from the benchmark rows.
- `asked`: `delegate dispatch --model <slug>` naming a model no Lane runs.

The queue lives beside the meter cache (`new-models.json`), or at
$DELEGATE_MODEL_QUEUE. The wizard's confirm write empties it, since that run
saw every model the refresh proposed. $DELEGATE_MODEL_SCAN=off stops the scan.

  model_queue.py show            print the queue as JSON
  model_queue.py scan [--config-dir DIR] [--fixture-dir DIR]
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usage  # noqa: E402

VERSION = "delegate-model-queue.v1"
# How long a scan's answer stands before dispatch starts another
SCAN_EVERY = timedelta(days=1)


def path():
    """The queue file: $DELEGATE_MODEL_QUEUE, else beside the meter cache."""
    return (os.environ.get("DELEGATE_MODEL_QUEUE")
            or os.path.join(os.path.dirname(usage.get_cache_path()), "new-models.json"))


def _now():
    return datetime.now(timezone.utc)


def read():
    """The queue document; an empty one when there is none or it does not parse."""
    try:
        with open(path(), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = None
    if not isinstance(doc, dict) or not isinstance(doc.get("models"), list):
        doc = {"version": VERSION, "checked_at": None, "models": []}
    return doc


def _write(doc):
    target = path()
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    tmp = f"{target}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    os.replace(tmp, target)


def pending():
    """The queued models, oldest first: `{harness, model, predecessor, via, first_seen}`."""
    return [m for m in read()["models"] if isinstance(m, dict) and m.get("model")]


def note(entries, via):
    """Add models to the queue; one already there keeps its first sighting."""
    doc = read()
    seen = {(m.get("harness"), m.get("model")) for m in doc["models"] if isinstance(m, dict)}
    stamp = _now().isoformat()
    added = []
    for entry in entries:
        key = (entry.get("harness"), entry.get("model"))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        added.append({"harness": key[0], "model": key[1],
                      "predecessor": entry.get("predecessor"), "via": via, "first_seen": stamp})
    if added:
        doc["models"] = doc["models"] + added
        _write(doc)
    return added


def clear():
    """Empty the queue after a wizard run wrote the catalog, keeping when the
    last scan ran so dispatch does not start another at once."""
    doc = read()
    if doc["models"]:
        doc["models"] = []
        _write(doc)


def due(now=None):
    """Whether the last scan is older than SCAN_EVERY, or there was none."""
    checked = read().get("checked_at")
    try:
        when = datetime.fromisoformat(checked)
    except (TypeError, ValueError):
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now or _now()) - when >= SCAN_EVERY


def _mark_checked():
    doc = read()
    doc["checked_at"] = _now().isoformat()
    _write(doc)


def scan(config_dir=None, fixture_dir=None, present=None):
    """Queue every model no Lane runs that the wizard's refresh would add a
    Lane for. Returns what it added."""
    import catalog
    import discover
    base = os.path.expanduser(config_dir if config_dir is not None else catalog.CONFIG_DIR)
    lanes_doc = catalog.load_json(os.path.join(base, "lanes.json"))
    discovery = discover.discover(lanes_doc, present=present, fixture_dir=fixture_dir)
    _doc, plan = discover.refresh_catalog(lanes_doc, discovery)
    _mark_checked()
    # the refresh also adds Lanes at new efforts of a model the catalog runs;
    # only a model no Lane runs is one the catalog lacks
    import harnesses
    run = {(lane.get("harness"), harnesses.family(lane.get("harness"), lane.get("model") or "")[0])
           for lane in (lanes_doc.get("lanes") or {}).values() if isinstance(lane, dict)}
    return note([item for item in plan.get("models") or []
                 if (item.get("harness"), item.get("model")) not in run], "scan")


def kick(config_dir=None):
    """Start a detached scan when one is due. Never raises and never waits:
    a dispatch must not slow down or fail over a model listing."""
    if os.environ.get("DELEGATE_MODEL_SCAN", "").lower() in ("off", "0", "false", "no"):
        return False
    try:
        if not due():
            return False
        # marked before the scan starts, so concurrent dispatches start one
        _mark_checked()
        cmd = [sys.executable, os.path.abspath(__file__), "scan"]
        if config_dir is not None:
            cmd += ["--config-dir", config_dir]
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(prog="model_queue.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="print the queue as JSON")
    p_scan = sub.add_parser("scan", help="queue the models the wizard's refresh would add")
    p_scan.add_argument("--config-dir", default=None)
    p_scan.add_argument("--fixture-dir", default=None)
    args = parser.parse_args(argv)
    if args.cmd == "show":
        sys.stdout.write(json.dumps(read(), indent=2) + "\n")
        return 0
    try:
        scan(config_dir=args.config_dir, fixture_dir=args.fixture_dir)
    except Exception as e:
        sys.stderr.write(f"model_queue: scan failed: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
