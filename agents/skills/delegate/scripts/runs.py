#!/usr/bin/env python3
"""runs.py — the Run module: a started Run always finishes.

A Run is one directory under the runs root, and the contract every
orchestrator reads:

  <runs-dir>/<YYYYMMDDTHHMMSSZ>-<lane>-<8 hex from uuid4>/
    dispatch.json   what was asked, and how it ended (DISPATCH_FIELDS); its
                    `tokens` are the Run's Token counts, null when unmeasured
    prompt.md       the assembled prompt
    return.json     the normalized child return (RETURN_FIELDS)
    ...             what the relay itself writes (result.json, which keeps
                    the relay's raw usage record; events.jsonl)

`execute(request, prompt, work)` runs a Run from its start to its Outcome. The
caller supplies only the work, a function of the `Run` that returns a
`Finish` (relayed work) or a `HandOff` (a native Lane's agent takes the
prompt). Before the work: the run directory, prompt.md, dispatch.json with a
null outcome, and the Ledger start. After it, whatever stopped it:
return.json (relayed only), the outcome in dispatch.json, the Meter hold, and
the Ledger finish. A write that fails becomes a note; nothing raises after the
start. Only this module writes dispatch.json and return.json, and only it
writes the Ledger: one v1 line when each Run starts and one when it ends.
Everything else reads a Run with `Run.read`, and the Ledger with `running`.

`Ended.text` spells the finish and metrics lines (a hand-off: the native and
spawn lines), or with `as_json` the one object `delegate dispatch --json` and
`delegate run --json` print. `parse_finish_line` and `parse_native_line` read
the lines back, so no reader keeps a regex of its own.

`running(now)` lists the Runs still running: a Ledger start with no finish,
whose dispatch.json has not ended, within its Lane's timeout. The statusline
counts them, and keeps no reader of the Ledger of its own.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import re
import signal
import threading
import time
from typing import NamedTuple, Optional
import uuid

import harnesses
import usage

DEFAULT_ROOT = "~/.cache/delegate/runs"
# The environment variable that moves the Ledger, for a sandbox (the tests, the
# offline evals). The Ledger's path and its lines are this module's alone.
LEDGER_ENV = "DELEGATE_LEDGER"
_DEFAULT_LEDGER = "~/.cache/delegate/ledger.jsonl"

# Every key dispatch.json carries, in the order it is written. A Run starts
# with the request filled and the outcome null; `execute` fills the outcome.
DISPATCH_FIELDS = (
    "lane", "harness", "model", "effort", "timeout", "class", "leash", "orchestrator",
    "cwd", "write", "brief", "prompt", "thread_id", "started_at",
    "relay_status", "relay_exit", "secs", "status", "reason", "session_id", "session",
    "tokens", "touched_files", "read_only_violation", "finished_at",
)
# The child return contract (assets/schemas/return.json).
RETURN_FIELDS = ("status", "deliverable", "evidence", "open_questions", "changed_files")
_STATUSES = ("done", "partial", "blocked")
# The kinds of a Run's two v1 Ledger lines.
_START_KIND, _FINISH_KIND = "dispatch.start", "dispatch.finish"

FINISH_LINE = re.compile(r"^delegate: (?P<lane>\S+) status=(?P<status>\S+) secs=(?P<secs>\S+) run=(?P<run>.+)$")
NATIVE_LINE = re.compile(r"^delegate: native lane=(?P<lane>\S+) agent=(?P<agent>\S+) prompt=(?P<prompt>.+)$")


class Request(NamedTuple):
    """What dispatch asks for: the request half of dispatch.json."""
    lane: str
    harness: str
    model: str
    effort: str
    timeout: str                       # the Lane's timeout, ^[0-9]+[smh]$
    class_name: Optional[str]
    cwd: str
    write: Optional[str]
    brief: str
    leash: bool = True
    orchestrator: Optional[str] = None
    meter: Optional[str] = None        # the Lane's Meter; the Outcome holds or releases it (not recorded)


class Finish(NamedTuple):
    """How relayed work ended, normalized: the one type for it. Every field
    except `returned` is a DISPATCH_FIELDS outcome key."""
    returned: dict                     # the five RETURN_FIELDS
    relay_status: Optional[str] = None
    relay_exit: Optional[int] = None
    secs: Optional[int] = None         # None: the Run records how long the work took
    reason: Optional[str] = None
    session_id: Optional[str] = None
    tokens: Optional[dict] = None      # Token counts {"in","out","cache_read","cache_write"}; None: unmeasured
    touched_files: Optional[list] = None
    read_only_violation: Optional[bool] = None


class HandOff(NamedTuple):
    """What a native Lane's work returns: the orchestrator's own agent runs the
    Lane on the Run's prompt, and delegate never sees what it hands back."""
    agent: str                         # the orchestrator's agent that runs the Lane
    spawn: str                         # the profile's spawn instruction


