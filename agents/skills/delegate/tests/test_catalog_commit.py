#!/usr/bin/env python3
"""test_catalog_commit.py — the one write of catalog documents (deepening D).

Every case runs on a temp config dir copied from assets/samples, never the live
catalog. Run: python3 tests/test_catalog_commit.py
"""
import contextlib
import copy
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Run from a fresh directory with no Git root above it, so no read finds the
# invoking checkout's own `.delegate/` documents.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
# never the real Model queue, even in a case that sets no HOME of its own
os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(_ISOLATED_CWD.name, "new-models.json")
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
SAMPLES = os.path.abspath(os.path.join(HERE, "..", "assets", "samples"))
# a catalog with sixteen claude Lanes: the native Lanes of the Claude profile
REFRESH_DIR = os.path.join(HERE, "fixtures", "refresh-2026-09-22")
sys.path.insert(0, SCRIPTS)
import catalog  # noqa: E402
import catalog_commit  # noqa: E402
import model_queue  # noqa: E402
import orchestrators  # noqa: E402

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


# --- D2: Agent files and the Model queue follow the commit -------------------

@contextlib.contextmanager
def temp_home():
    """A temp HOME: ~/.config/delegate there is a throwaway live catalog and
    ~/.claude/agents a throwaway agents directory, with its own Model queue
    and only the shipped orchestrator profiles."""
    keys = ("HOME", "DELEGATE_MODEL_QUEUE", "DELEGATE_ORCHESTRATORS_DIR")
    saved = {key: os.environ.get(key) for key in keys}
    with tempfile.TemporaryDirectory() as home:
        os.environ["HOME"] = home
        os.environ["DELEGATE_MODEL_QUEUE"] = os.path.join(home, "new-models.json")
        os.environ.pop("DELEGATE_ORCHESTRATORS_DIR", None)
        try:
            yield home
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def native_catalog(root, cfg=None):
    """A config dir holding the refresh fixture's lanes (sixteen claude
    Lanes) and the sample routing: by default the live one under `root`, a
    temp HOME. Returns (config dir, the agents directory of the Claude
    profile under `root`)."""
    cfg = cfg or os.path.join(root, ".config", "delegate")
    os.makedirs(cfg)
    shutil.copy(os.path.join(REFRESH_DIR, "lanes.json"), cfg)
    shutil.copy(os.path.join(SAMPLES, "routing.json"), cfg)
    return cfg, os.path.join(root, ".claude", "agents")


def claude_lanes(doc):
    return [name for name, lane in doc["lanes"].items() if lane["harness"] == "claude"]


def agent_file(agents, lane):
    """A claude Lane's Agent file: `lane-<model-effort>.md`."""
    return os.path.join(agents, f"lane-{lane.split('@')[0]}.md")


