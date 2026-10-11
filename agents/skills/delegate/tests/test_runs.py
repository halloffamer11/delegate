#!/usr/bin/env python3
"""test_runs.py — the Run module (runs.py): a started Run always finishes.

Every case drives `runs.execute` in-process against a temp runs root, a temp
$DELEGATE_LEDGER and a temp $DELEGATE_CACHE. The work is a plain function.
"""
import contextlib
from datetime import datetime
import json
import os
import signal
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))
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


def case_running_reads_a_ledger_an_earlier_delegate_wrote():
    def stamp(epoch):
        return datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="seconds")

    def start(thread, lane, ts, timeout_s, out):
        return (f'{{"v": 1, "kind": "dispatch.start", "ts": {json.dumps(ts)}, '
                f'"thread_id": {json.dumps(thread)}, "lane": {json.dumps(lane)}, "class": "impl", '
                f'"effort": "high", "timeout_s": {json.dumps(timeout_s)}, "cwd": "/w", '
                f'"brief": "/w/b.md", "out": {json.dumps(out)}, "write": null}}')

    with world() as w:
        now = float(int(time.time()))
        open_run = os.path.join(w.root, "20261011T080000Z-flash-high@agy-0a0a0a0a")
        os.makedirs(open_run)
        with open(os.path.join(open_run, "dispatch.json"), "w", encoding="utf-8") as f:
            json.dump({"lane": "flash-high@agy", "status": None, "finished_at": None}, f)
        elsewhere = os.path.join(w.root, "gone", "return.json")
        # Today's v1 lines, as delegate and its probes write them: a meter event,
        # an open start, a start past its timeout and a start with its finish.
        lines = [
            f'{{"v": 1, "kind": "meter", "ts": "{stamp(now - 900)}", "source": "probe", '
            f'"cache_age_s": 0, "probed_at": {now - 900}, "lanes": []}}',
            start("t-open", "flash-high@agy", stamp(now - 100), 1500,
                  os.path.join(open_run, "return.json")),
            start("t-stale", "terra-high@codex", stamp(now - 1000), 300, elsewhere),
            start("t-pair", "grok46-high@grok", stamp(now - 200), 2400, elsewhere),
            f'{{"v": 1, "kind": "dispatch.finish", "ts": "{stamp(now - 150)}", "thread_id": "t-pair", '
            f'"lane": "grok46-high@grok", "class": "impl", "secs": 50, "rc": 0, "status": "done", '
            f'"child_session": null, "out": {json.dumps(elsewhere)}}}',
            # lines that are not objects
            "[1]", '"dispatch.start"', "42", "null", "{not json", "",
            # starts it cannot read
            start("t-ts", "luna-low@codex", "yesterday", 600, elsewhere),
            start("t-timeout", "luna-low@codex", stamp(now - 100), "10m", elsewhere),
            start([1], "luna-low@codex", stamp(now - 100), 600, elsewhere),
            start("t-lane", None, stamp(now - 100), 600, elsewhere),
        ]
        with open(w.ledger, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        read = runs.running(now)
        os.remove(w.ledger)
        missing = runs.running(now)
        os.mkdir(w.ledger)
        unreadable = runs.running(now)
        record("11. running reads a Ledger an earlier delegate wrote, and skips lines that are not objects",
               read == [runs.Running("flash-high@agy", open_run, now - 100, now - 100 + 1500)]
               and missing == [] and unreadable == [],
               f"read={read} missing={missing} unreadable={unreadable}")


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
    case_a_return_json_that_cannot_be_written_still_ends_the_run()
    case_a_ledger_that_cannot_be_written_never_stops_a_run_ending()
    case_a_usage_limit_refusal_holds_the_lanes_meter()
    case_a_runs_root_that_cannot_be_made_starts_nothing()
    case_a_hand_off_ends_the_run_at_once_as_native()
    case_running_lists_a_run_while_its_work_runs()
    case_a_start_past_its_timeout_or_ended_is_not_running()
    case_running_reads_a_ledger_an_earlier_delegate_wrote()
    case_parse_finish_line()
    case_parse_native_line()

    os.environ["DELEGATE_RUNS_DIR"] = "/tmp/delegate-runs-test"
    record("p8. the runs root is the argument, else $DELEGATE_RUNS_DIR",
           runs.root("/x") == "/x" and runs.root() == "/tmp/delegate-runs-test")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
