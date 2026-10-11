#!/usr/bin/env python3
"""test_harnesses.py — the harness registry (any-harness ticket 11).

Run: python3 tests/test_harnesses.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import catalog  # noqa: E402
import harnesses  # noqa: E402
from harnesses.base import Harness  # noqa: E402

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}", file=sys.stderr)


def test_registry_is_the_list():
    record("catalog's harness list is the registry's",
           harnesses.NAMES == harnesses.NAMES and len(set(harnesses.NAMES)) == len(harnesses.NAMES),
           f"{harnesses.NAMES} vs {harnesses.NAMES}")
    record("each adapter names a binary, efforts, the models it owns and a relay",
           all(h.binary and h.efforts and (h.vendor or h.owns("any-model")) and h.relay
               for h in harnesses.REGISTRY),
           repr([(h.name, h.binary, h.efforts, h.vendor, h.relay) for h in harnesses.REGISTRY]))
    record("catalog's per-harness efforts come from the adapters",
           all(tuple(harnesses.get(h.name).efforts) == tuple(h.efforts) for h in harnesses.REGISTRY))
    record("discovery asks harnesses with a model list first",
           [harnesses.get(n).catalog_models for n in harnesses.discovery_order()]
           == sorted(harnesses.get(n).catalog_models for n in harnesses.discovery_order()))


def test_lane_name():
    """One owner spells and splits `<model-effort>@<harness>`; the scripts
    that build or read a Lane name agree with it."""
    import discover
    import orchestrators
    record("lane_name joins a stem, an effort and a harness",
           harnesses.lane_name("sol", "high", "codex") == "sol-high@codex"
           and harnesses.lane_name("sol-high", None, "codex") == "sol-high@codex")
    record("split_lane is lane_name's inverse; no `@` is no harness",
           harnesses.split_lane("sol-high@codex") == ("sol-high", "codex")
           and harnesses.split_lane("sol-high") == ("sol-high", None)
           and harnesses.split_lane("") == ("", None)
           and harnesses.split_lane(None) == ("", None))
    sample = catalog.load_json(os.path.join(SCRIPTS, "..", "assets", "samples", "lanes.json"))
    lanes = sample["lanes"]
    record("every sample Lane name splits to its own harness",
           all(harnesses.split_lane(name)[1] == lane["harness"] for name, lane in lanes.items()))
    record("discovery's names and stems go through the pair",
           discover._free_name("sol", "high", "codex", {"sol-high@codex"}) == "sol2-high@codex"
           and discover._lane_stem_of("sol-high@codex") == "sol")
    profile = {"native": {"agent": "lane-{model_effort}"}}
    record("an orchestrator's agent name takes the Lane's model-effort",
           orchestrators.agent_name(profile, "fable-xhigh@claude") == "lane-fable-xhigh")
    try:
        catalog.validate_lanes(dict(sample, lanes={"sol-high@agy": dict(lanes["sol-high@codex"])}))
        msg = ""
    except catalog.CatalogError as e:
        msg = str(e)
    record("the catalog refuses a Lane whose name names another harness",
           "must end with '@codex'" in msg, msg)


def test_binary_need_not_be_the_name():
    """A harness whose CLI is not named after it (Kiro: kiro-cli) is installed
    exactly when its binary is on PATH."""

    class Other(Harness):
        name = "other"
        binary = "other-cli"
        efforts = ("high",)
        vendor = "other"

    other = Other()
    saved_registry = harnesses._BY_NAME.copy()
    saved_path = os.environ.get("PATH", "")
    with tempfile.TemporaryDirectory() as d:
        harnesses._BY_NAME["other"] = other
        try:
            os.environ["PATH"] = d
            absent = harnesses.cli_installed("other")
            # a file named after the harness is not its CLI
            for name in ("other", "other-cli"):
                path = os.path.join(d, name)
                with open(path, "w") as f:
                    f.write("#!/bin/sh\nexit 0\n")
                os.chmod(path, 0o755)
                if name == "other":
                    named_after = harnesses.cli_installed("other")
                    os.remove(path)
            present = harnesses.cli_installed("other")
        finally:
            os.environ["PATH"] = saved_path
            harnesses._BY_NAME.clear()
            harnesses._BY_NAME.update(saved_registry)
    record("a CLI is found by the adapter's binary, not the harness name",
           absent is False and named_after is False and present is True,
           f"absent={absent} named_after={named_after} present={present}")
    record("the relay defaults to <name>-delegate", other.relay == "other-delegate", other.relay)


def test_family():
    agy = harnesses.get("agy")
    record("a harness with the effort in the slug splits it off; others never do",
           harnesses.family("agy", "gemini-3.8-flash-high") == ("gemini-3.8-flash", "high")
           and harnesses.family("codex", "gpt-6-sol-high") == ("gpt-6-sol-high", None)
           and agy.lane_model({"slug": "gemini-3.8-flash", "members": {"low": "gemini-3.8-flash-low"}}, "low")
           == "gemini-3.8-flash-low")


def test_run_args():
    record("a read-only run is read-only on every harness",
           all("--read-only" in h.run_args("high", "10m", None)[0] for h in harnesses.REGISTRY))
    record("agy takes no effort flag and writes with skipped permissions",
           harnesses.get("agy").run_args("high", "10m", "/w")[0]
           == ["--print-timeout", "10m", "--dangerously-skip-permissions"])


def test_ads_reads_the_registry():
    out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "harnesses"), "relays"],
                         capture_output=True, text=True)
    record("ads.sh's relay list is the registry's",
           out.stdout.split() == [h.relay for h in harnesses.REGISTRY], out.stdout + out.stderr)
    with open(os.path.join(SCRIPTS, "ads.sh")) as f:
        text = f.read()
    record("ads.sh keeps no harness list of its own", 'HARNESSES="' not in text)


def test_ads_install_fetches_a_pin_off_the_default_branch():
    """`ads.sh install` reaches a pin that only a side branch of the fork holds.
    A clone made before the pin is the 2026-10-03 "commit mismatch": a fetch by
    URL brings down the default branch only."""
    def git(*args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

    with tempfile.TemporaryDirectory() as tmp:
        fork = os.path.join(tmp, "fork")
        os.mkdir(fork)
        git("init", "-q", "-b", "main", cwd=fork)
        ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
        git(*ident, "commit", "-q", "--allow-empty", "-m", "default", cwd=fork)
        existing = os.path.join(tmp, "existing")
        git("clone", "-q", fork, existing)
        git("checkout", "-q", "-b", "side", cwd=fork)
        git(*ident, "commit", "-q", "--allow-empty", "-m", "pin", cwd=fork)
        pin = git("rev-parse", "HEAD", cwd=fork)
        git("checkout", "-q", "main", cwd=fork)

        with open(os.path.join(SCRIPTS, "ads.sh")) as f:
            text = f.read()
        lines = [f"ADS_REPO={fork}" if l.startswith("ADS_REPO=")
                 else f"ADS_COMMIT={pin}" if l.startswith("ADS_COMMIT=") else l
                 for l in text.splitlines()]
        script = os.path.join(tmp, "ads.sh")
        with open(script, "w") as f:
            f.write("\n".join(lines) + "\n")

        for case, ads in (("fresh clone", os.path.join(tmp, "fresh")), ("existing clone", existing)):
            out = subprocess.run(["sh", script, "install"], capture_output=True, text=True,
                                 env=dict(os.environ, ADS_DIR=ads))
            head = git("rev-parse", "HEAD", cwd=ads) if os.path.isdir(ads) else ""
            record(f"ads.sh install reaches a side-branch pin ({case})",
                   out.returncode == 0 and head == pin, out.stdout + out.stderr)


KIRO_FIXTURES = os.path.join(HERE, "fixtures", "kiro")


def test_kiro():
    """Kiro (ticket 15): its CLI is kiro-cli, it serves every vendor's models,
    and its first Lanes start from the adapter's starter with a Meter whose
    Remaining is unknown."""
    import copy
    import discover
    kiro = harnesses.get("kiro")
    with open(os.path.join(KIRO_FIXTURES, "kiro-models.json")) as f:
        models = kiro.parse_models(f.read())
    slugs = [m["slug"] for m in models]
    efforts = {m["slug"]: m["efforts"] for m in models}
    record("kiro's listing gives every model but the router, with the efforts each supports",
           kiro.binary == "kiro-cli" and "auto" not in slugs
           and efforts["claude-sonnet-5.5"] == ["low", "medium", "high"]
           and efforts["gpt-5.6-sol"] == list(kiro.efforts)
           and efforts["claude-haiku-4.5"] == [], repr(efforts))
    with open(os.path.join(KIRO_FIXTURES, "kiro-models-2.27.1.json")) as f:
        real = kiro.parse_models(f.read())
    record("kiro-cli 2.27.1's real listing gives its eight models, each with every Kiro effort",
           [m["slug"] for m in real] == ["claude-sonnet-4.5", "claude-sonnet-4", "claude-haiku-4.5",
                                         "deepseek-3.2", "minimax-m2.5", "minimax-m2.1", "glm-5",
                                         "qwen3-coder-next"]
           and all(m["efforts"] == list(kiro.efforts) and m["unknown_efforts"] == [] for m in real)
           and real[0]["display_name"] == "claude-sonnet-4.5", repr(real))
    record("a read-only kiro run passes the effort, the timeout and --read-only to the relay",
           kiro.run_args("high", "30m", None) == (["--effort", "high", "--timeout", "30m", "--read-only"], None))
    absent = kiro.meters()
    record("kiro's Meter has no Window read, so no Remaining, which the Gate never vetoes",
           len(absent) == 1 and absent[0].meter == "kiro" and absent[0].group is None
           and absent[0].five_h is None and absent[0].weekly is None, repr(absent))

    samples = os.path.join(HERE, "..", "assets", "samples")
    lanes_doc = catalog.load_json(os.path.join(samples, "lanes.json"))
    with tempfile.TemporaryDirectory() as d:
        fixtures = os.path.join(d, "fixtures")
        os.makedirs(fixtures)
        for name in os.listdir(os.path.join(HERE, "fixtures", "discover")):
            with open(os.path.join(HERE, "fixtures", "discover", name), "rb") as src, \
                    open(os.path.join(fixtures, name), "wb") as dst:
                dst.write(src.read())
        with open(os.path.join(KIRO_FIXTURES, "kiro-models.json"), "rb") as src, \
                open(os.path.join(fixtures, "kiro-models.json"), "wb") as dst:
            dst.write(src.read())
        found = discover.discover(copy.deepcopy(lanes_doc), fixture_dir=fixtures)
    refreshed, plan = discover.refresh_catalog(copy.deepcopy(lanes_doc), found)
    kiro_lanes = {n: l for n, l in refreshed["lanes"].items() if l["harness"] == "kiro"}
    models_run = {l["model"] for l in kiro_lanes.values()}
    record("the refresh offers Kiro's current models of every vendor as Lanes to screen",
           found["harnesses"]["kiro"]["status"] == "ok"
           # a superseded model (Opus 4.8) is not offered, and nor is one with
           # no effort level (Haiku), since every Lane carries an effort
           and models_run == {"claude-opus-5.5", "claude-sonnet-5.5", "gpt-5.6-sol"}
           and all(l["meter"] == "kiro" and l["tier"] == 1 for l in kiro_lanes.values())
           and refreshed["meters"]["kiro"]["harness"] == "kiro",
           f"{sorted(kiro_lanes)} {sorted(models_run)}")
    try:
        catalog.validate_lanes(copy.deepcopy(refreshed), "refreshed")
        valid = True
    except catalog.CatalogError as e:
        valid = repr(e)
    record("the refreshed catalog with Kiro's Lanes and Meter is valid", valid is True, valid)


def test_effort_words():
    """One effort list (base.EFFORTS): agy reads every effort word off a slug,
    and a word no Lane may carry is set apart, not dropped."""
    agy = harnesses.get("agy")
    listing = ("Fetching available models...\n"
               "gemini-3.9-flash-xhigh\tGemini 3.9 Flash (Xhigh)\n"
               "gemini-3.9-flash-high\tGemini 3.9 Flash (High)\n"
               "gemini-3.9-flash-max\tGemini 3.9 Flash (Max)\n"
               "gemini-3.9-flash-low\tGemini 3.9 Flash (Low)\n")
    families = agy.parse_models(listing)
    record("agy groups an -xhigh or -max slug into its family, not a model of its own",
           [f["slug"] for f in families] == ["gemini-3.9-flash"]
           and families[0]["efforts"] == ["low", "high", "xhigh", "max"]
           and families[0]["members"]["xhigh"] == "gemini-3.9-flash-xhigh"
           and families[0]["display_name"] == "Gemini 3.9 Flash", repr(families))
    record("agy offers an effort its slug names, beside the ones it is known to offer",
           agy.offers_effort("gemini-3.9-flash-xhigh", "xhigh")
           and not agy.offers_effort("gemini-3.9-flash-high", "xhigh")
           and agy.offers_effort("gemini-3.9-flash-high", "high")
           and not harnesses.get("codex").offers_effort("gpt-6-sol-xhigh", "extreme"))
    record("every adapter's efforts are EFFORTS words, in EFFORTS order",
           all(list(h.efforts) == [e for e in harnesses.EFFORTS if e in h.efforts]
               for h in harnesses.REGISTRY),
           repr([(h.name, h.efforts) for h in harnesses.REGISTRY]))
    record("an effort word no Lane may carry is set apart, not dropped",
           harnesses.get("codex").split_efforts(["low", "high", "extreme"]) == (["low", "high"], ["extreme"])
           and harnesses.get("kiro").split_efforts(["high", "ultra"]) == (["high"], ["ultra"])
           and agy.split_efforts(["xhigh", "turbo"]) == (["xhigh"], ["turbo"]))
    claude = harnesses.get("claude")
    help_text = "  --effort <level>  Effort level\n     (low, medium, high, xhigh, max, extreme)\n  --foo\n"
    record("claude --help keeps an effort word delegate does not know yet",
           claude.efforts_from_help(help_text) == ["low", "medium", "high", "xhigh", "max", "extreme"]
           and claude.efforts_from_help("  --effort <level>  Effort (default: on)\n") == [],
           repr(claude.efforts_from_help(help_text)))
    kiro = harnesses.get("kiro")
    listed = kiro.parse_models('[{"id": "m", "efforts": ["low", "high", "extreme"]}]')
    record("kiro keeps a listed effort it does not run apart, for the refresh to name",
           listed[0]["efforts"] == ["low", "high"] and listed[0]["unknown_efforts"] == ["extreme"],
           repr(listed))


def test_claude_model_meter():
    """A version in a /usage model label does not move the row off its Meter,
    and a Model meter's Windows are the shared ones beside its own week."""
    import json
    import types
    from unittest import mock
    from harnesses import claude as claude_module
    adapter = harnesses.get("claude")
    text = ("Current session: 40% used\nCurrent week (all models): 30% used\n"
            "Current week (Fable 5.2): 96% used\n")
    with mock.patch.object(adapter, "installed", return_value=True), \
         mock.patch.object(claude_module, "run_cli", return_value=types.SimpleNamespace(
             returncode=0, stdout=json.dumps({"result": text}))):
        windows = adapter.meters()
    record("'Current week (Fable 5.2)' is the claude-fable Meter, as 'Fable' was",
           [w.meter for w in windows] == ["claude-general", "claude-fable"]
           and [w.group for w in windows] == ["general", "fable"]
           and claude_module.model_meter_name("Fable") == "fable"
           and claude_module.model_meter_name("Fable v6") == "fable",
           repr(windows))
    fable = windows[-1] if windows else None
    record("a claude Model meter hands over the session, the week for all models and its own week",
           fable is not None and abs(fable.five_h - 0.6) < 1e-9 and abs(fable.weekly - 0.7) < 1e-9
           and abs(fable.weekly_model - 0.04) < 1e-9 and windows[0].weekly_model is None,
           repr(windows))


