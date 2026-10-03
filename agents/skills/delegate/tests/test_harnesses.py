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
           catalog.HARNESSES == harnesses.NAMES and len(set(harnesses.NAMES)) == len(harnesses.NAMES),
           f"{catalog.HARNESSES} vs {harnesses.NAMES}")
    record("each adapter names a binary, efforts, the models it owns and a relay",
           all(h.binary and h.efforts and (h.vendor or h.owns("any-model")) and h.relay
               for h in harnesses.REGISTRY),
           repr([(h.name, h.binary, h.efforts, h.vendor, h.relay) for h in harnesses.REGISTRY]))
    record("catalog's per-harness efforts come from the adapters",
           all(catalog.HARNESS_EFFORTS[h.name] == tuple(h.efforts) for h in harnesses.REGISTRY))
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
           and catalog.slug_family("gemini-3.8-flash-low") == ("gemini-3.8-flash", "low")
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
    record("a read-only kiro run passes the effort, the timeout and --read-only to the relay",
           kiro.run_args("high", "30m", None) == (["--effort", "high", "--timeout", "30m", "--read-only"], None))
    absent = kiro.meters()
    record("kiro's Meter row has no Remaining, which the Gate never vetoes",
           len(absent) == 1 and absent[0]["remaining_weekly"] is None and absent[0]["harness"] == "kiro")

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
    """A version in a /usage model label does not move the row off its Meter."""
    import json
    import types
    import usage
    from harnesses import claude as claude_module
    adapter = harnesses.get("claude")
    saved = usage.run
    text = ("Current session: 40% used\nCurrent week (all models): 30% used\n"
            "Current week (Fable 5.2): 96% used\n")
    try:
        adapter.installed = lambda: True
        usage.run = lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=json.dumps({"result": text}))
        rows = adapter.meters()
    finally:
        usage.run = saved
        del adapter.installed
    record("'Current week (Fable 5.2)' is the claude-fable Meter, as 'Fable' was",
           [r["meter"] for r in rows] == ["claude-general", "claude-fable"]
           and claude_module.model_meter_name("Fable") == "fable"
           and claude_module.model_meter_name("Fable v6") == "fable",
           repr([r["meter"] for r in rows]))


def test_meter_identity():
    """Each adapter says which Meters its probe reports, and the catalog check
    holds a Lane's Meter to them (ticket 25)."""
    import json
    import types
    import usage
    from unittest import mock
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
         mock.patch.object(usage, "run", return_value=types.SimpleNamespace(
             returncode=0, stdout=json.dumps(listing))):
        rows = agy.meters()
    record("agy's probe rows are the Meters it declares, under `meter`",
           tuple(r["meter"] for r in rows) == agy.meter_names()
           and [r["group"] for r in rows] == ["gemini", "claude-gpt"], repr(rows))


if __name__ == "__main__":
    test_meter_identity()
    test_registry_is_the_list()
    test_lane_name()
    test_effort_words()
    test_claude_model_meter()
    test_binary_need_not_be_the_name()
    test_family()
    test_run_args()
    test_ads_reads_the_registry()
    test_kiro()
    sys.exit(1 if fails else 0)
