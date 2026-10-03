#!/usr/bin/env python3
"""test_runs.py — the run directory's one owner (runs.py)."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))
import runs  # noqa: E402

failures = []


def record(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def create(root):
    return runs.Run.create(root, b"the prompt\n", lane="sol-high@codex", harness="codex",
                           model="gpt-6-sol", effort="high", timeout="30m", class_name="impl",
                           cwd="/w", write=None, brief="/w/b.md", leash=False, orchestrator=None)


def main():
    with tempfile.TemporaryDirectory() as root:
        run = create(root)
        read = run.read()
        record("1. create writes the prompt and a dispatch.json with every field, outcome null",
               os.path.basename(run.path).split("-", 1)[1].startswith("sol-high@codex-")
               and open(run.prompt_path, "rb").read() == b"the prompt\n"
               and tuple(read["dispatch"]) == runs.DISPATCH_FIELDS
               and read["dispatch"]["leash"] is False and read["dispatch"]["prompt"] == run.prompt_path
               and read["dispatch"]["thread_id"] == run.thread_id
               and all(read["dispatch"][k] is None for k in ("status", "secs", "finished_at"))
               and read["return"] is None,
               read)

        returned = {"status": "done", "deliverable": "pong", "evidence": [], "open_questions": [],
                    "changed_files": [], "extra": "dropped"}
        run.finish(returned, relay_status="completed", relay_exit=0, secs=12, reason=None,
                   session_id="s-1", usage={"in": 1})
        read = run.read()
        record("2. finish writes the return's five fields and the outcome, the session under both names",
               read["return"] == {k: returned[k] for k in runs.RETURN_FIELDS}
               and read["dispatch"]["status"] == "done" and read["dispatch"]["secs"] == 12
               and read["dispatch"]["session_id"] == "s-1" and read["dispatch"]["session"] == "s-1"
               and read["dispatch"]["touched_files"] is None and read["dispatch"]["finished_at"]
               and read["dispatch"]["lane"] == "sol-high@codex",
               read)

        failed = create(root)
        doc, problem = failed.fail(3, "node is not on PATH; the relay needs Node.js")
        read = failed.read()
        record("3. fail records a blocked run with its reason",
               problem is None and doc["status"] == "blocked"
               and read["return"]["deliverable"] == "blocked: node is not on PATH; the relay needs Node.js"
               and read["dispatch"]["status"] == "blocked" and read["dispatch"]["secs"] == 3,
               read)

        bare = runs.Run(os.path.join(root, "bare"))
        os.makedirs(bare.path)
        bare.finish(returned, relay_status="completed")
        record("4. finish on a directory with no dispatch.json writes the return only",
               bare.read() == {"dispatch": {}, "return": {k: returned[k] for k in runs.RETURN_FIELDS}},
               bare.read())

        summary = runs.summary(run, "sol-high@codex", "done", 12, "impl", 0)
        record("5. summary carries the finish and metrics lines' facts and the return",
               summary == {"lane": "sol-high@codex", "status": "done", "secs": 12, "run": run.path,
                           "thread": run.thread_id, "class": "impl", "rc": 0,
                           "return": run.read()["return"]}
               and json.loads(json.dumps(summary)) == summary,
               summary)

    out = "\n".join([
        "delegate: effort override ignored on flash-high@agy; agy carries effort in the model name",
        runs.finish_line("flash-high@agy", "done", 4, "/runs/a dir"),
        "delegate-metrics: thread=t status=done class=impl secs=4 rc=0",
    ])
    record("6. parse_finish_line skips other delegate: lines and keeps a path with a space",
           runs.parse_finish_line(out) == {"lane": "flash-high@agy", "status": "done", "secs": "4",
                                           "run": "/runs/a dir"}
           and runs.parse_finish_line("delegate: dispatching x") is None,
           runs.parse_finish_line(out))
    native = runs.native_line("opus-high@claude", "lane-opus-high", "/runs/p/prompt.md")
    record("7. the native line is not a finish line, and parses as its own",
           runs.parse_finish_line(native) is None
           and runs.parse_native_line(native + "\ndelegate: spawn: x") == {
               "lane": "opus-high@claude", "agent": "lane-opus-high", "prompt": "/runs/p/prompt.md"},
           native)
    os.environ["DELEGATE_RUNS_DIR"] = "/tmp/delegate-runs-test"
    record("8. the runs root is the argument, else $DELEGATE_RUNS_DIR",
           runs.root("/x") == "/x" and runs.root() == "/tmp/delegate-runs-test")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
