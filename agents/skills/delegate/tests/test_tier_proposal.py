#!/usr/bin/env python3
"""test_tier_proposal.py — the wizard's proposed Tiers (any-harness ticket 17).

Run: python3 tests/test_tier_proposal.py
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import catalog  # noqa: E402
import tier_proposal  # noqa: E402
from setup_tui import Wizard  # noqa: E402

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}", file=sys.stderr)


SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
LANES = catalog.load_json(os.path.join(SAMPLES, "lanes.json"))
ROUTING = catalog.load_json(os.path.join(SAMPLES, "routing.json"))
AA_INDEX = "Artificial Analysis Intelligence Index"
SETTINGS = catalog.tier_proposal_settings(ROUTING)


def row(model, effort, score, cost, source="aa", benchmark=AA_INDEX):
    return {"source": source, "model": model, "effort": effort, "benchmark": benchmark,
            "score": score, "cost_usd": cost, "uncertain": False,
            **({"composite": True} if benchmark == AA_INDEX else {})}


# Scores on the AA index, thresholds 2 >= 30, 3 >= 40, 4 >= 50 (the sample's).
# Fable beats Sol on both score and cost in Tier 4; Sol is codex's only Lane
# clearing it. Luna has no row.
AA_ROWS = [
    row("claude-fable-5-1", "xhigh", 55.0, 1.00),
    row("gpt-5.6-sol", "high", 52.0, 2.00),
    row("gpt-5.6-terra", "high", 41.0, 0.30),
    row("grok-4.6", "high", 44.0, 0.90),
    row("gemini-3.8-flash-high", "high", 33.0, 0.50),
    row("gpt-5.6-sol", "medium", 60.0, 0.10),   # another effort: not Sol-high's figure
]
# Terminal-Bench ranks them differently, and names a versioned benchmark.
TB_ROWS = [
    row("claude-fable-5-1", "xhigh", 20.0, 300.0, source="tbench", benchmark="Terminal-Bench 4.0"),
    row("gpt-5.6-sol", "high", 58.0, 200.0, source="tbench", benchmark="Terminal-Bench 4.0"),
]


def settings(**over):
    out = copy.deepcopy(SETTINGS)
    out.update(over)
    return out


def test_settings_are_data():
    record("the sample catalog carries the rule, so a catalog without one gets it",
           SETTINGS["source"] == "aa" and SETTINGS["benchmark"] == AA_INDEX
           and SETTINGS["diversity"] is True and catalog.tier_proposal_settings({}) == SETTINGS)
    bad = {
        "thresholds that fall": {"thresholds": {"2": 40, "3": 30, "4": 50}},
        "a missing tier": {"thresholds": {"2": 30, "3": 40}},
        "a diversity that is not a boolean": {"diversity": "yes"},
        "an empty benchmark": {"benchmark": ""},
    }
    for label, change in bad.items():
        doc = copy.deepcopy(ROUTING)
        doc["tier_proposal"].update(change)
        try:
            catalog.validate_routing(doc)
            ok = False
        except catalog.CatalogError as e:
            ok = "tier_proposal" in str(e)
        record(f"the validator rejects {label}", ok)
    try:
        catalog.validate_routing({"tier_proposal": SETTINGS}, partial=True)
        project = False
    except catalog.CatalogError:
        project = True
    record("the rule is this machine's, not a project's", project)


def test_bands_and_frontier():
    proposals = tier_proposal.propose(LANES, AA_ROWS, SETTINGS)
    tiers = {name: p["tier"] for name, p in proposals.items()}
    record("a Lane without a row at its own effort gets no proposal", "luna-low@codex" not in proposals,
           repr(tiers))
    record("each Lane's proposal carries its score, benchmark and cost",
           proposals["grok46-high@grok"]["score"] == 44.0
           and proposals["grok46-high@grok"]["cost"] == 0.90
           and proposals["grok46-high@grok"]["benchmark"] == AA_INDEX)
    record("a Lane takes the highest band it clears",
           tiers["fable-xhigh@claude"] == 4 and tiers["flash-high@agy"] == 2, repr(tiers))
    record("Lanes in one band that neither beats on both axes share its Tier",
           tiers["grok46-high@grok"] == 3 and tiers["terra-high@codex"] == 3, repr(tiers))
    record("inside a Tier the cheaper Lane comes first",
           proposals["terra-high@codex"]["place"] < proposals["grok46-high@grok"]["place"])


def test_diversity():
    """Sol clears Tier 4 but Fable beats it on score and cost: off the cost
    frontier, Sol still holds Tier 4 for codex."""
    with_rule = tier_proposal.propose(LANES, AA_ROWS, SETTINGS)
    without = tier_proposal.propose(LANES, AA_ROWS, settings(diversity=False))
    record("a harness whose best Lane is off the frontier keeps a proposal in that Tier",
           with_rule["sol-high@codex"]["tier"] == 4 and with_rule["sol-high@codex"]["why"] == "diversity"
           and with_rule["fable-xhigh@claude"]["why"] == "frontier",
           repr(with_rule["sol-high@codex"]))
    record("with the rule off it falls to the next Tier",
           without["sol-high@codex"]["tier"] == 3
           and without["sol-high@codex"]["beaten_by"] == "fable-xhigh@claude",
           repr(without["sol-high@codex"]))


def test_switching_the_benchmark():
    tb = settings(source="tbench", benchmark="Terminal-Bench")
    proposals = tier_proposal.propose(LANES, AA_ROWS + TB_ROWS, tb)
    record("switching to Terminal-Bench recomputes the proposals from its rows",
           set(proposals) == {"fable-xhigh@claude", "sol-high@codex"}
           and proposals["sol-high@codex"]["tier"] == 4
           and proposals["fable-xhigh@claude"]["tier"] == 1
           and proposals["sol-high@codex"]["benchmark"] == "Terminal-Bench 4.0",
           repr(proposals))


def walk_to_tier_four(w):
    w.handle("enter")      # start -> harnesses
    w.handle("enter")      # harnesses -> carry
    w.handle("enter")      # carry -> tier 4


def test_wizard_confirm_and_quit():
    def fresh():
        return Wizard(copy.deepcopy(LANES), copy.deepcopy(ROUTING), None, set(catalog.HARNESSES),
                      "/tmp/lanes.json", "/tmp/routing.json", effort_rows=AA_ROWS, class_guide={})

    w = fresh()
    walk_to_tier_four(w)
    shown = w.view()
    record("the tier page shows each proposal and names the benchmark",
           w.screen == "tier" and "proposed" in shown["columns"]
           and any(AA_INDEX in line for line in shown.get("legend", [])),
           repr(shown.get("columns")) + repr(shown.get("legend")))
    w.handle("p")
    for _ in range(4):     # tiers 4..1 -> review
        w.handle("enter")
    w.handle("enter")      # review -> routing
    w.handle("enter")      # routing -> confirm
    w.handle("y")
    result = w.result()
    expected = {name: p["tier"] for name, p in tier_proposal.propose(LANES, AA_ROWS, SETTINGS).items()}
    written = result and {name: lane["tier"] for name, lane in result[0]["lanes"].items()}
    record("confirming writes the proposed Tiers; a Lane with no score keeps its own",
           written is not None
           and all(written[name] == tier for name, tier in expected.items())
           and written["luna-low@codex"] == LANES["lanes"]["luna-low@codex"]["tier"],
           f"{written} vs {expected}")

    q = fresh()
    walk_to_tier_four(q)
    q.handle("p")
    q.handle("q")
    record("quitting after taking the proposals writes nothing", q.result() is None and q.screen == "quit")


if __name__ == "__main__":
    test_settings_are_data()
    test_bands_and_frontier()
    test_diversity()
    test_switching_the_benchmark()
    test_wizard_confirm_and_quit()
    sys.exit(1 if fails else 0)
