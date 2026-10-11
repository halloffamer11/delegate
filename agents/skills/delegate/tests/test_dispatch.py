#!/usr/bin/env python3
"""test_dispatch.py — tests for delegate.py dispatch path.
Run: python3 tests/test_dispatch.py
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so that
# `catalog.find_git_root()` never finds the invoking checkout's own
# `.delegate/routing.json`. Every path this file needs comes from HERE.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
DELEGATE_DIR = os.path.abspath(os.path.join(HERE, "..", "scripts"))
DELEGATE_PY = os.path.join(DELEGATE_DIR, "delegate.py")
COURIER_MD = os.path.join(HERE, "..", "assets", "orchestrators", "claude", "courier.md")

sys.path.insert(0, DELEGATE_DIR)
import delegate  # noqa: E402
import evals  # noqa: E402
import runs  # noqa: E402


fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}", file=sys.stderr)


def meter(name, weekly=None, five_h=None, pace=None, status="ok", note=None):
    known = [x for x in (five_h, weekly) if x is not None]
    r = min(known) if known else None
    binding = None
    if r is not None:
        binding = "weekly" if (weekly is not None and (five_h is None or weekly <= five_h)) else "5h"
    harness = name.split("-")[0] if "-" in name else name
    meter_sub = name.split("-", 1)[1] if "-" in name else None
    return {
        "lane": name,
        "harness": harness,
        "meter": meter_sub,
        "remaining_5h": five_h,
        "remaining_weekly": weekly,
        "r": r,
        "binding": binding,
        "reset_5h": None,
        "reset_weekly": None,
        "reset_binding": None,
        "cycle_left": None,
        "pace": pace,
        "score": pace if pace is not None else r,
        "status": status,
        "rollover_soon": False,
        "note": note,
    }


def write_meters_doc(path, meters_list):
    doc = {"probed_at": 1700000000, "lanes": meters_list}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return path


def run_delegate(world, command, args, extra_env=None, orchestrator=None, config_dir=None):
    """`delegate <command>` in the offline world, on its catalog unless
    `config_dir` names another."""
    env = dict(world.env)
    if extra_env:
        env.update(extra_env)
    cmd = [
        sys.executable,
        DELEGATE_PY,
        command,
        "--config-dir", config_dir or world.config_dir,
        "--ads-dir", world.ads_dir,
        "--runs-dir", world.runs_dir,
        "--no-probe",
    ] + args
    if orchestrator is not None:
        cmd += ["--orchestrator", orchestrator]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def run_dispatch(world, args, **kw):
    return run_delegate(world, "dispatch", args, **kw)


def run_run(world, args, **kw):
    return run_delegate(world, "run", args, **kw)


def parse_run_dir_from_stdout(stdout):
    found = runs.parse_finish_line(stdout)
    return found["run"] if found else None


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        # The offline world the evals run in, plus a worktree to dispatch
        # into. The cases were written with Claude Code orchestrating, so that
        # is the profile they run under unless one names another.
        world = evals.OfflineWorld(tmpdir)
        world.env["DELEGATE_ORCHESTRATOR"] = "claude"
        cwd = os.path.join(tmpdir, "worktree")
        os.makedirs(cwd)

        def make_brief(name, content):
            p = os.path.join(tmpdir, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return p

        def make_final(name, content):
            p = os.path.join(tmpdir, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return p

        # -------------------------------------------------------------
        # 1. Completed with a valid done block
        # -------------------------------------------------------------
        done_final = make_final("done_final.json", json.dumps({
            "status": "done",
            "deliverable": "all done deliverable",
            "evidence": [{"file": "test.py", "line": 42, "claim": "it works"}],
            "open_questions": [],
            "changed_files": ["test.py"]
        }))
        b1 = make_brief("b1.md", f"fake-relay: status=completed final={done_final}\nPlease test this.")
        res1 = run_dispatch(world, [
            "--lane", "terra-high@codex",
            "--class", "impl",
            "--brief", b1,
            "--cwd", cwd,
        ])
        run_dir1 = parse_run_dir_from_stdout(res1.stdout)
        ok1 = (res1.returncode == 0 and run_dir1 is not None and os.path.isdir(run_dir1))
        if ok1:
            ret1 = json.load(open(os.path.join(run_dir1, "return.json")))
            disp1 = json.load(open(os.path.join(run_dir1, "dispatch.json")))
            ok1 = (
                ret1.get("status") == "done" and
                ret1.get("deliverable") == "all done deliverable" and
                len(ret1.get("evidence", [])) == 1 and
                ret1["evidence"][0]["line"] == 42 and
                disp1.get("secs") is not None and
                disp1.get("session_id") == "fake-thread" and
                set(ret1.keys()) == {"status", "deliverable", "evidence", "open_questions", "changed_files"}
            )
        record("1. completed done block", ok1, f"rc={res1.returncode} stdout={res1.stdout} stderr={res1.stderr}")

        # -------------------------------------------------------------
        # 7. Byte fidelity
        # -------------------------------------------------------------
        raw_brief_bytes = b"\tline with tab\n  trailing spaces   \n- dash bullet\nnon-ascii: \xe2\x98\x83 snowman\nfake-relay: status=completed\n"
        b7_path = os.path.join(tmpdir, "b7_fidelity.md")
        with open(b7_path, "wb") as f:
            f.write(raw_brief_bytes)

        res7 = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b7_path, "--cwd", cwd])
        run_dir7 = parse_run_dir_from_stdout(res7.stdout)
        prompt7_path = os.path.join(run_dir7, "prompt.md") if run_dir7 else None
        brief_copy_path = os.path.join(run_dir7, "brief.txt") if run_dir7 else None

        with open(prompt7_path, "rb") as f:
            prompt_bytes = f.read()
        with open(brief_copy_path, "rb") as f:
            brief_copy_bytes = f.read()

        brief_heading = b"# Brief\n"
        schema_heading = b"# Return schema\n"
        h_idx = prompt_bytes.find(brief_heading)
        s_idx = prompt_bytes.find(schema_heading)
        between_bytes = prompt_bytes[h_idx + len(brief_heading):s_idx].rstrip(b"\n")
        expected_between = raw_brief_bytes.rstrip(b"\n")

        ok7 = (
            between_bytes == expected_between and
            brief_copy_bytes == prompt_bytes
        )
        record("7. byte fidelity", ok7, f"equal={brief_copy_bytes == prompt_bytes}")

        # -------------------------------------------------------------
        # 8. Two dispatches produce two different run directories
        # -------------------------------------------------------------
        b8 = make_brief("b8.md", "fake-relay: status=completed\nBrief 8.")
        res8a = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b8, "--cwd", cwd])
        res8b = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b8, "--cwd", cwd])
        dir8a = parse_run_dir_from_stdout(res8a.stdout)
        dir8b = parse_run_dir_from_stdout(res8b.stdout)
        ok8 = (
            dir8a is not None and dir8b is not None and
            dir8a != dir8b and
            os.path.isdir(dir8a) and os.path.isdir(dir8b)
        )
        record("8. distinct run directories", ok8, f"dir1={dir8a} dir2={dir8b}")

        # -------------------------------------------------------------
        # 9. argv per harness
        # -------------------------------------------------------------
        b9 = make_brief("b9.md", "fake-relay: status=completed\nArgv test.")

        # 9a: terra-high@codex read-only
        res9a = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b9, "--cwd", cwd])
        dir9a = parse_run_dir_from_stdout(res9a.stdout)
        argv9a = json.load(open(os.path.join(dir9a, "argv.json")))
        exp9a = ["--model", "gpt-5.6-terra", "--effort", "high", "--timeout", "25m", "--read-only", "--ignore-user-config", "--skip-git-repo-check"]
        ok9a = all(x in argv9a for x in exp9a)

        # 9a2: with a codex home of delegate's own, the run points CODEX_HOME at
        # it and drops --ignore-user-config. The worker then reads that home's
        # config alone — one MCP server, the disposable browser — and nothing in
        # ~/.codex: no plugins, no Gmail, no hooks, no AGENTS.md.
        delegate_codex_home = os.path.join(tmpdir, "delegate-codex-home")
        os.makedirs(delegate_codex_home, exist_ok=True)
        with open(os.path.join(delegate_codex_home, "config.toml"), "w") as f:
            f.write('approvals_reviewer = "auto_review"\n\n[mcp_servers.playwright]\ncommand = "npx"\nargs = []\n')
        res9a2 = run_dispatch(
            world,
            ["--lane", "terra-high@codex", "--class", "impl", "--brief", b9, "--cwd", cwd],
            extra_env={"DELEGATE_CODEX_HOME": delegate_codex_home},
        )
        dir9a2 = parse_run_dir_from_stdout(res9a2.stdout)
        argv9a2 = json.load(open(os.path.join(dir9a2, "argv.json")))
        env9a2 = json.load(open(os.path.join(dir9a2, "env.json")))
        ok9a2 = (
            "--ignore-user-config" not in argv9a2 and
            "--skip-git-repo-check" in argv9a2 and
            env9a2.get("CODEX_HOME") == delegate_codex_home
        )
        record("9a2. codex home replaces --ignore-user-config", ok9a2, f"argv={argv9a2} env={env9a2}")

        # 9b: terra-high@codex with --effort low
        res9b = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b9, "--cwd", cwd, "--effort", "low"])
        dir9b = parse_run_dir_from_stdout(res9b.stdout)
        argv9b = json.load(open(os.path.join(dir9b, "argv.json")))
        ok9b = ("--effort" in argv9b and argv9b[argv9b.index("--effort") + 1] == "low")

        # 9c: terra-high@codex with --write
        res9c = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b9, "--cwd", cwd, "--write", cwd])
        dir9c = parse_run_dir_from_stdout(res9c.stdout)
        argv9c = json.load(open(os.path.join(dir9c, "argv.json")))
        ok9c = ("--read-only" not in argv9c)

        # 9d: flash-high@agy read-only
        res9d = run_dispatch(world, ["--lane", "flash-high@agy", "--class", "impl", "--brief", b9, "--cwd", cwd])
        dir9d = parse_run_dir_from_stdout(res9d.stdout)
        argv9d = json.load(open(os.path.join(dir9d, "argv.json")))
        ok9d = ("--print-timeout" in argv9d and argv9d[argv9d.index("--print-timeout") + 1] == "25m" and "--effort" not in argv9d and "--read-only" in argv9d and "--dangerously-skip-permissions" not in argv9d)

        # 9e: flash-high@agy with --write
        res9e = run_dispatch(world, ["--lane", "flash-high@agy", "--class", "impl", "--brief", b9, "--cwd", cwd, "--write", cwd])
        dir9e = parse_run_dir_from_stdout(res9e.stdout)
        argv9e = json.load(open(os.path.join(dir9e, "argv.json")))
        ok9e = ("--dangerously-skip-permissions" in argv9e and "--read-only" not in argv9e)

        # 9f: fable-xhigh@claude (relay path when ORCHESTRATOR is codex)
        res9f = run_dispatch(world, ["--lane", "fable-xhigh@claude", "--class", "impl", "--brief", b9, "--cwd", cwd], orchestrator="codex")
        dir9f = parse_run_dir_from_stdout(res9f.stdout)
        argv9f = json.load(open(os.path.join(dir9f, "argv.json")))
        ok9f = ("--effort" in argv9f and argv9f[argv9f.index("--effort") + 1] == "xhigh" and "--timeout" in argv9f and argv9f[argv9f.index("--timeout") + 1] == "60m")

        # 9g: grok46-high@grok
        res9g = run_dispatch(world, ["--lane", "grok46-high@grok", "--class", "impl", "--brief", b9, "--cwd", cwd])
        dir9g = parse_run_dir_from_stdout(res9g.stdout)
        argv9g = json.load(open(os.path.join(dir9g, "argv.json")))
        ok9g = ("--effort" in argv9g and argv9g[argv9g.index("--effort") + 1] == "high" and "--timeout" in argv9g and argv9g[argv9g.index("--timeout") + 1] == "40m")

        # 9h: no argv ever contains --lane, --max-turns, or --max-budget-usd
        all_argvs = [argv9a, argv9b, argv9c, argv9d, argv9e, argv9f, argv9g]
        forbidden = {"--lane", "--max-turns", "--max-budget-usd"}
        ok9h = not any(forbidden.intersection(set(a)) for a in all_argvs)

        ok9 = ok9a and ok9b and ok9c and ok9d and ok9e and ok9f and ok9g and ok9h
        record("9. argv per harness", ok9, f"9a={ok9a} 9b={ok9b} 9c={ok9c} 9d={ok9d} 9e={ok9e} 9f={ok9f} 9g={ok9g} 9h={ok9h}")

        # -------------------------------------------------------------
        # 10. --effort on an agy lane is ignored; proceed with lane effort
        # -------------------------------------------------------------
        b10 = make_brief("b10.md", f"fake-relay: status=completed final={done_final}\nBrief 10.")
        res10 = run_dispatch(world, ["--lane", "flash-high@agy", "--class", "impl", "--brief", b10, "--cwd", cwd, "--effort", "low"])
        dir10 = parse_run_dir_from_stdout(res10.stdout)
        ignore_msg = "delegate: effort override ignored on flash-high@agy; agy carries effort in the model name"
        ok10 = (
            res10.returncode == 0 and
            ignore_msg in res10.stderr and
            dir10 is not None
        )
        if ok10:
            disp10 = json.load(open(os.path.join(dir10, "dispatch.json")))
            argv10 = json.load(open(os.path.join(dir10, "argv.json")))
            ok10 = disp10.get("effort") == "high" and "--effort" not in argv10
        record("10. ignore --effort on agy", ok10, f"rc={res10.returncode} err={res10.stderr}")

        # 10b. an --effort the lane's harness does not offer is refused with
        #      the harness's list, and no run starts (ticket 19)
        runs_before10b = set(os.listdir(world.runs_dir)) if os.path.isdir(world.runs_dir) else set()
        refusals = []
        for lane10b, eff10b, offered10b in (
            ("fable-xhigh@claude", "ultra", "claude offers low, medium, high, xhigh, max"),
            ("grok46-high@grok", "low", "grok offers high"),
            ("flash-high@agy", "xhigh", "agy offers low, medium, high"),
        ):
            res10b = run_dispatch(world, ["--lane", lane10b, "--class", "impl", "--brief", b10, "--cwd", cwd,
                                          "--effort", eff10b], orchestrator="codex")
            refusals.append((res10b.returncode == 2
                             and f"does not offer effort '{eff10b}'" in res10b.stderr
                             and offered10b in res10b.stderr, res10b.returncode, res10b.stderr))
        runs_after10b = set(os.listdir(world.runs_dir)) if os.path.isdir(world.runs_dir) else set()
        record("10b. --effort a harness does not offer is refused, naming its list",
               all(r[0] for r in refusals) and runs_after10b == runs_before10b, str(refusals))

        # -------------------------------------------------------------
        # 12. Errors before run dir: unknown lane, relative brief, ads check failure
        # -------------------------------------------------------------
        b12 = make_brief("b12.md", "Brief 12.")
        res12_lane = run_dispatch(world, ["--lane", "unknown@codex", "--class", "impl", "--brief", b12, "--cwd", cwd])
        ok12a = (res12_lane.returncode == 2 and "terra-high@codex" in res12_lane.stderr)

        res12_rel = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", "relative.md", "--cwd", cwd])
        ok12b = (res12_rel.returncode == 2)

        runs_before = set(os.listdir(world.runs_dir))
        res12_ads = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b12, "--cwd", cwd], extra_env={"ADS_FAKE_GIT_SHA": "0000000000000000000000000000000000000000"})
        runs_after = set(os.listdir(world.runs_dir))
        ok12c = (res12_ads.returncode == 2 and runs_after == runs_before)

        ok12 = ok12a and ok12b and ok12c
        record("12. pre-run errors exit 2 and no run dir", ok12, f"12a={ok12a} 12b={ok12b} 12c={ok12c} ads_err={res12_ads.stderr}")

        # -------------------------------------------------------------
        # 12d. node absent from PATH: ads.sh check refuses before the ledger
        # records a start. A node that goes missing after the check is the Ads
        # adapter's (test_relay a5): the Run still finishes, blocked, saying why.
        # -------------------------------------------------------------
        no_node_bin = os.path.join(tmpdir, "no_node_bin")
        os.makedirs(no_node_bin, exist_ok=True)
        for name in os.listdir(world.bin_dir):
            if name != "node":
                os.symlink(os.path.join(world.bin_dir, name), os.path.join(no_node_bin, name))
        no_node_env = {"PATH": no_node_bin}
        ledger_path = world.ledger_path

        def ledger_lines():
            with open(ledger_path, "r", encoding="utf-8") as f:
                return [json.loads(l) for l in f if l.strip()]

        b12d = make_brief("b12d.md", f"fake-relay: status=completed final={done_final}\nBrief 12d.")
        runs_before12d = set(os.listdir(world.runs_dir))
        ledger_before12d = len(ledger_lines())
        res12d = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b12d, "--cwd", cwd],
                              extra_env=no_node_env)
        ok12d_check = (
            res12d.returncode == 2 and "node is not on PATH" in res12d.stderr and
            set(os.listdir(world.runs_dir)) == runs_before12d and
            len(ledger_lines()) == ledger_before12d
        )
        record("12d. ads.sh check reports a missing node before the ledger records a start", ok12d_check,
               f"rc={res12d.returncode} err={res12d.stderr}")

        # 12g. Inside a Seatbelt sandbox that refuses a nested one, a codex lane
        # is blocked before its relay runs and says why; a lane on a harness
        # that does not nest Seatbelt still runs.
        world.stub("sandbox-exec", "echo 'sandbox-exec: sandbox_apply: Operation not permitted' >&2\nexit 71\n")
        try:
            ledger_before12g = len(ledger_lines())
            res12g = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "impl", "--brief", b12d, "--cwd", cwd])
            dir12g = parse_run_dir_from_stdout(res12g.stdout)
            new12g = ledger_lines()[ledger_before12g:]
            ret12g = json.load(open(os.path.join(dir12g, "return.json"))) if dir12g else {}
            ok12g = (
                res12g.returncode == 1 and dir12g is not None and
                not os.path.exists(os.path.join(dir12g, "result.json")) and
                [e.get("kind") for e in new12g] == ["dispatch.start", "dispatch.finish"] and
                new12g[1].get("status") == "blocked" and
                ret12g.get("status") == "blocked" and
                "sandbox_apply: Operation not permitted" in ret12g.get("deliverable", "") and
                "Herdr" in ret12g.get("deliverable", "")
            )
            record("12g. a codex lane inside a Seatbelt that refuses nesting is blocked before the relay", ok12g,
                   f"rc={res12g.returncode} out={res12g.stdout} err={res12g.stderr[-400:]} ret={ret12g}")

            res12h = run_dispatch(world, ["--lane", "grok46-high@grok", "--class", "impl", "--brief", b12d, "--cwd", cwd])
            record("12h. a grok lane is not probed and still runs", res12h.returncode == 0,
                   f"rc={res12h.returncode} out={res12h.stdout} err={res12h.stderr[-400:]}")
        finally:
            world.stub("sandbox-exec", "exit 0\n")

        # 12i. A dispatch terminated by SIGTERM (as `claude -p` ends a background
        # job at the end of its turn) still ends its Run, and its relay stops:
        # the fake relay waits for a hold file that only appears after dispatch
        # has exited, and must never get to write its result.
        hold12i = os.path.join(tmpdir, "never-12i")
        b12i = make_brief("b12i.md", f"fake-relay: status=completed final={done_final} hold={hold12i}\nBrief 12i.")
        ledger_before12i = len(ledger_lines())
        runs_before12i = set(os.listdir(world.runs_dir))
        proc12i = subprocess.Popen(
            [sys.executable, DELEGATE_PY, "dispatch", "--config-dir", world.config_dir,
             "--ads-dir", world.ads_dir, "--runs-dir", world.runs_dir, "--no-probe",
             "--lane", "terra-high@codex", "--class", "impl", "--brief", b12i, "--cwd", cwd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=world.env)
        started12i = False
        for _ in range(400):
            try:
                started12i = any(e.get("kind") == "dispatch.start" for e in ledger_lines()[ledger_before12i:])
            except ValueError:
                started12i = False
            if started12i or proc12i.poll() is not None:
                break
            time.sleep(0.05)
        proc12i.send_signal(signal.SIGTERM)
        out12i, err12i = proc12i.communicate(timeout=60)
        new12i = ledger_lines()[ledger_before12i:]
        dirs12i = sorted(set(os.listdir(world.runs_dir)) - runs_before12i)
        dir12i = os.path.join(world.runs_dir, dirs12i[0]) if len(dirs12i) == 1 else None
        disp12i = json.load(open(os.path.join(dir12i, "dispatch.json"))) if dir12i else {}
        open(hold12i, "w").close()
        time.sleep(1.5)
        ok12i = (
            started12i and proc12i.returncode == 1 and dir12i is not None and
            parse_run_dir_from_stdout(out12i) == dir12i and
            disp12i.get("status") == "blocked" and disp12i.get("reason") == "dispatch terminated (SIGTERM)" and
            [e.get("kind") for e in new12i] == ["dispatch.start", "dispatch.finish"] and
            new12i[1].get("status") == "blocked" and
            not os.path.exists(os.path.join(dir12i, "result.json"))
        )
        record("12i. a dispatch terminated by SIGTERM still ends its Run and stops its relay", ok12i,
               f"started={started12i} rc={proc12i.returncode} out={out12i!r} err={err12i[-400:]!r} "
               f"dispatch={disp12i} ledger={new12i} "
               f"result={dir12i and os.path.exists(os.path.join(dir12i, 'result.json'))}")


        # -------------------------------------------------------------
        # 14. --model gpt-5.6-terra dispatches terra-high@codex
        # -------------------------------------------------------------
        b14 = make_brief("b14.md", f"fake-relay: status=completed final={done_final}\nBrief 14.")
        res14 = run_dispatch(world, ["--model", "gpt-5.6-terra", "--class", "impl", "--brief", b14, "--cwd", cwd])
        dir14 = parse_run_dir_from_stdout(res14.stdout)
        ok14 = (res14.returncode == 0 and dir14 is not None)
        if ok14:
            argv14 = json.load(open(os.path.join(dir14, "argv.json")))
            disp14 = json.load(open(os.path.join(dir14, "dispatch.json")))
            ok14 = (
                "--model" in argv14 and argv14[argv14.index("--model") + 1] == "gpt-5.6-terra" and
                disp14.get("lane") == "terra-high@codex"
            )
        record("14. --model gpt-5.6-terra -> terra-high@codex", ok14, f"rc={res14.returncode} stdout={res14.stdout} stderr={res14.stderr}")

        # -------------------------------------------------------------
        # 15. unknown --model lists lanes (with and without --harness)
        # -------------------------------------------------------------
        b15 = make_brief("b15.md", "Brief 15.")
        res15a = run_dispatch(world, ["--model", "nope", "--harness", "grok", "--class", "impl", "--brief", b15, "--cwd", cwd])
        ok15a = (
            res15a.returncode == 2 and
            "no lane runs model 'nope' on grok" in res15a.stderr and
            "grok46-high@grok (grok-4.6)" in res15a.stderr
        )
        res15b = run_dispatch(world, ["--model", "nope", "--class", "impl", "--brief", b15, "--cwd", cwd])
        expected_lanes = [
            "fable-xhigh@claude (claude-fable-5-1)",
            "sol-high@codex (gpt-5.6-sol)",
            "terra-high@codex (gpt-5.6-terra)",
            "grok46-high@grok (grok-4.6)",
            "luna-low@codex (gpt-5.6-luna)",
            "flash-high@agy (gemini-3.8-flash-high)",
        ]
        ok15b = (
            res15b.returncode == 2 and
            "no lane runs model 'nope'" in res15b.stderr and
            all(item in res15b.stderr for item in expected_lanes)
        )
        record("15. unknown --model lists lanes", ok15a and ok15b, f"15a={ok15a} err_a={res15a.stderr} 15b={ok15b} err_b={res15b.stderr}")

        # -------------------------------------------------------------
        # 16. --lane grok46-high@grok --harness codex mismatch
        # -------------------------------------------------------------
        b16 = make_brief("b16.md", "Brief 16.")
        res16 = run_dispatch(world, ["--lane", "grok46-high@grok", "--harness", "codex", "--class", "impl", "--brief", b16, "--cwd", cwd])
        ok16 = (
            res16.returncode == 2 and
            res16.stderr.strip() == "delegate: lane 'grok46-high@grok' runs on grok, not codex"
        )
        record("16. --lane/--harness mismatch", ok16, f"rc={res16.returncode} err={res16.stderr}")

        # -------------------------------------------------------------
        # 17. grok stub removed: PATH error, no run directory
        # -------------------------------------------------------------
        b17 = make_brief("b17.md", "Brief 17.")
        os.remove(os.path.join(world.bin_dir, "grok"))
        runs_before17 = set(os.listdir(world.runs_dir))
        res17 = run_dispatch(world, ["--lane", "grok46-high@grok", "--class", "impl", "--brief", b17, "--cwd", cwd])
        runs_after17 = set(os.listdir(world.runs_dir))
        ok17 = (
            res17.returncode == 2 and
            "grok CLI is not on PATH; install it or pick a lane on another harness" in res17.stderr and
            runs_after17 == runs_before17
        )
        world.stub("grok", "exit 0\n")
        record("17. missing grok CLI, no run dir", ok17, f"rc={res17.returncode} err={res17.stderr}")

        # -------------------------------------------------------------
        # 18. neither --lane nor --model, and both
        # -------------------------------------------------------------
        b18 = make_brief("b18.md", "Brief 18.")
        res18a = run_dispatch(world, ["--class", "impl", "--brief", b18, "--cwd", cwd])
        res18b = run_dispatch(world, ["--lane", "terra-high@codex", "--model", "gpt-5.6-terra", "--class", "impl", "--brief", b18, "--cwd", cwd])
        ok18 = (res18a.returncode == 2 and res18b.returncode == 2)
        record("18. lane/model required exclusive", ok18, f"rc_a={res18a.returncode} err_a={res18a.stderr} rc_b={res18b.returncode} err_b={res18b.stderr}")

        # -------------------------------------------------------------
        # 19-22. run ranking + dispatch
        # -------------------------------------------------------------
        healthy_meters = write_meters_doc(os.path.join(tmpdir, "healthy_meters.json"), [
            meter("codex", weekly=0.55, five_h=0.55, pace=0.75, status="ok"),
            meter("grok", weekly=1.00, pace=0.90, status="ok"),
            meter("claude-fable", weekly=0.70, five_h=0.70, pace=0.85, status="ok"),
            meter("claude-general", weekly=0.70, five_h=0.70, pace=0.70, status="ok"),
            meter("agy-gemini", weekly=0.61, five_h=0.61, pace=3.27, status="ok"),
        ])
        b19 = make_brief("b19.md", f"fake-relay: status=completed final={done_final}\nBrief 19.")
        runs_before19 = set(os.listdir(world.runs_dir))
        res19 = run_run(world, ["mechanical", "--brief", b19, "--cwd", cwd, "--meters", healthy_meters, "--dry-run"])
        runs_after19 = set(os.listdir(world.runs_dir))
        lines19 = res19.stdout.strip().splitlines()
        ok19 = (
            res19.returncode == 0 and
            any("flash-high@agy" in line and line.endswith("pick") for line in lines19) and
            "delegate: dry run, nothing dispatched" in res19.stdout and
            runs_after19 == runs_before19
        )
        record("19. run mechanical --dry-run", ok19, f"rc={res19.returncode} stdout={res19.stdout} stderr={res19.stderr}")

        b20 = make_brief("b20.md", f"fake-relay: status=completed final={done_final}\nBrief 20.")
        res20 = run_run(world, ["mechanical", "--brief", b20, "--cwd", cwd, "--meters", healthy_meters])
        dir20 = parse_run_dir_from_stdout(res20.stdout)
        ok20 = (
            res20.returncode == 0 and
            "flash-high@agy" in res20.stdout and
            "delegate: dispatching flash-high@agy" in res20.stdout and
            "delegate:" in res20.stdout and
            "delegate-metrics:" in res20.stdout and
            dir20 is not None and os.path.isdir(dir20)
        )
        if ok20:
            disp20 = json.load(open(os.path.join(dir20, "dispatch.json")))
            ok20 = disp20.get("lane") == "flash-high@agy"
        record("20. run mechanical dispatches flash-high@agy", ok20, f"rc={res20.returncode} stdout={res20.stdout} stderr={res20.stderr}")

        # 20j. run --json: stdout is one object, the ranking and the
        # dispatching line go to stderr, and the object carries the return
        b20j = make_brief("b20j.md", f"fake-relay: status=completed final={done_final}\nBrief 20j.")
        res20j = run_run(world, ["mechanical", "--brief", b20j, "--cwd", cwd, "--meters", healthy_meters, "--json"])
        try:
            doc20j = json.loads(res20j.stdout)
        except ValueError:
            doc20j = None
        ok20j = (
            res20j.returncode == 0 and isinstance(doc20j, dict) and
            doc20j.get("lane") == "flash-high@agy" and doc20j.get("status") == "done" and
            doc20j.get("class") == "mechanical" and doc20j.get("thread") and
            doc20j.get("return") == json.load(open(os.path.join(doc20j["run"], "return.json"))) and
            "delegate: dispatching flash-high@agy" in res20j.stderr and "flash-high@agy" in res20j.stderr
        )
        res20d = run_run(world, ["mechanical", "--brief", b20j, "--cwd", cwd, "--meters", healthy_meters,
                                 "--json", "--dry-run"])
        ok20j = ok20j and res20d.returncode == 0 and json.loads(res20d.stdout) == {
            "class": "mechanical", "pick": "flash-high@agy", "dry_run": True}
        record("20j. run --json prints one object and sends the ranking to stderr", ok20j,
               f"rc={res20j.returncode} stdout={res20j.stdout} stderr={res20j.stderr} dry={res20d.stdout}")

        b21 = make_brief("b21.md", f"fake-relay: status=completed final={done_final}\nBrief 21.")
        res21 = run_run(world, ["impl", "--brief", b21, "--cwd", cwd, "--meters", healthy_meters, "--tier", "3"])
        dir21 = parse_run_dir_from_stdout(res21.stdout)
        sol_line = next((ln for ln in res21.stdout.splitlines() if "sol-high@codex" in ln), "")
        ok21_pick = (
            res21.returncode == 0 and
            "pick" in sol_line and
            dir21 is not None
        )
        if ok21_pick:
            disp21 = json.load(open(os.path.join(dir21, "dispatch.json")))
            ok21_pick = disp21.get("lane") == "sol-high@codex"

        res21_bad = run_run(world, ["impl", "--brief", b21, "--cwd", cwd, "--meters", healthy_meters, "--tier", "1"])
        ok21_bad = (
            res21_bad.returncode == 2 and
            "outside [2, 3] for class 'impl'" in res21_bad.stderr
        )
        ok21 = ok21_pick and ok21_bad
        record("21. run impl --tier 3 raises floor and bad tier exits 2", ok21, f"rc={res21.returncode} sol={sol_line} bad_err={res21_bad.stderr}")

        gated_meters = write_meters_doc(os.path.join(tmpdir, "gated_meters.json"), [
            meter("codex", weekly=0.05, five_h=0.05, pace=0.75, status="unavailable"),
            meter("grok", weekly=1.00, pace=0.90, status="ok"),
            meter("claude-fable", weekly=0.70, five_h=0.70, pace=0.85, status="ok"),
            meter("agy-gemini", weekly=0.61, five_h=0.61, pace=3.27, status="ok"),
        ])
        b22 = make_brief("b22.md", "Brief 22.")
        runs_before22 = set(os.listdir(world.runs_dir))
        res22 = run_run(world, ["hard-impl", "--brief", b22, "--cwd", cwd, "--meters", gated_meters, "--harnesses", "codex,agy,grok"])
        runs_after22 = set(os.listdir(world.runs_dir))
        ok22 = (
            res22.returncode == 1 and
            "STOP: no lane eligible for hard-impl" in res22.stdout and
            runs_after22 == runs_before22
        )
        record("22. run hard-impl STOP no pick", ok22, f"rc={res22.returncode} stdout={res22.stdout} stderr={res22.stderr}")

        # -------------------------------------------------------------
        # 23. run foo -> exit 2 listing classes
        # -------------------------------------------------------------
        b23 = make_brief("b23.md", "Brief 23.")
        res23 = run_run(world, ["foo", "--brief", b23, "--cwd", cwd])
        ok23 = (
            res23.returncode == 2 and
            all(c in res23.stderr for c in ("scout", "mechanical", "impl", "review", "hard-impl"))
        )
        record("23. run foo lists classes", ok23, f"rc={res23.returncode} err={res23.stderr}")

        # -------------------------------------------------------------
        # 24. --effort low on flash-high@agy proceeds; argv has no --effort
        # -------------------------------------------------------------
        b24 = make_brief("b24.md", f"fake-relay: status=completed final={done_final}\nBrief 24.")
        res24 = run_dispatch(world, ["--lane", "flash-high@agy", "--class", "impl", "--brief", b24, "--cwd", cwd, "--effort", "low"])
        dir24 = parse_run_dir_from_stdout(res24.stdout)
        ok24 = (
            res24.returncode == 0 and
            "delegate: effort override ignored on flash-high@agy; agy carries effort in the model name" in res24.stderr and
            dir24 is not None
        )
        if ok24:
            argv24 = json.load(open(os.path.join(dir24, "argv.json")))
            ok24 = "--effort" not in argv24
        record("24. agy --effort ignored, no argv --effort", ok24, f"rc={res24.returncode} err={res24.stderr}")

        # -------------------------------------------------------------
        # 25. hard-impl prompt contains no tool-call sentence; dispatch.json leash: false
        # -------------------------------------------------------------
        leash_sentence = "Stop exploring after 40 tool calls and write the answer."
        b25 = make_brief("b25.md", f"fake-relay: status=completed final={done_final}\nBrief 25.")
        res25 = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "hard-impl", "--brief", b25, "--cwd", cwd])
        dir25 = parse_run_dir_from_stdout(res25.stdout)
        ok25 = (res25.returncode == 0 and dir25 is not None)
        if ok25:
            prompt25 = open(os.path.join(dir25, "prompt.md"), "r", encoding="utf-8").read()
            disp25 = json.load(open(os.path.join(dir25, "dispatch.json")))
            ok25 = (
                leash_sentence not in prompt25 and
                disp25.get("leash") is False
            )
        record("25. hard-impl prompt has no leash, dispatch.json leash=False", ok25, f"rc={res25.returncode}")

        # -------------------------------------------------------------
        # 26. scout prompt contains tool-call sentence; dispatch.json leash: true
        # -------------------------------------------------------------
        b26 = make_brief("b26.md", f"fake-relay: status=completed final={done_final}\nBrief 26.")
        res26 = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "scout", "--brief", b26, "--cwd", cwd])
        dir26 = parse_run_dir_from_stdout(res26.stdout)
        ok26 = (res26.returncode == 0 and dir26 is not None)
        if ok26:
            prompt26 = open(os.path.join(dir26, "prompt.md"), "r", encoding="utf-8").read()
            disp26 = json.load(open(os.path.join(dir26, "dispatch.json")))
            ok26 = (
                leash_sentence in prompt26 and
                disp26.get("leash") is True
            )
        record("26. scout prompt has leash, dispatch.json leash=True", ok26, f"rc={res26.returncode}")

        # -------------------------------------------------------------
        # 27. --no-leash dispatch of a leashed class lacks leash; dispatch.json leash: false
        # -------------------------------------------------------------
        b27 = make_brief("b27.md", f"fake-relay: status=completed final={done_final}\nBrief 27.")
        res27 = run_dispatch(world, ["--lane", "terra-high@codex", "--class", "scout", "--brief", b27, "--cwd", cwd, "--no-leash"])
        dir27 = parse_run_dir_from_stdout(res27.stdout)
        ok27 = (res27.returncode == 0 and dir27 is not None)
        if ok27:
            prompt27 = open(os.path.join(dir27, "prompt.md"), "r", encoding="utf-8").read()
            disp27 = json.load(open(os.path.join(dir27, "dispatch.json")))
            ok27 = (
                leash_sentence not in prompt27 and
                disp27.get("leash") is False
            )
        record("27. --no-leash scout prompt lacks leash, dispatch.json leash=False", ok27, f"rc={res27.returncode}")

        # -------------------------------------------------------------
        # 27a. the leash is the Class's routing field: a catalog that sets
        #      scout's leash false drops it, and one written before the key
        #      existed (impl with no `leash`) keeps the shipped impl's false.
        # -------------------------------------------------------------
        leash_config = os.path.join(tmpdir, "config-leash")
        shutil.copytree(world.config_dir, leash_config)
        leash_routing_path = os.path.join(leash_config, "routing.json")
        leash_routing = json.load(open(leash_routing_path))
        leash_routing["classes"]["scout"]["leash"] = False
        leash_routing["classes"]["impl"].pop("leash", None)
        with open(leash_routing_path, "w") as f:
            json.dump(leash_routing, f)
        seen27a = {}
        for cls in ("scout", "impl", "review"):
            b27a = make_brief(f"b27a-{cls}.md", f"fake-relay: status=completed final={done_final}\nBrief 27a.")
            res27a = run_dispatch(world, ["--lane", "terra-high@codex", "--class", cls, "--brief", b27a, "--cwd", cwd],
                                  config_dir=leash_config)
            dir27a = parse_run_dir_from_stdout(res27a.stdout)
            if res27a.returncode != 0 or dir27a is None:
                seen27a[cls] = f"rc={res27a.returncode} err={res27a.stderr[-300:]}"
                continue
            prompt27a = open(os.path.join(dir27a, "prompt.md"), "r", encoding="utf-8").read()
            disp27a = json.load(open(os.path.join(dir27a, "dispatch.json")))
            seen27a[cls] = (leash_sentence in prompt27a, disp27a.get("leash"))
        record("27a. routing classes.<name>.leash decides the leash; a missing key keeps the shipped one",
               seen27a == {"scout": (False, False), "impl": (False, False), "review": (True, True)},
               repr(seen27a))

        # -------------------------------------------------------------
        # 27b. run --harness: the user's constraint runs that harness's Pick, and
        #      a harness that is not installed starts nothing (any-harness 12).
        # -------------------------------------------------------------
        b27b = make_brief("b27b.md", f"fake-relay: status=completed final={done_final}\nBrief 27b.")
        meters27b = os.path.join(HERE, "fixture", "meters.json")
        res27b = run_run(world, ["impl", "--brief", b27b, "--cwd", cwd, "--meters", meters27b,
                                 "--harness", "grok"])
        dir27b = parse_run_dir_from_stdout(res27b.stdout)
        lane27b = json.load(open(os.path.join(dir27b, "dispatch.json")))["lane"] if dir27b else None
        record("27b. run --harness grok runs a grok Lane", res27b.returncode == 0 and lane27b == "grok46-high@grok",
               f"rc={res27b.returncode} lane={lane27b} out={res27b.stdout[-300:]} err={res27b.stderr[-300:]}")
        runs_before27c = set(os.listdir(world.runs_dir))
        res27c = run_run(world, ["impl", "--brief", b27b, "--cwd", cwd, "--meters", meters27b,
                                 "--harnesses", "codex,agy", "--harness", "grok"])
        record("27c. run --harness refuses a harness that is not installed and starts nothing",
               res27c.returncode == 2 and "harness 'grok' is not installed" in res27c.stderr
               and set(os.listdir(world.runs_dir)) == runs_before27c,
               f"rc={res27c.returncode} err={res27c.stderr}")

        # -------------------------------------------------------------
        # Cases 29-31 need a claude lane inside the impl range. The sample keeps
        # only fable-xhigh@claude (tier 4), so add opus-high@claude to this copy.
        import json as _json
        _lanes_path = os.path.join(world.config_dir, "lanes.json")
        with open(_lanes_path, encoding="utf-8") as _f:
            _lanes_doc = _json.load(_f)
        _opus = {k: v for k, v in _lanes_doc["lanes"]["fable-xhigh@claude"].items()
                 if k not in ("published_as", "note")}
        _opus.update(model="claude-opus-5", effort="high", meter="claude-general",
                     tier=3, basis="test fixture: native claude lane")
        _lanes_doc["lanes"]["opus-high@claude"] = _opus
        with open(_lanes_path, "w", encoding="utf-8") as _f:
            _json.dump(_lanes_doc, _f, indent=2)

        # -------------------------------------------------------------
        # 29. dispatch native lane prints native line, writes prompt.md, no relay
        b29 = make_brief("b29.md", "Brief 29.")
        runs_before29 = set(os.listdir(world.runs_dir))
        res29 = run_dispatch(world, ["--lane", "opus-high@claude", "--class", "impl", "--brief", b29, "--cwd", cwd])
        runs_after29 = set(os.listdir(world.runs_dir))
        new_runs29 = list(runs_after29 - runs_before29)
        lines29 = res29.stdout.strip().splitlines()
        # the native line, then the profile's one-line spawn instruction
        ok29 = (
            res29.returncode == 0 and
            len(new_runs29) == 1 and len(lines29) == 2 and
            lines29[0].startswith("delegate: native lane=opus-high@claude agent=lane-opus-high prompt=") and
            lines29[1].startswith("delegate: spawn: spawn lane-opus-high with the Agent tool") and
            lines29[0].split("prompt=")[-1] in lines29[1]
        )
        disp29 = {}
        if ok29:
            dir29 = os.path.join(world.runs_dir, new_runs29[0])
            prompt_in_stdout = lines29[0].split("prompt=")[-1]
            expected_prompt = os.path.abspath(os.path.join(dir29, "prompt.md"))
            disp29 = json.load(open(os.path.join(dir29, "dispatch.json")))
            ok29 = (
                prompt_in_stdout == expected_prompt and
                os.path.isfile(expected_prompt) and
                not os.path.exists(os.path.join(dir29, "argv.json")) and
                not os.path.exists(os.path.join(dir29, "relay.stdout")) and
                # the Run ends at once, handed to its agent: an Outcome and no return
                disp29.get("status") == "native" and bool(disp29.get("finished_at")) and
                disp29.get("reason") == "handed to lane-opus-high" and disp29.get("secs") is None and
                not os.path.exists(os.path.join(dir29, "return.json"))
            )
        record("29. dispatch native lane prints native line, writes prompt.md, no relay", ok29,
               f"rc={res29.returncode} stdout={res29.stdout} dispatch={disp29}")

        # -------------------------------------------------------------
        # 29a. --effort on a native lane: a matching one passes quietly; a
        # differing one warns like agy, and dispatch.json records the effort
        # the agent file runs at. Relayed (orchestrator codex), it still applies.
        def native_effort(effort, orchestrator=None):
            before = set(os.listdir(world.runs_dir))
            res = run_dispatch(world, ["--lane", "opus-high@claude", "--class", "impl", "--brief", b29,
                                       "--cwd", cwd, "--effort", effort], orchestrator=orchestrator)
            new = list(set(os.listdir(world.runs_dir)) - before)
            disp = {}
            if len(new) == 1:
                disp = json.load(open(os.path.join(world.runs_dir, new[0], "dispatch.json")))
            return res, disp

        res29a_same, disp29a_same = native_effort("high")
        res29a_diff, disp29a_diff = native_effort("low")
        res29a_relay, disp29a_relay = native_effort("low", orchestrator="codex")
        native_warn = "delegate: effort override ignored on opus-high@claude; a native lane runs at its agent file's effort, high"
        ok29a = (
            res29a_same.returncode == 0 and "override ignored" not in res29a_same.stderr and
            disp29a_same.get("effort") == "high" and
            res29a_diff.returncode == 0 and native_warn in res29a_diff.stderr and
            disp29a_diff.get("effort") == "high" and
            res29a_diff.stdout.strip().startswith("delegate: native lane=opus-high@claude agent=lane-opus-high ") and
            "override ignored" not in res29a_relay.stderr and disp29a_relay.get("effort") == "low"
        )
        record("29a. --effort on a native lane: matching passes, differing warns and records the lane's effort", ok29a,
               f"same={res29a_same.stderr!r} {disp29a_same.get('effort')} diff={res29a_diff.stderr!r} "
               f"{disp29a_diff.get('effort')} relay={res29a_relay.stderr!r} {disp29a_relay.get('effort')}")

        # 29c. a native lane needs neither node nor ADS: it prints its agent line.
        res29c = run_dispatch(world, ["--lane", "opus-high@claude", "--class", "impl", "--brief", b29, "--cwd", cwd],
                              extra_env={'PATH': no_node_bin, 'ADS_FAKE_GIT_SHA': '0' * 40})
        ok29c = (res29c.returncode == 0 and
                 res29c.stdout.strip().startswith("delegate: native lane=opus-high@claude agent=lane-opus-high "))
        record("29c. a native lane runs with node absent and ADS out of date", ok29c,
               f"rc={res29c.returncode} out={res29c.stdout} err={res29c.stderr}")

        # -------------------------------------------------------------
        # 29b. the courier's command, read from courier.md: dispatch --json
        # writes one object to <brief>.json and everything else, the agy
        # override warning (24) included, to <brief>.log; the native line (29)
        # is an object of its own, never a result.
        courier_md = open(COURIER_MD).read()
        step1 = re.search(r"\{ delegate dispatch [^\n]*\} &", courier_md)
        poll_re = (re.findall(r"until `grep -q '([^']+)'", courier_md) + [None])[0]
        courier_shape = ("{ \"$0\" \"$@\" > \"$JSON\" 2> \"$LOG\"; "
                         "echo \"courier-exit: $?\" >> \"$LOG\"; }")

        def courier_argv(args):
            return ["sh", "-c", courier_shape, sys.executable, DELEGATE_PY, "dispatch",
                    "--config-dir", world.config_dir, "--ads-dir", world.ads_dir,
                    "--runs-dir", world.runs_dir, "--no-probe"] + args + ["--json"]

        def courier_run(name, args):
            files = {"JSON": os.path.join(tmpdir, f"{name}.md.json"),
                     "LOG": os.path.join(tmpdir, f"{name}.md.log")}
            subprocess.run(courier_argv(args), env=dict(world.env, **files), cwd=cwd)
            with open(files["LOG"]) as f:
                log = f.read()
            try:
                with open(files["JSON"]) as f:
                    doc = json.load(f)
            except ValueError:
                doc = None
            return doc, log

        b29b = make_brief("b29b.md", f"fake-relay: status=completed final={done_final}\nBrief 29b.")
        doc_agy, log_agy = courier_run("b29b-agy", ["--lane", "flash-high@agy", "--class", "impl", "--brief", b29b,
                                                    "--cwd", cwd, "--effort", "low"])
        doc_native, log_native = courier_run("b29b-native", ["--lane", "opus-high@claude", "--class", "impl",
                                                             "--brief", b29b, "--cwd", cwd])
        agy_return = (json.load(open(os.path.join(doc_agy["run"], "return.json")))
                      if isinstance(doc_agy, dict) and doc_agy.get("run") else None)
        ok29b = (
            step1 is not None and "--json > <brief-path>.json 2> <brief-path>.log" in step1.group(0) and
            "courier-exit: 0" in log_agy and "courier-exit: 0" in log_native and
            # the warning is in the log, and the result is the JSON alone
            log_agy.startswith("delegate: effort override ignored") and
            isinstance(doc_agy, dict) and doc_agy.get("lane") == "flash-high@agy" and
            doc_agy.get("status") == "done" and doc_agy.get("return") == agy_return and
            not doc_agy.get("native") and
            # the native object is never taken for a result
            isinstance(doc_native, dict) and doc_native.get("native") is True and
            doc_native.get("agent") == "lane-opus-high" and "return" not in doc_native
        )
        record("29b. courier reads dispatch's JSON, not the override warning or the native line", ok29b,
               f"step1={step1 and step1.group(0)} agy={doc_agy!r} {log_agy!r} native={doc_native!r}")

        # 29d. the courier's poll condition, read from courier.md: while the
        # relay runs, the log already holds a delegate: line (the override
        # warning) but the poll must keep waiting; once dispatch exits, it stops.
        hold29d = os.path.join(tmpdir, "release-29d")
        files29d = {"JSON": os.path.join(tmpdir, "b29d.md.json"), "LOG": os.path.join(tmpdir, "b29d.md.log")}
        b29d = make_brief("b29d.md", f"fake-relay: status=completed final={done_final} hold={hold29d}\nBrief 29d.")

        def poll_done():
            return (os.path.isfile(files29d["LOG"]) and
                    subprocess.run(["grep", "-q", poll_re, files29d["LOG"]]).returncode == 0)

        proc29d = subprocess.Popen(
            courier_argv(["--lane", "flash-high@agy", "--class", "impl", "--brief", b29d, "--cwd", cwd,
                          "--effort", "low"]),
            env=dict(world.env, **files29d), cwd=cwd)
        mid_log = ""
        for _ in range(200):
            mid_log = open(files29d["LOG"]).read() if os.path.isfile(files29d["LOG"]) else ""
            if "delegate: effort override ignored" in mid_log:
                break
            time.sleep(0.05)
        waiting_mid_run = poll_re is not None and proc29d.poll() is None and not poll_done()
        open(hold29d, "w").close()
        proc29d.wait(timeout=60)
        with open(files29d["JSON"]) as f:
            end_doc = json.load(f)
        ok29d = (
            waiting_mid_run and mid_log.startswith("delegate: effort override ignored") and
            poll_done() and end_doc.get("status") == "done"
        )
        record("29d. the courier keeps polling past an early delegate: line until dispatch exits", ok29d,
               f"poll_re={poll_re!r} mid={mid_log!r} end={end_doc!r}")

        # -------------------------------------------------------------
        # 30. run native lane prints rank and native line, no relay
        native_meters = write_meters_doc(os.path.join(tmpdir, "native_meters.json"), [
            meter("codex", weekly=0.55, five_h=0.55, pace=0.75, status="ok"),
            meter("grok", weekly=1.00, pace=0.90, status="ok"),
            meter("claude-fable", weekly=0.70, five_h=0.70, pace=0.85, status="ok"),
            meter("claude-general", weekly=0.70, five_h=0.70, pace=1.50, status="ok"),
            meter("agy-gemini", weekly=0.61, five_h=0.61, pace=3.27, status="ok"),
        ])
        b30 = make_brief("b30.md", "Brief 30.")
        runs_before30 = set(os.listdir(world.runs_dir))
        res30 = run_run(world, ["impl", "--brief", b30, "--cwd", cwd, "--meters", native_meters, "--tier", "3"])
        runs_after30 = set(os.listdir(world.runs_dir))
        new_runs30 = list(runs_after30 - runs_before30)
        lines30 = [ln for ln in res30.stdout.strip().splitlines() if ln.strip()]
        last_line30 = next((ln for ln in lines30 if ln.startswith("delegate: native")), "")
        ok30 = (
            res30.returncode == 0 and
            len(new_runs30) == 1 and
            "delegate: dispatching" not in res30.stdout and
            last_line30.startswith("delegate: native lane=opus-high@claude agent=lane-opus-high prompt=")
        )
        if ok30:
            dir30 = os.path.join(world.runs_dir, new_runs30[0])
            prompt_in_stdout30 = last_line30.split("prompt=")[-1]
            expected_prompt30 = os.path.abspath(os.path.join(dir30, "prompt.md"))
            ok30 = (
                prompt_in_stdout30 == expected_prompt30 and
                os.path.isfile(expected_prompt30) and
                not os.path.exists(os.path.join(dir30, "argv.json")) and
                not os.path.exists(os.path.join(dir30, "relay.stdout"))
            )
        record("30. run native lane prints native line, writes prompt.md, no relay", ok30, f"rc={res30.returncode} stdout={res30.stdout}")

        # -------------------------------------------------------------
        # 31. ORCHESTRATOR=codex sends claude lane through fake relay
        b31 = make_brief("b31.md", f"fake-relay: status=completed final={done_final}\nBrief 31.")
        runs_before31 = set(os.listdir(world.runs_dir))
        res31 = run_dispatch(world, ["--lane", "opus-high@claude", "--class", "impl", "--brief", b31, "--cwd", cwd], orchestrator="codex")
        runs_after31 = set(os.listdir(world.runs_dir))
        new_runs31 = list(runs_after31 - runs_before31)
        ok31 = (
            res31.returncode == 0 and
            len(new_runs31) == 1 and
            "delegate:" in res31.stdout and
            "delegate-metrics:" in res31.stdout and
            "delegate: native" not in res31.stdout
        )
        if ok31:
            dir31 = os.path.join(world.runs_dir, new_runs31[0])
            ok31 = os.path.exists(os.path.join(dir31, "argv.json")) and os.path.exists(os.path.join(dir31, "relay.stdout"))
        record("31. ORCHESTRATOR=codex sends claude lane through fake relay", ok31, f"rc={res31.returncode} stdout={res31.stdout}")

        # 31b-31e. the orchestrator is never assumed: none, an unknown name or
        # nothing detected relays a claude Lane; CLAUDECODE alone detects Claude Code
        def relayed(res):
            return (res.returncode == 0 and "delegate-metrics:" in res.stdout
                    and "delegate: native" not in res.stdout)
        no_orch_env = {"DELEGATE_ORCHESTRATOR": ""}
        for tag, orch, extra in (("31b. --orchestrator none", "none", None),
                                 ("31c. an unknown orchestrator", "kiro", None),
                                 ("31d. nothing detected", None, no_orch_env)):
            b = make_brief(f"b{tag[:3]}.md", f"fake-relay: status=completed final={done_final}\nBrief {tag}.")
            res = run_dispatch(world, ["--lane", "opus-high@claude", "--class", "impl", "--brief", b, "--cwd", cwd],
                               extra_env=extra, orchestrator=orch)
            record(f"{tag} relays a claude lane", relayed(res), f"rc={res.returncode} stdout={res.stdout} stderr={res.stderr}")
        b31e = make_brief("b31e.md", "Brief 31e.")
        res31e = run_dispatch(world, ["--lane", "opus-high@claude", "--class", "impl", "--brief", b31e, "--cwd", cwd],
                              extra_env={"DELEGATE_ORCHESTRATOR": "", "CLAUDECODE": "1"})
        record("31e. CLAUDECODE alone runs a claude lane natively",
               res31e.returncode == 0 and res31e.stdout.startswith("delegate: native lane=opus-high@claude"),
               f"rc={res31e.returncode} stdout={res31e.stdout} stderr={res31e.stderr}")

        # 31f. a Kiro Lane dispatches through kiro-delegate with the model and
        # effort (any-harness ticket 15); offline, through the fake relay
        kiro_config = os.path.join(tmpdir, "config-kiro")
        shutil.copytree(world.config_dir, kiro_config)
        lanes_kiro = json.load(open(os.path.join(kiro_config, "lanes.json")))
        lanes_kiro["meters"]["kiro"] = {"harness": "kiro", "plan": "Kiro Pro", "price_month": 20,
                                       "probe": "usage.py"}
        lanes_kiro["lanes"]["opus55-high@kiro"] = {
            "harness": "kiro", "model": "claude-opus-5.5", "effort": "high", "meter": "kiro",
            "meter_weight": 1, "timeout": "30m",
            "price": {"in": None, "cache_read": None, "cache_write": None, "out": None},
            "tier": 3, "basis": "test"}
        with open(os.path.join(kiro_config, "lanes.json"), "w") as f:
            json.dump(lanes_kiro, f)
        b31f = make_brief("b31f.md", f"fake-relay: status=completed final={done_final}\nBrief 31f.")
        res31f = run_dispatch(world, ["--lane", "opus55-high@kiro", "--class", "impl", "--brief", b31f,
                                      "--cwd", cwd], config_dir=kiro_config)
        dir31f = parse_run_dir_from_stdout(res31f.stdout)
        argv31f = json.load(open(os.path.join(dir31f, "argv.json"))) if dir31f else []
        record("31f. a kiro lane dispatches through its relay with model, effort and --read-only",
               res31f.returncode == 0 and "status=done" in res31f.stdout
               and all(x in argv31f for x in ["--model", "claude-opus-5.5", "--effort", "high",
                                               "--timeout", "30m", "--read-only"]),
               f"rc={res31f.returncode} stdout={res31f.stdout} stderr={res31f.stderr} argv={argv31f}")

        # -------------------------------------------------------------
        # 32. prompt.md preamble permits disposable browser and forbids other network writes
        # -------------------------------------------------------------
        prompt_path24 = os.path.join(dir24, "prompt.md")
        with open(prompt_path24, "r", encoding="utf-8") as f:
            prompt24_text = f.read()
        ok32 = (
            "you may read and write in a disposable browser only" in prompt24_text and
            "every other network write stays forbidden" in prompt24_text and
            "no commits, no pushes, no messages" in prompt24_text and
            # browser ticket 06: the agent profile only where the brief lists it
            "only on the sites and for the actions the brief lists under `# Agent profile`" in prompt24_text and
            "not at all when it lists none" in prompt24_text
        )
        record("32. prompt preamble permits disposable browser and forbids other network writes", ok32)

        # -------------------------------------------------------------
        # 33. agy read-only prompt has new line and no 'file tools only'; --write prompt omits it
        # -------------------------------------------------------------
        prompt_path9e = os.path.join(dir9e, "prompt.md")
        with open(prompt_path9e, "r", encoding="utf-8") as f:
            prompt9e_text = f.read()
        new_agy_line = "Browser tools are permitted. Terminal commands run inside a sandbox confined to the workspace; you still must not create, edit, or delete files."
        ok33 = (
            new_agy_line in prompt24_text and
            "file tools only" not in prompt24_text and
            "auto-denied" not in prompt24_text and
            new_agy_line not in prompt9e_text and
            "file tools only" not in prompt9e_text and
            "Writes are authorized inside" in prompt9e_text
        )
        record("33. agy prompt: read-only has new sandbox line and no 'file tools only', --write omits it", ok33)

        # 34. routing.meters off skips automatic probes on named and ranked paths.
        import usage
        routing_path = os.path.join(world.config_dir, "routing.json")
        routing_doc = json.load(open(routing_path))
        routing_doc["meters"] = False
        with open(routing_path, "w", encoding="utf-8") as f:
            json.dump(routing_doc, f, indent=2)
            f.write("\n")
        acquire_calls = []
        orig_acquire = usage.acquire
        def mark_acquire(*a, **k):
            acquire_calls.append((a, k))
            return {}
        usage.acquire = mark_acquire
        prev_cache = os.environ.get("DELEGATE_CACHE")
        os.environ["DELEGATE_CACHE"] = world.cache_path
        try:
            from catalog import load_catalog, meters_enabled
            cat_off = load_catalog(cwd=cwd, config_dir=world.config_dir)
            delegate.probe_meters(False, cat_off["routing"])
            first = list(acquire_calls)
            meters_doc = delegate.rank.load_usage(cat_off, refresh=True)
            delegate.probe_meters(False, cat_off["routing"])
            ok34 = (
                meters_enabled(cat_off["routing"]) is False
                and acquire_calls == []
                and first == []
                and not os.path.exists(world.cache_path)
            )
        finally:
            usage.acquire = orig_acquire
            if prev_cache is None:
                os.environ.pop("DELEGATE_CACHE", None)
            else:
                os.environ["DELEGATE_CACHE"] = prev_cache
        record(
            "34. meters off skips start/finish probes through dispatch and rank callers",
            ok34,
            repr(acquire_calls),
        )

        routing_doc["meters"] = True
        with open(routing_path, "w", encoding="utf-8") as f:
            json.dump(routing_doc, f, indent=2)
            f.write("\n")
        acquire_on = []
        def mark_on(*a, **k):
            acquire_on.append("acquire")
            return {}
        usage.acquire = mark_on
        try:
            cat_on = load_catalog(cwd=cwd, config_dir=world.config_dir)
            delegate.probe_meters(False, cat_on["routing"])
            ok34b = acquire_on == ["acquire"]
            delegate.probe_meters(True, cat_on["routing"])
            ok34b = ok34b and acquire_on == ["acquire"]
        finally:
            usage.acquire = orig_acquire
        record("34b meters on still probes unless --no-probe", ok34b, repr(acquire_on))

        # 34c. one `run` acquires the Meters once before the relay: the rank's
        # acquisition serves the dispatch. `dispatch` alone still probes first.
        # Meters are on here (34b). Each usage.acquire call is logged with its
        # refresh flag; the Ads adapter's launch marks when the relay ran.
        probe_log = os.path.join(tmpdir, "probes34c.log")
        count_probes = (
            f"import sys; sys.path.insert(0, {DELEGATE_DIR!r}); import delegate, relays, usage\n"
            "def counted(*a, **k):\n"
            f"    open({probe_log!r}, 'a').write(('refresh' if k.get('refresh') else 'cached') + '\\n')\n"
            "    return {}\n"
            "usage.acquire = counted\n"
            "real_launch = relays.Ads._launch\n"
            "def marked_launch(self, job, run_dir):\n"
            f"    open({probe_log!r}, 'a').write('relay\\n')\n"
            "    return real_launch(self, job, run_dir)\n"
            "relays.Ads._launch = marked_launch\n"
            "sys.exit(delegate.main())"
        )

        def probes_for(cmd, args):
            if os.path.exists(probe_log):
                os.remove(probe_log)
            res = subprocess.run(
                [sys.executable, "-c", count_probes, cmd, "--config-dir", world.config_dir,
                 "--ads-dir", world.ads_dir, "--runs-dir", world.runs_dir] + args,
                capture_output=True, text=True, env=world.env)
            seen = open(probe_log).read().split() if os.path.exists(probe_log) else []
            return res, seen

        b34c = make_brief("b34c.md", f"fake-relay: status=completed final={done_final}\nBrief 34c.")
        res34c_run, seen_run = probes_for("run", ["mechanical", "--brief", b34c, "--cwd", cwd,
                                                  "--harnesses", "agy,codex,grok"])
        res34c_disp, seen_disp = probes_for("dispatch", ["--lane", "flash-high@agy", "--class", "mechanical",
                                                         "--brief", b34c, "--cwd", cwd])
        before_relay = lambda seen: seen[:seen.index("relay")] if "relay" in seen else None
        ok34c = (
            res34c_run.returncode == 0 and before_relay(seen_run) is not None and
            len(before_relay(seen_run)) == 1 and
            res34c_disp.returncode == 0 and before_relay(seen_disp) == ["refresh"]
        )
        record("34c. run acquires the Meters once before the relay; dispatch alone still probes", ok34c,
               f"run={seen_run} rc={res34c_run.returncode} out={res34c_run.stdout[-300:]} err={res34c_run.stderr[-300:]} "
               f"dispatch={seen_disp} rc={res34c_disp.returncode}")

        # -------------------------------------------------------------
        # 35. run prints the overflow header and picks in the admitted Tier
        # (ticket 29). flash-high@agy moves to tier 4 for this case: its Meter
        # is unknown by decision, so in the mechanical Range it would always be
        # eligible and the Range could never stop.
        _lanes_path35 = os.path.join(world.config_dir, "lanes.json")
        with open(_lanes_path35, encoding="utf-8") as _f:
            _lanes35 = _json.load(_f)
        _lanes35["lanes"]["flash-high@agy"]["tier"] = 4
        with open(_lanes_path35, "w", encoding="utf-8") as _f:
            _json.dump(_lanes35, _f, indent=2)

        # codex and grok under the Gate; claude-general healthy at tier 3
        over_meters35 = write_meters_doc(os.path.join(tmpdir, "over_meters35.json"), [
            meter("codex", weekly=0.02, five_h=0.02, pace=0.05, status="unavailable"),
            meter("grok", weekly=0.02, pace=0.05, status="unavailable"),
            meter("claude-fable", weekly=0.90, five_h=0.90, pace=1.10, status="ok"),
            meter("claude-general", weekly=0.90, five_h=0.90, pace=1.10, status="ok"),
            meter("agy-gemini", weekly=0.61, five_h=0.61, pace=3.27, status="ok"),
        ])
        b35 = make_brief("b35.md", "Brief 35.")
        runs_before35 = set(os.listdir(world.runs_dir))
        res35 = run_run(world, ["mechanical", "--brief", b35, "--cwd", cwd,
                                "--meters", over_meters35, "--dry-run"])
        runs_after35 = set(os.listdir(world.runs_dir))
        lines35 = res35.stdout.strip().splitlines()
        ok35 = (
            res35.returncode == 0 and
            lines35[0].startswith("# mechanical") and "floor=1 ceiling=2" in lines35[0] and
            lines35[1] == "# overflow: ceiling 2 -> 3, all in-Range Lanes under Gate" and
            "1. opus-high@claude" in lines35[2] and
            any("terra-high@codex" in line and "vetoed:gate" in line for line in lines35) and
            "delegate: dry run, nothing dispatched" in res35.stdout and
            runs_after35 == runs_before35
        )
        record("35. run --dry-run prints the overflow header and a Tier 3 pick", ok35,
               f"rc={res35.returncode} stdout={res35.stdout} stderr={res35.stderr}")

        # -------------------------------------------------------------
        # 37. A relayed Run refused for its usage limit holds that Lane's
        # Meter. test_runs proves the Run settles the hold; this proves
        # dispatch hands the Run its Lane's meter.
        limits37 = os.path.join(os.path.dirname(world.cache_path), "limits.json")
        if os.path.exists(limits37):
            os.remove(limits37)
        b37 = make_brief("b37.md", 'fake-relay: status=failed error="You\'ve reached your free Grok Build usage limit for now" exit=1\nBrief 37.')
        res37 = run_dispatch(world, ["--lane", "grok46-high@grok", "--class", "impl", "--brief", b37, "--cwd", cwd])
        held37 = json.load(open(limits37)) if os.path.exists(limits37) else {}
        record("37. a relayed Run refused for its usage limit holds that Lane's Meter",
               res37.returncode == 1 and list(held37) == ["grok"] and
               "delegate: grok meter held at 0% left until " in res37.stderr,
               f"rc={res37.returncode} limits={held37} out={res37.stdout} err={res37.stderr[-400:]}")
        if os.path.exists(limits37):
            os.remove(limits37)

    if fails > 0:
        print(f"FAIL: {fails} tests failed", file=sys.stderr)
        sys.exit(1)
    else:
        print("PASS: all test_dispatch.py tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
