#!/usr/bin/env python3
"""catalog_edit.py — the catalog edit engine: `set`, `range` and `order`.

Each edit previews by default (the proposed documents, the ranking they give
under the cached meters, and the catalog revision), and writes only with
`--apply --expect REVISION`, refusing when another edit landed between. The
wizard, the dashboard and `delegate catalog set|range|order` all edit through
`edit_catalog`. Split out of catalog.py (ticket 26), which keeps loading and
validating; this module imports `rank` at load, and `catalog` never does. The
sources and their revision come from `catalog_commit.read()`, and an apply
writes its one document with `catalog_commit.commit()`, which also backs up a
global document it replaces and, for the live catalog's lanes.json, keeps the
Agent files in step; its lines go to stderr.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import catalog_commit  # noqa: E402
import harnesses  # noqa: E402
import rank  # noqa: E402


# The refusal when a source changed between the preview and the apply, at the
# revision check or at the commit; the dashboard matches this exact text.
INTERVENING_EDIT = "intervening edit: source documents or resolved paths changed; preview again"
_SET_LANE_PREFIX = "lanes."
_SET_LANE_TIER_SUFFIX = ".tier"
_SET_ROUTING_FIELDS = {
    "gate": "routing.gate",
    "margin": "routing.margin",
    "meters": "routing.meters",
    "overflow": "routing.overflow",
    "quota_unit": "routing.quota_unit",
}
# The routing switches whose value is a boolean defaulting on, each with the
# reader that says what the merged documents come to.
_BOOL_ROUTING_KEYS = {"meters": catalog.meters_enabled, "overflow": catalog.overflow_enabled}


def _present_harnesses(present=None):
    if present is not None:
        return set(present)
    return harnesses.installed()


def _cached_meters(meters=None):
    if meters is not None:
        return meters
    return rank.load_cached_usage()


def _catalog_from_docs(lanes_doc, routing_doc, project_doc, files, project_lanes_doc=None):
    """Effective catalog from already-loaded source documents."""
    lanes_source = files["lanes"]
    routing_source = files["routing"]
    project_source = files.get("project")
    project_lanes_source = files.get("project_lanes")
    catalog.validate_lanes(lanes_doc, source=lanes_source)
    if project_lanes_doc is not None:
        catalog.validate_project_lanes(
            project_lanes_doc,
            lanes_doc,
            source=project_lanes_source or "project lanes.json",
            lanes_source=lanes_source,
        )
    if project_doc is not None:
        catalog.validate_project_routing(
            project_doc,
            lanes_doc,
            routing_doc,
            source=project_source or "project routing.json",
            lanes_source=lanes_source,
            global_source=routing_source,
        )
        routing, sources = catalog.merge_routing(
            routing_doc,
            project_doc,
            global_source=routing_source,
            project_source=project_source,
        )
        catalog._validate_merged_routing(
            routing,
            source=f"{project_source} merged with {routing_source}",
        )
    else:
        catalog.validate_routing(routing_doc, source=routing_source, partial=False)
        routing, sources = catalog.merge_routing(
            routing_doc,
            None,
            global_source=routing_source,
            project_source=None,
        )
        catalog._validate_merged_routing(routing, source=routing_source)
    lanes = catalog._effective_lanes(
        lanes_doc["lanes"],
        routing,
        sources,
        lanes_source,
        project_lanes=project_lanes_doc,
        project_lanes_source=project_lanes_source,
    )
    return {
        "meters": lanes_doc["meters"],
        "lanes": lanes,
        "routing": routing,
        "sources": sources,
        "project_tiers": catalog.project_tier_changes(lanes_doc, project_lanes_doc),
        "files": {
            "lanes": lanes_source,
            "routing": routing_source,
            "project": project_source,
            "project_lanes": project_lanes_source,
        },
    }


def _rank_preview(cat, meters_doc, present):
    picks = {}
    for cls in catalog.class_names(cat["routing"]):
        rows = rank.rank(cls, cat, meters_doc, present)
        picks[cls] = next((row["lane"] for row in rows if row.get("pick")), None)
    leaders = [
        {"tier": preview["tier"], "leader": preview["leader"]}
        for preview in rank.tier_leaders(cat, meters_doc, present)
    ]
    return picks, leaders


def _observations_report(meters_doc, meter_names):
    observed = rank.meter_observations(meters_doc)
    names = list(meter_names)
    if observed is None:
        return "invalid", sorted(names)
    missing = sorted(name for name in names if name not in observed)
    status = "cached" if observed else "missing"
    return status, missing


def parse_set_field(field):
    """Split an allowed set field on the known prefix and final name, not every dot."""
    if not isinstance(field, str) or not field.strip():
        raise catalog.CatalogError("field is required")
    if field in _SET_ROUTING_FIELDS.values():
        return ("routing", field.split(".", 1)[1])
    if field.startswith("routing.classes."):
        raise catalog.CatalogError(
            f"field '{field}' is outside this command's allowlist; "
            "use range CLASS FLOOR CEILING to set Floor and Ceiling together"
        )
    if field.startswith(_SET_LANE_PREFIX) and field.endswith(_SET_LANE_TIER_SUFFIX):
        lane = field[len(_SET_LANE_PREFIX):-len(_SET_LANE_TIER_SUFFIX)]
        if not lane:
            raise catalog.CatalogError(f"field '{field}': missing lane name")
        return ("lane_tier", lane)
    if field.startswith(_SET_LANE_PREFIX):
        raise catalog.CatalogError(
            f"field '{field}' is outside this command's allowlist; "
            "allowed lane field is lanes.<lane>.tier (global, or project with "
            "--scope project); Order uses the order command and carry is not "
            "editable here"
        )
    raise catalog.CatalogError(
        f"unknown field '{field}'; allowed fields are "
        "lanes.<lane>.tier, routing.gate, routing.margin, routing.meters, "
        "routing.overflow"
    )


def _move_in_sequence(names, lane, position):
    if lane not in names:
        raise catalog.CatalogError(
            f"lane '{lane}' is not a carried lane in this Tier; "
            "Order is one-based among carried Lanes"
        )
    n = len(names)
    if type(position) is not int or position < 1 or position > n:
        raise catalog.CatalogError(
            f"position {position!r} is out of range 1..{n} for this Tier"
        )
    rest = [name for name in names if name != lane]
    rest.insert(position - 1, lane)
    return rest


def _append_order_in_tier(lanes, lane_name, new_tier):
    """Place a lane at the end of the destination Tier's existing Order."""
    names = [name for name in catalog.carried_in_tier(lanes, new_tier) if name != lane_name]
    # Materialize the existing effective Order before appending. An unordered
    # Lane sorts after every numbered Lane, so max(order)+1 is not sufficient.
    for order, name in enumerate(names, 1):
        lanes[name]["order"] = order
    lanes[lane_name]["order"] = len(names) + 1



