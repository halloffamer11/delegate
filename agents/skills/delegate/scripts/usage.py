#!/usr/bin/env python3
"""usage.py — read subscription usage for each installed agent CLI, headlessly.

Emits one JSON document of *lanes* (harness × meter). Per lane:
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
  usage.py --pretty   human table instead of JSON

Cache: get_cache_path() — $DELEGATE_CACHE, else $CONSULT_CACHE, else
~/.cache/delegate/usage.json. Absence of a CLI, auth failure, or a probe
timeout marks that lane "unknown" — never a crash. Exit 0 always.

Public acquisition: load_cached() never probes and never writes a meter
event; probe(refresh=...) is the refresh/TTL path.
"""
import json, math, os, re, subprocess, sys, time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Each harness's probe lives in its adapter (scripts/harnesses/); this module
# owns the rows they build, the cache and the combined figures.
import harnesses  # noqa: E402
try:
    from events import append, meter_event
except ImportError:
    from .events import append, meter_event

TTL_MIN_DEFAULT = 10
WEEK = 7 * 86400      # assumed weekly-cycle length for pace
CYCLE_FLOOR = 0.02    # ~3.4h: pace denominator floor near a reset
ROLLOVER_MIN = 30     # binding window resets within this → ask user whether to wait

def get_cache_path():
    return os.environ.get("DELEGATE_CACHE") or os.environ.get("CONSULT_CACHE") or os.path.expanduser("~/.cache/delegate/usage.json")
CACHE = get_cache_path()

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


def combined(five_h, weekly, reset_5h=None, reset_wk=None):
    """The figures every Meter derives from its raw Window values.

    Remaining is the lower of the Window fractions, and Pace divides the weekly
    fraction by the share of the week still to run. One arithmetic for every
    harness: agy has a 5-hour and a weekly Window like the Claude Meters, so it
    is read the same way (ticket 31).
    """
    known = [x for x in (five_h, weekly) if x is not None]
    r = min(known) if known else None
    binding = None
    if r is not None:
        binding = "weekly" if (weekly is not None and (five_h is None or weekly <= five_h)) else "5h"
    reset = reset_wk if binding == "weekly" else reset_5h
    cycle_left = pace = None
    if weekly is not None and reset_wk:
        cycle_left = min(1.0, max(CYCLE_FLOOR, (reset_wk - time.time()) / WEEK))
        pace = round(weekly / cycle_left, 3)
    return {"r": r, "binding": binding, "reset_binding": reset,
            "cycle_left": cycle_left, "pace": pace,
            "score": pace if pace is not None else r,
            # Observation quality is independent of a project's effective Gate.
            "status": "unknown" if r is None else "ok"}


def _filled(observation):
    """Derive the combined figures a cache is missing. Never overwrites one.

    A cache written while agy figures were forced unknown holds the Windows
    beside a null Remaining and Pace. Reading it derives them by the same
    arithmetic a probe uses, so the figures need no fresh probe. An observation
    that already carries a Remaining or a Pace is returned untouched, and one
    with no Window at all stays unknown.
    """
    if not isinstance(observation, dict):
        return observation
    if observation.get("r") is not None or observation.get("pace") is not None:
        return observation
    if observation.get("remaining_5h") is None and observation.get("remaining_weekly") is None:
        return observation
    out = dict(observation)
    out.update(combined(out.get("remaining_5h"), out.get("remaining_weekly"),
                        out.get("reset_5h"), out.get("reset_weekly")))
    note = out.get("note")
    for h in harnesses.REGISTRY:
        for old, new in h.note_renames:
            if note and old in str(note):
                note = out["note"] = str(note).replace(old, new)
    return out


def _fill_document(document):
    """Return a copy whose observations carry their combined figures. Does not write."""
    if not isinstance(document, dict):
        return document
    out = dict(document)
    if "lanes" in out and isinstance(out["lanes"], list):
        out["lanes"] = [_filled(entry) for entry in out["lanes"]]
        return out
    return {name: _filled(obs) for name, obs in out.items()}


def observations(document):
    """Return validated observations by Meter, or None for a malformed document.

    Accept the usage-cache envelope and the legacy bare Meter map. Invalid
    observations make the whole document unknown, consistently for every caller.
    No Window value is repaired and this boundary never probes a vendor; a
    combined figure a cache never wrote is derived from the Windows (`_filled`).
    """
    if not isinstance(document, dict):
        return None
    if "lanes" in document:
        if document.get("probed_at") is None or not _valid_meter_number(document["probed_at"]):
            return None
        if not isinstance(document["lanes"], list):
            return None
        parsed = {}
        for entry in document["lanes"]:
            if not isinstance(entry, dict):
                return None
            name = entry.get("lane")
            if not isinstance(name, str) or not name:
                return None
            parsed[name] = entry
        entries = [(entry["lane"], entry) for entry in document["lanes"]]
    else:
        parsed = document
        entries = document.items()
    for name, observation in entries:
        if not isinstance(name, str) or not name or not isinstance(observation, dict):
            return None
        if not _valid_meter_number(observation.get("r"), fraction=True):
            return None
        if not _valid_meter_number(observation.get("pace")):
            return None
        for field in ("remaining_weekly", "remaining_5h", "remaining_weekly_model"):
            if not _valid_meter_number(observation.get(field), fraction=True):
                return None
        for field in ("reset_5h", "reset_weekly", "reset_binding"):
            if not _valid_meter_number(observation.get(field)):
                return None
        if "status" in observation and not isinstance(observation["status"], str):
            return None
    return {name: _filled(observation) for name, observation in parsed.items()}


