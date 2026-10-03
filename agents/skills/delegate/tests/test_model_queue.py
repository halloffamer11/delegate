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


def main():
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
               models == [("codex", "gpt-6-astra"), ("codex", "gpt-5.5"), ("agy", "gemini-3.1-pro")]
               and all(m["via"] == "scan" and m["first_seen"] for m in added)
               and not model_queue.due(),
               repr(models))

        again = model_queue.scan(config_dir=cfg, fixture_dir=FIXTURES,
                                 present={"codex", "agy", "grok"})
        first = model_queue.pending()[0]["first_seen"]
        model_queue.note([{"harness": "codex", "model": "gpt-6-astra"}], "asked")
        record("3. a model already queued is not queued twice and keeps its first sighting",
               again == [] and len(model_queue.pending()) == 3
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
               any(line.startswith("Dispatch noticed (3): gpt-6-astra, gpt-5.5, gemini-3.1-pro")
                   for line in lines),
               repr(lines))

        setup.clear_queue(None)
        kept = len(model_queue.pending())
        setup.clear_queue({"models": [], "queued": model_queue.pending()})
        record("7. a write after a run that saw the queue empties it; one that saw none keeps it",
               kept == 3 and model_queue.pending() == [])

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
