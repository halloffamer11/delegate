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
import catalog  # noqa: E402
import catalog_commit  # noqa: E402
import discover  # noqa: E402
import model_queue  # noqa: E402
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


def start_facts(cfg):
    """The wizard's start facts from a read that takes the queue, as the full
    wizard reads it, with no refresh run."""
    snap = catalog_commit.read(cfg, queue=True)
    return setup_tui.start_facts(snap.files["lanes"], snap.files["routing"], None, None,
                                 width=200, queued=snap.queued, applied=snap.applied)


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
    # the catalog commit backs up the lanes.json it replaces beside the catalog
    folder = os.path.join(cfg, "backups")
    backups = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    record("9. a newer version of a model the catalog runs takes its lane's place, tier and all",
           "sol-high@codex" not in after["lanes"] and len(new) == 1
           and names.index(new[0]) == old_at and lane.get("tier") == 3 and lane.get("effort") == "high"
           and "enabled" not in lane and len(backups) == 1 and backups[0].startswith("lanes-")
           and load(os.path.join(folder, backups[0])) == before
           and not os.path.exists(os.path.join(root, "q9", "lanes-backups"))
           and [(a["old"], a["new"]) for a in model_queue.applied()] == [("sol-high@codex", new[0])],
           repr((new, names, lane, backups, model_queue.applied())))
    lines = start_facts(cfg)
    record("9b. the wizard's start facts name the swap",
           any(line.startswith(f"Dispatch swapped in: sol-high@codex -> {new[0]}") for line in lines),
           repr(lines))
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

    os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(root, "q13", "new-models.json")
    cfg = config_dir(os.path.join(root, "a13"))
    path = os.path.join(cfg, "lanes.json")
    real_discover = discover.discover

    def listing(lanes_doc, **kwargs):
        # a catalog set lands while the scan lists the harnesses' models
        doc = load(path)
        doc["lanes"]["sol-high@codex"]["tier"] = 1
        catalog.write_json(path, doc)
        return real_discover(lanes_doc, **kwargs)

    discover.discover = listing
    try:
        model_queue.scan(config_dir=cfg, fixture_dir=fixtures, present=present)
    finally:
        discover.discover = real_discover
    after = load(path)
    queued = [(m["harness"], m["model"]) for m in model_queue.pending()]
    record("13. a scan whose catalog changed while it listed models writes nothing and still queues",
           after["lanes"]["sol-high@codex"]["tier"] == 1
           and not any(lane["model"] == "gpt-6.1-sol" for lane in after["lanes"].values())
           and not os.path.exists(os.path.join(cfg, "backups"))
           and ("codex", "gpt-6.1-sol") in queued and model_queue.applied() == [],
           repr((queued, model_queue.applied())))


def scan_imports_test(root):
    """A detached scan swaps a newer model into the catalog and writes it, and
    loads no module of the wizard to do it (deepening D2)."""
    cfg = config_dir(os.path.join(root, "a14"))
    fixtures = newer_fixtures(root)
    wizard = ("setup", "setup_tui", "bench", "bench_page", "effort")
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {SCRIPTS!r})\n"
        "import model_queue\n"
        f"model_queue.scan(config_dir={cfg!r}, fixture_dir={fixtures!r},\n"
        "                 present={'codex', 'agy', 'grok'})\n"
        f"print(json.dumps(sorted(m for m in {wizard!r} if m in sys.modules)))\n"
    )
    env = dict(os.environ, HOME=root, DELEGATE_MODEL_QUEUE=os.path.join(root, "q14", "new-models.json"))
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, cwd=root, timeout=120)
    try:
        loaded = json.loads(res.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        loaded = None
    swapped = any(lane["model"] == "gpt-6.1-sol"
                  for lane in load(os.path.join(cfg, "lanes.json"))["lanes"].values())
    record("14. the scan imports no wizard module",
           res.returncode == 0 and loaded == [] and swapped,
           f"rc={res.returncode} loaded={loaded} swapped={swapped} stderr={res.stderr[-400:]!r}")


def main():
    with tempfile.TemporaryDirectory() as root:
        os.environ.pop("DELEGATE_MODEL_APPLY", None)
        apply_tests(root)
    with tempfile.TemporaryDirectory() as root:
        scan_imports_test(root)
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

        lines = start_facts(cfg)
        record("6. the wizard's start facts name what dispatch noticed",
               any(line.startswith("Dispatch noticed (4): gpt-6-astra, gpt-5.5, gemini-3.1-pro, claude-opus-5-5")
                   for line in lines),
               repr(lines))

        # dispatch naming a model no Lane runs queues it, and still refuses;
        # on a queue of its own, so the entries above do not count
        os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(root, "q8", "new-models.json")
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
