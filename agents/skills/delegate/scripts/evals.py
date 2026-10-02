#!/usr/bin/env python3
"""evals.py — end-to-end evals for delegate (any-harness ticket 10).

Three evals, as Orin set them out in review on 2026-10-02. They are the
baseline every later change to the skill keeps passing.

  1. ping         For each harness whose CLI is installed, send a trivial job
                  ("reply pong") on one of its Lanes and check that it comes
                  back with a valid return.json. A harness that is not
                  installed is skipped, not failed.
  2. routing      Gate veto, Pace order and a Margin steal on fixture Meters.
                  Offline and deterministic; it lives in tests/test_evals.py
                  and runs in `make test`.
  3. orchestrate  The same ping job, sent through the skill from each harness
                  that can orchestrate, produces an equivalent run directory
                  and return.json.

Each prints one line per harness, `pass`, `skip` or `fail`, and exits 1 when
any line is a fail.

    python3 evals.py ping [--offline] [--harness H ...] [--keep]
    python3 evals.py orchestrate [--offline] [--harness H ...] [--keep]

--offline runs against the fake relay in tests/fake-ads and stub harness CLIs,
with the sample catalog and fixture Meters, so a machine with no CLI still
exercises the whole path. Without it the evals use this machine's catalog,
CLIs and relays, and spend a little real quota: one tiny job per harness.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import catalog  # noqa: E402
import rank  # noqa: E402

# The evals drive delegate the way a harness does: through the `delegate`
# command, which is the contract.
DELEGATE = [sys.executable, os.path.join(SKILL_DIR, "..", "..", "..", "bin", "delegate")]
ADS_SH = os.path.join(HERE, "ads.sh")
SAMPLES_DIR = os.path.join(SKILL_DIR, "assets", "samples")
SCHEMA_PATH = os.path.join(SKILL_DIR, "assets", "schemas", "return.json")
FAKE_RELAY = os.path.join(SKILL_DIR, "tests", "fake-ads", "relay.mjs")
FIXTURE_METERS = os.path.join(SKILL_DIR, "tests", "fixture", "meters.json")

PING_CLASS = "scout"
PING_BRIEF = """# Objective
Reply with the single word pong. Read no files and run no commands.

