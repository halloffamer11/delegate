#!/usr/bin/env python3
"""delegate.py — dispatch worker runs through pinned delegate-skills relays.

What a run is:
  A single execution of an external worker on a designated lane (harness × model × effort).
  The worker executes against a specific task brief with either read-only or worktree-write permissions.
  The run manages catalog resolution, prompt assembly, ledger accounting, relay execution,
  and child return normalization.

Run directory: `runs.py` owns it (dispatch.json, prompt.md, return.json, and
the finish line). The relay adds relay.stdout, relay.stderr, result.json,
brief.txt, final.txt and events.jsonl.

Status mapping:
  completed:
    - with return block (status in done, partial, blocked) -> block status
    - without block, a tool cancelled at the permission gate
      (events.jsonl)                                       -> blocked (reason: permission gate cancelled the run at <tool>)
    - without block and non-empty finalMessage             -> partial (open_question added)
    - with empty finalMessage                              -> blocked (reason: empty final message)
  timeout                                                  -> blocked (reason: timeout after <timeout>)
  failed / aborted / *_unavailable                         -> blocked (reason: error / stderrTail / relay status)
  missing result.json                                      -> blocked (reason: relay wrote no result)
  readOnlyViolation on read-only run                       -> appends tripwire notice to open_questions

CLI:
  python3 delegate.py dispatch (--lane <name> | --model <slug>) [--class <c>] --brief <path> --cwd <dir>
          [--write <worktree>] [--effort <e>] [--harness <h>] [--config-dir DIR]
          [--ads-dir DIR] [--runs-dir DIR] [--no-probe] [--no-leash] [--json]
  python3 delegate.py run <class> --brief <path> --cwd <dir> [--write <worktree>] [--tier <n>]
          [--dry-run] [--config-dir DIR] [--meters FILE] [--harnesses a,b,c]
          [--ads-dir DIR] [--runs-dir DIR] [--no-probe] [--no-leash] [--json]

  --json prints one JSON object (`runs.summary`, or `runs.native_summary` for a
  native Lane) in place of the finish and metrics lines; `run --json` sends the
  ranking to stderr.
"""
import argparse
import contextlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from catalog import load_catalog, CatalogError, meters_enabled
from harnesses import NAMES as HARNESSES, EFFORTS
import catalog
import events
import harnesses
import model_queue
import orchestrators
import rank
import runs
import usage

# No orchestrator is assumed. A Lane runs in-process only when the orchestrator
# profile for this run says its harness can (orchestrators.py); otherwise, and
# for every unknown orchestrator, it is relayed.


def parse_timeout_s(timeout_str):
    if not isinstance(timeout_str, str):
        raise ValueError(f"invalid timeout: {timeout_str}")
    if timeout_str.endswith("s"):
        return int(timeout_str[:-1])
    elif timeout_str.endswith("m"):
        return int(timeout_str[:-1]) * 60
    elif timeout_str.endswith("h"):
        return int(timeout_str[:-1]) * 3600
    raise ValueError(f"invalid timeout string: {timeout_str}")


def find_return_block(text, max_candidates=200):
    """Last JSON object in text that parses and carries a status of done, partial,
    or blocked. Scans from the end; bounded so a brace-heavy final message cannot
    turn the scan quadratic."""
    if not text:
        return None
    r_indices = [i for i, c in enumerate(text) if c == "}"][-max_candidates:]
    for end_idx in reversed(r_indices):
        # 1. Balanced depth scan from end_idx backwards
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
            candidate = text[candidate_start:end_idx + 1]
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and obj.get("status") in ("done", "partial", "blocked"):
                    return obj
            except Exception:
                pass

        # 2. Check candidate starts before end_idx in reverse
        c_starts = [i for i, c in enumerate(text[:end_idx]) if c == "{"][-max_candidates:]
        for start_idx in reversed(c_starts):
            candidate = text[start_idx:end_idx + 1]
            if "\"status\"" not in candidate and "'status'" not in candidate:
                continue
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and obj.get("status") in ("done", "partial", "blocked"):
                    return obj
            except Exception:
                continue

    return None


def _lane_model_listing(lanes, harness=None):
    items = []
    for name in sorted(lanes):
        data = lanes[name]
        if harness is None or data.get("harness") == harness:
            items.append(f"{name} ({data.get('model')})")
    return ", ".join(items)


