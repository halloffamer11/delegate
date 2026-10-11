#!/usr/bin/env python3
"""test_bench_snapshot.py — the Benchmark snapshot: which rows one wizard
scrub, report or model inspection reads, and where each came from.

The interface is the test surface: `snapshot()` over the `web`, `fixture` and
`local` adapters. The web adapter gets a temp cache, a fixed clock and a `get`
that serves the saved pages, so nothing here reaches the web.
Run: python3 tests/test_bench_snapshot.py
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import bench_snapshot  # noqa: E402
from bench_snapshot import fixture, local, snapshot, web  # noqa: E402

with open(os.path.join(HERE, "fixtures", "real_aa_model_page_sample.html"), "rb") as f:
    AA_PAGE = f.read()
EPOCH_CSV = os.path.join(HERE, "fixture", "bench-epoch.csv")
with open(EPOCH_CSV, "rb") as f:
    EPOCH_BYTES = f.read()
# one row, on a benchmark the snapshot keeps, so an old copy is told from a new one
OLD_EPOCH = EPOCH_BYTES.split(b"\n")[0] + b"\n" + EPOCH_BYTES.split(b"\n")[1] + b"\n"
NOT_EPOCH = b"model,score\nsomething,1\n"
T = 1_800_000_000.0
HOUR = 60 * 60

fails = 0


def record(name, ok, detail=""):
    global fails
    if ok:
        print(f"PASS {name}")
    else:
        fails += 1
        print(f"FAIL {name}: {detail}")


def aa_row(model, benchmark="b", score=1):
    return {"source": "aa", "model": model, "effort": "high", "benchmark": benchmark,
            "score": score}


def served(log, epoch=EPOCH_BYTES, page=AA_PAGE, fail=None):
    """The web as a test sees it: each URL asked for is logged, and the Epoch
    URL gets the CSV and any other the Artificial Analysis page."""
    def get(url):
        log.append(url)
        if fail is not None:
            raise fail
        return epoch if url == bench_snapshot.EPOCH_URL else page
    return get


def seed(cache, aa_rows=None, epoch=None, age=0.0):
    """A cache as an earlier run left it, `age` seconds before T."""
    paths = []
    if aa_rows is not None:
        os.makedirs(os.path.join(cache, "aa"), exist_ok=True)
        paths.append(os.path.join(cache, "aa", "accepted.json"))
        with open(paths[-1], "w", encoding="utf-8") as f:
            json.dump(aa_rows, f)
    if epoch is not None:
        os.makedirs(os.path.join(cache, "epoch"), exist_ok=True)
        paths.append(os.path.join(cache, "epoch", "eci_benchmarks.csv"))
        with open(paths[-1], "wb") as f:
            f.write(epoch)
    for path in paths:
        os.utime(path, (T - age, T - age))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


def both(cache, get, **kwargs):
    adapter = web(cache_dir=cache, get=get, clock=lambda: T)
    return snapshot(kwargs.pop("row_files", ()), aa=adapter, epoch=adapter, **kwargs)


# --- the web adapter and its cache --------------------------------------------

try:
    with tempfile.TemporaryDirectory() as td:
        cached = [aa_row("Grok 4.6")]
        seed(td, aa_rows=cached, epoch=EPOCH_BYTES, age=3 * HOUR)
        log = []
        snap = both(td, served(log))
        epoch = snap.epoch_rows or []
        record(
            "a fetch under 24 hours old is not fetched again, and the note gives its age",
            log == [] and snap.effort_rows == cached
            and len(epoch) == 25 and all(r["model"] and r["slug"] for r in epoch)
            and snap.origins["aa"].how == "cache" and snap.origins["epoch"].how == "cache"
            and snap.origins["aa"].age == 3 * HOUR and snap.origins["aa"].failure is None
            and snap.note == "Benchmark rows: AA fetched 3h ago, Epoch fetched 3h ago"
            and snap.errors == (),
            f"log={log} origins={snap.origins} note={snap.note!r}",
        )
except Exception as e:
    record("a fetch under 24 hours old is not fetched again, and the note gives its age",
           False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        seed(td, aa_rows=[aa_row("Grok 4.6")], epoch=OLD_EPOCH, age=30 * HOUR)
        log = []
        snap = both(td, served(log))
        accepted = os.path.join(td, "aa", "accepted.json")
        with open(accepted, encoding="utf-8") as f:
            on_disk = json.load(f)
        record(
            "a fetch older than 24 hours is fetched again, into the same directory",
            len(log) == 2 and log.count(bench_snapshot.EPOCH_URL) == 1
            and snap.effort_rows == on_disk and len(on_disk) > 1
            and all(r["source"] == "aa" and r.get("variant") for r in on_disk)
            and read_bytes(os.path.join(td, "epoch", "eci_benchmarks.csv")) == EPOCH_BYTES
            and len(snap.epoch_rows) == 25
            and sorted(os.listdir(os.path.join(td, "aa"))) == [
                "accepted.json", "packet.txt", "rejected.json", "rows.json"]
            and sorted(os.listdir(td)) == ["aa", "epoch"]
            and snap.origins["aa"].how == "fetched" and snap.origins["epoch"].how == "fetched"
            and snap.note == "Benchmark rows: AA fetched just now, Epoch fetched just now",
            f"log={log} files={sorted(os.listdir(td))} origins={snap.origins} note={snap.note!r}",
        )
except Exception as e:
    record("a fetch older than 24 hours is fetched again, into the same directory", False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        seed(td, aa_rows=[aa_row("Grok 4.6")], epoch=OLD_EPOCH, age=HOUR)
        log = []
        snap = both(td, served(log), renew=True)
        record(
            "a renew fetches Artificial Analysis now and keeps Epoch's cache",
            len(log) == 1 and log[0] != bench_snapshot.EPOCH_URL
            and snap.origins["aa"].how == "fetched" and snap.origins["epoch"].how == "cache"
            and len(snap.effort_rows) > 1 and len(snap.epoch_rows) == 1
            and read_bytes(os.path.join(td, "epoch", "eci_benchmarks.csv")) == OLD_EPOCH,
            f"log={log} origins={snap.origins}",
        )
except Exception as e:
    record("a renew fetches Artificial Analysis now and keeps Epoch's cache", False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        cached = [aa_row("Grok 4.6")]
        seed(td, aa_rows=cached, epoch=OLD_EPOCH, age=30 * HOUR)
        log = []
        snap = both(td, served(log, fail=RuntimeError("the page could not be read")))
        aa, ep = snap.origins["aa"], snap.origins["epoch"]
        record(
            "a failed fetch keeps the newest copy on hand and says how old it is",
            len(log) == 2 and snap.effort_rows == cached and len(snap.epoch_rows) == 1
            and aa.how == "cache" and aa.age == 30 * HOUR and "the page could not be read" in aa.failure
            and ep.how == "cache" and ep.age == 30 * HOUR and "the page could not be read" in ep.failure
            # both sources first, then the reason they share, said once
            and snap.note == ("Benchmark rows: AA fetched 30h ago, Epoch fetched 30h ago; "
                              "AA and Epoch: the page could not be read")
            and snap.errors == (),
            f"origins={snap.origins} note={snap.note!r}",
        )
except Exception as e:
    record("a failed fetch keeps the newest copy on hand and says how old it is", False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "cache")
        repo = write_json(os.path.join(td, "repo.json"),
                          [aa_row("Grok 4.6"), dict(aa_row("Grok 4.6"), source="tbench")])
        log = []
        snap = both(cache, served(log, fail=OSError("offline")), row_files=[repo])
        aa, ep = snap.origins["aa"], snap.origins["epoch"]
        record(
            "a failed fetch with nothing cached keeps the named Artificial Analysis rows; "
            "Epoch is unavailable while the accepted rows stand",
            snap.effort_rows == [aa_row("Grok 4.6"), dict(aa_row("Grok 4.6"), source="tbench")]
            and aa.how == "rows" and "offline" in aa.failure
            and snap.epoch_rows is None and ep.how == "none" and "offline" in ep.failure
            and snap.note == "Benchmark rows: AA from --effort-rows, Epoch skipped; AA and Epoch: offline"
            and snap.errors == (),
            f"origins={snap.origins} rows={snap.effort_rows} note={snap.note!r}",
        )
        # and with no named file either, there are no accepted rows at all
        # effort.fetch_page puts the URL in front of its reason; the line leaves it out

        def refused(url):
            raise OSError(f"{url}: cannot fetch: connection refused")

        bare = both(os.path.join(td, "bare"), refused)
        record(
            "a failed fetch with nothing cached and no named file leaves no accepted rows",
            bare.effort_rows is None and bare.origins["aa"].how == "none"
            and bare.note == ("Benchmark rows: AA skipped, Epoch skipped; "
                              "AA and Epoch: cannot fetch: connection refused"),
            f"origins={bare.origins} note={bare.note!r}",
        )
        # nothing came back, so nothing was written: not even an empty
        # directory for either source
        record(
            "a failed fetch with nothing cached leaves no cache directory behind",
            not os.path.exists(cache) and not os.path.exists(os.path.join(td, "bare")),
            f"cache={sorted(os.listdir(cache)) if os.path.isdir(cache) else None}",
        )
except Exception as e:
    record("a failed fetch with nothing cached keeps the named Artificial Analysis rows; "
           "Epoch is unavailable while the accepted rows stand", False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        cached = [aa_row("Grok 4.6")]
        seed(td, aa_rows=cached, epoch=OLD_EPOCH, age=30 * HOUR)
        before = (read_bytes(os.path.join(td, "aa", "accepted.json")),
                  read_bytes(os.path.join(td, "epoch", "eci_benchmarks.csv")))
        snap = both(td, served([], epoch=NOT_EPOCH, page=b"<html><title>moved</title></html>"))
        after = (read_bytes(os.path.join(td, "aa", "accepted.json")),
                 read_bytes(os.path.join(td, "epoch", "eci_benchmarks.csv")))
        record(
            "a fetched CSV without Epoch's header, or a page with no dataset, never replaces the cache",
            before == after and len(snap.epoch_rows) == 1 and snap.effort_rows == cached
            and "header" in snap.origins["epoch"].failure
            and snap.origins["aa"].failure
            and sorted(os.listdir(td)) == ["aa", "epoch"],
            f"origins={snap.origins} files={sorted(os.listdir(td))}",
        )
except Exception as e:
    record("a fetched CSV without Epoch's header, or a page with no dataset, never replaces the cache",
           False, repr(e))

# --- named files and the merge -------------------------------------------------

try:
    with tempfile.TemporaryDirectory() as td:
        a = write_json(os.path.join(td, "aa.json"), [aa_row("Grok 4.6")])
        t = write_json(os.path.join(td, "tbench.json"), [dict(aa_row("Grok 4.6"), source="tbench")])
        bad = write_json(os.path.join(td, "bad.json"), {"not": "a list"})
        snap = snapshot([a, t])
        refused = snapshot([a, bad])
        try:
            bench_snapshot.load_effort_rows([a, bad])
            raised = ""
        except Exception as e:
            raised = str(e)
        record(
            "named files combine in order, and a bad file refuses every accepted row and is named",
            [r["source"] for r in snap.effort_rows] == ["aa", "tbench"]
            and [r["source"] for r in bench_snapshot.load_effort_rows(a)] == ["aa"]
            and snap.origins == {} and snap.epoch_rows is None and snap.errors == ()
            and refused.effort_rows is None and len(refused.errors) == 1
            and bad in refused.errors[0] and "expected a JSON list" in refused.errors[0]
            and bad in raised and "expected a JSON list" in raised,
            f"rows={snap.effort_rows} errors={refused.errors} raised={raised!r}",
        )
        empty = snapshot()
        record(
            "with no file named and no adapter there are no rows and no note",
            empty.effort_rows is None and empty.epoch_rows is None and empty.origins == {}
            and empty.errors == () and empty.note == "",
            repr(empty),
        )
except Exception as e:
    record("named files combine in order, and a bad file refuses every accepted row and is named",
           False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        fresh = [aa_row("Grok 4.7", "x"), aa_row("Grok 4.7", "y")]
        seed(td, aa_rows=fresh, age=HOUR)
        tbench = dict(aa_row("Grok 4.6"), source="tbench")
        swerb = dict(aa_row("Grok 4.6"), source="swerb")
        mixed = write_json(os.path.join(td, "mixed.json"),
                           [tbench, aa_row("Grok 4.6", "x"), swerb, aa_row("Grok 4.6", "y")])
        other = write_json(os.path.join(td, "other.json"), [tbench])
        adapter = web(cache_dir=td, get=served([]), clock=lambda: T)
        snap = snapshot([mixed], aa=adapter)
        appended = snapshot([other], aa=adapter)
        record(
            "the fetched Artificial Analysis rows replace only the named Artificial Analysis rows",
            snap.effort_rows == [tbench, *fresh, swerb]
            and appended.effort_rows == [tbench, *fresh]
            and "epoch" not in snap.origins and snap.epoch_rows is None,
            f"rows={snap.effort_rows} appended={appended.effort_rows}",
        )
except Exception as e:
    record("the fetched Artificial Analysis rows replace only the named Artificial Analysis rows",
           False, repr(e))

# --- the fixture and named-file adapters ---------------------------------------

try:
    real_home, real_urlopen = os.environ.get("HOME"), urllib.request.urlopen
    opened = []

    def no_web(*a, **k):
        opened.append(a)
        raise AssertionError("a URL was opened")

    with tempfile.TemporaryDirectory() as td:
        home, saved, empty_dir = (os.path.join(td, n) for n in ("home", "saved", "empty"))
        for d in (home, saved, empty_dir):
            os.makedirs(d)
        rows = [aa_row("Grok 4.6")]
        write_json(os.path.join(saved, "aa-accepted.json"), rows)
        with open(os.path.join(saved, "epoch.csv"), "wb") as f:
            f.write(EPOCH_BYTES)
        os.environ["HOME"] = home
        urllib.request.urlopen = no_web
        try:
            snap = snapshot((), aa=fixture(saved), epoch=fixture(saved), renew=True)
            missing = snapshot((), aa=fixture(empty_dir), epoch=fixture(empty_dir))
            named = snapshot((), aa=local(os.path.join(saved, "aa-accepted.json")),
                             epoch=local(EPOCH_CSV))
        finally:
            urllib.request.urlopen = real_urlopen
            if real_home is None:
                del os.environ["HOME"]
            else:
                os.environ["HOME"] = real_home
        record(
            "a fixture directory reads aa-accepted.json and epoch.csv, opens no URL and "
            "touches no cache",
            opened == [] and os.listdir(home) == []
            and snap.effort_rows == rows and len(snap.epoch_rows) == 25
            and snap.origins["aa"].how == "file" and snap.origins["epoch"].how == "file"
            and snap.origins["epoch"].path == os.path.join(saved, "epoch.csv")
            and snap.note == "Benchmark rows: AA read from aa-accepted.json, Epoch read from epoch.csv"
            # a file missing from a fixture directory is a note, not an error
            and missing.effort_rows is None and missing.epoch_rows is None and missing.errors == ()
            and missing.note == ("Benchmark rows: AA skipped, Epoch skipped; "
                                 "AA: no aa-accepted.json in the fixture directory; "
                                 "Epoch: no epoch.csv in the fixture directory")
            and named.effort_rows == rows and len(named.epoch_rows) == 25 and named.errors == (),
            f"opened={opened} home={os.listdir(home)} origins={snap.origins} note={snap.note!r} "
            f"missing={missing.note!r}",
        )
except Exception as e:
    record("a fixture directory reads aa-accepted.json and epoch.csv, opens no URL and "
           "touches no cache", False, repr(e))

try:
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "bad.csv")
        with open(bad, "wb") as f:
            f.write(NOT_EPOCH)
        aa = write_json(os.path.join(td, "aa.json"), [aa_row("Grok 4.6")])
        snap = snapshot([aa], epoch=local(bad))
        gone = snapshot((), epoch=local(os.path.join(td, "absent.csv")))
        record(
            "a named Epoch CSV without the header is an error, not a note",
            snap.epoch_rows is None and len(snap.errors) == 1
            and bad in snap.errors[0] and "header" in snap.errors[0]
            and snap.effort_rows == [aa_row("Grok 4.6")]
            and len(gone.errors) == 1 and "absent.csv" in gone.errors[0]
            and snap.note.startswith("Benchmark rows: AA from --effort-rows, "
                                     "Epoch skipped; Epoch: epoch-csv: "),
            f"errors={snap.errors} gone={gone.errors} note={snap.note!r}",
        )
        offline = snapshot([aa])
        record(
            "a source with no adapter is named on the rows line with what would read it",
            offline.note == "Benchmark rows: AA from --effort-rows, Epoch skipped; Epoch: no --epoch-csv"
            and offline.origins == {},
            repr(offline.note),
        )
except Exception as e:
    record("a named Epoch CSV without the header is an error, not a note", False, repr(e))

# --- routing never reads benchmark data ----------------------------------------

probe = (
    "import sys; sys.path.insert(0, %r)\n"
    "import rank, delegate, usage, report\n"
    "print(sorted(m for m in ('bench', 'bench_snapshot', 'bench_page', 'effort') if m in sys.modules))\n"
    "print('lane_evidence' in sys.modules)\n" % SCRIPTS
)
res = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                     cwd=tempfile.gettempdir())
lines = res.stdout.splitlines()
record(
    "routing imports no benchmark module (lane_evidence, for the published_as check, is allowed)",
    res.returncode == 0 and lines[:1] == ["[]"],
    f"rc={res.returncode} stdout={res.stdout!r} stderr={res.stderr[-400:]!r}",
)

sys.exit(1 if fails else 0)