def test_claude_reset():
    """`/usage` prints a reset as 'Sep 8 at 2:59pm (America/New_York)', with
    no year; the adapter reads it as epoch seconds (moved from
    test_usage_reset)."""
    from harnesses.claude import reset
    t_3pm = reset("Sep 8 at 3pm (America/New_York)")
    t_259pm = reset("Sep 8 at 2:59pm (America/New_York)")
    record("claude reads a reset with and without minutes, a minute apart",
           t_3pm is not None and t_259pm is not None and t_3pm - t_259pm == 60.0,
           f"{t_3pm} {t_259pm}")
    record("claude reads a reset at 12am",
           reset("Sep 8 at 12am (America/New_York)") is not None)
    record("claude reads no reset from empty or other text",
           reset("") is None and reset("invalid text") is None)


AGY_TWO_GROUPS = {"command": {"data": {"groups": [
    {"name": "Gemini Models", "buckets": [
        {"window": "5h", "remaining_fraction": 0.9, "reset_time": "2026-10-03T18:00:00Z"},
        {"window": "weekly", "remaining_fraction": 0.7, "reset_time": "2026-10-08T00:00:00Z"}]},
    {"name": "Claude and GPT models", "buckets": [
        {"window": "5h", "remaining_fraction": 0.4, "reset_time": "2026-10-03T17:00:00Z"},
        {"window": "weekly", "remaining_fraction": 0.6, "reset_time": "2026-10-09T00:00:00Z"}]}]}}}

