#!/usr/bin/env python3
"""catalog_commit.py — the Catalog read and the Catalog commit (deepening D).

`read()` takes the catalog's documents as one session sees them: each file's
bytes, where its path resolves, and one revision over them all. Every present
document is strict JSON and passes the catalog validators, and a dangling link
or a link loop at a document's path is refused.

`commit(read, documents)` writes whole documents back against that read, in
this order: it validates them with the read side's validators; refuses an
Intervening edit (`CatalogChanged`) when any document the read saw differs on
disk; skips a document equal to its read; copies each global document it
replaces to `<config dir>/backups/<name>-<UTC stamp>.json`, keeping the newest
twenty per document; writes each one atomically, through a link to an existing
file (`catalog.write_json`); and when a later write fails, puts back what it
already wrote. Callers print `Committed.lines` to stderr.

This is not a lock: a writer outside delegate can still race the last check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import sys
import tempfile
from typing import Mapping, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402

# The documents a read holds and a commit may write, in the order both handle them.
DOCUMENTS = ("lanes", "routing", "project", "project_lanes")
# The global pair, the only documents a commit backs up (decision D.5).
_GLOBAL = ("lanes", "routing")
_PROJECT_FILES = {"project": "routing.json", "project_lanes": "lanes.json"}
# How many backups of each global document a commit keeps.
BACKUPS_KEPT = 20
_BACKUP_NAME = re.compile(r"^(lanes|routing)-\d{8}T\d{6}\.\d{6}Z\.json$")


class CatalogChanged(catalog.CatalogError):
    """An Intervening edit: a document the read saw differs on disk."""

    def __init__(self, changed, files):
        self.changed = tuple(name for name in DOCUMENTS if name in changed)
        named = ", ".join(files[name] for name in self.changed)
        super().__init__(f"intervening edit: {named} changed since the catalog was read")


@dataclass(frozen=True)
class CatalogRead:
    """The catalog's documents as one session read them. The dicts belong to
    the caller and may be changed; a commit never compares against them."""
    lanes: Optional[dict]          # None when lanes.json is absent (a first run)
    routing: Optional[dict]
    project: Optional[dict]        # None when absent, or when no project was read
    project_lanes: Optional[dict]
    files: Mapping[str, Optional[str]]     # each document's path as named
    sources: Mapping[str, Optional[dict]]  # {file, resolved, symlink, exists}, as previews print them
    git_root: Optional[str]
    revision: str                  # one sha256 over every document read
    # the bytes read for each document, and the config dir: the commit
    # compares against these, never against the dicts above
    _contents: Mapping[str, Optional[bytes]] = field(default_factory=dict, repr=False, compare=False)
    _config_dir: str = field(default="", repr=False, compare=False)


@dataclass(frozen=True)
class Committed:
    written: Tuple[str, ...]   # paths of the documents written, in DOCUMENTS order; () when none changed
    lines: Tuple[str, ...]     # lines for the caller to print to stderr


def _describe(path):
    """{file, resolved, symlink, exists, content} for one document path. A
    dangling link or a loop there raises CatalogError (`catalog.link_target`)."""
    abs_path = os.path.abspath(os.path.expanduser(path))
    is_link = os.path.islink(abs_path)
    if is_link:
        catalog.link_target(abs_path)
    is_file = os.path.isfile(abs_path)
    resolved = os.path.realpath(abs_path) if (is_link or is_file or os.path.lexists(abs_path)) else None
    content = None
    if is_file:
        try:
            with open(abs_path, "rb") as f:
                content = f.read()
        except OSError as e:
            raise catalog.CatalogError(f"{path}: file: cannot read: {e}")
    return {"file": abs_path, "resolved": resolved, "symlink": is_link,
            "exists": is_file, "content": content}


def _public(desc):
    if desc is None:
        return None
    return {key: desc[key] for key in ("file", "resolved", "symlink", "exists")}


def _hash(hasher, key, desc):
    hasher.update(key.encode("utf-8"))
    hasher.update(b"\0")
    if desc is None:
        hasher.update(b"ABSENT\0")
        return
    for part in (desc["file"], desc["resolved"] or ""):
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\0")
    hasher.update(b"1" if desc["symlink"] else b"0")
    hasher.update(b"\0")
    hasher.update(b"1" if desc["exists"] else b"0")
    hasher.update(b"\0")
    hasher.update(desc["content"] or b"")
    hasher.update(b"\0")


def _loads(content, path):
    """Parse a document's bytes with load_json's strict JSON rules."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise catalog.CatalogError(f"{path}: file: cannot read: {e}")

    def _reject_constant(c):
        raise ValueError(f"{c} is not allowed in strict JSON")

    try:
        return json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as e:
        raise catalog.CatalogError(
            f"{path}: line {e.lineno}, column {e.colno}: JSON syntax error: {e.msg}"
        )
    except ValueError as e:
        raise catalog.CatalogError(f"{path}: number: NaN is not allowed in strict JSON ({e})")


