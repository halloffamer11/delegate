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
    record("each adapter names a binary, efforts, a vendor and a relay",
           all(h.binary and h.efforts and h.vendor and h.relay for h in harnesses.REGISTRY),
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


if __name__ == "__main__":
    test_registry_is_the_list()
    test_binary_need_not_be_the_name()
    test_family()
    test_run_args()
    test_ads_reads_the_registry()
    sys.exit(1 if fails else 0)
