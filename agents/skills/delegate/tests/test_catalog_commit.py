#!/usr/bin/env python3
"""test_catalog_commit.py — the one write of catalog documents (deepening D).

Every case runs on a temp config dir copied from assets/samples, never the live
catalog. Run: python3 tests/test_catalog_commit.py
"""
import copy
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so no read finds the
# invoking checkout's own `.delegate/` documents.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
sys.path.insert(0, SCRIPTS)
import catalog  # noqa: E402
import catalog_commit  # noqa: E402

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def sample_config(root, name="cfg"):
    """A config dir holding the sample lanes.json and routing.json."""
    cfg = os.path.join(root, name)
    os.makedirs(cfg)
    for doc in ("lanes.json", "routing.json"):
        shutil.copy(os.path.join(SAMPLES, doc), cfg)
    return cfg


def paths(cfg):
    return os.path.join(cfg, "lanes.json"), os.path.join(cfg, "routing.json")


def on_disk(path):
    """A file's bytes and mtime, which a document the commit skips keeps."""
    with open(path, "rb") as f:
        return f.read(), os.stat(path).st_mtime_ns


def with_tier(doc, lane, tier):
    doc = copy.deepcopy(doc)
    doc["lanes"][lane]["tier"] = tier
    return doc


def case_a_commit_writes_only_the_documents_that_changed():
    """A document handed back equal to its read keeps its bytes and mtime; a
    commit with no change writes nothing at all."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_config(td)
        lanes_path, routing_path = paths(cfg)
        routing_before = on_disk(routing_path)
        snap = catalog_commit.read(cfg)
        lanes = with_tier(snap.lanes, "terra-high@codex", 1)
        done = catalog_commit.commit(snap, {"lanes": lanes, "routing": copy.deepcopy(snap.routing)})
        lanes_after = on_disk(lanes_path)
        again = catalog_commit.commit(catalog_commit.read(cfg), {"lanes": lanes})
        ok = (done.written == (lanes_path,)
              and catalog.load_json(lanes_path)["lanes"]["terra-high@codex"]["tier"] == 1
              and on_disk(routing_path) == routing_before
              and again.written == () and on_disk(lanes_path) == lanes_after)
        return ok, f"written={done.written} again={again.written}"


def refusal(fn, *args):
    """The CatalogError `fn` raised, or None."""
    try:
        fn(*args)
    except catalog.CatalogError as e:
        return e
    return None


def case_an_intervening_edit_is_refused_and_nothing_is_written():
    """A document the read saw that differs on disk at the commit is an
    Intervening edit: CatalogChanged names it, and no document is written, the
    one that did not change included."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_config(td)
        lanes_path, routing_path = paths(cfg)
        snap = catalog_commit.read(cfg)
        # a catalog set lands between the read and the commit
        catalog.write_json(lanes_path, with_tier(snap.lanes, "sol-high@codex", 1))
        theirs, routing_before = on_disk(lanes_path), on_disk(routing_path)
        routing = copy.deepcopy(snap.routing)
        routing["gate"] = 0.2
        e = refusal(catalog_commit.commit, snap,
                    {"lanes": with_tier(snap.lanes, "terra-high@codex", 1), "routing": routing})
        ok = (isinstance(e, catalog_commit.CatalogChanged) and e.changed == ("lanes",)
              and lanes_path in str(e)
              and on_disk(lanes_path) == theirs and on_disk(routing_path) == routing_before)
        return ok, repr(e)


def linked_config(root):
    """A config dir whose two documents are links to files in another folder,
    as a machine-local catalog the user placed elsewhere is."""
    real = sample_config(root, "real")
    cfg = os.path.join(root, "cfg")
    os.makedirs(cfg)
    for name in ("lanes.json", "routing.json"):
        os.symlink(os.path.join(real, name), os.path.join(cfg, name))
    return cfg, real


def case_a_link_retargeted_since_the_read_is_refused():
    """Same bytes behind a different file is still a change: the link is part
    of what the read saw, so the commit refuses and writes through neither."""
    with tempfile.TemporaryDirectory() as td:
        cfg, real = linked_config(td)
        lanes_link = os.path.join(cfg, "lanes.json")
        snap = catalog_commit.read(cfg)
        other = os.path.join(td, "other-lanes.json")
        shutil.copy(os.path.join(real, "lanes.json"), other)
        os.remove(lanes_link)
        os.symlink(other, lanes_link)
        before = {p: on_disk(p) for p in (other, os.path.join(real, "lanes.json"))}
        e = refusal(catalog_commit.commit, snap,
                    {"lanes": with_tier(snap.lanes, "terra-high@codex", 1)})
        ok = (isinstance(e, catalog_commit.CatalogChanged) and e.changed == ("lanes",)
              and all(on_disk(p) == before[p] for p in before))
        return ok, repr(e)


