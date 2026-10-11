#!/usr/bin/env python3
"""test_catalog_draft.py — the catalog as setup holds it before save (deepening F).

Every case drives `CatalogDraft` through its interface only: the verbs that
decide, the queries that answer, and `documents()` and `changes()`, which say
what a save writes. Pure computation over two dicts: no file, no network.
Run: python3 tests/test_catalog_draft.py
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
sys.path.insert(0, SCRIPTS)
import catalog  # noqa: E402
import catalog_commit  # noqa: E402
from catalog_draft import CatalogDraft, Change, LaneDecision  # noqa: E402

fails = 0
LANES = catalog.load_json(os.path.join(SAMPLES, "lanes.json"))
ROUTING = catalog.load_json(os.path.join(SAMPLES, "routing.json"))
FABLE, SOL, TERRA, GROK, LUNA, FLASH = (
    "fable-xhigh@claude", "sol-high@codex", "terra-high@codex",
    "grok46-high@grok", "luna-low@codex", "flash-high@agy")


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def sample(**records):
    """The sample lanes document, each named Lane's record updated with the
    given fields; a field given as None is removed."""
    doc = copy.deepcopy(LANES)
    for name, fields in records.items():
        for key, value in fields.items():
            if value is None:
                doc["lanes"][name].pop(key, None)
            else:
                doc["lanes"][name][key] = value
    return doc


def placed(doc):
    """{lane: (tier, order or None, enabled or None)} of a lanes document."""
    return {name: (lane["tier"], lane.get("order"), lane.get("enabled"))
            for name, lane in doc["lanes"].items()}


def tier_two():
    """A Tier 2 holding orders 7 and 1 and two Lanes with none, in an order
    that is neither the Order nor the names'."""
    doc = {"version": "delegate-lanes.v1", "meters": {}, "lanes": {}}
    for name, order in (("b@codex", 7), ("z@codex", None), ("d@codex", 1), ("a@codex", None)):
        lane = {"harness": "codex", "model": name, "effort": "high", "meter": "codex", "tier": 2}
        if order is not None:
            lane["order"] = order
        doc["lanes"][name] = lane
    return doc


def case_no_decision_writes_back_the_catalog_it_read():
    lanes = sample(**{SOL: {"enabled": True}, LUNA: {"order": 5}, FLASH: {"order": 9},
                      GROK: {"enabled": False}})
    focused = CatalogDraft(lanes, ROUTING, whole=False).documents()
    whole = CatalogDraft(LANES, ROUTING, whole=True).documents()
    expected_whole = sample(**{FABLE: {"order": 1}, SOL: {"order": 1}, GROK: {"order": 1},
                               TERRA: {"order": 2}, FLASH: {"order": 1}, LUNA: {"order": 2}})
    ok = (set(focused) == {"lanes", "routing"} and set(focused) <= set(catalog_commit.DOCUMENTS)
          and catalog.format_json(focused["lanes"]) == catalog.format_json(lanes)
          and catalog.format_json(focused["routing"]) == catalog.format_json(ROUTING)
          and whole["lanes"] == expected_whole and whole["routing"] == ROUTING)
    return ok, f"focused={placed(focused['lanes'])} whole={placed(whole['lanes'])}"


def case_a_tier_as_read_is_numbered_by_order_then_name_and_gaps_close():
    draft = CatalogDraft(tier_two(), ROUTING, whole=True)
    order = draft.tier_lanes(2)
    places = {name: draft.lane(name).place for name in order}
    written = {name: lane["order"] for name, lane in draft.documents()["lanes"]["lanes"].items()}
    ok = (order == ["d@codex", "b@codex", "a@codex", "z@codex"]
          and places == {"d@codex": 1, "b@codex": 2, "a@codex": 3, "z@codex": 4}
          and written == places
          and draft.lane("b@codex") == LaneDecision(carried=True, tier=2, place=2, start_tier=2))
    return ok, f"order={order} places={places} written={written}"


NUMBERED = sample(**{FABLE: {"order": 1}, SOL: {"order": 1}, TERRA: {"order": 1},
                     GROK: {"order": 2}, LUNA: {"order": 1}, FLASH: {"order": 2}})


