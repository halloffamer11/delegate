#!/usr/bin/env python3
"""Black-box tests for setup.py. Run: python3 tests/test_setup.py"""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so that
# `catalog.find_git_root()` never finds the invoking checkout's own
# `.delegate/routing.json`. Every path this file needs comes from HERE.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
# the wizard reads and empties dispatch's model queue (ticket 29): never the real one
os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(_ISOLATED_CWD.name, "new-models.json")
os.environ["DELEGATE_MODEL_SCAN"] = "off"
DELEGATE_DIR = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SETUP_PY = os.path.join(DELEGATE_DIR, "setup.py")
SAMPLES_DIR = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))

sys.path.insert(0, DELEGATE_DIR)
import catalog
import harnesses
import catalog_edit
import catalog_commit  # noqa: E402

fails = 0
lanes_sample = catalog.load_json(os.path.join(SAMPLES_DIR, "lanes.json"))
routing_sample = catalog.load_json(os.path.join(SAMPLES_DIR, "routing.json"))


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def discovered(keys):
    return {
        "version": "delegate-discover.v1",
        "discovered": [
            {
                "key": key,
                "binary": key,
                "version": f"{key} test version",
                "path": f"/test/{key}",
                "authenticated": True,
                "models": {"status": "reported", "values": []},
            }
            for key in keys
        ],
        "missing": [],
    }


def write_discover(path, keys):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(discovered(keys), f)


def run_setup(config_dir, discover_path, answers, *extra):
    return subprocess.run(
        [
            sys.executable,
            SETUP_PY,
            "--config-dir",
            config_dir,
            "--discover-json",
            discover_path,
            # model discovery shells out to the real harness CLIs; these cases
            # are about the prompts, and the facts case below drives fixtures
            "--no-discover",
            *extra,
        ],
        input=answers,
        capture_output=True,
        text=True,
        cwd=DELEGATE_DIR,
    )


def default_answers(lane_count):
    # one blank per lane (tier), plus one for the "keep routing as shown?" prompt
    return "\n" * (lane_count + 1) + "y\n"


def load_written(config_dir):
    lanes_path = os.path.join(config_dir, "lanes.json")
    routing_path = os.path.join(config_dir, "routing.json")
    return catalog.load_json(lanes_path), catalog.load_json(routing_path)


def sample_proposal(harnesses):
    doc = copy.deepcopy(lanes_sample)
    doc["lanes"] = {
        name: lane for name, lane in doc["lanes"].items()
        if lane["harness"] in harnesses
    }
    used = {lane["meter"] for lane in doc["lanes"].values()}
    doc["meters"] = {
        name: meter for name, meter in doc["meters"].items() if name in used
    }
    return doc


def case_all_harnesses_write_canonical_samples():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(cfg, discover_path, default_answers(len(lanes_sample["lanes"])), "--no-bench")
        lanes, routing = load_written(cfg)
        canonical = (
            open(os.path.join(cfg, "lanes.json"), "rb").read()
            == catalog.format_json(lanes).encode("utf-8")
            and open(os.path.join(cfg, "routing.json"), "rb").read()
            == catalog.format_json(routing).encode("utf-8")
        )
        expected = sample_proposal(harnesses.NAMES)
        all_sample_values = all(
            lanes["lanes"][name]["tier"] == sample["tier"]
            for name, sample in lanes_sample["lanes"].items()
        )
        catalog.check_file(os.path.join(cfg, "lanes.json"))
        catalog.check_file(os.path.join(cfg, "routing.json"))
        return (
            result.returncode == 0
            and lanes == expected
            and routing == routing_sample
            and canonical
            and all_sample_values,
            f"code={result.returncode}, lanes={lanes == expected}, routing={routing == routing_sample}, canonical={canonical}, values={all_sample_values}, stderr={result.stderr!r}",
        )


def case_subset_filters_lanes_and_meters():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, ("agy", "grok"))
        result = run_setup(cfg, discover_path, default_answers(2), "--no-bench")
        lanes, _routing = load_written(cfg)
        wanted_lanes = {"flash-high@agy", "grok46-high@grok"}
        wanted_meters = {"agy-gemini", "grok"}
        return (
            result.returncode == 0
            and set(lanes["lanes"]) == wanted_lanes
            and set(lanes["meters"]) == wanted_meters
            and "terra-high@codex" not in lanes["lanes"]
            and "sol-high@codex" not in lanes["lanes"],
            f"code={result.returncode}, lanes={lanes['lanes'].keys()}",
        )


def case_existing_values_are_prompt_defaults():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        os.makedirs(cfg)
        existing = copy.deepcopy(lanes_sample)
        existing["lanes"]["terra-high@codex"]["tier"] = 3
        catalog.write_json(os.path.join(cfg, "lanes.json"), existing)
        catalog.write_json(os.path.join(cfg, "routing.json"), routing_sample)
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(cfg, discover_path, default_answers(6), "--no-bench")
        lanes, _routing = load_written(cfg)
        return (
            result.returncode == 0
            and "tier [3]:" in result.stdout
            and lanes["lanes"]["terra-high@codex"]["tier"] == 3,
            f"code={result.returncode}, stdout={result.stdout!r}",
        )


def case_one_lane_values_change_only_that_lane():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        answers = "4\n" + "\n" * 6 + "y\n"
        result = run_setup(cfg, discover_path, answers, "--no-bench")
        lanes, _routing = load_written(cfg)
        changed = sample_proposal(harnesses.NAMES)
        changed["lanes"]["fable-xhigh@claude"]["tier"] = 4
        return lanes == changed and result.returncode == 0, f"code={result.returncode}, lanes={lanes == changed}"


def case_bench_report_is_display_only():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        report_path = os.path.join(td, "bench.md")
        write_discover(discover_path, harnesses.NAMES)
        report_text = "terra-high@codex tier 1\nfixture benchmark report\n"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        result = run_setup(
            cfg,
            discover_path,
            default_answers(6),
            "--bench-report",
            report_path,
        )
        first_prompt = result.stdout.find("tier [")
        return (
            result.returncode == 0
            and result.stdout.find(report_text) != -1
            and result.stdout.find(report_text) < first_prompt
            and "tier [2]:" in result.stdout,
            f"code={result.returncode}, stdout={result.stdout!r}",
        )


def case_decline_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        answers = "\n" * 13 + "n\n"
        result = run_setup(cfg, discover_path, answers, "--no-bench")
        return (
            result.returncode == 0
            and not os.path.exists(os.path.join(cfg, "lanes.json"))
            and not os.path.exists(os.path.join(cfg, "routing.json"))
            and result.stdout.rstrip().endswith("nothing written"),
            f"code={result.returncode}, stdout={result.stdout!r}",
        )


def case_out_of_range_retries_then_writes_value():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        answers = "9\n3\n" + "\n" * 6 + "y\n"
        result = run_setup(cfg, discover_path, answers, "--no-bench")
        lanes, _routing = load_written(cfg)
        return (
            result.returncode == 0
            and lanes["lanes"]["fable-xhigh@claude"]["tier"] == 3
            and result.stdout.count("tier must be an integer from 1 to 4") == 1,
            f"code={result.returncode}, stdout={result.stdout!r}",
        )