def resolve(lane_name, class_name, brief_path, cwd_dir, write_dir, effort_arg, config_dir, ads_dir, model_slug=None, harness_filter=None, profile=None):
    try:
        cat = load_catalog(cwd=cwd_dir, config_dir=config_dir)
    except CatalogError as e:
        sys.stderr.write(f"delegate: {e}\n")
        sys.exit(2)

    lanes = cat.get("lanes", {})

    if model_slug is not None:
        matches = [
            (name, data) for name, data in lanes.items()
            if data.get("model") == model_slug
        ]
        if harness_filter is not None:
            matches = [(n, d) for n, d in matches if d.get("harness") == harness_filter]
        if not matches:
            # the next wizard run names it (ticket 29); a queue that cannot be
            # written never changes this refusal
            try:
                model_queue.note([{"harness": harness_filter, "model": model_slug}], "asked")
                queued = "; noted for the next delegate global"
            except Exception:
                queued = ""
            if harness_filter is not None:
                listing = _lane_model_listing(lanes, harness_filter)
                sys.stderr.write(
                    f"delegate: no lane runs model '{model_slug}' on {harness_filter}{queued}; lanes on {harness_filter}: {listing}\n"
                )
            else:
                listing = _lane_model_listing(lanes)
                sys.stderr.write(
                    f"delegate: no lane runs model '{model_slug}'{queued}; lanes: {listing}\n"
                )
            sys.exit(2)
        if len(matches) > 1:
            listing = ", ".join(f"{n} ({d.get('harness')})" for n, d in sorted(matches))
            sys.stderr.write(
                f"delegate: model '{model_slug}' matches multiple lanes; pass --harness: {listing}\n"
            )
            sys.exit(2)
        lane_name = matches[0][0]

    if not lane_name or lane_name not in lanes:
        shown = lane_name or ""
        harness = harnesses.split_lane(shown)[1]
        if harness and harness in HARNESSES:
            avail = [l for l, d in lanes.items() if d.get("harness") == harness]
            if avail:
                sys.stderr.write(f"delegate: unknown lane '{shown}'; available lanes for {harness}: {', '.join(sorted(avail))}\n")
            else:
                sys.stderr.write(f"delegate: unknown lane '{shown}'; available lanes: {', '.join(sorted(lanes.keys()))}\n")
        else:
            sys.stderr.write(f"delegate: unknown lane '{shown}'; available lanes: {', '.join(sorted(lanes.keys()))}\n")
        sys.exit(2)

    lane_data = lanes[lane_name]
    harness = lane_data["harness"]

    known_classes = catalog.class_names(cat["routing"])
    if class_name is not None and class_name not in known_classes:
        sys.stderr.write(f"delegate: invalid class '{class_name}'; must be one of {', '.join(known_classes)}\n")
        sys.exit(2)

    if not os.path.isabs(brief_path):
        sys.stderr.write(f"delegate: brief path must be absolute: '{brief_path}'\n")
        sys.exit(2)
    if not os.path.isfile(brief_path):
        sys.stderr.write(f"delegate: brief not found: '{brief_path}'\n")
        sys.exit(2)

    if not os.path.isabs(cwd_dir):
        sys.stderr.write(f"delegate: cwd must be an absolute path: '{cwd_dir}'\n")
        sys.exit(2)
    if not os.path.isdir(cwd_dir):
        sys.stderr.write(f"delegate: cwd not a directory: '{cwd_dir}'\n")
        sys.exit(2)

    if write_dir is not None:
        if not os.path.isabs(write_dir):
            sys.stderr.write(f"delegate: write path must be absolute: '{write_dir}'\n")
            sys.exit(2)
        if not os.path.isdir(write_dir):
            sys.stderr.write(f"delegate: write path not a directory: '{write_dir}'\n")
            sys.exit(2)

    child_cwd = write_dir if write_dir else cwd_dir

    if harness_filter is not None and harness != harness_filter:
        sys.stderr.write(f"delegate: lane '{lane_name}' runs on {harness}, not {harness_filter}\n")
        sys.exit(2)

    # The harness decides what an override does (`Harness.effort_for`): one it
    # does not offer is refused, and one a harness cannot take is ignored.
    adapter = harnesses.get(harness)
    try:
        effort, ignored = adapter.effort_for(lane_data, effort_arg)
    except ValueError as e:
        sys.stderr.write(f"delegate: {e} on {lane_name}; {harness} offers {', '.join(adapter.efforts)}\n")
        sys.exit(2)
    if (ignored is None and orchestrators.is_native(profile, harness)
            and effort_arg is not None and effort_arg != lane_data["effort"]):
        # A native lane runs as its lane-*.md agent, whose file fixes the effort,
        # so an override would be recorded and never used.
        effort = lane_data["effort"]
        ignored = f"a native lane runs at its agent file's effort, {effort}"
    if ignored:
        sys.stderr.write(f"delegate: effort override ignored on {lane_name}; {ignored}\n")
    if effort not in EFFORTS:
        sys.stderr.write(f"delegate: invalid effort '{effort}'; must be one of {', '.join(EFFORTS)}\n")
        sys.exit(2)

    if not adapter.installed():
        sys.stderr.write(
            f"delegate: {harness} CLI is not on PATH; install it or pick a lane on another harness\n"
        )
        sys.exit(2)

    # Only a relayed lane goes through ADS and node. A native lane runs as the
    # orchestrator's own agent, so a machine without node (or ADS) still runs it.
    if not orchestrators.is_native(profile, harness):
        ads_sh = os.path.join(HERE, "ads.sh")
        env = dict(os.environ)
        if ads_dir:
            env["ADS_DIR"] = os.path.abspath(ads_dir)
        proc = subprocess.run(["sh", ads_sh, "check"], capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout).strip()
            sys.stderr.write(f"{msg}\n")
            sys.exit(2)

    resolved_ads_dir = os.path.abspath(ads_dir) if ads_dir else (os.environ.get("ADS_DIR") or os.path.expanduser("~/.local/share/delegate/ads"))

    return {
        "lane": lane_name,
        "lane_data": lane_data,
        "harness": harness,
        "model": lane_data["model"],
        "effort": effort,
        "timeout": lane_data["timeout"],
        "child_cwd": child_cwd,
        "ads_dir": resolved_ads_dir,
        "routing": cat.get("routing", {}),
    }


