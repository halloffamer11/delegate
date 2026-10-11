#!/usr/bin/env python3
"""usage.py — read subscription usage for each installed agent CLI, headlessly.

Emits one JSON document with one row per Meter (under its `lanes` key). Each
harness's adapter probes its CLI and hands back Windows (`harnesses.base`);
this module builds the rows from them. Per Meter:
  r      = min(remaining_5h, remaining_weekly): the gate (availability).
           Every meter with two windows is read this way, agy included; no
           vendor publishes a joint bound, so agy carries a note saying the
           combined figure is the lower window, an assumption (ticket 31).
  pace   = remaining_weekly / fraction of the weekly cycle still to run.
           1.0 = spending evenly; >1 = ahead (under-used, will expire unspent);
           <1 = behind (over-spent). Cycle length is assumed 7 days.
  score  = pace when the weekly meter and its reset are known, else r.
           rank.py sorts on pace. The 5h window is a rate cap, not a budget:
           what expires unspent is the weekly allotment, so pace is the thing
           to balance.

Codex, agy, and grok probes are status/RPC commands. The Claude probe runs
`claude -p /usage` and can spend the meter being measured.

  usage.py            serve cache if younger than TTL, else re-probe
  usage.py --refresh  force re-probe
  usage.py --max-age-min N   override TTL (default 10)
  usage.py --cache PATH      the document to read and write (default cache_path())
  usage.py --pretty   one line per Meter, from its Readout, instead of JSON

Cache: cache_path() — the explicit path, else $DELEGATE_CACHE, else
$CONSULT_CACHE, else ~/.cache/delegate/usage.json. Absence of a CLI, auth
failure, or a probe timeout marks that lane "unknown" — never a crash. Exit 0
always. A probe writes nothing to the Ledger, which records Runs only.

The Meters module (tickets 16 to 19): `read(routing, freshness, path=...)`
returns a Meter snapshot, and `Snapshot.readout(meter, cat)` answers one
Meter's Remaining, Pace, Weekly figure, Gate and plan price for a given
catalog. Freshness is CACHED (never probes), FRESH (probes when the reading
is older than ten minutes) or FORCED (probes now); a probe runs this file as
a child process with `--refresh --cache PATH` under one 180 s bound, and
with routing.meters off neither FRESH nor FORCED probes. Validation, the
legacy rows, the derived figures and the usage-limit hold (`hold`,
`release`, in `limits.json` beside the document read) live behind them.
Its public names are CACHED, FRESH, FORCED, MAX_PACE, read, hold, release,
cache_path, Snapshot, Readout and main; everything else here is private.
"""
from __future__ import annotations

import hashlib, json, math, os, subprocess, sys, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Each harness's probe lives in its adapter (scripts/harnesses/) and hands back
# Windows; this module owns the rows built from them, the cache and the
# combined figures.
import harnesses  # noqa: E402
import catalog  # noqa: E402

CACHED = "cached"     # the document as it is; never probes
FRESH = "fresh"       # probe when the reading is older than max_age_min (default 10) or absent
FORCED = "forced"     # probe now
_FRESHNESS = (CACHED, FRESH, FORCED)

_MAX_AGE_MIN = 10     # FRESH's age, in minutes
_PROBE_BOUND = 180    # seconds: the one bound around the probe child (decision B.5)
_WEEK_DAYS = 7
_DAYS_PER_MONTH = 30.4375
_WEEK = _WEEK_DAYS * 86400   # assumed weekly-cycle length for pace
_CYCLE_FLOOR = 0.02   # ~3.4h: pace denominator floor near a reset
_ROLLOVER_MIN = 30    # binding window resets within this → ask user whether to wait
MAX_PACE = 1 / _CYCLE_FLOOR   # the highest Pace a Meter can read: a full week at its reset (50)