def _paths(config_dir, git_root):
    base = os.path.abspath(os.path.expanduser(config_dir))
    paths = {"lanes": os.path.join(base, "lanes.json"),
             "routing": os.path.join(base, "routing.json"),
             "project": None, "project_lanes": None}
    if git_root is not None:
        for name, file_name in _PROJECT_FILES.items():
            paths[name] = os.path.join(git_root, ".delegate", file_name)
    return paths


def _describe_all(paths):
    return {name: (None if paths[name] is None else _describe(paths[name])) for name in DOCUMENTS}


def _validate(docs, files, names):
    """The read side's validators over the documents `names` picks out of
    `docs`: each global document on its own, each project document against the
    global pair in `docs` when that pair is there. A named document that is
    None is a present `null`, which is invalid, not absent."""
    lanes, routing = docs["lanes"], docs["routing"]
    if "project" in names:
        catalog.validate_routing(docs["project"], source=files["project"], partial=True)
    if "lanes" in names:
        catalog.validate_lanes(lanes, source=files["lanes"])
    if "routing" in names:
        catalog.validate_routing(routing, source=files["routing"], partial=False)
    if lanes is None:
        return
    if "project_lanes" in names:
        catalog.validate_project_lanes(docs["project_lanes"], lanes, source=files["project_lanes"],
                                       lanes_source=files["lanes"])
    if "project" in names and routing is not None:
        catalog.validate_project_routing(docs["project"], lanes, routing, source=files["project"],
                                         lanes_source=files["lanes"], global_source=files["routing"])


def read(config_dir: Optional[str] = None, *, project_dir: Optional[str] = None) -> CatalogRead:
    """The catalog as one session reads it.

    The global pair always comes from `config_dir` (default
    `catalog.CONFIG_DIR`); the project pair only when `project_dir` is given
    and a Git root is found above it. An absent document reads as None.
    """
    base = os.path.abspath(os.path.expanduser(
        config_dir if config_dir is not None else catalog.CONFIG_DIR))
    git_root = catalog.find_git_root(project_dir) if project_dir is not None else None
    paths = _paths(base, git_root)
    descs = _describe_all(paths)
    hasher = hashlib.sha256()
    for name in DOCUMENTS:
        _hash(hasher, name, descs[name])
    contents = {name: (None if descs[name] is None else descs[name]["content"]) for name in DOCUMENTS}
    present = [name for name in DOCUMENTS if contents[name] is not None]
    docs = {name: (_loads(contents[name], paths[name]) if name in present else None)
            for name in DOCUMENTS}
    _validate(docs, paths, present)
    return CatalogRead(
        lanes=docs["lanes"], routing=docs["routing"], project=docs["project"],
        project_lanes=docs["project_lanes"],
        files=paths, sources={name: _public(descs[name]) for name in DOCUMENTS},
        git_root=git_root, revision=hasher.hexdigest(),
        _contents=contents, _config_dir=base,
    )