def case_eof_aborts_without_writing():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(cfg, discover_path, "", "--no-bench")
        return (
            result.returncode == 130
            and not os.path.exists(os.path.join(cfg, "lanes.json"))
            and not os.path.exists(os.path.join(cfg, "routing.json")),
            f"code={result.returncode}, stdout={result.stdout!r}",
        )


def case_routing_edits_keep_other_classes():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        answers = "\n" * 6 + "n\n" + "\n" * 6 + "3\n3\n" + "\n" * 2 + "0.3\n\n\n" + "y\n"
        result = run_setup(cfg, discover_path, answers, "--no-bench")
        _lanes, routing = load_written(cfg)
        unchanged = all(
            routing["classes"][name] == routing_sample["classes"][name]
            for name in catalog.CLASSES
            if name != "review"
        )
        return (
            result.returncode == 0
            and routing["classes"]["review"] == {"floor": 3, "ceiling": 3}
            and routing["margin"] == 0.3
            and unchanged,
            f"code={result.returncode}, routing={routing}",
        )


def case_effort_rows_says_the_prompt_interface_has_no_prescreen():
    """--effort-rows is TUI-only. A pipe or --plain reads it and does nothing
    with it, and the instruction a human is handed names the flag, so silence
    would read as "the pre-screen ran and proposed nothing off"."""
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        rows_path = os.path.join(td, "rows.json")
        with open(rows_path, "w", encoding="utf-8") as f:
            json.dump([{"source": "t", "model": "gpt-5.6-luna", "effort": "low",
                        "benchmark": "b", "score": 4.0, "cost_usd": 1.7,
                        "uncertain": False}], f)
        result = run_setup(cfg, discover_path, default_answers(len(lanes_sample["lanes"])),
                           "--no-bench", "--effort-rows", rows_path)
        said = "--effort-rows" in result.stdout and "pre-screen" in result.stdout
        wrote = os.path.isfile(os.path.join(cfg, "lanes.json"))
        lanes, _routing = load_written(cfg)
        untouched = all("enabled" not in lane for lane in lanes["lanes"].values())
        return (said and wrote and untouched,
                f"said={said} wrote={wrote} untouched={untouched} stdout={result.stdout[:300]!r}")