def cache_path(path=None):
    """The usage document a read names: `path`, else $DELEGATE_CACHE, else
    $CONSULT_CACHE, else ~/.cache/delegate/usage.json."""
    chosen = os.fspath(path) if path else (
        os.environ.get("DELEGATE_CACHE") or os.environ.get("CONSULT_CACHE")
        or "~/.cache/delegate/usage.json")
    return os.path.expanduser(chosen)


def _week_dollars(meter_def):
    """A catalog Meter's plan price per week, or None when it has no price."""
    pm = (meter_def or {}).get("price_month")
    if type(pm) is bool or not isinstance(pm, (int, float)):
        return None
    return pm * _WEEK_DAYS / _DAYS_PER_MONTH


def _valid_meter_number(value, *, fraction=False):
    if value is None:
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        number = float(value)
    except OverflowError:
        return False
    return math.isfinite(number) and (0 <= number <= 1 if fraction else number >= 0)


def _binding(five_h, weekly):
    """The Window that sets Remaining: "weekly" when it is the lower one or
    the only one read, "5h" when that is, None when neither was read."""
    if weekly is not None and (five_h is None or weekly <= five_h):
        return "weekly"
    return "5h" if five_h is not None else None


def _combined(five_h, weekly, reset_5h=None, reset_wk=None, now=None):
    """The figures every Meter derives from its raw Window values.

    Remaining is the lower of the Window fractions, and Pace divides the weekly
    fraction by the share of the week still to run at `now` (default: the
    clock). One arithmetic for every harness: agy has a 5-hour and a weekly
    Window like the Claude Meters, so it is read the same way (ticket 31).
    """
    now = time.time() if now is None else now
    known = [x for x in (five_h, weekly) if x is not None]
    r = min(known) if known else None
    binding = _binding(five_h, weekly)
    reset = reset_wk if binding == "weekly" else reset_5h
    cycle_left = pace = None
    if weekly is not None and reset_wk:
        cycle_left = min(1.0, max(_CYCLE_FLOOR, (reset_wk - now) / _WEEK))
        pace = round(weekly / cycle_left, 3)
    return {"r": r, "binding": binding, "reset_binding": reset,
            "cycle_left": cycle_left, "pace": pace,
            "score": pace if pace is not None else r,
            # Observation quality is independent of a project's effective Gate.
            "status": "unknown" if r is None else "ok"}


def _row_meter(entry):
    """The Meter a usage row is for. A row written before ticket 25 named it
    under `lane` and kept the probe group under `meter`."""
    if not isinstance(entry, dict):
        return None
    return entry.get("lane") if "lane" in entry else entry.get("meter")


def _upgraded(entry):
    """A usage row in the current shape: an old row's `lane` becomes `meter`
    and its `meter` the `group`, so old caches still read."""
    if not isinstance(entry, dict) or "lane" not in entry:
        return entry
    out = dict(entry)
    out["group"] = out.get("meter")
    out["meter"] = out.pop("lane")
    return out


def _filled(observation, now=None):
    """Derive the combined figures a cache is missing. Never overwrites one.

    A cache written while agy figures were forced unknown holds the Windows
    beside a null Remaining and Pace. Reading it derives them by the same
    arithmetic a probe uses, at `now` (a Meter snapshot passes the moment of
    its reading), so the figures need no fresh probe. An observation that
    already carries a Remaining or a Pace is returned untouched, and one with
    no Window at all stays unknown.
    """
    if not isinstance(observation, dict):
        return observation
    observation = _upgraded(observation)
    if observation.get("r") is not None or observation.get("pace") is not None:
        return observation
    if observation.get("remaining_5h") is None and observation.get("remaining_weekly") is None:
        return observation
    out = dict(observation)
    out.update(_combined(out.get("remaining_5h"), out.get("remaining_weekly"),
                         out.get("reset_5h"), out.get("reset_weekly"), now=now))
    note = out.get("note")
    for h in harnesses.REGISTRY:
        for old, new in h.note_renames:
            if note and old in str(note):
                note = out["note"] = str(note).replace(old, new)
    return out


