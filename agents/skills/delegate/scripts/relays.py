#!/usr/bin/env python3
"""relays.py — the Relay seam: one relayed job in, one `runs.Finish` out.

A Relay runs one Job in a separate process and settles what the relay said
into the Finish the Run records. How relayed work ended is `runs.Finish`, and
this module defines no outcome type of its own.

  relay.check() -> Optional[str]             why relays cannot run here now, in one line, or None;
                                             asked before a Run starts
  relay.run(job, run_dir) -> runs.Finish     run_dir already exists

Two adapters:
  Ads       the pinned delegate-skills relays, through node. It alone knows
            the ADS directory (the argument, else $ADS_DIR, else DEFAULT_DIR),
            `ads.sh check`, node, the relay path, the argv, the env overrides,
            relay.stdout and relay.stderr, every result.json key (the usage
            record's spellings it normalizes into Token counts), the form of
            node's crash output, and events.jsonl (through
            `Harness.blocked_reason`).
  Scripted  a fake for tests, scripted with what a relay says (a Report), so
            settling runs under it too; its check answers `ready`.

Ads returns a Finish for every way a relay can fail: node missing at spawn,
no result.json, a result.json that does not parse or is not an object, an
unreadable relay.stderr or events.jsonl. It catches only OSError and
ValueError, and RecursionError from a result.json nested too deep to parse,
so KeyboardInterrupt and the Run's SIGTERM termination pass through to
`runs.execute`, which ends the Run with why.

Settling (the private `_settle(report, job)`) is pure, and reads only the
Job's timeout and write:
  completed:
    - with a return block (status done, partial or blocked) -> the block's status
    - without one, stopped short (`Report.stopped`)        -> blocked (reason: why it stopped)
    - without one, and a final message                    -> partial (open question added)
    - with an empty final message                         -> blocked (reason: empty final message)
  timeout                                                  -> blocked (reason: timeout after <timeout>)
  failed / aborted / *_unavailable                         -> blocked (reason: the relay's error, else its status)
  nothing reported (no result.json, node missing)          -> blocked (reason: why nothing was reported)
  any other status                                         -> blocked (reason: relay status <status>)
  readOnlyViolation on a read-only job                     -> the tripwire question is added
A block keeps at most 12 evidence items with 200-character claims and 5 open
questions; a partial's deliverable is the final message's first 60 lines.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import NamedTuple, Optional

import harnesses
import runs

_ADS_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads.sh")
# ads.sh's own default for $ADS_DIR (`ADS_DIR=${ADS_DIR:-...}`); test_relay a8
# holds the two equal.
DEFAULT_DIR = os.path.expanduser("~/.local/share/delegate/ads")

_STATUSES = ("done", "partial", "blocked")
_TRIPWIRE = "read-only tripwire fired; review the diff"
_NO_BLOCK = "no return block in final message"
_NODE_MISSING = "node is not on PATH; the relay needs Node.js"

# The line where node names an uncaught error ("Error: ...", "TypeError: ...",
# "Error [ERR_MODULE_NOT_FOUND]: ..."), and the version line node ends with.
_NODE_ERROR = re.compile(r"^(?:[A-Za-z_$][\w$]*)?Error(?: \[[^\]]+\])?: ")
_NODE_TRAILER = re.compile(r"^Node\.js v\d")

# Each Token count, keyed like a Lane's price record, and the spellings a
# relay's usage record gives it under, read in this order.
_TOKEN_SPELLINGS = (
    ("in", ("input_tokens", "inputTokens", "prompt_tokens", "promptTokens")),
    ("out", ("output_tokens", "outputTokens", "completion_tokens", "completionTokens")),
    ("cache_read", ("cache_read_input_tokens", "cachedInputTokens", "cached_tokens", "cache_read_tokens")),
    ("cache_write", ("cache_creation_input_tokens", "cacheCreationInputTokens")),
)


class Job(NamedTuple):
    """One relayed job: what a relay needs to run it."""
    harness: str                  # registry name; its adapter names the relay dir and the flags
    model: str
    effort: str                   # the effort this Run takes, after any override
    timeout: str                  # the Lane's timeout, such as "25m"
    prompt: str                   # absolute path of the Run's prompt.md (passed as --brief)
    cwd: str                      # the worker's working directory
    write: Optional[str] = None   # the writable worktree; None is a read-only job


class Report(NamedTuple):
    """What one relay said. An adapter builds it; the fake is scripted with it."""
    status: Optional[str] = None  # completed, timeout, failed, aborted, <harness>_unavailable, ...; None: nothing reported
    final_message: str = ""
    error: Optional[str] = None   # the relay's own account of a failure, or why nothing was reported
    exit: Optional[int] = None    # the relay process's exit code; None when no process ran
    secs: int = 0
    session_id: Optional[str] = None
    tokens: Optional[dict] = None # Token counts {"in","out","cache_read","cache_write"}, or None
    touched_files: Optional[list] = None
    read_only_violation: Optional[bool] = None
    stopped: Optional[str] = None # why a completed job stopped short (Harness.blocked_reason), or None


class Relay:
    """The port: whether relays can run here, and run one Job in a run
    directory that already exists."""

    def check(self):
        """Why relays cannot run on this machine now, in one line, or None."""
        raise NotImplementedError

    def run(self, job, run_dir):
        """How the job ended, settled into a `runs.Finish`."""
        return _settle(self._launch(job, run_dir), job)

    def _launch(self, job, run_dir):
        raise NotImplementedError


class Ads(Relay):
    """The pinned delegate-skills relays, run with node. Their directory is
    `ads_dir`, else the env's $ADS_DIR, else DEFAULT_DIR. `env` is the relay's
    environment (default: this process's)."""

    def __init__(self, ads_dir=None, env=None):
        self.env = env
        given = ads_dir or (os.environ if env is None else env).get("ADS_DIR") or DEFAULT_DIR
        self.ads_dir = os.path.abspath(given)

    def check(self):
        """`ads.sh check` on this adapter's directory: None when node, the pin
        and every relay script are in place, else the first line it printed."""
        env = dict(os.environ if self.env is None else self.env, ADS_DIR=self.ads_dir)
        try:
            proc = subprocess.run(["sh", _ADS_SH, "check"], capture_output=True, text=True, env=env)
        except OSError as e:
            return f"ads: cannot run ads.sh check: {e}"
        if proc.returncode == 0:
            return None
        lines = [line.strip() for line in (proc.stderr + "\n" + proc.stdout).splitlines() if line.strip()]
        return lines[0] if lines else f"ads: ads.sh check failed (exit {proc.returncode})"

    def _launch(self, job, run_dir):
        adapter = harnesses.get(job.harness)
        script = os.path.join(self.ads_dir, "skills", adapter.relay, "scripts", "relay.mjs")
        cmd = ["node", script, "--brief", job.prompt, "--cd", job.cwd, "--out-dir", run_dir,
               "--model", job.model]
        args, env_extra = adapter.run_args(job.effort, job.timeout, job.write)
        cmd.extend(args)
        env = self.env
        if env_extra:
            env = dict(os.environ if env is None else env)
            env.update(env_extra)
        t0 = time.monotonic()
        try:
            with open(os.path.join(run_dir, "relay.stdout"), "wb") as out, \
                    open(os.path.join(run_dir, "relay.stderr"), "wb") as err:
                exit_code = subprocess.run(cmd, stdout=out, stderr=err, env=env).returncode
        except OSError as e:
            # nothing ran: node is gone, or the relay's output could not be opened
            if isinstance(e, FileNotFoundError) and e.filename == "node":
                why = _NODE_MISSING
            else:
                why = f"relay could not start: {e}"
            return Report(error=why, secs=int(time.monotonic() - t0))
        return _read(adapter, run_dir, exit_code, int(time.monotonic() - t0))


def _read(adapter, run_dir, exit_code, secs):
    """The Report a relay left in run_dir: result.json's keys, or why there is none."""
    result_path = os.path.join(run_dir, "result.json")
    if not os.path.isfile(result_path):
        line = _crash_line(os.path.join(run_dir, "relay.stderr"))
        return Report(error=f"relay wrote no result (exit {exit_code})" + (f": {line}" if line else ""),
                      exit=exit_code, secs=secs)
    try:
        with open(result_path, "r", encoding="utf-8", errors="replace") as f:
            doc = json.load(f)
    except (OSError, ValueError, RecursionError) as e:
        # RecursionError: nested deeper than the json module parses
        return Report(status="failed", error=f"corrupt result.json: {e}", exit=exit_code, secs=secs)
    if not isinstance(doc, dict):
        why = f"corrupt result.json: a JSON {type(doc).__name__}, not an object"
        return Report(status="failed", error=why, exit=exit_code, secs=secs)
    status = doc.get("status")
    error = None
    if doc.get("error"):
        error = str(doc["error"])
    elif doc.get("stderrTail"):
        tail = doc["stderrTail"]
        error = "\n".join(str(x) for x in tail) if isinstance(tail, list) else str(tail)
    stopped = None
    if status == "completed":
        try:
            stopped = adapter.blocked_reason(run_dir)
        except (OSError, ValueError):
            stopped = None
    final = doc.get("finalMessage")
    return Report(
        status=status, final_message=str(final) if final else "", error=error, exit=exit_code,
        secs=secs, session_id=doc.get("threadId") or doc.get("sessionId") or doc.get("conversationId"),
        tokens=_tokens(doc.get("usage")), touched_files=doc.get("touchedFiles"),
        read_only_violation=doc.get("readOnlyViolation"), stopped=stopped)


def _tokens(usage):
    """A relay's usage record as Token counts, or None when it reported
    neither input nor output. A count that is not a number is not read."""
    if not isinstance(usage, dict):
        return None
    counts = {key: next((usage[s] for s in spellings if _is_count(usage.get(s))), None)
              for key, spellings in _TOKEN_SPELLINGS}
    if counts["in"] is None and counts["out"] is None:
        return None
    return {key: 0 if n is None else n for key, n in counts.items()}


def _is_count(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _crash_line(stderr_path):
    """Why a relay that wrote no result stopped, from its stderr: the line
    where node names the uncaught error, else the last nonblank line, never
    node's version trailer. "" when there is none or it cannot be read."""
    try:
        with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.rstrip() for line in f if line.strip()]
    except (OSError, ValueError):
        return ""
    named = [line for line in lines if _NODE_ERROR.match(line)]
    if named:
        return named[-1].strip()
    rest = [line.strip() for line in lines if not _NODE_TRAILER.match(line.strip())]
    return rest[-1] if rest else ""


class Scripted(Relay):
    """A fake relay for tests: each run takes the next item of the script, a
    Report to settle or an exception to raise. `jobs` holds the (job, run_dir)
    pairs it ran, in order. Its check answers `ready`: None, or why it
    refuses."""

    def __init__(self, *script, ready=None):
        self._script = list(script)
        self.ready = ready
        self.jobs = []

    def check(self):
        return self.ready

    def _launch(self, job, run_dir):
        self.jobs.append((job, run_dir))
        if not self._script:
            raise AssertionError(f"Scripted relay: the script is exhausted at run {len(self.jobs)}")
        item = self._script.pop(0)
        if isinstance(item, BaseException) or (isinstance(item, type) and issubclass(item, BaseException)):
            raise item
        return item


def _settle(report, job):
    """The Report settled into a `runs.Finish` (the table in the docstring).
    Pure: reads only the Job's timeout and write."""
    status = "blocked"
    reason = None
    deliverable = ""
    evidence, open_questions, changed_files = [], [], []
    relay_status = report.status

    if relay_status is None:
        reason = report.error or "relay reported nothing"
        deliverable = f"blocked: {reason}"
    elif relay_status == "completed":
        block = _find_return_block(report.final_message)
        if block is not None:
            status = block.get("status")
            deliv = block.get("deliverable", "")
            deliverable = deliv if isinstance(deliv, str) else str(deliv)
            evidence = _evidence(block.get("evidence", []))
            oq = block.get("open_questions", [])
            if isinstance(oq, list):
                open_questions = [str(q)[:200] for q in oq[:5] if q is not None]
            cf = block.get("changed_files", [])
            if isinstance(cf, list):
                changed_files = [str(item) for item in cf if item is not None]
            if status == "blocked":
                reason = deliverable
        elif report.stopped is not None:
            # The relay says completed, but the worker did not finish. As on
            # timeout, the final message stays in final.txt.
            reason = report.stopped
            deliverable = f"blocked: {reason}"
        elif report.final_message.strip():
            status = "partial"
            deliverable = "\n".join(report.final_message.splitlines()[:60])
            open_questions = [_NO_BLOCK]
        else:
            reason = "empty final message"
            deliverable = f"blocked: {reason}"
    elif relay_status == "timeout":
        reason = f"timeout after {job.timeout}"
        deliverable = f"blocked: {reason}"
    elif relay_status in ("failed", "aborted") or (
            isinstance(relay_status, str) and relay_status.endswith("_unavailable")):
        reason = report.error or f"relay status {relay_status}"
        deliverable = f"blocked: {reason}"
    else:
        reason = f"relay status {relay_status}"
        deliverable = f"blocked: {reason}"

    if not job.write and report.read_only_violation is True:
        open_questions.append(_TRIPWIRE)

    return runs.Finish(
        {"status": status, "deliverable": deliverable, "evidence": evidence,
         "open_questions": open_questions, "changed_files": changed_files},
        relay_status=relay_status, relay_exit=report.exit, secs=report.secs, reason=reason,
        session_id=report.session_id, tokens=report.tokens, touched_files=report.touched_files,
        read_only_violation=report.read_only_violation,
    )


def _evidence(items):
    """At most 12 well-formed evidence items, each claim cut to 200 characters."""
    kept = []
    if not isinstance(items, list):
        return kept
    for item in items[:12]:
        if isinstance(item, dict) and "file" in item and "line" in item and "claim" in item:
            try:
                kept.append({"file": str(item["file"]), "line": int(item["line"]),
                             "claim": str(item["claim"])[:200]})
            except (TypeError, ValueError, OverflowError):
                pass
    return kept


def _find_return_block(text, max_candidates=200):
    """The last JSON object in text that parses and carries a status of done,
    partial or blocked, or None. Scans from the end; bounded so a brace-heavy
    final message cannot turn the scan quadratic."""
    if not text:
        return None
    r_indices = [i for i, c in enumerate(text) if c == "}"][-max_candidates:]
    for end_idx in reversed(r_indices):
        # 1. the balanced object that ends here
        depth = 0
        candidate_start = None
        for i in range(end_idx, -1, -1):
            if text[i] == "}":
                depth += 1
            elif text[i] == "{":
                depth -= 1
                if depth == 0:
                    candidate_start = i
                    break
        if candidate_start is not None:
            found = _block(text[candidate_start:end_idx + 1])
            if found is not None:
                return found

        # 2. any object that starts before end_idx, latest start first
        c_starts = [i for i, c in enumerate(text[:end_idx]) if c == "{"][-max_candidates:]
        for start_idx in reversed(c_starts):
            candidate = text[start_idx:end_idx + 1]
            if "\"status\"" not in candidate and "'status'" not in candidate:
                continue
            found = _block(candidate)
            if found is not None:
                return found
    return None


def _block(candidate):
    """candidate as a return block, or None."""
    try:
        obj = json.loads(candidate)
    except (ValueError, RecursionError):
        return None
    if isinstance(obj, dict) and obj.get("status") in _STATUSES:
        return obj
    return None