def _target(snap, dest):
    """The source an edit writes, as the read described it; dest is 'lanes',
    'routing', 'project' or 'project_lanes'. A project document is unread only
    when no Git root was found."""
    source = snap.sources[dest]
    if source is None:
        raise catalog.CatalogError(
            "scope 'project' needs a git root so the .delegate files can be written"
        )
    return dict(source)


def _require_globals(snap):
    """The global pair the edit engine needs; an absent one is named."""
    if snap.lanes is None:
        raise catalog.CatalogError(
            f"{snap.files['lanes']}: file is missing; copy samples/lanes.json there or run /delegate setup"
        )
    if snap.routing is None:
        raise catalog.CatalogError(f"{snap.files['routing']}: file is missing")


def _read(cwd, config_dir):
    """The catalog read an edit works from: the global pair, and the project
    pair of the Git root above `cwd` (default: the current directory)."""
    return catalog_commit.read(config_dir, project_dir=cwd if cwd is not None else os.getcwd())


def _require_scope(scope):
    if scope not in ("global", "project"):
        raise catalog.CatalogError("scope must be 'global' or 'project'")
    return scope


def _plan_set(field, value, scope, lanes_doc, routing_doc, project_doc,
              project_lanes_doc=None):
    kind, name = parse_set_field(field)
    if kind == "lane_tier":
        if name not in lanes_doc["lanes"]:
            raise catalog.CatalogError(f"lane '{name}' is not in the global lane catalog")
        if type(value) is not int or value < 1 or value > 4:
            raise catalog.CatalogError(
                f"lane '{name}': tier must be a whole number from 1 to 4, got {value!r}"
            )
        proposed_lanes = copy.deepcopy(lanes_doc)
        proposed_routing = copy.deepcopy(routing_doc)
        proposed_project = copy.deepcopy(project_doc)
        proposed_project_lanes = copy.deepcopy(project_lanes_doc)
        global_tier = lanes_doc["lanes"][name]["tier"]
        if scope == "global":
            lane = proposed_lanes["lanes"][name]
            old_tier = lane["tier"]
            lane["tier"] = value
            if old_tier != value:
                _append_order_in_tier(proposed_lanes["lanes"], name, value)
            values = {
                "field": f"lanes.{name}.tier",
                "lane": name,
                "original": {
                    "tier": global_tier,
                    "order": lanes_doc["lanes"][name].get("order"),
                },
                "resulting": {
                    "tier": proposed_lanes["lanes"][name]["tier"],
                    "order": proposed_lanes["lanes"][name].get("order"),
                },
            }
            return ("lanes", proposed_lanes, proposed_routing, proposed_project,
                    proposed_project_lanes, values)
        # Project scope: the Tier lives in the project's own lanes file, and a
        # Tier equal to the global one is no customization at all (ticket 32).
        if proposed_project_lanes is None:
            proposed_project_lanes = {}
        entries = dict(proposed_project_lanes.get("lanes") or {})
        original_tier = entries.get(name, {}).get("tier", global_tier)
        if value == global_tier:
            entries.pop(name, None)
        else:
            entry = dict(entries.get(name) or {})
            entry["tier"] = value
            entries[name] = entry
        if entries or "lanes" in proposed_project_lanes:
            proposed_project_lanes["lanes"] = entries
        values = {
            "field": f"lanes.{name}.tier",
            "lane": name,
            "original": {"tier": original_tier, "global": global_tier},
            "resulting": {"tier": value, "global": global_tier},
        }
        return ("project_lanes", proposed_lanes, proposed_routing, proposed_project,
                proposed_project_lanes, values)
    if kind == "routing":
        key = name
        proposed_lanes = copy.deepcopy(lanes_doc)
        proposed_routing = copy.deepcopy(routing_doc)
        proposed_project = copy.deepcopy(project_doc)
        proposed_project_lanes = copy.deepcopy(project_lanes_doc)
        dest = "routing" if scope == "global" else "project"
        write_value = True
        effective_reader = _BOOL_ROUTING_KEYS.get(key)
        if effective_reader is not None:
            if type(value) is not bool:
                raise catalog.CatalogError(
                    f"key '{key}': {key} must be a JSON boolean, got {value!r}"
                )
            # A no-op of the default on a legacy document must not add the key.
            if value is True:
                if scope == "global" and key not in routing_doc:
                    write_value = False
                elif scope == "project":
                    global_on = effective_reader(routing_doc)
                    project_has = project_doc is not None and key in project_doc
                    if global_on and not project_has:
                        write_value = False
        if write_value:
            if scope == "global":
                proposed_routing[key] = value
            else:
                if proposed_project is None:
                    proposed_project = {}
                proposed_project[key] = value
        original_global = routing_doc.get(key) if key in routing_doc else None
        original_merged, _sources = catalog.merge_routing(routing_doc, project_doc)
        original_effective = (
            effective_reader(original_merged) if effective_reader is not None
            else (
                project_doc.get(key, original_global)
                if project_doc is not None else original_global
            )
        )
        resulting_global = proposed_routing.get(key) if key in proposed_routing else None
        resulting_merged, _sources = catalog.merge_routing(proposed_routing, proposed_project)
        resulting_effective = (
            effective_reader(resulting_merged) if effective_reader is not None
            else (
                proposed_project.get(key, resulting_global)
                if proposed_project is not None else resulting_global
            )
        )
        return dest, proposed_lanes, proposed_routing, proposed_project, proposed_project_lanes, {
            "field": _SET_ROUTING_FIELDS[key],
            "original": {"global": original_global, "effective": original_effective},
            "resulting": {"global": resulting_global, "effective": resulting_effective},
        }
    raise catalog.CatalogError(f"unknown field '{field}'")