def should_leash(class_name, no_leash=False, routing=None):
    # The leash is a Class's `leash` in the effective routing (catalog.class_leash).
    # The shipped catalog sets it false for impl and hard-impl, whose real limit
    # is the lane timeout; scout, mechanical and review keep it (review is a
    # reading job bounded by the diff). A Class without the key, or no Class,
    # keeps the conservative leash. --no-leash drops it for one job of any class.
    if no_leash:
        return False
    return catalog.class_leash(routing, class_name)


def build_prompt(child_cwd, harness, write_dir, brief_path, run_dir=None, class_=None, no_leash=False,
                 routing=None):
    preamble_path = os.path.abspath(os.path.join(HERE, "..", "assets", "preamble.md"))
    leash_path = os.path.abspath(os.path.join(HERE, "..", "assets", "preamble-leash.md"))
    schema_path = os.path.abspath(os.path.join(HERE, "..", "assets", "schemas", "return.json"))

    with open(preamble_path, "rb") as f:
        preamble_bytes = f.read()

    leash_active = should_leash(class_, no_leash=no_leash, routing=routing)
    if leash_active:
        with open(leash_path, "rb") as f:
            leash_bytes = f.read().strip()
        anchor = b"no messages. Your final message"
        if anchor not in preamble_bytes:
            # The leash is spliced into the base paragraph at this anchor. Reword
            # preamble.md and the splice would silently drop the sentence, so fail
            # loudly here rather than dispatch a worker with no leash.
            raise RuntimeError(
                f"{preamble_path}: cannot splice the leash: the text "
                f"{anchor.decode()!r} is no longer in the preamble"
            )
        preamble_bytes = preamble_bytes.replace(
            anchor, b"no messages. " + leash_bytes + b" Your final message",
        )

    if not preamble_bytes.endswith(b"\n"):
        preamble_bytes += b"\n"

    if write_dir:
        clause = f"Writes are authorized inside {write_dir} only. Do not commit.\n".encode("utf-8")
    else:
        clause = b"Read-only: do not create, edit, or delete files.\n"

    harness_note = harnesses.get(harness).prompt_note(write_dir).encode("utf-8")

    cwd_section = f"\n# Working directory\n{child_cwd}\nEvery relative path in this brief is under it. Do not search elsewhere.\n\n".encode("utf-8")

    brief_heading = b"# Brief\n"

    with open(brief_path, "rb") as f:
        brief_bytes = f.read()

    if brief_bytes.endswith(b"\n"):
        schema_prefix = b"\n# Return schema\nYour final message must end with exactly one JSON object matching this schema, and nothing after it:\n"
    else:
        schema_prefix = b"\n\n# Return schema\nYour final message must end with exactly one JSON object matching this schema, and nothing after it:\n"

    with open(schema_path, "rb") as f:
        schema_bytes = f.read()
    if not schema_bytes.endswith(b"\n"):
        schema_bytes += b"\n"

    prompt_bytes = (
        preamble_bytes +
        clause +
        harness_note +
        cwd_section +
        brief_heading +
        brief_bytes +
        schema_prefix +
        schema_bytes
    )

    prompt_path = None
    if run_dir is not None:
        prompt_path = os.path.join(run_dir, "prompt.md")
        with open(prompt_path, "wb") as f:
            f.write(prompt_bytes)

    return prompt_bytes, prompt_path


