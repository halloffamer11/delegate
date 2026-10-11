#!/usr/bin/env python3
"""bench_snapshot.py — the Benchmark snapshot: the benchmark rows one wizard
scrub, one report or one model inspection reads, taken once, with where each
Fetched source's rows came from and how old they are.

A caller states where each source comes from by passing one adapter per
source to `snapshot()`:

  web()           the web, through one 24-hour cache under ~/.cache/delegate/bench/
  fixture(dir)    <dir>/aa-accepted.json and <dir>/epoch.csv; opens no URL
  local(path)     one named file; opens no URL

    snap = snapshot(["repo-aa.json"], aa=web(), epoch=local("epoch.csv"))

Routing never reads this, and it reads no catalog: it names sources and URLs,
never a model. It writes only under its cache directory, and only `web()`
does. `effort.fetch_page` stays the one function that opens a URL.

The cache, one directory with one rule for both sources:
  aa/        packet.txt, rows.json, accepted.json and rejected.json, exactly as
             `effort.py aa` writes them
  epoch/     eci_benchmarks.csv as served, so a change to EPOCH_BENCHMARKS
             needs no refetch
An artifact (accepted.json, the CSV) is fresh for MAX_AGE after its mtime. A
fetch writes into a temporary directory beside the source's directory, and
the artifact moves in last, only after it parsed. `renew` refetches
Artificial Analysis only: its rows are the only list of claude models the
wizard's refresh reads, and no Epoch row names one.
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
import time
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence

import effort

MAX_AGE = 24 * 60 * 60                  # every fetched source (decision H.1)
CACHE_DIR = "~/.cache/delegate/bench"   # expanded when web() is called, never at import
EPOCH_URL = "https://epoch.ai/data/eci_benchmarks.csv"
EPOCH_BENCHMARKS = (
    "DeepSWE",
    "FrontierCode",
    "APEX-Agents",
    "Terminal Bench",
    "SWE-Bench verified",
)

AA = effort.AA_SOURCE
EPOCH = "epoch"
# the names the rows line gives the sources: the wizard's own column names
# ("AA mean rank", "Epoch mean rank"), so the line fits 80 columns
_NAMES = {AA: "AA", EPOCH: "Epoch"}
# each source's directory in the cache and the artifact whose mtime is its age
_ARTIFACT = {AA: "accepted.json", EPOCH: "eci_benchmarks.csv"}
# what a fixture directory holds for each source
_FIXTURE = {AA: "aa-accepted.json", EPOCH: "epoch.csv"}
_EPOCH_HEADER = (
    "model_id,benchmark_id,performance,benchmark,benchmark_release_date,"
    "model,model_version,Model,date,source"
)
_EPOCH_FIELDS = _EPOCH_HEADER.split(",")


class Origin(NamedTuple):
    """Where one fetched source's rows came from."""
    how: str                  # "fetched", "cache", "file", "rows" or "none"
    path: Optional[str]       # the file the rows were read from
    age: Optional[float]      # seconds since the rows left the web, or since the file was written
    failure: Optional[str]    # why there are no fresh rows: the fetch that failed, the file missing


class Fetched(NamedTuple):
    """What an adapter gives for one source."""
    rows: Optional[List[dict]]
    origin: Origin
    error: Optional[str] = None   # a named input that could not be read: an error, not a note


class Snapshot(NamedTuple):
    effort_rows: Optional[List[dict]]   # every accepted row; None means no per-effort evidence
    epoch_rows: Optional[List[dict]]    # Epoch rows on EPOCH_BENCHMARKS; None means unavailable
    origins: Dict[str, Origin]          # "aa" and "epoch", one for each source given an adapter
    errors: tuple                       # one line per named input that could not be read
    note: str                           # the start page's rows line; "" when nothing was read


Fetch = Callable[[str, bool], Fetched]   # the port: (source id, renew) -> rows with their origin