def blocked(reason, secs=None):
    """A Run that did no work: status blocked, deliverable 'blocked: <reason>'."""
    return Finish({"status": "blocked", "deliverable": f"blocked: {reason}", "evidence": [],
                   "open_questions": [], "changed_files": []}, secs=secs, reason=reason)


class StartError(Exception):
    """The run directory could not be made. Nothing started."""


def root(runs_dir=None):
    """The runs root, absolute: the argument, else $DELEGATE_RUNS_DIR, else the
    default."""
    param = runs_dir or os.environ.get("DELEGATE_RUNS_DIR") or DEFAULT_ROOT
    return os.path.abspath(os.path.expanduser(param))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_json(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, RecursionError):
        return None


class Run:
    """A handle on one run directory."""

    def __init__(self, path):
        self.path = path

    @property
    def dispatch_path(self):
        return os.path.join(self.path, "dispatch.json")

    @property
    def return_path(self):
        return os.path.join(self.path, "return.json")

    @property
    def prompt_path(self):
        return os.path.join(self.path, "prompt.md")

    def read(self):
        """{"dispatch": dispatch.json or {}, "return": return.json or None}."""
        return {"dispatch": _read_json(self.dispatch_path) or {},
                "return": _read_json(self.return_path)}


class Ended:
    """How `execute` left a Run: what dispatch prints and exits with."""

    def __init__(self, run, lane, status, exit_code, notes, lines, shown):
        self.run = run                 # the run directory
        self.lane = lane
        self.status = status           # done | partial | blocked | native
        self.exit_code = exit_code     # 0 for done, partial and native; else 1
        self.notes = tuple(notes)      # one line each for stderr
        self._lines = tuple(lines)
        self._shown = shown

    def text(self, as_json=False):
        """The finish and metrics lines (a hand-off: the native and spawn
        lines), or with `as_json` the one object that carries their facts."""
        if as_json:
            return json.dumps(self._shown, indent=2)
        return "\n".join(self._lines)