# ---------------------------------------------------------------- the usage-limit hold
# A harness that refused a run for its usage limit holds its Meter at nothing
# left until the Meter's reset, at most this long (ticket 43): a probe can read
# a quota the refusal shows is not the one that binds. The hold lives in
# limits.json beside the usage document it overlays, whichever document that is.
_HOLD_LONGEST = 24 * 3600


def _holds_path(document_path):
    return os.path.join(os.path.dirname(document_path) or ".", "limits.json")


def _read_holds(document_path):
    """{meter: {"at", "until", "reset", "reason"}} beside the document, or {}."""
    try:
        with open(_holds_path(document_path), "r", encoding="utf-8") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_holds(document_path, doc):
    p = _holds_path(document_path)
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, p)


def _hold_until(held, reset_weekly, now):
    """When a hold still in force on a row with this weekly reset ends, or None."""
    if not isinstance(held, dict):
        return None
    until = held.get("until")
    if (isinstance(until, bool) or not isinstance(until, (int, float))
            or not math.isfinite(until) or until <= now):
        return None
    if held.get("reset") is not None and reset_weekly not in (None, held["reset"]):
        # the vendor reset the Meter early: the probe's reading stands again
        return None
    return until


def _held_note(until):
    stamp = datetime.fromtimestamp(until, timezone.utc).strftime('%Y-%m-%d %H:%MZ')
    return f"usage limit reached (held until {stamp})"


def hold(meter, reason, *, path=None, now=None):
    """Hold `meter` at nothing left beside the document at `path` (cache_path()):
    until that document's weekly reset for the Meter when it comes within 24
    hours, else for 24 hours. Returns the until time. Raises OSError when the
    hold file cannot be written."""
    p = cache_path(path)
    now = time.time() if now is None else now
    until = now + _HOLD_LONGEST
    reset = None
    status, _detail, document = _read_document(p)
    parsed = _parse(document) if status == "ok" else None
    row = parsed[1].get(meter) if parsed else None
    if row is not None:
        reset = row.get("reset_weekly")
        if isinstance(reset, (int, float)) and now < reset < until:
            until = reset
    doc = _read_holds(p)
    # `reset` is the reset the probe read when the harness refused: a probe
    # that reads a different one has seen the vendor start a new period
    doc[meter] = {"at": now, "until": until, "reset": reset, "reason": str(reason)[:200]}
    _write_holds(p, doc)
    return until


def release(meter, *, path=None):
    """A run on `meter` finished, so its hold beside the document at `path`
    no longer stands. Raises OSError when the hold file cannot be written."""
    p = cache_path(path)
    doc = _read_holds(p)
    if meter in doc:
        del doc[meter]
        _write_holds(p, doc)


def _limited(observation, holds, now):
    until = (_hold_until(holds.get(_row_meter(observation)), observation.get("reset_weekly"), now)
             if isinstance(observation, dict) else None)
    if until is None:
        return observation
    out = dict(observation)
    out.update({"remaining_weekly": 0.0, "r": 0.0, "pace": 0.0, "score": 0.0,
                "binding": "weekly", "status": "limited"})
    note = _held_note(until)
    out["note"] = f"{out['note']}; {note}" if out.get("note") else note
    return out


def _fill_document(document, document_path=None):
    """Return a copy whose observations carry their combined figures, and a
    Meter its harness refused for a usage limit reads empty. Does not write.

    The overlay of the document `usage.py` prints (`delegate status --json`);
    every other reader reads a Snapshot.
    """
    if not isinstance(document, dict):
        return document
    out = dict(document)
    if "lanes" in out and isinstance(out["lanes"], list):
        holds, now = _read_holds(cache_path(document_path)), time.time()
        out["lanes"] = [_limited(_filled(entry), holds, now) for entry in out["lanes"]]
        return out
    return {name: _filled(obs) for name, obs in out.items()}


