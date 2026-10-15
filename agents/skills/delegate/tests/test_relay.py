#!/usr/bin/env python3
"""test_relay.py — the Relay seam (relays.py): one relayed job in, one
`runs.Finish` out.

Settling cases run through `relays.Scripted`, scripted with what a relay says
(a Report), in-process with no node and no subprocess. Ads cases run the fake
relay (tests/fake-ads/relay.mjs) under node, with the fake ADS tree and the env
of `evals.OfflineWorld`; `replay=<dir>` leaves a staged run directory's relay
files, such as the grok gate-cancel fixture, in the run, and the fake relay's
`argv.json` and `env.json` show what Ads handed it. `Ads.check` runs ads.sh's
own check in that world.
Every case checks the Finish against the Run's record contracts:
`runs.DISPATCH_FIELDS` and `runs.RETURN_FIELDS`.

Run: python3 tests/test_relay.py
"""
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
# Relay output copied from real runs, trimmed of paths and signatures. Each
# directory is a run directory as the relay leaves it.
RUN_FIXTURES = os.path.join(HERE, "fixtures", "dispatch")
ADS_SH = os.path.join(SCRIPTS, "ads.sh")
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
sys.path.insert(0, SCRIPTS)
import evals  # noqa: E402
import harnesses  # noqa: E402
import relays  # noqa: E402
import runs  # noqa: E402

failures = []

with open(os.path.join(SAMPLES, "lanes.json"), encoding="utf-8") as _f:
    LANES = json.load(_f)["lanes"]

GATE = "permission gate cancelled the run at run_terminal_command"
# The sample catalog has no Kiro Lane; this is the one any-harness ticket 15 ran.
KIRO = {"harness": "kiro", "model": "claude-opus-5.5", "effort": "high", "timeout": "30m"}