# Definition of done
The deliverable is exactly `pong`.
"""

# How each harness that can orchestrate is started headless with one prompt,
# which takes the place of "{prompt}" in its argv. These are the documented
# headless forms; they are not checked by the offline eval, which stands a
# stub in for each CLI, and Orin's live run is what proves them. A harness
# not listed here is reported as skipped by `orchestrate`.
ORCHESTRATOR_COMMANDS = {
    # `/delegate` must be typed: the skill is user-invoked only, and in -p mode
    # the leading slash command is the user's own invocation.
    "claude": {
        "argv": ["claude", "-p", "{prompt}", "--allowedTools", "Bash,Read"],
        "prompt": "/delegate {cls} job, brief {brief}, working directory {cwd}. "
                  "When it finishes, print the run directory.",
    },
    # Codex needs no sandbox here: delegate itself starts other CLIs, which
    # need the network and their own homes.
    "codex": {
        "argv": ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "{prompt}"],
        "prompt": "I am explicitly asking you to use the delegate skill. Delegate the job in "
                  "{brief} as class {cls}, working directory {cwd}. When it finishes, print "
                  "the run directory.",
    },
}

# The files every relayed run directory holds when it finishes. Others (final.txt,
# events.jsonl, brief.txt) depend on the harness and are not compared.
RUN_FILES = ("dispatch.json", "prompt.md", "relay.stdout", "relay.stderr", "result.json", "return.json")


def validate_return(doc):
    """Problems with a return.json document against assets/schemas/return.json.

    The schema is small and fixed, so this checks it by hand rather than pull
    in a JSON Schema library: required keys, no others, and each type.
    """
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    if not isinstance(doc, dict):
        return ["not an object"]
    problems = []
    required = schema["required"]
    for key in required:
        if key not in doc:
            problems.append(f"missing {key}")
    for key in doc:
        if key not in schema["properties"]:
            problems.append(f"unexpected key {key}")
    if doc.get("status") not in schema["properties"]["status"]["enum"]:
        problems.append(f"status {doc.get('status')!r} is not one of done, partial, blocked")
    if not isinstance(doc.get("deliverable"), str):
        problems.append("deliverable is not a string")
    for key in ("evidence", "open_questions", "changed_files"):
        if key in doc and not isinstance(doc[key], list):
            problems.append(f"{key} is not a list")
    return problems


def check_ping_run(run_dir):
    """None when run_dir holds a finished ping that answered pong, else why not."""
    path = os.path.join(run_dir, "return.json")
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        return f"no readable return.json in {run_dir}: {e}"
    problems = validate_return(doc)
    if problems:
        return f"return.json invalid: {'; '.join(problems)}"
    if doc["status"] != "done":
        return f"status {doc['status']}: {doc['deliverable'][:120]}"
    if "pong" not in doc["deliverable"].lower():
        return f"deliverable is not pong: {doc['deliverable'][:120]!r}"
    return None


class Sandbox:
    """Where an eval runs: its brief, working directory, runs directory and env.

    Live, it uses this machine's catalog, relays and CLIs. Offline, it builds a
    throwaway world: the sample catalog, the fake relay standing in for every
    harness's relay, a stub CLI per harness and fixture Meters.
    """

    def __init__(self, offline, keep=False):
        self.offline = offline
        self.root = tempfile.mkdtemp(prefix="delegate-eval-")
        self.keep = keep
        self.cwd = os.path.join(self.root, "work")
        self.runs_dir = os.path.join(self.root, "runs")
        os.makedirs(self.cwd)
        os.makedirs(self.runs_dir)
        self.brief = os.path.join(self.root, "ping.md")
        self.env = dict(os.environ)
        self.env["DELEGATE_RUNS_DIR"] = self.runs_dir
        self.config_dir = None
        self.ads_dir = None
        self.meters = None
        brief = PING_BRIEF
        if offline:
            brief += "\n" + self._build_offline_world() + "\n"
        with open(self.brief, "w", encoding="utf-8") as f:
            f.write(brief)

    def _build_offline_world(self):
        self.config_dir = os.path.join(self.root, "config")
        os.makedirs(self.config_dir)
        for name in ("lanes.json", "routing.json"):
            shutil.copy(os.path.join(SAMPLES_DIR, name), self.config_dir)
        self.meters = FIXTURE_METERS

        self.ads_dir = os.path.join(self.root, "ads")
        for h in catalog.HARNESSES:
            scripts = os.path.join(self.ads_dir, "skills", f"{h}-delegate", "scripts")
            os.makedirs(scripts)
            shutil.copy(FAKE_RELAY, os.path.join(scripts, "relay.mjs"))

        bin_dir = os.path.join(self.root, "bin")
        os.makedirs(bin_dir)
        # ads.sh checks the clone's HEAD against its pin; answer with the pin.
        pin = next(line.split("=", 1)[1].strip() for line in open(ADS_SH) if line.startswith("ADS_COMMIT="))
        real_git = shutil.which("git") or "/usr/bin/git"
        self._stub(bin_dir, "git", f'for a in "$@"; do [ "$a" = HEAD ] && {{ echo {pin}; exit 0; }}; done\nexec {real_git} "$@"\n')
        for h in catalog.HARNESSES:
            self._stub(bin_dir, h, "exit 0\n")
        # Real node, sh and python3 stay reachable without exposing a real
        # harness CLI that shares their directory.
        for tool in ("node", "sh", "python3"):
            src = shutil.which(tool)
            if src:
                os.symlink(src, os.path.join(bin_dir, tool))
        self.env["PATH"] = os.pathsep.join([bin_dir, "/bin", "/usr/bin"])
        self.env["DELEGATE_LEDGER"] = os.path.join(self.root, "ledger.jsonl")
        self.env["DELEGATE_CACHE"] = os.path.join(self.root, "usage.json")
        self.env["DELEGATE_CODEX_HOME"] = os.path.join(self.root, "codex-home")
        self.env["ADS_DIR"] = self.ads_dir
        self.bin_dir = bin_dir

        # The fake relay answers with the final message this file holds.
        final = os.path.join(self.root, "final.txt")
        with open(final, "w", encoding="utf-8") as f:
            f.write('pong\n{"status": "done", "deliverable": "pong", "evidence": [], '
                    '"open_questions": [], "changed_files": []}\n')
        return f"fake-relay: final={final}"

    @staticmethod
    def _stub(bin_dir, name, body):
        path = os.path.join(bin_dir, name)
        with open(path, "w") as f:
            f.write("#!/bin/sh\n" + body)
        os.chmod(path, 0o755)

    def common_args(self):
        args = ["--runs-dir", self.runs_dir]
        if self.config_dir:
            args += ["--config-dir", self.config_dir]
        if self.ads_dir:
            args += ["--ads-dir", self.ads_dir]
        return args

    def installed(self, harness):
        return shutil.which(harness, path=self.env.get("PATH")) is not None

    def run_dirs(self):
        return {os.path.join(self.runs_dir, d) for d in os.listdir(self.runs_dir)}

    def close(self):
        if self.keep:
            print(f"eval: kept {self.root}")
        else:
            shutil.rmtree(self.root, ignore_errors=True)


def ping_lane(sandbox, harness):
    """The Lane a ping runs on for this harness: its first Pick at any Tier.

    Ranking over every Tier with only this harness present picks the lowest
    Tier, which is the cheapest Lane to spend a ping on, and still honours the
    Gate. Returns (lane, None) or (None, why there is none).
    """
    cat = catalog.load_catalog(cwd=sandbox.cwd, config_dir=sandbox.config_dir)
    if sandbox.meters:
        with open(sandbox.meters, encoding="utf-8") as f:
            meters = json.load(f)
    else:
        meters = rank.load_usage(cat, refresh=False)
    rows = [r for r in rank.rank_range(cat, meters, {harness}) if r["harness"] == harness]
    if not rows:
        return None, "no Lane in the catalog"
    if rows[0]["pick"]:
        return rows[0]["lane"], None
    return None, "no eligible Lane: " + "; ".join(r["reason"] for r in rows[:3])


def run_dir_from(stdout):
    for line in stdout.splitlines():
        m = re.match(r"^delegate: \S+ status=\S+ secs=\S+ run=(.+)$", line)
        if m:
            return m.group(1).strip()
    return None


def ping_one(sandbox, harness):
    """(verdict, detail, run_dir) for one harness's ping."""
    if not sandbox.installed(harness):
        return "skip", f"{harness} CLI not installed", None
    try:
        lane, why = ping_lane(sandbox, harness)
    except catalog.CatalogError as e:
        return "fail", str(e), None
    if lane is None:
        return "skip", why, None
    cmd = DELEGATE + ["dispatch", "--lane", lane, "--class", PING_CLASS,
           "--brief", sandbox.brief, "--cwd", sandbox.cwd] + sandbox.common_args()
    if sandbox.offline:
        cmd.append("--no-probe")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=sandbox.env)
    native = re.search(r"^delegate: native lane=\S+ agent=(\S+)", proc.stdout, re.M)
    if native:
        return "skip", f"{lane} is a native lane; spawn {native.group(1)} from the orchestrator", None
    run_dir = run_dir_from(proc.stdout)
    if run_dir is None:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        return "fail", f"{lane}: no run directory (exit {proc.returncode}): {tail[0]}", None
    problem = check_ping_run(run_dir)
    if problem:
        return "fail", f"{lane}: {problem}", run_dir
    return "pass", f"{lane} answered pong ({run_dir})", run_dir


