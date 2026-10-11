#!/usr/bin/env python3
"""test_usage_reset.py — claude_reset format parsing, the usage cache write and the
usage rows a probe builds, until ticket 19 moves what is left to test_harnesses and
test_usage."""
import json, os, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so that
# `catalog.find_git_root()` never finds the invoking checkout's own
# `.delegate/routing.json`. Every path this file needs comes from HERE.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))
import usage
import harnesses
from harnesses.agy import COMBINED_NOTE as AGY_NOTE
from harnesses.claude import reset as claude_reset
from usage import write_cache, meter_row as lane, get_cache_path


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def assert_true(cond, msg):
    if not cond:
        fail(msg)


def main():
    # 1. claude_reset tests
    t_3pm = claude_reset("Sep 8 at 3pm (America/New_York)")
    assert_true(t_3pm is not None, "claude_reset('Sep 8 at 3pm (America/New_York)') returned None")

    t_259pm = claude_reset("Sep 8 at 2:59pm (America/New_York)")
    assert_true(t_259pm is not None, "claude_reset('Sep 8 at 2:59pm (America/New_York)') returned None")

    diff = t_3pm - t_259pm
    assert_true(diff == 60.0, f"expected 60s diff between 2:59pm and 3pm, got {diff}")

    t_12am = claude_reset("Sep 8 at 12am (America/New_York)")
    assert_true(t_12am is not None, "claude_reset('Sep 8 at 12am (America/New_York)') returned None")

    assert_true(claude_reset("") is None, "claude_reset('') should be None")
    assert_true(claude_reset("invalid text") is None, "claude_reset('invalid text') should be None")

    # 2. The cache write writes the document and nothing to the Ledger, which
    #    records Runs only (decision C.2).
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = os.path.join(tmpdir, "ledger.jsonl")
        cache_path = os.path.join(tmpdir, "cache.json")
        os.environ["DELEGATE_LEDGER"] = ledger_path
        os.environ["DELEGATE_CACHE"] = cache_path

        now = time.time()
        doc = {
            "probed_at": now,
            "probed_at_iso": "2026-09-02T23:00:00+00:00",
            "gate": 0.1,
            "rollover_min": 30,
            "lanes": [
                {
                    "lane": "test-lane",
                    "harness": "agy",
                    "meter": "gemini",
                    "remaining_5h": 0.8,
                    "remaining_weekly": 0.9,
                    "r": 0.8,
                    "binding": "5h",
                    "reset_5h": 1788406804,
                    "reset_weekly": 1788616225,
                    "pace": 2.5,
                    "status": "ok",
                    "note": None,
                }
            ],
        }

        write_cache(doc, cache_path=cache_path)

        # Check cache written
        assert_true(os.path.exists(cache_path), f"cache file not found at {cache_path}")
        with open(cache_path) as f:
            loaded_doc = json.load(f)
        assert_true(loaded_doc == doc, "cache file content mismatch")
        assert_true(not os.path.exists(ledger_path), "the cache write appended to the Ledger")

        # 3. Test remaining_weekly_model on model meter lane and general lane
        l_fable = lane("claude", "fable", 0.58, 0.46, None, None, remaining_weekly_model=0.59)
        assert_true(l_fable.get("remaining_weekly_model") == 0.59, "l_fable remaining_weekly_model != 0.59")
        assert_true(l_fable.get("remaining_weekly") == 0.46, "l_fable remaining_weekly != 0.46")

        l_gen = lane("claude", "general", 0.58, 0.46, None, None)
        assert_true(l_gen.get("remaining_weekly_model") is None, "l_gen remaining_weekly_model is not None")

        doc_with_model = {
            "probed_at": now,
            "probed_at_iso": "2026-09-02T23:00:00+00:00",
            "gate": 0.1,
            "rollover_min": 30,
            "lanes": [l_fable, l_gen],
        }
        write_cache(doc_with_model, cache_path=cache_path)
        with open(cache_path) as f:
            written = json.load(f)
        assert_true(written["lanes"][0].get("remaining_weekly_model") == 0.59, "cache fable remaining_weekly_model mismatch")
        assert_true(written["lanes"][1].get("remaining_weekly_model") is None, "cache general remaining_weekly_model mismatch")
        assert_true(not os.path.exists(ledger_path), "the cache write appended to the Ledger")

        # 4. A cached read probes nothing: test_usage 9a, at usage.read.

    # 5. Cache path: DELEGATE_CACHE wins, else CONSULT_CACHE, else default.
    with tempfile.TemporaryDirectory() as tmpdir:
        delegate_path = os.path.join(tmpdir, "delegate.json")
        consult_path = os.path.join(tmpdir, "consult.json")
        os.environ["DELEGATE_CACHE"] = delegate_path
        os.environ["CONSULT_CACHE"] = consult_path
        assert_true(get_cache_path() == delegate_path, f"DELEGATE_CACHE should win, got {get_cache_path()}")
        del os.environ["DELEGATE_CACHE"]
        assert_true(get_cache_path() == consult_path, f"CONSULT_CACHE should apply, got {get_cache_path()}")
        del os.environ["CONSULT_CACHE"]
        assert_true(get_cache_path() == os.path.expanduser("~/.cache/delegate/usage.json"),
                    f"default cache path mismatch: {get_cache_path()}")

    # 6. The Gate predicate is Readout.gated: test_usage 5b, 5c, 5d and 5d2.

    # 7. An agy lane runs through the same arithmetic as every other Meter:
    #    Remaining is the lower Window, Pace comes from the weekly Window.
    l_agy = lane("agy", "gemini", 0.80, 0.90, 1788406804, 1788616225)
    l_codex = lane("codex", None, 0.80, 0.90, 1788406804, 1788616225)
    assert_true(l_agy["remaining_5h"] == 0.80 and l_agy["remaining_weekly"] == 0.90,
                "agy windows should remain visible")
    assert_true(l_agy["r"] == 0.80 and l_agy["binding"] == "5h" and l_agy["status"] == "ok",
                f"agy Remaining should be the lower window, got r={l_agy['r']}")
    assert_true(l_agy["pace"] is not None and l_agy["pace"] == l_codex["pace"],
                f"agy Pace should match the other Meters, got {l_agy['pace']}")
    derived = ("r", "binding", "reset_binding", "cycle_left", "pace", "score", "status")
    assert_true(all(l_agy[k] == l_codex[k] for k in derived),
                f"agy and codex should derive the same figures: {l_agy} vs {l_codex}")
    assert_true("assumption" in AGY_NOTE and "not a vendor bound" in AGY_NOTE,
                f"the agy note must call the combined figure an assumption: {AGY_NOTE}")

    # One Window missing: the documented fallback of the other Meters applies.
    for meter_name, five_h, weekly in (("gemini", None, 0.90), ("gemini", 0.80, None)):
        one_agy = lane("agy", meter_name, five_h, weekly, 1788406804, 1788616225)
        one_codex = lane("codex", None, five_h, weekly, 1788406804, 1788616225)
        assert_true(all(one_agy[k] == one_codex[k] for k in derived),
                    f"a one-window agy lane must fall back as codex does: {one_agy}")
    assert_true(lane("agy", "gemini", 0.80, None, 1788406804, None)["pace"] is None,
                "no weekly Window means no Pace, on agy as anywhere else")

    # A fresh agy probe carries the windows, the figures and the assumption note.
    from unittest.mock import patch
    class _R:
        returncode = 0
        stdout = json.dumps({"command": {"data": {"groups": [
            {"name": "Gemini", "buckets": [
                {"window": "5h", "remaining_fraction": 0.80, "reset_time": "2026-09-19T03:00:00Z"},
                {"window": "weekly", "remaining_fraction": 0.90, "reset_time": "2026-09-24T03:00:00Z"}]}]}}})
    with patch.object(harnesses.get("agy"), "installed", return_value=True), \
         patch.object(usage, "run", return_value=_R()):
        probed_agy = harnesses.get("agy").meters()
    assert_true(len(probed_agy) == 1 and probed_agy[0]["r"] == 0.80
                and probed_agy[0]["pace"] is not None,
                f"a fresh agy probe must give Remaining and Pace: {probed_agy}")
    assert_true(AGY_NOTE in (probed_agy[0].get("note") or ""),
                f"a fresh agy probe must carry the assumption note: {probed_agy[0].get('note')}")

    # 8. The legacy rows, derived figures, validity, FRESH's age and the probe
    #    bound are test_usage cases 3d to 3k, 4, 4b, 9 and 11, at usage.read
    #    and Snapshot.of. A probe's row still says nothing of a Gate:
    low = usage.meter_row("codex", None, 0.05, 0.06)
    assert_true(low["status"] == "ok", "observation status must not encode a private Gate")

    # A figure past 100% used reads as nothing left, not as a negative
    # fraction that would fail the whole document and turn every Gate off.
    over = usage.meter_row("claude", "general", -0.04, 0.7, remaining_weekly_model=1.2)
    assert_true(over["remaining_5h"] == 0.0 and over["r"] == 0.0
                and over["remaining_weekly_model"] == 1.0,
                f"remaining fractions must be held to 0..1: {over}")
    over_doc = {"probed_at": time.time(), "lanes": [over, usage.meter_row("codex", None, 0.05, 0.05)]}
    parsed = usage.Snapshot.of(over_doc)
    assert_true(parsed.status == "ok" and parsed.readout("codex", None).remaining == 0.05,
                "one overspent row must not unread every Meter")
    assert_true(usage.remaining(None) is None and usage.remaining(0.5) == 0.5,
                "a fraction inside 0..1, or none, is left as it is")

    # Ticket 43's hold is test_usage's case 2, at usage.hold, usage.release and usage.read.

    print("PASS: all test_usage_reset tests passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
