#!/usr/bin/env python3
"""Tests for tier_matrix.py (the matrix both tier views read) and
page_link.py (the live link between the wizard and the benchmark page)."""
import http.client
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))

import page_link
import tier_matrix

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def lane(name, harness, group, effort, carried=True):
    return {"name": name, "harness": harness, "group": group, "model": group,
            "effort": effort, "carried": carried, "tier": 1 if carried else None}


def point(lanes, effort, cost, score=50.0, kind="lane", model=None, harness=()):
    return {"lanes": [{"name": n} for n in lanes], "effort": effort, "cost": cost,
            "score": score, "kind": kind, "model": model, "harness": list(harness)}


LANES = [
    lane("luna-low@codex", "codex", "gpt-luna", "low"),
    lane("astra-high@codex", "codex", "gpt-astra", "high"),
    lane("astra-low@codex", "codex", "gpt-astra", "low"),
    lane("sol-high@codex", "codex", "gpt-sol", "high"),
    lane("unpriced-high@codex", "codex", "gpt-new", "high"),
    lane("opus-high@claude", "claude", "claude-opus", "high"),
    lane("kiro-high@kiro", "kiro", "kiro-model", "high", carried=False),
]
COMPOSITE = {"id": "b0", "composite": True, "benchmark": "Index", "sourceName": "Index",
             "points": [point(["luna-low@codex"], "low", 0.01),
                        point(["astra-high@codex"], "high", 4.0),
                        point(["astra-low@codex"], "low", 1.0),
                        point(["sol-high@codex"], "high", 0.5),
                        point(["opus-high@claude"], "high", 2.0),
                        # measured at an effort no lane runs: counts toward the order
                        point([], "medium", 0.2, kind="own_other", model="gpt-luna-medium",
                              harness=["codex"])]}
DATA = {"lanes": LANES, "boards": [
    COMPOSITE,
    {"id": "b1", "benchmark": "Terminal-Bench 4.0", "sourceName": "Artificial Analysis",
     "category": "Coding", "points": []},
    {"id": "b2", "benchmark": "AA-Briefcase", "sourceName": "Artificial Analysis",
     "category": "Knowledge Work", "points": []},
    {"id": "b3", "benchmark": "Terminal-Bench 4.0", "sourceName": "Terminal-Bench",
     "category": "Coding", "points": []},
]}

try:
    fams = tier_matrix.families(DATA)
    harnesses = [h for h, _f in fams]
    codex = dict(fams)["codex"]
    astra = codex[0]
    luna = next(f for f in codex if f["group"] == "gpt-luna")
    record("1 a harness lists its models dearest first by geometric-mean cost, an unpriced one last",
           harnesses == ["claude", "codex", "kiro"]
           and [f["group"] for f in codex] == ["gpt-astra", "gpt-sol", "gpt-luna", "gpt-new"]
           and astra["lanes"] == ["astra-low@codex", "astra-high@codex"]
           and astra["by_effort"] == {"high": "astra-high@codex", "low": "astra-low@codex"}
           and abs(astra["geo"] - 2.0) < 1e-9
           # luna's own_other point at medium (0.2) counts with its lane's 0.01
           and abs(luna["geo"] - (0.01 * 0.2) ** 0.5) < 1e-9
           and codex[-1]["geo"] is None, repr(codex))
except Exception as e:
    record("1 a harness lists its models dearest first", False, repr(e))

try:
    others = tier_matrix.own_others(COMPOSITE, dict(tier_matrix.families(DATA))["codex"])
    record("2 own_others finds an effort a board measures where no lane runs",
           list(others) == ["codex|gpt-luna"] and list(others["codex|gpt-luna"]) == ["medium"],
           repr(others))
except Exception as e:
    record("2 own_others finds an effort a board measures where no lane runs", False, repr(e))

try:
    used = tier_matrix.used_harnesses(DATA)
    none_carried = tier_matrix.used_harnesses({"lanes": [dict(l, carried=False) for l in LANES]})
    record("3 the harnesses in use are those with a carried lane, else every one",
           used == {"codex", "claude"} and none_carried == {"codex", "claude", "kiro"}, repr(used))
except Exception as e:
    record("3 the harnesses in use are those with a carried lane", False, repr(e))

try:
    order = tier_matrix.board_order(DATA["boards"])
    labels = [tier_matrix.board_label(DATA["boards"][i]) for i in order]
    record("4 boards step by category, and a label names the source when two share a name",
           order == [0, 1, 3, 2]
           and labels == ["Index", "Terminal-Bench 4.0 · Artificial Analysis",
                          "Terminal-Bench 4.0 · Terminal-Bench", "AA-Briefcase · Artificial Analysis"]
           and tier_matrix.board_category(COMPOSITE) == "Composite", repr(labels))
except Exception as e:
    record("4 boards step by category", False, repr(e))


def request(link, method, path, body=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", link.port, timeout=5)
    headers = {"Host": host or f"127.0.0.1:{link.port}"}
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    res = conn.getresponse()
    out = res.status, res.read()
    conn.close()
    return out


link = page_link.PageLink()
try:
    url = link.start()
    key = link.key
    link.set_page("<p>page</p>")
    link.publish({"a@x": 2}, "b0")
    page = request(link, "GET", f"/?k={key}")
    state = request(link, "GET", f"/state?k={key}")
    first = json.loads(state[1])
    link.publish({"a@x": 2}, "b0")
    same = json.loads(request(link, "GET", f"/state?k={key}")[1])
    link.publish({"a@x": 3}, "b0")
    moved = json.loads(request(link, "GET", f"/state?k={key}")[1])
    record("5 the link serves the page and the wizard's state, and the version moves only on a change",
           url == f"http://127.0.0.1:{link.port}/?k={key}"
           and page == (200, b"<p>page</p>")
           and first == {"version": 1, "tiers": {"a@x": 2}, "board": "b0"}
           and same["version"] == 1 and moved["version"] == 2, repr((first, same, moved)))
except Exception as e:
    record("5 the link serves the page and the wizard's state", False, repr(e))

try:
    sent = [request(link, "POST", f"/set?k={key}", {"lane": "a@x", "tier": 4}),
            request(link, "POST", f"/set?k={key}", {"board": "b2"}),
            request(link, "POST", f"/set?k={key}", {"lane": "a@x", "tier": 7}),
            request(link, "POST", f"/set?k={key}", {"tier": 1}),
            request(link, "POST", f"/set?k={key}", b"not json")]
    taken = link.take()
    record("6 the page's changes queue in order for the wizard; a bad one is refused",
           [code for code, _b in sent] == [200, 200, 400, 400, 400]
           and taken == [{"lane": "a@x", "tier": 4}, {"board": "b2"}]
           and link.take() == [], repr((sent, taken)))
except Exception as e:
    record("6 the page's changes queue in order for the wizard", False, repr(e))

try:
    refused = [request(link, "GET", "/state"),
               request(link, "GET", "/state?k=wrong"),
               request(link, "GET", f"/state?k={key}", host="evil.example"),
               request(link, "POST", f"/set?k={key}", {"lane": "a@x", "tier": 1}, host="evil.example")]
    record("7 a request without the key, or from another host name, is refused",
           [code for code, _b in refused] == [403, 403, 403, 403] and link.take() == [],
           repr(refused))
except Exception as e:
    record("7 a request without the key, or from another host name, is refused", False, repr(e))
finally:
    link.stop()

sys.exit(1 if fails else 0)
