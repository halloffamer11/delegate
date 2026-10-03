#!/usr/bin/env python3
"""orchestrators.py — orchestrator profiles: data, not code paths.

Delegate assumes nothing about the harness that is orchestrating. Every
harness that can run a shell and read files orchestrates the same way:
`delegate run` relays the job, and the orchestrator reads the run directory.
That default path needs no profile, and it is what an unknown or new harness
gets.

A profile, one JSON file named `<name>.json`, declares what an orchestrator can
do beyond that:

  harness     the harness the orchestrator is (lanes.json's name for it)
  detect_env  environment variables the orchestrator sets in the shell it
              gives its model; any one set means this orchestrator
  native      null, or how it runs a Lane of its own harness in-process:
                agents_dir  where its agent files live (~ expanded)
                agent       the agent name, from {model_effort}
                file        the agent file name, from {agent}
                template    the agent file, one line per entry, from {agent}
                            {lane} {model} {effort}; a line whose value is
                            empty (a model with no effort level) is dropped
                spawn       the one-line spawn instruction dispatch prints,
                            from {agent} {prompt}
  launch      optional: the headless command eval 3 starts it with
  agents      optional: agent files only this orchestrator uses, each
              {"file": path beside the profile, "dir": where it is linked};
              Claude's courier, the glue a Claude Workflow script needs
              because it has no shell. `make install` links them
              (`orchestrators.py agents`), so no other harness carries them

Profiles ship in assets/orchestrators/; a machine adds or overrides one in
~/.config/delegate/orchestrators/ ($DELEGATE_ORCHESTRATORS_DIR), with no code
change. The orchestrator is never assumed: `--orchestrator NAME`, else
$DELEGATE_ORCHESTRATOR, else the first profile whose detect_env is set; `none`,
an unknown name or nothing detected all mean the default path.

    python3 orchestrators.py            the profiles and which one is detected
    python3 orchestrators.py agents     each shipped profile agent: <source>\t<link>
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED_DIR = os.path.abspath(os.path.join(HERE, "..", "assets", "orchestrators"))
LOCAL_DIR = "~/.config/delegate/orchestrators"
DEFAULT = "none"


class ProfileError(ValueError):
    pass


def profile_dirs():
    local = os.environ.get("DELEGATE_ORCHESTRATORS_DIR") or LOCAL_DIR
    return [SHIPPED_DIR, os.path.expanduser(local)]


def _validate(name, doc, path):
    if not isinstance(doc, dict):
        raise ProfileError(f"{path}: a profile is a JSON object")
    if not isinstance(doc.get("harness"), str) or not doc["harness"]:
        raise ProfileError(f"{path}: harness must be a harness name")
    env = doc.get("detect_env", [])
    if not isinstance(env, list) or not all(isinstance(v, str) for v in env):
        raise ProfileError(f"{path}: detect_env must be a list of variable names")
    native = doc.get("native")
    if native is not None:
        if not isinstance(native, dict):
            raise ProfileError(f"{path}: native must be null or an object")
        for key in ("agents_dir", "agent", "file", "spawn"):
            if not isinstance(native.get(key), str) or not native[key]:
                raise ProfileError(f"{path}: native.{key} must be a non-empty string")
        template = native.get("template")
        if not isinstance(template, list) or not all(isinstance(v, str) for v in template):
            raise ProfileError(f"{path}: native.template must be a list of lines")
    agents = doc.get("agents", [])
    if not isinstance(agents, list) or not all(
            isinstance(a, dict) and all(isinstance(a.get(k), str) and a[k] for k in ("file", "dir"))
            for a in agents):
        raise ProfileError(f"{path}: agents must be a list of {{file, dir}} objects")
    out = dict(doc)
    out["name"] = name
    out["source_dir"] = os.path.dirname(os.path.abspath(path))
    out["agents"] = [dict(a) for a in agents]
    out["detect_env"] = list(env)
    return out


def load(dirs=None):
    """{name: profile}. A later directory's profile replaces an earlier one's."""
    profiles = {}
    for d in dirs or profile_dirs():
        if not os.path.isdir(d):
            continue
        for entry in sorted(os.listdir(d)):
            if not entry.endswith(".json"):
                continue
            path = os.path.join(d, entry)
            try:
                with open(path, encoding="utf-8") as f:
                    doc = json.load(f)
            except (OSError, ValueError) as e:
                raise ProfileError(f"{path}: {e}") from e
            name = entry[:-len(".json")]
            profiles[name] = _validate(name, doc, path)
    return profiles


def detect(env=None, profiles=None):
    """The detected orchestrator's name, or None for the default path."""
    env = os.environ if env is None else env
    profiles = load() if profiles is None else profiles
    for name, profile in profiles.items():
        if any(env.get(var) for var in profile["detect_env"]):
            return name
    return None