def _plan_range(cls, floor, ceiling, scope, lanes_doc, routing_doc, project_doc,
                project_lanes_doc=None):
    if not catalog.CLASS_NAME.match(cls):
        raise catalog.CatalogError(
            f"class '{cls}': a class name is lower-case letters, digits and single "
            "hyphens, starting with a letter"
        )
    if type(floor) is not int or type(ceiling) is not int:
        raise catalog.CatalogError(
            f"class '{cls}': floor and ceiling must be integers from 1 to 4"
        )
    proposed_lanes = copy.deepcopy(lanes_doc)
    proposed_routing = copy.deepcopy(routing_doc)
    proposed_project = copy.deepcopy(project_doc)
    proposed_project_lanes = copy.deepcopy(project_lanes_doc)
    dest = "routing" if scope == "global" else "project"
    if scope == "global":
        proposed_routing.setdefault("classes", {})
        proposed_routing["classes"].setdefault(cls, {})
        proposed_routing["classes"][cls]["floor"] = floor
        proposed_routing["classes"][cls]["ceiling"] = ceiling
    else:
        if proposed_project is None:
            proposed_project = {}
        proposed_project.setdefault("classes", {})
        proposed_project["classes"].setdefault(cls, {})
        proposed_project["classes"][cls]["floor"] = floor
        proposed_project["classes"][cls]["ceiling"] = ceiling
    original_global = copy.deepcopy(
        routing_doc.get("classes", {}).get(cls, catalog.default_class_ranges().get(cls, {})))
    if project_doc and "classes" in project_doc and cls in project_doc.get("classes", {}):
        original_effective = copy.deepcopy(original_global)
        original_effective.update(project_doc["classes"][cls])
    else:
        original_effective = copy.deepcopy(original_global)
    resulting_global = copy.deepcopy(
        proposed_routing.get("classes", {}).get(cls, catalog.default_class_ranges().get(cls, {})))
    if proposed_project and "classes" in proposed_project and cls in proposed_project.get("classes", {}):
        resulting_effective = copy.deepcopy(resulting_global)
        resulting_effective.update(proposed_project["classes"][cls])
    else:
        resulting_effective = copy.deepcopy(resulting_global)
    return dest, proposed_lanes, proposed_routing, proposed_project, proposed_project_lanes, {
        "class": cls,
        "original": {"global": original_global, "effective": original_effective},
        "resulting": {"global": resulting_global, "effective": resulting_effective},
    }


