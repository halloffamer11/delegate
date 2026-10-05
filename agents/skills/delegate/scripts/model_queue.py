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

A newer version of a model the catalog already runs is not queued: the scan
applies it (`apply_successors`). Each Lane the refresh would replace with its
successor (`gpt-6-sol` to `gpt-6.1-sol` at the same effort) is swapped in the
global lanes.json, keeping its Tier, Order, Meter and weight, and staying off
if it was off. The old lanes.json is copied beside the queue first, and native
agent files follow. A model new to its harness, a new effort, and a superseded
Lane with no successor at its effort still wait for the wizard, since the
human sets those Tiers. Nothing here names a model: the harness's own list says
what is newer. $DELEGATE_MODEL_APPLY=off keeps the scan to queueing.

The queue lives beside the meter cache (`new-models.json`), or at
$DELEGATE_MODEL_QUEUE. The wizard's confirm write empties it, since that run
saw every model the refresh proposed. $DELEGATE_MODEL_SCAN=off stops the scan.

  model_queue.py show            print the queue (and the swaps applied) as JSON
  model_queue.py scan [--config-dir DIR] [--fixture-dir DIR]
"""
import argparse
import copy
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
# How many applied swaps the queue file remembers until the next wizard run
APPLIED_KEPT = 50
OFF = ("off", "0", "false", "no")


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
    """Empty the queue, and the swaps it reported, after a wizard run wrote the
    catalog, keeping when the last scan ran so dispatch does not start another
    at once."""
    doc = read()
    if doc["models"] or doc.get("applied"):
        doc["models"] = []
        doc["applied"] = []
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


def applied():
    """The swaps scans made, oldest first: `{old, new, model, at}`."""
    return [m for m in read().get("applied") or () if isinstance(m, dict)]


def apply_successors(lanes_doc, refreshed, plan):
    """(catalog, [(old lane, new lane)]): `lanes_doc` with each Lane the
    refresh replaced by a newer version of its own model swapped for that
    successor, in its place.

    The successor is the refresh's own record, so it carries the predecessor's
    Tier, Order, Meter, weight and timeout. Unlike the wizard's refresh, it
    also keeps the predecessor's `enabled: false`: nobody screens this swap,
    so it never turns on a slot the user turned off. Every other change the
    refresh proposes is left for the wizard.
    """
    successors = plan.get("successors") or {}
    doc = copy.deepcopy(lanes_doc)
    new_lanes = refreshed.get("lanes") or {}
    ordered, swaps = {}, []
    for name, lane in (doc.get("lanes") or {}).items():
        names = [new for new in successors.get(name) or () if new in new_lanes]
        if not names:
            ordered[name] = lane
            continue
        for new in names:
            record = copy.deepcopy(new_lanes[new])
            if isinstance(lane, dict) and lane.get("enabled") is False:
                record["enabled"] = False
            ordered[new] = record
            swaps.append((name, new))
    if not swaps:
        return doc, []
    doc["lanes"] = ordered
    meters = doc.setdefault("meters", {})
    for lane in ordered.values():
        meter = lane.get("meter") if isinstance(lane, dict) else None
        if meter and meter not in meters and meter in (refreshed.get("meters") or {}):
            meters[meter] = copy.deepcopy(refreshed["meters"][meter])
    return doc, swaps


def _backup(lanes_path, raw):
    """Copy the lanes.json a scan is about to change beside the queue."""
    folder = os.path.join(os.path.dirname(path()), "lanes-backups")
    os.makedirs(folder, exist_ok=True)
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    target = os.path.join(folder, f"lanes-{stamp}.json")
    with open(target, "wb") as f:
        f.write(raw)
    return target


def _write_applied(base, lanes_path, raw, doc, swaps):
    """Write the swapped catalog, unless lanes.json changed since the scan read
    it (a wizard run in between wins), and the native agents that follow it.
    Returns True when it wrote."""
    import catalog
    import catalog_edit
    import setup
    catalog.validate_lanes(doc, source=lanes_path)
    with open(lanes_path, "rb") as f:
        if f.read() != raw:
            return False
    _backup(lanes_path, raw)
    catalog_edit._write_preserving_link(lanes_path, doc)
    change = {"new": [new for _old, new in swaps], "removed": [old for old, _new in swaps]}
    setup.save_all_native_agents(change, doc, setup.native_targets(base))
    return True


def scan(config_dir=None, fixture_dir=None, present=None):
    """Apply each newer version of a model the catalog runs, then queue every
    model no Lane runs that the wizard's refresh would add a Lane for. Returns
    what it queued."""
    import catalog
    import discover
    base = os.path.expanduser(config_dir if config_dir is not None else catalog.CONFIG_DIR)
    lanes_path = os.path.join(base, "lanes.json")
    with open(lanes_path, "rb") as f:
        raw = f.read()
    lanes_doc = catalog.load_json(lanes_path)
    discovery = discover.discover(lanes_doc, present=present, fixture_dir=fixture_dir)
    refreshed, plan = discover.refresh_catalog(lanes_doc, discovery)
    _mark_checked()
    if os.environ.get("DELEGATE_MODEL_APPLY", "").lower() not in OFF:
        doc, swaps = apply_successors(lanes_doc, refreshed, plan)
        if swaps and _write_applied(base, lanes_path, raw, doc, swaps):
            lanes_doc = doc
            _note_applied(swaps, doc)
    # the refresh also adds Lanes at new efforts of a model the catalog runs;
    # only a model no Lane runs is one the catalog lacks
    import harnesses
    run = {(lane.get("harness"), harnesses.family(lane.get("harness"), lane.get("model") or "")[0])
           for lane in (lanes_doc.get("lanes") or {}).values() if isinstance(lane, dict)}
    return note([item for item in plan.get("models") or []
                 if (item.get("harness"), item.get("model")) not in run], "scan")


def _note_applied(swaps, lanes_doc):
    queue = read()
    stamp = _now().isoformat()
    lanes = lanes_doc.get("lanes") or {}
    queue["applied"] = (list(queue.get("applied") or []) + [
        {"old": old, "new": new, "model": (lanes.get(new) or {}).get("model"), "at": stamp}
        for old, new in swaps
    ])[-APPLIED_KEPT:]
    _write(queue)


def kick(config_dir=None):
    """Start a detached scan when one is due. Never raises and never waits:
    a dispatch must not slow down or fail over a model listing."""
    if os.environ.get("DELEGATE_MODEL_SCAN", "").lower() in OFF:
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
    p_scan = sub.add_parser("scan", help="apply newer versions and queue the models the wizard's refresh would add")
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
