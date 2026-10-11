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
import harnesses  # noqa: E402
import rank  # noqa: E402
import usage  # noqa: E402

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


EVERY = set(harnesses.NAMES)
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
        rows = rank.rank("impl", cat, usage.Snapshot.of(doc), EVERY)
        pick = rows[0]["lane"] if rows and rows[0]["pick"] else None
        ok = pick == expected and (reason is None or rows[0]["reason"].startswith(reason))
        record(name, ok, f"pick={pick} reason={rows[0]['reason'] if rows else None}")


def test_gate_veto_is_named():
    cat = catalog_with({})
    rows = rank.rank("impl", cat, usage.Snapshot.of(meters(codex=(0.05, 2.0), grok=(0.5, 0.5))), EVERY)
    terra = next(r for r in rows if r["lane"] == "terra-high@codex")
    record("Gate: the vetoed Lane says it is under the Gate",
           terra["cause"] == "gate" and "5% left < gate 10%" in terra["reason"], terra["reason"])


def run_eval(name):
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "evals.py"), name, "--offline"],
                          capture_output=True, text=True)
    lines = proc.stdout.splitlines()
    return proc.returncode, lines, proc.stderr


def test_offline_ping():
    rc, lines, err = run_eval("ping")
    verdicts = {line.split()[2].rstrip(":"): line.split()[0] for line in lines if len(line.split()) > 2}
    relayed = [h for h in harnesses.NAMES if verdicts.get(h) == "pass"]
    record("eval 1 offline: every relayed harness answers pong, none fails",
           rc == 0 and "fail" not in verdicts.values() and len(relayed) >= 3,
           f"rc={rc} lines={lines} stderr={err[-300:]}")
    record("eval 1 offline: one line per harness",
           sorted(verdicts) == sorted(harnesses.NAMES), f"{lines}")


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
        os.remove(os.path.join(sandbox.world.bin_dir, "grok"))
        verdict, detail, _ = evals.ping_one(sandbox, "grok")
        record("eval 1: a harness whose CLI is absent is skipped, not failed",
               verdict == "skip" and "not installed" in detail, f"{verdict} {detail}")
    finally:
        sandbox.close()


def test_host_seatbelt_never_reaches_the_offline_world():
    # A shell inside a Seatbelt that refuses a nested one (a Claude Code Bash
    # sandbox on a Mac) has a sandbox-exec like this one on its PATH, after
    # the world's bin directory. The world's own sandbox-exec must answer
    # first, or codex's preflight blocks the offline ping.
    import evals
    sandbox = evals.Sandbox(offline=True)
    try:
        host_bin = os.path.join(sandbox.root, "host-bin")
        os.makedirs(host_bin)
        refusing = os.path.join(host_bin, "sandbox-exec")
        with open(refusing, "w") as f:
            f.write("#!/bin/sh\necho 'sandbox-exec: sandbox_apply: Operation not permitted' >&2\nexit 71\n")
        os.chmod(refusing, 0o755)
        path = sandbox.env["PATH"].split(os.pathsep)
        after = path.index(sandbox.world.bin_dir) + 1
        sandbox.env["PATH"] = os.pathsep.join(path[:after] + [host_bin] + path[after:])
        verdict, detail, _ = evals.ping_one(sandbox, "codex")
        record("eval 1 offline: the host's Seatbelt never reaches the offline world",
               verdict == "pass", f"{verdict} {detail}")
    finally:
        sandbox.close()


def test_offline_world_keeps_the_host_out():
    # The host names an orchestrator, sets Claude Code's marker and has a
    # Ledger of its own; none of it reaches the world's env. A stub replaces a
    # linked tool without writing through the link.
    import evals
    root = tempfile.mkdtemp(prefix="delegate-eval-world-")
    host = {"DELEGATE_ORCHESTRATOR": "codex", "CLAUDECODE": "1", "DELEGATE_LEDGER": "/host/ledger.jsonl"}
    saved = {k: os.environ.get(k) for k in host}
    os.environ.update(host)
    try:
        world = evals.OfflineWorld(root)
        env = world.env
        sh = os.path.join(world.bin_dir, "sh")
        linked = os.path.islink(sh)
        world.stub("sh", "exit 3\n")
        ran = subprocess.run([sh], env=env).returncode
        seen = {k: env.get(k) for k in ("DELEGATE_ORCHESTRATOR", "CLAUDECODE", "DELEGATE_LEDGER",
                                        "DELEGATE_ORCHESTRATORS_DIR", "DELEGATE_RUNS_DIR", "ADS_DIR")}
        record("the offline world: no host orchestrator, marker or Ledger reaches its env, and a stub replaces a link",
               seen == {"DELEGATE_ORCHESTRATOR": None, "CLAUDECODE": None, "DELEGATE_LEDGER": world.ledger_path,
                        "DELEGATE_ORCHESTRATORS_DIR": world.orchestrators_dir,
                        "DELEGATE_RUNS_DIR": world.runs_dir, "ADS_DIR": world.ads_dir}
               and os.listdir(world.orchestrators_dir) == []
               and env["PATH"].split(os.pathsep)[0] == world.bin_dir
               and linked and not os.path.islink(sh) and ran == 3,
               f"seen={seen} linked={linked} ran={ran}")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(root)


def test_equivalence_reads_the_runs_own_files():
    # Eval 3 compares what the orchestrator gets back. A Run holds its own
    # files whatever relay ran it, so two Runs that left no relay file at all
    # are still equivalent, and a Run that lost its return is not.
    import evals
    root = tempfile.mkdtemp(prefix="delegate-eval-runs-")
    try:
        ret = {"status": "done", "deliverable": "pong", "evidence": [], "open_questions": [],
               "changed_files": []}

        def run_dir(name, files):
            d = os.path.join(root, name)
            os.makedirs(d)
            for file in files:
                with open(os.path.join(d, file), "w", encoding="utf-8") as f:
                    if file == "dispatch.json":
                        json.dump({"lane": "luna-low@codex", "status": "done"}, f)
                    elif file == "return.json":
                        json.dump(ret, f)
                    else:
                        f.write("the prompt\n")
            return d

        every = ("dispatch.json", "prompt.md", "return.json")
        reference, other = run_dir("reference", every), run_dir("other", every)
        no_return = run_dir("no-return", ("dispatch.json", "prompt.md"))
        same, missing = evals.equivalent(reference, other), evals.equivalent(reference, no_return)
        record("eval 3: Runs are equivalent by the Run's own files, with no relay file named",
               same is None and missing == "missing return.json", f"same={same} missing={missing}")
    finally:
        shutil.rmtree(root)


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
    test_equivalence_reads_the_runs_own_files()
    test_offline_world_keeps_the_host_out()
    test_not_installed_is_skip()
    test_host_seatbelt_never_reaches_the_offline_world()
    test_offline_ping()
    test_offline_orchestrate()
    sys.exit(1 if fails else 0)
