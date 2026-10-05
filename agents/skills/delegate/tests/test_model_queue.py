#!/usr/bin/env python3
"""test_model_queue.py — models the catalog lacks, noted at dispatch (ticket 29)."""
from datetime import timedelta
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
FIXTURES = os.path.join(HERE, "fixtures", "discover")
sys.path.insert(0, SCRIPTS)
import model_queue  # noqa: E402
import setup  # noqa: E402
import setup_tui  # noqa: E402

failures = []


def record(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def config_dir(root):
    cfg = os.path.join(root, "cfg")
    os.makedirs(cfg)
    for name in ("lanes.json", "routing.json"):
        shutil.copy(os.path.join(SAMPLES, name), cfg)
    return cfg


def newer_fixtures(root, slug="gpt-6.1-sol", like="gpt-5.6-sol"):
    """The discover fixtures, with codex also listing a newer version of a
    model the sample catalog runs."""
    folder = os.path.join(root, "fx")
    shutil.copytree(FIXTURES, folder)
    target = os.path.join(folder, "codex-debug-models.json")
    with open(target, encoding="utf-8") as f:
        doc = json.load(f)
    entry = dict(next(m for m in doc["models"] if m["slug"] == like), slug=slug, display_name=slug)
    doc["models"].insert(0, entry)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return folder


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def apply_tests(root):
    present = {"codex", "agy", "grok"}
    fixtures = newer_fixtures(root)

    os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(root, "q9", "new-models.json")
    cfg = config_dir(os.path.join(root, "a9"))
    before = load(os.path.join(cfg, "lanes.json"))
    queued = model_queue.scan(config_dir=cfg, fixture_dir=fixtures, present=present)
    after = load(os.path.join(cfg, "lanes.json"))
    names = list(after["lanes"])
    new = [n for n, lane in after["lanes"].items() if lane["model"] == "gpt-6.1-sol"]
    old_at = list(before["lanes"]).index("sol-high@codex")
    lane = after["lanes"][new[0]] if len(new) == 1 else {}
    backups = os.listdir(os.path.join(root, "q9", "lanes-backups"))
    record("9. a newer version of a model the catalog runs takes its lane's place, tier and all",
           "sol-high@codex" not in after["lanes"] and len(new) == 1
           and names.index(new[0]) == old_at and lane.get("tier") == 3 and lane.get("effort") == "high"
           and "enabled" not in lane and len(backups) == 1
           and load(os.path.join(root, "q9", "lanes-backups", backups[0])) == before
           and [(a["old"], a["new"]) for a in model_queue.applied()] == [("sol-high@codex", new[0])],
           repr((new, names, lane, backups, model_queue.applied())))
    lines = setup_tui.refresh_lines({"models": [], "removed": [], "notices": [], "queued": [],
                                     "applied": model_queue.applied()}, width=200)
    record("9b. the wizard's start facts name the swap",
           any(line.startswith(f"Dispatch swapped in: sol-high@codex -> {new[0]}") for line in lines),
           repr(lines))
    setup.clear_queue({"models": [], "queued": model_queue.pending()})
    record("9c. the wizard's write empties the swaps it reported",
           model_queue.applied() == [])
    models = [(m["harness"], m["model"]) for m in queued]
    record("10. the applied model is not queued; a model new to the harness still is",
           ("codex", "gpt-6.1-sol") not in models and ("codex", "gpt-6-astra") in models,
           repr(models))

    os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(root, "q11", "new-models.json")
    cfg = config_dir(os.path.join(root, "a11"))
    path = os.path.join(cfg, "lanes.json")
    doc = load(path)
    doc["lanes"]["sol-high@codex"]["enabled"] = False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    model_queue.scan(config_dir=cfg, fixture_dir=fixtures, present=present)
    new = [lane for lane in load(path)["lanes"].values() if lane["model"] == "gpt-6.1-sol"]
    record("11. a swap keeps an off lane off",
           len(new) == 1 and new[0].get("enabled") is False, repr(new))

    os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(root, "q12", "new-models.json")
    os.environ["DELEGATE_MODEL_APPLY"] = "off"
    cfg = config_dir(os.path.join(root, "a12"))
    path = os.path.join(cfg, "lanes.json")
    with open(path, "rb") as f:
        raw = f.read()
    model_queue.scan(config_dir=cfg, fixture_dir=fixtures, present=present)
    with open(path, "rb") as f:
        same = f.read() == raw
    os.environ.pop("DELEGATE_MODEL_APPLY")
    record("12. DELEGATE_MODEL_APPLY=off changes no catalog and queues the newer version",
           same and ("codex", "gpt-6.1-sol") in [(m["harness"], m["model"]) for m in model_queue.pending()]
           and model_queue.applied() == [])

    doc = load(path)
    swapped = dict(doc, lanes={"x@codex": doc["lanes"]["sol-high@codex"]})
    wrote = model_queue._write_applied(cfg, path, raw + b" ", swapped, [("sol-high@codex", "x@codex")])
    record("13. a catalog changed since the scan read it is not overwritten",
           wrote is False and load(path) == doc)


def main():
    with tempfile.TemporaryDirectory() as root:
        os.environ.pop("DELEGATE_MODEL_APPLY", None)
        apply_tests(root)
    with tempfile.TemporaryDirectory() as root:
        os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(root, "q", "new-models.json")
        os.environ.pop("DELEGATE_MODEL_SCAN", None)
        cfg = config_dir(root)

        record("1. no queue file reads as an empty queue, and a scan is due",
               model_queue.pending() == [] and model_queue.due())

        added = model_queue.scan(config_dir=cfg, fixture_dir=FIXTURES,
                                 present={"codex", "agy", "grok"})
        models = [(m["harness"], m["model"]) for m in model_queue.pending()]
        record("2. a scan queues the models no Lane runs, not new efforts of a model one does",
               models == [("codex", "gpt-6-astra"), ("codex", "gpt-5.5"), ("agy", "gemini-3.1-pro"),
                          ("agy", "claude-opus-5-5")]
               and all(m["via"] == "scan" and m["first_seen"] for m in added)
               and not model_queue.due(),
               repr(models))

        again = model_queue.scan(config_dir=cfg, fixture_dir=FIXTURES,
                                 present={"codex", "agy", "grok"})
        first = model_queue.pending()[0]["first_seen"]
        model_queue.note([{"harness": "codex", "model": "gpt-6-astra"}], "asked")
        record("3. a model already queued is not queued twice and keeps its first sighting",
               again == [] and len(model_queue.pending()) == 4
               and model_queue.pending()[0]["first_seen"] == first
               and model_queue.pending()[0]["via"] == "scan")

        later = model_queue._now() + model_queue.SCAN_EVERY + timedelta(minutes=1)
        record("4. a scan is due again a day after the last",
               model_queue.due(now=later) and not model_queue.due())

        os.environ["DELEGATE_MODEL_SCAN"] = "off"
        with open(model_queue.path(), encoding="utf-8") as f:
            doc = json.load(f)
        doc["checked_at"] = None
        with open(model_queue.path(), "w", encoding="utf-8") as f:
            json.dump(doc, f)
        record("5. DELEGATE_MODEL_SCAN=off starts no scan, however due",
               model_queue.due() and model_queue.kick(cfg) is False and model_queue.due())
        os.environ.pop("DELEGATE_MODEL_SCAN")

        lines = setup_tui.refresh_lines({"models": [], "removed": [], "notices": [],
                                         "queued": model_queue.pending()}, width=200)
        record("6. the wizard's start facts name what dispatch noticed",
               any(line.startswith("Dispatch noticed (4): gpt-6-astra, gpt-5.5, gemini-3.1-pro, claude-opus-5-5")
                   for line in lines),
               repr(lines))

        setup.clear_queue(None)
        kept = len(model_queue.pending())
        setup.clear_queue({"models": [], "queued": model_queue.pending()})
        record("7. a write after a run that saw the queue empties it; one that saw none keeps it",
               kept == 4 and model_queue.pending() == [])

        # dispatch naming a model no Lane runs queues it, and still refuses
        env = dict(os.environ, DELEGATE_MODEL_SCAN="off", DELEGATE_CACHE=os.path.join(root, "usage.json"))
        brief = os.path.join(root, "brief.md")
        with open(brief, "w") as f:
            f.write("ping\n")
        res = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "delegate.py"), "dispatch", "--model", "gpt-9-nova",
             "--harness", "codex", "--class", "scout", "--brief", brief, "--cwd", root,
             "--config-dir", cfg],
            capture_output=True, text=True, env=env, timeout=60)
        queued = [(m["harness"], m["model"], m["via"]) for m in model_queue.pending()]
        record("8. dispatch --model naming a model no Lane runs refuses and queues it",
               res.returncode == 2 and "noted for the next delegate global" in res.stderr
               and queued == [("codex", "gpt-9-nova", "asked")],
               f"rc={res.returncode} stderr={res.stderr!r} queued={queued}")

    if failures:
        print(f"FAIL: {len(failures)} tests failed")
        sys.exit(1)
    print("all model queue tests passed")


if __name__ == "__main__":
    main()