def ledger_start(thread_id, lane, class_name, effort, timeout_str, child_cwd, brief_path, return_path, write_dir):
    timeout_s = parse_timeout_s(timeout_str)
    events.append(events.start_event(
        thread_id=thread_id,
        lane=lane,
        class_=class_name,
        effort=effort,
        timeout_s=timeout_s,
        cwd=child_cwd,
        brief=brief_path,
        out=return_path,
        write=write_dir,
    ))


def probe_meters(no_probe, routing=None):
    if no_probe or (routing is not None and not meters_enabled(routing)):
        return
    usage.acquire(refresh=True, timeout=180)


def run_relay(ads_dir, harness, model, effort, timeout_str, prompt_path, child_cwd, write_dir, run_dir):
    adapter = harnesses.get(harness)
    relay_script = os.path.join(ads_dir, "skills", adapter.relay, "scripts", "relay.mjs")
    cmd = [
        "node",
        relay_script,
        "--brief", prompt_path,
        "--cd", child_cwd,
        "--out-dir", run_dir,
        "--model", model,
    ]
    args, env_extra = adapter.run_args(effort, timeout_str, write_dir)
    cmd.extend(args)
    env = None
    if env_extra:
        env = dict(os.environ)
        env.update(env_extra)

    stdout_path = os.path.join(run_dir, "relay.stdout")
    stderr_path = os.path.join(run_dir, "relay.stderr")

    t0 = time.time()
    with open(stdout_path, "wb") as out_f, open(stderr_path, "wb") as err_f:
        proc = subprocess.run(cmd, stdout=out_f, stderr=err_f, env=env)
    secs = int(time.time() - t0)
    relay_exit = proc.returncode

    return relay_exit, secs


def map_result(run_dir, lane_timeout, relay_exit, write_dir, harness, secs=None):
    result_path = os.path.join(run_dir, "result.json")
    stderr_path = os.path.join(run_dir, "relay.stderr")

    status = "blocked"
    reason = None
    deliverable = ""
    evidence = []
    open_questions = []
    changed_files = []
    relay_status = None
    session_id = None
    usage = None
    touched_files = None
    read_only_violation = None

    if not os.path.isfile(result_path):
        last_stderr_line = ""
        if os.path.isfile(stderr_path):
            with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [l.strip() for l in f if l.strip()]
                if lines:
                    last_stderr_line = lines[-1]
        reason = f"relay wrote no result (exit {relay_exit}): {last_stderr_line}".rstrip()
        deliverable = f"blocked: {reason}"
    else:
        try:
            with open(result_path, "r", encoding="utf-8", errors="replace") as f:
                res_doc = json.load(f)
        except Exception as e:
            res_doc = {"status": "failed", "error": f"corrupt result.json: {e}"}

        relay_status = res_doc.get("status")
        session_id = res_doc.get("threadId") or res_doc.get("sessionId") or res_doc.get("conversationId")
        usage = res_doc.get("usage")
        touched_files = res_doc.get("touchedFiles")
        read_only_violation = res_doc.get("readOnlyViolation")
        final_message = res_doc.get("finalMessage") or ""

        if relay_status == "completed":
            block = find_return_block(final_message)
            # a harness whose events say why the run stopped short has a
            # reason a completed relay status hides (`Harness.blocked_reason`)
            stopped = harnesses.get(harness).blocked_reason(run_dir) if block is None else None
            if block is not None:
                status = block.get("status")
                deliv = block.get("deliverable", "")
                deliverable = deliv if isinstance(deliv, str) else str(deliv)

                ev = block.get("evidence", [])
                if isinstance(ev, list):
                    for item in ev[:12]:
                        if isinstance(item, dict) and "file" in item and "line" in item and "claim" in item:
                            try:
                                evidence.append({
                                    "file": str(item["file"]),
                                    "line": int(item["line"]),
                                    "claim": str(item["claim"])[:200],
                                })
                            except Exception:
                                pass

                oq = block.get("open_questions", [])
                if isinstance(oq, list):
                    for q in oq[:5]:
                        if q is not None:
                            open_questions.append(str(q)[:200])

                cf = block.get("changed_files", [])
                if isinstance(cf, list):
                    for item in cf:
                        if item is not None:
                            changed_files.append(str(item))

                if status == "blocked":
                    reason = deliverable
            elif stopped is not None:
                # The relay says completed, but the worker did not finish. As
                # on timeout, the final message stays in final.txt.
                status = "blocked"
                reason = stopped
                deliverable = f"blocked: {reason}"
            elif final_message.strip():
                status = "partial"
                deliverable = "\n".join(final_message.splitlines()[:60])
                open_questions = ["no return block in final message"]
            else:
                status = "blocked"
                reason = "empty final message"
                deliverable = f"blocked: {reason}"

        elif relay_status == "timeout":
            status = "blocked"
            reason = f"timeout after {lane_timeout}"
            deliverable = f"blocked: {reason}"

        elif relay_status in ("failed", "aborted") or (isinstance(relay_status, str) and relay_status.endswith("_unavailable")):
            status = "blocked"
            if res_doc.get("error"):
                reason = str(res_doc["error"])
            elif res_doc.get("stderrTail"):
                st = res_doc["stderrTail"]
                reason = "\n".join(st) if isinstance(st, list) else str(st)
            else:
                reason = f"relay status {relay_status}"
            deliverable = f"blocked: {reason}"
        else:
            status = "blocked"
            reason = f"relay status {relay_status}"
            deliverable = f"blocked: {reason}"

        if not write_dir and read_only_violation is True:
            open_questions.append("read-only tripwire fired; review the diff")

    runs.Run(run_dir).finish(
        {"status": status, "deliverable": deliverable, "evidence": evidence,
         "open_questions": open_questions, "changed_files": changed_files},
        relay_status=relay_status, relay_exit=relay_exit, secs=secs, reason=reason,
        session_id=session_id, usage=usage, touched_files=touched_files,
        read_only_violation=read_only_violation,
    )
    return_path = runs.Run(run_dir).return_path

    return {
        "status": status,
        "reason": reason,
        "deliverable": deliverable,
        "evidence": evidence,
        "open_questions": open_questions,
        "changed_files": changed_files,
        "relay_status": relay_status,
        "session_id": session_id,
        "usage": usage,
        "touched_files": touched_files,
        "read_only_violation": read_only_violation,
        "return_path": return_path,
    }