def _plan_order(lane, position, scope, lanes_doc, routing_doc, project_doc, files,
                project_lanes_doc=None):
    if lane not in lanes_doc["lanes"]:
        raise catalog.CatalogError(f"lane '{lane}' is not in the global lane catalog")
    if not lanes_doc["lanes"][lane].get("enabled", True):
        raise catalog.CatalogError(
            f"lane '{lane}' is globally off; Order is among carried Lanes"
        )
    tier = lanes_doc["lanes"][lane]["tier"]
    proposed_lanes = copy.deepcopy(lanes_doc)
    proposed_routing = copy.deepcopy(routing_doc)
    proposed_project = copy.deepcopy(project_doc)
    proposed_project_lanes = copy.deepcopy(project_lanes_doc)
    if scope == "global":
        current = catalog.carried_in_tier(proposed_lanes["lanes"], tier)
        new_seq = _move_in_sequence(current, lane, position)
        for order, name in enumerate(new_seq, 1):
            proposed_lanes["lanes"][name]["order"] = order
        return ("lanes", proposed_lanes, proposed_routing, proposed_project,
                proposed_project_lanes, {
                    "lane": lane,
                    "tier": tier,
                    "position": {
                        "original": current.index(lane) + 1,
                        "resulting": position,
                    },
                    "sequence": {"original": current, "resulting": new_seq},
                })
    before_cat = _catalog_from_docs(
        lanes_doc, routing_doc, project_doc, files, project_lanes_doc
    )
    # Project Order works inside the effective Tier, which a project Tier may
    # have moved the Lane into (ticket 32).
    tier = before_cat["lanes"][lane]["tier"]
    current = catalog.carried_in_tier(before_cat["lanes"], tier)
    new_seq = _move_in_sequence(current, lane, position)
    existing = list((project_doc or {}).get("project_order", []))
    # A save drops what the load ignored: a lane the catalog lost (ticket 33) and
    # a lane it turned off (ticket 36). Project order orders carried lanes.
    kept = [
        name for name in existing
        if name in before_cat["lanes"] and before_cat["lanes"][name]["tier"] != tier
        and before_cat["lanes"][name].get("enabled", True)
    ]
    if proposed_project is None:
        proposed_project = {}
    else:
        proposed_project = copy.deepcopy(proposed_project)
    proposed_project["project_order"] = kept + new_seq
    return ("project", proposed_lanes, proposed_routing, proposed_project,
            proposed_project_lanes, {
                "lane": lane,
                "tier": tier,
                "position": {
                    "original": current.index(lane) + 1,
                    "resulting": position,
                },
                "sequence": {"original": current, "resulting": new_seq},
            })