# Probes agy in a fresh interpreter and prints what came back, and whether
# usage was imported on the way.
_PROBE_CHILD = """
import json, sys
sys.path.insert(0, sys.argv[1])
import harnesses
from harnesses import base
probed = harnesses.get("agy").meters()
windows = getattr(base, "Windows", None)
print(json.dumps({
    "windows": windows is not None and all(isinstance(w, windows) for w in probed),
    "probed": [w._asdict() if hasattr(w, "_asdict") else w for w in probed],
    "usage": "usage" in sys.modules,
}))
"""


def test_a_probe_hands_back_windows_without_importing_usage():
    """The harness port (Meters ticket B4): a probe hands the Meters module
    its Windows, and usage.py builds the rows, so no adapter imports usage."""
    import json
    from datetime import datetime
    from harnesses.agy import COMBINED_NOTE
    with tempfile.TemporaryDirectory() as d:
        agy = os.path.join(d, "agy")
        with open(agy, "w") as f:
            f.write("#!/bin/sh\nprintf '%s\\n' '" + json.dumps(AGY_TWO_GROUPS) + "'\n")
        os.chmod(agy, 0o755)
        child = subprocess.run([sys.executable, "-c", _PROBE_CHILD, SCRIPTS],
                               capture_output=True, text=True, env=dict(os.environ, PATH=d))
    try:
        out = json.loads(child.stdout)
    except ValueError:
        out = {}
    probed = {w.get("meter"): w for w in out.get("probed") or () if isinstance(w, dict)}
    gemini = probed.get("agy-gemini") or {}
    week_end = datetime.fromisoformat("2026-10-08T00:00:00+00:00").timestamp()
    record("a probe hands back Windows without importing usage",
           child.returncode == 0 and out.get("windows") is True and out.get("usage") is False
           and list(probed) == ["agy-gemini", "agy-claude-gpt"]
           and [w["group"] for w in probed.values()] == ["gemini", "claude-gpt"]
           and gemini.get("five_h") == 0.9 and gemini.get("weekly") == 0.7
           and gemini.get("reset_weekly") == week_end and gemini.get("weekly_model") is None
           and all(w["note"] == COMBINED_NOTE for w in probed.values()),
           child.stdout + child.stderr)
    adapters = os.path.join(SCRIPTS, "harnesses")
    importers = []
    for name in sorted(os.listdir(adapters)):
        if name.endswith(".py"):
            with open(os.path.join(adapters, name), encoding="utf-8") as f:
                if any(line.strip().startswith(("import usage", "from usage")) for line in f):
                    importers.append(name)
    record("no adapter imports usage", importers == [], importers)