def relay_and_map(no_probe, routing, ads_d, harness, model, eff, lane_timeout, prompt_path, child_cwd, write, run_dir, probed=False):
    """Steps 5-7 of dispatch: probe, run the relay, probe, map its result.

    ``probed`` means the caller acquired the Meters just now to rank, so the
    before-probe would only repeat it (and `claude -p /usage` can spend the
    quota it measures).
    """
    # Step 5: Probe meters (before)
    if not probed:
        probe_meters(no_probe, routing)

    # Step 6: Run the relay
    relay_exit, secs = run_relay(
        ads_dir=ads_d,
        harness=harness,
        model=model,
        effort=eff,
        timeout_str=lane_timeout,
        prompt_path=prompt_path,
        child_cwd=child_cwd,
        write_dir=write,
        run_dir=run_dir,
    )

    # Step 5: Probe meters (after)
    probe_meters(no_probe, routing)

    # Step 7: Map the result
    mapped = map_result(
        run_dir=run_dir,
        lane_timeout=lane_timeout,
        relay_exit=relay_exit,
        write_dir=write,
        harness=harness,
        secs=secs,
    )

    return relay_exit, secs, mapped


def note_usage_limit(harness, meter, mapped):
    """Hold the Meter empty when its harness refused the run for its usage
    limit, and release it when a run on it finishes (ticket 43). Never raises:
    the run's own result stands either way."""
    if not meter:
        return
    try:
        if mapped["status"] == "blocked":
            text = "\n".join(str(x) for x in (mapped.get("reason"), mapped.get("deliverable")) if x)
            line = harnesses.get(harness).usage_limit(text)
            if line:
                until = usage.mark_limited(meter, line)
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(until))
                print(f"delegate: {meter} meter held at 0% left until {stamp}: {line}", file=sys.stderr)
        elif mapped["status"] in ("done", "partial"):
            usage.clear_limited(meter)
    except Exception:
        pass


def start_failure(exc):
    """Why a run that the ledger has started could not run, in one line."""
    if isinstance(exc, FileNotFoundError) and exc.filename == "node":
        return "node is not on PATH; the relay needs Node.js"
    if isinstance(exc, KeyboardInterrupt):
        return "dispatch interrupted"
    return f"dispatch failed: {type(exc).__name__}: {exc}"