def case_effort_rows_from_several_files_combine():
    """--effort-rows may be repeated, so two sources share one benchmark page.
    Every file's rows arrive in order, and a bad file is named, not skipped."""
    import setup
    row = {"source": "t", "model": "gpt-5.6-luna", "effort": "low", "benchmark": "b",
           "score": 4.0, "cost_usd": 1.7, "uncertain": False}
    with tempfile.TemporaryDirectory() as td:
        paths = []
        for i, source in enumerate(("aa", "tbench")):
            paths.append(os.path.join(td, f"rows{i}.json"))
            with open(paths[-1], "w", encoding="utf-8") as f:
                json.dump([dict(row, source=source)], f)
        bad = os.path.join(td, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            json.dump({"not": "a list"}, f)
        rows, message = setup.load_effort_rows(paths)
        one, _ = setup.load_effort_rows(paths[0])
        refused, why = setup.load_effort_rows([paths[0], bad])
    ok = ([r["source"] for r in rows] == ["aa", "tbench"] and message == ""
          and [r["source"] for r in one] == ["aa"]
          and refused is None and bad in why and "expected a JSON list" in why)
    return ok, f"rows={rows} message={message!r} refused={refused} why={why!r}"


def case_plain_prints_the_start_facts():
    """--plain prints what the TUI's start page shows, from the same function:
    both output paths, the benchmark page line, where the benchmark rows came
    from, what the refresh proposes and the discovery notices, before the first
    prompt, and no definition of a term (tickets 25 and 33)."""
    import discover
    import setup
    import setup_tui
    fixture_dir = os.path.join(HERE, "fixtures", "discover")
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        saved = discover.discover(sample_proposal(harnesses.NAMES), fixture_dir=fixture_dir)
        catalog.write_json(discover_path, saved)
        # the same refresh the wizard runs, so the facts are the same facts
        refreshed, refresh = discover.refresh_catalog(
            sample_proposal(harnesses.NAMES), saved
        )
        _paths, rows_note = setup.refresh_effort_rows(None, fixture_dir=fixture_dir)
        result = subprocess.run(
            [sys.executable, SETUP_PY, "--config-dir", cfg, "--discover-json", discover_path,
             "--fixture-dir", fixture_dir, "--no-bench", "--plain"],
            input=default_answers(len(refreshed["lanes"])), capture_output=True, text=True,
            cwd=DELEGATE_DIR)
        facts = setup_tui.start_facts(os.path.join(cfg, "lanes.json"), os.path.join(cfg, "routing.json"),
                                      None, discover.map_lanes(saved, refreshed), width=10_000,
                                      refresh=refresh, rows_note=rows_note)
        first_prompt = result.stdout.find("tier [")
        positions = [result.stdout.find(line) for line in facts]
        ok = (result.returncode == 0 and len(facts) >= 4
              and all(0 <= p < first_prompt for p in positions)
              and "Benchmark page: (not written)" in result.stdout
              and any(line.startswith(("Model discovery", "Models with no lane", "Lanes with retired", "Harness "))
                      for line in facts)
              and "Tier is capability" not in result.stdout)
        return ok, f"facts={facts} positions={positions} stdout={result.stdout[:500]!r}"


def case_tiers_from_applies_the_page_lines():
    """--tiers-from applies the benchmark page's lines with the review page's
    parser: a tier line becomes the lane's tier, an off line writes it off, a
    carried lane no line names is written off, the lines' order inside a tier is
    the order written, and the summary line is printed before the first prompt
    (tickets 27 and 28)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        lines = os.path.join(td, "tiers.txt")
        with open(lines, "w", encoding="utf-8") as f:
            f.write("grok46-high@grok 4\nterra-high@codex 4\n\nluna-low@codex off\nnobody@codex 2\n")
        result = run_setup(cfg, discover_path, default_answers(len(lanes_sample["lanes"])),
                           "--no-bench", "--plain", "--tiers-from", lines)
        lanes, _routing = load_written(cfg)
        summary = "Lines: 2 took a tier; 1 went off; 3 not named, so off; unknown, ignored: nobody@codex."
        ok = (result.returncode == 0
              and 0 <= result.stdout.find(summary) < result.stdout.find("tier [")
              and lanes["lanes"]["terra-high@codex"]["tier"] == 4
              and "enabled" not in lanes["lanes"]["terra-high@codex"]
              and lanes["lanes"]["grok46-high@grok"]["order"] == 1
              and lanes["lanes"]["terra-high@codex"]["order"] == 2
              and "terra-high@codex: tier 4, order 2" in result.stdout
              and lanes["lanes"]["luna-low@codex"]["enabled"] is False
              and all(lanes["lanes"][name]["enabled"] is False and "order" not in lanes["lanes"][name]
                      for name in ("sol-high@codex", "fable-xhigh@claude", "flash-high@agy", "luna-low@codex"))
              and lanes["lanes"]["sol-high@codex"]["tier"] == lanes_sample["lanes"]["sol-high@codex"]["tier"])
        return ok, f"code={result.returncode} stdout={result.stdout[:600]!r} stderr={result.stderr!r}"


def case_tiers_from_unreadable_file_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(cfg, discover_path, default_answers(len(lanes_sample["lanes"])),
                           "--no-bench", "--plain", "--tiers-from", os.path.join(td, "absent.txt"))
        ok = (result.returncode == 1 and "tiers-from" in result.stderr
              and not os.path.exists(os.path.join(cfg, "lanes.json")))
        return ok, f"code={result.returncode} stderr={result.stderr!r}"


def case_no_discover_skips_all_acquisition():
    """--no-discover must skip discover.discover and never call node."""
    import setup
    import discover as discover_mod
    hits = {"discover": 0, "node": 0}
    orig_discover = discover_mod.discover
    orig_run = getattr(setup, "subprocess", None)

    def wrapped_discover(*a, **k):
        hits["discover"] += 1
        return orig_discover(*a, **k)

    class Args:
        no_discover = True
        discover_json = None
        fixture_dir = None
        ads_dir = None

    discover_mod.discover = wrapped_discover
    try:
        discovered, data = setup.acquire_discovery({"lanes": {}}, Args())
    finally:
        discover_mod.discover = orig_discover
    return (
        data == "skipped (--no-discover)"
        and hits["discover"] == 0
        and discovered == set(harnesses.NAMES)
        and orig_run is None
    ), f"data={data!r} hits={hits} discovered={discovered} subprocess={orig_run}"


def case_one_discovery_path_is_discover():
    """The default setup path acquires through discover.discover once, never node."""
    import setup
    import discover as discover_mod
    fixtures = os.path.join(HERE, "fixtures", "discover")
    hits = {"discover": 0, "node": 0}
    orig_discover = discover_mod.discover

    def wrapped_discover(*a, **k):
        hits["discover"] += 1
        return orig_discover(*a, **k)

    class Args:
        no_discover = False
        discover_json = None
        fixture_dir = fixtures
        ads_dir = None

    discover_mod.discover = wrapped_discover
    try:
        discovered, data = setup.acquire_discovery(sample_proposal(harnesses.NAMES), Args())
    finally:
        discover_mod.discover = orig_discover
    ok = (
        hits["discover"] == 1
        and isinstance(data, dict)
        and "harnesses" in data
        and all(h in data["harnesses"] for h in ("codex", "agy", "grok", "claude"))
        and "discover.mjs" not in str(data)
    )
    return ok, f"hits={hits} discovered={discovered} harnesses={getattr(data, 'get', lambda *_: None)('harnesses')}"


def case_harness_error_keeps_existing_lanes():
    """A single harness failure is a notice; setup continues and existing lanes stay."""
    fixture_dir = os.path.join(HERE, "fixtures", "discover")
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        os.makedirs(cfg)
        existing = copy.deepcopy(lanes_sample)
        catalog.write_json(os.path.join(cfg, "lanes.json"), existing)
        catalog.write_json(os.path.join(cfg, "routing.json"), routing_sample)
        broken = os.path.join(td, "fixtures")
        os.makedirs(broken)
        for name in os.listdir(fixture_dir):
            src = os.path.join(fixture_dir, name)
            dst = os.path.join(broken, name)
            if name == "codex-debug-models.json":
                with open(dst, "w", encoding="utf-8") as f:
                    f.write("{not json")
            else:
                with open(src, "r", encoding="utf-8") as f:
                    text = f.read()
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(text)
        import discover
        saved = discover.discover(existing, fixture_dir=broken)
        refreshed, _refresh = discover.refresh_catalog(existing, saved)
        result = subprocess.run(
            [sys.executable, SETUP_PY, "--config-dir", cfg, "--fixture-dir", broken,
             "--no-bench", "--plain"],
            input=default_answers(len(refreshed["lanes"])),
            capture_output=True, text=True, cwd=DELEGATE_DIR,
        )
        lanes, _routing = load_written(cfg)
        notice = "discovery error" in result.stdout or "Harness codex: error" in result.stdout
        ok = (
            result.returncode == 0
            # the failing harness keeps every lane it has; the refresh may add
            # lanes on the harnesses that answered, never take one away here
            and set(lanes_sample["lanes"]) <= set(lanes["lanes"])
            and {name for name in lanes["lanes"] if name.endswith("@codex")}
            == {name for name in lanes_sample["lanes"] if name.endswith("@codex")}
            and notice
        )
        return ok, (
            f"code={result.returncode} lanes={set(lanes['lanes'])} "
            f"notice={notice} stdout={result.stdout[:500]!r} stderr={result.stderr!r}"
        )


def case_plain_collects_bench_in_process():
    """Plain setup renders collect() in process; it does not spawn bench.py."""
    import setup
    fixture = os.path.join(HERE, "fixture", "bench-epoch.csv")
    spawned = []

    class Args:
        no_bench = False
        bench_report = None
        epoch_csv = fixture
        effort_rows = None

    buf = []
    orig_print = setup.print if hasattr(setup, "print") else print

    def capture(*a, **k):
        buf.append(" ".join(str(x) for x in a))

    import builtins
    real_print = builtins.print
    builtins.print = capture
    try:
        setup.show_bench(Args(), sample_proposal(harnesses.NAMES), routing_sample)
    finally:
        builtins.print = real_print
    text = "\n".join(buf)
    import inspect
    source = inspect.getsource(setup.show_bench)
    ok = (
        "Lane benchmark ranking" in text
        and "bench.py" not in source
        and "subprocess" not in source
        and spawned == []
    )
    return ok, f"text={text[:200]!r} source_has_bench={'bench.py' in source}"


def case_focused_screen_rejects_plain():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        os.makedirs(cfg)
        catalog.write_json(os.path.join(cfg, "lanes.json"), copy.deepcopy(lanes_sample))
        catalog.write_json(os.path.join(cfg, "routing.json"), copy.deepcopy(routing_sample))
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(cfg, discover_path, "", "--no-bench", "--plain", "--screen", "carry")
        return (
            result.returncode == 1
            and "delegate catalog" in result.stderr
            and "set" in result.stderr
            and not (result.stdout or "").strip().endswith("wrote"),
            f"code={result.returncode} stderr={result.stderr!r}",
        )


def case_start_screen_keeps_plain_wizard():
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(
            cfg, discover_path, default_answers(len(lanes_sample["lanes"])),
            "--no-bench", "--screen", "start",
        )
        wrote = os.path.isfile(os.path.join(cfg, "lanes.json"))
        return (
            result.returncode == 0 and wrote,
            f"code={result.returncode} stdout={result.stdout[-200:]!r}",
        )


def case_saved_discovery_never_probes():
    import setup
    from unittest.mock import patch
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "discovery.json")
        for document in (
            {"discovered": [{"key": "codex"}], "missing": [{"key": "agy"}]},
            {"harnesses": {"codex": {"status": "ok"}}, "models": [], "unmapped": [], "retired": []},
        ):
            catalog.write_json(path, document)
            args = SimpleNamespace(discover_json=path, no_discover=False, fixture_dir=None)
            with patch.object(setup.discover, "discover", side_effect=AssertionError("unexpected live probe")) as probe:
                found, result = setup.acquire_discovery(lanes_sample, args)
            if found != {"codex"} or probe.called or result["harnesses"]["codex"]["status"] != "ok":
                return False, repr((found, result))
    return True, "both saved formats supplied facts without a live acquisition"


# --- ticket 33: the wizard refreshes to the current generation --------------

REFRESH_DIR = os.path.join(HERE, "fixtures", "refresh-2026-09-22")


def refresh_fixture():
    """(the frozen catalog, the refreshed catalog, the plan) on the 2026-09-22
    fixtures. The catalog is the frozen copy beside them, never the live one,
    which the refresh's own first run changes."""
    import discover
    import setup
    frozen = catalog.load_json(os.path.join(REFRESH_DIR, "lanes.json"))
    rows = catalog.load_json(os.path.join(REFRESH_DIR, "aa-accepted.json"))
    saved = discover.discover(frozen, fixture_dir=REFRESH_DIR)
    refreshed, plan = discover.refresh_catalog(
        frozen, saved, published_models=setup.published_model_names(rows)
    )
    return frozen, refreshed, plan


def write_rows(path, source, model):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"source": source, "model": model, "benchmark": "b", "score": 1}], f)
    return path