def plan_edits(ops, lanes_doc, routing_doc, project_doc, files,
               project_lanes_doc=None):
    """Plan a list of edits against source documents already in hand.

    ``ops`` is a sequence of mappings, one per edit, each holding the arguments
    ``edit_catalog`` takes for that edit: ``op``, which is 'set', 'range' or
    'order'; ``scope``, which is 'global' or 'project'; and the operation's own
    keys (``field`` and ``value``; ``cls``, ``floor`` and ``ceiling``; ``lane``
    and ``position``).  Each edit is planned on the documents the edit before it
    produced, so a list plans exactly as the same calls made one after another.
    ``files`` names the four source paths, as a source snapshot names them, and
    is used for messages only.

    Nothing is read from disk, no Meter is read, and nothing is written.  The
    documents handed in are left as they are.

    Returns named fields: the four planned documents, ``lanes``, ``routing``,
    ``project`` and ``project_lanes``; the effective ``catalog`` they produce;
    and one ``steps`` entry per edit, holding its ``op``, ``scope``, ``dest``
    (the document that edit writes) and ``values``.
    """
    lanes = copy.deepcopy(lanes_doc)
    routing = copy.deepcopy(routing_doc)
    project = copy.deepcopy(project_doc)
    project_lanes = copy.deepcopy(project_lanes_doc)
    steps = []
    for spec in ops:
        op = spec.get("op")
        scope = _require_scope(spec.get("scope"))
        if op == "set":
            planned = _plan_set(
                spec.get("field"), spec.get("value"), scope,
                lanes, routing, project, project_lanes,
            )
        elif op == "range":
            planned = _plan_range(
                spec.get("cls"), spec.get("floor"), spec.get("ceiling"), scope,
                lanes, routing, project, project_lanes,
            )
        elif op == "order":
            planned = _plan_order(
                spec.get("lane"), spec.get("position"), scope,
                lanes, routing, project, files, project_lanes,
            )
        else:
            raise catalog.CatalogError(f"unknown operation '{op}'")
        dest, lanes, routing, project, project_lanes, values = planned
        steps.append({"op": op, "scope": scope, "dest": dest, "values": values})
    return {
        "lanes": lanes,
        "routing": routing,
        "project": project,
        "project_lanes": project_lanes,
        # The proposal is validated here, before anything is computed from it.
        "catalog": _catalog_from_docs(lanes, routing, project, files, project_lanes),
        "steps": steps,
    }


