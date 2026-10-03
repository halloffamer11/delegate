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
    record("each adapter names a binary, efforts, a vendor (or serves any) and a relay",
           all(h.binary and h.efforts and (h.vendor or h.any_vendor) and h.relay
               for h in harnesses.REGISTRY),
           repr([(h.name, h.binary, h.efforts, h.vendor, h.relay) for h in harnesses.REGISTRY]))
    record("catalog's per-harness efforts come from the adapters",
           all(catalog.HARNESS_EFFORTS[h.name] == tuple(h.efforts) for h in harnesses.REGISTRY))
    record("discovery asks harnesses with a model list first",
           [harnesses.get(n).catalog_models for n in harnesses.discovery_order()]
           == sorted(harnesses.get(n).catalog_models for n in harnesses.discovery_order()))


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
    absent = kiro.probe()
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


if __name__ == "__main__":
    test_registry_is_the_list()
    test_binary_need_not_be_the_name()
    test_family()
    test_run_args()
    test_ads_reads_the_registry()
    test_kiro()
    sys.exit(1 if fails else 0)
