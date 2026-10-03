#!/usr/bin/env python3
"""class_guides.py — the Class guides (`assets/classes.md` and its overlays)
checked against the effective routing: every Class has one section, and no
guide declares a Floor or Ceiling, which belong in routing.json. Split out of
catalog.py (ticket 26); `delegate catalog check-guide` runs it.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402

# Class sections in assets/classes.md (and a project overlay) are ATX headings
# at this level, named exactly as CLASSES. Other heading levels are metadata
# and are not checked against the registry, so "How to pick" cannot collide.
CLASS_GUIDE_HEADING_LEVEL = 2
ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*$")
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# Floor/Ceiling integers belong in routing.json. A `floor:` / `ceiling:` (or
# `=`) declaration in the guide is how numeric policy drifted before.
FLOOR_CEILING_DECL = re.compile(r"(?i)\b(floor|ceiling)\s*[:=]\s*\d+")


def default_class_guide_path():
    """Shipped Class guide beside this script: ../assets/classes.md."""
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "classes.md")
    )


def _iter_guide_headings(text):
    """Yield (lineno, level, title) for ATX headings outside fenced code."""
    in_fence = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        fence = FENCE_OPEN.match(raw)
        if fence:
            mark = fence.group(1)
            ch, n = mark[0], len(mark)
            if in_fence is None:
                in_fence = (ch, n)
            elif ch == in_fence[0] and n >= in_fence[1]:
                in_fence = None
            continue
        if in_fence is not None:
            continue
        matched = ATX_HEADING.match(raw)
        if not matched:
            continue
        title = re.sub(r"\s+#+\s*$", "", matched.group(2)).strip()
        if not title:
            continue
        yield lineno, len(matched.group(1)), title


def validate_guide_text(text, source="classes.md", overlay=False, classes=None):
    """Validate Class-guide markdown. The shipped guide's headings must equal
    catalog.CLASSES; an overlay's must be a subset of `classes` (the effective
    routing's, catalog.CLASSES when not given). Metadata headings are any other level."""
    if not isinstance(text, str):
        raise catalog.CatalogError(f"{source}: document: class guide must be markdown text")

    decl = FLOOR_CEILING_DECL.search(text)
    if decl:
        line = text.count("\n", 0, decl.start()) + 1
        kind = decl.group(1).lower()
        raise catalog.CatalogError(
            f"{source}: line {line}: '{kind}' integer is routing.json policy; "
            "the guide must not declare Floor or Ceiling"
        )

    found = []
    seen = {}
    known = tuple(classes) if classes is not None else catalog.CLASSES
    allowed = ", ".join(known)
    for lineno, level, title in _iter_guide_headings(text):
        if level != CLASS_GUIDE_HEADING_LEVEL:
            continue
        if title in seen:
            raise catalog.CatalogError(
                f"{source}: heading '## {title}': duplicate class section "
                f"(first at line {seen[title]})"
            )
        if title not in known:
            raise catalog.CatalogError(
                f"{source}: heading '## {title}': unknown class; class sections "
                f"must be one of {allowed} (a new Class needs a floor and a ceiling "
                "in routing.json first)"
            )
        seen[title] = lineno
        found.append(title)

    names = tuple(found)
    if overlay:
        return names

    missing = [c for c in catalog.CLASSES if c not in seen]
    if missing:
        raise catalog.CatalogError(
            f"{source}: classes: missing required class '{missing[0]}'"
        )
    return names


def validate_guide(path, overlay=False, classes=None):
    """Validate one Class guide file. overlay=True for a global or project
    overlay, whose sections name Classes in `classes`."""
    expanded = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(expanded):
        raise catalog.CatalogError(f"{path}: file is missing")
    try:
        with open(expanded, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        raise catalog.CatalogError(f"{path}: file: cannot read: {e}")
    validate_guide_text(text, source=path, overlay=overlay, classes=classes)
    return text


def _effective_class_names(cwd=None, config_dir=None):
    """The effective routing's Classes, or the shipped five when this machine
    has no routing.json yet."""
    base_dir = os.path.expanduser(config_dir if config_dir is not None else catalog.CONFIG_DIR)
    if not os.path.isfile(os.path.join(base_dir, "routing.json")):
        return list(catalog.CLASSES)
    routing, _sources = catalog.effective_routing(cwd=cwd, config_dir=config_dir)
    return catalog.class_names(routing)


def check_routing_guides(path, doc):
    """`check` on a routing file: each Class it adds has a section in a Class
    guide, the shipped one, the classes.md beside the file, or this machine's."""
    classes = catalog.class_names(catalog.with_default_classes(doc))
    try:
        classes += [c for c in _effective_class_names() if c not in classes]
    except catalog.CatalogError:
        pass
    guides = [(default_class_guide_path(), False)]
    for candidate in (os.path.join(os.path.dirname(os.path.abspath(path)), "classes.md"),
                      os.path.join(os.path.expanduser(catalog.CONFIG_DIR), "classes.md")):
        if os.path.isfile(candidate) and all(not os.path.samefile(candidate, g) for g, _ in guides):
            guides.append((candidate, True))
    return check_class_guides(classes, guides)


def guide_files(cwd=None, config_dir=None):
    """[(path, overlay)] for every Class guide in effect: the shipped one, then
    this machine's (<catalog.CONFIG_DIR>/classes.md) and the project's
    (.delegate/classes.md) when they exist."""
    base_dir = os.path.expanduser(config_dir if config_dir is not None else catalog.CONFIG_DIR)
    out = [(default_class_guide_path(), False)]
    global_guide = os.path.join(base_dir, "classes.md")
    if os.path.isfile(global_guide):
        out.append((global_guide, True))
    git_root = catalog.find_git_root(cwd)
    if git_root:
        project_guide = os.path.join(git_root, ".delegate", "classes.md")
        if os.path.isfile(project_guide):
            out.append((project_guide, True))
    return out


def check_class_guides(classes, guides):
    """Validate the Class guides together against the effective routing's
    Classes: every Class has a section in some guide, and every overlay
    section names a Class with a Range. Raises catalog.CatalogError naming the Class;
    returns {class: the guide that holds its section}."""
    found = {}
    for path, overlay in guides:
        text = validate_guide(path, overlay=overlay, classes=classes if overlay else None)
        names = validate_guide_text(text, source=path, overlay=overlay,
                                    classes=classes if overlay else None)
        for name in names:
            found.setdefault(name, path)
    for name in classes:
        if name not in found:
            paths = ", ".join(path for path, _ in guides)
            raise catalog.CatalogError(
                f"classes: class '{name}' has a floor and a ceiling in routing.json but "
                f"no '## {name}' section in any Class guide ({paths})"
            )
    return found
