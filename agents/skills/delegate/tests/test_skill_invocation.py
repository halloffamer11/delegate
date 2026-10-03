#!/usr/bin/env python3
"""test_skill_invocation.py — a user-invoked skill says so to every harness that reads it.

ADR 0001: delegate is user-invoked only. Claude Code reads
`disable-model-invocation: true` in SKILL.md; Codex ignores that field and
reads `policy.allow_implicit_invocation: false` from `agents/openai.yaml`
beside it. A skill that sets one switch must set the other, so a new skill
cannot miss Codex.
"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))

failures = []


def record(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def frontmatter(skill_md):
    """The SKILL.md frontmatter as {key: raw value}, top-level keys only."""
    with open(skill_md, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line[:1] not in (" ", "\t") and ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def codex_implicit_invocation(skill_dir):
    """`policy.allow_implicit_invocation` from agents/openai.yaml as a string,
    or None when the file or the key is missing.

    Stdlib only, so a small reader for the one nested key this test needs.
    """
    path = os.path.join(skill_dir, "agents", "openai.yaml")
    if not os.path.isfile(path):
        return None
    in_policy = False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if line[:1] not in (" ", "\t"):
                in_policy = line.strip() == "policy:"
                continue
            key, _, value = line.strip().partition(":")
            if in_policy and key.strip() == "allow_implicit_invocation":
                return value.strip()
    return None


def mismatches(skills_dir):
    """Skill names whose two switches disagree, with the reason."""
    out = []
    for name in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        claude_off = frontmatter(skill_md).get("disable-model-invocation") == "true"
        codex = codex_implicit_invocation(os.path.join(skills_dir, name))
        codex_off = codex == "false"
        if claude_off and not codex_off:
            out.append((name, "sets disable-model-invocation but agents/openai.yaml does not set "
                              "policy.allow_implicit_invocation: false"))
        elif codex_off and not claude_off:
            out.append((name, "agents/openai.yaml blocks implicit invocation but SKILL.md does not "
                              "set disable-model-invocation: true"))
    return out


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    found = mismatches(SKILLS_DIR)
    record("1. every shipped skill sets both switches or neither", not found, found)

    user_invoked = [n for n in sorted(os.listdir(SKILLS_DIR))
                    if os.path.isfile(os.path.join(SKILLS_DIR, n, "SKILL.md"))
                    and frontmatter(os.path.join(SKILLS_DIR, n, "SKILL.md")).get(
                        "disable-model-invocation") == "true"]
    record("2. delegate and council are user-invoked", {"delegate", "council"} <= set(user_invoked),
           user_invoked)

    with tempfile.TemporaryDirectory() as tmp:
        claude_only = "---\nname: a\ndescription: x\ndisable-model-invocation: true\n---\n"
        write(os.path.join(tmp, "a", "SKILL.md"), claude_only)
        write(os.path.join(tmp, "b", "SKILL.md"), claude_only)
        write(os.path.join(tmp, "b", "agents", "openai.yaml"),
              "interface:\n  allow_implicit_invocation: false\n")
        write(os.path.join(tmp, "c", "SKILL.md"), claude_only)
        write(os.path.join(tmp, "c", "agents", "openai.yaml"),
              "policy:\n  allow_implicit_invocation: false  # Codex's switch\n")
        write(os.path.join(tmp, "d", "SKILL.md"), "---\nname: d\ndescription: x\n---\n")
        write(os.path.join(tmp, "d", "agents", "openai.yaml"),
              "policy:\n  allow_implicit_invocation: false\n")
        names = [n for n, _ in mismatches(tmp)]
        record("3. a Claude-only skill fails", "a" in names, names)
        record("4. the key outside `policy:` does not count", "b" in names, names)
        record("5. both switches pass", "c" not in names, names)
        record("6. a Codex-only skill fails", "d" in names, names)

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
