#!/usr/bin/env python3
"""test_runs.py — the Run module (runs.py): a started Run always finishes.

Every case drives `runs.execute` in-process against a temp runs root, a temp
$DELEGATE_LEDGER and a temp $DELEGATE_CACHE. The work is a plain function, or
in case 3b a relay adapter's `run`. Cases 3b and 13 read the scripts' source:
no relay adapter catches what ends a Run, and only runs.py touches the Ledger
and a Run's records.
"""
import ast
import contextlib
from datetime import datetime
import json
import os
import signal
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
sys.path.insert(0, SCRIPTS)
import relays  # noqa: E402
import runs  # noqa: E402
import usage  # noqa: E402

failures = []

RETURNED = {"status": "done", "deliverable": "pong", "evidence": [], "open_questions": [],
            "changed_files": []}
# The outcome half of dispatch.json, null until the Run ends.
OUTCOME = runs.DISPATCH_FIELDS[runs.DISPATCH_FIELDS.index("relay_status"):]
GROK_LIMIT = "You've reached your free Grok Build usage limit for now"


def record(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def request(**fields):
    base = dict(lane="sol-high@codex", harness="codex", model="gpt-6-sol", effort="high",
                timeout="30m", class_name="impl", cwd="/w", write=None, brief="/w/b.md",
                leash=False)
    base.update(fields)
    return runs.Request(**base)


class World:
    """A temp runs root, Ledger and usage cache, set in the environment."""

    def __init__(self, path):
        self.dir = path
        self.root = os.path.join(path, "runs")
        self.ledger = os.path.join(path, "ledger.jsonl")
        self.cache = os.path.join(path, "usage.json")

    def lines(self):
        try:
            with open(self.ledger, encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except OSError:
            return []


@contextlib.contextmanager
def world():
    saved = {k: os.environ.get(k) for k in ("DELEGATE_LEDGER", "DELEGATE_CACHE")}
    with tempfile.TemporaryDirectory() as td:
        w = World(td)
        os.environ["DELEGATE_LEDGER"] = w.ledger
        os.environ["DELEGATE_CACHE"] = w.cache
        try:
            yield w
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def case_a_run_that_returns():
    with world() as w:
        seen = {}

        def work(run):
            seen["path"] = run.path
            seen["dispatch"] = run.read()["dispatch"]
            seen["ledger"] = w.lines()
            return runs.Finish(dict(RETURNED, extra="dropped"), relay_status="completed",
                               relay_exit=0, secs=12, session_id="s-1", usage={"in": 1})

        ended = runs.execute(request(), b"the prompt\n", work, w.root)
        run = runs.Run(ended.run)
        read = run.read()
        disp = read["dispatch"]
        lines = w.lines()
        start, finish = (lines + [{}, {}])[:2]
        thread = disp.get("thread_id")
        with open(run.prompt_path, "rb") as f:
            prompt = f.read()
        text = (f"delegate: sol-high@codex status=done secs=12 run={ended.run}\n"
                f"delegate-metrics: thread={thread} status=done class=impl secs=12 rc=0")
        summary = {"lane": "sol-high@codex", "status": "done", "secs": 12, "run": ended.run,
                   "thread": thread, "class": "impl", "rc": 0, "return": RETURNED}
        stamped = ("thread_id", "started_at", "finished_at")
        record("1. a Run that returns ends with that return in every record",
               ended.run == seen.get("path") and os.path.dirname(ended.run) == w.root
               and os.path.basename(ended.run).split("-", 1)[1].startswith("sol-high@codex-")
               and prompt == b"the prompt\n"
               # before the work: the request with a null outcome, and the Ledger start
               and tuple(seen["dispatch"]) == runs.DISPATCH_FIELDS
               and all(seen["dispatch"][k] is None for k in OUTCOME)
               and [e.get("kind") for e in seen["ledger"]] == ["dispatch.start"]
               # after: the five fields, the outcome in order, the session under both names
               and read["return"] == RETURNED
               and tuple(disp) == runs.DISPATCH_FIELDS
               and {k: disp[k] for k in runs.DISPATCH_FIELDS if k not in stamped} == {
                   "lane": "sol-high@codex", "harness": "codex", "model": "gpt-6-sol",
                   "effort": "high", "timeout": "30m", "class": "impl", "leash": False,
                   "orchestrator": None, "cwd": "/w", "write": None, "brief": "/w/b.md",
                   "prompt": run.prompt_path, "relay_status": "completed", "relay_exit": 0,
                   "secs": 12, "status": "done", "reason": None, "session_id": "s-1",
                   "session": "s-1", "usage": {"in": 1}, "touched_files": None,
                   "read_only_violation": None}
               and thread and disp["started_at"] and disp["finished_at"]
               # the Ledger: one start and one finish on one thread
               and [e.get("kind") for e in lines] == ["dispatch.start", "dispatch.finish"]
               and start.get("thread_id") == thread == finish.get("thread_id")
               and start.get("timeout_s") == 1800 and start.get("cwd") == "/w"
               and start.get("out") == run.return_path and start.get("class") == "impl"
               and finish.get("status") == "done" and finish.get("rc") == 0
               and finish.get("secs") == 12 and finish.get("child_session") == "s-1"
               # what dispatch prints and exits with
               and ended.lane == "sol-high@codex" and ended.status == "done"
               and ended.exit_code == 0 and ended.notes == ()
               and ended.text() == text
               and ended.text(as_json=True) == json.dumps(summary, indent=2),
               f"ended={vars(ended)} read={read} ledger={lines} seen={seen}")


def case_work_that_raises_ends_the_run_blocked():
    seen = []
    for name, exc, reason, nap in (
            ("RuntimeError", RuntimeError("boom"), "dispatch failed: RuntimeError: boom", 1.05),
            ("KeyboardInterrupt", KeyboardInterrupt(), "dispatch interrupted", 0)):
        with world() as w:
            def work(run, exc=exc, nap=nap):
                time.sleep(nap)
                raise exc

            ended = runs.execute(request(), b"p", work, w.root)
            read = runs.Run(ended.run).read()
            disp = read["dispatch"]
            lines = w.lines()
            finish = lines[-1] if lines else {}
            ok = (ended.status == "blocked" and ended.exit_code == 1 and ended.notes == ()
                  and disp["status"] == "blocked" and disp["reason"] == reason
                  and disp["relay_exit"] is None and disp["finished_at"]
                  # secs are measured by the Run, since the work gave none
                  and disp["secs"] == int(nap)
                  and read["return"] == {"status": "blocked", "deliverable": f"blocked: {reason}",
                                         "evidence": [], "open_questions": [], "changed_files": []}
                  and [e.get("kind") for e in lines] == ["dispatch.start", "dispatch.finish"]
                  and finish.get("status") == "blocked" and finish.get("rc") == 1
                  and ended.text().endswith(f"status=blocked class=impl secs={int(nap)} rc=None"))
            seen.append((name, ok, disp, ended.text()))
    record("2. work that raises ends the Run blocked with why",
           all(ok for _, ok, _, _ in seen), repr([s for s in seen if not s[1]]))


def case_sigterm_during_work_ends_the_run_blocked_as_terminated():
    with world() as w:
        def previous(signum, frame):
            pass

        def work(run):
            try:
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(5)
            except Exception:
                # a work that swallows every Exception still cannot swallow SIGTERM
                return runs.Finish(RETURNED)
            return runs.Finish(RETURNED)

        before = signal.signal(signal.SIGTERM, previous)
        try:
            t0 = time.monotonic()
            ended = runs.execute(request(), b"p", work, w.root)
            took = time.monotonic() - t0
            restored = signal.getsignal(signal.SIGTERM) is previous
        finally:
            signal.signal(signal.SIGTERM, before)
        read = runs.Run(ended.run).read()
        lines = w.lines()
        record("3. SIGTERM during work ends the Run blocked as terminated",
               ended.status == "blocked" and ended.exit_code == 1 and took < 4
               and read["dispatch"]["reason"] == "dispatch terminated (SIGTERM)"
               and read["dispatch"]["finished_at"]
               and read["return"]["deliverable"] == "blocked: dispatch terminated (SIGTERM)"
               and [e.get("kind") for e in lines] == ["dispatch.start", "dispatch.finish"]
               and lines[-1].get("status") == "blocked"
               # the previous handler comes back
               and restored,
               f"took={took:.1f} restored={restored} ended={vars(ended)} read={read} ledger={lines}")


class _SignalledRelay(relays.Scripted):
    """A relay adapter whose `run` gets SIGTERM after it settled, as a relay
    does when `claude -p` ends its background job at the end of a turn."""

    def run(self, job, run_dir):
        finish = super().run(job, run_dir)
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(5)
        return finish


def broad_handlers(source, name="relays.py"):
    """Every `except` in source that is bare or names Exception or
    BaseException, as "<name>:<line>"."""
    found = []
    for node in ast.walk(ast.parse(source, name)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        caught = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        if any(c is None or (isinstance(c, ast.Name) and c.id in ("Exception", "BaseException"))
               for c in caught):
            found.append(f"{name}:{node.lineno}")
    return found


def case_sigterm_inside_a_relay_adapters_run_ends_the_run_terminated():
    with world() as w:
        relay = _SignalledRelay(relays.Report(status="completed", exit=0, final_message=json.dumps(RETURNED)))

        def work(run):
            job = relays.Job(harness="codex", model="gpt-6-sol", effort="high", timeout="30m",
                             prompt=run.prompt_path, cwd="/w")
            return relay.run(job, run.path)

        before = signal.getsignal(signal.SIGTERM)
        t0 = time.monotonic()
        ended = runs.execute(request(), b"p", work, w.root)
        took = time.monotonic() - t0
        read = runs.Run(ended.run).read()
        lines = w.lines()
        with open(os.path.join(SCRIPTS, "relays.py"), encoding="utf-8") as f:
            broad = broad_handlers(f.read())
        # the scan is live: it finds each broad form in a planted adapter
        planted = broad_handlers("try:\n    pass\nexcept Exception:\n    pass\n"
                                 "try:\n    pass\nexcept (OSError, BaseException):\n    pass\n"
                                 "try:\n    pass\nexcept:\n    pass\n", "planted.py")
        record("3b. SIGTERM inside a relay adapter's run ends the Run terminated; no adapter catches it",
               len(relay.jobs) == 1 and took < 4
               and ended.status == "blocked" and ended.exit_code == 1
               and read["dispatch"]["reason"] == "dispatch terminated (SIGTERM)"
               and read["return"]["deliverable"] == "blocked: dispatch terminated (SIGTERM)"
               and [e.get("kind") for e in lines] == ["dispatch.start", "dispatch.finish"]
               and signal.getsignal(signal.SIGTERM) == before
               # Ads catches only OSError and ValueError, so termination passes through
               and broad == [] and planted == ["planted.py:3", "planted.py:7", "planted.py:11"],
               f"took={took:.1f} jobs={relay.jobs} ended={vars(ended)} read={read} ledger={lines} "
               f"broad={broad} planted={planted}")


def case_a_return_json_that_cannot_be_written_still_ends_the_run():
    with world() as w:
        def work(run):
            os.mkdir(run.return_path)
            return runs.Finish(RETURNED, relay_status="completed", relay_exit=0, secs=3,
                               session_id="s-4")

        ended = runs.execute(request(), b"p", work, w.root)
        disp = runs.Run(ended.run).read()["dispatch"]
        lines = w.lines()
        record("4. a return.json that cannot be written still ends dispatch.json and the Ledger",
               ended.status == "blocked" and ended.exit_code == 1
               and disp["status"] == "blocked"
               and (disp["reason"] or "").startswith("could not write return.json: ")
               and disp["finished_at"] and disp["secs"] == 3
               # the relay's facts stay recorded
               and disp["relay_status"] == "completed" and disp["session_id"] == "s-4"
               and [e.get("kind") for e in lines] == ["dispatch.start", "dispatch.finish"]
               and lines[-1].get("status") == "blocked"
               and len(ended.notes) == 1 and "return.json" in ended.notes[0]
               and "status=blocked secs=3" in ended.text(),
               f"ended={vars(ended)} dispatch={disp} ledger={lines}")


def case_a_ledger_that_cannot_be_written_never_stops_a_run_ending():
    def ended_done(ended):
        read = runs.Run(ended.run).read()
        return (ended.status == "done" and ended.exit_code == 0
                and read["return"] == RETURNED and read["dispatch"]["status"] == "done"
                and read["dispatch"]["finished_at"]
                and ended.text().startswith("delegate: sol-high@codex status=done secs=2 run="))

    # the Ledger's directory is a regular file: neither line can be written
    with world() as w:
        blocker = os.path.join(w.dir, "blocker")
        open(blocker, "w").close()
        os.environ["DELEGATE_LEDGER"] = os.path.join(blocker, "ledger.jsonl")
        ended_a = runs.execute(request(), b"p", lambda run: runs.Finish(RETURNED, relay_exit=0, secs=2),
                               w.root)
        ok_a = (ended_done(ended_a) and len(ended_a.notes) == 2
                and ended_a.notes[0].startswith("could not write the Ledger start: ")
                and ended_a.notes[1].startswith("could not write the Ledger finish: "))

    # the work swaps the Ledger for a directory: the start is written, the finish lost
    with world() as w:
        def work(run):
            os.remove(w.ledger)
            os.mkdir(w.ledger)
            return runs.Finish(RETURNED, relay_exit=0, secs=2)

        ended_b = runs.execute(request(), b"p", work, w.root)
        ok_b = (ended_done(ended_b) and len(ended_b.notes) == 1
                and ended_b.notes[0].startswith("could not write the Ledger finish: "))
    record("5. a Ledger that cannot be written never stops a Run ending", ok_a and ok_b,
           f"a={vars(ended_a)} b={vars(ended_b)}")


def case_a_usage_limit_refusal_holds_the_lanes_meter():
    grok = request(lane="grok46-high@grok", harness="grok", model="grok-4.6", meter="grok")

    def held():
        return sorted(usage.read_limits())

    with world() as w:
        refused = runs.execute(grok, b"p", lambda run: runs.blocked(GROK_LIMIT), w.root)
        after_refusal = held()
        timed_out = runs.execute(grok, b"p", lambda run: runs.blocked("timeout after 40m"), w.root)
        after_timeout = held()
        runs.execute(grok, b"p", lambda run: runs.Finish(RETURNED), w.root)
        after_done = held()
        runs.execute(grok, b"p", lambda run: runs.blocked(GROK_LIMIT), w.root)
        runs.execute(grok, b"p", lambda run: runs.Finish(dict(RETURNED, status="partial")), w.root)
        after_partial = held()
        # another harness's Meter is never held by grok's words
        codex = runs.execute(request(meter="codex"), b"p", lambda run: runs.blocked(GROK_LIMIT), w.root)
        after_codex = held()
        # a Request without a meter holds nothing
        runs.execute(grok._replace(meter=None), b"p", lambda run: runs.blocked(GROK_LIMIT), w.root)
        after_none = held()
        note = refused.notes[0] if refused.notes else ""
        record("6. a usage-limit refusal holds the Lane's Meter, and a done or partial Run releases it",
               after_refusal == ["grok"] and note.startswith("grok meter held at 0% left until ")
               and note.endswith(f": {GROK_LIMIT}")
               and after_timeout == ["grok"] and timed_out.notes == ()
               and after_done == [] and after_partial == []
               and after_codex == [] and codex.notes == () and after_none == [],
               f"refusal={after_refusal} {refused.notes} timeout={after_timeout} done={after_done} "
               f"partial={after_partial} codex={after_codex} none={after_none}")


def case_a_runs_root_that_cannot_be_made_starts_nothing():
    with world() as w:
        blocker = os.path.join(w.dir, "blocker")
        open(blocker, "w").close()
        called = []
        try:
            runs.execute(request(), b"p", called.append, os.path.join(blocker, "runs"))
            raised = None
        except runs.StartError as e:
            raised = e
        record("7. a runs root that cannot be made starts nothing",
               raised is not None and "blocker" in str(raised) and called == []
               and not os.path.exists(w.ledger),
               f"raised={raised!r} called={called} ledger={w.lines()}")


def case_a_hand_off_ends_the_run_at_once_as_native():
    claude = request(lane="opus-high@claude", harness="claude", model="claude-opus-5",
                     meter="claude-general")
    with world() as w:
        usage.mark_limited("claude-general", "held before the hand-off")
        seen = {}

        def work(run):
            seen["prompt"] = run.prompt_path
            seen["spawn"] = f"spawn lane-opus-high with the Agent tool on {run.prompt_path}"
            return runs.HandOff("lane-opus-high", seen["spawn"])

        ended = runs.execute(claude, b"p", work, w.root)
        run = runs.Run(ended.run)
        disp = run.read()["dispatch"]
        lines = w.lines()
        start, finish = (lines + [{}, {}])[:2]
        prompt, spawn = seen.get("prompt"), seen.get("spawn")
        native = {"native": True, "lane": "opus-high@claude", "agent": "lane-opus-high",
                  "prompt": prompt, "spawn": spawn}
        record("8. a hand-off ends the Run at once as native",
               ended.status == "native" and ended.exit_code == 0 and ended.notes == ()
               and ended.lane == "opus-high@claude"
               # an Outcome in dispatch.json, and no return
               and not os.path.exists(run.return_path)
               and disp["status"] == "native" and disp["reason"] == "handed to lane-opus-high"
               and disp["secs"] is None and disp["finished_at"]
               and disp["relay_status"] is None and disp["relay_exit"] is None
               # the Ledger: one start and one finish, native, on one thread
               and [e.get("kind") for e in lines] == ["dispatch.start", "dispatch.finish"]
               and start.get("thread_id") == disp["thread_id"] == finish.get("thread_id")
               and finish.get("status") == "native" and finish.get("secs") is None
               # the Meter hold is never touched
               and sorted(usage.read_limits()) == ["claude-general"]
               # what dispatch prints: the native line, then the spawn line
               and ended.text() == (f"delegate: native lane=opus-high@claude agent=lane-opus-high "
                                    f"prompt={prompt}\ndelegate: spawn: {spawn}")
               and ended.text(as_json=True) == json.dumps(native, indent=2),
               f"ended={vars(ended)} dispatch={disp} ledger={lines} limits={usage.read_limits()}")


def case_running_lists_a_run_while_its_work_runs():
    with world() as w:
        seen = {}

        def work(run):
            seen["running"] = runs.running()
            return runs.Finish(RETURNED, relay_exit=0, secs=1)

        before = time.time()
        ended = runs.execute(request(), b"p", work, w.root)
        after = runs.running()
        inside = seen.get("running") or []
        found = inside[0] if inside else None
        record("9. running lists a Run while its work runs, and not after",
               len(inside) == 1 and found.lane == "sol-high@codex" and found.run == ended.run
               # the Ledger stamps whole seconds
               and before - 1 <= found.started <= time.time()
               and found.deadline == found.started + 1800
               and after == [],
               f"inside={inside} after={after}")


def case_a_start_past_its_timeout_or_ended_is_not_running():
    with world() as w:
        seen = {}

        def work(run):
            listed = runs.running()
            if listed:
                seen["at_deadline"] = runs.running(now=listed[0].deadline)
                seen["past"] = runs.running(now=listed[0].deadline + 1)
            return runs.Finish(RETURNED, relay_exit=0, secs=1)

        ended = runs.execute(request(), b"p", work, w.root)
        # The Ledger finish is lost: only the start is left, and dispatch.json has ended.
        with open(w.ledger, encoding="utf-8") as f:
            start = f.readline()
        with open(w.ledger, "w", encoding="utf-8") as f:
            f.write(start)
        lost_finish = runs.running()
        # The same start beside a dispatch.json that has not ended is running.
        run = runs.Run(ended.run)
        with open(run.dispatch_path, encoding="utf-8") as f:
            doc = json.load(f)
        doc["finished_at"] = None
        with open(run.dispatch_path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        unended = runs.running()
        record("10. a start past its timeout is not running, nor one whose dispatch.json has ended",
               len(seen.get("at_deadline") or []) == 1 and seen.get("past") == []
               and lost_finish == []
               and [r.run for r in unended] == [ended.run],
               f"seen={seen} lost_finish={lost_finish} unended={unended}")


def v1_start(thread, lane, ts, timeout_s, out, class_="impl", effort="high", cwd="/w",
             brief="/w/b.md", write=None):
    """A Ledger start exactly as every delegate since v1 spells it."""
    return (f'{{"v": 1, "kind": "dispatch.start", "ts": {json.dumps(ts)}, '
            f'"thread_id": {json.dumps(thread)}, "lane": {json.dumps(lane)}, "class": {json.dumps(class_)}, '
            f'"effort": {json.dumps(effort)}, "timeout_s": {json.dumps(timeout_s)}, "cwd": {json.dumps(cwd)}, '
            f'"brief": {json.dumps(brief)}, "out": {json.dumps(out)}, "write": {json.dumps(write)}}}')


def v1_finish(thread, lane, ts, secs, rc, status, child_session, out, class_="impl"):
    """A Ledger finish exactly as every delegate since v1 spells it."""
    return (f'{{"v": 1, "kind": "dispatch.finish", "ts": {json.dumps(ts)}, "thread_id": {json.dumps(thread)}, '
            f'"lane": {json.dumps(lane)}, "class": {json.dumps(class_)}, "secs": {json.dumps(secs)}, '
            f'"rc": {json.dumps(rc)}, "status": {json.dumps(status)}, '
            f'"child_session": {json.dumps(child_session)}, "out": {json.dumps(out)}}}')


def case_running_reads_a_ledger_an_earlier_delegate_wrote():
    def stamp(epoch):
        return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")

    start = v1_start
    with world() as w:
        now = float(int(time.time()))
        open_run = os.path.join(w.root, "20261011T080000Z-flash-high@agy-0a0a0a0a")
        os.makedirs(open_run)
        with open(os.path.join(open_run, "dispatch.json"), "w", encoding="utf-8") as f:
            json.dump({"lane": "flash-high@agy", "status": None, "finished_at": None}, f)
        # a Run whose dispatch.json no reader can parse: only an ended one drops a start
        deep_run = os.path.join(w.root, "20261011T080100Z-luna-low@codex-0b0b0b0b")
        os.makedirs(deep_run)
        with open(os.path.join(deep_run, "dispatch.json"), "w", encoding="utf-8") as f:
            f.write("[" * 100000)
        elsewhere = os.path.join(w.root, "gone", "return.json")
        # v1 lines as earlier delegates wrote them: a meter event (probes wrote
        # them until delegate-deepening 04), an open start, a start past its
        # timeout and a start with its finish.
        lines = [
            f'{{"v": 1, "kind": "meter", "ts": "{stamp(now - 900)}", "source": "probe", '
            f'"cache_age_s": 0, "probed_at": {now - 900}, "lanes": []}}',
            start("t-open", "flash-high@agy", stamp(now - 100), 1500,
                  os.path.join(open_run, "return.json")),
            start("t-deep", "luna-low@codex", stamp(now - 50), 600,
                  os.path.join(deep_run, "return.json")),
            start("t-stale", "terra-high@codex", stamp(now - 1000), 300, elsewhere),
            start("t-pair", "grok46-high@grok", stamp(now - 200), 2400, elsewhere),
            v1_finish("t-pair", "grok46-high@grok", stamp(now - 150), 50, 0, "done", None, elsewhere),
            # lines that are not objects
            "[1]", '"dispatch.start"', "42", "null", "{not json", "",
            # starts it cannot read
            start("t-ts", "luna-low@codex", "yesterday", 600, elsewhere),
            start("t-timeout", "luna-low@codex", stamp(now - 100), "10m", elsewhere),
            start([1], "luna-low@codex", stamp(now - 100), 600, elsewhere),
            start("t-lane", None, stamp(now - 100), 600, elsewhere),
            # a timeout no float holds, and ones that are not finite
            start("t-huge", "luna-low@codex", stamp(now - 100), int("9" * 400), elsewhere),
            start("t-nan", "luna-low@codex", stamp(now - 100), float("nan"), elsewhere),
            start("t-inf", "luna-low@codex", stamp(now - 100), float("inf"), elsewhere),
        ]
        with open(w.ledger, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        def listed():
            try:
                return runs.running(now)
            except Exception as e:  # running never raises
                return repr(e)

        read = listed()
        os.remove(w.ledger)
        missing = listed()
        os.mkdir(w.ledger)
        unreadable = listed()
        record("11. running reads a Ledger an earlier delegate wrote, and skips lines that are not objects",
               read == [runs.Running("flash-high@agy", open_run, now - 100, now - 100 + 1500),
                        runs.Running("luna-low@codex", deep_run, now - 50, now - 50 + 600)]
               and missing == [] and unreadable == [],
               f"read={read} missing={missing} unreadable={unreadable}")


def case_the_ledger_lines_keep_their_v1_keys_in_order():
    # A relayed Run with a Class, one with a worktree and no Class, and a hand-off;
    # each with its start's timeout_s, then its finish's secs, rc, status and session.
    asked = (
        (request(), lambda run: runs.Finish(RETURNED, relay_exit=0, secs=7, session_id="s-12"),
         1800, 7, 0, "done", "s-12"),
        (request(class_name=None, write="/wt", timeout="2h"), lambda run: runs.blocked("no relay"),
         7200, 0, 1, "blocked", None),
        (request(lane="opus-high@claude", harness="claude", timeout="40m"),
         lambda run: runs.HandOff("lane-opus-high", "spawn it"), 2400, None, 0, "native", None),
    )
    seen = []
    with world() as w:
        for req, work, timeout_s, secs, rc, status, session in asked:
            ended = runs.execute(req, b"p", work, w.root)
            with open(w.ledger, encoding="utf-8") as f:
                wrote = f.read().splitlines()[-2:]
            start, finish = (json.loads(line) for line in wrote)
            out = runs.Run(ended.run).return_path
            thread = start["thread_id"]
            # the same lines the running() fixture (case 11) reads, byte for byte
            seen.append((wrote, [
                v1_start(thread, req.lane, start["ts"], timeout_s, out, class_=req.class_name,
                         effort=req.effort, cwd=req.write or req.cwd, brief=req.brief, write=req.write),
                v1_finish(thread, req.lane, finish["ts"], secs, rc, status, session, out,
                          class_=req.class_name),
            ]))
    record("12. the Ledger lines a Run writes keep their v1 keys, in order",
           len(seen) == 3 and all(wrote == expected for wrote, expected in seen),
           "".join(f"\n  wrote    {wrote}\n  expected {expected}"
                   for wrote, expected in seen if wrote != expected))


# A Run's two records, and the names a script reaches them by.
RUN_RECORDS = ("dispatch.json", "return.json")
RECORD_PATHS = ("dispatch_path", "return_path")


def _names_a_record(node, schema):
    """True for a Run record's name or path. `schema` holds the nodes that
    spell the return contract's schema, assets/schemas/return.json, which no
    Run writes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node not in schema and any(node.value == r or node.value.endswith("/" + r)
                                          for r in RUN_RECORDS)
    return isinstance(node, ast.Attribute) and node.attr in RECORD_PATHS


def _schema_parts(nodes):
    parts = set()
    for node in nodes:
        if isinstance(node, ast.Call) and any(
                isinstance(a, ast.Constant) and a.value == "schemas" for a in node.args):
            parts.update(a for a in node.args if isinstance(a, ast.Constant))
    return parts


def _writes(node):
    """True for a call that writes a file: open() in a write mode, anything
    named for writing or dumping, and os or shutil moving a file into place."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    if name == "open":
        modes = node.args[1:2] + [k.value for k in node.keywords if k.arg == "mode"]
        return any(isinstance(m, ast.Constant) and isinstance(m.value, str)
                   and set(m.value) & set("wax+") for m in modes)
    if "write" in name.lower() or "dump" in name.lower():
        return True
    owner = func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else ""
    return owner == "shutil" or (owner == "os" and name in ("replace", "rename", "link", "symlink"))


def _scopes(tree):
    """Each function or lambda body, and the module's own statements, as the
    list of nodes in it, nested scopes left out."""
    scope_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    found = []

    def collect(root):
        nodes, todo = [], list(ast.iter_child_nodes(root))
        while todo:
            node = todo.pop()
            if isinstance(node, scope_types):
                collect(node)
                continue
            nodes.append(node)
            todo.extend(ast.iter_child_nodes(node))
        found.append(nodes)

    collect(tree)
    return found


def ledger_and_record_writers(scripts_dir, allowed=("runs.py",)):
    """Every script under `scripts_dir` but `allowed` that names
    DELEGATE_LEDGER, or that in one scope names a Run record and writes a
    file; a script that is not Python may not name a Run record at all."""
    offenders = []
    for dirpath, dirnames, filenames in os.walk(scripts_dir):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, scripts_dir)
            if rel in allowed:
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            if "DELEGATE_LEDGER" in text:
                offenders.append(f"{rel} names DELEGATE_LEDGER")
            if not name.endswith(".py"):
                offenders += [f"{rel} names {r}" for r in RUN_RECORDS if r in text]
                continue
            for nodes in _scopes(ast.parse(text, rel)):
                schema = _schema_parts(nodes)
                if any(_names_a_record(n, schema) for n in nodes):
                    offenders += [f"{rel}:{n.lineno} writes beside a Run record"
                                  for n in nodes if _writes(n)]
    return sorted(offenders)


def case_only_runs_py_writes_the_ledger_and_the_run_records():
    found = ledger_and_record_writers(SCRIPTS)
    # The scan is live: it sees runs.py's own writes, and a planted writer.
    in_runs = ledger_and_record_writers(SCRIPTS, allowed=())
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "runs.py"), "w") as f:
            f.write('LEDGER = "DELEGATE_LEDGER"\n')
        with open(os.path.join(td, "planted.py"), "w") as f:
            f.write("import json, os\n\n\ndef end(run_dir, doc):\n"
                    "    with open(os.path.join(run_dir, 'dispatch.json'), 'w') as f:\n"
                    "        json.dump(doc, f)\n")
        with open(os.path.join(td, "relay.sh"), "w") as f:
            f.write('echo "{}" > "$RUN/return.json"\n')
        planted = ledger_and_record_writers(td)
    record("13. no script but runs.py names DELEGATE_LEDGER or writes dispatch.json or return.json",
           found == []
           and any(o.startswith("runs.py:") for o in in_runs)
           and planted == ["planted.py:5 writes beside a Run record", "planted.py:6 writes beside a Run record",
                           "relay.sh names return.json"],
           f"found={found} in_runs={in_runs} planted={planted}")


def case_parse_finish_line():
    with world() as w:
        ended = runs.execute(request(lane="flash-high@agy", harness="agy"), b"p",
                             lambda run: runs.Finish(RETURNED, relay_exit=0, secs=4),
                             os.path.join(w.dir, "a dir"))
        out = "\n".join([
            "delegate: effort override ignored on flash-high@agy; agy carries effort in the model name",
            ended.text(),
        ])
        record("p6. parse_finish_line skips other delegate: lines and keeps a path with a space",
               " " in ended.run
               and runs.parse_finish_line(out) == {"lane": "flash-high@agy", "status": "done",
                                                   "secs": "4", "run": ended.run}
               and runs.parse_finish_line("delegate: dispatching x") is None,
               runs.parse_finish_line(out))


def case_parse_native_line():
    with world() as w:
        ended = runs.execute(request(lane="opus-high@claude", harness="claude"), b"p",
                             lambda run: runs.HandOff("lane-opus-high", "x"), w.root)
        native = ended.text()
        record("p7. the native line is not a finish line, and parses as its own",
               runs.parse_finish_line(native) is None
               and runs.parse_native_line(native) == {
                   "lane": "opus-high@claude", "agent": "lane-opus-high",
                   "prompt": runs.Run(ended.run).prompt_path},
               native)


def main():
    case_a_run_that_returns()
    case_work_that_raises_ends_the_run_blocked()
    case_sigterm_during_work_ends_the_run_blocked_as_terminated()
    case_sigterm_inside_a_relay_adapters_run_ends_the_run_terminated()
    case_a_return_json_that_cannot_be_written_still_ends_the_run()
    case_a_ledger_that_cannot_be_written_never_stops_a_run_ending()
    case_a_usage_limit_refusal_holds_the_lanes_meter()
    case_a_runs_root_that_cannot_be_made_starts_nothing()
    case_a_hand_off_ends_the_run_at_once_as_native()
    case_running_lists_a_run_while_its_work_runs()
    case_a_start_past_its_timeout_or_ended_is_not_running()
    case_running_reads_a_ledger_an_earlier_delegate_wrote()
    case_the_ledger_lines_keep_their_v1_keys_in_order()
    case_only_runs_py_writes_the_ledger_and_the_run_records()
    case_parse_finish_line()
    case_parse_native_line()

    os.environ["DELEGATE_RUNS_DIR"] = "/tmp/delegate-runs-test"
    record("p8. the runs root is the argument, else $DELEGATE_RUNS_DIR",
           runs.root("/x") == "/x" and runs.root() == "/tmp/delegate-runs-test")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