def fail_run(run_dir, secs, reason):
    """Finish a run that failed after its start (`runs.Run.fail`). Never
    raises: the ledger finish comes after it."""
    _doc, problem = runs.Run(run_dir).fail(secs, reason)
    if problem:
        sys.stderr.write(f"delegate: {problem}\n")
    return {"status": "blocked", "reason": reason, "session_id": None}


def ledger_finish(thread_id, lane, class_name, secs, relay_exit, status, session_id, return_path):
    events.append(events.finish_event(
        thread_id=thread_id,
        lane=lane,
        class_=class_name,
        secs=secs,
        rc=relay_exit if relay_exit is not None else 1,
        status=status,
        child_session=session_id,
        out=return_path,
    ))


def print_and_exit(lane, status, secs, run_dir, thread_id, class_name, relay_exit, as_json=False):
    if as_json:
        print(json.dumps(runs.summary(runs.Run(run_dir), lane, status, secs, class_name, relay_exit), indent=2))
    else:
        class_disp = "-" if class_name is None else class_name
        print(runs.finish_line(lane, status, secs, run_dir))
        print(f"delegate-metrics: thread={thread_id} status={status} class={class_disp} secs={secs} rc={relay_exit}")
    sys.exit(0 if status in ("done", "partial") else 1)


def dispatch(lane, class_, brief, cwd, write=None, effort=None, config_dir=None, ads_dir=None, runs_dir=None, no_probe=False, harness=None, model=None, no_leash=False, probed=False, orchestrator=None, as_json=False):
    profile = load_profile(orchestrator)
    # Step 1: Resolve
    resolved = resolve(
        lane_name=lane,
        class_name=class_,
        brief_path=brief,
        cwd_dir=cwd,
        write_dir=write,
        effort_arg=effort,
        config_dir=config_dir,
        ads_dir=ads_dir,
        model_slug=model,
        harness_filter=harness,
        profile=profile,
    )
    lane = resolved["lane"]
    harness = resolved["harness"]
    model = resolved["model"]
    eff = resolved["effort"]
    lane_timeout = resolved["timeout"]
    child_cwd = resolved["child_cwd"]
    ads_d = resolved["ads_dir"]

    effective_leash = should_leash(class_, no_leash=no_leash, routing=resolved["routing"])
    # at most once a day, a detached look for models the catalog lacks (ticket 29)
    model_queue.kick(config_dir)

    # Step 2: Build the prompt
    prompt_bytes, _ = build_prompt(
        child_cwd=child_cwd,
        harness=harness,
        write_dir=write,
        brief_path=brief,
        class_=class_,
        no_leash=no_leash,
        routing=resolved["routing"],
    )

    # Step 3: Create the Run
    run = runs.Run.create(
        runs_dir, prompt_bytes,
        lane=lane, harness=harness, model=model, effort=eff, timeout=lane_timeout,
        class_name=class_, cwd=cwd, write=write, brief=brief, leash=effective_leash,
        orchestrator=profile["name"] if profile else None,
    )
    run_dir, thread_id, prompt_path = run.path, run.thread_id, run.prompt_path

    # The one native-or-relayed decision: a native Lane stops here, with the
    # Run's prompt for the orchestrator's own agent.
    if orchestrators.is_native(profile, harness):
        abs_prompt = os.path.abspath(prompt_path)
        agent = orchestrators.agent_name(profile, lane)
        spawn = orchestrators.spawn_line(profile, lane, abs_prompt)
        if as_json:
            print(json.dumps(runs.native_summary(lane, agent, abs_prompt, spawn), indent=2))
        else:
            print(runs.native_line(lane, agent, abs_prompt))
            print(f"delegate: spawn: {spawn}")
        sys.exit(0)

    return_path = run.return_path

    # Step 4: Ledger start
    ledger_start(
        thread_id=thread_id,
        lane=lane,
        class_name=class_,
        effort=eff,
        timeout_str=lane_timeout,
        child_cwd=child_cwd,
        brief_path=brief,
        return_path=return_path,
        write_dir=write,
    )

    # Steps 5-8. Anything that stops them, a missing `node` included, would leave
    # the start above with no finish: no return.json, and a running glyph in the
    # statusline until the timeout. So a failure here still finishes the run.
    t0 = time.time()
    try:
        relay_exit, secs, mapped = relay_and_map(
            no_probe=no_probe, routing=resolved.get("routing"), ads_d=ads_d, harness=harness,
            model=model, eff=eff, lane_timeout=lane_timeout, prompt_path=prompt_path,
            child_cwd=child_cwd, write=write, run_dir=run_dir, probed=probed,
        )
    except (Exception, KeyboardInterrupt) as e:
        relay_exit, secs = None, int(time.time() - t0)
        mapped = fail_run(run_dir, secs, start_failure(e))
    note_usage_limit(harness, resolved["lane_data"].get("meter"), mapped)

    # Step 8: Ledger finish
    ledger_finish(
        thread_id=thread_id,
        lane=lane,
        class_name=class_,
        secs=secs,
        relay_exit=relay_exit,
        status=mapped["status"],
        session_id=mapped["session_id"],
        return_path=return_path,
    )

    # Step 9: Print and exit
    print_and_exit(
        lane=lane,
        status=mapped["status"],
        secs=secs,
        run_dir=run_dir,
        thread_id=thread_id,
        class_name=class_,
        relay_exit=relay_exit,
        as_json=as_json,
    )


