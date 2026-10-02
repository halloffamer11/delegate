#!/usr/bin/env python3
"""test_orchestrators.py — orchestrator profiles (any-harness ticket 13).

Run: python3 tests/test_orchestrators.py
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import orchestrators  # noqa: E402

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}", file=sys.stderr)


SHIPPED = orchestrators.load([orchestrators.SHIPPED_DIR])


def write_profile(d, name, doc):
    with open(os.path.join(d, f"{name}.json"), "w") as f:
        json.dump(doc, f)


def test_shipped():
    record("claude and codex profiles ship", {"claude", "codex"} <= set(SHIPPED), sorted(SHIPPED))
    record("only claude runs a Lane in-process",
           orchestrators.native_harnesses(SHIPPED) == {"claude"})
    record("every shipped launch puts the prompt in its argv",
           all("{prompt}" in p["launch"]["argv"] for p in SHIPPED.values() if p.get("launch")))


def test_resolution():
    claude = SHIPPED["claude"]
    cases = [
        ("nothing set is the default path", None, {}, None),
        ("CLAUDECODE detects Claude Code", None, {"CLAUDECODE": "1"}, "claude"),
        ("$DELEGATE_ORCHESTRATOR beats detection", None,
         {"CLAUDECODE": "1", "DELEGATE_ORCHESTRATOR": "codex"}, "codex"),
        ("--orchestrator beats both", "claude", {"DELEGATE_ORCHESTRATOR": "codex"}, "claude"),
        ("none is the default path, even inside Claude Code", "none", {"CLAUDECODE": "1"}, None),
        ("an unknown name is the default path", "kiro", {}, None),
    ]
    for label, name, env, want in cases:
        got = orchestrators.resolve(name, env=env, profiles=SHIPPED)
        record(label, (got or {}).get("name") == want, repr(got and got["name"]))
    record("a native harness is native only under its own orchestrator",
           orchestrators.is_native(claude, "claude")
           and not orchestrators.is_native(claude, "codex")
           and not orchestrators.is_native(SHIPPED["codex"], "codex")
           and not orchestrators.is_native(None, "claude"))


def test_agent_file():
    claude = SHIPPED["claude"]
    text = orchestrators.agent_text(claude, "opus-high@claude", "claude-opus-5-5", "high")
    record("the agent file names the agent, model and effort",
           "name: lane-opus-high" in text and "model: claude-opus-5-5" in text and "effort: high" in text, text)
    no_effort = orchestrators.agent_text(claude, "haiku@claude", "claude-haiku-4-5", None)
    record("a model with no effort drops the effort line",
           "effort:" not in no_effort and "model: claude-haiku-4-5" in no_effort, no_effort)
    path = orchestrators.agent_path(claude, "opus-high@claude", "/agents")
    record("the agent file path comes from the profile", path == "/agents/lane-opus-high.md", path)
    line = orchestrators.spawn_line(claude, "opus-high@claude", "/r/prompt.md")
    record("the spawn line names the agent and the prompt",
           "lane-opus-high" in line and "/r/prompt.md" in line, line)


def test_local_profile():
    """A machine adds an orchestrator with a file, no code change."""
    with tempfile.TemporaryDirectory() as d:
        write_profile(d, "kiro", {
            "harness": "kiro", "detect_env": ["KIRO_SESSION"],
            "native": {"agents_dir": os.path.join(d, "agents"), "agent": "k-{model_effort}",
                       "file": "{agent}.json", "template": ["{{\"model\": \"{model}\"}}"],
                       "spawn": "run {agent} on {prompt}"},
        })
        profiles = orchestrators.load([orchestrators.SHIPPED_DIR, d])
        kiro = orchestrators.resolve(env={"KIRO_SESSION": "1"}, profiles=profiles)
        record("a local profile is detected by its own env",
               kiro is not None and kiro["name"] == "kiro")
        record("a local profile adds native Lanes",
               orchestrators.is_native(kiro, "kiro") and "kiro" in orchestrators.native_harnesses(profiles))
        record("its agent file follows its template",
               orchestrators.agent_text(kiro, "sonnet-high@kiro", "s5", "high") == '{"model": "s5"}'
               and orchestrators.agent_path(kiro, "sonnet-high@kiro").endswith("k-sonnet-high.json"))
        write_profile(d, "claude", {"harness": "claude", "detect_env": ["CLAUDECODE"], "native": None})
        overridden = orchestrators.load([orchestrators.SHIPPED_DIR, d])["claude"]
        record("a local profile overrides a shipped one", overridden["native"] is None)

    with tempfile.TemporaryDirectory() as d:
        write_profile(d, "bad", {"harness": "x", "native": {"agent": "a"}})
        try:
            orchestrators.load([d])
            raised = False
        except orchestrators.ProfileError:
            raised = True
        record("a malformed profile is an error, not a silent default", raised)


def test_no_script_names_an_orchestrator():
    """Orchestrator behaviour lives in profiles: no script outside the harness
    adapters checks CLAUDECODE or writes into ~/.claude/agents."""
    offenders = []
    for entry in sorted(os.listdir(SCRIPTS)):
        if not entry.endswith(".py"):
            continue
        with open(os.path.join(SCRIPTS, entry), encoding="utf-8") as f:
            text = f.read()
        if entry == "orchestrators.py":
            continue
        if re.search(r"CLAUDECODE|\.claude/agents|ORCHESTRATOR\s*=", text):
            offenders.append(entry)
    record("no script hard-codes an orchestrator", not offenders, offenders)


if __name__ == "__main__":
    test_shipped()
    test_resolution()
    test_agent_file()
    test_local_profile()
    test_no_script_names_an_orchestrator()
    sys.exit(1 if fails else 0)