# ---------------------------------------------------------------- validity
def _parse(document):
    """(taken_at, {meter: row}) for a valid document, rows in document order
    and in the current shape; None for a malformed one.

    Accept the usage-cache envelope and the legacy bare Meter map (no
    taken_at). Invalid observations make the whole document unknown,
    consistently for every caller. No Window value is repaired here.
    """
    if not isinstance(document, dict):
        return None
    if "lanes" in document:
        taken_at = document.get("probed_at")
        if taken_at is None or not _valid_meter_number(taken_at):
            return None
        if not isinstance(document["lanes"], list):
            return None
        entries = []
        for entry in document["lanes"]:
            if not isinstance(entry, dict):
                return None
            entries.append((_row_meter(entry), entry))
    else:
        taken_at = None
        entries = list(document.items())
    rows = {}
    for name, observation in entries:
        if not isinstance(name, str) or not name or not isinstance(observation, dict):
            return None
        if not _valid_meter_number(observation.get("r"), fraction=True):
            return None
        if not _valid_meter_number(observation.get("pace")):
            return None
        for key in ("remaining_weekly", "remaining_5h", "remaining_weekly_model"):
            if not _valid_meter_number(observation.get(key), fraction=True):
                return None
        for key in ("reset_5h", "reset_weekly", "reset_binding"):
            if not _valid_meter_number(observation.get(key)):
                return None
        if "status" in observation and not isinstance(observation["status"], str):
            return None
        rows[name] = _upgraded(observation)
    return (None if taken_at is None else float(taken_at)), rows


# ---------------------------------------------------------------- the Meter snapshot
@dataclass(frozen=True)
class Readout:
    """One Meter's facts in one snapshot, joined with one catalog's policy."""
    meter: Optional[str]
    harness: Optional[str]
    group: Optional[str]
    remaining: Optional[float]     # Remaining, with any usage-limit hold applied
    pace: Optional[float]
    weekly: Optional[float]        # the Weekly figure: Pace's numerator and what every display shows
    five_h: Optional[float]
    shares_five_h: bool            # a Model meter: its 5h cell belongs to the harness row
    reset_weekly: Optional[float]
    reset_5h: Optional[float]
    week_left: Optional[float]     # share of the week left at the reading: Pace's divisor
    gated: bool                    # routing.meters on and Remaining under the Gate
    week_dollars: Optional[float]  # the catalog Meter's plan price per week
    held_until: Optional[float]    # a usage-limit hold in force, or None
    note: Optional[str]