def case_a_fresh_fetch_is_not_fetched_again():
    """A fetch from the last 24 hours stands in for a new one, and the rows it
    holds replace the repo's Artificial Analysis rows (ticket 33)."""
    import setup
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "aa")
        os.makedirs(cache)
        accepted = write_rows(os.path.join(cache, "accepted.json"), "aa", "Grok 4.7")
        repo_aa = write_rows(os.path.join(td, "repo-aa.json"), "aa", "Grok 4.6")
        tbench = write_rows(os.path.join(td, "repo-tbench.json"), "tbench", "Grok 4.6")
        calls = []
        paths, note = setup.refresh_effort_rows(
            [repo_aa, tbench], cache_dir=cache, fetch=lambda *a, **k: calls.append(a)
        )
        ok = paths == [accepted, tbench] and calls == [] and "0h ago" in note
        return ok, f"paths={paths} calls={calls} note={note!r}"


def case_a_stale_fetch_is_fetched_again():
    """A cache older than 24 hours is fetched again, into the same directory."""
    import setup
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "aa")
        os.makedirs(cache)
        accepted = write_rows(os.path.join(cache, "accepted.json"), "aa", "Grok 4.6")
        old = time.time() - 48 * 60 * 60
        os.utime(accepted, (old, old))
        repo_aa = write_rows(os.path.join(td, "repo-aa.json"), "aa", "Grok 4.6")
        calls = []

        def fetch(out_dir, **kwargs):
            calls.append(out_dir)
            write_rows(os.path.join(out_dir, "accepted.json"), "aa", "Grok 4.7")

        paths, note = setup.refresh_effort_rows([repo_aa], cache_dir=cache, fetch=fetch)
        rows, _message = setup.load_effort_rows(paths)
        ok = (calls == [cache] and paths == [accepted]
              and rows == [{"source": "aa", "model": "Grok 4.7", "benchmark": "b", "score": 1}]
              and "fetched just now" in note)
        return ok, f"paths={paths} calls={calls} note={note!r}"


def case_a_failed_fetch_keeps_the_repo_rows():
    """A leaderboard that is down never stops a catalog edit: the repo's rows
    stand, and the start page carries the reason."""
    import setup
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "aa")
        repo_aa = write_rows(os.path.join(td, "repo-aa.json"), "aa", "Grok 4.6")

        def fetch(out_dir, **kwargs):
            raise RuntimeError("the page could not be read")

        paths, note = setup.refresh_effort_rows([repo_aa], cache_dir=cache, fetch=fetch)
        ok = (paths == [repo_aa] and "repo rows" in note
              and "the page could not be read" in note)
        return ok, f"paths={paths} note={note!r}"


def case_a_forced_fetch_passes_a_fresh_cache():
    """The harnesses page's `r` asks for the rows as they are now: `force`
    fetches even when the cache is under 24 hours old, into the same
    directory, and the note says so."""
    import setup
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "aa")
        os.makedirs(cache)
        accepted = write_rows(os.path.join(cache, "accepted.json"), "aa", "Grok 4.6")
        repo_aa = write_rows(os.path.join(td, "repo-aa.json"), "aa", "Grok 4.6")
        calls = []

        def fetch(out_dir, **kwargs):
            calls.append(out_dir)
            write_rows(os.path.join(out_dir, "accepted.json"), "aa", "Grok 4.7")

        paths, note = setup.refresh_effort_rows([repo_aa], cache_dir=cache, fetch=fetch, force=True)
        rows, _message = setup.load_effort_rows(paths)
        ok = (calls == [cache] and paths == [accepted]
              and rows == [{"source": "aa", "model": "Grok 4.7", "benchmark": "b", "score": 1}]
              and "fetched just now" in note)
        return ok, f"paths={paths} calls={calls} note={note!r}"


def case_a_failed_forced_fetch_keeps_the_launch_rows():
    """The harnesses page's `r` passes the paths launch used: a forced fetch
    that fails keeps those rows, the cache launch read, and not the repo's
    older ones, and the note says so (wizard-design 01)."""
    import setup
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "aa")
        os.makedirs(cache)
        accepted = write_rows(os.path.join(cache, "accepted.json"), "aa", "Grok 4.7")
        repo_aa = write_rows(os.path.join(td, "repo-aa.json"), "aa", "Grok 4.6")
        tbench = write_rows(os.path.join(td, "repo-tbench.json"), "tbench", "Grok 4.6")
        launch, _note = setup.refresh_effort_rows([repo_aa, tbench], cache_dir=cache)

        def fetch(out_dir, **kwargs):
            raise RuntimeError("the page could not be read")

        paths, note = setup.refresh_effort_rows([repo_aa, tbench], cache_dir=cache, fetch=fetch,
                                                force=True, fallback=launch)
        rows, _message = setup.load_effort_rows(paths)
        ok = (launch == [accepted, tbench] and paths == launch
              and rows[0]["model"] == "Grok 4.7"
              and "rows launch used" in note and "the page could not be read" in note
              and "repo rows" not in note)
        return ok, f"paths={paths} note={note!r}"