def execute(request, prompt, work, runs_dir=None):
    """Run one Run from its start to its Outcome.

    Raises StartError before the Ledger has a start, or returns an `Ended`;
    never raises after the start. Anything that stops `work` ends the Run
    blocked with why, SIGTERM included. A `HandOff` ends it at once as
    native: no return.json, secs null, and the Meter left as it is.
    """
    run, doc = _start(request, prompt, runs_dir)
    notes = []
    t0 = time.monotonic()
    # Trapped before the Ledger start, so a SIGTERM that lands between the
    # start and the work still ends the Run.
    previous = _trap_sigterm()
    try:
        _attempt(notes, "could not write the Ledger start",
                 lambda: _append(_start_line(request, doc["thread_id"], run.return_path)))
        result = work(run)
    except BaseException as e:
        result = blocked(_why(e))
    finally:
        _release_sigterm(previous)

    handed = isinstance(result, HandOff)
    if handed:
        # delegate never sees how long the agent runs, nor what it hands back
        finish, returned = Finish({}, reason=f"handed to {result.agent}"), None
        status, secs, rc = "native", None, 0
    else:
        finish = _settled(result)
        returned = {key: finish.returned[key] for key in RETURN_FIELDS}
        status = returned["status"]
        secs = finish.secs if finish.secs is not None else int(time.monotonic() - t0)
        rc = finish.relay_exit if finish.relay_exit is not None else 1
    outcome = {
        "relay_status": finish.relay_status, "relay_exit": finish.relay_exit, "secs": secs,
        "status": status, "reason": finish.reason,
        # the session under both of its names
        "session_id": finish.session_id, "session": finish.session_id,
        "tokens": finish.tokens, "touched_files": finish.touched_files,
        "read_only_violation": finish.read_only_violation,
    }
    if returned is not None and not _attempt(notes, "could not write return.json",
                                             lambda: _write_json(run.return_path, returned)):
        # The worker's answer stays in result.json and final.txt.
        outcome.update(status="blocked", reason=notes[-1])
        returned = None
    outcome["finished_at"] = _now()
    doc.update(outcome)
    _attempt(notes, "could not write dispatch.json", lambda: _write_json(run.dispatch_path, doc))
    text = "\n".join(str(x) for x in (outcome["reason"], finish.returned.get("deliverable")) if x)
    held = _settle_meter(request, outcome["status"], text)
    if held:
        notes.append(held)
    _attempt(notes, "could not write the Ledger finish", lambda: _append(_finish_line(
        request, doc["thread_id"], secs, rc, outcome["status"], finish.session_id, run.return_path)))

    status = outcome["status"]
    if handed:
        lines = (_native_line(request.lane, result.agent, run.prompt_path),
                 f"delegate: spawn: {result.spawn}")
        shown = _native_summary(request.lane, result.agent, run.prompt_path, result.spawn)
    else:
        shown = {"lane": request.lane, "status": status, "secs": secs, "run": run.path,
                 "thread": doc["thread_id"], "class": request.class_name, "rc": finish.relay_exit,
                 "return": returned}
        lines = _finish_lines(shown)
    return Ended(run.path, request.lane, status, 0 if status in ("done", "partial", "native") else 1,
                 notes, lines, shown)


class Running(NamedTuple):
    """A Run that has started and has no Outcome yet, within its Lane's timeout."""
    lane: str
    run: Optional[str]                 # the run directory, when its start names one
    started: float                     # epoch seconds, as the Ledger start stamps them
    deadline: float                    # started plus the Lane's timeout


def running(now=None):
    """The Runs running at `now` (default: the time now), in the order they
    started. A Run is running while the Ledger has its start and no finish,
    its dispatch.json has not ended, and `now` is within its start plus its
    timeout. Reads the v1 lines any earlier delegate wrote, and skips a line it
    cannot read. Never raises: a Ledger that cannot be read has none."""
    now = time.time() if now is None else now
    starts = {}
    for entry in _ledger_entries():
        thread = entry.get("thread_id")
        if not isinstance(thread, str) or not thread:
            continue
        if entry.get("kind") == _START_KIND:
            starts[thread] = entry
        elif entry.get("kind") == _FINISH_KIND:
            starts.pop(thread, None)
    found = (_running(start, now) for start in starts.values())
    return [r for r in found if r is not None]


def _ledger_entries():
    """Every Ledger line that is a JSON object; none when the Ledger cannot be read."""
    entries = []
    try:
        with open(_ledger_path(), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except (ValueError, RecursionError):
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except OSError:
        return []
    return entries


def _running(start, now):
    """The Running a Ledger start stands for at `now`, or None: past its
    timeout, ended in its dispatch.json, or a start it cannot read."""
    lane, ts, timeout_s, out = (start.get(k) for k in ("lane", "ts", "timeout_s", "out"))
    if (not isinstance(lane, str) or not isinstance(ts, str)
            or isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float))):
        return None
    try:
        started = datetime.fromisoformat(ts).timestamp()
        deadline = started + timeout_s
    except (ValueError, OverflowError, OSError):
        return None
    # a timeout that is not finite (NaN, Infinity) is not one a start can carry
    if not math.isfinite(deadline) or now > deadline:
        return None
    # The start names the Run's return.json; its directory is the Run's.
    path = (os.path.dirname(out) if isinstance(out, str) else "") or None
    if path is not None:
        # a lost Ledger finish leaves no phantom: dispatch.json says the Run ended
        doc = _read_json(Run(path).dispatch_path)
        if isinstance(doc, dict) and doc.get("finished_at"):
            return None
    return Running(lane, path, started, deadline)