def _as_read(snap, name):
    """A document as the read parsed it, from its bytes: None when absent."""
    content = snap._contents[name]
    return None if content is None else _loads(content, snap.files[name])


def _seen(snap, name):
    """A document's description as the read saw it, bytes included."""
    source = snap.sources[name]
    return None if source is None else dict(source, content=snap._contents[name])


def _backup(snap, name):
    """Copy a global document's read bytes to <config dir>/backups, then keep
    only the newest BACKUPS_KEPT of that document. The stamp sorts as the time
    does, so the file names alone say which are newest."""
    folder = os.path.join(snap._config_dir, "backups")
    os.makedirs(folder, exist_ok=True)
    when = datetime.now(timezone.utc)
    while True:
        target = os.path.join(folder, f"{name}-{when.strftime('%Y%m%dT%H%M%S.%fZ')}.json")
        try:
            with open(target, "xb") as f:
                f.write(snap._contents[name])
            break
        except FileExistsError:
            when += timedelta(microseconds=1)
    kept = sorted(f for f in os.listdir(folder) if _BACKUP_NAME.match(f) and f.startswith(f"{name}-"))
    for old in kept[:-BACKUPS_KEPT]:
        os.remove(os.path.join(folder, old))


def commit(read: CatalogRead, documents: Mapping[str, dict]) -> Committed:
    """Write `documents`, names from DOCUMENTS to whole documents, against
    `read`. A name left out keeps its file; a project name needs a read that
    found a Git root. Returns the paths written, in DOCUMENTS order."""
    snap = read
    for name, doc in documents.items():
        if name not in DOCUMENTS:
            raise catalog.CatalogError(
                f"unknown catalog document '{name}'; documents are {', '.join(DOCUMENTS)}")
        if snap.files[name] is None:
            raise catalog.CatalogError(
                f"the {name} document needs a read that found a Git root")
        if doc is None:
            raise catalog.CatalogError(f"the {name} document to write is missing")
    after = {name: documents[name] if name in documents else _as_read(snap, name)
             for name in DOCUMENTS}
    _validate(after, snap.files, names=tuple(documents))
    # every document the read saw, described again: bytes, link, resolved
    # path and presence
    now = _describe_all(snap.files)
    moved = [name for name in DOCUMENTS if now[name] != _seen(snap, name)]
    if moved:
        raise CatalogChanged(moved, snap.files)
    changed = [name for name in DOCUMENTS
               if name in documents and documents[name] != _as_read(snap, name)]
    for name in changed:
        if name in _GLOBAL and snap._contents[name] is not None:
            try:
                _backup(snap, name)
            except OSError as e:
                raise catalog.CatalogError(
                    f"{snap.files[name]}: cannot back it up before the write: {e}; nothing written")
    written = []
    for name in changed:
        try:
            catalog.write_json(snap.files[name], documents[name])
        except (OSError, catalog.CatalogError) as e:
            raise catalog.CatalogError(
                f"{snap.files[name]}: cannot write: {e}; {_restore(snap, written)}") from e
        written.append(name)
    return Committed(written=tuple(snap.files[name] for name in written), lines=())


def _restore(snap, names):
    """Put the documents `names` back as the read saw them, and say what
    happened: the bytes go back where the read resolved them, and a document
    the read found absent is removed again."""
    if not names:
        return "nothing written"
    back, failed = [], []
    for name in names:
        path = snap.files[name]
        try:
            if snap._contents[name] is None:
                os.remove(path)
            else:
                _write_bytes(snap.sources[name]["resolved"], snap._contents[name])
            back.append(path)
        except OSError as e:
            failed.append(f"{path} ({e})")
    said = f"put back as read: {', '.join(back)}" if back else ""
    if failed:
        said = f"{said}; could not put back: {', '.join(failed)}".lstrip("; ")
    return said


def _write_bytes(path, data):
    """Replace the file at `path` with `data` atomically."""
    fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_catalog_")
    try:
        with open(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