def case_an_invalid_document_is_refused_and_nothing_is_written():
    """The commit validates with the read side's validators before it writes
    anything: an invalid routing.json stops a valid lanes.json too."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_config(td)
        lanes_path, routing_path = paths(cfg)
        before = {p: on_disk(p) for p in (lanes_path, routing_path)}
        snap = catalog_commit.read(cfg)
        routing = copy.deepcopy(snap.routing)
        routing["gate"] = 2
        e = refusal(catalog_commit.commit, snap,
                    {"lanes": with_tier(snap.lanes, "terra-high@codex", 1), "routing": routing})
        unknown = refusal(catalog_commit.commit, snap, {"meters": {}})
        ok = (e is not None and not isinstance(e, catalog_commit.CatalogChanged)
              and "gate" in str(e) and routing_path in str(e)
              and unknown is not None and "meters" in str(unknown)
              and all(on_disk(p) == before[p] for p in before))
        return ok, f"{e!r} {unknown!r}"


def case_a_commit_writes_through_a_link_and_keeps_it():
    """A link to an existing file is written through: the file it names takes
    the document, and the link stays a link (decision D.1)."""
    with tempfile.TemporaryDirectory() as td:
        cfg, real = linked_config(td)
        lanes_link, routing_link = paths(cfg)
        snap = catalog_commit.read(cfg)
        done = catalog_commit.commit(snap, {"lanes": with_tier(snap.lanes, "terra-high@codex", 1)})
        ok = (done.written == (lanes_link,)
              and os.path.islink(lanes_link) and os.path.islink(routing_link)
              and os.readlink(lanes_link) == os.path.join(real, "lanes.json")
              and catalog.load_json(os.path.join(real, "lanes.json"))["lanes"]["terra-high@codex"]["tier"] == 1
              and snap.sources["lanes"]["symlink"] is True
              and snap.sources["lanes"]["resolved"] == os.path.realpath(os.path.join(real, "lanes.json")))
        return ok, f"written={done.written} link={os.path.islink(lanes_link)} sources={snap.sources['lanes']}"


def case_a_dangling_link_is_refused_at_read_and_at_commit():
    """A link that names no file is refused when it is read and when it
    appears between the read and the commit, and the file it names is never
    created; a loop is refused the same way."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_config(td)
        lanes_path, routing_path = paths(cfg)
        missing = os.path.join(td, "elsewhere", "routing.json")
        os.remove(routing_path)
        os.symlink(missing, routing_path)
        at_read = refusal(catalog_commit.read, cfg)

        loop = sample_config(td, "loop")
        loop_lanes = os.path.join(loop, "lanes.json")
        os.remove(loop_lanes)
        os.symlink(os.path.join(loop, "lanes-b.json"), loop_lanes)
        os.symlink(loop_lanes, os.path.join(loop, "lanes-b.json"))
        looped = refusal(catalog_commit.read, loop)

        os.remove(routing_path)
        shutil.copy(os.path.join(SAMPLES, "routing.json"), routing_path)
        snap = catalog_commit.read(cfg)
        os.remove(routing_path)
        os.symlink(missing, routing_path)
        routing = copy.deepcopy(snap.routing)
        routing["gate"] = 0.2
        at_commit = refusal(catalog_commit.commit, snap, {"routing": routing})
        through = refusal(catalog.write_json, routing_path, routing)
        ok = (at_read is not None and routing_path in str(at_read) and missing in str(at_read)
              and looped is not None and "loop" in str(looped)
              and at_commit is not None and through is not None
              and not os.path.lexists(missing) and not os.path.isdir(os.path.dirname(missing)))
        return ok, f"read={at_read!r} loop={looped!r} commit={at_commit!r} write={through!r}"


def backups(cfg, name):
    """The backups of one document, oldest first, as their bytes."""
    folder = os.path.join(cfg, "backups")
    found = sorted(f for f in (os.listdir(folder) if os.path.isdir(folder) else ())
                   if f.startswith(f"{name}-") and f.endswith(".json"))
    out = []
    for f in found:
        with open(os.path.join(folder, f), "rb") as fh:
            out.append(fh.read())
    return out


def case_a_commit_backs_up_what_it_replaces():
    """Each global document a commit replaces is copied, as read, to
    <config dir>/backups/<name>-<UTC stamp>.json first, and only the newest
    twenty per document are kept. A document the commit skips gets none, and
    a project document is not backed up."""
    with tempfile.TemporaryDirectory() as td:
        cfg = sample_config(td)
        lanes_path, _routing_path = paths(cfg)
        replaced = []
        for i in range(22):
            snap = catalog_commit.read(cfg)
            replaced.append(on_disk(lanes_path)[0])
            catalog_commit.commit(snap, {"lanes": with_tier(snap.lanes, "terra-high@codex", i % 4 + 1),
                                         "routing": snap.routing})
        repo = os.path.join(td, "repo")
        os.makedirs(os.path.join(repo, ".delegate"))
        open(os.path.join(repo, ".git"), "w").close()
        catalog.write_json(os.path.join(repo, ".delegate", "routing.json"), {"gate": 0.2})
        snap = catalog_commit.read(cfg, project_dir=repo)
        catalog_commit.commit(snap, {"project": {"gate": 0.3}})
        kept = backups(cfg, "lanes")
        stamped = sorted(os.listdir(os.path.join(cfg, "backups")))
        ok = (kept == replaced[-20:] and backups(cfg, "routing") == []
              and all(f.startswith("lanes-") for f in stamped) and len(stamped) == 20
              and catalog.load_json(os.path.join(repo, ".delegate", "routing.json")) == {"gate": 0.3}
              and not os.path.isdir(os.path.join(repo, ".delegate", "backups")))
        return ok, f"kept={len(kept)} files={stamped[:2]}"