def snapshot(row_files: Sequence[str] = (), aa: Optional[Fetch] = None,
             epoch: Optional[Fetch] = None, *, renew: bool = False) -> Snapshot:
    """The rows of the named accepted-rows files, with the Artificial Analysis
    adapter's rows in place of the named AA rows, and the Epoch adapter's rows.

    Never raises for a source: a named input that cannot be read is a line in
    `errors`, and a fetch that fails is its Origin's `failure`. Any named
    accepted-rows input that fails refuses every accepted row, so the
    pre-screen never judges a Lane on part of its evidence. Keeps no state.
    """
    if isinstance(row_files, str):
        row_files = [row_files]
    row_files = list(row_files or ())
    errors = []
    refused = False
    named = None
    if row_files:
        try:
            named = load_effort_rows(row_files)
        except ValueError as e:
            errors.append(str(e))
            refused = True
    effort_rows = named
    origins = {}
    if aa is not None:
        got = _ask(aa, AA, renew)
        if got.error:
            errors.append(got.error)
            refused = True
        origin = got.origin
        if got.rows is not None:
            effort_rows = _merge(named, got.rows)
        elif origin.how == "none" and not got.error and _has_aa(named):
            origin = origin._replace(how="rows")
        origins[AA] = origin
    epoch_rows = None
    if epoch is not None:
        # Epoch is never renewed: its cache is what keeps `r` off the web for it
        got = _ask(epoch, EPOCH, False)
        if got.error:
            errors.append(got.error)
        epoch_rows = got.rows
        origins[EPOCH] = got.origin
    if refused:
        effort_rows = None
    return Snapshot(effort_rows, epoch_rows, origins, tuple(errors),
                    _note(origins, named, bool(row_files)))


def load_effort_rows(paths) -> list:
    """Every row of one accepted-rows file or several, in order. The
    pre-screen judges each source on its own rows, so files from different
    sources combine safely. Raises ValueError naming the file that cannot be
    read or is not a JSON list."""
    if isinstance(paths, str):
        paths = [paths]
    rows = []
    for path in paths or ():
        full = os.path.abspath(os.path.expanduser(path))
        try:
            with open(full, "r", encoding="utf-8-sig") as f:
                doc = json.load(f)
        except OSError as e:
            raise ValueError(f"effort-rows: {e}") from e
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"effort-rows: {path}: invalid JSON: {e}") from e
        if not isinstance(doc, list):
            raise ValueError(f"effort-rows: {path}: expected a JSON list")
        rows.extend(doc)
    return rows


def web(cache_dir: str = CACHE_DIR, get: Optional[Callable[[str], bytes]] = None,
        clock: Callable[[], float] = time.time) -> Fetch:
    """The web, through the cache. `get` (url -> bytes) is `effort.fetch_page`
    unless a test passes its own; `clock` dates the artifacts it writes and
    measures their age."""
    root = os.path.expanduser(cache_dir)
    read_url = get or effort.fetch_page

    def fetch(source, renew):
        if source == AA:
            return _web(root, AA, lambda: effort.source_url(AA), _accept_aa, _read_aa,
                        read_url, clock, renew)
        if source == EPOCH:
            return _web(root, EPOCH, lambda: EPOCH_URL, _accept_epoch, _read_epoch,
                        read_url, clock, renew)
        return Fetched(None, Origin("none", None, None, f"no web source {source}"))
    return fetch


def fixture(directory: str) -> Fetch:
    """A saved directory: aa-accepted.json and epoch.csv beside the harness
    fixtures. Opens no URL and never reads or writes the cache; a file the
    directory lacks is a note."""
    def fetch(source, renew):
        name = _FIXTURE.get(source)
        path = os.path.join(directory, name) if name else None
        if path is None or not os.path.isfile(path):
            return Fetched(None, Origin("none", None, None, f"no {name} in the fixture directory"))
        return _read_named(source, path)
    return fetch


def local(path: str) -> Fetch:
    """One named file, for whichever source it is passed as. Opens no URL and
    never reads or writes the cache; a file that cannot be read is an error."""
    def fetch(source, renew):
        return _read_named(source, path)
    return fetch