def run(class_, brief, cwd, write=None, tier=None, dry_run=False, config_dir=None, meters=None, present_harnesses=None, ads_dir=None, runs_dir=None, no_probe=False, no_leash=False, harness=None, orchestrator=None, as_json=False):
    try:
        cat = load_catalog(cwd=cwd, config_dir=config_dir)
    except CatalogError as e:
        sys.stderr.write(f"delegate: {e}\n")
        sys.exit(2)

    known_classes = catalog.class_names(cat["routing"])
    if class_ not in known_classes:
        sys.stderr.write(f"delegate: invalid class '{class_}'; must be one of {', '.join(known_classes)}\n")
        sys.exit(2)

    if harness is not None:
        present_list = None if present_harnesses is None else [h.strip() for h in present_harnesses.split(",")]
        error = (harnesses.constraint_error(harness) if present_list is None else
                 None if harness in present_list else
                 f"harness '{harness}' is not installed; installed: {', '.join(present_list)}")
        if error:
            sys.stderr.write(f"delegate: {error}\n")
            sys.exit(2)
        cat = rank.restrict_to_harness(cat, harness)

    cls_config = cat.get("routing", {}).get("classes", {}).get(class_, {})
    floor = cls_config.get("floor")
    ceiling = cls_config.get("ceiling")
    if tier is not None:
        if floor is not None and ceiling is not None and (tier < floor or tier > ceiling):
            sys.stderr.write(
                f"delegate: tier {tier} outside [{floor}, {ceiling}] for class '{class_}'\n"
            )
            sys.exit(2)

    meters_doc = rank.load_usage(cat, meters, refresh=True)
    # rank.load_usage just acquired the Meters unless a document was passed or
    # metering is off; dispatch then ranks and runs on that one acquisition.
    probed = meters is None and meters_enabled(cat.get("routing", {}))

    if present_harnesses is not None:
        present = set(h.strip() for h in present_harnesses.split(",") if h.strip())
    else:
        present = harnesses.installed()

    rows = rank.rank(class_, cat, meters_doc, present, tier=tier)
    # with --json, stdout carries the one JSON object, so the ranking is
    # written to stderr
    text_out = sys.stderr if as_json else sys.stdout
    with contextlib.redirect_stdout(text_out):
        has_pick = rank.print_rank_output(class_, cat, rows, tier=tier)
    if not has_pick:
        if as_json:
            print(json.dumps({"class": class_, "pick": None}))
        sys.exit(1)

    pick_lane = rows[0]["lane"]
    if dry_run:
        if as_json:
            print(json.dumps({"class": class_, "pick": pick_lane, "dry_run": True}))
        else:
            print("delegate: dry run, nothing dispatched")
        sys.exit(0)

    lane_harness = cat["lanes"][pick_lane]["harness"]
    if not orchestrators.is_native(load_profile(orchestrator), lane_harness):
        print(f"delegate: dispatching {pick_lane}", file=text_out)
    dispatch(
        lane=pick_lane,
        class_=class_,
        brief=brief,
        cwd=cwd,
        write=write,
        effort=None,
        config_dir=config_dir,
        ads_dir=ads_dir,
        runs_dir=runs_dir,
        no_probe=no_probe,
        no_leash=no_leash,
        probed=probed,
        orchestrator=orchestrator,
        as_json=as_json,
    )


def load_profile(name):
    """The orchestrator profile for this run, or None for the default path. A
    broken profile file stops the run: guessing would decide native or relay
    wrongly."""
    try:
        return orchestrators.resolve(name)
    except orchestrators.ProfileError as e:
        sys.stderr.write(f"delegate: orchestrator profile: {e}\n")
        sys.exit(2)