def failing_routing_write():
    """catalog.write_json, raising for any routing.json; returns the restore."""
    real = catalog.write_json

    def write(path, doc):
        if os.path.basename(path) == "routing.json":
            raise OSError("disk full")
        return real(path, doc)

    catalog.write_json = write
    return lambda: setattr(catalog, "write_json", real)


def case_a_failed_write_puts_back_what_the_commit_wrote():
    """lanes.json is written before routing.json; when routing.json fails, the
    lanes.json bytes the read saw go back through the link, and the error names
    both the failure and the restore. On a first run the file the commit made
    is removed again."""
    with tempfile.TemporaryDirectory() as td:
        cfg, real = linked_config(td)
        lanes_link, _routing_link = paths(cfg)
        target = os.path.join(real, "lanes.json")
        before = on_disk(target)[0]
        snap = catalog_commit.read(cfg)
        routing = copy.deepcopy(snap.routing)
        routing["gate"] = 0.2
        restore = failing_routing_write()
        try:
            e = refusal(catalog_commit.commit, snap,
                        {"lanes": with_tier(snap.lanes, "terra-high@codex", 1), "routing": routing})
            fresh = os.path.join(td, "fresh")
            first = refusal(catalog_commit.commit, catalog_commit.read(fresh),
                            {"lanes": catalog.load_json(os.path.join(SAMPLES, "lanes.json")),
                             "routing": catalog.load_json(os.path.join(SAMPLES, "routing.json"))})
        finally:
            restore()
        ok = (e is not None and "disk full" in str(e) and lanes_link in str(e)
              and on_disk(target)[0] == before and os.path.islink(lanes_link)
              and first is not None and not os.path.lexists(os.path.join(fresh, "lanes.json")))
        return ok, f"{e!r} first={first!r}"


def case_a_first_run_commits_onto_absent_documents():
    """With no catalog yet, both documents read as None and the commit
    creates them, with nothing to back up; a file that appears in between is
    still an Intervening edit."""
    with tempfile.TemporaryDirectory() as td:
        cfg = os.path.join(td, "new", "delegate")
        lanes_path, routing_path = paths(cfg)
        lanes = catalog.load_json(os.path.join(SAMPLES, "lanes.json"))
        routing = catalog.load_json(os.path.join(SAMPLES, "routing.json"))
        snap = catalog_commit.read(cfg)
        done = catalog_commit.commit(snap, {"lanes": lanes, "routing": routing})
        raced = catalog_commit.read(os.path.join(td, "raced"))
        catalog.write_json(os.path.join(td, "raced", "lanes.json"), lanes)
        e = refusal(catalog_commit.commit, raced, {"lanes": lanes, "routing": routing})
        ok = (snap.lanes is None and snap.routing is None
              and snap.sources["lanes"]["exists"] is False and snap.files["lanes"] == lanes_path
              and done.written == (lanes_path, routing_path)
              and catalog.load_json(lanes_path) == lanes and catalog.load_json(routing_path) == routing
              and not os.path.exists(os.path.join(cfg, "backups"))
              and isinstance(e, catalog_commit.CatalogChanged) and e.changed == ("lanes",)
              and not os.path.exists(os.path.join(td, "raced", "routing.json")))
        return ok, f"written={done.written} raced={e!r}"


for name, case in (
    ("a commit writes only the documents that changed",
     case_a_commit_writes_only_the_documents_that_changed),
    ("an intervening edit is refused and nothing is written",
     case_an_intervening_edit_is_refused_and_nothing_is_written),
    ("a link retargeted since the read is refused",
     case_a_link_retargeted_since_the_read_is_refused),
    ("an invalid document is refused and nothing is written",
     case_an_invalid_document_is_refused_and_nothing_is_written),
    ("a commit writes through a link to an existing file and keeps the link",
     case_a_commit_writes_through_a_link_and_keeps_it),
    ("a dangling link is refused at read and at commit, and its target is never created",
     case_a_dangling_link_is_refused_at_read_and_at_commit),
    ("a commit backs up what it replaces and keeps the newest twenty",
     case_a_commit_backs_up_what_it_replaces),
    ("a write that fails puts back what the commit already wrote",
     case_a_failed_write_puts_back_what_the_commit_wrote),
    ("a first run commits onto absent documents",
     case_a_first_run_commits_onto_absent_documents),
):
    try:
        ok, detail = case()
    except Exception as e:
        ok, detail = False, repr(e)
    record(name, ok, detail)

sys.exit(1 if fails else 0)