# --- the web adapter -------------------------------------------------------------

def _web(root, source, url_of, accept, read, get, clock, renew):
    """Reuse the artifact under MAX_AGE unless `renew`; else fetch, and keep
    the new artifact only once it parsed. A fetch that fails gives the newest
    artifact on hand, whatever its age, with the failure (decision H.2)."""
    artifact = os.path.join(root, source, _ARTIFACT[source])
    now = clock()
    on_hand = read(artifact)
    age = now - os.path.getmtime(artifact) if on_hand is not None else None
    if on_hand is not None and not renew and 0 <= age < MAX_AGE:
        return Fetched(on_hand, Origin("cache", artifact, age, None))
    url = None
    try:
        url = url_of()
        rows = _replace(root, source, artifact, lambda staging: accept(get(url), url, staging), now)
    except Exception as e:  # a source that is down is a note, never a stop
        failure = str(e)
        # the URLs are this module's to know, so the reason the rows line
        # shows leaves the one `effort.fetch_page` puts in front of it out
        if url and failure.startswith(f"{url}: "):
            failure = failure[len(url) + 2:]
        if on_hand is not None:
            return Fetched(on_hand, Origin("cache", artifact, age, failure))
        return Fetched(None, Origin("none", None, None, failure))
    return Fetched(rows, Origin("fetched", artifact, 0.0, None))


def _replace(root, source, artifact, accept, now):
    """Run `accept` in a temporary directory beside the source's directory,
    then move what it wrote into that directory, the artifact last."""
    os.makedirs(os.path.join(root, source), exist_ok=True)
    staging = tempfile.mkdtemp(prefix=f".{source}-", dir=root)
    try:
        rows, files = accept(staging)
        for name in files:
            os.replace(os.path.join(staging, name), os.path.join(root, source, name))
        os.utime(artifact, (now, now))
        return rows
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _accept_aa(raw, url, staging):
    _checked, accepted, _rejected = effort.aa_accept(raw, url, staging, quiet=True)
    if not accepted:
        raise ValueError("no row of the page passed the check")
    return accepted, ("packet.txt", "rows.json", "rejected.json", "accepted.json")


def _accept_epoch(raw, url, staging):
    rows = _parse_epoch(raw.decode("utf-8-sig"))
    with open(os.path.join(staging, _ARTIFACT[EPOCH]), "wb") as f:
        f.write(raw)
    return rows, (_ARTIFACT[EPOCH],)


def _read_aa(path):
    """The cached accepted rows, or None when there are none to read."""
    try:
        rows = load_effort_rows([path])
    except ValueError:
        return None
    return rows


def _read_epoch(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return _parse_epoch(f.read())
    except (OSError, UnicodeDecodeError, ValueError):
        return None


# --- named files -------------------------------------------------------------------

def _read_named(source, path):
    """A named file's rows, or an error naming it."""
    try:
        if source == AA:
            rows = load_effort_rows([path])
        elif source == EPOCH:
            try:
                with open(path, "r", encoding="utf-8-sig", newline="") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError) as e:
                raise ValueError(f"epoch-csv: cannot read Epoch CSV: {e}") from e
            try:
                rows = _parse_epoch(text)
            except ValueError as e:
                raise ValueError(f"epoch-csv: {path}: {e}") from e
        else:
            raise ValueError(f"{path}: no source {source}")
    except ValueError as e:
        return Fetched(None, Origin("none", path, None, str(e)), error=str(e))
    try:
        age = max(0.0, time.time() - os.path.getmtime(path))
    except OSError:
        age = None
    return Fetched(rows, Origin("file", path, age, None))


# --- Epoch's CSV -----------------------------------------------------------------