def case_the_save_after_a_rescan_writes_the_agent_files_of_the_lanes_it_saved():
    """The TUI save after `r` keeps the Agent files in step with the catalog
    it wrote: launch here found no models, the rescan proposes the opus55
    Lanes in place of the opus ones, and after the save every claude Lane
    saved has its file and the superseded ones have none (wizard-design 01,
    deepening D.7). It runs under a temp HOME, so ~/.config/delegate there is
    the live catalog."""
    import io
    import setup
    import setup_tui
    real_scan, real_run = setup.scan, setup_tui.run_curses
    real_in, real_out, real_err = sys.stdin, sys.stdout, sys.stderr
    real_env = {key: os.environ.get(key) for key in ("HOME", "DELEGATE_MODEL_QUEUE")}
    aa = os.path.join(REFRESH_DIR, "aa-accepted.json")
    seen = []

    def scan(args, lanes_doc, force=False, fallback=None):
        seen.append((force, fallback))
        if not force:
            return (set(harnesses.NAMES), "probe failed", setup.load_effort_rows([aa]), "", [aa])
        return real_scan(args, lanes_doc, force=force, fallback=fallback)

    def run_curses(wizard):
        wizard.handle("enter")
        wizard.handle("r")
        seen.append(wizard.message)
        for _ in range(40):
            if wizard.screen in ("done", "quit"):
                break
            wizard.handle("y" if wizard.screen == "confirm" else "enter")
        return wizard.result()

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    with tempfile.TemporaryDirectory() as td:
        agents = os.path.join(td, ".claude", "agents")
        config = os.path.join(td, ".config", "delegate")
        os.makedirs(agents)
        os.makedirs(config)
        shutil.copy(os.path.join(REFRESH_DIR, "lanes.json"), os.path.join(config, "lanes.json"))
        catalog.write_json(os.path.join(config, "routing.json"), routing_sample)
        for effort in ("low", "medium", "high", "xhigh", "max"):
            with open(os.path.join(agents, f"lane-opus-{effort}.md"), "w") as f:
                f.write("superseded\n")
        out, err = Terminal(), io.StringIO()
        setup.scan, setup_tui.run_curses = scan, run_curses
        sys.stdin, sys.stdout, sys.stderr = Terminal(), out, err
        os.environ["HOME"] = td
        os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(td, "new-models.json")
        try:
            code = setup.main(["--config-dir", config, "--fixture-dir", REFRESH_DIR,
                               "--effort-rows", aa, "--no-bench"])
        finally:
            setup.scan, setup_tui.run_curses = real_scan, real_run
            sys.stdin, sys.stdout, sys.stderr = real_in, real_out, real_err
            for key, value in real_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        written = sorted(os.listdir(agents))
        saved = catalog.load_json(os.path.join(config, "lanes.json"))["lanes"]
        claude = sorted(f"lane-{name.split('@')[0]}.md" for name, lane in saved.items()
                        if lane["harness"] == "claude")
        opus55 = [f"lane-opus55-{e}.md" for e in ("low", "medium", "high", "xhigh", "max")]
        ok = (code == 0 and seen[0] == (False, None) and seen[1] == (True, [aa])
              and str(seen[2]).startswith("Rescanned at ")
              and written == claude and all(name in written for name in opus55)
              and not any(name.startswith("lane-opus-") for name in written)
              and f"removed {os.path.join(agents, 'lane-opus-high.md')}" in err.getvalue())
        return ok, f"code={code} seen={seen} written={written} err={err.getvalue()[-400:]!r}"


def case_scan_and_propose_are_the_launch_steps():
    """`r` runs the same steps launch ran, through the same functions: `scan`
    acquires the rows and the harnesses' models, `propose_generation`
    proposes the current generation, and the result is what
    `refresh_catalog` gives directly, with the discovery mapped against it."""
    import discover
    import setup
    from types import SimpleNamespace
    frozen, refreshed, plan = refresh_fixture()
    args = SimpleNamespace(discover_json=None, no_discover=False, fixture_dir=REFRESH_DIR,
                           effort_rows=[os.path.join(REFRESH_DIR, "aa-accepted.json")],
                           no_bench=True, epoch_csv=None)
    discovered, data, rows, note, paths = setup.scan(args, copy.deepcopy(frozen), force=True)
    doc, plan_again, mapped = setup.propose_generation(copy.deepcopy(frozen), data, rows)
    skipped = setup.propose_generation(copy.deepcopy(frozen), "probe failed", rows)
    # the refresh fixture predates Kiro, so its machine has no Kiro listing
    ok = (discovered == set(harnesses.NAMES) - {"kiro"} and isinstance(data, dict)
          and note.startswith("Benchmark rows: Artificial Analysis from ")
          and paths == [os.path.join(REFRESH_DIR, "aa-accepted.json")]
          and rows[1] == "" and len(rows[0]) > 0
          and doc == refreshed and plan_again == plan
          and mapped == discover.map_lanes(data, doc)
          and skipped == (frozen, None, "probe failed")
          and setup.collect_bench(args, doc, rows[0]) == (None, ""))
    return ok, f"note={note!r} new={len(plan_again['new'])} removed={len(plan_again['removed'])}"


def case_the_refreshed_rows_reach_the_new_lanes():
    """The rows the refresh brings in are attributed to the lanes it adds:
    Claude Opus 5.5 to the opus55 lanes and Grok 4.7 high to grok47-high@grok,
    each at its own effort. A lane no source scored keeps no figures, which is
    what the carry page reports as no rows (ticket 33)."""
    import bench
    _frozen, refreshed, _plan = refresh_fixture()
    rows = catalog.load_json(os.path.join(REFRESH_DIR, "aa-accepted.json"))
    # the Epoch fixture, so the case reaches no URL
    data = bench.collect(refreshed, epoch_csv=os.path.join(HERE, "fixture", "bench-epoch.csv"),
                         effort_rows=rows)
    lanes = data["lanes"]

    def columns(name):
        return sorted((lanes[name].get("aa") or {}).get("cols", {}))

    ok = (columns("opus55-high@claude") and columns("opus55-max@claude")
          and columns("grok47-high@grok")
          and lanes["opus55-high@claude"]["aa"]["effort"] == "high"
          and lanes["grok47-high@grok"]["aa"]["effort"] == "high"
          # no source scores these yet, and none of the predecessor's rows leak
          and not columns("sol6-high@codex") and not columns("pro31-high@agy")
          and not columns("grok47fast-high@grok"))
    return ok, f"opus55={columns('opus55-high@claude')} grok47={columns('grok47-high@grok')}"