@dataclass(frozen=True)
class Snapshot:
    """Every Meter's reading at one moment, with the holds beside it fixed.

    `read` builds one from the usage document; `Snapshot.of` from an
    in-memory document, which carries no holds. Never hashed by a caller; the
    maps below take no part in equality or hashing.
    """
    path: Optional[str]            # the document read; None for Snapshot.of
    status: str                    # ok | missing | unreadable | malformed | stale
    detail: Optional[str]          # plain words for any status but ok
    taken_at: Optional[float]      # when the probe read it; None for a legacy bare map or no reading
    signature: tuple               # equal for two reads that would rank alike
    _rows: dict = field(default_factory=dict, compare=False, hash=False, repr=False)
    _held: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    @classmethod
    def of(cls, document) -> "Snapshot":
        """An in-memory document with no holds (fixtures, evals)."""
        return _snapshot(document, path=None, holds={}, now=time.time())

    def names(self) -> Tuple[str, ...]:
        """The Meters with a reading, in document order."""
        return tuple(self._rows)

    def readout(self, meter, cat, *, spend=0.0) -> Readout:
        """One Meter joined with `cat`'s Gate, metering switch, Model meter
        flag and plan price. An unknown or None Meter reads unknown; `cat`
        None has no Gate.

        `spend` asks what the Meter would read with that fraction more of its
        week spent: the Weekly figure falls by it, never below 0; Remaining is
        the lower of the 5h Window and that; Pace is that over the share of the
        week left (unknown when that share is); and the Gate is asked again. A
        held Meter stays at 0, and spend=0 is the reading itself. A spend
        outside 0..1 raises ValueError.
        """
        if (isinstance(spend, bool) or not isinstance(spend, (int, float))
                or not 0 <= spend <= 1):
            raise ValueError(f"spend must be a fraction from 0 to 1, not {spend!r}")
        cat = cat if isinstance(cat, dict) else None
        meter_def = ((cat or {}).get("meters") or {}).get(meter) if meter else None
        meter_def = meter_def if isinstance(meter_def, dict) else {}
        model_meter = meter_def.get("model_meter") is True
        row = self._rows.get(meter) if meter else None
        if row is None:
            return Readout(meter=meter, harness=meter_def.get("harness"), group=None,
                           remaining=None, pace=None, weekly=None, five_h=None,
                           shares_five_h=model_meter, reset_weekly=None, reset_5h=None,
                           week_left=None, gated=False, week_dollars=_week_dollars(meter_def),
                           held_until=None, note=None)
        remaining, pace, weekly = row.get("r"), row.get("pace"), row.get("remaining_weekly")
        note = row.get("note")
        held_until = self._held.get(meter)
        if held_until is not None:
            remaining = pace = weekly = 0.0
            note = f"{note}; {_held_note(held_until)}" if note else _held_note(held_until)
        elif spend and weekly is not None:
            weekly = max(0.0, weekly - spend)
            five_h, week_left = row.get("remaining_5h"), row.get("cycle_left")
            remaining = weekly if five_h is None else min(five_h, weekly)
            pace = weekly / week_left if week_left else None
        routing = (cat or {}).get("routing")
        routing = routing if isinstance(routing, dict) else {}
        gate = routing.get("gate")
        gated = (cat is not None and catalog.meters_enabled(routing) and remaining is not None
                 and not isinstance(gate, bool) and isinstance(gate, (int, float))
                 and remaining < gate)
        return Readout(
            meter=meter, harness=row.get("harness") or meter_def.get("harness"),
            group=row.get("group"), remaining=remaining, pace=pace, weekly=weekly,
            five_h=row.get("remaining_5h"),
            shares_five_h=model_meter or row.get("remaining_weekly_model") is not None,
            reset_weekly=row.get("reset_weekly"), reset_5h=row.get("reset_5h"),
            week_left=row.get("cycle_left"), gated=gated,
            week_dollars=_week_dollars(meter_def), held_until=held_until,
            note=None if note is None else str(note))


def _unknown(path, status, detail):
    return Snapshot(path=path, status=status, detail=detail, taken_at=None,
                    signature=(status, detail))


def _snapshot(document, *, path, holds, now):
    parsed = _parse(document)
    if parsed is None:
        return _unknown(path, "malformed",
                        "Meter cache has an invalid row or timestamp; every Meter is unknown.")
    taken_at, rows = parsed
    at = now if taken_at is None else taken_at
    figures = {name: _filled(r, now=at) for name, r in rows.items()}
    held = {}
    for name, r in figures.items():
        until = _hold_until(holds.get(name), r.get("reset_weekly"), now)
        if until is not None:
            held[name] = until
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return Snapshot(path=path, status="ok", detail=None, taken_at=taken_at,
                    signature=("ok", taken_at, digest, tuple(sorted(held.items()))),
                    _rows=figures, _held=held)


def _strict_json(raw):
    def reject_constant(value):
        raise ValueError(f"{value} is not valid JSON")
    return json.loads(raw.decode("utf-8"), parse_constant=reject_constant)


