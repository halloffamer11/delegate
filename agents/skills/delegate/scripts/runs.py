#!/usr/bin/env python3
"""runs.py — the run directory's one owner.

A Run is one directory under the runs root, and the contract every
orchestrator reads:

  <runs-dir>/<YYYYMMDDTHHMMSSZ>-<lane>-<8 hex from uuid4>/
    dispatch.json   what was asked, and how it ended (DISPATCH_FIELDS)
    prompt.md       the assembled prompt
    return.json     the normalized child return (RETURN_FIELDS)
    ...             what the relay itself writes (result.json, events.jsonl)

Only this module writes dispatch.json and return.json. `delegate.py` creates
a Run, and finishes or fails it; everything else reads one with `Run.read`.

Dispatch prints one finish line per relayed run, and one native line for a
Lane the orchestrator runs itself. `finish_line` and `native_line` spell them,
and `parse_finish_line` and `parse_native_line` read them back, so no reader
keeps a regex of its own. `delegate dispatch --json` and `delegate run --json`
print `summary` instead, for a reader that would rather not parse text.
"""
from datetime import datetime, timezone
import json
import os
import re
import uuid

DEFAULT_ROOT = "~/.cache/delegate/runs"

# Every key dispatch.json carries, in the order it is written. A Run starts
# with the request filled and the outcome null; `finish` and `fail` fill it.
DISPATCH_FIELDS = (
    "lane", "harness", "model", "effort", "timeout", "class", "leash", "orchestrator",
    "cwd", "write", "brief", "prompt", "thread_id", "started_at",
    "relay_status", "relay_exit", "secs", "status", "reason", "session_id", "session",
    "usage", "touched_files", "read_only_violation", "finished_at",
)
# The child return contract (assets/schemas/return.json).
RETURN_FIELDS = ("status", "deliverable", "evidence", "open_questions", "changed_files")

FINISH_LINE = re.compile(r"^delegate: (?P<lane>\S+) status=(?P<status>\S+) secs=(?P<secs>\S+) run=(?P<run>.+)$")
NATIVE_LINE = re.compile(r"^delegate: native lane=(?P<lane>\S+) agent=(?P<agent>\S+) prompt=(?P<prompt>.+)$")


def root(runs_dir=None):
    """The runs root: the argument, else $DELEGATE_RUNS_DIR, else the default."""
    param = runs_dir or os.environ.get("DELEGATE_RUNS_DIR")
    return os.path.abspath(os.path.expanduser(param)) if param else os.path.expanduser(DEFAULT_ROOT)


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
    except (OSError, ValueError):
        return None


class Run:
    """One run directory."""

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

    @classmethod
    def create(cls, runs_dir, prompt_bytes, *, lane, harness, model, effort, timeout, class_name,
               cwd, write, brief, leash=True, orchestrator=None):
        """A new Run under the runs root, holding the prompt and a dispatch.json
        with the request filled and the outcome null."""
        base = root(runs_dir)
        os.makedirs(base, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run = cls(os.path.join(base, f"{stamp}-{lane}-{uuid.uuid4().hex[:8]}"))
        os.makedirs(run.path, exist_ok=False)
        with open(run.prompt_path, "wb") as f:
            f.write(prompt_bytes)
        doc = dict.fromkeys(DISPATCH_FIELDS)
        doc.update({
            "lane": lane, "harness": harness, "model": model, "effort": effort,
            "timeout": timeout, "class": class_name, "leash": leash,
            # the orchestrator profile this run was resolved under; null is the
            # default path, where every Lane is relayed
            "orchestrator": orchestrator,
            "cwd": cwd, "write": write, "brief": brief, "prompt": run.prompt_path,
            "thread_id": str(uuid.uuid4()), "started_at": _now(),
        })
        _write_json(run.dispatch_path, doc)
        return run

    def read(self):
        """{"dispatch": dispatch.json or {}, "return": return.json or None}."""
        return {"dispatch": _read_json(self.dispatch_path) or {},
                "return": _read_json(self.return_path)}

    @property
    def thread_id(self):
        return self.read()["dispatch"].get("thread_id")

    def _update(self, fields, create=False):
        doc = _read_json(self.dispatch_path)
        if doc is None:
            if not create and not os.path.isfile(self.dispatch_path):
                return
            doc = {}
        doc.update(fields)
        _write_json(self.dispatch_path, doc)

    def finish(self, returned, **outcome):
        """Write the child return and record the outcome in dispatch.json.

        `returned` holds RETURN_FIELDS; `outcome` the dispatch.json outcome
        keys the relay gave (relay_status, relay_exit, secs, reason, ...).
        The status is the return's, and the session is recorded under both of
        its names.
        """
        doc = {key: returned[key] for key in RETURN_FIELDS}
        _write_json(self.return_path, doc)
        fields = {key: None for key in DISPATCH_FIELDS[DISPATCH_FIELDS.index("relay_status"):]}
        fields.update(outcome)
        fields["status"] = doc["status"]
        fields["session"] = fields.get("session_id")
        fields["finished_at"] = _now()
        self._update(fields)
        return doc

    def fail(self, secs, reason):
        """Record a run that failed after its start: blocked, as for a relay
        that fails, since return.json has no other word for a run that did no
        work. Never raises: the ledger finish comes after it, and a file that
        cannot be written must not leave the run running."""
        doc = {"status": "blocked", "deliverable": f"blocked: {reason}", "evidence": [],
               "open_questions": [], "changed_files": []}
        try:
            _write_json(self.return_path, doc)
        except OSError as e:
            return doc, f"could not write return.json: {e}"
        try:
            self._update({"status": "blocked", "reason": reason, "secs": secs,
                          "finished_at": _now()}, create=True)
        except OSError as e:
            return doc, f"could not write dispatch.json: {e}"
        return doc, None


def finish_line(lane, status, secs, run_dir):
    return f"delegate: {lane} status={status} secs={secs} run={run_dir}"


def native_line(lane, agent, prompt):
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


def summary(run, lane, status, secs, class_name, relay_exit):
    """What `--json` prints for a relayed run: the finish and metrics lines'
    facts and the child return."""
    read = run.read()
    return {"lane": lane, "status": status, "secs": secs, "run": run.path,
            "thread": read["dispatch"].get("thread_id"), "class": class_name,
            "rc": relay_exit, "return": read["return"]}


def native_summary(lane, agent, prompt, spawn):
    """What `--json` prints for a native Lane: nothing ran, and the caller
    spawns the agent."""
    return {"native": True, "lane": lane, "agent": agent, "prompt": prompt, "spawn": spawn}