ORCHESTRATOR_HELP = ("the orchestrating harness's profile (assets/orchestrators/); default "
                     "$DELEGATE_ORCHESTRATOR, else detected; 'none' relays every Lane")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(prog="delegate.py", description="Delegate worker dispatcher.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dispatch = sub.add_parser("dispatch", help="dispatch a worker run")
    lane_model = p_dispatch.add_mutually_exclusive_group(required=True)
    lane_model.add_argument("--lane", default=None, help="lane name (e.g. terra-high@codex)")
    lane_model.add_argument("--model", default=None, help="model slug; resolved to a catalog lane")
    p_dispatch.add_argument("--class", dest="class_", default=None, help="work class (e.g. impl)")
    p_dispatch.add_argument("--brief", required=True, help="absolute path to brief file")
    p_dispatch.add_argument("--cwd", required=True, help="working directory")
    p_dispatch.add_argument("--write", default=None, help="writable worktree directory")
    p_dispatch.add_argument("--effort", default=None, help="reasoning effort override")
    p_dispatch.add_argument("--harness", default=None, choices=HARNESSES, help="require the resolved lane to run on this harness")
    p_dispatch.add_argument("--config-dir", default=None, help="directory containing lanes.json and routing.json")
    p_dispatch.add_argument("--ads-dir", default=None, help="directory of amElnagdy/delegate-skills clone")
    p_dispatch.add_argument("--runs-dir", default=None, help="directory where run artifacts are stored (default $DELEGATE_RUNS_DIR, else ~/.cache/delegate/runs)")
    p_dispatch.add_argument("--no-probe", action="store_true", help="skip probing usage meters")
    p_dispatch.add_argument("--no-leash", action="store_true", help="drop the 40-tool-call leash for this job")
    p_dispatch.add_argument("--orchestrator", default=None, help=ORCHESTRATOR_HELP)
    p_dispatch.add_argument("--json", action="store_true", help="print one JSON object in place of the finish lines")

    p_run = sub.add_parser("run", help="rank and dispatch in one step")
    p_run.add_argument("class_", metavar="class", help="work class")
    p_run.add_argument("--brief", required=True, help="absolute path to brief file")
    p_run.add_argument("--cwd", required=True, help="working directory")
    p_run.add_argument("--write", default=None, help="writable worktree directory")
    p_run.add_argument("--tier", type=int, default=None, help="override floor tier for this job")
    p_run.add_argument("--dry-run", action="store_true", help="print ranking only; do not dispatch")
    p_run.add_argument("--config-dir", default=None, help="directory containing lanes.json and routing.json")
    p_run.add_argument("--meters", default=None, help="path to usage document JSON file")
    p_run.add_argument("--harnesses", default=None, help="comma-separated list of present harnesses")
    p_run.add_argument("--harness", default=None,
                       help="the user's harness constraint: rank and run this harness's Lanes only")
    p_run.add_argument("--ads-dir", default=None, help="directory of amElnagdy/delegate-skills clone")
    p_run.add_argument("--runs-dir", default=None, help="directory where run artifacts are stored (default $DELEGATE_RUNS_DIR, else ~/.cache/delegate/runs)")
    p_run.add_argument("--no-probe", action="store_true", help="skip probing usage meters")
    p_run.add_argument("--no-leash", action="store_true", help="drop the 40-tool-call leash for this job")
    p_run.add_argument("--orchestrator", default=None, help=ORCHESTRATOR_HELP)
    p_run.add_argument("--json", action="store_true", help="print one JSON object in place of the finish lines")

    args = parser.parse_args(argv)
    if args.cmd == "dispatch":
        dispatch(
            lane=args.lane,
            class_=args.class_,
            brief=args.brief,
            cwd=args.cwd,
            write=args.write,
            effort=args.effort,
            config_dir=args.config_dir,
            ads_dir=args.ads_dir,
            runs_dir=args.runs_dir,
            no_probe=args.no_probe,
            harness=args.harness,
            model=args.model,
            no_leash=args.no_leash,
            orchestrator=args.orchestrator,
            as_json=args.json,
        )
    elif args.cmd == "run":
        run(
            class_=args.class_,
            brief=args.brief,
            cwd=args.cwd,
            write=args.write,
            tier=args.tier,
            dry_run=args.dry_run,
            config_dir=args.config_dir,
            meters=args.meters,
            present_harnesses=args.harnesses,
            ads_dir=args.ads_dir,
            runs_dir=args.runs_dir,
            no_probe=args.no_probe,
            no_leash=args.no_leash,
            harness=args.harness,
            orchestrator=args.orchestrator,
            as_json=args.json,
        )


if __name__ == "__main__":
    main()
