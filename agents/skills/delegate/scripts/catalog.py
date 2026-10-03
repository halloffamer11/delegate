#!/usr/bin/env python3
"""catalog.py — lane catalog and routing configuration for delegate.

Manages the catalog of execution lanes (harness x model x meter) and the
routing policy mapping task classes to minimum model tiers.

Locations:
  CONFIG_DIR = ~/.config/delegate (expanded at call time)
  global lanes:    <CONFIG_DIR>/lanes.json
  global routing:  <CONFIG_DIR>/routing.json
  project routing: <git-root>/.delegate/routing.json
  class guide:     <skill>/assets/classes.md   (the five shipped Classes)
  global guide:    <CONFIG_DIR>/classes.md      (overlay: Classes this machine adds)
  project guide:   <git-root>/.delegate/classes.md

One job: load, validate and project the effective catalog. The rest of what
catalog.py once held lives beside it (ticket 26): the edit engine in
`catalog_edit`, the Class guide checks in `class_guides`, the `delegate
catalog` command in `catalog_cli`, bulk Tier lines in `tier_lines` and the
published-name reconciliation in `published_names`.
"""
import copy
import json
import os
import re
import sys
import tempfile

CONFIG_DIR = "~/.config/delegate"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnesses  # noqa: E402
import published_names  # noqa: E402

# The starting catalog's routing: the shipped Classes and the Tier proposal
# rule a catalog falls back to.
SHIPPED_ROUTING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                    "assets", "samples", "routing.json")


def _shipped_routing():
    with open(SHIPPED_ROUTING_PATH, encoding="utf-8") as f:
        return json.load(f)


# The five shipped Classes (ticket 16), in the order the starting catalog
# writes them. A catalog gets them, with their Ranges, when it defines none; a
# catalog may give one a Range of its own, and may add a Class of its own
# beside them (a Range in routing.json and a section in a Class guide), but
# never loses one.
CLASSES = tuple(_shipped_routing()["classes"])
DEFAULT_CLASSES_SOURCE = "default"
# A Class name a catalog adds: lower case, digits and hyphens, as the shipped
# ones are, so it reads the same in a Lane header, a flag and a guide heading.
CLASS_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
LANES_VERSION = "delegate-lanes.v1"
ROUTING_VERSION = "delegate-routing.v1"

class CatalogError(Exception):
    """Plain-language catalog configuration or validation error."""
    pass