def resolve(name=None, env=None, profiles=None):
    """The profile for this run, or None for the default path.

    `name` is the `--orchestrator` value; then $DELEGATE_ORCHESTRATOR; then
    detection. `none`, an unknown name or nothing detected is None.
    """
    env = os.environ if env is None else env
    profiles = load() if profiles is None else profiles
    if name is None:
        name = env.get("DELEGATE_ORCHESTRATOR") or detect(env, profiles)
    if not name or name == DEFAULT:
        return None
    return profiles.get(name)


def is_native(profile, harness):
    """True when this orchestrator runs a Lane on this harness in-process."""
    return bool(profile and profile.get("native") and profile["harness"] == harness)


def native_profiles(profiles=None):
    """The profiles that run Lanes in-process."""
    profiles = load() if profiles is None else profiles
    return [p for p in profiles.values() if p.get("native")]


def native_harnesses(profiles=None):
    """Harnesses some orchestrator runs in-process, so its Meters are spent by
    the session itself."""
    return {p["harness"] for p in native_profiles(profiles)}


def _fill(text, values):
    return text.format(**values)


def agent_name(profile, lane):
    model_effort = lane.split("@", 1)[0]
    return _fill(profile["native"]["agent"], {"model_effort": model_effort, "lane": lane})


def agent_path(profile, lane, agents_dir=None):
    agent = agent_name(profile, lane)
    directory = agents_dir or os.path.expanduser(profile["native"]["agents_dir"])
    return os.path.join(directory, _fill(profile["native"]["file"], {"agent": agent}))


def agent_text(profile, lane, model, effort):
    """The agent file for one native Lane. `effort` None drops its line."""
    values = {"agent": agent_name(profile, lane), "lane": lane, "model": model,
              "effort": effort}
    lines = []
    for line in profile["native"]["template"]:
        fields = re.findall(r"\{(\w+)\}", line)
        if any(values.get(field) in (None, "") for field in fields):
            continue
        lines.append(_fill(line, values))
    return "\n".join(lines)


def spawn_line(profile, lane, prompt):
    return _fill(profile["native"]["spawn"], {"agent": agent_name(profile, lane), "prompt": prompt})


def agent_links(profiles=None):
    """[(source, link)] for every profile agent file: the file beside its
    profile, and where it is linked (~ expanded)."""
    profiles = load() if profiles is None else profiles
    links = []
    for profile in profiles.values():
        for agent in profile["agents"]:
            source = os.path.join(profile["source_dir"], agent["file"])
            link = os.path.join(os.path.expanduser(agent["dir"]), os.path.basename(agent["file"]))
            links.append((source, link))
    return links


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["agents"]:
        for source, link in agent_links(load([SHIPPED_DIR])):
            print(f"{source}\t{link}")
        return 0
    profiles = load()
    found = resolve()
    for name, profile in profiles.items():
        native = "native" if profile.get("native") else "relays every Lane"
        mark = "  (detected)" if found is not None and found["name"] == name else ""
        print(f"{name}: harness={profile['harness']} {native}{mark}")
    if found is None:
        print("orchestrator: none detected; every Lane is relayed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