def case_no_discover_fetches_no_rows():
    """--no-discover skips every live acquisition, the benchmark-row fetch
    included: a run with it says nothing about where rows came from, because it
    went nowhere for them (ticket 33)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        discover_path = os.path.join(td, "discover.json")
        write_discover(discover_path, harnesses.NAMES)
        result = run_setup(cfg, discover_path,
                           default_answers(len(lanes_sample["lanes"])), "--no-bench")
        ok = (result.returncode == 0
              and "Benchmark rows:" not in result.stdout
              and "Catalog refresh" not in result.stdout)
        return ok, f"code={result.returncode} stdout={result.stdout[:300]!r}"


def case_plain_prints_the_refresh_change_lines():
    """--plain states the refresh, one line per model, and the catalog it then
    writes passes catalog.py check (ticket 33)."""
    import setup_tui
    _frozen, refreshed, plan = refresh_fixture()
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "config")
        os.makedirs(cfg)
        shutil.copy(os.path.join(REFRESH_DIR, "lanes.json"), os.path.join(cfg, "lanes.json"))
        catalog.write_json(os.path.join(cfg, "routing.json"), routing_sample)
        result = subprocess.run(
            [sys.executable, SETUP_PY, "--config-dir", cfg, "--fixture-dir", REFRESH_DIR,
             "--effort-rows", os.path.join(REFRESH_DIR, "aa-accepted.json"),
             "--no-bench", "--plain"],
            input=default_answers(len(refreshed["lanes"])),
            capture_output=True, text=True, cwd=DELEGATE_DIR,
        )
        expected = setup_tui.refresh_lines(plan, 10_000)
        check = subprocess.run(
            [sys.executable, os.path.join(DELEGATE_DIR, "catalog_cli.py"), "check",
             os.path.join(cfg, "lanes.json")],
            capture_output=True, text=True,
        )
        written = catalog.load_json(os.path.join(cfg, "lanes.json"))
        ok = (result.returncode == 0
              and all(line in result.stdout for line in expected)
              and "gpt-5.6-sol → gpt-6-sol: sol6-*@codex replace sol-*@codex (6 Lanes)"
              in result.stdout
              and check.returncode == 0
              and "sol6-high@codex" in written["lanes"]
              and "sol-high@codex" not in written["lanes"]
              # the temp catalog is not the live one, so no agent file moved,
              # and the commit's note says so on stderr
              and "agent file" in result.stderr and "agent file" not in result.stdout)
        return ok, (f"code={result.returncode} check={check.returncode} "
                    f"expected={expected} stdout={result.stdout[:600]!r}")


# --- deepening D1: a wizard save commits through the catalog it read ---------

class Terminal(io.StringIO):
    def isatty(self):
        return True


def confirm_every_page(wizard):
    """The full wizard from its start page to the confirm, every page taken
    as it opens, then `y`."""
    wizard.handle("enter")
    for _ in range(40):
        if wizard.screen in ("done", "quit"):
            break
        wizard.handle("y" if wizard.screen == "confirm" else "enter")
    return wizard.result()


def wizard_in_process(home, argv, during=None, stdin=None, drive=None):
    """setup.main in this process under the temp HOME `home`, with its own
    model queue: on a terminal whose TUI runs `during()` while the wizard is
    open and then confirms every page, or runs `drive(wizard)` when given,
    or, with `stdin`, on that input. Returns (exit code, stdout, stderr)."""
    import setup
    import setup_tui
    real_run = setup_tui.run_curses
    real_streams = sys.stdin, sys.stdout, sys.stderr
    real_env = {key: os.environ.get(key) for key in ("HOME", "DELEGATE_MODEL_QUEUE")}

    def run_curses(wizard):
        if during is not None:
            during()
        return (drive or confirm_every_page)(wizard)

    out, err = Terminal(), io.StringIO()
    setup_tui.run_curses = run_curses
    sys.stdin, sys.stdout, sys.stderr = stdin or Terminal(), out, err
    os.environ["HOME"] = home
    os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(home, "new-models.json")
    try:
        code = setup.main(argv)
    finally:
        setup_tui.run_curses = real_run
        sys.stdin, sys.stdout, sys.stderr = real_streams
        for key, value in real_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return code, out.getvalue(), err.getvalue()


def sample_catalog(root):
    cfg = os.path.join(root, "cfg")
    os.makedirs(cfg)
    for name in ("lanes.json", "routing.json"):
        shutil.copy(os.path.join(SAMPLES_DIR, name), cfg)
    return cfg


def only_the_sets_backup(cfg):
    """Whether <cfg>/backups holds one file, the lanes.json backup the
    `catalog set` made: a refused save backs up nothing."""
    folder = os.path.join(cfg, "backups")
    found = os.listdir(folder) if os.path.isdir(folder) else []
    return len(found) == 1 and found[0].startswith("lanes-")


def case_a_catalog_set_made_while_the_wizard_is_open_survives_its_save():
    """`delegate catalog set` lands while the wizard is open; the wizard's
    save then refuses, names lanes.json, writes nothing and exits 1, so the
    set's Tier stays (deepening D, bug 1)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_catalog(td)

        def catalog_set():
            kwargs = dict(scope="global", cwd=td, config_dir=cfg, field="lanes.terra-high@codex.tier",
                          value=1, meters={}, present=set(harnesses.NAMES))
            preview = catalog_edit.edit_catalog("set", **kwargs)
            catalog_edit.edit_catalog("set", apply=True, expect=preview["revision"], **kwargs)

        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--no-discover", "--no-bench"], during=catalog_set)
        tier = catalog.load_json(os.path.join(cfg, "lanes.json"))["lanes"]["terra-high@codex"]["tier"]
        ok = (code == 1 and "lanes.json" in err and "nothing written" in err and tier == 1
              and only_the_sets_backup(cfg))
        return ok, f"code={code} tier={tier} err={err!r} out={out[-300:]!r}"


def case_a_model_swap_made_while_the_wizard_is_open_survives_its_save():
    """Dispatch's scan swaps a newer codex model into lanes.json while the
    wizard is open; the wizard's save refuses rather than put the old Lane
    back (deepening D, bug 1)."""
    import model_queue
    sys.path.insert(0, HERE)
    from test_model_queue import newer_fixtures
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_catalog(td)
        fixtures = newer_fixtures(td)

        def scan():
            model_queue.scan(config_dir=cfg, fixture_dir=fixtures, present={"codex", "agy", "grok"})

        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--no-discover", "--no-bench"], during=scan)
        lanes = catalog.load_json(os.path.join(cfg, "lanes.json"))["lanes"]
        successor = [name for name, lane in lanes.items() if lane["model"] == "gpt-6.1-sol"]
        ok = (code == 1 and "lanes.json" in err and len(successor) == 1
              and "sol-high@codex" not in lanes)
        return ok, f"code={code} successor={successor} err={err!r}"


def case_the_full_save_writes_through_a_linked_catalog():
    """A config dir whose documents are links to files elsewhere keeps its
    links: the full save writes the changed lanes.json through its link and
    leaves the unchanged routing.json alone (deepening D, bug 3)."""
    with tempfile.TemporaryDirectory() as td:
        real = sample_catalog(os.path.join(td, "real"))
        cfg = os.path.join(td, "linked")
        os.makedirs(cfg)
        for name in ("lanes.json", "routing.json"):
            os.symlink(os.path.join(real, name), os.path.join(cfg, name))
        routing_before = open(os.path.join(real, "routing.json"), "rb").read()
        code, out, err = wizard_in_process(td, ["--config-dir", cfg, "--no-discover", "--no-bench"])
        saved = catalog.load_json(os.path.join(real, "lanes.json"))["lanes"]
        ok = (code == 0
              and all(os.path.islink(os.path.join(cfg, name)) for name in ("lanes.json", "routing.json"))
              and all("order" in lane for lane in saved.values())
              and open(os.path.join(real, "routing.json"), "rb").read() == routing_before)
        return ok, f"code={code} links={[os.path.islink(os.path.join(cfg, n)) for n in os.listdir(cfg)]} err={err!r}"