def _start(request, prompt, runs_dir):
    """The run directory, prompt.md and dispatch.json with a null outcome:
    (Run, the dispatch.json document). Raises StartError."""
    base = root(runs_dir)
    try:
        os.makedirs(base, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run = Run(os.path.join(base, f"{stamp}-{request.lane}-{uuid.uuid4().hex[:8]}"))
        os.makedirs(run.path, exist_ok=False)
        with open(run.prompt_path, "wb") as f:
            f.write(prompt)
        doc = dict.fromkeys(DISPATCH_FIELDS)
        doc.update({
            "lane": request.lane, "harness": request.harness, "model": request.model,
            "effort": request.effort, "timeout": request.timeout, "class": request.class_name,
            "leash": request.leash,
            # the orchestrator profile this run was resolved under; null is the
            # default path, where every Lane is relayed
            "orchestrator": request.orchestrator,
            "cwd": request.cwd, "write": request.write, "brief": request.brief,
            "prompt": run.prompt_path, "thread_id": str(uuid.uuid4()), "started_at": _now(),
        })
        _write_json(run.dispatch_path, doc)
    except OSError as e:
        raise StartError(f"could not start a run under {base}: {e}") from e
    return run, doc


def _ledger_path():
    return os.environ.get(LEDGER_ENV) or os.path.expanduser(_DEFAULT_LEDGER)


def _append(entry):
    """Append one line to the Ledger, making its directory. Raises OSError."""
    path = _ledger_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _ledger_now():
    """The Ledger's stamp: local time, to the second."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _start_line(request, thread_id, out):
    """A Run's v1 Ledger start. The keys and their order are the format every
    earlier delegate wrote; `running` reads them back."""
    return {
        "v": 1,
        "kind": _START_KIND,
        "ts": _ledger_now(),
        "thread_id": thread_id,
        "lane": request.lane,
        "class": request.class_name or None,
        "effort": request.effort,
        "timeout_s": _timeout_s(request.timeout),
        "cwd": request.write or request.cwd,
        "brief": request.brief,
        "out": out,
        "write": request.write or None,
    }


def _finish_line(request, thread_id, secs, rc, status, child_session, out):
    """A Run's v1 Ledger finish, in the same v1 format."""
    return {
        "v": 1,
        "kind": _FINISH_KIND,
        "ts": _ledger_now(),
        "thread_id": thread_id,
        "lane": request.lane,
        "class": request.class_name or None,
        # null for a native Run: delegate never sees how long its agent runs
        "secs": None if secs is None else int(secs),
        "rc": int(rc),
        "status": status,
        "child_session": child_session or None,
        "out": out,
    }


def _attempt(notes, what, write):
    """Run one write after the start. A failure becomes a note, never an
    exception: the writes after it still happen. True when it succeeded."""
    try:
        write()
        return True
    except Exception as e:
        notes.append(f"{what}: {e}")
        return False


def _settled(result):
    """The work's result as a Finish whose return has the five fields and a
    known status, else a blocked one that says what was wrong."""
    if not isinstance(result, Finish):
        return blocked(f"dispatch failed: the work returned {type(result).__name__}, "
                       "not a Finish or a HandOff")
    returned = result.returned if isinstance(result.returned, dict) else {}
    lacks = [key for key in RETURN_FIELDS if key not in returned]
    if lacks:
        why = f"dispatch failed: the return lacks {', '.join(lacks)}"
    elif returned["status"] not in _STATUSES:
        why = f"dispatch failed: the return's status is {returned['status']!r}"
    else:
        return result
    return result._replace(returned=blocked(why).returned, reason=why)


class _Terminated(BaseException):
    """SIGTERM during the work. A BaseException, as KeyboardInterrupt is, so
    no `except Exception` inside the work can swallow it."""


def _raise_terminated(signum, frame):
    raise _Terminated()


def _trap_sigterm():
    """Make SIGTERM raise _Terminated. Returns the handler to restore, or None
    off the main thread, where Python cannot install one."""
    if threading.current_thread() is not threading.main_thread():
        return None
    previous = signal.signal(signal.SIGTERM, _raise_terminated)
    # None: the previous handler was not installed from Python
    return signal.SIG_DFL if previous is None else previous


def _release_sigterm(previous):
    if previous is not None:
        signal.signal(signal.SIGTERM, previous)


def _why(exc):
    """Why the work stopped, as a blocked Run's reason."""
    if isinstance(exc, _Terminated):
        return "dispatch terminated (SIGTERM)"
    if isinstance(exc, KeyboardInterrupt):
        return "dispatch interrupted"
    return f"dispatch failed: {type(exc).__name__}: {exc}"


def _timeout_s(timeout):
    if not isinstance(timeout, str):
        raise ValueError(f"invalid timeout: {timeout}")
    if timeout.endswith("s"):
        return int(timeout[:-1])
    if timeout.endswith("m"):
        return int(timeout[:-1]) * 60
    if timeout.endswith("h"):
        return int(timeout[:-1]) * 3600
    raise ValueError(f"invalid timeout string: {timeout}")


def _settle_meter(request, status, text):
    """The Run's one touch of its Lane's Meter (ticket 43). A blocked Run whose
    harness says, in `text`, that its usage limit is reached holds the Meter at
    nothing left; a done or partial Run releases it; any other Run leaves it.
    The hold goes beside the usage cache every reader reads (`usage.hold`,
    `usage.release`). Returns the hold's note, or why the settle failed; never
    raises."""
    meter = request.meter
    if not meter:
        return None
    try:
        if status == "blocked":
            line = harnesses.get(request.harness).usage_limit(text)
            if line:
                until = usage.hold(meter, line)
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(until))
                return f"{meter} meter held at 0% left until {stamp}: {line}"
        elif status in ("done", "partial"):
            usage.release(meter)
    except Exception as e:
        return f"could not settle the {meter} meter: {e}"
    return None