def record(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def job(lane, prompt="/w/prompt.md", cwd="/w", write=None, effort=None):
    """The Job a sample Lane's Run hands its relay (or a Lane given as its
    fields), at `effort` when the Run overrides it."""
    data = LANES[lane] if isinstance(lane, str) else lane
    return relays.Job(harness=data["harness"], model=data["model"], effort=effort or data["effort"],
                      timeout=data["timeout"], prompt=prompt, cwd=cwd, write=write)


def problems(finish):
    """How a Finish breaks the Run's record contracts, or []: every field but
    `returned` is a dispatch.json key, `returned` has exactly the five return
    fields with a known status, and only a blocked return has a reason."""
    if not isinstance(finish, runs.Finish):
        return [f"not a runs.Finish: {finish!r}"]
    found = [f"{f} is not a DISPATCH_FIELDS key" for f in finish._fields
             if f != "returned" and f not in runs.DISPATCH_FIELDS]
    if tuple(finish.returned) != runs.RETURN_FIELDS:
        found.append(f"returned keys {tuple(finish.returned)}")
    status = finish.returned.get("status")
    if status not in ("done", "partial", "blocked"):
        found.append(f"status {status!r}")
    if status == "blocked" and not isinstance(finish.reason, str):
        found.append("a blocked return with no reason")
    if status in ("done", "partial") and finish.reason is not None:
        found.append(f"a {status} return with reason {finish.reason!r}")
    return found


def blocked(reason):
    return {"status": "blocked", "deliverable": f"blocked: {reason}", "evidence": [],
            "open_questions": [], "changed_files": []}


def tokens(n_in=0, out=0, cache_read=0, cache_write=0):
    """Token counts, keyed like a Lane's price record."""
    return {"in": n_in, "out": out, "cache_read": cache_read, "cache_write": cache_write}


# ---------------------------------------------------------------------------
# Settling, through Scripted
# ---------------------------------------------------------------------------

def settle(report, run_dir, **job_fields):
    return relays.Scripted(report).run(job("grok46-high@grok", **job_fields), run_dir)


def case_a_done_block_is_kept_within_its_caps(run_dir):
    items = [{"file": f"f{i}.py", "line": i, "claim": "c" * 250} for i in range(14)]
    items[3] = {"file": "f3.py", "line": 3}                    # no claim
    items[5] = {"file": "f5.py", "line": "five", "claim": "x"}  # a line that is not a number
    block = {"status": "done", "deliverable": "all done", "evidence": items,
             "open_questions": [f"q{i}" for i in range(7)], "changed_files": ["a.py", None, "b.py"]}
    final = "Done, notes first. {not json}\n" + json.dumps(block)
    finish = settle(relays.Report(status="completed", final_message=final, exit=0, secs=12,
                                  session_id="s-1", tokens=tokens(n_in=3), touched_files=["a.py"],
                                  read_only_violation=False), run_dir)
    kept = [{"file": f"f{i}.py", "line": i, "claim": "c" * 200} for i in (0, 1, 2, 4, 6, 7, 8, 9, 10, 11)]
    record("s1. a done block is the return, within its caps",
           not problems(finish)
           and finish.returned == {"status": "done", "deliverable": "all done", "evidence": kept,
                                   "open_questions": ["q0", "q1", "q2", "q3", "q4"],
                                   "changed_files": ["a.py", "b.py"]}
           and finish == runs.Finish(finish.returned, relay_status="completed", relay_exit=0, secs=12,
                                     session_id="s-1", tokens=tokens(n_in=3), touched_files=["a.py"],
                                     read_only_violation=False),
           f"{finish} problems={problems(finish)}")


def case_a_done_block_preserves_null_line_evidence(run_dir):
    block = {"status": "done", "deliverable": "all done",
             "evidence": [{"file": "CONTEXT.md", "line": None, "claim": "domain vocabulary"}],
             "open_questions": [], "changed_files": []}
    finish = settle(relays.Report(status="completed", final_message=json.dumps(block), exit=0), run_dir)
    record("s1b. a done block preserves evidence with a null line",
           not problems(finish) and finish.returned == block,
           f"{finish} problems={problems(finish)}")


def case_a_partial_or_blocked_block_is_the_return(run_dir):
    partial = settle(relays.Report(status="completed", exit=0, final_message=json.dumps({
        "status": "partial", "deliverable": "partially done", "evidence": [],
        "open_questions": ["what about edge cases?"], "changed_files": []})), run_dir)
    stuck = settle(relays.Report(status="completed", exit=0, final_message=json.dumps({
        "status": "blocked", "deliverable": "cannot read the spec", "evidence": [],
        "open_questions": [], "changed_files": []})), run_dir)
    record("s2. a partial or blocked block is the return; a blocked one gives its reason",
           not problems(partial) and not problems(stuck)
           and partial.returned["status"] == "partial" and partial.reason is None
           and partial.returned["deliverable"] == "partially done"
           and partial.returned["open_questions"] == ["what about edge cases?"]
           and stuck.returned["status"] == "blocked" and stuck.reason == "cannot read the spec"
           and stuck.returned["deliverable"] == "cannot read the spec",
           f"partial={partial} blocked={stuck}")


def case_prose_with_no_block_is_partial(run_dir):
    prose = "\n".join(f"Line {i} of prose without json block" for i in range(70))
    finish = settle(relays.Report(status="completed", final_message=prose, exit=0), run_dir)
    record("s3. prose with no block is partial: its first 60 lines and an open question",
           not problems(finish) and finish.returned["status"] == "partial"
           and finish.returned["deliverable"] == "\n".join(prose.splitlines()[:60])
           and finish.returned["deliverable"].splitlines()[-1] == "Line 59 of prose without json block"
           and finish.returned["open_questions"] == ["no return block in final message"],
           f"{finish} problems={problems(finish)}")


def case_an_empty_final_message_is_blocked(run_dir):
    finish = settle(relays.Report(status="completed", final_message="  \n", exit=0), run_dir)
    record("s4. an empty final message is blocked",
           not problems(finish) and finish.returned == blocked("empty final message")
           and finish.reason == "empty final message",
           f"{finish} problems={problems(finish)}")


def case_a_timeout_names_the_lanes_timeout(run_dir):
    finish = settle(relays.Report(status="timeout", final_message="Partial progress", exit=1), run_dir)
    record("s5. a timeout is blocked and names the Lane's timeout",
           not problems(finish) and finish.returned == blocked("timeout after 40m")
           and finish.relay_status == "timeout" and finish.relay_exit == 1,
           f"{finish} problems={problems(finish)}")


def case_a_failed_aborted_or_unavailable_relay_is_blocked(run_dir):
    seen = []
    for report, reason in (
            (relays.Report(status="failed", error="boom", exit=1), "boom"),
            (relays.Report(status="failed", error="Antigravity returned no output", exit=1),
             "Antigravity returned no output"),
            (relays.Report(status="aborted", exit=1), "relay status aborted"),
            (relays.Report(status="agy_unavailable", exit=127), "relay status agy_unavailable"),
            (relays.Report(status="grok_unavailable", error="grok is not installed", exit=127),
             "grok is not installed")):
        finish = settle(report, run_dir)
        seen.append((report.status, not problems(finish) and finish.returned == blocked(reason)
                     and finish.reason == reason and finish.relay_status == report.status
                     and finish.relay_exit == report.exit, finish))
    record("s6. a failed, aborted or unavailable relay is blocked with its error, else its status",
           all(ok for _, ok, _ in seen), repr([s for s in seen if not s[1]]))


def case_a_relay_that_reported_nothing_is_blocked(run_dir):
    told = settle(relays.Report(error="relay wrote no result (exit 2)", exit=2, secs=1), run_dir)
    silent = settle(relays.Report(), run_dir)
    odd = settle(relays.Report(status="weird", exit=0), run_dir)
    record("s7. a relay that reported nothing, or an unknown status, is blocked with why",
           not problems(told) and not problems(silent) and not problems(odd)
           and told.returned == blocked("relay wrote no result (exit 2)")
           and told.relay_status is None and told.relay_exit == 2 and told.secs == 1
           and silent.returned == blocked("relay reported nothing") and silent.relay_exit is None
           and odd.returned == blocked("relay status weird"),
           f"told={told} silent={silent} odd={odd}")


def case_a_job_that_stopped_short_is_blocked_unless_it_returned(run_dir):
    intent = "I'll research the sources, starting from the repo."
    stopped = settle(relays.Report(status="completed", final_message=intent, exit=0, stopped=GATE), run_dir)
    empty = settle(relays.Report(status="completed", exit=0, stopped=GATE), run_dir)
    block = json.dumps({"status": "done", "deliverable": "found it", "evidence": [],
                        "open_questions": [], "changed_files": []})
    returned = settle(relays.Report(status="completed", final_message=block, exit=0, stopped=GATE), run_dir)
    record("s8. a job that stopped short is blocked naming why, and a return block wins over the stop",
           not problems(stopped) and not problems(empty) and not problems(returned)
           and stopped.returned == blocked(GATE) and stopped.relay_status == "completed"
           and empty.returned == blocked(GATE)
           and returned.returned["status"] == "done" and returned.reason is None,
           f"stopped={stopped} empty={empty} returned={returned}")


def case_the_tripwire_fires_on_read_only_jobs_only(run_dir):
    block = json.dumps({"status": "done", "deliverable": "d", "evidence": [],
                        "open_questions": ["q"], "changed_files": []})
    tripped = relays.Report(status="completed", final_message=block, exit=0, read_only_violation=True)
    read_only = settle(tripped, run_dir)
    write = settle(tripped, run_dir, write="/w")
    clean = settle(tripped._replace(read_only_violation=False), run_dir)
    failed = settle(relays.Report(status="failed", error="boom", exit=1, read_only_violation=True), run_dir)
    tripwire = "read-only tripwire fired; review the diff"
    record("s9. a read-only job whose relay reports a violation gets the tripwire question; a write job never",
           all(not problems(f) for f in (read_only, write, clean, failed))
           and read_only.returned["open_questions"] == ["q", tripwire]
           and read_only.read_only_violation is True
           and write.returned["open_questions"] == ["q"]
           and clean.returned["open_questions"] == ["q"]
           and failed.returned["open_questions"] == [tripwire],
           f"read_only={read_only} write={write} clean={clean} failed={failed}")


def case_scripted_runs_its_script_in_order(run_dir):
    first = relays.Report(status="completed", final_message="done here", exit=0)
    fake = relays.Scripted(first, KeyboardInterrupt())
    j = job("terra-high@codex")
    finished = fake.run(j, run_dir)
    raised = []
    for _ in range(2):
        try:
            fake.run(j, run_dir)
        except BaseException as e:  # what the script raises, and the exhausted script
            raised.append(type(e).__name__)
    record("s10. Scripted settles each Report in turn, raises what it was scripted to, then fails the test",
           not problems(finished) and finished.returned["status"] == "partial"
           and raised == ["KeyboardInterrupt", "AssertionError"]
           and fake.jobs == [(j, run_dir)] * 3,
           f"finished={finished} raised={raised} jobs={fake.jobs}")


def case_scripted_check_answers_what_it_was_given():
    ready = relays.Scripted()
    refusing = relays.Scripted(ready="relays are down for this test")
    record("s12. Scripted's check answers None, or the line it was given, and runs nothing",
           ready.check() is None and refusing.check() == "relays are down for this test"
           and ready.jobs == [] and refusing.jobs == [],
           f"ready={ready.check()!r} refusing={refusing.check()!r}")


# ---------------------------------------------------------------------------
# Ads, through the fake relay under node
# ---------------------------------------------------------------------------

class AdsWorld:
    """The offline world's fake ADS tree and env, and a run directory per case."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="delegate-relay-")
        self.world = evals.OfflineWorld(self.root)
        self.ads_dir = self.world.ads_dir
        self.env = self.world.env
        self.codex_home = self.world.codex_home
        self.cwd = os.path.join(self.root, "work")
        self.dir = os.path.join(self.root, "relay-cases")
        os.makedirs(self.cwd)
        os.makedirs(self.dir)

    def run(self, name, lane, directive, env=None, write=None, effort=None):
        """(Finish, run_dir) of one Ads run whose prompt carries `directive`.
        A write job works in `write`, as dispatch has it."""
        run_dir = os.path.join(self.dir, name)
        os.makedirs(run_dir)
        prompt = os.path.join(run_dir, "prompt.md")
        with open(prompt, "w", encoding="utf-8") as f:
            f.write(f"fake-relay: {directive}\nBrief {name}.\n")
        relay = relays.Ads(self.ads_dir, env=self.env if env is None else env)
        the_job = job(lane, prompt=prompt, cwd=write or self.cwd, write=write, effort=effort)
        return relay.run(the_job, run_dir), run_dir

    def stage(self, name, fixture=None, result=None, keep_event=None, final_message=None):
        """A run directory as a relay left it: a fixture's copy, or one holding
        `result` (written verbatim when it is a string), edited as asked."""
        staged = os.path.join(self.dir, "staged", name)
        if fixture:
            shutil.copytree(os.path.join(RUN_FIXTURES, fixture), staged)
        else:
            os.makedirs(staged)
        if result is not None:
            with open(os.path.join(staged, "result.json"), "w", encoding="utf-8") as f:
                f.write(result if isinstance(result, str) else json.dumps(result))
        if keep_event is not None:
            events = os.path.join(staged, "events.jsonl")
            with open(events, encoding="utf-8") as f:
                kept = [line for line in f if keep_event(json.loads(line))]
            with open(events, "w", encoding="utf-8") as f:
                f.writelines(kept)
        if final_message is not None:
            path = os.path.join(staged, "result.json")
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            doc["finalMessage"] = final_message
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f)
        return staged

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def stderr_lines(run_dir):
    with open(os.path.join(run_dir, "relay.stderr"), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def case_ads_a_relay_that_throws_before_its_result(w):
    finish, run_dir = w.run("crash", "terra-high@codex", "crash=relay blew up before result.json")
    reason = "relay wrote no result (exit 1): Error: relay blew up before result.json"
    trailer = (stderr_lines(run_dir) or [""])[-1]
    quiet, _ = w.run("none", "terra-high@codex", "status=none exit=2")
    record("a1. Ads: a relay that throws before result.json is blocked with node's error line",
           not problems(finish) and finish.returned == blocked(reason) and finish.reason == reason
           and finish.relay_exit == 1 and finish.relay_status is None
           # node did end its output with its version, and that is not the reason
           and trailer.startswith("Node.js v")
           and not problems(quiet) and quiet.reason == "relay wrote no result (exit 2)"
           and quiet.relay_exit == 2,
           f"finish={finish} trailer={trailer!r} quiet={quiet}")


def case_ads_a_result_json_that_is_not_an_object(w):
    listed, _ = w.run("not-an-object", "terra-high@codex",
                      f"replay={w.stage('not-an-object', result='[]')} exit=0")
    broken, _ = w.run("not-json", "terra-high@codex",
                      f"replay={w.stage('not-json', result='{not json')} exit=3")
    # nested deeper than Python's json parses: RecursionError, not ValueError
    try:
        deep, _ = w.run("too-deep", "terra-high@codex",
                        f"replay={w.stage('too-deep', result='[' * 100000 + ']' * 100000)} exit=4")
    except Exception as e:  # the case fails, and says what Ads raised
        deep = e
    record("a2. Ads: a result.json that is not an object is blocked and keeps the relay's exit",
           not problems(listed) and listed.returned["status"] == "blocked"
           and listed.relay_exit == 0 and listed.reason.startswith("corrupt result.json: ")
           and "AttributeError" not in listed.reason
           and not problems(broken) and broken.relay_exit == 3
           and broken.reason.startswith("corrupt result.json: ")
           and not problems(deep) and deep.relay_exit == 4
           and deep.reason.startswith("corrupt result.json: "),
           f"listed={listed} broken={broken} deep={deep!r}")


def case_ads_replays_the_grok_gate_cancel_fixture(w):
    gate, gate_dir = w.run("gate", "grok46-high@grok", f"replay={w.stage('gate', fixture='grok-gate-cancel')}")
    # The end event alone is not the gate: stopReason=cancelled with no
    # cancelled tool call keeps the old reading.
    no_tool, _ = w.run("gate-no-tool", "grok46-high@grok", "replay=" + w.stage(
        "gate-no-tool", fixture="grok-gate-cancel",
        keep_event=lambda ev: not (ev.get("type") == "tool_call_update" and ev.get("status") == "failed")))
    # The gate is the better reason than an empty final message.
    empty, _ = w.run("gate-empty", "grok46-high@grok", "replay=" + w.stage(
        "gate-empty", fixture="grok-gate-cancel", final_message=""))
    with open(os.path.join(RUN_FIXTURES, "grok-gate-cancel", "result.json"), encoding="utf-8") as f:
        fixture = json.load(f)
    with open(os.path.join(gate_dir, "result.json"), encoding="utf-8") as f:
        left = json.load(f)
    record("a3. Ads: the grok gate-cancel replay is blocked naming the gate, and its two variants are not",
           all(not problems(f) for f in (gate, no_tool, empty))
           and gate.returned == blocked(GATE) and gate.reason == GATE
           and gate.relay_status == "completed" and gate.relay_exit == 0
           and gate.session_id == "01a087c8-34ac-7d70-8c56-d8c6d5a30f77"
           # the Finish carries Token counts; the raw record stays in the run's result.json
           and gate.tokens == tokens(n_in=16595, out=794, cache_read=5888, cache_write=0)
           and left.get("usage") == fixture["usage"] and gate.touched_files == []
           and gate.read_only_violation is False
           and os.path.isfile(os.path.join(gate_dir, "events.jsonl"))
           and no_tool.returned["status"] == "partial"
           and no_tool.returned["open_questions"] == ["no return block in final message"]
           and empty.returned == blocked(GATE),
           f"gate={gate} no_tool={no_tool} empty={empty}")


def case_ads_reads_every_result_key(w):
    def replay(name, result, write=None):
        finish, _ = w.run(name, "terra-high@codex", f"replay={w.stage(name, result=result)}", write=write)
        return finish

    spellings = {
        key: replay(f"session-{key}", {"status": "completed", "finalMessage": "prose", key: f"id-{key}"})
        for key in ("threadId", "sessionId", "conversationId")}
    tail = replay("tail", {"status": "failed", "stderrTail": ["first line", "second line"], "exitCode": 1})
    error_first = replay("error-first", {"status": "failed", "error": "boom", "stderrTail": ["ignored"]})
    tripped = replay("tripped", {"status": "completed", "finalMessage": "prose", "readOnlyViolation": True,
                                 "touchedFiles": ["x.py"], "usage": {"input_tokens": 5}})
    record("a4. Ads: reads the session under each spelling, the error or stderr tail, and the other keys",
           all(not problems(f) for f in list(spellings.values()) + [tail, error_first, tripped])
           and all(f.session_id == f"id-{key}" for key, f in spellings.items())
           and tail.reason == "first line\nsecond line" and tail.relay_exit == 1
           and error_first.reason == "boom"
           and tripped.read_only_violation is True and tripped.touched_files == ["x.py"]
           and tripped.tokens == tokens(n_in=5)
           and tripped.returned["open_questions"][-1] == "read-only tripwire fired; review the diff",
           f"spellings={spellings} tail={tail} error_first={error_first} tripped={tripped}")


def case_ads_node_missing_at_spawn(w):
    try:
        finish, run_dir = w.run("no-node", "terra-high@codex", "status=completed",
                                env=dict(w.env, PATH=w.world.path_without("node")))
    except Exception as e:  # the case fails, and says what Ads raised
        finish, run_dir = e, None
    reason = "node is not on PATH; the relay needs Node.js"
    record("a5. Ads: node missing at spawn is blocked with relay_exit None, and raises nothing",
           not problems(finish) and finish.returned == blocked(reason) and finish.reason == reason
           and finish.relay_exit is None and finish.relay_status is None
           and not os.path.exists(os.path.join(run_dir, "result.json")),
           repr(finish))


@contextlib.contextmanager
def process_env(**values):
    """This process's environment with `values` set, for the length of a
    block. A harness reads its own settings (codex's home) from it."""
    saved = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def flags(argv):
    """argv as {flag: value}, True for a flag with no value."""
    found = {}
    for i, arg in enumerate(argv):
        if arg.startswith("--"):
            value = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else True
            found[arg] = value
    return found


def case_ads_argv_and_env_per_harness(w):
    """What Ads hands each harness's relay: the common flags, the harness's
    own, and CODEX_HOME only for codex with a home of delegate's own."""
    worktree = os.path.join(w.root, "worktree")
    os.makedirs(worktree)
    home = os.path.join(w.root, "delegate-codex-home")
    os.makedirs(home)
    with open(os.path.join(home, "config.toml"), "w", encoding="utf-8") as f:
        f.write('approvals_reviewer = "auto_review"\n\n[mcp_servers.playwright]\ncommand = "npx"\nargs = []\n')
    # the relay's env holds no CODEX_HOME of the host's, so only Ads can set one
    env = {k: v for k, v in w.env.items() if k != "CODEX_HOME"}

    def handed(name, lane, write=None, effort=None, codex_home=w.codex_home):
        with process_env(DELEGATE_CODEX_HOME=codex_home):
            finish, run_dir = w.run(name, lane, "status=completed", env=env, write=write, effort=effort)
        with open(os.path.join(run_dir, "argv.json"), encoding="utf-8") as f:
            argv = json.load(f)
        with open(os.path.join(run_dir, "env.json"), encoding="utf-8") as f:
            seen_env = json.load(f)
        common = {"--brief": os.path.join(run_dir, "prompt.md"), "--cd": write or w.cwd, "--out-dir": run_dir}
        return finish, common, flags(argv), seen_env.get("CODEX_HOME"), argv

    rows = (
        # codex: its own flags; read-only unless it writes; without a home of
        # delegate's own it ignores the user's config (9a, 9c)
        ("codex-read", "terra-high@codex", {}, {
            "--model": "gpt-5.6-terra", "--effort": "high", "--timeout": "25m",
            "--skip-git-repo-check": True, "--ignore-user-config": True, "--read-only": True}, None),
        ("codex-write", "terra-high@codex", {"write": worktree}, {
            "--model": "gpt-5.6-terra", "--effort": "high", "--timeout": "25m",
            "--skip-git-repo-check": True, "--ignore-user-config": True}, None),
        # 9a2: with a home of delegate's own, CODEX_HOME points at it and
        # --ignore-user-config goes: the worker reads that home's one MCP server
        ("codex-home", "terra-high@codex", {"codex_home": home}, {
            "--model": "gpt-5.6-terra", "--effort": "high", "--timeout": "25m",
            "--skip-git-repo-check": True, "--read-only": True}, home),
        # agy: no effort flag, even when the Run overrides it (24); a print
        # timeout; read-only, or skip permissions to write (9d, 9e)
        ("agy-read", "flash-high@agy", {"effort": "low"}, {
            "--model": "gemini-3.8-flash-high", "--print-timeout": "25m", "--read-only": True}, None),
        ("agy-write", "flash-high@agy", {"write": worktree}, {
            "--model": "gemini-3.8-flash-high", "--print-timeout": "25m",
            "--dangerously-skip-permissions": True}, None),
        # claude, relayed (9f), grok (9g) and kiro (31f): the effort and the
        # Lane's timeout
        ("claude", "fable-xhigh@claude", {}, {
            "--model": "claude-fable-5-1", "--effort": "xhigh", "--timeout": "60m", "--read-only": True}, None),
        ("grok", "grok46-high@grok", {}, {
            "--model": "grok-4.6", "--effort": "high", "--timeout": "40m", "--read-only": True}, None),
        ("kiro", KIRO, {}, {
            "--model": "claude-opus-5.5", "--effort": "high", "--timeout": "30m", "--read-only": True}, None),
    )
    seen = []
    for name, lane, kw, own, codex_home in rows:
        finish, common, got, got_home, argv = handed(f"argv-{name}", lane, **kw)
        want = dict(common, **own)
        ok = got == want and got_home == codex_home and not problems(finish) and finish.relay_exit == 0
        seen.append((name, ok, got if got != want else "", got_home, argv))
    # 9h: no relay is ever handed a Lane name, a turn cap or a budget
    forbidden = {"--lane", "--max-turns", "--max-budget-usd"}
    clean = not any(forbidden.intersection(argv) for _, _, _, _, argv in seen)
    record("a6. Ads: argv and env per harness, and no argv names a Lane, a turn cap or a budget",
           all(ok for _, ok, _, _, _ in seen) and clean,
           repr([s[:4] for s in seen if not s[1]]) + f" clean={clean}")


def case_ads_check(w):
    pinned = relays.Ads(w.ads_dir, env=w.env).check()
    wrong_pin = relays.Ads(w.ads_dir, env=dict(w.env, ADS_FAKE_GIT_SHA="0" * 40)).check()
    no_node = relays.Ads(w.ads_dir, env=dict(w.env, PATH=w.world.path_without("node"))).check()
    # A tree that lost one relay script. The env's ADS_DIR still names the
    # whole tree, so the check must run on the directory Ads was given.
    torn = os.path.join(w.root, "torn-ads")
    shutil.copytree(w.ads_dir, torn)
    grok = harnesses.get("grok").relay
    os.remove(os.path.join(torn, "skills", grok, "scripts", "relay.mjs"))
    missing = relays.Ads(torn, env=w.env).check()

    def one_line(line, *names):
        return isinstance(line, str) and line and "\n" not in line and all(n in line for n in names)

    record("a7. Ads: check passes the pinned world, and names in one line a wrong pin, no node, a missing relay",
           pinned is None
           and one_line(wrong_pin, "commit mismatch", "0" * 40)
           and one_line(no_node, "node is not on PATH")
           and one_line(missing, f"missing relay {grok}", torn),
           f"pinned={pinned!r} wrong_pin={wrong_pin!r} no_node={no_node!r} missing={missing!r}")


def case_ads_default_directory():
    # ads.sh's own default, as its shell expands it: `path` prints
    # $ADS_DIR/skills/<harness>-delegate/scripts/relay.mjs
    env = {k: v for k, v in os.environ.items() if k != "ADS_DIR"}
    env.setdefault("HOME", os.path.expanduser("~"))
    printed = subprocess.run(["sh", ADS_SH, "path", "probe"], capture_output=True, text=True,
                             env=env).stdout.strip()
    suffix = "/skills/probe-delegate/scripts/relay.mjs"
    shell_default = printed[:-len(suffix)] if printed.endswith(suffix) else printed
    elsewhere = os.path.join(_ISOLATED_CWD.name, "elsewhere")
    record("a8. Ads: relays.DEFAULT_DIR is ads.sh's default; the argument, else $ADS_DIR, else it",
           relays.DEFAULT_DIR == shell_default
           and relays.Ads("given", env={"ADS_DIR": elsewhere}).ads_dir == os.path.abspath("given")
           and relays.Ads(env={"ADS_DIR": elsewhere}).ads_dir == elsewhere
           and relays.Ads(env={}).ads_dir == relays.DEFAULT_DIR,
           f"DEFAULT_DIR={getattr(relays, 'DEFAULT_DIR', None)!r} ads.sh={shell_default!r}")


def case_ads_token_counts_for_each_spelling(w):
    """Every usage spelling a relay writes normalizes into Token counts. A
    cache count rides with an input count, since a record with neither input
    nor output holds no counts."""
    no_record = object()
    rows = (
        ("input_tokens", {"input_tokens": 11}, tokens(n_in=11)),
        ("inputTokens", {"inputTokens": 12}, tokens(n_in=12)),
        ("prompt_tokens", {"prompt_tokens": 13}, tokens(n_in=13)),
        ("promptTokens", {"promptTokens": 14}, tokens(n_in=14)),
        ("output_tokens", {"output_tokens": 21}, tokens(out=21)),
        ("outputTokens", {"outputTokens": 22}, tokens(out=22)),
        ("completion_tokens", {"completion_tokens": 23}, tokens(out=23)),
        ("completionTokens", {"completionTokens": 24}, tokens(out=24)),
        ("cache_read_input_tokens", {"input_tokens": 1, "cache_read_input_tokens": 31},
         tokens(n_in=1, cache_read=31)),
        ("cachedInputTokens", {"inputTokens": 1, "cachedInputTokens": 32}, tokens(n_in=1, cache_read=32)),
        ("cached_tokens", {"prompt_tokens": 1, "cached_tokens": 33}, tokens(n_in=1, cache_read=33)),
        ("cache_read_tokens", {"input_tokens": 1, "cache_read_tokens": 34}, tokens(n_in=1, cache_read=34)),
        ("cache_creation_input_tokens", {"input_tokens": 1, "cache_creation_input_tokens": 41},
         tokens(n_in=1, cache_write=41)),
        ("cacheCreationInputTokens", {"inputTokens": 1, "cacheCreationInputTokens": 42},
         tokens(n_in=1, cache_write=42)),
        # a count that is not a number is not read; the next spelling is
        ("not-a-number", {"input_tokens": "lots", "inputTokens": 7, "output_tokens": True},
         tokens(n_in=7)),
        # no counts: a null record, cache counts with neither input nor
        # output, a record that is not an object, and no record at all
        ("null", None, None),
        ("cache-only", {"cached_tokens": 9, "cache_creation_input_tokens": 3}, None),
        ("not-a-record", ["input_tokens", 5], None),
        ("absent", no_record, None),
    )
    seen = []
    for name, usage, want in rows:
        result = {"status": "completed", "finalMessage": "prose", "exitCode": 0}
        if usage is not no_record:
            result["usage"] = usage
        finish, _ = w.run(f"tokens-{name}", "grok46-high@grok",
                          f"replay={w.stage(f'tokens-{name}', result=result)}")
        seen.append((name, finish.tokens == want and not problems(finish), finish.tokens))
    # the fake relay, like codex, reports usage null
    fake, _ = w.run("tokens-fake-relay", "terra-high@codex", "status=completed")
    seen.append(("fake relay", fake.tokens is None and not problems(fake), fake.tokens))
    record("a9. Ads: Token counts for every usage spelling, and none from a relay that reported none",
           all(ok for _, ok, _ in seen), repr([s for s in seen if not s[1]]))


def main():
    with tempfile.TemporaryDirectory() as run_dir:
        case_a_done_block_is_kept_within_its_caps(run_dir)
        case_a_done_block_preserves_null_line_evidence(run_dir)
        case_a_partial_or_blocked_block_is_the_return(run_dir)
        case_prose_with_no_block_is_partial(run_dir)
        case_an_empty_final_message_is_blocked(run_dir)
        case_a_timeout_names_the_lanes_timeout(run_dir)
        case_a_failed_aborted_or_unavailable_relay_is_blocked(run_dir)
        case_a_relay_that_reported_nothing_is_blocked(run_dir)
        case_a_job_that_stopped_short_is_blocked_unless_it_returned(run_dir)
        case_the_tripwire_fires_on_read_only_jobs_only(run_dir)
        case_scripted_runs_its_script_in_order(run_dir)
        case_scripted_check_answers_what_it_was_given()
        # settling ran nothing: no relay file appeared in the run directory
        record("s11. settling through Scripted runs no relay and writes nothing",
               os.listdir(run_dir) == [], repr(os.listdir(run_dir)))

    w = AdsWorld()
    try:
        case_ads_a_relay_that_throws_before_its_result(w)
        case_ads_a_result_json_that_is_not_an_object(w)
        case_ads_replays_the_grok_gate_cancel_fixture(w)
        case_ads_reads_every_result_key(w)
        case_ads_node_missing_at_spawn(w)
        case_ads_argv_and_env_per_harness(w)
        case_ads_check(w)
        case_ads_default_directory()
        case_ads_token_counts_for_each_spelling(w)
    finally:
        w.close()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