def test_meter_identity():
    """Each adapter says which Meters its probe reports, and the catalog check
    holds a Lane's Meter to them (ticket 25)."""
    import json
    import types
    from unittest import mock
    from harnesses import agy as agy_module
    sample = catalog.load_json(os.path.join(SCRIPTS, "..", "assets", "samples", "lanes.json"))
    models = {}
    for lane in sample["lanes"].values():
        models.setdefault(lane["meter"], []).append(lane["model"])
    record("every sample Meter is one its harness's probe reports",
           all(harnesses.get(meter["harness"]).reports_meter(name, models.get(name, ()))
               for name, meter in sample["meters"].items()),
           repr({n: harnesses.get(m["harness"]).meter_names() for n, m in sample["meters"].items()}))
    claude = harnesses.get("claude")
    record("a claude model Meter is named for a model the catalog runs on it",
           claude.reports_meter("claude-fable", ["claude-fable-5-1"])
           and not claude.reports_meter("claude-fabel", ["claude-fable-5-1"])
           and not claude.reports_meter("claude-generl")
           and harnesses.get("agy").meter_names() == ("agy-gemini", "agy-claude-gpt")
           and harnesses.get("codex").meter_names() == ("codex",))
    agy = harnesses.get("agy")
    listing = {"command": {"data": {"groups": [{"name": "Gemini Models", "buckets": []},
                                               {"name": "Claude and GPT", "buckets": []}]}}}
    with mock.patch.object(agy, "installed", return_value=True), \
         mock.patch.object(agy_module, "run_cli", return_value=types.SimpleNamespace(
             returncode=0, stdout=json.dumps(listing))):
        windows = agy.meters()
    record("agy's probe Windows are the Meters it declares",
           tuple(w.meter for w in windows) == agy.meter_names()
           and [w.group for w in windows] == ["gemini", "claude-gpt"], repr(windows))
    record("a Meter's name is the harness's, or `<harness>-<group>`",
           agy.meter_name("gemini") == "agy-gemini" and harnesses.get("codex").meter_name(None) == "codex"
           and agy.windows("claude-gpt", weekly=0.5).meter == "agy-claude-gpt")