def _finish_lines(summary):
    """The finish line, then the metrics line, from the `--json` summary."""
    s = summary
    class_disp = "-" if s["class"] is None else s["class"]
    return (f"delegate: {s['lane']} status={s['status']} secs={s['secs']} run={s['run']}",
            f"delegate-metrics: thread={s['thread']} status={s['status']} class={class_disp} "
            f"secs={s['secs']} rc={s['rc']}")


def _native_line(lane, agent, prompt):
    return f"delegate: native lane={lane} agent={agent} prompt={prompt}"


def _first(pattern, text):
    for line in (text or "").splitlines():
        found = pattern.match(line.strip())
        if found:
            return found.groupdict()
    return None


def parse_finish_line(text):
    """{lane, status, secs, run} from the first finish line in dispatch's
    output, or None. Other `delegate:` lines (an override warning, the
    native line) are not it."""
    found = _first(FINISH_LINE, text)
    if found:
        found["run"] = found["run"].strip()
    return found


def parse_native_line(text):
    """{lane, agent, prompt} from the native line in dispatch's output, or None."""
    return _first(NATIVE_LINE, text)


def _native_summary(lane, agent, prompt, spawn):
    """What `--json` prints for a native Lane: nothing ran, and the caller
    spawns the agent."""
    return {"native": True, "lane": lane, "agent": agent, "prompt": prompt, "spawn": spawn}
