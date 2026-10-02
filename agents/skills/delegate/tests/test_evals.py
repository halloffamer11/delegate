#!/usr/bin/env python3
"""test_evals.py — delegate's evals that run offline (any-harness ticket 10).

Eval 2, Gate and load balancing on simulated usage, lives here: fixture Meters
at chosen Remaining and Pace drive `rank`, and each case states its expected
Pick. Evals 1 and 3 run here against the fake relay and stub CLIs, so a machine
with no harness CLI still exercises the dispatch path.

Run: python3 tests/test_evals.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
sys.path.insert(0, SCRIPTS)

# No Git root above the cwd, so no project overlay leaks in.
_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_CWD.name)

import catalog  # noqa: E402
import rank  # noqa: E402

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}", file=sys.stderr)


def meters(**by_meter):
    """A usage document: meter name -> (Remaining, Pace)."""
    return {
        "probed_at": 1700000000,
        "lanes": [
            {"lane": name, "harness": name.split("-")[0], "r": r, "pace": pace,
             "remaining_5h": r, "remaining_weekly": r, "status": "ok"}
            for name, (r, pace) in by_meter.items()
        ],
    }


def catalog_with(lane_overrides):
    """The sample catalog with some Lane fields replaced, loaded and validated."""
    d = tempfile.mkdtemp(prefix="delegate-eval-cat-")
    with open(os.path.join(SAMPLES, "lanes.json")) as f:
        lanes = json.load(f)
    for lane, fields in lane_overrides.items():
        lanes["lanes"][lane].update(fields)
    with open(os.path.join(d, "lanes.json"), "w") as f:
        json.dump(lanes, f)
    shutil.copy(os.path.join(SAMPLES, "routing.json"), d)
    try:
        return catalog.load_catalog(config_dir=d)
    finally:
        shutil.rmtree(d)


EVERY = set(catalog.HARNESSES)
# impl's Range in the sample routing is Tier 2 to 3. Its Tier 2 holds
# terra-high@codex (Meter codex) and grok46-high@grok (Meter grok); Tier 3 holds
# sol-high@codex, on the same codex Meter. Margin is 0.2 and the Gate 10%.
CASES = [
    # (name, lane overrides, meters, expected Pick, expected reason prefix)
    ("Gate: a Lane under the Gate is vetoed and the other Tier 2 Lane is picked",
     {}, meters(codex=(0.05, 2.0), grok=(0.5, 0.5)),
     "grok46-high@grok", "pick"),
    ("Pace: with no Order, the higher Pace leads its Tier",
     {}, meters(codex=(0.6, 0.9), grok=(0.6, 0.8)),
     "terra-high@codex", "pick"),
    ("Pace: the other way round, the other Lane leads",
     {}, meters(codex=(0.6, 0.8), grok=(0.6, 0.9)),
     "grok46-high@grok", "pick"),
    ("Margin: a Lane lower in the Order steals when its Pace beats the Pick by the Margin",
     {"terra-high@codex": {"order": 1}, "grok46-high@grok": {"order": 2}},
     meters(codex=(0.6, 0.5), grok=(0.6, 0.75)),
     "grok46-high@grok", "stolen by pace"),
    ("Margin: short of the Margin, the Order holds",
     {"terra-high@codex": {"order": 1}, "grok46-high@grok": {"order": 2}},
     meters(codex=(0.6, 0.5), grok=(0.6, 0.65)),
     "terra-high@codex", "pick"),
    ("Gate and overflow: every Tier 2 and 3 Lane under the Gate stops impl",
     {}, meters(codex=(0.05, 1.0), grok=(0.05, 1.0)),
     None, None),
]


def test_routing_cases():
    for name, overrides, doc, expected, reason in CASES:
        cat = catalog_with(overrides)
        rows = rank.rank("impl", cat, doc, EVERY)
        pick = rows[0]["lane"] if rows and rows[0]["pick"] else None
        ok = pick == expected and (reason is None or rows[0]["reason"].startswith(reason))
        record(name, ok, f"pick={pick} reason={rows[0]['reason'] if rows else None}")


def test_gate_veto_is_named():
    cat = catalog_with({})
    rows = rank.rank("impl", cat, meters(codex=(0.05, 2.0), grok=(0.5, 0.5)), EVERY)
    terra = next(r for r in rows if r["lane"] == "terra-high@codex")
    record("Gate: the vetoed Lane says it is under the Gate",
           terra["veto"] == "gate" and "5% left < gate 10%" in terra["reason"], terra["reason"])


def run_eval(name):
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "evals.py"), name, "--offline"],
                          capture_output=True, text=True)
    lines = proc.stdout.splitlines()
    return proc.returncode, lines, proc.stderr


def test_offline_ping():
    rc, lines, err = run_eval("ping")
    verdicts = {line.split()[2].rstrip(":"): line.split()[0] for line in lines if len(line.split()) > 2}
    relayed = [h for h in catalog.HARNESSES if verdicts.get(h) == "pass"]
    record("eval 1 offline: every relayed harness answers pong, none fails",
           rc == 0 and "fail" not in verdicts.values() and len(relayed) >= 3,
           f"rc={rc} lines={lines} stderr={err[-300:]}")
    record("eval 1 offline: one line per harness",
           sorted(verdicts) == sorted(catalog.HARNESSES), f"{lines}")


def test_offline_orchestrate():
    rc, lines, err = run_eval("orchestrate")
    passes = [line for line in lines if line.startswith("pass")]
    record("eval 3 offline: each known orchestrator gets an equivalent run, none fails",
           rc == 0 and len(passes) >= 2 and not any(line.startswith("fail") for line in lines),
           f"rc={rc} lines={lines} stderr={err[-300:]}")


def test_not_installed_is_skip():
    sys.path.insert(0, SCRIPTS)
    import evals
    sandbox = evals.Sandbox(offline=True)
    try:
        os.remove(os.path.join(sandbox.bin_dir, "grok"))
        verdict, detail, _ = evals.ping_one(sandbox, "grok")
        record("eval 1: a harness whose CLI is absent is skipped, not failed",
               verdict == "skip" and "not installed" in detail, f"{verdict} {detail}")
    finally:
        sandbox.close()


def test_validate_return():
    import evals
    good = {"status": "done", "deliverable": "pong", "evidence": [], "open_questions": [], "changed_files": []}
    bad = dict(good, status="finished", extra=1)
    del bad["evidence"]
    problems = evals.validate_return(bad)
    record("return.json validation accepts the contract and names each break",
           evals.validate_return(good) == [] and len(problems) == 3, f"{problems}")


if __name__ == "__main__":
    test_routing_cases()
    test_gate_veto_is_named()
    test_validate_return()
    test_not_installed_is_skip()
    test_offline_ping()
    test_offline_orchestrate()
    sys.exit(1 if fails else 0)