def find_git_root(start_dir=None):
    """Find git root by walking up from start_dir (default: current directory)
    until a .git entry (file or directory) is found. No git subprocess.
    Returns absolute directory path, or None if no git root found."""
    if start_dir is None:
        start_dir = os.getcwd()
    current = os.path.abspath(os.path.expanduser(start_dir))
    while True:
        git_path = os.path.join(current, ".git")
        if os.path.exists(git_path) or os.path.islink(git_path):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def format_json(doc):
    """Returns canonical text: json.dumps(doc, indent=2, ensure_ascii=False) plus trailing newline."""
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def write_json(path, doc):
    """Writes format_json(doc) atomically (temp file in the same directory, then os.replace).
    Creates parent directory if needed."""
    full_path = os.path.abspath(os.path.expanduser(path))
    parent_dir = os.path.dirname(full_path)
    os.makedirs(parent_dir, exist_ok=True)
    text = format_json(doc)
    fd, temp_path = tempfile.mkstemp(dir=parent_dir, prefix=".tmp_catalog_", text=True)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, full_path)
    except BaseException:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def load_json(path):
    """Strict JSON parser. Rejects NaN, Infinity, -Infinity.
    Missing file raises CatalogError naming the file and, for global lanes file,
    that samples/lanes.json can be copied there.
    Syntax error raises CatalogError with file name, line, and column."""
    expanded = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(expanded):
        if os.path.basename(expanded) == "lanes.json":
            raise CatalogError(
                f"{path}: file is missing; copy samples/lanes.json there or run /delegate setup"
            )
        raise CatalogError(f"{path}: file is missing")

    try:
        with open(expanded, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise CatalogError(f"{path}: file: cannot read: {e}")

    def _reject_constant(c):
        raise ValueError(f"{c} is not allowed in strict JSON")

    try:
        return json.loads(content, parse_constant=_reject_constant)
    except json.JSONDecodeError as e:
        raise CatalogError(
            f"{path}: line {e.lineno}, column {e.colno}: JSON syntax error: {e.msg}"
        )
    except ValueError as e:
        raise CatalogError(f"{path}: number: NaN is not allowed in strict JSON ({e})")


def validate_lanes(doc, source="lanes.json"):
    """Validates a lanes document against the schema. Returns doc or raises CatalogError."""
    if not isinstance(doc, dict):
        raise CatalogError(f"{source}: document: must be a JSON object")

    allowed_top = {"version", "meters", "lanes", "note"}
    for k in doc:
        if k not in allowed_top:
            raise CatalogError(
                f"{source}: key '{k}': unknown top-level key; allowed keys are 'version', 'meters', 'lanes', 'note'"
            )

    for req in ("version", "meters", "lanes"):
        if req not in doc:
            raise CatalogError(f"{source}: key '{req}': missing required top-level key")

    if doc["version"] != LANES_VERSION:
        raise CatalogError(
            f"{source}: key 'version': must equal '{LANES_VERSION}', got {doc['version']!r}"
        )

    if "note" in doc and not isinstance(doc["note"], str):
        raise CatalogError(f"{source}: key 'note': note must be a string")

    meters = doc["meters"]
    if not isinstance(meters, dict) or len(meters) == 0:
        raise CatalogError(f"{source}: key 'meters': meters must be a non-empty object")

    # `probe` named the script that read a Meter before the adapters did; a
    # catalog that still carries it reads, and the field means nothing
    allowed_meter_fields = {"harness", "plan", "price_month", "probe", "note", "model_meter"}
    required_meter_fields = ("harness", "plan", "price_month")

    for meter_name, meter in meters.items():
        if not isinstance(meter, dict):
            raise CatalogError(f"{source}: meter '{meter_name}': must be an object")
        for field in meter:
            if field not in allowed_meter_fields:
                raise CatalogError(f"{source}: meter '{meter_name}': unknown field '{field}'")
        for req in required_meter_fields:
            if req not in meter:
                raise CatalogError(f"{source}: meter '{meter_name}': missing required field '{req}'")

        if meter["harness"] not in harnesses.NAMES:
            raise CatalogError(
                f"{source}: meter '{meter_name}': harness must be one of {', '.join(harnesses.NAMES)}, got {meter['harness']!r}"
            )
        if not isinstance(meter["plan"], str) or not meter["plan"].strip():
            raise CatalogError(f"{source}: meter '{meter_name}': plan must be a non-empty string")
        pm = meter["price_month"]
        if type(pm) is bool or not isinstance(pm, (int, float)) or pm < 0:
            raise CatalogError(
                f"{source}: meter '{meter_name}': price_month must be a number >= 0, got {pm!r}"
            )
        if "note" in meter and not isinstance(meter["note"], str):
            raise CatalogError(f"{source}: meter '{meter_name}': note must be a string")
        if "model_meter" in meter and not isinstance(meter["model_meter"], bool):
            raise CatalogError(f"{source}: meter '{meter_name}': model_meter must be true or false")

    lanes = doc["lanes"]
    if not isinstance(lanes, dict) or len(lanes) == 0:
        raise CatalogError(f"{source}: key 'lanes': lanes must be a non-empty object")

    allowed_lane_fields = {
        "harness", "model", "effort", "meter", "meter_weight", "timeout",
        "price", "tier", "basis", "note", "enabled", "published_as", "order"
    }
    required_lane_fields = (
        "harness", "model", "effort", "meter", "meter_weight", "timeout",
        "price", "tier", "basis"
    )
    price_keys = ("in", "cache_read", "cache_write", "out")
    claimed = {}
    # Which lane models a published name could denote on its own, so that a
    # published_as entry cannot be pointed at somebody else's model.
    owners = {}
    for lane in lanes.values():
        if not isinstance(lane, dict):
            continue
        model = lane.get("model")
        if not isinstance(model, str) or not model.strip():
            continue
        normalized = published_names.normalize_name(model)
        base, _effort = published_names.strip_effort_suffix(normalized)
        for key in {normalized, base}:
            owners.setdefault(key, set()).add(model)

    for lane_name, lane in lanes.items():
        if not isinstance(lane, dict):
            raise CatalogError(f"{source}: lane '{lane_name}': must be an object")
        for field in lane:
            if field not in allowed_lane_fields:
                raise CatalogError(f"{source}: lane '{lane_name}': unknown field '{field}'")
        for req in required_lane_fields:
            if req not in lane:
                raise CatalogError(f"{source}: lane '{lane_name}': missing required field '{req}'")

        harness = lane["harness"]
        if harness not in harnesses.NAMES:
            raise CatalogError(
                f"{source}: lane '{lane_name}': harness must be one of {', '.join(harnesses.NAMES)}, got {harness!r}"
            )
        expected_suffix = f"@{harness}"
        if harnesses.split_lane(lane_name)[1] != harness:
            raise CatalogError(
                f"{source}: lane '{lane_name}': lane name must end with '{expected_suffix}'"
            )

        if not isinstance(lane["model"], str) or not lane["model"].strip():
            raise CatalogError(f"{source}: lane '{lane_name}': model must be a non-empty string")

        if lane["effort"] not in harnesses.EFFORTS:
            raise CatalogError(
                f"{source}: lane '{lane_name}': effort must be one of {', '.join(harnesses.EFFORTS)}, got {lane['effort']!r}"
            )
        offered = harnesses.get(harness).efforts
        # agy offers whatever effort the slug carries (`gemini-3.9-flash-xhigh`),
        # beside the ones it is known to offer
        if not harnesses.get(harness).offers_effort(lane["model"], lane["effort"]):
            raise CatalogError(
                f"{source}: lane '{lane_name}': {harness} does not offer effort {lane['effort']!r}; "
                f"{harness} offers {', '.join(offered)}"
            )

        meter_id = lane["meter"]
        if meter_id not in meters:
            raise CatalogError(
                f"{source}: lane '{lane_name}': meter '{meter_id}' is not defined in meters (missing meter)"
            )
        meter_harness = meters[meter_id].get("harness")
        if meter_harness != harness:
            raise CatalogError(
                f"{source}: lane '{lane_name}': meter '{meter_id}' belongs to another harness '{meter_harness}', does not match lane harness '{harness}'"
            )
        mw = lane["meter_weight"]
        if type(mw) is bool or not isinstance(mw, (int, float)) or mw <= 0:
            raise CatalogError(
                f"{source}: lane '{lane_name}': meter_weight must be a number > 0, got {mw!r}"
            )

        timeout = lane["timeout"]
        if not isinstance(timeout, str) or not re.fullmatch(r"[0-9]+[smh]", timeout):
            raise CatalogError(
                f"{source}: lane '{lane_name}': timeout must match '^[0-9]+[smh]$', got {timeout!r}"
            )

        price = lane["price"]
        if not isinstance(price, dict):
            raise CatalogError(f"{source}: lane '{lane_name}': price must be an object")
        for pk in price:
            if pk not in price_keys:
                raise CatalogError(f"{source}: lane '{lane_name}': price has unknown key '{pk}'")
        for pk in price_keys:
            if pk not in price:
                raise CatalogError(f"{source}: lane '{lane_name}': price is missing required key '{pk}'")
            pv = price[pk]
            if pv is not None:
                if type(pv) is bool or not isinstance(pv, (int, float)) or pv < 0:
                    raise CatalogError(
                        f"{source}: lane '{lane_name}': price key '{pk}' must be a number >= 0 or null, got {pv!r}"
                    )

        tier = lane["tier"]
        if type(tier) is not int or tier < 1 or tier > 4:
            raise CatalogError(
                f"{source}: lane '{lane_name}': tier must be a whole number from 1 to 4, got {tier!r}"
            )

        if "order" in lane:
            # the lane's place inside its tier, from 1, which the wizard's review
            # page writes and rank.py sorts by after tier (ticket 28)
            order = lane["order"]
            if type(order) is not int or order < 1:
                raise CatalogError(
                    f"{source}: lane '{lane_name}': order is the lane's place inside its tier "
                    f"and must be a whole number from 1 up, got {order!r}"
                )

        if not isinstance(lane["basis"], str):
            raise CatalogError(f"{source}: lane '{lane_name}': basis must be a string")

        if "note" in lane and not isinstance(lane["note"], str):
            raise CatalogError(f"{source}: lane '{lane_name}': note must be a string")

        if "enabled" in lane:
            en = lane["enabled"]
            if type(en) is not bool:
                raise CatalogError(
                    f"{source}: lane '{lane_name}': enabled must be a boolean, got {en!r}"
                )

        if "published_as" in lane:
            names = lane["published_as"]
            if not isinstance(names, list) or not names:
                raise CatalogError(
                    f"{source}: lane '{lane_name}': published_as must be a non-empty list of "
                    f"the names benchmark sources print for this model, got {names!r}"
                )
            for name in names:
                if not isinstance(name, str) or not name.strip():
                    raise CatalogError(
                        f"{source}: lane '{lane_name}': published_as entries must be "
                        f"non-empty strings, got {name!r}"
                    )
                key = published_names.normalize_name(name)
                foreign = sorted(m for m in owners.get(key, ()) if m != lane["model"])
                if foreign:
                    raise CatalogError(
                        f"{source}: lane '{lane_name}': published_as {name!r} already names "
                        f"model '{foreign[0]}', which another lane runs; that would read "
                        f"'{foreign[0]}' rows as '{lane['model']}'. Drop the entry, or put it "
                        f"on the lane that runs '{foreign[0]}'"
                    )
                first = claimed.get(key)
                if first is not None and first[2] != lane["model"]:
                    raise CatalogError(
                        f"{source}: lane '{lane_name}': published_as {name!r} names the same "
                        f"model as {first[0]!r} on lane '{first[1]}'; one published name "
                        f"denotes one model, but this would make it both '{first[2]}' and "
                        f"'{lane['model']}'"
                    )
                if first is None:
                    claimed[key] = (name, lane_name, lane["model"])

    return doc


# Each (file, lane) said once in a process: one edit validates its sources
# several times over — the load, the plan, and the recheck before the write —
# and three copies of one warning read like three problems.
_WARNED_STALE_LANES = set()


def warn_stale_lane(source, lane_name, lanes_source):
    """Say once, on stderr, that a project file names a lane the catalog lost.

    The wizard's refresh takes a superseded model's lanes out of the global
    catalog, and a project file written before it still names one. Routing in
    that project must not stop over a stale name, so the entry is ignored and
    the next project save drops it (ticket 33).
    """
    _warn_once(
        source, lane_name,
        f"warning: {source}: lane '{lane_name}' is not in {lanes_source} any more; "
        "ignoring it. The next project save drops it.\n",
    )


def warn_off_lane(source, lane_name, lanes_source):
    """Say once, on stderr, that a project file names a lane that is globally off.

    Turning a lane off in the wizard must never stop routing in a project that
    named it, so the entry is ignored on load exactly as a removed lane's is
    (ticket 36). A project save still refuses to name an off lane: `project_order`
    orders carried lanes and cannot restore one.
    """
    _warn_once(
        source, lane_name,
        f"warning: {source}: lane '{lane_name}' is off in {lanes_source}; ignoring it. "
        "project_order orders carried lanes and cannot restore one, and the next "
        "project save drops it.\n",
    )


def _warn_once(source, lane_name, text):
    if (source, lane_name) in _WARNED_STALE_LANES:
        return
    _WARNED_STALE_LANES.add((source, lane_name))
    sys.stderr.write(text)


def validate_project_lanes(doc, global_lanes, source="project lanes.json",
                           lanes_source="lanes.json"):
    """Validate a project's lane customization against the global lane catalog.

    The file is `<git-root>/.delegate/lanes.json`, beside the project's
    routing.json. It names Lanes the global catalog already has and sets one
    field on them, `tier`; every other Lane field stays global (ticket 32).
    Returns ``doc`` or raises ``CatalogError``.
    """
    if not isinstance(doc, dict):
        raise CatalogError(f"{source}: document: must be a JSON object")

    allowed_top = {"lanes", "note"}
    for k in doc:
        if k == "version":
            # `check` picks its validator by version, so a project file that
            # claimed the lanes version would be checked as a global catalog.
            raise CatalogError(
                f"{source}: key 'version': a project lane customization carries no "
                f"version; the lanes it names are versioned by {lanes_source}"
            )
        if k not in allowed_top:
            raise CatalogError(
                f"{source}: key '{k}': unknown top-level key; allowed keys are "
                f"{', '.join(sorted(allowed_top))}"
            )
    if "note" in doc and not isinstance(doc["note"], str):
        raise CatalogError(f"{source}: key 'note': note must be a string")

    lanes = doc.get("lanes", {})
    if not isinstance(lanes, dict):
        raise CatalogError(
            f"{source}: key 'lanes': lanes must be an object of lane names to "
            "the fields this project sets"
        )
    known = global_lanes.get("lanes", {}) if isinstance(global_lanes, dict) else {}
    for lane_name, lane in lanes.items():
        if lane_name not in known:
            warn_stale_lane(source, lane_name, lanes_source)
            continue
        if not isinstance(lane, dict):
            raise CatalogError(f"{source}: lane '{lane_name}': must be an object")
        for field in lane:
            if field not in ("tier", "note"):
                raise CatalogError(
                    f"{source}: lane '{lane_name}': unknown field '{field}'; a "
                    "project may set only 'tier' (with an optional 'note'); every "
                    "other lane field stays global"
                )
        if "tier" not in lane:
            raise CatalogError(
                f"{source}: lane '{lane_name}': missing required field 'tier'; "
                "a lane entry exists to set a tier"
            )
        tier = lane["tier"]
        if type(tier) is not int or tier < 1 or tier > 4:
            raise CatalogError(
                f"{source}: lane '{lane_name}': tier must be a whole number from "
                f"1 to 4, got {tier!r}"
            )
        if "note" in lane and not isinstance(lane["note"], str):
            raise CatalogError(f"{source}: lane '{lane_name}': note must be a string")
    return doc


def project_tier_changes(global_lanes, project_lanes):
    """Lanes whose Tier the project changes: {lane: {"from": n, "to": m}}.

    A project entry equal to the global Tier changes nothing and is left out,
    which is what "a project Tier is in effect" means to `show` and the rank
    header.
    """
    if not project_lanes:
        return {}
    known = global_lanes.get("lanes", {}) if isinstance(global_lanes, dict) else {}
    changes = {}
    for lane_name, lane in (project_lanes.get("lanes") or {}).items():
        if lane_name not in known or not isinstance(lane, dict):
            continue
        global_tier = known[lane_name].get("tier")
        tier = lane.get("tier")
        if tier is not None and tier != global_tier:
            changes[lane_name] = {"from": global_tier, "to": tier}
    return changes


def validate_routing(doc, source="routing.json", partial=False):
    """Validates a routing document. If partial=False (global file), all required keys
    and all classes must be present. If partial=True (project override), keys are optional.
    Returns doc or raises CatalogError."""
    if not isinstance(doc, dict):
        raise CatalogError(f"{source}: document: must be a JSON object")

    if "classTier" in doc:
        raise CatalogError(f"{source}: key 'classTier': 'classTier' has been replaced by 'classes'; use {{\"classes\": {{\"<class>\": {{\"floor\": 1, \"ceiling\": 2}}}}}}")

    if not partial and "project_order" in doc:
        raise CatalogError(
            f"{source}: key 'project_order': project_order is project-only and "
            "cannot appear in global routing"
        )

    allowed_top = {"version", "classes", "margin", "gate", "meters", "overflow", "note"}
    if partial:
        allowed_top.add("project_order")
    else:
        # the wizard's Tier proposal rule, this machine's (ticket 17)
        allowed_top.add("tier_proposal")
    for k in doc:
        if k not in allowed_top:
            raise CatalogError(
                f"{source}: key '{k}': unknown top-level key; allowed keys are {', '.join(sorted(allowed_top))}"
            )

    if not partial:
        # `classes` is optional: the shipped Classes are the defaults.
        for req in ("version", "margin", "gate"):
            if req not in doc:
                raise CatalogError(f"{source}: key '{req}': missing required top-level key")

    if "version" in doc and doc["version"] != ROUTING_VERSION:
        raise CatalogError(
            f"{source}: key 'version': must equal '{ROUTING_VERSION}', got {doc['version']!r}"
        )

    if "classes" in doc:
        cls_map = doc["classes"]
        if not isinstance(cls_map, dict):
            raise CatalogError(f"{source}: key 'classes': classes must be an object")
        for cls_name, cls_range in cls_map.items():
            if not CLASS_NAME.match(cls_name):
                raise CatalogError(
                    f"{source}: classes: class '{cls_name}': a class name is lower-case "
                    "letters, digits and single hyphens, starting with a letter"
                )
            if not isinstance(cls_range, dict):
                raise CatalogError(
                    f"{source}: classes: class '{cls_name}': must be an object with 'floor' and 'ceiling'"
                )
            for fld in cls_range:
                if fld not in ("floor", "ceiling", "leash"):
                    raise CatalogError(
                        f"{source}: classes: class '{cls_name}': unknown field '{fld}'"
                    )
            if "leash" in cls_range and type(cls_range["leash"]) is not bool:
                raise CatalogError(
                    f"{source}: classes: class '{cls_name}': leash must be true or false, "
                    f"got {cls_range['leash']!r}"
                )
            if not partial:
                for req in ("floor", "ceiling"):
                    if req not in cls_range:
                        raise CatalogError(
                            f"{source}: classes: class '{cls_name}': missing required field '{req}'"
                        )
            f = cls_range.get("floor")
            c = cls_range.get("ceiling")
            if f is not None:
                if type(f) is not int or f < 1 or f > 4:
                    raise CatalogError(
                        f"{source}: classes: class '{cls_name}': floor must be an integer from 1 to 4, got {f!r}"
                    )
            if c is not None:
                if type(c) is not int or c < 1 or c > 4:
                    raise CatalogError(
                        f"{source}: classes: class '{cls_name}': ceiling must be an integer from 1 to 4, got {c!r}"
                    )
            if f is not None and c is not None and f > c:
                raise CatalogError(
                    f"{source}: classes: class '{cls_name}': floor ({f}) cannot exceed ceiling ({c}); 1 <= floor <= ceiling <= 4"
                )

    if "margin" in doc:
        m = doc["margin"]
        if type(m) is bool or not isinstance(m, (int, float)) or not (0.0 <= m <= 1.0):
            raise CatalogError(
                f"{source}: key 'margin': margin must be a number between 0 and 1, got {m!r}"
            )

    if "gate" in doc:
        g = doc["gate"]
        if type(g) is bool or not isinstance(g, (int, float)) or not (0.0 <= g <= 1.0):
            raise CatalogError(
                f"{source}: key 'gate': gate must be a number between 0 and 1, got {g!r}"
            )

    if "meters" in doc:
        m = doc["meters"]
        if type(m) is not bool:
            raise CatalogError(
                f"{source}: key 'meters': meters must be a JSON boolean, got {m!r}"
            )

    if "overflow" in doc:
        o = doc["overflow"]
        if type(o) is not bool:
            raise CatalogError(
                f"{source}: key 'overflow': overflow must be a JSON boolean, got {o!r}; "
                "true lets a Range whose carried Lanes are all under the Gate admit the "
                "next Tier instead of stopping"
            )

    if "project_order" in doc:
        project_order = doc["project_order"]
        if not isinstance(project_order, list):
            raise CatalogError(
                f"{source}: key 'project_order': project_order must be a flat list "
                f"of non-empty lane-name strings, got {project_order!r}"
            )
        for lane_name in project_order:
            if not isinstance(lane_name, str) or not lane_name.strip():
                raise CatalogError(
                    f"{source}: key 'project_order': project_order must be a flat list "
                    f"of non-empty lane-name strings, got entry {lane_name!r}"
                )

    if "tier_proposal" in doc:
        validate_tier_proposal(doc["tier_proposal"], source=source)

    if "note" in doc and not isinstance(doc["note"], str):
        raise CatalogError(f"{source}: key 'note': note must be a string")

    return doc


def validate_tier_proposal(doc, source="routing.json"):
    """The wizard's Tier proposal rule: which benchmark's score bands slice,
    each Tier's threshold on it, and whether a Tier keeps every harness."""
    where = f"{source}: key 'tier_proposal'"
    if not isinstance(doc, dict):
        raise CatalogError(f"{where}: must be an object with source, benchmark, thresholds, diversity")
    for k in doc:
        if k not in ("source", "benchmark", "thresholds", "diversity", "note"):
            raise CatalogError(f"{where}: unknown field '{k}'")
    for k in ("source", "benchmark"):
        if not isinstance(doc.get(k), str) or not doc[k].strip():
            raise CatalogError(f"{where}: {k} must be a non-empty string, got {doc.get(k)!r}")
    thresholds = doc.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != {"2", "3", "4"}:
        raise CatalogError(
            f"{where}: thresholds must give tiers \"2\", \"3\" and \"4\" a score each, got {thresholds!r}")
    previous = None
    for tier in ("2", "3", "4"):
        value = thresholds[tier]
        if type(value) is bool or not isinstance(value, (int, float)):
            raise CatalogError(f"{where}: thresholds.{tier} must be a number, got {value!r}")
        if previous is not None and value < previous:
            raise CatalogError(
                f"{where}: thresholds.{tier} ({value}) is below thresholds.{int(tier) - 1} "
                f"({previous}); a higher Tier needs at least the score of the one below")
        previous = value
    if type(doc.get("diversity")) is not bool:
        raise CatalogError(f"{where}: diversity must be true or false, got {doc.get('diversity')!r}")
    if "note" in doc and not isinstance(doc["note"], str):
        raise CatalogError(f"{where}: note must be a string")
    return doc


def tier_proposal_settings(routing):
    """The Tier proposal rule in effect: the routing's own, else the sample
    catalog's (assets/samples/routing.json)."""
    if isinstance(routing, dict) and "tier_proposal" in routing:
        return copy.deepcopy(routing["tier_proposal"])
    return _shipped_routing()["tier_proposal"]


def merge_routing(global_doc, project_doc=None, global_source="routing.json", project_source=None):
    """Merges global routing and optional project routing.
    Each top-level key in project_doc replaces global value, except classes which merges per class and per key.
    Returns (routing, sources)."""
    g_src = global_source
    p_src = project_source

    routing = copy.deepcopy(global_doc)
    sources = {}
    for k in global_doc:
        sources[k] = g_src
    # The shipped Classes come first, then the global document's own: a
    # catalog's Range for a shipped Class replaces the default, a key it leaves
    # out (`leash`) keeps the shipped one, and a Class it adds sorts after the
    # shipped five.
    classes = {}
    for c, c_val in default_class_ranges().items():
        classes[c] = c_val
        sources[f"classes.{c}"] = DEFAULT_CLASSES_SOURCE
        for sub_k in c_val:
            sources[f"classes.{c}.{sub_k}"] = DEFAULT_CLASSES_SOURCE
    if "classes" in global_doc and isinstance(global_doc["classes"], dict):
        sources["classes"] = g_src
        for c, c_val in global_doc["classes"].items():
            if isinstance(c_val, dict) and isinstance(classes.get(c), dict):
                classes[c] = {**classes[c], **copy.deepcopy(c_val)}
            else:
                classes[c] = copy.deepcopy(c_val)
            sources[f"classes.{c}"] = g_src
            if isinstance(c_val, dict):
                for sub_k in c_val:
                    sources[f"classes.{c}.{sub_k}"] = g_src
    else:
        sources["classes"] = DEFAULT_CLASSES_SOURCE
    routing["classes"] = classes

    if project_doc:
        for k, v in project_doc.items():
            if k == "classes" and isinstance(v, dict):
                if "classes" not in routing or not isinstance(routing["classes"], dict):
                    routing["classes"] = {}
                sources["classes"] = p_src
                for c, c_val in v.items():
                    if isinstance(c_val, dict):
                        if c not in routing["classes"] or not isinstance(routing["classes"][c], dict):
                            routing["classes"][c] = {}
                        sources[f"classes.{c}"] = p_src
                        for sub_k, sub_v in c_val.items():
                            routing["classes"][c][sub_k] = sub_v
                            sources[f"classes.{c}.{sub_k}"] = p_src
                    else:
                        routing["classes"][c] = copy.deepcopy(c_val)
                        sources[f"classes.{c}"] = p_src
            else:
                routing[k] = copy.deepcopy(v)
                sources[k] = p_src

    return routing, sources


def default_class_ranges():
    """{class: {floor, ceiling[, leash]}} for the shipped Classes: what the
    starting catalog (assets/samples/routing.json) gives them."""
    shipped = _shipped_routing()["classes"]
    return {c: dict(shipped[c]) for c in CLASSES}


def with_default_classes(routing_doc):
    """A copy of one routing document whose `classes` holds every shipped
    Class, its own Range where it gives one, then the Classes it adds."""
    doc = copy.deepcopy(routing_doc)
    own = doc.get("classes") if isinstance(doc.get("classes"), dict) else {}
    classes = default_class_ranges()
    for c, c_val in own.items():
        classes[c] = copy.deepcopy(c_val)
    doc["classes"] = classes
    return doc


def class_names(routing):
    """The Classes an effective routing defines: the shipped five, then the
    Classes the catalog adds, in the order it writes them."""
    own = [c for c in (routing or {}).get("classes", {}) if c not in CLASSES]
    return list(CLASSES) + own


def class_leash(routing, cls):
    """Whether a job of this Class gets the leash sentence: the effective
    routing's `classes.<cls>.leash`, else the shipped Class's, else true. A
    job with no Class, or a Class the catalog adds without the key, keeps the
    leash."""
    entry = ((routing or {}).get("classes") or {}).get(cls)
    if isinstance(entry, dict) and "leash" in entry:
        return entry["leash"]
    return default_class_ranges().get(cls, {}).get("leash", True)


def meters_enabled(routing):
    """Effective routing.meters: JSON true or false, absent defaults on."""
    if not isinstance(routing, dict) or "meters" not in routing:
        return True
    return routing["meters"] is True


def overflow_enabled(routing):
    """Effective routing.overflow: JSON true or false, absent defaults on.

    On, a Class whose carried in-Range Lanes are every one of them under the
    Gate admits the next Tier above its Ceiling rather than stopping the job
    (ticket 29). Off keeps the stop. The default is on because a Gate-only
    outage costs the job, while the Tier above it costs usage.
    """
    if not isinstance(routing, dict) or "overflow" not in routing:
        return True
    return routing["overflow"] is True


def single_meter_tiers(lanes):
    """[(tier, meter, [lane, ...]), ...] for each Tier one Meter wholly serves.

    Coverage, not judgment (ticket 29): when every carried Lane of a Tier drains
    one Meter, that Meter falling under the Gate takes the whole Tier with it.
    Which Lanes a Tier carries is Orin's decision and this never questions it.
    A Tier with no carried Lane is not named.
    """
    out = []
    for tier in range(1, 5):
        carried = sorted(
            name for name, lane in (lanes or {}).items()
            if isinstance(lane, dict)
            and lane.get("enabled", True)
            and lane.get("tier") == tier
        )
        if not carried:
            continue
        used = {lanes[name].get("meter") for name in carried}
        if len(used) == 1:
            out.append((tier, used.pop(), carried))
    return out


def meter_dependency_lines(lanes, names=False):
    """One line per Tier that `single_meter_tiers` names.

    `names=True` appends the carried Lanes, which `check` has room for. The
    wizard's review page does not: a legend line past 79 places is clipped, so
    that page takes the short form.
    """
    lines = []
    for tier, meter, lane_names in single_meter_tiers(lanes):
        line = f"Tier {tier} depends on Meter {meter}; a Gate stop there stops the Tier."
        if names:
            line += f" Carried: {', '.join(lane_names)}"
        lines.append(line)
    return lines


def _validate_merged_routing(routing, source):
    """Validate a complete effective routing document.

    ``project_order`` has already been validated as project policy; remove that
    project-only projection before applying the complete global-routing shape.
    """
    routing_fields = copy.deepcopy(routing)
    routing_fields.pop("project_order", None)
    validate_routing(routing_fields, source=source, partial=False)


def validate_project_routing(
    doc,
    global_lanes,
    global_routing,
    source="project routing.json",
    lanes_source="lanes.json",
    global_source="routing.json",
    proposal=False,
):
    """Validate proposed project policy against both global documents.

    This is the public pre-save boundary for project routing. It validates all
    three input documents, Project order's catalog references, and the complete
    routing document produced by merging the proposal over global routing.
    Returns ``doc`` unchanged, or raises ``CatalogError``.

    ``proposal`` says which side of the write this is. A document being saved
    may not name a lane that is globally off, and says so. A document being read
    already exists, and a lane the wizard turned off since it was written must
    not stop routing in that project, so the entry warns and is ignored
    (ticket 36), the way a removed lane's does (ticket 33).
    """
    validate_lanes(global_lanes, source=lanes_source)
    validate_routing(global_routing, source=global_source, partial=False)
    validate_routing(doc, source=source, partial=True)

    lanes = global_lanes["lanes"]
    seen = set()
    for lane_name in doc.get("project_order", []):
        if lane_name in seen:
            raise CatalogError(
                f"{source}: project_order lane '{lane_name}': duplicate lane; "
                "each lane may appear only once"
            )
        seen.add(lane_name)
        if lane_name not in lanes:
            warn_stale_lane(source, lane_name, lanes_source)
            continue
        if not lanes[lane_name].get("enabled", True):
            if not proposal:
                warn_off_lane(source, lane_name, lanes_source)
                continue
            raise CatalogError(
                f"{source}: project_order lane '{lane_name}': lane is globally off; "
                "project_order cannot restore it"
            )

    routing, _sources = merge_routing(
        global_routing,
        doc,
        global_source=global_source,
        project_source=source,
    )
    _validate_merged_routing(
        routing,
        source=f"{source} merged with {global_source}",
    )
    return doc


def effective_routing(cwd=None, config_dir=None, lanes_doc=None, lanes_source=None):
    """Loads global routing, validates it, finds project file from cwd (default current dir),
    validates with partial=True if exists, merges. Returns (routing, sources)."""
    base_dir = os.path.expanduser(config_dir if config_dir is not None else CONFIG_DIR)
    global_path = os.path.join(base_dir, "routing.json")
    global_doc = load_json(global_path)
    validate_routing(global_doc, source=global_path, partial=False)

    git_root = find_git_root(cwd)
    project_path = os.path.join(git_root, ".delegate", "routing.json") if git_root else None

    if project_path and os.path.isfile(project_path):
        project_doc = load_json(project_path)
        validate_routing(project_doc, source=project_path, partial=True)
        if lanes_doc is None and "project_order" in project_doc:
            lanes_source = os.path.join(base_dir, "lanes.json")
            lanes_doc = load_json(lanes_source)
        if lanes_doc is not None:
            validate_project_routing(
                project_doc,
                lanes_doc,
                global_doc,
                source=project_path,
                lanes_source=lanes_source or "lanes.json",
                global_source=global_path,
            )
        routing, sources = merge_routing(
            global_doc,
            project_doc,
            global_source=global_path,
            project_source=project_path,
        )
        _validate_merged_routing(
            routing,
            source=f"{project_path} merged with {global_path}",
        )
        return routing, sources
    routing, sources = merge_routing(
        global_doc,
        None,
        global_source=global_path,
        project_source=None,
    )
    _validate_merged_routing(routing, source=global_path)
    return routing, sources


def _effective_lanes(lanes, routing, sources, lanes_source, project_lanes=None,
                     project_lanes_source=None):
    """Return lane records with the project Tier and the Project order projection.

    A project Tier is applied first, so the Class Range, the Gate, overflow and
    the Order projection below all read the effective Tier (ticket 32). A Lane
    the project moves has no global place in its new Tier, so its `order` goes
    with the move; `project_order` is what can give it one again.
    """
    effective = copy.deepcopy(lanes)
    for lane_name, lane in effective.items():
        if "order" in lane:
            sources[f"lanes.{lane_name}.order"] = lanes_source

    for lane_name, change in project_tier_changes({"lanes": lanes}, project_lanes).items():
        effective[lane_name]["tier"] = change["to"]
        effective[lane_name].pop("order", None)
        sources.pop(f"lanes.{lane_name}.order", None)
        sources[f"lanes.{lane_name}.tier"] = (
            project_lanes_source or "project lanes.json"
        )

    if "project_order" not in routing:
        return effective

    project_source = sources.get("project_order", "project routing.json")
    # A name the global catalog no longer has, or has turned off, was warned
    # about in validation and is ignored here, so neither a refreshed catalog nor
    # a lane switched off stops routing in a project whose file predates it
    # (tickets 33 and 36). Project order orders carried lanes; an off lane takes
    # no place in a Tier.
    project_order = [name for name in routing["project_order"]
                     if name in effective and effective[name].get("enabled", True)]
    named = set(project_order)

    for tier in range(1, 5):
        named_in_tier = [
            name for name in project_order if effective[name]["tier"] == tier
        ]
        fallback = sorted(
            (
                (name, lane)
                for name, lane in effective.items()
                if lane["tier"] == tier
                and lane.get("enabled", True)
                and name not in named
            ),
            key=lambda item: (
                item[1].get("order") is None,
                item[1].get("order", 0),
                item[0],
            ),
        )
        ordered_names = named_in_tier + [name for name, _lane in fallback]
        for order, lane_name in enumerate(ordered_names, 1):
            effective[lane_name]["order"] = order
            sources[f"lanes.{lane_name}.order"] = (
                project_source if lane_name in named else lanes_source
            )

    return effective


def project_lanes_path(cwd=None):
    """The project lane customization beside the project's routing.json, or None."""
    git_root = find_git_root(cwd)
    if not git_root:
        return None
    path = os.path.join(git_root, ".delegate", "lanes.json")
    return path if os.path.isfile(path) else None


def load_catalog(cwd=None, config_dir=None):
    """Loads and validates lanes and effective routing.
    Returns dict: {"meters": ..., "lanes": ..., "routing": ..., "sources": ..., "files": {...}}."""
    base_dir = os.path.expanduser(config_dir if config_dir is not None else CONFIG_DIR)
    lanes_path = os.path.join(base_dir, "lanes.json")
    routing_path = os.path.join(base_dir, "routing.json")

    lanes_doc = load_json(lanes_path)
    validate_lanes(lanes_doc, source=lanes_path)

    project_lanes_file = project_lanes_path(cwd)
    project_lanes_doc = None
    if project_lanes_file:
        project_lanes_doc = load_json(project_lanes_file)
        validate_project_lanes(
            project_lanes_doc,
            lanes_doc,
            source=project_lanes_file,
            lanes_source=lanes_path,
        )

    routing, sources = effective_routing(
        cwd=cwd,
        config_dir=config_dir,
        lanes_doc=lanes_doc,
        lanes_source=lanes_path,
    )
    lanes = _effective_lanes(
        lanes_doc["lanes"],
        routing,
        sources,
        lanes_path,
        project_lanes=project_lanes_doc,
        project_lanes_source=project_lanes_file,
    )

    git_root = find_git_root(cwd)
    project_path = os.path.join(git_root, ".delegate", "routing.json") if git_root else None
    if project_path and not os.path.isfile(project_path):
        project_path = None

    return {
        "meters": lanes_doc["meters"],
        "lanes": lanes,
        "routing": routing,
        "sources": sources,
        "project_tiers": project_tier_changes(lanes_doc, project_lanes_doc),
        "files": {
            "lanes": lanes_path,
            "routing": routing_path,
            "project": project_path,
            "project_lanes": project_lanes_file,
        },
    }


def check_meter_identity(doc, source):
    """Refuses a Lane whose Meter its harness's probe does not report.

    Such a Meter has an unknown Remaining for good, which the Gate never
    vetoes, so a misspelled name fails open (ticket 25). It is a `catalog
    check` refusal, not a load one: a catalog written before the names were
    checked keeps routing until the next check or wizard run names the fix.
    """
    lanes = doc.get("lanes") or {}
    for lane_name, lane in lanes.items():
        harness, meter_id = lane["harness"], lane["meter"]
        adapter = harnesses.get(harness)
        on_meter = [other.get("model") for other in lanes.values() if other.get("meter") == meter_id]
        if not adapter.reports_meter(meter_id, on_meter):
            raise CatalogError(
                f"{source}: lane '{lane_name}': meter '{meter_id}' is not one the {harness} probe reports; "
                f"it reports {', '.join(adapter.meter_names())}"
            )


def check_file(path, partial=False):
    """Validates one file. Detects validator from version field."""
    doc = load_json(path)
    if not isinstance(doc, dict) or "version" not in doc:
        raise CatalogError(
            f"{path}: version: missing version; must be one of '{LANES_VERSION}', '{ROUTING_VERSION}'"
        )
    version = doc["version"]
    if version == LANES_VERSION:
        validate_lanes(doc, source=path)
        check_meter_identity(doc, source=path)
    elif version == ROUTING_VERSION:
        validate_routing(doc, source=path, partial=partial)
    else:
        raise CatalogError(
            f"{path}: version: unknown version {version!r}; must be one of '{LANES_VERSION}', '{ROUTING_VERSION}'"
        )
    return doc


def fmt_file(path, partial=False):
    """Validates like check and rewrites file through write_json."""
    doc = check_file(path, partial=partial)
    write_json(path, doc)
    return doc