def _parse_epoch(text):
    """The rows on EPOCH_BENCHMARKS, each keeping `model` and the `slug` and
    `effort` its model_version carries. Raises ValueError without the header."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != _EPOCH_HEADER:
        raise ValueError("Epoch CSV missing expected header")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != _EPOCH_FIELDS:
        raise ValueError("Epoch CSV missing expected header")
    rows = []
    for raw in reader:
        benchmark = (raw.get("benchmark") or "").strip()
        if benchmark not in EPOCH_BENCHMARKS:
            continue
        performance = _number(raw.get("performance"))
        if performance is None:
            continue
        model_version = (raw.get("model_version") or "").strip()
        slug, effort_level = _split_model_version(model_version)
        rows.append({
            "benchmark": benchmark,
            "performance": performance,
            "model_version": model_version,
            "slug": slug,
            "effort": effort_level,
            "source": (raw.get("source") or "").strip(),
            "model": (raw.get("model") or "").strip(),
            "date": (raw.get("date") or "").strip(),
            "benchmark_release_date": (raw.get("benchmark_release_date") or "").strip(),
        })
    return rows


def _split_model_version(model_version):
    text = (model_version or "").strip()
    if not text:
        return "", "unknown"
    if "_" not in text:
        return text, "unknown"
    slug, effort_level = text.rsplit("_", 1)
    if not slug:
        return text, "unknown"
    if not effort_level:
        return slug, "unknown"
    return slug, effort_level


def _number(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


# --- the merge, the fallback and the note -----------------------------------------

def _ask(adapter, source, renew):
    """An adapter's answer; one that raises is a failure, never a stop."""
    try:
        return adapter(source, renew)
    except Exception as e:
        return Fetched(None, Origin("none", None, None, str(e)))


def _has_aa(rows):
    return any(isinstance(row, dict) and row.get("source") == AA for row in rows or ())


def _merge(named, fetched):
    """The named rows with `fetched` in place of every named AA row, at the
    first one's position, or appended when no named row is AA's."""
    out, placed = [], False
    for row in named or ():
        if isinstance(row, dict) and row.get("source") == AA:
            if not placed:
                out.extend(fetched)
                placed = True
            continue
        out.append(row)
    if not placed:
        out.extend(fetched)
    return out


def _ago(seconds):
    if seconds < 60:
        return "just now"
    if seconds < 60 * 60:
        return f"{int(seconds // 60)}m ago"
    if seconds < 2 * MAX_AGE:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // MAX_AGE)}d ago"


def _status(source, origin, named):
    """Where one source's rows came from, in a few words."""
    name = _NAMES[source]
    if origin is None:
        # no adapter: the named rows, if they hold any of this source's
        return f"{name} from --effort-rows" if source == AA and _has_aa(named) else f"{name} skipped"
    if origin.how == "fetched":
        return f"{name} fetched just now"
    if origin.how == "cache":
        return f"{name} fetched {_ago(origin.age or 0.0)}"
    if origin.how == "file":
        return f"{name} read from {os.path.basename(origin.path or '')}"
    if origin.how == "rows":
        return f"{name} from --effort-rows"
    return f"{name} skipped"


def _reason(source, origin, named):
    """Why one source's rows are not fresh, or None when they are."""
    if origin is None:
        # what would have read it
        if source == AA:
            return None if _has_aa(named) else "no rows named"
        return "no --epoch-csv"
    return origin.failure


def _note(origins, named, any_named):
    """The start page's rows line: where each source's rows came from, both
    on one line and AA first, then why any of them is not fresh, so a
    terminal too narrow for the reasons still shows both sources.
    A reason both sources share is said once. Empty when nothing was named
    and no source had an adapter, because then nothing was read."""
    if not origins and not any_named:
        return ""
    sources = (AA, EPOCH)
    line = "Benchmark rows: " + ", ".join(_status(s, origins.get(s), named) for s in sources)
    reasons = {}
    for source in sources:
        reason = _reason(source, origins.get(source), named)
        if reason:
            reasons.setdefault(reason, []).append(_NAMES[source])
    for reason, names in reasons.items():
        line += f"; {' and '.join(names)}: {reason}"
    return line