def _changed_fields(op, values, original_doc, proposed_doc, dest):
    changed = []
    if op == "set":
        field = values.get("field")
        if dest == "lanes":
            lane = values["lane"]
            old = original_doc["lanes"][lane]
            new = proposed_doc["lanes"][lane]
            if old.get("tier") != new.get("tier"):
                changed.append(f"lanes.{lane}.tier")
            for name, proposed_lane in proposed_doc["lanes"].items():
                if original_doc["lanes"][name].get("order") != proposed_lane.get("order"):
                    changed.append(f"lanes.{name}.order")
        elif dest == "project_lanes":
            lane = values["lane"]
            old = (original_doc.get("lanes") or {}).get(lane, {})
            new = (proposed_doc.get("lanes") or {}).get(lane, {})
            if old.get("tier") != new.get("tier"):
                changed.append(f"lanes.{lane}.tier")
        else:
            if field == "routing.gate" and original_doc.get("gate") != proposed_doc.get("gate"):
                changed.append("routing.gate")
            if field == "routing.margin" and original_doc.get("margin") != proposed_doc.get("margin"):
                changed.append("routing.margin")
            if field == "routing.meters" and original_doc.get("meters") != proposed_doc.get("meters"):
                changed.append("routing.meters")
            if field == "routing.overflow" and original_doc.get("overflow") != proposed_doc.get("overflow"):
                changed.append("routing.overflow")
            if field == "routing.quota_unit" and original_doc.get("quota_unit") != proposed_doc.get("quota_unit"):
                changed.append("routing.quota_unit")
        return changed
    if op == "range":
        cls = values["class"]
        old = (original_doc.get("classes") or {}).get(cls) or {}
        new = (proposed_doc.get("classes") or {}).get(cls) or {}
        if old.get("floor") != new.get("floor"):
            changed.append(f"classes.{cls}.floor")
        if old.get("ceiling") != new.get("ceiling"):
            changed.append(f"classes.{cls}.ceiling")
        return changed
    if op == "order":
        if dest == "project":
            if original_doc.get("project_order") != proposed_doc.get("project_order"):
                changed.append("project_order")
            return changed
        old_lanes = original_doc["lanes"]
        new_lanes = proposed_doc["lanes"]
        for name in sorted(set(old_lanes) | set(new_lanes)):
            if old_lanes.get(name, {}).get("order") != new_lanes.get(name, {}).get("order"):
                changed.append(f"lanes.{name}.order")
        return changed
    return changed