class EditingInput(io.StringIO):
    """The prompts' answers, from a reader that changes the catalog the first
    time it is read: a write that lands while --plain asks."""

    def __init__(self, answers, edit):
        super().__init__(answers)
        self._edit = edit

    def readline(self, *args):
        if self._edit is not None:
            edit, self._edit = self._edit, None
            edit()
        return super().readline(*args)


def case_the_plain_save_refuses_a_catalog_changed_while_it_asked():
    """--plain reads the catalog at launch and commits through that read: a
    lanes.json changed while it asked is refused, and the change stays."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_catalog(td)
        lanes_path = os.path.join(cfg, "lanes.json")

        def edit():
            doc = catalog.load_json(lanes_path)
            doc["lanes"]["sol-high@codex"]["tier"] = 4
            catalog.write_json(lanes_path, doc)

        answers = EditingInput(default_answers(len(lanes_sample["lanes"])), edit)
        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--no-discover", "--no-bench", "--plain"], stdin=answers)
        tier = catalog.load_json(lanes_path)["lanes"]["sol-high@codex"]["tier"]
        ok = code == 1 and "lanes.json" in err and "nothing written" in err and tier == 4
        return ok, f"code={code} tier={tier} err={err!r} out={out[-300:]!r}"


# --- deepening D2: Agent files and the Model queue follow the commit --------

def refresh_catalog_in(cfg):
    """`cfg` holding the frozen refresh-2026-09-22 lanes (sixteen claude
    Lanes) and the sample routing."""
    os.makedirs(cfg)
    shutil.copy(os.path.join(REFRESH_DIR, "lanes.json"), os.path.join(cfg, "lanes.json"))
    catalog.write_json(os.path.join(cfg, "routing.json"), routing_sample)
    return cfg


def case_a_model_noticed_while_the_wizard_is_open_stays_queued():
    """Dispatch notes a model while the wizard is open; the save forgets the
    entry the start page named and keeps the one it never showed (deepening
    D.4, bug 2)."""
    import model_queue
    with tempfile.TemporaryDirectory() as td:
        cfg = refresh_catalog_in(os.path.join(td, "cfg"))
        shown = {"harness": "codex", "model": "gpt-6-astra", "predecessor": None, "via": "scan",
                 "first_seen": "2026-10-09T08:00:00+00:00"}
        catalog.write_json(os.path.join(td, "new-models.json"),
                           {"version": model_queue.VERSION, "checked_at": None, "models": [shown]})
        noticed = []

        def note():
            noticed.extend(model_queue.note([{"harness": "agy", "model": "gemini-9-pro"}], "asked"))

        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--fixture-dir", REFRESH_DIR, "--no-bench"], during=note)
        queue = catalog.load_json(os.path.join(td, "new-models.json"))
        ok = (code == 0 and len(noticed) == 1 and queue["models"] == noticed
              and "wrote" in out)
        return ok, f"code={code} queue={queue} err={err[-300:]!r}"


def case_a_save_gives_every_native_lane_its_agent_file():
    """On the live catalog, a save gives every claude Lane in the catalog its
    Agent file, the Lanes the save did not add included: here none had one
    (deepening D.7)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = refresh_catalog_in(os.path.join(td, ".config", "delegate"))
        agents = os.path.join(td, ".claude", "agents")
        code, out, err = wizard_in_process(td, ["--config-dir", cfg, "--no-discover", "--no-bench"])
        saved = catalog.load_json(os.path.join(cfg, "lanes.json"))["lanes"]
        claude = sorted(f"lane-{name.split('@')[0]}.md" for name, lane in saved.items()
                        if lane["harness"] == "claude")
        files = sorted(os.listdir(agents)) if os.path.isdir(agents) else []
        ok = (code == 0 and len(claude) == 16 and files == claude
              and f"wrote {os.path.join(agents, 'lane-opus-high.md')}" in err)
        return ok, f"code={code} files={files} err={err[-300:]!r}"


# --- deepening D3: a focused screen saves only the change made on it -------

def toggle_one_lane(wizard):
    """A focused Tier screen: space on the Lane under the cursor, then enter
    and the confirm's y."""
    wizard.handle("space")
    return take_as_is(wizard)


def take_as_is(wizard):
    """A focused screen confirmed with nothing more done on it."""
    wizard.handle("enter")
    wizard.handle("y")
    return wizard.result()


def changed_fields(before, after):
    """{lane: the fields whose value differs} for the Lanes both documents hold."""
    return {name: sorted(key for key in set(lane) | set(after[name])
                         if lane.get(key) != after[name].get(key))
            for name, lane in before.items()
            if name in after and lane != after[name]}


def case_a_focused_tier_screen_saves_only_the_change_made_on_it():
    """One toggle on `--screen tier3` writes that Lane's Tier and the Orders
    it moved, and nothing else: the screen starts from the catalog as read and
    proposes no generation, which on these fixtures adds 20 Lanes and removes
    17 the screen never showed (deepening D.6, bug 4)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = refresh_catalog_in(os.path.join(td, "cfg"))
        lanes_path, routing_path = os.path.join(cfg, "lanes.json"), os.path.join(cfg, "routing.json")
        frozen = catalog.load_json(lanes_path)["lanes"]
        routing_before = open(routing_path, "rb").read()
        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--fixture-dir", REFRESH_DIR, "--no-bench", "--screen", "tier3"],
            drive=toggle_one_lane)
        saved = catalog.load_json(lanes_path)["lanes"]
        changes = changed_fields(frozen, saved)
        moved = [name for name, fields in changes.items() if "tier" in fields]
        tiers = {frozen[moved[0]]["tier"], saved[moved[0]]["tier"]} if len(moved) == 1 else set()
        others = {name: fields for name, fields in changes.items() if name not in moved}
        ok = (code == 0 and set(saved) == set(frozen)
              and len(moved) == 1 and 3 in tiers and len(tiers) == 2
              and all(fields == ["order"] for fields in others.values())
              and all(saved[name]["tier"] in tiers for name in others)
              and f"wrote {lanes_path}" in out and routing_path not in out
              and open(routing_path, "rb").read() == routing_before)
        added, removed = set(saved) - set(frozen), set(frozen) - set(saved)
        return ok, (f"code={code} added={len(added)} removed={len(removed)} moved={moved} "
                    f"changes={changes if len(changes) < 8 else len(changes)} err={err[-300:]!r}")


def without_a_shipped_class(cfg):
    """`cfg`'s routing.json without the shipped scout Class, which every
    screen shows with its default Range."""
    path = os.path.join(cfg, "routing.json")
    doc = catalog.load_json(path)
    del doc["classes"]["scout"]
    catalog.write_json(path, doc)
    return path


def on_disk(path):
    with open(path, "rb") as f:
        return f.read(), os.stat(path).st_mtime_ns


def case_a_focused_save_that_changed_no_routing_field_leaves_routing_alone():
    """The routing a screen shows carries every shipped Class. A focused save
    whose screen changed no routing field writes its Lanes and leaves
    routing.json's bytes and mtime as they were, the Class it lacks
    included (deepening D3)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_catalog(td)
        routing_path = without_a_shipped_class(cfg)
        before = on_disk(routing_path)
        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--no-discover", "--no-bench", "--screen", "tier3"],
            drive=toggle_one_lane)
        ok = (code == 0 and f"wrote {os.path.join(cfg, 'lanes.json')}" in out
              and routing_path not in out and on_disk(routing_path) == before
              and "scout" not in catalog.load_json(routing_path)["classes"])
        return ok, f"code={code} out={out[-300:]!r} err={err[-300:]!r}"


