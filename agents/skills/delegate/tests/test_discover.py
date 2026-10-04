#!/usr/bin/env python3
"""test_discover.py — unit and CLI tests for discover.py. Run: python3 tests/test_discover.py"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so that
# `catalog.find_git_root()` never finds the invoking checkout's own
# `.delegate/routing.json`. Every path this file needs comes from HERE.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
DELEGATE_DIR = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES_DIR = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
FIXTURES_DIR = os.path.join(HERE, "fixtures", "discover")
DISCOVER_PY = os.path.join(DELEGATE_DIR, "discover.py")
CATALOG_PY = os.path.join(DELEGATE_DIR, "catalog_cli.py")
PRICE_KEY = '"price": {'

sys.path.insert(0, DELEGATE_DIR)
import bench
import carry
import catalog
import discover
import harnesses
from harnesses import agy as agy_module, grok as grok_module
import setup_tui

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


# -------------------------------------------------------------
# 1. Codex fixture parser: list visibility kept, hide visibility excluded
codex_fixture_path = os.path.join(FIXTURES_DIR, "codex-debug-models.json")
with open(codex_fixture_path, "r", encoding="utf-8") as f:
    codex_raw = f.read()

codex_models = harnesses.get("codex").parse_models(codex_raw)
codex_slugs = [m["slug"] for m in codex_models]
codex_ok = (
    codex_slugs == ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"]
    and "gpt-reserve" not in codex_slugs
    and "codex-auto-review" not in codex_slugs
    and all(m["display_name"] is not None for m in codex_models)
)
record("codex fixture parsing excludes hide visibility", codex_ok, f"slugs={codex_slugs}")


# -------------------------------------------------------------
# 2. AGY fixture parser: skips header, extracts slugs and display names
agy_fixture_path = os.path.join(FIXTURES_DIR, "agy-models.txt")
with open(agy_fixture_path, "r", encoding="utf-8") as f:
    agy_raw = f.read()

agy_models = agy_module.parse_listing(agy_raw)
agy_slugs = [m["slug"] for m in agy_models]
agy_ok = (
    len(agy_models) == 18
    and agy_models[0]["slug"] == "gemini-3.8-flash-high"
    and agy_models[0]["display_name"] == "Gemini 3.8 Flash (High)"
    and "claude-opus-5-5-high" in agy_slugs
    and "claude-sonnet-5-5-low" in agy_slugs
    and "gpt-oss-120b-medium" in agy_slugs
)
record("agy fixture parsing parses tabs", agy_ok, f"count={len(agy_models)}, slugs={agy_slugs[:3]}")

# agy no longer prints the header (the user's listing, 2026-10-03), but an older
# agy did, and the space-separated form is what the user pasted.
older = agy_module.parse_listing(
    "Fetching available models...\n"
    "claude-opus-5-5-low       Claude Opus 5.5 (Low)\n"
    "gemini-3.8-flash-high\tGemini 3.8 Flash (High)\n")
record(
    "agy listing skips the old header and reads space-separated lines",
    [m["slug"] for m in older] == ["claude-opus-5-5-low", "gemini-3.8-flash-high"]
    and older[0]["display_name"] == "Claude Opus 5.5 (Low)",
    repr(older),
)


# -------------------------------------------------------------
# 3. Grok fixture parser: strips bullets and (default) suffix
grok_fixture_path = os.path.join(FIXTURES_DIR, "grok-models.txt")
with open(grok_fixture_path, "r", encoding="utf-8") as f:
    grok_raw = f.read()

grok_models = grok_module.parse_listing(grok_raw)
grok_slugs = [m["slug"] for m in grok_models]
grok_ok = (
    grok_slugs == ["grok-4.6", "grok-4.5"]
    and not any(s.startswith("*") or s.startswith("-") for s in grok_slugs)
    and not any("(default)" in s for s in grok_slugs)
)
record("grok fixture parsing strips bullets and default suffix", grok_ok, f"slugs={grok_slugs}")


# -------------------------------------------------------------
# 4. Discovery with fixtures against sample catalog
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)
    cat = catalog.load_catalog(config_dir=cfg_dir)

    all_harnesses = {"claude", "codex", "agy", "grok"}
    res = discover.discover(cat, present=all_harnesses, fixture_dir=FIXTURES_DIR)

    # Codex checks
    codex_entry = res["harnesses"]["codex"]
    codex_status_ok = codex_entry["status"] == "ok" and codex_entry["discovered_count"] == 5

    # Claude checks: hand-named, undiscoverable
    claude_models = [m for m in res["models"] if m["harness"] == "claude"]
    claude_ok = (
        len(claude_models) == 1
        and claude_models[0]["slug"] == "claude-fable-5-1"
        and claude_models[0]["lane"] == "fable-xhigh@claude"
        and claude_models[0]["reason"] == "hand-named, undiscoverable"
    )

    # Sample catalog has:
    # sol-high@codex -> gpt-5.6-sol
    # terra-high@codex -> gpt-5.6-terra
    # luna-low@codex -> gpt-5.6-luna
    # flash-high@agy -> gemini-3.8-flash-high
    # grok46-high@grok -> grok-4.6
    # fable-xhigh@claude -> claude-fable-5-1
    # Note: gpt-6-astra and gpt-5.5 have no lane in sample lanes.json!
    # agy slugs are grouped into families (ticket 19): flash-high's lane maps
    # gemini-3.8-flash, so its -medium and -low slugs are no longer models
    # with no lane, and gemini-3.7-flash is one unmapped model, not three.
    unmapped_slugs = {(u["harness"], u["slug"]) for u in res["unmapped"]}
    unmapped_ok = (
        ("codex", "gpt-6-astra") in unmapped_slugs
        and ("codex", "gpt-5.5") in unmapped_slugs
        and ("grok", "grok-4.5") in unmapped_slugs
        and ("agy", "gemini-3.7-flash") in unmapped_slugs
        and not any(slug.startswith("gemini-3.8-flash") for _h, slug in unmapped_slugs)
        and ("codex", "gpt-5.6-sol") not in unmapped_slugs
        and ("grok", "grok-4.6") not in unmapped_slugs
    )

    # Retired should be empty with sample catalog (all sample lanes exist in fixtures)
    retired_ok = len(res["retired"]) == 0

    record("discover() full fixture evaluation against sample catalog", codex_status_ok and claude_ok and unmapped_ok and retired_ok,
           f"codex={codex_status_ok} claude={claude_models} unmapped={sorted(unmapped_slugs)} retired={res['retired']}")


# -------------------------------------------------------------
# 5. Retired slug tail: lane pointing to model that no longer appears in harness
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    with open(os.path.join(SAMPLES_DIR, "lanes.json"), "r", encoding="utf-8") as f:
        lanes_doc = json.load(f)

    # Add a lane pointing to a retired model
    lanes_doc["lanes"]["old-codex@codex"] = {
        "harness": "codex",
        "model": "gpt-old-retired",
        "effort": "high",
        "meter": "codex",
        "meter_weight": 10,
        "timeout": "30m",
        "price": {"in": 1, "cache_read": 0.1, "cache_write": None, "out": 2},
        "tier": 2,
        "basis": "retired test model",
    }
    catalog.write_json(os.path.join(cfg_dir, "lanes.json"), lanes_doc)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)

    cat_retired = catalog.load_catalog(config_dir=cfg_dir)
    res_retired = discover.discover(cat_retired, present={"codex"}, fixture_dir=FIXTURES_DIR)

    ret_lanes = [r["lane"] for r in res_retired["retired"]]
    ret_models = [r["model"] for r in res_retired["retired"]]
    retired_detected = (
        "old-codex@codex" in ret_lanes
        and "gpt-old-retired" in ret_models
    )
    record("retired slug tail detects unoffered lane model", retired_detected, f"retired={res_retired['retired']}")

    # Formatted report carries the retired line
    report = discover.format_report(res_retired)
    report_retired_ok = (
        "# lanes whose model no longer appears in harness" in report
        and "old-codex@codex" in report
        and "model: gpt-old-retired" in report
    )
    record("format_report prints retired lane line", report_retired_ok)


# -------------------------------------------------------------
# 6. Missing harness binary path: reported as missing, not an error and no crash
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)
    cat = catalog.load_catalog(config_dir=cfg_dir)

    # Only agy is present; codex, grok, claude are absent
    res_missing = discover.discover(cat, present={"agy"}, fixture_dir=FIXTURES_DIR)
    h_doc = res_missing["harnesses"]

    missing_ok = (
        h_doc["agy"]["status"] == "ok"
        and h_doc["codex"]["status"] == "missing"
        and h_doc["grok"]["status"] == "missing"
        and h_doc["claude"]["status"] == "missing"
        and h_doc["codex"]["error"] is None
    )
    record("missing harness binary reported as missing", missing_ok, f"statuses={[(k, v['status']) for k, v in h_doc.items()]}")

    report_missing = discover.format_report(res_missing)
    report_missing_ok = (
        "codex   missing" in report_missing
        and "grok    missing" in report_missing
        and "claude  missing" in report_missing
        and "gemini-3.8-flash " in report_missing
        and "lane: flash-high@agy" in report_missing
        and "efforts: low, medium, high" in report_missing
    )
    record("format_report prints missing harness line", report_missing_ok)


# -------------------------------------------------------------
# 7. All harnesses missing path: exits 0, reports missing, no crash
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)
    cat = catalog.load_catalog(config_dir=cfg_dir)

    res_all_missing = discover.discover(cat, present=set(), fixture_dir=FIXTURES_DIR)
    all_missing_ok = (
        all(v["status"] == "missing" for v in res_all_missing["harnesses"].values())
        and len(res_all_missing["models"]) == 0
        and len(res_all_missing["unmapped"]) == 0
        and len(res_all_missing["retired"]) == 0
    )
    record("all harnesses missing produces empty results with status missing", all_missing_ok)


# -------------------------------------------------------------
# 8. Failing/unparseable harness command: reports error, other harnesses continue
def faulty_runner(harness):
    if harness == "codex":
        raise RuntimeError("simulated crash in codex execution")
    elif harness == "agy":
        return "not valid json or tab format: [[["
    elif harness == "grok":
        with open(os.path.join(FIXTURES_DIR, "grok-models.txt"), "r", encoding="utf-8") as f:
            return f.read()
    return ""

with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)
    cat = catalog.load_catalog(config_dir=cfg_dir)

    res_faulty = discover.discover(cat, present={"codex", "agy", "grok"}, runner=faulty_runner)
    h_faulty = res_faulty["harnesses"]

    faulty_ok = (
        h_faulty["codex"]["status"] == "error"
        and "simulated crash" in h_faulty["codex"]["error"]
        and h_faulty["grok"]["status"] == "ok"
        and h_faulty["grok"]["discovered_count"] == 2
    )
    record("failing harness reports error line while others report", faulty_ok)


# -------------------------------------------------------------
# 9. CLI execution: plain text report with aligned columns and exit 0
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)

    res_cli = subprocess.run(
        [
            sys.executable, DISCOVER_PY,
            "--config-dir", cfg_dir,
            "--fixture-dir", FIXTURES_DIR,
            "--harnesses", "claude,codex,agy,grok",
        ],
        capture_output=True,
        text=True,
    )

    out = res_cli.stdout
    cli_ok = (
        res_cli.returncode == 0
        and "# models" in out
        and "# slugs with no lane" in out
        and "# lanes whose model no longer appears in harness" in out
        and "codex   gpt-6-astra" in out
        and "lane: none" in out
        and "codex   gpt-5.6-sol" in out
        and "lane: sol-high@codex" in out
        and "claude  claude-fable-5-1" in out
        and "lane: fable-xhigh@claude" in out
        and "(hand-named, undiscoverable)" in out
    )
    record("CLI plain text execution exits 0 and renders aligned report", cli_ok, f"rc={res_cli.returncode}, out={out[:200]}")


# -------------------------------------------------------------
# 10. CLI execution: --json emits valid JSON document matching schema
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)

    res_json = subprocess.run(
        [
            sys.executable, DISCOVER_PY,
            "--config-dir", cfg_dir,
            "--fixture-dir", FIXTURES_DIR,
            "--harnesses", "claude,codex,agy,grok",
            "--json",
        ],
        capture_output=True,
        text=True,
    )

    data = json.loads(res_json.stdout)
    top_keys = {"harnesses", "models", "unmapped", "retired"}
    model_keys = {"harness", "slug", "display_name", "lane", "lanes", "efforts", "unknown_efforts", "reason",
                  "level", "version", "superseded", "members"}
    json_ok = (
        res_json.returncode == 0
        and set(data.keys()) == top_keys
        and all(set(m.keys()) == model_keys for m in data["models"])
        # 5 codex + 7 agy families (14 slugs) + 2 grok + 1 claude
        and len(data["models"]) == 5 + 7 + 2 + 1
        and any(u["slug"] == "gpt-5.5" for u in data["unmapped"])
        and data["retired"] == []
    )
    record("CLI --json produces valid schema-compliant JSON document", json_ok, f"rc={res_json.returncode}")


# -------------------------------------------------------------
# 11. CLI execution: missing harness binary reported as missing
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "lanes.json"), cfg_dir)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)

    res_missing_cli = subprocess.run(
        [
            sys.executable, DISCOVER_PY,
            "--config-dir", cfg_dir,
            "--fixture-dir", FIXTURES_DIR,
            "--harnesses", "agy",
        ],
        capture_output=True,
        text=True,
    )

    out_missing = res_missing_cli.stdout
    missing_cli_ok = (
        res_missing_cli.returncode == 0
        and "codex   missing" in out_missing
        and "grok    missing" in out_missing
        and "claude  missing" in out_missing
        and "gemini-3.8-flash " in out_missing
        and "lane: flash-high@agy" in out_missing
    )
    record("CLI reports missing binary without error", missing_cli_ok, f"rc={res_missing_cli.returncode}")


# -------------------------------------------------------------
# 12. CLI execution: retired model tail in CLI output
with tempfile.TemporaryDirectory() as td:
    cfg_dir = os.path.join(td, "cfg")
    os.makedirs(cfg_dir)
    with open(os.path.join(SAMPLES_DIR, "lanes.json"), "r", encoding="utf-8") as f:
        lanes_doc = json.load(f)

    lanes_doc["lanes"]["retired-grok@grok"] = {
        "harness": "grok",
        "model": "grok-3.0-ancient",
        "effort": "high",
        "meter": "grok",
        "meter_weight": 1,
        "timeout": "30m",
        "price": {"in": 1, "cache_read": 0.1, "cache_write": None, "out": 2},
        "tier": 2,
        "basis": "ancient model test",
    }
    catalog.write_json(os.path.join(cfg_dir, "lanes.json"), lanes_doc)
    shutil.copy(os.path.join(SAMPLES_DIR, "routing.json"), cfg_dir)

    res_retired_cli = subprocess.run(
        [
            sys.executable, DISCOVER_PY,
            "--config-dir", cfg_dir,
            "--fixture-dir", FIXTURES_DIR,
            "--harnesses", "claude,codex,agy,grok",
        ],
        capture_output=True,
        text=True,
    )

    out_ret = res_retired_cli.stdout
    ret_cli_ok = (
        res_retired_cli.returncode == 0
        and "# lanes whose model no longer appears in harness" in out_ret
        and "retired-grok@grok" in out_ret
        and "model: grok-3.0-ancient" in out_ret
    )
    record("CLI reports retired model in tail", ret_cli_ok, f"rc={res_retired_cli.returncode}")


# -------------------------------------------------------------
# 18. ticket 19: effort lists for claude, grok and agy
with open(os.path.join(FIXTURES_DIR, "claude-help.txt"), encoding="utf-8") as f:
    claude_help = f.read()
record(
    "the claude --help fixture (Claude Code 2.1.269) parses to its five efforts, in order",
    harnesses.get("claude").efforts_from_help(claude_help) == ["low", "medium", "high", "xhigh", "max"]
    and harnesses.get("claude").efforts_from_help("  --effort <level>  Effort level\n  --other  x (a, b)") == []
    and harnesses.get("claude").efforts_from_help("") == [],
    repr(harnesses.get("claude").efforts_from_help(claude_help)),
)
claude_adapter = harnesses.get("claude")
record(
    "when claude --help lists no effort, or cannot be read, the adapter's efforts stand in",
    claude_adapter.help_efforts("  --effort <level>  Effort level\n", None)
    == (list(claude_adapter.efforts), [])
    and claude_adapter.help_efforts(None, "command failed") == (list(claude_adapter.efforts), [])
    and claude_adapter.help_efforts(claude_help, None)[0] == ["low", "medium", "high", "xhigh", "max"],
    repr(claude_adapter.help_efforts("", None)),
)
named, named_err, named_complete = claude_adapter.models(claude_help, None, {
    "fable-xhigh@claude": {"harness": "claude", "model": "claude-fable-5-1", "effort": "xhigh"},
    "fable-high@claude": {"harness": "claude", "model": "claude-fable-5-1", "effort": "high"},
    "haiku-high@claude": {"harness": "claude", "model": "claude-haiku-4-5-20251001", "effort": "high"},
})
record(
    "claude's models are the catalog's, one per model, Haiku with no effort, and never a complete list",
    named_err is None and named_complete is False
    and [m["slug"] for m in named] == ["claude-fable-5-1", "claude-haiku-4-5-20251001"]
    and named[0]["efforts"] == ["low", "medium", "high", "xhigh", "max"]
    and named[1]["efforts"] == [] and named[0]["reason"] == "hand-named, undiscoverable",
    repr(named),
)
res_no_efforts = subprocess.run(
    [sys.executable, DISCOVER_PY, "--fixture-dir", FIXTURES_DIR, "--efforts", "gpt-6-astra"],
    capture_output=True, text=True,
)
record(
    "discover.py has no --efforts: the wizard's refresh proposes a new model's lanes",
    res_no_efforts.returncode == 2 and "--efforts" in res_no_efforts.stderr,
    res_no_efforts.stderr[-200:],
)

families = harnesses.get("agy").group(agy_models)
by_slug = {f["slug"]: f for f in families}
record(
    "agy slugs group into one model per family with its efforts and member slugs",
    [f["slug"] for f in families] == ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
                                      "gemini-3.1-pro", "claude-opus-5-5",
                                      "claude-sonnet-5-5", "gpt-oss-120b"]
    and by_slug["gemini-3.8-flash"]["efforts"] == ["low", "medium", "high"]
    and by_slug["gemini-3.8-flash"]["members"]["medium"] == "gemini-3.8-flash-medium"
    and by_slug["gemini-3.8-flash"]["display_name"] == "Gemini 3.8 Flash"
    and by_slug["gemini-3.1-pro"]["efforts"] == ["low", "high"]
    and by_slug["claude-opus-5-5"]["efforts"] == ["low", "medium", "high"]
    and by_slug["claude-opus-5-5"]["members"]["high"] == "claude-opus-5-5-high"
    and by_slug["claude-opus-5-5"]["display_name"] == "Claude Opus 5.5"
    and discover.model_level("claude-opus-5-5-high", "agy") == ("claude-opus", (5, 5)),
    repr(families[:2]),
)

# -------------------------------------------------------------
# The refresh to the current generation (ticket 33). Every figure below comes
# from the fixtures captured on 2026-09-22 and from the catalog frozen beside
# them, never from the live catalog, which the refresh's own first run changes.

REFRESH_DIR = os.path.join(HERE, "fixtures", "refresh-2026-09-22")
with open(os.path.join(REFRESH_DIR, "lanes.json"), encoding="utf-8") as f:
    frozen_lanes = json.load(f)
with open(os.path.join(REFRESH_DIR, "aa-accepted.json"), encoding="utf-8") as f:
    frozen_rows = json.load(f)
published = sorted({r["model"] for r in frozen_rows if r.get("source") == "aa"})

levels = {slug: discover.model_level(slug, harness) for slug, harness in (
    ("gpt-6-sol", "codex"), ("gpt-5.6-sol", "codex"), ("claude-opus-5-5", "claude"),
    ("claude-opus-5", "claude"), ("grok-4.7", "grok"), ("grok-4.7-build-fast", "grok"),
    ("gemini-3.8-flash-high", "agy"), ("gemini-3.1-pro-low", "agy"),
)}
record(
    "a model's level is its slug without the version",
    levels["gpt-6-sol"] == ("gpt-sol", (6,))
    and levels["gpt-5.6-sol"] == ("gpt-sol", (5, 6))
    and levels["claude-opus-5-5"] == ("claude-opus", (5, 5))
    and levels["claude-opus-5"] == ("claude-opus", (5,))
    and levels["grok-4.7"] == ("grok", (4, 7))
    and levels["grok-4.7-build-fast"] == ("grok-build-fast", (4, 7))
    # the agy effort suffix comes off first, so one family has one level
    and levels["gemini-3.8-flash-high"] == ("gemini-flash", (3, 8))
    and levels["gemini-3.1-pro-low"] == ("gemini-pro", (3, 1)),
    repr(levels),
)

with open(os.path.join(REFRESH_DIR, "codex-debug-models.json"), encoding="utf-8") as f:
    codex_generation = discover.mark_generation(harnesses.get("codex").parse_models(f.read()), "codex")
by_slug = {m["slug"]: m for m in codex_generation}
record(
    "superseded is the harness's own word or a higher version of the level",
    bool(by_slug["gpt-5.5"]["superseded"]) and "gpt-5.6-sol" in by_slug["gpt-5.5"]["superseded"]
    and by_slug["gpt-5.6-sol"]["superseded"] == "gpt-6-sol is newer"
    and by_slug["gpt-5.6-luna"]["superseded"] == "gpt-6-luna is newer"
    and by_slug["gpt-6-sol"]["superseded"] is None
    and by_slug["gpt-6-astra"]["superseded"] is None
    # nothing newer is listed for terra, so it is the current generation
    and by_slug["gpt-5.6-terra"]["superseded"] is None,
    repr({s: m["superseded"] for s, m in by_slug.items()}),
)

stems = {
    "sol6": discover.lane_stem("gpt-sol", (6,), {"gpt-sol", "gpt-luna", "gpt-astra"}),
    "luna6": discover.lane_stem("gpt-luna", (6,), {"gpt-sol", "gpt-luna"}),
    "opus55": discover.lane_stem("claude-opus", (5, 5), {"claude-opus", "claude-sonnet"}),
    "grok47": discover.lane_stem("grok", (4, 7), {"grok", "grok-build-fast"}),
    "grok47fast": discover.lane_stem("grok-build-fast", (4, 7), {"grok", "grok-build-fast"}),
    "pro31": discover.lane_stem("gemini-pro", (3, 1), {"gemini-flash", "gemini-pro"}),
}
record(
    "a new lane's name is the level's word and the version's digits",
    all(expected == found for expected, found in stems.items()),
    repr(stems),
)

refresh_discovery = discover.discover(frozen_lanes, fixture_dir=REFRESH_DIR)
refreshed, plan = discover.refresh_catalog(
    frozen_lanes, refresh_discovery, published_models=published
)
expected_new = [
    "sol6-low@codex", "sol6-medium@codex", "sol6-high@codex", "sol6-xhigh@codex",
    "sol6-max@codex", "sol6-ultra@codex",
    "luna6-low@codex", "luna6-medium@codex", "luna6-high@codex", "luna6-xhigh@codex",
    "luna6-max@codex",
    "pro31-low@agy", "pro31-high@agy",
    "grok47-high@grok", "grok47fast-high@grok",
    "opus55-low@claude", "opus55-medium@claude", "opus55-high@claude",
    "opus55-xhigh@claude", "opus55-max@claude",
]
expected_removed = sorted(
    [f"sol-{e}@codex" for e in ("low", "medium", "high", "xhigh", "max", "ultra")]
    + [f"luna-{e}@codex" for e in ("low", "medium", "high", "xhigh", "max")]
    + [f"opus-{e}@claude" for e in ("low", "medium", "high", "xhigh", "max")]
    + ["grok46-high@grok"]
)
record(
    "the refresh proposes the current generation of every harness",
    sorted(plan["new"]) == sorted(expected_new) and plan["removed"] == expected_removed,
    f"new={sorted(plan['new'])} removed={plan['removed']}",
)

untouched = ([f"astra-{e}@codex" for e in ("low", "medium", "high", "xhigh", "max", "ultra")]
             + [f"terra-{e}@codex" for e in ("low", "medium", "high", "xhigh", "max", "ultra")]
             + ["flash-low@agy", "flash-medium@agy", "flash-high@agy", "haiku-high@claude"]
             + [f"fable-{e}@claude" for e in ("low", "medium", "high", "xhigh", "max")]
             + [f"sonnet-{e}@claude" for e in ("low", "medium", "high", "xhigh", "max")])
record(
    "a current-generation lane the catalog already has keeps every field",
    all(refreshed["lanes"].get(name) == frozen_lanes["lanes"][name] for name in untouched),
    repr([name for name in untouched
          if refreshed["lanes"].get(name) != frozen_lanes["lanes"][name]]),
)

not_shown = ("gpt-5.5", "gemini-3.7-flash", "gemini-3.6-flash", "grok-4.6", "grok-4.5",
             "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gpt-oss-120b",
             "gpt-reserve", "codex-auto-review")
proposed_models = {refreshed["lanes"][name]["model"] for name in plan["new"]}
record(
    "a superseded, other-vendor or hidden model gets no lane",
    not any(model.startswith(slug) for slug in not_shown for model in proposed_models),
    repr(sorted(proposed_models)),
)

inherited = []
for successor, predecessor in (("sol6-high@codex", "sol-high@codex"),
                               ("sol6-ultra@codex", "sol-ultra@codex"),
                               ("luna6-max@codex", "luna-max@codex"),
                               ("opus55-low@claude", "opus-low@claude"),
                               ("grok47-high@grok", "grok46-high@grok")):
    new, old = refreshed["lanes"][successor], frozen_lanes["lanes"][predecessor]
    inherited.append(
        new["tier"] == old["tier"]
        and new.get("order") == old.get("order")
        and (new["meter"], new["meter_weight"], new["timeout"])
        == (old["meter"], old["meter_weight"], old["timeout"])
        and predecessor in new["note"] and "UNMEASURED" in new["note"]
    )
record(
    "a successor takes its predecessor's place and says what it copied",
    all(inherited),
    repr(inherited),
)

new_records = [refreshed["lanes"][name] for name in plan["new"]]
record(
    "every new lane is unpriced, and an ultra lane is generated off",
    all(lane["price"] == {"in": None, "cache_read": None, "cache_write": None, "out": None}
        and "UNPRICED" in lane["note"] for lane in new_records)
    and all(lane.get("enabled") is False
            for lane in new_records if lane["effort"] == "ultra"),
    repr([lane for lane in new_records if lane["effort"] == "ultra"]),
)

# A predecessor switched off at an effort is a verdict on that model, not on the
# one replacing it: every effort of a new model reaches the screening page, and
# only ultra starts off (ticket 35).
off_predecessors = [name for name in ("opus-low@claude", "opus-medium@claude",
                                      "sol-low@codex", "luna-low@codex")
                    if frozen_lanes["lanes"][name].get("enabled") is False]
started_off = [name for name in plan["new"] if refreshed["lanes"][name].get("enabled") is False]
record(
    "every new lane starts carried but ultra, keeping its predecessor's tier and order",
    len(off_predecessors) == 4
    and started_off == ["sol6-ultra@codex"]
    and all("enabled" not in refreshed["lanes"][name]
            for name in plan["new"] if refreshed["lanes"][name]["effort"] != "ultra")
    and refreshed["lanes"]["opus55-medium@claude"]["tier"]
    == frozen_lanes["lanes"]["opus-medium@claude"]["tier"],
    repr(started_off),
)

# The carry page's "off in the catalog" is a claim about the file, so no new
# lane may make it: a new lane records no `enabled` at all, and ultra reads as
# ultra (ticket 35).
new_reasons = {name: bench.carry_reason(decision)
               for name, decision in carry.decisions(refreshed, frozen_rows).items()
               if name in set(plan["new"])}
record(
    "no new lane's carry reason claims catalog state the file does not hold",
    not any("in the catalog" in reason for reason in new_reasons.values())
    and new_reasons["sol6-ultra@codex"] == bench.ULTRA_REASON,
    repr(sorted(set(new_reasons.values()))),
)

record(
    "a lane with no predecessor starts carried on tier 1 and copies its harness",
    refreshed["lanes"]["pro31-high@agy"]["tier"] == 1
    and "enabled" not in refreshed["lanes"]["pro31-high@agy"]
    and refreshed["lanes"]["pro31-high@agy"]["meter"] == "agy-gemini"
    and "flash-high@agy" in refreshed["lanes"]["pro31-high@agy"]["note"]
    and refreshed["lanes"]["grok47fast-high@grok"]["tier"] == 1,
    repr(refreshed["lanes"]["pro31-high@agy"]),
)

catalog.validate_lanes(copy.deepcopy(refreshed), "refreshed")
again_discovery = discover.discover(refreshed, fixture_dir=REFRESH_DIR)
again, again_plan = discover.refresh_catalog(
    refreshed, again_discovery, published_models=published
)
record(
    "a second refresh on the saved catalog proposes nothing",
    again_plan["new"] == [] and again_plan["removed"] == [] and again == refreshed,
    repr(again_plan),
)

remapped = discover.map_lanes(refresh_discovery, refreshed)
adopted = {m["slug"] for m in remapped["models"] if m["lanes"]}
record(
    "the drift notices read the refreshed catalog, not the one on disk",
    {"gpt-6-sol", "gpt-6-luna", "grok-4.7", "gemini-3.1-pro"} <= adopted
    and not any(u["slug"] in ("gpt-6-sol", "grok-4.7") for u in remapped["unmapped"])
    and remapped["retired"] == [],
    repr(sorted(adopted)),
)

# A model with no lane is worth naming only where the refresh would have given
# it one. A superseded model, another vendor's model on agy and a hidden model
# are not shown. The 2026-09-22 listing's Opus 4.6 Thinking is agy's own since
# any-harness ticket 31, and its slug names no effort, so no lane can be made
# for it and the notice says so; nothing else is named.
record(
    "the models-with-no-lane notice names only the harnesses' own models",
    [u["slug"] for u in remapped["unmapped"]] == ["claude-opus-4-6-thinking"]
    # the fixture machine has no Kiro CLI, which is the other thing worth saying
    and setup_tui.discovery_notices(remapped, 10_000)
    == ["Harness kiro: missing", "Models with no lane: agy claude-opus-4-6-thinking"],
    repr(setup_tui.discovery_notices(remapped, 10_000)),
)

# A current-generation model of the harness's own vendor that really has no lane
# is still named: that is the notice doing its job.
no_lanes = copy.deepcopy(refreshed)
for name in [n for n, lane in no_lanes["lanes"].items() if lane["model"].startswith("gpt-6-sol")]:
    del no_lanes["lanes"][name]
still_named = [u["slug"] for u in discover.map_lanes(refresh_discovery, no_lanes)["unmapped"]]
record(
    "a current-generation model that truly has no lane is still named",
    still_named == ["gpt-6-sol", "claude-opus-4-6-thinking"],
    repr(still_named),
)


# --- refresh robustness: listing order, no-effort successors, dates, effort words

def refresh_with(edit, extra_published=()):
    """The refresh of the frozen catalog against a copy of the frozen fixtures
    that `edit(directory)` changed: (discovery, refreshed catalog, plan)."""
    with tempfile.TemporaryDirectory() as d:
        fixtures = os.path.join(d, "fixtures")
        shutil.copytree(REFRESH_DIR, fixtures)
        edit(fixtures)
        found = discover.discover(copy.deepcopy(frozen_lanes), fixture_dir=fixtures)
    doc, made = discover.refresh_catalog(copy.deepcopy(frozen_lanes), found,
                                         published_models=published + list(extra_published))
    return found, doc, made


def valid_or_error(doc):
    try:
        catalog.validate_lanes(copy.deepcopy(doc), "refreshed")
        return True
    except catalog.CatalogError as e:
        return repr(e)


def agy_listing(where):
    """Lists gemini-3.9-flash at the top or the bottom of `agy models`."""
    def edit(fixtures):
        path = os.path.join(fixtures, "agy-models.txt")
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        new = [f"gemini-3.9-flash-{e}\tGemini 3.9 Flash ({e.title()})" for e in ("high", "medium", "low")]
        lines = lines[:1] + new + lines[1:] if where == "top" else lines + new
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return edit


_, top_doc, _ = refresh_with(agy_listing("top"))
_, bottom_doc, _ = refresh_with(agy_listing("bottom"))
top_agy = sorted(n for n, lane in top_doc["lanes"].items() if lane["harness"] == "agy")
bottom_agy = sorted(n for n, lane in bottom_doc["lanes"].items() if lane["harness"] == "agy")
record(
    "a new level gets its lanes whether agy lists it before or after the only successor",
    top_agy == bottom_agy
    and {"pro31-low@agy", "pro31-high@agy", "flash39-high@agy"} <= set(bottom_agy)
    and not any(n.startswith("flash-") for n in bottom_agy),
    f"top={top_agy} bottom={bottom_agy}",
)


def codex_add(*models):
    def edit(fixtures):
        path = os.path.join(fixtures, "codex-debug-models.json")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        for slug, efforts in models:
            doc["models"].append({"slug": slug, "display_name": slug, "visibility": "list",
                                  "supported_reasoning_levels": [{"effort": e} for e in efforts]})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f)
    return edit


_, haiku_doc, haiku_plan = refresh_with(lambda d: None, extra_published=["Claude Haiku 5"])
haiku = {n: lane for n, lane in haiku_doc["lanes"].items() if "haiku" in lane["model"]}
record(
    "a successor that takes no effort level takes its predecessor's place in one lane",
    list(haiku) == ["haiku5-high@claude"]
    and haiku["haiku5-high@claude"]["model"] == "claude-haiku-5"
    and haiku["haiku5-high@claude"]["tier"] == frozen_lanes["lanes"]["haiku-high@claude"]["tier"]
    and "haiku-high@claude" in haiku_plan["removed"]
    and valid_or_error(haiku_doc) is True,
    f"{sorted(haiku)} {valid_or_error(haiku_doc)}",
)

dated = {slug: discover.model_level(slug, harness) for slug, harness in (
    ("gpt-6-sol-2026-11-01", "codex"), ("gpt-6-sol-20261101", "codex"),
    ("claude-haiku-4-5-20251001", "claude"))}
_, dated_doc, dated_plan = refresh_with(codex_add(("gpt-6-sol-2026-11-01", ["high"]),
                                                  ("gpt-6.1-sol", ["high"])))
record(
    "a trailing date stamps a snapshot and is no part of the version",
    dated == {"gpt-6-sol-2026-11-01": ("gpt-sol", (6,)), "gpt-6-sol-20261101": ("gpt-sol", (6,)),
              "claude-haiku-4-5-20251001": ("claude-haiku", (4, 5))}
    and [m["model"] for m in dated_plan["models"] if m["harness"] == "codex" and "sol" in m["model"]]
    == ["gpt-6.1-sol"],
    f"{dated} {[m['model'] for m in dated_plan['models']]}",
)

_, extreme_doc, extreme_plan = refresh_with(
    codex_add(("gpt-6.1-sol", ["low", "medium", "high", "xhigh", "max", "extreme"])))
record(
    "an effort word delegate does not know gets a notice, not a lane",
    not any(lane["effort"] == "extreme" for lane in extreme_doc["lanes"].values())
    and "sol61-high@codex" in extreme_doc["lanes"]
    and extreme_plan["notices"]
    == ["codex lists effort 'extreme' for gpt-6.1-sol; delegate does not know it yet"]
    and valid_or_error(extreme_doc) is True
    and any("delegate does not know it yet" in line
            for line in setup_tui.refresh_lines(extreme_plan, 10_000)),
    f"{extreme_plan['notices']} {valid_or_error(extreme_doc)}",
)


def claude_help_extreme(fixtures):
    with open(os.path.join(fixtures, "claude-help.txt"), "w", encoding="utf-8") as f:
        f.write("  --effort <level>  Effort level for the current session\n"
                "                    (low, medium, high, xhigh, max, extreme)\n  --other  x\n")


claude_found, claude_doc, claude_plan = refresh_with(claude_help_extreme)
claude_models = [m for m in claude_found["models"] if m["harness"] == "claude"]
record(
    "claude --help naming an unknown effort is reported, and its efforts stay the known ones",
    all("extreme" not in m["efforts"] for m in claude_models)
    and any("claude lists effort 'extreme' for claude-opus-5-5" in n for n in claude_plan["notices"])
    and valid_or_error(claude_doc) is True,
    repr(claude_plan["notices"]),
)


def agy_xhigh(fixtures):
    with open(os.path.join(fixtures, "agy-models.txt"), "a", encoding="utf-8") as f:
        f.write("gemini-3.8-flash-xhigh\tGemini 3.8 Flash (Xhigh)\n")


xhigh_found, xhigh_doc, _ = refresh_with(agy_xhigh)
record(
    "agy listing an -xhigh slug adds an xhigh lane to the family, which the catalog accepts",
    not any(m["slug"] == "gemini-3.8-flash-xhigh" for m in xhigh_found["models"])
    and any(lane["model"] == "gemini-3.8-flash-xhigh" and lane["effort"] == "xhigh"
            for lane in xhigh_doc["lanes"].values())
    and valid_or_error(xhigh_doc) is True,
    f"{valid_or_error(xhigh_doc)}",
)


# any-harness ticket 31: agy serves Opus 5.5 on the pool it shares with Sonnet
# and GPT-OSS, which `/usage` reports as its second group. The refresh offers
# Opus and nothing else of another vendor's, and puts it on that pool's Meter.
def agy_listing_2026_10_03(fixtures):
    shutil.copy(agy_fixture_path, os.path.join(fixtures, "agy-models.txt"))


opus_found, opus_doc, opus_plan = refresh_with(agy_listing_2026_10_03)
opus_lanes = {name: lane for name, lane in opus_doc["lanes"].items()
              if lane["harness"] == "agy" and lane["model"].startswith("claude-")}
record(
    "the refresh proposes an agy Lane on Opus only, on the agy-claude-gpt Meter",
    sorted(opus_lanes) == ["opus55-high@agy", "opus55-low@agy", "opus55-medium@agy"]
    and {lane["model"] for lane in opus_lanes.values()}
    == {"claude-opus-5-5-low", "claude-opus-5-5-medium", "claude-opus-5-5-high"}
    and all(lane["meter"] == "agy-claude-gpt" for lane in opus_lanes.values())
    and not any(lane["model"].startswith(("claude-sonnet", "gpt-oss"))
                for lane in opus_doc["lanes"].values() if lane["harness"] == "agy")
    and valid_or_error(opus_doc) is True,
    repr({name: lane["meter"] for name, lane in opus_lanes.items()}),
)
added_meter = opus_doc["meters"].get("agy-claude-gpt") or {}
record(
    "the refresh adds the agy-claude-gpt Meter on agy's plan when the catalog lacks it",
    "agy-claude-gpt" not in frozen_lanes["meters"]
    and added_meter.get("harness") == "agy"
    and added_meter.get("plan") == frozen_lanes["meters"]["agy-gemini"]["plan"]
    and "UNMEASURED" in added_meter.get("note", ""),
    repr(added_meter),
)
record(
    "a Gemini lane stays on agy-gemini beside an Opus lane at the same effort",
    opus_doc["lanes"]["pro31-high@agy"]["meter"] == "agy-gemini"
    and opus_doc["lanes"]["pro31-low@agy"]["meter"] == "agy-gemini",
    repr(opus_doc["lanes"]["pro31-high@agy"]),
)
with tempfile.TemporaryDirectory() as d:
    shutil.copytree(REFRESH_DIR, os.path.join(d, "f"))
    agy_listing_2026_10_03(os.path.join(d, "f"))
    opus_again_found = discover.discover(copy.deepcopy(opus_doc), fixture_dir=os.path.join(d, "f"))
_again, opus_again_plan = discover.refresh_catalog(opus_doc, opus_again_found,
                                                   published_models=published)
record(
    "a second refresh after the Opus lanes proposes nothing more on agy",
    not any(name.endswith("@agy") for name in opus_again_plan["new"]),
    repr(opus_again_plan["new"]),
)

sys.exit(1 if fails else 0)