def case_a_lane_placed_in_another_tier_goes_to_its_end_and_back_to_its_place():
    draft = CatalogDraft(NUMBERED, ROUTING, whole=False)
    draft.place(SOL, 3)
    stayed = draft.tier_lanes(3) == [SOL]
    draft.place(TERRA, 3)
    moved = (draft.tier_lanes(3), draft.tier_lanes(2), draft.lane(TERRA))
    written = placed(draft.documents()["lanes"])
    draft.place(TERRA, 2)
    back = (draft.tier_lanes(2), catalog.format_json(draft.documents()["lanes"]))
    # another Lane joins Tier 2 meanwhile: terra still goes back before grok,
    # the Lane that followed it, and the newcomer stays at the end
    draft.place(TERRA, 3)
    draft.place(LUNA, 2)
    draft.place(TERRA, 2)
    around = draft.tier_lanes(2)
    ok = (stayed
          and moved == ([SOL, TERRA], [GROK], LaneDecision(True, 3, 2, 2))
          and written[TERRA] == (3, 2, None) and written[SOL] == (3, 1, None)
          and written[GROK] == (2, 1, None)
          and back == ([TERRA, GROK], catalog.format_json(NUMBERED))
          and around == [TERRA, GROK, LUNA])
    return ok, f"moved={moved} written={written} back={back[0]} around={around}"


def case_switching_a_lane_off_and_on_gives_back_its_tier_and_place():
    draft = CatalogDraft(NUMBERED, ROUTING, whole=False)
    draft.carry(TERRA, False)
    draft.carry(TERRA, False)
    off = (draft.lane(TERRA), draft.tier_lanes(2))
    draft.carry(TERRA, True)
    draft.carry(TERRA, True)
    on = (draft.lane(TERRA), draft.tier_lanes(2), draft.documents()["lanes"] == NUMBERED)
    # a Lane moved and then switched off goes back to the Tier it started in
    draft.place(TERRA, 3)
    draft.carry(TERRA, False)
    home = (draft.lane(TERRA), draft.tier_lanes(3))
    # a Lane off as given goes back to its place in the documents as given
    given_off = sample(**{GROK: {"order": 2, "enabled": False}, TERRA: {"order": 1},
                          LUNA: {"enabled": False}, FLASH: {"order": 1}})
    other = CatalogDraft(given_off, ROUTING, whole=False)
    before = (other.tier_lanes(2), other.tier_lanes(1))
    other.carry(GROK, True)
    other.carry(LUNA, True)
    after = (other.tier_lanes(2), other.tier_lanes(1))
    ok = (off == (LaneDecision(False, 2, None, 2), [GROK])
          and on == (LaneDecision(True, 2, 1, 2), [TERRA, GROK], True)
          and home == (LaneDecision(False, 2, None, 2), [SOL])
          and before == ([TERRA], [FLASH]) and after == ([TERRA, GROK], [FLASH, LUNA]))
    return ok, f"off={off} on={on} home={home} before={before} after={after}"


def case_at_moves_a_lane_inside_its_tier_and_stops_at_either_end():
    draft = CatalogDraft(tier_two(), ROUTING, whole=True)
    steps = []
    for name, at in (("a@codex", 1), ("a@codex", 0), ("z@codex", 5), ("d@codex", 99),
                     ("a@codex", "end"), ("z@codex", 2)):
        draft.place(name, 2, at=at)
        steps.append(draft.tier_lanes(2))
    other = CatalogDraft(LANES, ROUTING, whole=False)
    other.place(SOL, 2, at=1)
    joined = other.tier_lanes(2)
    other.place(TERRA, 2, at="end")
    ok = (steps == [["a@codex", "d@codex", "b@codex", "z@codex"],
                    ["a@codex", "d@codex", "b@codex", "z@codex"],
                    ["a@codex", "d@codex", "b@codex", "z@codex"],
                    ["a@codex", "b@codex", "z@codex", "d@codex"],
                    ["b@codex", "z@codex", "d@codex", "a@codex"],
                    ["b@codex", "z@codex", "d@codex", "a@codex"]]
          and joined == [SOL, GROK, TERRA]
          and other.tier_lanes(2) == [SOL, GROK, TERRA])
    return ok, f"steps={steps} joined={joined} then={other.tier_lanes(2)}"