def _read_document(path):
    """(status, detail, document) for the file at `path`; document None unless ok."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return "missing", "Meter cache is missing; every Meter is unknown.", None
    except OSError as exc:
        return "unreadable", f"Meter cache cannot be read; every Meter is unknown: {exc}", None
    try:
        return "ok", None, _strict_json(raw)
    except (UnicodeError, ValueError):
        return "malformed", "Meter cache is not valid JSON; every Meter is unknown.", None


def _cached(path):
    """The Snapshot of the document at `path` as it is, with the holds beside it."""
    status, detail, document = _read_document(path)
    if status != "ok":
        return _unknown(path, status, detail)
    return _snapshot(document, path=path, holds=_read_holds(path), now=time.time())


def _fresh_enough(snap, max_age_min):
    """True when `snap` is a reading no older than `max_age_min` minutes."""
    if snap.status != "ok" or snap.taken_at is None:
        return False
    return 0 <= time.time() - snap.taken_at <= max_age_min * 60


def _probe(path):
    """Probe every harness in the usage.py child process, which writes the
    document at `path`, under the one bound. True when the child finished.
    It is a child process so that a stream read that blocks despite an
    adapter's own timeout cannot hold the caller past the bound."""
    command = [sys.executable, os.path.abspath(__file__), "--refresh", "--cache", path]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=_PROBE_BOUND)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def read(routing, freshness, *, path=None, max_age_min=None) -> Snapshot:
    """The Meter snapshot at `path` (cache_path()), with the holds beside it.

    CACHED reads the document as it is and never probes or writes. FRESH
    probes when the reading is older than `max_age_min` (default 10) minutes
    or absent; FORCED probes now. Either probes only when `routing` has
    metering on, or when `routing` is None (a person's own `delegate status
    --refresh`); otherwise it reads as CACHED. A probe writes the document at
    the read's own path and nothing to the Ledger. A probe that fails or
    outlasts its 180 s bound gives the last reading when that is fresh
    enough, and otherwise a Snapshot whose status is `stale`.

    Never raises for I/O, JSON, validation or probe failure: the Snapshot's
    `status` and `detail` say why its Meters are unknown. It catches
    Exception only, so a Run's termination passes through. An unknown
    freshness raises ValueError.
    """
    if freshness not in _FRESHNESS:
        raise ValueError(f"unknown freshness {freshness!r}; expected one of {', '.join(_FRESHNESS)}")
    p = cache_path(path)
    try:
        if freshness == CACHED or (routing is not None and not catalog.meters_enabled(routing)):
            return _cached(p)
        age = _MAX_AGE_MIN if max_age_min is None else max_age_min
        if freshness == FRESH:
            last = _cached(p)
            if _fresh_enough(last, age):
                return last
        if _probe(p):
            return _cached(p)
        last = _cached(p)
        if _fresh_enough(last, age):
            return last
        return _unknown(p, "stale", f"Meter probe failed or outlasted {_PROBE_BOUND} s, and the last "
                                    f"reading is older than {age:g} min; every Meter is unknown.")
    except Exception as exc:  # never BaseException: a Run's SIGTERM passes through
        return _unknown(p, "unreadable", f"Meter cache cannot be read; every Meter is unknown: {exc}")


# ---------------------------------------------------------------- rows from Windows
def _fraction(value):
    """A remaining fraction held to [0, 1], or None.

    A vendor can print more than 100% used (an overage, or a rounding past the
    cap), which reads as a negative fraction. One such row would fail the
    document's validation and take every Meter's figures, and so the Gate,
    with it; an overspent Window has nothing left, so it reads 0.
    """
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if math.isnan(value):
        return value
    return min(1.0, max(0.0, value))


def _row(harness, windows, now):
    """One usage row from the Windows a probe of `harness` handed back: the
    fractions held to 0..1 and the combined figures at `now`. A Model meter's
    Weekly figure (`remaining_weekly`) is the lower of its own week and its
    harness's week for all models (decision B.1); its own week stays in
    `remaining_weekly_model`."""
    five_h, weekly, own_week = (_fraction(x) for x in (windows.five_h, windows.weekly, windows.weekly_model))
    if own_week is not None:
        weekly = own_week if weekly is None else min(weekly, own_week)
    row = {"meter": windows.meter, "harness": harness, "group": windows.group,
           "remaining_5h": five_h, "remaining_weekly": weekly,
           "remaining_weekly_model": own_week,
           "reset_5h": windows.reset_5h, "reset_weekly": windows.reset_weekly,
           "rollover_soon": False, "note": windows.note}
    row.update(_combined(five_h, weekly, windows.reset_5h, windows.reset_weekly, now=now))
    return row