def text_of(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def place(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# The Agent file of opus55-high@claude, byte for byte as a real save wrote it.
OPUS55_HIGH = (
    "---\n"
    "name: lane-opus55-high\n"
    'description: "Delegate native lane opus55-high@claude. Use only when /delegate '
    'prints a native line that names this agent, or when the user names this lane."\n'
    "model: claude-opus-5-5\n"
    "effort: high\n"
    "tools: Read, Grep, Glob, Bash, Edit, Write, WebFetch, WebSearch, mcp__playwright\n"
    "---\n"
    "\n"
    "You are a delegate worker. Read the prompt file named in your task and follow it "
    "exactly. Your final message is the return block that the prompt asks for.\n"
)


def case_native_lanes_added_and_removed_gain_and_lose_their_agent_files():
    """A commit of the live catalog's lanes gives every claude Lane after it
    an Agent file in the template's text, the new Lane and the Lanes that had
    none alike, and removes the file of the Lane it took out. A file in the
    agents directory that is no Lane's stays (decision D.7)."""
    with temp_home() as home:
        cfg, agents = native_catalog(home)
        place(agent_file(agents, "opus-high@claude"), "placed by an earlier save\n")
        place(os.path.join(agents, "courier.md"), "not a lane\n")
        snap = catalog_commit.read(cfg)
        lanes = copy.deepcopy(snap.lanes)
        opus55 = dict(lanes["lanes"].pop("opus-high@claude"), model="claude-opus-5-5")
        opus55.pop("published_as", None)
        lanes["lanes"]["opus55-high@claude"] = opus55
        done = catalog_commit.commit(snap, {"lanes": lanes})
        files = sorted(os.listdir(agents))
        expected = sorted([os.path.basename(agent_file(agents, n)) for n in claude_lanes(lanes)]
                          + ["courier.md"])
        ok = (files == expected and "lane-opus-high.md" not in files
              and text_of(agent_file(agents, "opus55-high@claude")) == OPUS55_HIGH
              and text_of(os.path.join(agents, "courier.md")) == "not a lane\n"
              and f"wrote {agent_file(agents, 'opus55-high@claude')}" in done.lines
              and f"removed {agent_file(agents, 'opus-high@claude')}" in done.lines
              and len(done.lines) == len(claude_lanes(lanes)) + 1)
        return ok, f"files={files} lines={done.lines}"


def case_a_link_at_a_lanes_agent_path_is_replaced():
    """A link at a Lane's Agent path is a repository's file (a stow link):
    the commit replaces it with a plain file and never writes through it, so
    the file it named keeps its text (decision D.2). A commit that changes no
    document still keeps the Agent files in step."""
    with temp_home() as home:
        cfg, agents = native_catalog(home)
        repo_file = os.path.join(home, "dotfiles", "agents", "lane-opus-high.md")
        place(repo_file, "the repo's copy\n")
        os.makedirs(agents)
        path = agent_file(agents, "opus-high@claude")
        os.symlink(repo_file, path)
        snap = catalog_commit.read(cfg)
        done = catalog_commit.commit(snap, {"lanes": snap.lanes})
        ok = (done.written == () and not os.path.islink(path) and os.path.isfile(path)
              and "name: lane-opus-high\n" in text_of(path)
              and text_of(repo_file) == "the repo's copy\n"
              and f"wrote {path}" in done.lines)
        return ok, f"link={os.path.islink(path)} repo={text_of(repo_file)!r} lines={done.lines[:3]}"


def case_a_template_change_reaches_the_lanes_already_placed():
    """An Agent file that no longer matches its profile's template (browser
    ticket 02's `tools` line) is rewritten by the next commit; one that
    matches is left alone, mtime and all."""
    with temp_home() as home:
        cfg, agents = native_catalog(home)
        snap = catalog_commit.read(cfg)
        catalog_commit.commit(snap, {"lanes": snap.lanes})
        old = agent_file(agents, "fable-high@claude")
        same = agent_file(agents, "opus-high@claude")
        place(old, "---\nname: the old form, no tools line\n---\n")
        os.utime(same, (1_000_000, 1_000_000))
        snap = catalog_commit.read(cfg)
        done = catalog_commit.commit(snap, {"lanes": snap.lanes})
        ok = (done.lines == (f"updated {old}",)
              and "tools: Read, Grep, Glob, Bash, Edit, Write, WebFetch, WebSearch, mcp__playwright\n"
              in text_of(old)
              and os.stat(same).st_mtime == 1_000_000)
        return ok, f"lines={done.lines} text={text_of(old)!r}"


def case_a_catalog_that_is_not_the_live_one_gets_a_note():
    """The Agent files belong to the live catalog, so a commit of another
    catalog's lanes writes none, not even the agents directory, and says so
    in one note line."""
    with temp_home() as home:
        cfg, _agents = native_catalog(home, os.path.join(home, "elsewhere"))
        snap = catalog_commit.read(cfg)
        done = catalog_commit.commit(snap, {"lanes": with_tier(snap.lanes, "opus-high@claude", 1)})
        ok = (done.written == (os.path.join(cfg, "lanes.json"),)
              and not os.path.exists(os.path.join(home, ".claude"))
              and len(done.lines) == 1 and done.lines[0].startswith("note: ")
              and "agent file" in done.lines[0] and "not the live one" in done.lines[0])
        return ok, f"lines={done.lines}"


def case_a_commit_of_project_documents_alone_writes_no_agent_file():
    """The dashboard's project-scope `catalog set` commits a project document
    alone; it never touches the agents directory, even on the live catalog
    whose claude Lanes have no Agent file yet."""
    with temp_home() as home:
        cfg, agents = native_catalog(home)
        repo = os.path.join(home, "repo")
        os.makedirs(os.path.join(repo, ".delegate"))
        open(os.path.join(repo, ".git"), "w").close()
        project = os.path.join(repo, ".delegate", "routing.json")
        catalog.write_json(project, {"gate": 0.2})
        snap = catalog_commit.read(cfg, project_dir=repo)
        done = catalog_commit.commit(snap, {"project": {"gate": 0.3}})
        ok = (done.written == (project,) and done.lines == ()
              and not os.path.exists(agents))
        return ok, f"written={done.written} lines={done.lines}"


NOTICED = [{"harness": "codex", "model": "gpt-6-astra", "predecessor": None, "via": "scan",
            "first_seen": "2026-10-09T08:00:00+00:00"},
           {"harness": "agy", "model": "gemini-3.1-pro", "predecessor": None, "via": "asked",
            "first_seen": "2026-10-09T09:00:00+00:00"}]
SWAPPED = [{"old": "sol-high@codex", "new": "sol61-high@codex", "model": "gpt-6.1-sol",
            "at": "2026-10-09T08:00:00+00:00"}]


def write_queue(models, applied):
    """The Model queue file as dispatch leaves it, last scanned on 10 October."""
    with open(model_queue.path(), "w", encoding="utf-8") as f:
        json.dump({"version": model_queue.VERSION, "checked_at": "2026-10-10T00:00:00+00:00",
                   "models": models, "applied": applied}, f)


def queue_file():
    with open(model_queue.path(), encoding="utf-8") as f:
        return json.load(f)


def case_a_commit_forgets_exactly_the_queue_entries_its_read_returned():
    """A wizard reads the queue with the catalog and names it on its start
    page; its commit forgets exactly those entries. A model noticed and a
    swap applied while it was open stay for the next run, and so does when
    the last scan ran. A commit that is refused forgets nothing (decision
    D.4)."""
    with temp_home() as home:
        cfg = sample_config(home)
        write_queue(NOTICED, SWAPPED)
        snap = catalog_commit.read(cfg, queue=True)
        # dispatch notes a model and its scan swaps one in while the wizard is open
        later = model_queue.note([{"harness": "codex", "model": "gpt-7-nova"}], "asked")
        doc = queue_file()
        late_swap = {"old": "terra-high@codex", "new": "terra2-high@codex", "model": "gpt-6.2-terra",
                     "at": "2026-10-10T12:00:00+00:00"}
        doc["applied"].append(late_swap)
        with open(model_queue.path(), "w", encoding="utf-8") as f:
            json.dump(doc, f)
        done = catalog_commit.commit(snap, {"lanes": with_tier(snap.lanes, "terra-high@codex", 1)})
        after = queue_file()

        stale = catalog_commit.read(cfg, queue=True)
        catalog.write_json(os.path.join(cfg, "lanes.json"), with_tier(stale.lanes, "sol-high@codex", 1))
        refused = refusal(catalog_commit.commit, stale,
                          {"lanes": with_tier(stale.lanes, "terra-high@codex", 2)})
        ok = (snap.queued == tuple(NOTICED) and snap.applied == tuple(SWAPPED)
              and done.written == (os.path.join(cfg, "lanes.json"),)
              and after["models"] == later and after["applied"] == [late_swap]
              and after["checked_at"] == "2026-10-10T00:00:00+00:00"
              and stale.queued == tuple(later)
              and isinstance(refused, catalog_commit.CatalogChanged)
              and queue_file() == after)
        return ok, f"queued={snap.queued} after={after} lines={done.lines}"


def case_a_read_without_the_queue_leaves_the_queue_alone():
    """Focused screens, the scan and `catalog set` read no queue: their read
    names none, and their commit leaves the queue file as it was."""
    with temp_home() as home:
        cfg = sample_config(home)
        write_queue(NOTICED, SWAPPED)
        with open(model_queue.path(), "rb") as f:
            before = f.read()
        snap = catalog_commit.read(cfg)
        done = catalog_commit.commit(snap, {"lanes": with_tier(snap.lanes, "terra-high@codex", 1)})
        with open(model_queue.path(), "rb") as f:
            after = f.read()
        ok = (snap.queued == () and snap.applied == () and len(done.written) == 1
              and after == before)
        return ok, f"queued={snap.queued} lines={done.lines}"


def case_an_agent_file_that_cannot_be_written_is_a_note():
    """The Agent files and the queue follow a catalog already written, so a
    failure there is a note line, never an error. A machine-local Claude
    profile whose template holds a JSON object cannot fill any Agent file;
    the commit still returns, the catalog stays written, each claude Lane
    gets a note, and the queue entries its read returned are forgotten."""
    with temp_home() as home:
        cfg, agents = native_catalog(home)
        with open(os.path.join(orchestrators.SHIPPED_DIR, "claude.json"), encoding="utf-8") as f:
            profile = json.load(f)
        profile["native"]["template"].insert(-1, 'End with a JSON object: {"ok": true}')
        place(os.path.join(cfg, "orchestrators", "claude.json"), json.dumps(profile))
        write_queue(NOTICED, SWAPPED)
        snap = catalog_commit.read(cfg, queue=True)
        tier = 2 if snap.lanes["lanes"]["opus-high@claude"]["tier"] != 2 else 3
        try:
            done = catalog_commit.commit(snap, {"lanes": with_tier(snap.lanes, "opus-high@claude", tier)})
        except Exception as e:
            return False, f"the commit raised {e!r}"
        lanes_path = os.path.join(cfg, "lanes.json")
        notes = [line for line in done.lines if line.startswith("note: ")]
        placed = os.listdir(agents) if os.path.isdir(agents) else []
        ok = (done.written == (lanes_path,)
              and catalog.load_json(lanes_path)["lanes"]["opus-high@claude"]["tier"] == tier
              and len(notes) == len(done.lines) == len(claude_lanes(snap.lanes))
              and any("opus-high@claude" in line for line in notes)
              and not any(name.startswith("lane-") for name in placed)
              and queue_file()["models"] == [] and queue_file()["applied"] == [])
        return ok, f"written={done.written} lines={done.lines[:2]} queue={queue_file()}"


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
    ("native Lanes added and removed gain and lose their agent files",
     case_native_lanes_added_and_removed_gain_and_lose_their_agent_files),
    ("a link at a Lane's agent path is replaced and its target is untouched",
     case_a_link_at_a_lanes_agent_path_is_replaced),
    ("a template change reaches the Lanes already placed",
     case_a_template_change_reaches_the_lanes_already_placed),
    ("a catalog that is not the live one gets no agent file and a note",
     case_a_catalog_that_is_not_the_live_one_gets_a_note),
    ("a commit of project documents alone writes no agent file",
     case_a_commit_of_project_documents_alone_writes_no_agent_file),
    ("a commit forgets exactly the queue entries its read returned",
     case_a_commit_forgets_exactly_the_queue_entries_its_read_returned),
    ("a read without the queue leaves the queue alone",
     case_a_read_without_the_queue_leaves_the_queue_alone),
    ("an agent file that cannot be written is a note, and the queue is still forgotten",
     case_an_agent_file_that_cannot_be_written_is_a_note),
):
    try:
        ok, detail = case()
    except Exception as e:
        ok, detail = False, repr(e)
    record(name, ok, detail)

sys.exit(1 if fails else 0)