def case_an_unplaced_lane_keeps_its_tier_as_given_and_a_prompt_sets_an_off_lane_tier():
    whole = CatalogDraft(LANES, ROUTING, whole=True)
    whole.place(TERRA, None)
    unplaced = (whole.lane(TERRA), whole.tier_lanes(2))
    written = placed(whole.documents()["lanes"])
    focused = CatalogDraft(NUMBERED, ROUTING, whole=False)
    focused.place(TERRA, None)
    focused_written = placed(focused.documents()["lanes"])
    focused.carry(LUNA, False)
    focused.place(LUNA, 3)
    off = (focused.lane(LUNA), focused.tier_lanes(3), placed(focused.documents()["lanes"])[LUNA])
    whole.carry(LUNA, False)
    whole.place(LUNA, 3)
    whole_off = placed(whole.documents()["lanes"])[LUNA]
    # a Lane off as given, carried and then unplaced, is written carried
    given_off = CatalogDraft(sample(**{LUNA: {"enabled": False}}), ROUTING, whole=False)
    given_off.carry(LUNA, True)
    given_off.place(LUNA, None)
    carried_unplaced = placed(given_off.documents()["lanes"])[LUNA]
    ok = (unplaced == (LaneDecision(True, None, None, 2), [GROK])
          and written[TERRA] == (2, None, None) and written[GROK] == (2, 1, None)
          and focused_written[TERRA] == (2, None, None) and focused_written[GROK] == (2, 1, None)
          and off == (LaneDecision(False, 3, None, 1), [SOL], (3, None, False))
          and whole_off == (3, None, False) and carried_unplaced == (1, None, None))
    return ok, (f"unplaced={unplaced} written={written} focused={focused_written} off={off} "
                f"whole_off={whole_off} carried_unplaced={carried_unplaced}")