def test_agy_opus_pool():
    """agy serves Opus on the pool `/usage` reports as its second group, shared
    with Sonnet and GPT-OSS (any-harness ticket 31)."""
    import json
    import types
    from unittest import mock
    from harnesses import agy as agy_module
    agy = harnesses.get("agy")
    record("agy owns Gemini and Opus, and no other vendor's model",
           agy.owns("gemini-3.8-flash-high") and agy.owns("claude-opus-5-5-high")
           and not agy.owns("claude-sonnet-5-5-high") and not agy.owns("gpt-oss-120b-medium"))
    record("an agy model's group decides its Meter",
           agy.lane_meter("claude-opus-5-5-low") == "agy-claude-gpt"
           and agy.lane_meter("gemini-3.8-flash-high") == "agy-gemini"
           and harnesses.get("codex").lane_meter("gpt-6-sol") is None)
    # The shape of the user's `agy --print /usage --output-format json`, 2026-10-03:
    # two groups, each with a 5h and a weekly bucket.
    with mock.patch.object(agy, "installed", return_value=True), \
         mock.patch.object(agy_module, "run_cli", return_value=types.SimpleNamespace(
             returncode=0, stdout=json.dumps(AGY_TWO_GROUPS))):
        windows = {w.meter: w for w in agy.meters()}
    filled = all(getattr(windows.get(name), key, None) is not None
                 for name in ("agy-gemini", "agy-claude-gpt")
                 for key in ("five_h", "weekly", "reset_5h", "reset_weekly"))
    record("agy's two-group usage gives agy-gemini and agy-claude-gpt with both Windows",
           sorted(windows) == ["agy-claude-gpt", "agy-gemini"] and filled
           and windows["agy-claude-gpt"].five_h == 0.4
           and windows["agy-claude-gpt"].weekly == 0.6, repr(windows))
    from harnesses.agy import COMBINED_NOTE
    record("agy's note calls the combined figure the lower Window, an assumption",
           "assumption" in COMBINED_NOTE and "not a vendor bound" in COMBINED_NOTE
           and all(w.note == COMBINED_NOTE for w in windows.values()), COMBINED_NOTE)


def test_usage_limit():
    """Ticket 43: grok's free-tier refusal is a usage limit; other text is not."""
    grok = harnesses.get("grok")
    seen = "blocked: You've reached your free Grok Build usage limit for now. Get SuperGrok"
    record("grok reads its usage-limit refusal",
           grok.usage_limit("x\n" + seen) == seen)
    record("grok does not read other text as a usage limit",
           grok.usage_limit("permission gate cancelled the run") is None)
    record("a harness with no patterns never reads a usage limit",
           harnesses.get("codex").usage_limit(seen) is None)


if __name__ == "__main__":
    test_agy_opus_pool()
    test_meter_identity()
    test_registry_is_the_list()
    test_lane_name()
    test_effort_words()
    test_claude_model_meter()
    test_claude_reset()
    test_a_probe_hands_back_windows_without_importing_usage()
    test_binary_need_not_be_the_name()
    test_family()
    test_run_args()
    test_ads_reads_the_registry()
    test_ads_install_fetches_a_pin_off_the_default_branch()
    test_kiro()
    test_usage_limit()
    sys.exit(1 if fails else 0)