def case_a_focused_save_with_no_change_writes_nothing():
    """Each focused screen confirmed as it opened writes neither document and
    backs up nothing, on a catalog that lacks a shipped Class (deepening D3)."""
    failed = []
    for screen in ("carry", "tier3", "review", "routing"):
        with tempfile.TemporaryDirectory() as td:
            cfg = sample_catalog(td)
            without_a_shipped_class(cfg)
            files = [os.path.join(cfg, name) for name in ("lanes.json", "routing.json")]
            before = [on_disk(p) for p in files]
            code, out, err = wizard_in_process(
                td, ["--config-dir", cfg, "--no-discover", "--no-bench", "--screen", screen],
                drive=take_as_is)
            if not (code == 0 and [on_disk(p) for p in files] == before
                    and "nothing changed; nothing written" in out and "wrote" not in out
                    and not os.path.isdir(os.path.join(cfg, "backups"))):
                failed.append((screen, code, out[-200:], err[-200:]))
    return not failed, repr(failed)


def case_a_focused_save_refuses_a_catalog_changed_since_launch():
    """`delegate catalog set` lands while a focused screen is open; the
    screen's save names lanes.json, writes nothing and exits 1, so the set's
    Tier stays (deepening D3)."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_catalog(td)
        lanes_path, routing_path = os.path.join(cfg, "lanes.json"), os.path.join(cfg, "routing.json")
        routing_before = open(routing_path, "rb").read()
        theirs = []

        def catalog_set():
            kwargs = dict(scope="global", cwd=td, config_dir=cfg, field="lanes.terra-high@codex.tier",
                          value=1, meters={}, present=set(harnesses.NAMES))
            preview = catalog_edit.edit_catalog("set", **kwargs)
            catalog_edit.edit_catalog("set", apply=True, expect=preview["revision"], **kwargs)
            theirs.append(open(lanes_path, "rb").read())

        code, out, err = wizard_in_process(
            td, ["--config-dir", cfg, "--no-discover", "--no-bench", "--screen", "tier3"],
            during=catalog_set, drive=toggle_one_lane)
        tier = catalog.load_json(lanes_path)["lanes"]["terra-high@codex"]["tier"]
        ok = (code == 1 and lanes_path in err and "nothing written" in err
              and tier == 1 and [open(lanes_path, "rb").read()] == theirs
              and open(routing_path, "rb").read() == routing_before
              and "wrote" not in out and only_the_sets_backup(cfg))
        return ok, f"code={code} tier={tier} err={err!r} out={out[-300:]!r}"


for name, case in (
    ("saved discovery never probes", case_saved_discovery_never_probes),
    ("tiers-from applies the page lines", case_tiers_from_applies_the_page_lines),
    ("tiers-from with an unreadable file writes nothing", case_tiers_from_unreadable_file_writes_nothing),
    ("plain prints the start facts", case_plain_prints_the_start_facts),
    ("a fresh fetch is not fetched again", case_a_fresh_fetch_is_not_fetched_again),
    ("a stale fetch is fetched again", case_a_stale_fetch_is_fetched_again),
    ("a failed fetch keeps the repo rows", case_a_failed_fetch_keeps_the_repo_rows),
    ("a forced fetch passes a fresh cache", case_a_forced_fetch_passes_a_fresh_cache),
    ("a failed forced fetch keeps the launch rows", case_a_failed_forced_fetch_keeps_the_launch_rows),
    ("the save after a rescan writes the agent files of the Lanes it saved",
     case_the_save_after_a_rescan_writes_the_agent_files_of_the_lanes_it_saved),
    ("scan and propose are the launch steps", case_scan_and_propose_are_the_launch_steps),
    ("the refreshed rows reach the new lanes", case_the_refreshed_rows_reach_the_new_lanes),
    ("no-discover fetches no rows", case_no_discover_fetches_no_rows),
    ("plain prints the refresh change lines", case_plain_prints_the_refresh_change_lines),
    ("effort rows from several files combine", case_effort_rows_from_several_files_combine),
    ("all harnesses write canonical samples", case_all_harnesses_write_canonical_samples),
    ("subset filters lanes and meters", case_subset_filters_lanes_and_meters),
    ("existing values are prompt defaults", case_existing_values_are_prompt_defaults),
    ("one lane values change only that lane", case_one_lane_values_change_only_that_lane),
    ("bench report is display only", case_bench_report_is_display_only),
    ("decline writes nothing", case_decline_writes_nothing),
    ("out of range retries then writes value", case_out_of_range_retries_then_writes_value),
    ("EOF aborts without writing", case_eof_aborts_without_writing),
    ("routing edits keep other classes", case_routing_edits_keep_other_classes),
    ("effort rows say the prompt interface has no pre-screen",
     case_effort_rows_says_the_prompt_interface_has_no_prescreen),
    ("no-discover skips all acquisition", case_no_discover_skips_all_acquisition),
    ("one discovery path is discover.discover", case_one_discovery_path_is_discover),
    ("a harness error keeps existing lanes", case_harness_error_keeps_existing_lanes),
    ("plain collects bench in process", case_plain_collects_bench_in_process),
    ("focused screen on a pipe names the surgical CLI", case_focused_screen_rejects_plain),
    ("full start on a pipe still runs the wizard", case_start_screen_keeps_plain_wizard),
    ("a catalog set made while the wizard is open survives its save",
     case_a_catalog_set_made_while_the_wizard_is_open_survives_its_save),
    ("a model swap made while the wizard is open survives its save",
     case_a_model_swap_made_while_the_wizard_is_open_survives_its_save),
    ("the full save writes through a linked catalog", case_the_full_save_writes_through_a_linked_catalog),
    ("the plain save refuses a catalog changed while it asked",
     case_the_plain_save_refuses_a_catalog_changed_while_it_asked),
    ("a model noticed while the wizard is open stays queued",
     case_a_model_noticed_while_the_wizard_is_open_stays_queued),
    ("a save gives every native Lane in the catalog its agent file",
     case_a_save_gives_every_native_lane_its_agent_file),
    ("a focused tier screen saves only the change made on it",
     case_a_focused_tier_screen_saves_only_the_change_made_on_it),
    ("a focused save that changed no routing field leaves routing.json alone",
     case_a_focused_save_that_changed_no_routing_field_leaves_routing_alone),
    ("a focused save with no change writes nothing", case_a_focused_save_with_no_change_writes_nothing),
    ("a focused save refuses a catalog changed since launch",
     case_a_focused_save_refuses_a_catalog_changed_since_launch),
):
    try:
        ok, detail = case()
    except Exception as e:
        ok, detail = False, repr(e)
    record(name, ok, detail)

sys.exit(1 if fails else 0)