def raises(error, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except error:
        return True
    except Exception:
        return False
    return False


def case_a_bad_decision_is_refused_and_changes_nothing():
    draft = CatalogDraft(NUMBERED, ROUTING, whole=False)
    draft.carry(LUNA, False)
    before = draft.documents()
    refused = [
        raises(KeyError, draft.place, "nobody@codex", 2),
        raises(KeyError, draft.carry, "nobody@codex", True),
        raises(KeyError, draft.lane, "nobody@codex"),
        raises(ValueError, draft.place, TERRA, 5),
        raises(ValueError, draft.place, TERRA, 0),
        raises(ValueError, draft.place, TERRA, "2"),
        raises(ValueError, draft.place, TERRA, True),
        raises(ValueError, draft.place, TERRA, 2, at="top"),
        raises(ValueError, draft.place, TERRA, 2, at=1.0),
        raises(ValueError, draft.place, LUNA, None),
        raises(ValueError, draft.tier_lanes, 5),
    ]
    return all(refused) and draft.documents() == before, f"refused={refused}"


def case_lines_carry_place_and_order_what_they_name_and_switch_the_rest_off():
    given = sample(**{LUNA: {"enabled": False}})
    draft = CatalogDraft(given, ROUTING, whole=False)
    dropped = draft.apply([(GROK, 4), (FLASH, 4), (LUNA, 3), (SOL, "off")], "off")
    written = placed(draft.documents()["lanes"])
    same = CatalogDraft(given, ROUTING, whole=False)
    same_dropped = same.apply({GROK: 4, FLASH: 4, LUNA: 3, SOL: "off"}, "off")
    nothing = CatalogDraft(given, ROUTING, whole=False)
    none_dropped = (nothing.apply([], "off"), nothing.apply({}, "keep"))
    ok = (dropped == [FABLE, TERRA]
          and draft.tier_lanes(4) == [GROK, FLASH] and draft.tier_lanes(3) == [LUNA]
          and draft.tier_lanes(2) == [] and draft.tier_lanes(1) == []
          and written == {FABLE: (4, None, False), SOL: (3, None, False), TERRA: (2, None, False),
                          GROK: (4, 1, None), LUNA: (3, 1, None), FLASH: (4, 2, None)}
          and same_dropped == dropped and same == draft
          and none_dropped == ([], []) and nothing.documents()["lanes"] == given)
    return ok, f"dropped={dropped} written={written} none={none_dropped}"


def case_a_proposal_places_the_lanes_it_names_first_and_keeps_the_rest_in_order():
    given = copy.deepcopy(NUMBERED)
    given["lanes"][SOL]["enabled"] = False
    draft = CatalogDraft(given, ROUTING, whole=False)
    kept = draft.apply([(LUNA, 2), (GROK, 2), (SOL, 4), (FLASH, "off")], "keep")
    written = placed(draft.documents()["lanes"])
    ok = (kept == []
          and draft.tier_lanes(2) == [LUNA, GROK, TERRA] and draft.tier_lanes(1) == []
          and draft.tier_lanes(4) == [SOL, FABLE] and draft.tier_lanes(3) == []
          and written == {FABLE: (4, 2, None), SOL: (4, 1, None), TERRA: (2, 3, None),
                          GROK: (2, 2, None), LUNA: (2, 1, None), FLASH: (1, None, False)})
    return ok, f"tiers={[draft.tier_lanes(t) for t in (1, 2, 3, 4)]} written={written}"


def case_bad_lines_are_refused_and_change_nothing():
    draft = CatalogDraft(NUMBERED, ROUTING, whole=False)
    refused = [
        raises(ValueError, draft.apply, [(GROK, 4)], "drop"),
        raises(ValueError, draft.apply, [(GROK, 4), (TERRA, 5)], "off"),
        raises(ValueError, draft.apply, [(GROK, "4")], "keep"),
        raises(ValueError, draft.apply, [(GROK, True)], "keep"),
        raises(KeyError, draft.apply, [(GROK, 4), ("nobody@codex", 2)], "off"),
    ]
    return (all(refused) and draft.documents()["lanes"] == NUMBERED
            and draft.tier_lanes(2) == [TERRA, GROK]), f"refused={refused}"


def case_a_focused_save_writes_only_the_changed_fields():
    given = sample(**{SOL: {"enabled": True}, LUNA: {"order": 3}, FLASH: {"order": 7},
                      TERRA: {"order": 1}, GROK: {"order": 2}})
    draft = CatalogDraft(given, ROUTING, whole=False)
    draft.carry(GROK, False)
    written = placed(draft.documents()["lanes"])
    ok = (written == {FABLE: (4, None, None), SOL: (3, None, True), TERRA: (2, 1, None),
                      GROK: (2, None, False), LUNA: (1, 3, None), FLASH: (1, 7, None)}
          and draft.changes() == [Change(("lanes", GROK, "order"), 2, None),
                                  Change(("lanes", GROK, "enabled"), None, False)]
          and draft.documents()["routing"] == ROUTING)
    return ok, f"written={written} changes={draft.changes()}"


def case_a_whole_save_writes_every_place_and_off_on_off_lanes_only():
    given = sample(**{SOL: {"enabled": True}, GROK: {"order": 2, "enabled": False},
                      TERRA: {"order": 5}, LUNA: {"order": 1}})
    draft = CatalogDraft(given, ROUTING, whole=True)
    draft.carry(FLASH, False)
    written = placed(draft.documents()["lanes"])
    ok = written == {FABLE: (4, 1, None), SOL: (3, 1, None), TERRA: (2, 1, None),
                     GROK: (2, None, False), LUNA: (1, 1, None), FLASH: (1, None, False)}
    return ok, f"written={written}"


def case_meters_off_is_written_and_on_removes_only_a_key_the_catalog_lacked():
    results = {}
    for given_meters in (None, False, True):
        routing = copy.deepcopy(ROUTING)
        if given_meters is not None:
            routing["meters"] = given_meters
        draft = CatalogDraft(LANES, routing, whole=False)
        draft.set_routing("meters", False)
        off = draft.documents()["routing"].get("meters", "absent")
        draft.set_routing("meters", True)
        on = draft.documents()["routing"].get("meters", "absent")
        results[given_meters] = (off, on)
    draft = CatalogDraft(LANES, ROUTING, whole=False)
    draft.set_routing("floor", 1, "review")
    draft.set_routing("ceiling", 4, "review")
    draft.set_routing("margin", 0.3)
    draft.set_routing("gate", 0.05)
    routing = draft.documents()["routing"]
    refused = [
        raises(ValueError, draft.set_routing, "overflow", False),
        raises(ValueError, draft.set_routing, "floor", 2),
        raises(KeyError, draft.set_routing, "floor", 2, "nobody"),
    ]
    ok = (results == {None: (False, "absent"), False: (False, True), True: (False, True)}
          and routing["classes"]["review"] == {"floor": 1, "ceiling": 4}
          and routing["margin"] == 0.3 and routing["gate"] == 0.05
          and all(routing["classes"][c] == ROUTING["classes"][c] for c in ROUTING["classes"] if c != "review")
          and all(refused) and "overflow" not in draft.documents()["routing"])
    return ok, f"results={results} routing={routing} refused={refused}"


def scripts():
    """Decision scripts over both save scopes: (name, whole, given, steps)."""
    given_off = sample(**{GROK: {"order": 2, "enabled": False}, SOL: {"enabled": True},
                          LUNA: {"order": 4}})
    return [
        ("prompted move", False, NUMBERED, [("place", TERRA, 3)]),
        ("off, on and J", False, given_off,
         [("carry", SOL, False), ("carry", GROK, True), ("place", LUNA, 1, "end")]),
        ("lines", False, LANES, [("apply", [(GROK, 4), (FLASH, 4), (LUNA, "off")], "off")]),
        ("proposal and routing", True, given_off,
         [("apply", [(FLASH, 2)], "keep"), ("route", "margin", 0.25), ("route", "meters", False),
          ("route", "floor", 2, "mechanical")]),
        ("unplaced and an off Lane's Tier", True, NUMBERED,
         [("place", TERRA, None), ("carry", LUNA, False), ("place", LUNA, 3)]),
        ("nothing", True, LANES, []),
    ]


def run(draft, steps):
    for verb, *args in steps:
        if verb == "route":
            draft.set_routing(*args)
        else:
            getattr(draft, verb)(*args)
    return draft


def field_diff(given_lanes, given_routing, docs):
    """{(path): (old, new)} over the fields a save may touch, read off the
    documents themselves."""
    out = {}
    for name, lane in given_lanes["lanes"].items():
        for key in ("tier", "order", "enabled"):
            old, new = lane.get(key), docs["lanes"]["lanes"][name].get(key)
            if old != new:
                out[("lanes", name, key)] = (old, new)
    for cls, rng in docs["routing"]["classes"].items():
        for key in ("floor", "ceiling"):
            old, new = given_routing["classes"].get(cls, {}).get(key), rng.get(key)
            if old != new:
                out[("classes", cls, key)] = (old, new)
    for key in ("margin", "gate", "meters"):
        old, new = given_routing.get(key), docs["routing"].get(key)
        if old != new:
            out[(key,)] = (old, new)
    return out


def case_changes_lists_exactly_the_fields_documents_changes():
    literal = run(CatalogDraft(NUMBERED, ROUTING, whole=False),
                  [("place", TERRA, 3), ("carry", LUNA, False), ("route", "margin", 0.3),
                   ("route", "meters", False), ("route", "ceiling", 4, "review")]).changes()
    expected = [Change(("lanes", TERRA, "tier"), 2, 3), Change(("lanes", TERRA, "order"), 1, 2),
                Change(("lanes", GROK, "order"), 2, 1), Change(("lanes", LUNA, "order"), 1, None),
                Change(("lanes", LUNA, "enabled"), None, False), Change(("lanes", FLASH, "order"), 2, 1),
                Change(("classes", "review", "ceiling"), 3, 4), Change(("margin",), 0.2, 0.3),
                Change(("meters",), None, False)]
    wrong = []
    for name, whole, given, steps in scripts():
        draft = run(CatalogDraft(given, ROUTING, whole=whole), steps)
        docs = draft.documents()
        listed = {change.path: (change.old, change.new) for change in draft.changes()}
        # the changes applied to the documents as given rebuild what save writes
        rebuilt = {"lanes": copy.deepcopy(given), "routing": copy.deepcopy(ROUTING)}
        for change in draft.changes():
            if change.path[0] == "lanes":
                target, key = rebuilt["lanes"]["lanes"][change.path[1]], change.path[2]
            elif change.path[0] == "classes":
                target, key = rebuilt["routing"]["classes"][change.path[1]], change.path[2]
            else:
                target, key = rebuilt["routing"], change.path[0]
            if change.new is None:
                target.pop(key, None)
            else:
                target[key] = change.new
        if (listed != field_diff(given, ROUTING, docs) or len(listed) != len(draft.changes())
                or rebuilt != docs):
            wrong.append((name, draft.changes(), field_diff(given, ROUTING, docs)))
    return literal == expected and not wrong, f"literal={literal} wrong={wrong}"


def case_settle_and_is_settled_notice_a_change_and_its_undo():
    draft = CatalogDraft(NUMBERED, ROUTING, whole=False)
    seen = [draft.is_settled()]
    for do, undo in ((("place", TERRA, 3), ("place", TERRA, 2)),
                     (("carry", LUNA, False), ("carry", LUNA, True)),
                     (("place", TERRA, 2, "end"), ("place", TERRA, 2, 1)),
                     (("place", TERRA, None), ("place", TERRA, 2)),
                     (("route", "gate", 0.3), ("route", "gate", 0.1)),
                     (("route", "meters", False), ("route", "meters", True)),
                     (("route", "floor", 1, "scout"), ("route", "floor", 2, "scout"))):
        run(draft, [do])
        seen.append(draft.is_settled())
        run(draft, [undo])
        seen.append(draft.is_settled())
    fresh = CatalogDraft(NUMBERED, ROUTING, whole=False)
    undone = draft == fresh
    # settle makes the decisions as they stand the start: Tier, place and reference
    draft.place(TERRA, 3)
    draft.settle()
    settled = (draft.is_settled(), draft.lane(TERRA).start_tier,
               placed(draft.documents()["lanes"])[TERRA])
    draft.place(TERRA, 2)
    left = (draft.is_settled(), draft.tier_lanes(2))
    draft.place(TERRA, 3)
    back = (draft.is_settled(), draft.tier_lanes(3))
    # a Lane off when the draft settled goes back to its place as given
    other = CatalogDraft(NUMBERED, ROUTING, whole=False)
    other.carry(LUNA, False)
    other.settle()
    other.carry(LUNA, True)
    ok = (seen == [True] + [False, True] * 7 and undone
          and settled == (True, 3, (3, 2, None))
          and left == (False, [GROK, TERRA]) and back == (True, [SOL, TERRA])
          and other.tier_lanes(1) == [LUNA, FLASH] and not other.is_settled())
    return ok, f"seen={seen} undone={undone} settled={settled} left={left} back={back} other={other.tier_lanes(1)}"


def case_a_draft_compares_by_value_and_is_never_hashed():
    one, two = CatalogDraft(NUMBERED, ROUTING, whole=False), CatalogDraft(NUMBERED, ROUTING, whole=False)
    equal = one == two
    one.place(TERRA, 3)
    differ = one != two
    one.place(TERRA, 2)
    again = one == two
    scope = CatalogDraft(NUMBERED, ROUTING, whole=True) != two
    unhashable = [raises(TypeError, hash, one), raises(TypeError, set, [one]),
                  raises(TypeError, dict, [(one, 1)])]
    ok = equal and differ and again and scope and all(unhashable) and one != "a draft"
    return ok, f"equal={equal} differ={differ} again={again} scope={scope} unhashable={unhashable}"


def case_the_draft_never_mutates_the_documents_it_was_given():
    wrong = []
    for name, whole, given, steps in scripts():
        lanes, routing = copy.deepcopy(given), copy.deepcopy(ROUTING)
        draft = run(CatalogDraft(lanes, routing, whole=whole), steps)
        draft.settle()
        docs = draft.documents()
        draft.changes()
        untouched = lanes == given and routing == ROUTING
        before = draft.documents()
        # what documents() returns is the caller's: changing it changes no draft
        docs["lanes"]["lanes"].clear()
        docs["routing"]["classes"].clear()
        # nor does changing the documents given, once the draft has them
        lanes["lanes"][TERRA]["tier"] = 1
        routing["margin"] = 0.9
        if not (untouched and draft.documents() == before):
            wrong.append(name)
    return not wrong, f"wrong={wrong}"


def case_lines_that_keep_a_tiers_sequence_still_write_it_as_its_order():
    """Lines and proposals are decisions, not tie-breaks: a focused save writes
    their order even where it is the order the catalog already gave, so pace
    never reorders what a line placed. A Tier no line named keeps its bytes."""
    lines = CatalogDraft(LANES, ROUTING, whole=False)
    lines.apply([(GROK, 2), (TERRA, 2), (FABLE, 4), (SOL, 3), (FLASH, 1), (LUNA, 1)], "off")
    proposal = CatalogDraft(NUMBERED, ROUTING, whole=False)
    proposal.apply([(LUNA, 1)], "keep")
    ok = (placed(lines.documents()["lanes"])
          == {FABLE: (4, 1, None), SOL: (3, 1, None), TERRA: (2, 2, None),
              GROK: (2, 1, None), LUNA: (1, 2, None), FLASH: (1, 1, None)}
          and proposal.documents()["lanes"] == NUMBERED and proposal.changes() == [])
    return ok, f"lines={placed(lines.documents()['lanes'])} proposal={proposal.changes()}"


for name, case in (
    ("a draft with no decision writes back the catalog it read",
     case_no_decision_writes_back_the_catalog_it_read),
    ("a Tier as read is numbered by Order, then lane name, and gaps close",
     case_a_tier_as_read_is_numbered_by_order_then_name_and_gaps_close),
    ("a Lane placed in another Tier goes to its end, and placed back takes its starting place",
     case_a_lane_placed_in_another_tier_goes_to_its_end_and_back_to_its_place),
    ("switching a Lane off and on gives it back its Tier and place",
     case_switching_a_lane_off_and_on_gives_back_its_tier_and_place),
    ("at moves a Lane inside its Tier and stops at either end; end puts it last",
     case_at_moves_a_lane_inside_its_tier_and_stops_at_either_end),
    ("a Lane not placed yet is written at its Tier as given, and a prompt sets an off Lane's Tier",
     case_an_unplaced_lane_keeps_its_tier_as_given_and_a_prompt_sets_an_off_lane_tier),
    ("a bad decision is refused and changes nothing", case_a_bad_decision_is_refused_and_changes_nothing),
    ("lines carry, set the Tier of and order the Lanes they name, and switch the rest off",
     case_lines_carry_place_and_order_what_they_name_and_switch_the_rest_off),
    ("a proposal places the Lanes it names first and keeps the rest in their order",
     case_a_proposal_places_the_lanes_it_names_first_and_keeps_the_rest_in_order),
    ("bad lines are refused and change nothing", case_bad_lines_are_refused_and_change_nothing),
    ("lines that keep a Tier's sequence still write it as its order",
     case_lines_that_keep_a_tiers_sequence_still_write_it_as_its_order),
    ("a focused save writes only the changed fields", case_a_focused_save_writes_only_the_changed_fields),
    ("a whole save writes every carried Lane's place, and enabled: false on off Lanes only",
     case_a_whole_save_writes_every_place_and_off_on_off_lanes_only),
    ("meters off is written; meters on removes only a key the catalog lacked",
     case_meters_off_is_written_and_on_removes_only_a_key_the_catalog_lacked),
    ("changes() lists exactly the fields documents() changes",
     case_changes_lists_exactly_the_fields_documents_changes),
    ("settle and is_settled notice a change and its undo",
     case_settle_and_is_settled_notice_a_change_and_its_undo),
    ("a draft compares by value and is never hashed", case_a_draft_compares_by_value_and_is_never_hashed),
    ("the draft never mutates the documents it was given",
     case_the_draft_never_mutates_the_documents_it_was_given),
):
    try:
        ok, detail = case()
    except Exception as e:
        ok, detail = False, repr(e)
    record(name, ok, detail)

sys.exit(1 if fails else 0)