def edit_catalog(
    op,
    *,
    scope,
    cwd=None,
    config_dir=None,
    apply=False,
    expect=None,
    present=None,
    meters=None,
    field=None,
    value=None,
    cls=None,
    floor=None,
    ceiling=None,
    lane=None,
    position=None,
):
    """Preview or apply one focused catalog edit. Public for setup reuse.

    ``meters`` is a cached usage document; omitted means load_cached_usage().
    ``present`` is the harness set; omitted means CLIs found on PATH.
    Applying requires ``expect`` equal to the current source revision.
    """
    scope = _require_scope(scope)
    if op not in ("set", "range", "order"):
        raise catalog.CatalogError(f"unknown operation '{op}'")
    if apply and not expect:
        raise catalog.CatalogError("--apply requires --expect REVISION")
    if expect and not apply:
        raise catalog.CatalogError("--expect is only valid with --apply")

    snap = _read(cwd, config_dir)
    if scope == "project" and snap.git_root is None:
        raise catalog.CatalogError(
            "scope 'project' needs a git root so the .delegate files can be written"
        )
    if apply and snap.revision != expect:
        raise catalog.CatalogError(INTERVENING_EDIT)

    _require_globals(snap)
    lanes_doc, routing_doc = snap.lanes, snap.routing
    project_doc, project_lanes_doc = snap.project, snap.project_lanes
    files = snap.files
    # One edit is a plan of one operation: the planning path the staged view of
    # the dashboard uses is the path this write uses.
    plan = plan_edits(
        [{
            "op": op,
            "scope": scope,
            "field": field,
            "value": value,
            "cls": cls,
            "floor": floor,
            "ceiling": ceiling,
            "lane": lane,
            "position": position,
        }],
        lanes_doc, routing_doc, project_doc, files, project_lanes_doc,
    )
    proposed_lanes = plan["lanes"]
    proposed_routing = plan["routing"]
    proposed_project = plan["project"]
    proposed_project_lanes = plan["project_lanes"]
    dest = plan["steps"][0]["dest"]
    values = plan["steps"][0]["values"]

    # Validate the proposal against the original global documents, then
    # the effective catalog the ranker would see after this one write.
    original_by_dest = {
        "lanes": lanes_doc,
        "routing": routing_doc,
        "project": project_doc if project_doc is not None else {},
        "project_lanes": project_lanes_doc if project_lanes_doc is not None else {},
    }
    proposed_by_dest = {
        "lanes": proposed_lanes,
        "routing": proposed_routing,
        "project": proposed_project if proposed_project is not None else {},
        "project_lanes": (
            proposed_project_lanes if proposed_project_lanes is not None else {}
        ),
    }

    after_cat = plan["catalog"]
    before_cat = _catalog_from_docs(
        lanes_doc, routing_doc, project_doc, files, project_lanes_doc
    )
    present_set = _present_harnesses(present)
    meters_doc = _cached_meters(meters)
    picks_before, leaders_before = _rank_preview(before_cat, meters_doc, present_set)
    picks_after, leaders_after = _rank_preview(after_cat, meters_doc, present_set)
    observations, missing = _observations_report(meters_doc, before_cat["meters"])
    # a harness this catalog runs no Lane on cannot change a Pick, so its
    # absence is not news
    in_catalog = {lane.get("harness") for lane in (after_cat.get("lanes") or {}).values()}
    unavailable = sorted(h for h in harnesses.NAMES if h not in present_set and h in in_catalog)

    changed = _changed_fields(
        op,
        values,
        original_by_dest[dest],
        proposed_by_dest[dest],
        dest,
    )
    noop = proposed_by_dest[dest] == original_by_dest[dest]
    if dest == "project" and project_doc is None:
        noop = proposed_project in (None, {})
        if proposed_project:
            noop = False
    # An empty customization over an absent file writes no empty file.
    if dest == "project_lanes" and project_lanes_doc is None:
        noop = not (proposed_project_lanes or {}).get("lanes")

    target = _target(snap, dest)
    written = False
    if apply and not noop:
        try:
            done = catalog_commit.commit(snap, {dest: proposed_by_dest[dest]})
        except catalog_commit.CatalogChanged as e:
            raise catalog.CatalogError(INTERVENING_EDIT) from e
        # the Agent files and notes go to stderr, so the JSON on stdout stays
        # the result alone
        for line in done.lines:
            sys.stderr.write(f"{line}\n")
        written = True

    return {
        "op": op,
        "scope": scope,
        "revision": snap.revision,
        "target": target,
        "sources": {name: (None if snap.sources[name] is None else dict(snap.sources[name]))
                    for name in catalog_commit.DOCUMENTS},
        "values": values,
        "changed": changed,
        "picks": {"before": picks_before, "after": picks_after},
        "leaders": {"before": leaders_before, "after": leaders_after},
        "unavailable_harnesses": unavailable,
        "missing_observations": missing,
        "observations": observations,
        "noop": noop,
        "written": written,
    }