def eval_ping(sandbox, harnesses):
    results = {}
    for h in harnesses:
        results[h] = ping_one(sandbox, h)
    return results


def equivalent(reference_dir, run_dir):
    """None when run_dir is equivalent to reference_dir, else why not.

    Equivalent means the same Lane, the same files and the same return.json:
    what the orchestrator gets back does not depend on which harness asked.
    """
    for name in RUN_FILES:
        if not os.path.isfile(os.path.join(run_dir, name)):
            return f"missing {name}"
    with open(os.path.join(reference_dir, "dispatch.json")) as f:
        ref_lane = json.load(f).get("lane")
    with open(os.path.join(run_dir, "dispatch.json")) as f:
        lane = json.load(f).get("lane")
    if lane != ref_lane:
        return f"ran {lane}, the reference ran {ref_lane}"
    with open(os.path.join(reference_dir, "return.json")) as f:
        ref_return = json.load(f)
    with open(os.path.join(run_dir, "return.json")) as f:
        got = json.load(f)
    if got != ref_return:
        return "return.json differs from the reference"
    return None


def orchestrate_one(sandbox, orchestrator, reference):
    """(verdict, detail) for one orchestrator sending the ping through the skill."""
    spec = ORCHESTRATOR_COMMANDS.get(orchestrator)
    if spec is None:
        return "skip", f"no headless command known for {orchestrator}"
    if not sandbox.offline and not sandbox.installed(orchestrator):
        return "skip", f"{orchestrator} CLI not installed"
    prompt = spec["prompt"].format(cls=PING_CLASS, brief=sandbox.brief, cwd=sandbox.cwd)
    before = sandbox.run_dirs()
    if sandbox.offline:
        # The stub orchestrator does what the skill tells any orchestrator to
        # do: one `delegate run` from a shell. It runs with the env the real
        # harness would have, so nothing about the caller leaks in.
        cmd = DELEGATE + ["run", PING_CLASS, "--brief", sandbox.brief,
               "--cwd", sandbox.cwd, "--meters", sandbox.meters, "--no-probe"] + sandbox.common_args()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=sandbox.env)
    else:
        argv = [prompt if a == "{prompt}" else a for a in spec["argv"]]
        proc = subprocess.run(argv, capture_output=True, text=True,
                              env=sandbox.env, cwd=sandbox.cwd, timeout=1800)
    new = sorted(sandbox.run_dirs() - before)
    if not new:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        return "fail", f"no run directory (exit {proc.returncode}): {tail[0]}"
    run_dir = new[-1]
    problem = check_ping_run(run_dir)
    if problem:
        return "fail", problem
    if reference is not None:
        problem = equivalent(reference, run_dir)
        if problem:
            return "fail", f"{run_dir}: {problem}"
    return "pass", f"equivalent run ({run_dir})"


