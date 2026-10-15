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
already wrote. Then, when the documents include the global lanes document of
the live catalog (the config dir resolves to `catalog.CONFIG_DIR`), it gives
every native Lane after the commit its Agent file, a plain file in its
profile's template, and removes the file of each native Lane the commit took
out; another catalog gets one note line. Last, it forgets the Model queue
entries the read returned (`read(queue=True)`), and keeps any added since. A
failure in those two steps is a note line, never an error: the catalog is
already written. Callers print `Committed.lines` to stderr.

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
import harnesses  # noqa: E402
import model_queue  # noqa: E402
import orchestrators  # noqa: E402

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
    queued: Tuple[dict, ...] = ()  # models dispatch noticed, only when read with queue=True
    applied: Tuple[dict, ...] = () # Model swaps the scan applied, only when read with queue=True
    # the bytes read for each document, and the config dir: the commit
    # compares against these, never against the dicts above
    _contents: Mapping[str, Optional[bytes]] = field(default_factory=dict, repr=False, compare=False)
    _config_dir: str = field(default="", repr=False, compare=False)


@dataclass(frozen=True)
class Committed:
    written: Tuple[str, ...]   # paths of the documents written, in DOCUMENTS order; () when none changed
    lines: Tuple[str, ...]     # one per Agent file written, updated or removed, and each note


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


def read(config_dir: Optional[str] = None, *, project_dir: Optional[str] = None,
         queue: bool = False) -> CatalogRead:
    """The catalog as one session reads it.

    The global pair always comes from `config_dir` (default
    `catalog.CONFIG_DIR`); the project pair only when `project_dir` is given
    and a Git root is found above it. An absent document reads as None.
    `queue` also reads the Model queue, which a commit through this read then
    forgets; a queue that cannot be read counts as empty.
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
    queued, applied = _read_queue() if queue else ((), ())
    return CatalogRead(
        lanes=docs["lanes"], routing=docs["routing"], project=docs["project"],
        project_lanes=docs["project_lanes"],
        files=paths, sources={name: _public(descs[name]) for name in DOCUMENTS},
        git_root=git_root, revision=hasher.hexdigest(),
        queued=queued, applied=applied,
        _contents=contents, _config_dir=base,
    )


def _read_queue():
    """(the queued models, the applied Model swaps); both empty when the
    queue cannot be read."""
    try:
        return tuple(model_queue.pending()), tuple(model_queue.applied())
    except (OSError, ValueError, TypeError):
        return (), ()


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
    found a Git root. Returns the paths written, in DOCUMENTS order, and the
    lines the Agent files and the queue gave."""
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
    moved = []
    for name in DOCUMENTS:
        try:
            now = None if snap.files[name] is None else _describe(snap.files[name])
        except catalog.CatalogError:
            moved.append(name)
        else:
            if now != _seen(snap, name):
                moved.append(name)
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
        except BaseException:
            _restore(snap, written)
            raise
        written.append(name)
    # The catalog is written: from here on a failure is a note line, never an
    # error, so these two steps catch any Exception (a machine-local profile
    # can fail in ways no narrower class names).
    lines = []
    if "lanes" in documents:
        lines += _sync_agents(snap, documents["lanes"])
    if snap.queued or snap.applied:
        try:
            model_queue.forget(snap.queued, snap.applied)
        except Exception as e:
            lines.append(f"note: could not forget the model queue entries this run named: {_why(e)}")
    return Committed(written=tuple(snap.files[name] for name in written), lines=tuple(lines))


def _why(error):
    """How a note names an exception: an OSError's message already says what
    failed; any other gets its class too, since a KeyError's message is only
    the key."""
    if isinstance(error, OSError):
        return str(error)
    return f"{type(error).__name__}: {error}"


def _is_live(config_dir):
    """Whether `config_dir` is this machine's live catalog, `catalog.CONFIG_DIR`."""
    live = os.path.expanduser(catalog.CONFIG_DIR)
    return os.path.realpath(config_dir) == os.path.realpath(live)


def _native(lanes, harness):
    """The names of the Lanes in `lanes` on `harness`, in catalog order."""
    return [name for name, lane in (lanes or {}).items()
            if isinstance(lane, dict) and lane.get("harness") == harness]


def _sync_agents(snap, lanes_doc):
    """The Agent files (decisions D.2 and D.7): every native Lane in
    `lanes_doc` gets its Agent file, and every native Lane the read had that
    `lanes_doc` lacks loses its file. Only the live catalog has Agent files:
    the profile's agents directory is that catalog's, so another catalog gets
    one note. Returns the lines; a failure is a note line, never an error."""
    try:
        profiles = orchestrators.native_profiles()
    except Exception as e:
        return [f"note: no agent file was written: {_why(e)}"]
    after = lanes_doc.get("lanes") or {}
    before = (_as_read(snap, "lanes") or {}).get("lanes") or {}
    if not _is_live(snap._config_dir):
        waiting = {profile["harness"]: len(_native(after, profile["harness"])) for profile in profiles}
        count = sum(waiting.values())
        if not count:
            return []
        named = "/".join(harness for harness, n in waiting.items() if n)
        lanes = f"{named} lane needs" if count == 1 else f"{named} lanes need"
        return [f"note: {count} {lanes} an agent file; this catalog is not the live one, "
                "so none was written"]
    lines = []
    for profile in profiles:
        agents_dir = os.path.expanduser(profile["native"]["agents_dir"])
        for name in _native(after, profile["harness"]):
            try:
                line = _place_agent(orchestrators.agent_path(profile, name, agents_dir),
                                    _agent_text(profile, name, after[name]))
            except Exception as e:
                line = f"note: could not write the agent file of {name}: {_why(e)}"
            if line:
                lines.append(line)
        for name in _native(before, profile["harness"]):
            if name in after:
                continue
            try:
                path = orchestrators.agent_path(profile, name, agents_dir)
                if os.path.lexists(path):
                    os.remove(path)
                    lines.append(f"removed {path}")
            except Exception as e:
                lines.append(f"note: could not remove the agent file of {name}: {_why(e)}")
    return lines


def _agent_text(profile, name, lane):
    """A native Lane's Agent file from its profile's template. A model its
    harness runs with no effort level carries no `effort` line."""
    adapter = harnesses.get(lane.get("harness"))
    takes_effort = adapter is None or adapter.model_takes_effort(lane["model"])
    return orchestrators.agent_text(profile, name, lane["model"],
                                    lane["effort"] if takes_effort else None)


def _place_agent(path, text):
    """Make `path` a plain file holding `text`, and say what changed: None
    when it already held it. A link there is replaced, never written
    through: a profile's agents directory holds links into repositories (a
    stowed agents package, the courier), and a Lane's Agent file is
    machine-local (ADR 0001)."""
    if os.path.islink(path):
        os.remove(path)
        verb = "wrote"
    elif os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return None
        verb = "updated"
    else:
        verb = "wrote"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return f"{verb} {path}"


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