# ---------------------------------------------------------------- main: the probe child
def _young_document(path, max_age_min):
    """The valid usage document at `path` when it is no older than
    `max_age_min` minutes, else None."""
    status, _detail, d = _read_document(path)
    if status != "ok" or not isinstance(d, dict) or "lanes" not in d:
        return None
    parsed = _parse(d)
    if parsed is None or parsed[0] is None:
        return None
    return d if 0 <= time.time() - parsed[0] <= max_age_min * 60 else None


def _write_document(d, p):
    """Write the usage document at `p`, whole or not at all. Nothing goes to
    the Ledger: it records Runs only (decision C.2)."""
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, p)


def _probe_document(path):
    """Run every harness's probe and write the document at `path`, one row per
    Meter from the Windows each adapter hands back, its figures at the moment
    of the reading. Timeouts and per-harness failures stay inside each
    adapter's `meters` (Windows with nothing read)."""
    probed = [(h.name, windows) for h in harnesses.REGISTRY for windows in h.meters()]
    now = time.time()
    d = {"probed_at": now, "probed_at_iso": datetime.fromtimestamp(now, timezone.utc).isoformat(),
         "rollover_min": _ROLLOVER_MIN, "lanes": [_row(name, w, now) for name, w in probed]}
    _write_document(d, path)
    return d


def _pretty(snap, from_cache):
    """`--pretty`: one line per Meter from its Readout (decision B.4), with
    Pace, Remaining, both Windows (the weekly one the Weekly figure), the
    binding Window and its reset, and the note, any hold applied."""
    def pct(x):
        return "  ?" if x is None else f"{int(round(x * 100)):3d}%"
    age = "?" if snap.taken_at is None else int((time.time() - snap.taken_at) / 60)
    lines = [f"# usage (cache age {age} min, from_cache={from_cache})"]
    for name in snap.names():
        m = snap.readout(name, None)
        binding = _binding(m.five_h, m.weekly)
        reset = m.reset_weekly if binding == "weekly" else m.reset_5h if binding == "5h" else None
        stamp = datetime.fromtimestamp(reset).strftime("%b %d %H:%M") if reset else "-"
        pace = "   ?" if m.pace is None else f"{m.pace:4.2f}"
        state = "held" if m.held_until is not None else "unknown" if m.remaining is None else "ok"
        lines.append(f"{name:<18} pace={pace}  r={pct(m.remaining)}  5h={pct(m.five_h)}  wk={pct(m.weekly)}  "
                     f"binding={binding or '-':<6} reset={stamp:<12} {state}  {m.note or ''}".rstrip())
    return lines


def main(argv=None):
    """usage.py [--refresh] [--max-age-min N] [--cache PATH] [--pretty]: the
    usage document at PATH (cache_path()), probed when it is older than N
    minutes (10) or with --refresh. `read` runs this as its probe child with
    --refresh --cache PATH; `delegate status --json` runs it too."""
    args = sys.argv[1:] if argv is None else list(argv)
    refresh = "--refresh" in args; pretty = "--pretty" in args
    ttl = _MAX_AGE_MIN
    if "--max-age-min" in args: ttl = float(args[args.index("--max-age-min") + 1])
    path = cache_path(args[args.index("--cache") + 1] if "--cache" in args else None)
    d = None if refresh else _young_document(path, ttl)
    from_cache = d is not None
    if not from_cache:
        d = _probe_document(path)
    if pretty:
        print("\n".join(_pretty(_cached(path), from_cache)))
    else:
        d = _fill_document(d, path)
        d["from_cache"] = from_cache
        print(json.dumps(d, indent=1))

if __name__ == "__main__":
    main()