def eval_orchestrate(sandbox, orchestrators):
    # The reference is a plain dispatch of the Lane the class ranks first; an
    # orchestrator's run is compared with it.
    reference = None
    try:
        catalog.load_catalog(cwd=sandbox.cwd, config_dir=sandbox.config_dir)
    except catalog.CatalogError as e:
        return {o: ("fail", str(e)) for o in orchestrators}
    if sandbox.offline:
        cmd = DELEGATE + ["run", PING_CLASS, "--brief", sandbox.brief,
               "--cwd", sandbox.cwd, "--meters", sandbox.meters, "--no-probe"] + sandbox.common_args()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=sandbox.env)
        reference = run_dir_from(proc.stdout)
    return {o: orchestrate_one(sandbox, o, reference) for o in orchestrators}


def print_results(name, results):
    failed = False
    for harness, result in results.items():
        verdict, detail = result[0], result[1]
        failed = failed or verdict == "fail"
        print(f"{verdict:<4} {name} {harness}: {detail}")
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="evals.py", description="delegate's end-to-end evals")
    parser.add_argument("eval", choices=("ping", "orchestrate"))
    parser.add_argument("--offline", action="store_true", help="fake relay, stub CLIs, sample catalog")
    parser.add_argument("--harness", action="append", default=None, help="limit to this harness (repeatable)")
    parser.add_argument("--keep", action="store_true", help="keep the sandbox directory")
    args = parser.parse_args(argv)

    harnesses = args.harness or list(catalog.HARNESSES)
    sandbox = Sandbox(args.offline, keep=args.keep)
    try:
        if args.eval == "ping":
            return print_results("ping", eval_ping(sandbox, harnesses))
        orchestrators = args.harness or list(catalog.HARNESSES)
        return print_results("orchestrate", eval_orchestrate(sandbox, orchestrators))
    finally:
        sandbox.close()


if __name__ == "__main__":
    sys.exit(main())