def eligible(observation, gate):
    """Unknown Remaining never vetoes; Remaining equal to Gate is eligible."""
    if not observation or not isinstance(observation, dict):
        return True
    r = observation.get("r")
    if r is None:
        return True
    try:
        return float(r) >= float(gate)
    except (TypeError, ValueError, OverflowError):
        return True


def load_cached(cache_path=None):
    """Read the usage cache without probing or emitting a meter event.

    Missing or unreadable files become {}. A combined Remaining or Pace the
    cache lacks is derived in the returned copy; the file on disk is not
    rewritten.
    """
    path = cache_path or get_cache_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict) or observations(doc) is None:
            return {}
        return _fill_document(doc)
    except (OSError, ValueError):
        return {}

# Whether a harness's CLI is installed is catalog's one answer, so a probe says
# "absent" exactly when ranking does.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import cli_installed as which  # noqa: E402

def run(cmd, timeout=60, stdin_data=None, cwd=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=stdin_data, cwd=cwd)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

def lane(harness, meter, five_h=None, weekly=None, reset_5h=None, reset_wk=None, note=None, remaining_weekly_model=None):
    """five_h/weekly are REMAINING fractions (0..1) or None; resets are epoch seconds or None."""
    row = {"lane": f"{harness}-{meter}" if meter else harness, "harness": harness, "meter": meter,
           "remaining_5h": five_h, "remaining_weekly": weekly,
           "remaining_weekly_model": remaining_weekly_model,
           "reset_5h": reset_5h, "reset_weekly": reset_wk,
           "rollover_soon": False, "note": note}
    row.update(combined(five_h, weekly, reset_5h, reset_wk))
    return row

def iso(s):
    try: return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception: return None


# ---------------------------------------------------------------- main
def load_cache(max_age_min, cache_path=None):
    p = cache_path or get_cache_path()
    try:
        with open(p) as f: d = json.load(f)
        if (isinstance(d, dict) and "lanes" in d and observations(d) is not None
                and _valid_meter_number(d.get("probed_at"))
                and d.get("probed_at") is not None
                and 0 <= time.time() - d["probed_at"] <= max_age_min * 60):
            return d
    except Exception: pass
    return None

def write_cache(d, cache_path=None):
    p = cache_path or get_cache_path()
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(p, "w") as f:
        json.dump(d, f, indent=1)
    append(meter_event(d))

def probe(refresh=False, max_age_min=None, cache_path=None):
    """Return a usage document, probing vendors when the cache is missing or stale.

    refresh=True always probes. A cache hit emits no meter event. Timeout and
    per-harness failures stay inside each adapter's probe (unknown rows).
    """
    ttl = TTL_MIN_DEFAULT if max_age_min is None else max_age_min
    d = None if refresh else load_cache(ttl, cache_path=cache_path)
    if d is None:
        lanes = []
        for h in harnesses.REGISTRY:
            lanes += h.probe()
        now = time.time()
        d = {"probed_at": now, "probed_at_iso": datetime.fromtimestamp(now, timezone.utc).isoformat(),
             "rollover_min": ROLLOVER_MIN, "lanes": lanes}
        write_cache(d, cache_path=cache_path)
        d = _fill_document(d)
        d["from_cache"] = False
    else:
        d = _fill_document(d)
        d["from_cache"] = True
    return d

def acquire(refresh=False, max_age_min=None, timeout=180):
    """Shared bounded acquisition for callers; cached-only viewers use load_cached.

    Keep a process boundary around vendor probes: their stream reads may block
    despite per-vendor timeouts. The CLI process owns probe/cache/event writes.
    A timeout or failed probe returns a valid, fresh cached document, or {}.
    """
    command = [sys.executable, os.path.abspath(__file__)]
    if refresh:
        command.append("--refresh")
    if max_age_min is not None:
        command.extend(["--max-age-min", str(max_age_min)])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            doc = json.loads(result.stdout)
            if isinstance(doc, dict) and observations(doc) is not None:
                return _fill_document(doc)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    cached = load_cache(TTL_MIN_DEFAULT if max_age_min is None else max_age_min)
    return _fill_document(cached) if cached is not None else {}


def main():
    args = sys.argv[1:]
    refresh = "--refresh" in args; pretty = "--pretty" in args
    ttl = TTL_MIN_DEFAULT
    if "--max-age-min" in args: ttl = float(args[args.index("--max-age-min") + 1])
    d = probe(refresh=refresh, max_age_min=ttl)
    if pretty:
        age = int((time.time() - d["probed_at"]) / 60)
        print(f"# usage (cache age {age} min, from_cache={d['from_cache']})")
        for L in d["lanes"]:
            def f(x): return "  ?" if x is None else f"{int(round(x*100)):3d}%"
            rb = L.get("reset_binding")
            rb = datetime.fromtimestamp(rb).strftime("%b %d %H:%M") if rb else "-"
            pace = "   ?" if L.get('pace') is None else f"{L['pace']:4.2f}"
            print(f"{L['lane']:<18} pace={pace}  r={f(L['r'])}  5h={f(L['remaining_5h'])}  wk={f(L['remaining_weekly'])}  "
                  f"binding={L['binding'] or '-':<6} reset={rb:<12} {L['status']}"
                  f"{' ROLLOVER-SOON' if L['rollover_soon'] else ''}  {L.get('note') or ''}")
    else:
        print(json.dumps(d, indent=1))

if __name__ == "__main__":
    main()
