#!/usr/bin/env python3
"""evals.py — end-to-end evals for delegate (any-harness ticket 10).

Three evals, as the user set them out in review on 2026-10-02. They are the
baseline every later change to the skill keeps passing.

  1. ping         For each harness whose CLI is installed, send a trivial job
                  ("reply pong") on one of its Lanes and check that it comes
                  back with a valid return.json. A harness that is not
                  installed is skipped, not failed.
  2. routing      Gate veto, Pace order and a Margin steal on fixture Meters.
                  Offline and deterministic; it lives in tests/test_evals.py
                  and runs in `make test`.
  3. orchestrate  The same ping job, sent through the skill from each
                  orchestrator profile with a headless launch, produces an
                  equivalent run directory and return.json.

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
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import catalog  # noqa: E402
import harnesses  # noqa: E402
import orchestrators  # noqa: E402
import rank  # noqa: E402
import runs  # noqa: E402

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

# How each orchestrator is started headless is its profile's `launch`
# (assets/orchestrators/, or a machine's own profile): an argv with "{prompt}"
# where the prompt goes, and the prompt. The offline eval stands a stub in for
# each CLI, so the user's live run is what proves them. An orchestrator with no
# launch is reported as skipped by `orchestrate`.

# The Run's own files, which every relayed Run holds when it finishes. What a
# relay leaves beside them depends on the relay and the harness, and is not
# compared.
RUN_FILES = ("dispatch.json", "prompt.md", "return.json")


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


class OfflineWorld:
    """A throwaway world where delegate runs needing no harness CLI, no relay
    clone and no network: the one the offline evals, test_dispatch and
    test_relay share.

    Under `root`, which the caller owns and removes, it holds the sample
    catalog, a fake ADS tree with the fake relay standing in for each registry
    relay, an empty orchestrator profile directory and a runs directory. Its
    bin directory holds a `git` that answers ads.sh's pin read (with
    $ADS_FAKE_GIT_SHA, when set, in place of the pin), one stub per harness
    CLI, a `sandbox-exec` that nests, and links to the real node, sh and
    python3. `env` puts that bin directory first on PATH and points every
    delegate path at the world, so nothing on the host reaches a Run: not its
    CLIs, its catalog, its Ledger, its Meters, its codex home, its Seatbelt or
    its orchestrator. A test replaces one CLI with `stub`.
    """

    def __init__(self, root):
        self.root = root
        self.config_dir = os.path.join(root, "config")
        self.ads_dir = os.path.join(root, "ads")
        self.bin_dir = os.path.join(root, "bin")
        self.runs_dir = os.path.join(root, "runs")
        self.orchestrators_dir = os.path.join(root, "orchestrators")
        self.ledger_path = os.path.join(root, "ledger.jsonl")
        self.cache_path = os.path.join(root, "usage.json")
        # A codex home of delegate's own changes the codex argv, so the world
        # names one that does not exist; the host's never reaches a case.
        self.codex_home = os.path.join(root, "codex-home")
        for d in (self.config_dir, self.bin_dir, self.runs_dir, self.orchestrators_dir):
            os.makedirs(d)

        for name in ("lanes.json", "routing.json"):
            shutil.copy(os.path.join(SAMPLES_DIR, name), self.config_dir)
        for h in harnesses.REGISTRY:
            scripts = os.path.join(self.ads_dir, "skills", h.relay, "scripts")
            os.makedirs(scripts, exist_ok=True)
            shutil.copy(FAKE_RELAY, os.path.join(scripts, "relay.mjs"))

        # ads.sh checks the clone's HEAD against its pin; answer with the pin.
        real_git = shutil.which("git") or "/usr/bin/git"
        self.stub("git", 'for a in "$@"; do\n'
                         f'  [ "$a" = HEAD ] && {{ echo "${{ADS_FAKE_GIT_SHA:-{_pinned_ads_commit()}}}"; exit 0; }}\n'
                         f'done\nexec {real_git} "$@"\n')
        for h in harnesses.REGISTRY:
            self.stub(h.binary, "exit 0\n")
        # The host's Seatbelt never reaches a Run: a sandbox-exec that nests
        # answers before the one a Mac keeps in /usr/bin.
        self.stub("sandbox-exec", "exit 0\n")
        # Real node, sh and python3 stay reachable without exposing a real
        # harness CLI that shares their directory.
        for tool in ("node", "sh", "python3"):
            src = shutil.which(tool)
            if src:
                os.symlink(src, os.path.join(self.bin_dir, tool))

        env = dict(os.environ)
        # No orchestrator is assumed: neither the host's choice nor any marker
        # a profile the world loads detects.
        env.pop("DELEGATE_ORCHESTRATOR", None)
        for profile in orchestrators.load([orchestrators.SHIPPED_DIR, self.orchestrators_dir]).values():
            for var in profile["detect_env"]:
                env.pop(var, None)
        env.update({
            "PATH": os.pathsep.join([self.bin_dir, "/bin", "/usr/bin"]),
            runs.LEDGER_ENV: self.ledger_path,
            "DELEGATE_CACHE": self.cache_path,
            # the world is stubs: no detached model scan runs against them
            "DELEGATE_MODEL_SCAN": "off",
            "ADS_DIR": self.ads_dir,
            "DELEGATE_CODEX_HOME": self.codex_home,
            "DELEGATE_ORCHESTRATORS_DIR": self.orchestrators_dir,
            "DELEGATE_RUNS_DIR": self.runs_dir,
        })
        self.env = env

    def stub(self, name, body):
        """Put a shell script running `body` at `name` in the bin directory,
        replacing what is there (a link is replaced, never written through).
        Returns its path."""
        path = os.path.join(self.bin_dir, name)
        if os.path.lexists(path):
            os.remove(path)
        with open(path, "w") as f:
            f.write("#!/bin/sh\n" + body)
        os.chmod(path, 0o755)
        return path


def _pinned_ads_commit():
    """The commit ads.sh pins, read from ads.sh itself, so the world follows
    each repin."""
    with open(ADS_SH) as f:
        for line in f:
            if line.startswith("ADS_COMMIT="):
                return line.split("=", 1)[1].strip()
    raise ValueError(f"no ADS_COMMIT= line in {ADS_SH}")


class Sandbox:
    """Where an eval runs: its brief, working directory, runs directory and env.

    Live, it uses this machine's catalog, relays and CLIs. Offline, it runs in
    an OfflineWorld (`world`) with fixture Meters, and the fake relay answers
    pong.
    """

    def __init__(self, offline, keep=False):
        self.offline = offline
        self.root = tempfile.mkdtemp(prefix="delegate-eval-")
        self.keep = keep
        self.cwd = os.path.join(self.root, "work")
        os.makedirs(self.cwd)
        self.brief = os.path.join(self.root, "ping.md")
        brief = PING_BRIEF
        if offline:
            self.world = OfflineWorld(self.root)
            self.env = self.world.env
            self.runs_dir = self.world.runs_dir
            self.config_dir = self.world.config_dir
            self.ads_dir = self.world.ads_dir
            self.meters = FIXTURE_METERS
            # The fake relay answers with the final message this file holds.
            final = os.path.join(self.root, "final.txt")
            with open(final, "w", encoding="utf-8") as f:
                f.write('pong\n{"status": "done", "deliverable": "pong", "evidence": [], '
                        '"open_questions": [], "changed_files": []}\n')
            brief += f"\nfake-relay: final={final}\n"
        else:
            self.world = None
            self.runs_dir = os.path.join(self.root, "runs")
            os.makedirs(self.runs_dir)
            self.env = dict(os.environ, DELEGATE_RUNS_DIR=self.runs_dir)
            self.config_dir = self.ads_dir = self.meters = None
        with open(self.brief, "w", encoding="utf-8") as f:
            f.write(brief)

    def common_args(self):
        args = ["--runs-dir", self.runs_dir]
        if self.config_dir:
            args += ["--config-dir", self.config_dir]
        if self.ads_dir:
            args += ["--ads-dir", self.ads_dir]
        return args

    def installed(self, harness):
        adapter = harnesses.get(harness)
        binary = adapter.binary if adapter is not None else harness
        return shutil.which(binary, path=self.env.get("PATH")) is not None

    def orchestrator_env(self, profile):
        """The env an orchestrator's shell gives delegate: no other
        orchestrator's markers. Offline, the stub sets this profile's own, as
        the real harness would; live, the harness sets them itself."""
        env = dict(self.env)
        env.pop("DELEGATE_ORCHESTRATOR", None)
        for other in orchestrators.load().values():
            for var in other["detect_env"]:
                env.pop(var, None)
        if self.offline:
            for var in profile["detect_env"]:
                env[var] = "1"
        return env

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
    """The run directory `delegate dispatch --json` or `run --json` printed, or None."""
    try:
        doc = json.loads(stdout)
    except ValueError:
        return None
    return doc.get("run") if isinstance(doc, dict) else None


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
           "--brief", sandbox.brief, "--cwd", sandbox.cwd,
           # A ping proves the relay, so no Lane runs natively, whoever runs the eval.
           "--orchestrator", "none", "--json"] + sandbox.common_args()
    if sandbox.offline:
        cmd.append("--no-probe")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=sandbox.env)
    run_dir = run_dir_from(proc.stdout)
    if run_dir is None:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        return "fail", f"{lane}: no run directory (exit {proc.returncode}): {tail[0]}", None
    problem = check_ping_run(run_dir)
    if problem:
        return "fail", f"{lane}: {problem}", run_dir
    return "pass", f"{lane} answered pong ({run_dir})", run_dir


def eval_ping(sandbox, names):
    results = {}
    for h in names:
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
    reference, got = runs.Run(reference_dir).read(), runs.Run(run_dir).read()
    ref_lane, lane = reference["dispatch"].get("lane"), got["dispatch"].get("lane")
    if lane != ref_lane:
        return f"ran {lane}, the reference ran {ref_lane}"
    if got["return"] != reference["return"]:
        return "return.json differs from the reference"
    return None


def orchestrate_one(sandbox, orchestrator, reference, profiles):
    """(verdict, detail) for one orchestrator sending the ping through the skill."""
    profile = profiles.get(orchestrator)
    if profile is None:
        return "skip", f"no orchestrator profile for {orchestrator}"
    spec = profile.get("launch")
    if not spec:
        return "skip", f"the {orchestrator} profile has no headless launch"
    binary = spec["argv"][0]
    if not sandbox.offline and not sandbox.installed(binary):
        return "skip", f"{binary} CLI not installed"
    prompt = spec["prompt"].format(cls=PING_CLASS, brief=sandbox.brief, cwd=sandbox.cwd)
    env = sandbox.orchestrator_env(profile)
    before = sandbox.run_dirs()
    if sandbox.offline:
        # The stub orchestrator does what the skill tells any orchestrator to
        # do: one `delegate run` from a shell, with the env its harness sets.
        cmd = DELEGATE + ["run", PING_CLASS, "--brief", sandbox.brief,
               "--cwd", sandbox.cwd, "--meters", sandbox.meters, "--no-probe"] + sandbox.common_args()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    else:
        argv = [prompt if a == "{prompt}" else a for a in spec["argv"]]
        # An empty stdin: `claude -p` reads its input too, and a headless
        # launch must see only the prompt it was given.
        proc = subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              env=env, cwd=sandbox.cwd, timeout=1800)
    new = sorted(sandbox.run_dirs() - before)
    if not new:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        return "fail", f"no run directory (exit {proc.returncode}): {tail[0]}"
    run_dir = new[-1]
    native = runs.parse_native_line(proc.stdout)
    if native and sandbox.offline:
        # The stub cannot spawn a subagent; the run directory and its prompt
        # are what the orchestrator's agent would read.
        if not os.path.isfile(os.path.join(run_dir, "prompt.md")):
            return "fail", f"{run_dir}: native run wrote no prompt.md"
        return "pass", f"native lane {native['lane']}: spawn {native['agent']} ({run_dir})"
    problem = check_ping_run(run_dir)
    if problem:
        return "fail", problem
    if reference is not None:
        problem = equivalent(reference, run_dir)
        if problem:
            return "fail", f"{run_dir}: {problem}"
    return "pass", f"equivalent run ({run_dir})"


def eval_orchestrate(sandbox, names):
    # The reference is a plain dispatch of the Lane the class ranks first; an
    # orchestrator's run is compared with it.
    reference = None
    try:
        profiles = orchestrators.load()
        catalog.load_catalog(cwd=sandbox.cwd, config_dir=sandbox.config_dir)
    except catalog.CatalogError as e:
        return {o: ("fail", str(e)) for o in names}
    except orchestrators.ProfileError as e:
        return {o: ("fail", str(e)) for o in names}
    if sandbox.offline:
        cmd = DELEGATE + ["run", PING_CLASS, "--brief", sandbox.brief, "--orchestrator", "none", "--json",
               "--cwd", sandbox.cwd, "--meters", sandbox.meters, "--no-probe"] + sandbox.common_args()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=sandbox.env)
        reference = run_dir_from(proc.stdout)
    return {o: orchestrate_one(sandbox, o, reference, profiles) for o in names}


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

    names = args.harness or list(harnesses.NAMES)
    sandbox = Sandbox(args.offline, keep=args.keep)
    try:
        if args.eval == "ping":
            return print_results("ping", eval_ping(sandbox, names))
        launchable = args.harness or [n for n, p in orchestrators.load().items() if p.get("launch")]
        return print_results("orchestrate", eval_orchestrate(sandbox, launchable))
    finally:
        sandbox.close()


if __name__ == "__main__":
    sys.exit(main())
