#!/usr/bin/env python3
"""catalog_cli.py — `delegate catalog`: show, check, check-guide, fmt, and the
set/range/order edits.

CLI forms:
  delegate catalog show [--cwd DIR] [--config-dir DIR] [--json]
  delegate catalog check FILE [--partial]   (warns when one Meter serves a whole Tier)
  delegate catalog check-guide [FILE] [--overlay] [--cwd DIR] [--config-dir DIR]
      no FILE: every guide together against the effective routing
  delegate catalog fmt FILE [--partial]
  delegate catalog set FIELD JSON_VALUE --scope global|project [--cwd DIR] [--config-dir DIR]
      FIELD is lanes.<lane>.tier, routing.gate, routing.margin, routing.meters,
      or routing.overflow
  delegate catalog range CLASS FLOOR CEILING --scope global|project [--cwd DIR] [--config-dir DIR]
  delegate catalog order LANE POSITION --scope global|project [--cwd DIR] [--config-dir DIR]
  (set/range/order default to a JSON preview; --apply --expect REVISION writes)
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import catalog_edit  # noqa: E402
import class_guides  # noqa: E402


def show_catalog(cwd=None, config_dir=None, as_json=False):
    """Prints effective catalog for cwd. If as_json, prints formatted JSON."""
    cat = catalog.load_catalog(cwd=cwd, config_dir=config_dir)
    if as_json:
        sys.stdout.write(catalog.format_json(cat))
        return

    print("# meters")
    for name, m in cat["meters"].items():
        print(f"{name}  {m['harness']}  {m['plan']}  {m['price_month']}")

    print("\n# lanes")
    sorted_lanes = sorted(
        cat["lanes"].items(),
        key=lambda item: (
            -item[1]["tier"],
            item[1].get("order") is None,
            item[1].get("order", 0),
            item[0],
        ),
    )
    for name, l in sorted_lanes:
        order = l.get("order")
        order_source = cat["sources"].get(f"lanes.{name}.order", "")
        order_text = f"  order={order}  {order_source}" if order is not None else ""
        print(
            f"{name}  {l['tier']}  {l['harness']}  {l['model']}  "
            f"{l['effort']}  {l['meter']}  {l['meter_weight']}  {l['timeout']}  "
            f"{l['basis']}{order_text}"
        )

    project_tiers = cat.get("project_tiers") or {}
    if project_tiers:
        moved = "  ".join(
            f"{name} {change['from']} -> {change['to']}"
            for name, change in sorted(project_tiers.items())
        )
        print(f"\n# project tier in effect: {moved}  "
              f"{cat['files'].get('project_lanes') or ''}")

    print("\n# routing")
    routing = cat["routing"]
    sources = cat["sources"]
    for k in ("version", "margin", "gate"):
        if k in routing:
            src = sources.get(k, "")
            print(f"{k}: {routing[k]}  {src}")
    if "classes" in routing and isinstance(routing["classes"], dict):
        for cls in catalog.class_names(routing):
            if cls in routing["classes"]:
                c_val = routing["classes"][cls]
                if isinstance(c_val, dict):
                    f_val = c_val.get("floor")
                    c_val_ceil = c_val.get("ceiling")
                    f_src = sources.get(f"classes.{cls}.floor", sources.get(f"classes.{cls}", sources.get("classes", "")))
                    c_src = sources.get(f"classes.{cls}.ceiling", sources.get(f"classes.{cls}", sources.get("classes", "")))
                    if f_src == c_src:
                        print(f"classes.{cls}: floor={f_val} ceiling={c_val_ceil}  {f_src}")
                    else:
                        print(f"classes.{cls}.floor: {f_val}  {f_src}")
                        print(f"classes.{cls}.ceiling: {c_val_ceil}  {c_src}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="delegate catalog",
        description="Delegate catalog and routing management."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="show effective catalog")
    p_show.add_argument("--cwd", default=None, help="working directory to find git root from")
    p_show.add_argument("--config-dir", default=None, help="config directory containing lanes.json and routing.json")
    p_show.add_argument("--json", action="store_true", help="output effective catalog as formatted JSON")

    p_check = sub.add_parser("check", help="validate a catalog or routing file")
    p_check.add_argument("file", help="path to file to check")
    p_check.add_argument("--partial", action="store_true", help="allow partial routing file")

    p_guide = sub.add_parser("check-guide", help="validate a class guide")
    p_guide.add_argument(
        "file",
        nargs="?",
        default=None,
        help="path to classes.md (default: this skill's assets/classes.md)",
    )
    p_guide.add_argument(
        "--overlay",
        action="store_true",
        help="a global or project overlay: class sections name Classes the routing defines",
    )
    p_guide.add_argument("--cwd", default=None, help="working directory to find git root from")
    p_guide.add_argument("--config-dir", default=None,
                         help="config directory containing routing.json and classes.md")

    p_fmt = sub.add_parser("fmt", help="format and validate a catalog or routing file")
    p_fmt.add_argument("file", help="path to file to format")
    p_fmt.add_argument("--partial", action="store_true", help="allow partial routing file")

    def add_edit_flags(p):
        p.add_argument(
            "--scope",
            required=True,
            choices=("global", "project"),
            help="which source document to change",
        )
        p.add_argument("--cwd", default=None, help="working directory to find git root from")
        p.add_argument(
            "--config-dir",
            default=None,
            help="config directory containing lanes.json and routing.json",
        )
        p.add_argument("--apply", action="store_true", help="write the selected source document")
        p.add_argument("--expect", default=None, help="revision from a preview of the same sources")

    p_set = sub.add_parser("set", help="preview or apply one allowed field edit")
    p_set.add_argument(
        "field",
        help="lanes.<lane>.tier, routing.gate, routing.margin, routing.meters, "
             "or routing.overflow",
    )
    p_set.add_argument("value", help="JSON value")
    add_edit_flags(p_set)

    p_range = sub.add_parser("range", help="preview or apply a paired Floor and Ceiling")
    p_range.add_argument("cls", metavar="CLASS", help="class name")
    p_range.add_argument("floor", type=int, help="new floor")
    p_range.add_argument("ceiling", type=int, help="new ceiling")
    add_edit_flags(p_range)

    p_order = sub.add_parser("order", help="preview or apply a one-based Order in a Tier")
    p_order.add_argument("lane", help="carried lane name")
    p_order.add_argument("position", type=int, help="one-based position among carried lanes in the Tier")
    add_edit_flags(p_order)

    args = parser.parse_args(argv)

    try:
        if args.cmd == "show":
            show_catalog(cwd=args.cwd, config_dir=args.config_dir, as_json=args.json)
        elif args.cmd == "check":
            doc = catalog.check_file(args.file, partial=args.partial)
            # Coverage warnings, never failures: a valid catalog can still
            # leave a Tier resting on one Meter (ticket 29). They go to stderr
            # so that `ok: <file>` stays the whole of this command's stdout.
            for line in catalog.meter_dependency_lines(doc.get("lanes"), names=True):
                sys.stderr.write(f"warning: {line}\n")
            if doc.get("version") == catalog.ROUTING_VERSION:
                class_guides.check_routing_guides(args.file, doc)
            print(f"ok: {args.file}")
        elif args.cmd == "check-guide":
            classes = class_guides._effective_class_names(args.cwd, args.config_dir)
            if args.file is not None:
                class_guides.validate_guide(args.file, overlay=args.overlay,
                               classes=classes if args.overlay else None)
                print(f"ok: {args.file}")
            else:
                guides = class_guides.guide_files(cwd=args.cwd, config_dir=args.config_dir)
                class_guides.check_class_guides(classes, guides)
                for path, _overlay in guides:
                    print(f"ok: {path}")
        elif args.cmd == "fmt":
            catalog.fmt_file(args.file, partial=args.partial)
            print(f"formatted: {args.file}")
        elif args.cmd in ("set", "range", "order"):
            kwargs = {
                "scope": args.scope,
                "cwd": args.cwd,
                "config_dir": args.config_dir,
                "apply": args.apply,
                "expect": args.expect,
            }
            if args.cmd == "set":
                def _reject_constant(c):
                    raise ValueError(f"{c} is not allowed in strict JSON")
                try:
                    value = json.loads(args.value, parse_constant=_reject_constant)
                except json.JSONDecodeError as e:
                    raise catalog.CatalogError(
                        f"value is not strict JSON: {e.msg} at column {e.colno}"
                    )
                except ValueError as e:
                    raise catalog.CatalogError(f"value is not strict JSON: {e}")
                result = catalog_edit.edit_catalog("set", field=args.field, value=value, **kwargs)
            elif args.cmd == "range":
                result = catalog_edit.edit_catalog(
                    "range", cls=args.cls, floor=args.floor, ceiling=args.ceiling, **kwargs
                )
            else:
                result = catalog_edit.edit_catalog(
                    "order", lane=args.lane, position=args.position, **kwargs
                )
            sys.stdout.write(catalog.format_json(result))
    except catalog.CatalogError as e:
        sys.stderr.write(f"catalog: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
