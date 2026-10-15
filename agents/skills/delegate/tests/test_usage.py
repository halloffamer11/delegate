#!/usr/bin/env python3
"""test_usage.py — the Meters module at its interface: usage.read, the Meter
snapshot and its Readouts, and the usage-limit hold (usage.hold, usage.release).

No network: every case reads a usage document it wrote into a temporary
directory, and a case that probes runs the probe child with no harness CLI on
PATH."""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# Run from a fresh directory with no Git root above it.
_ISOLATED_CWD = tempfile.TemporaryDirectory(prefix="delegate-test-")
os.chdir(_ISOLATED_CWD.name)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))
import usage  # noqa: E402

failures = []


def record(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures.append(name)


def write_doc(path, rows, taken_at=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"probed_at": time.time() if taken_at is None else taken_at, "lanes": rows}, f)
    return path


def row(meter, five_h=None, weekly=None, reset_weekly=None, **extra):
    """A usage row as a probe writes it: the Windows and their combined figures."""
    known = [x for x in (five_h, weekly) if x is not None]
    out = {"meter": meter, "harness": meter.split("-")[0], "group": None,
           "remaining_5h": five_h, "remaining_weekly": weekly,
           "reset_5h": None, "reset_weekly": reset_weekly,
           "r": min(known) if known else None, "pace": extra.pop("pace", None),
           "status": "ok" if known else "unknown", "note": None}
    out.update(extra)
    return out


def case_a_hold_lives_beside_the_document_it_overlays():
    """Three caches, A, B and C, each holding codex; DELEGATE_CACHE names C.
    A hold written at A ends at A's weekly reset and reaches only the reads of
    A, and its release lifts it there."""
    with tempfile.TemporaryDirectory() as td:
        now = time.time()
        paths = {}
        for name, reset in (("A", now + 3600), ("B", now + 7200), ("C", now + 7200)):
            paths[name] = write_doc(os.path.join(td, name, "usage.json"),
                                    [row("codex", 0.5, 0.5, reset_weekly=reset, pace=1.0)], taken_at=now)
        before = os.environ.get("DELEGATE_CACHE")
        os.environ["DELEGATE_CACHE"] = paths["C"]
        try:
            until = usage.hold("codex", "You've hit your usage limit", path=paths["A"], now=now)
            held = {name: usage.read(None, usage.CACHED, path=p).readout("codex", None)
                    for name, p in paths.items()}
            default = usage.read(None, usage.CACHED).readout("codex", None)
            usage.release("codex", path=paths["A"])
            released = usage.read(None, usage.CACHED, path=paths["A"]).readout("codex", None)
        finally:
            if before is None:
                os.environ.pop("DELEGATE_CACHE", None)
            else:
                os.environ["DELEGATE_CACHE"] = before
        record("1. a hold lives beside the document it overlays",
               until == now + 3600
               and held["A"].remaining == 0.0 and held["A"].held_until == now + 3600
               and held["B"].remaining == 0.5 and held["B"].held_until is None
               and held["C"].remaining == 0.5 and held["C"].held_until is None
               and default.remaining == 0.5
               and released.remaining == 0.5 and released.held_until is None,
               f"until={until - now} held={held} default={default} released={released}")


def case_a_usage_limit_hold_ends_at_the_reset_a_new_reset_a_finished_run_or_a_day():
    """Ticket 43's hold at the new interface: the refused Meter alone reads
    empty and under the Gate, until its reset, a probe that reads a new
    reset, a finished run (release) or 24 hours."""
    cat = {"routing": {"gate": 0.1}, "meters": {}}
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "usage.json")
        now = time.time()
        reset = now + 3600
        write_doc(cache, [row("grok", None, 1.0, reset_weekly=reset, pace=1.0),
                          row("codex", 0.5, 0.5, pace=1.0)], taken_at=now)
        until = usage.hold("grok", "You've reached your free Grok Build usage limit", path=cache, now=now)
        snap = usage.read(None, usage.CACHED, path=cache)
        grok, codex = snap.readout("grok", cat), snap.readout("codex", cat)
        record("2a. the hold ends at the Meter's reset when that comes first, and only it reads empty",
               until == reset and grok.remaining == 0.0 and grok.pace == 0.0 and grok.weekly == 0.0
               and grok.held_until == reset and grok.gated and "usage limit reached" in grok.note
               and codex.remaining == 0.5 and codex.held_until is None and not codex.gated,
               f"until={until - now} grok={grok} codex={codex}")

        write_doc(cache, [row("grok", None, 1.0, reset_weekly=reset + 7 * 86400, pace=1.0)], taken_at=now)
        moved = usage.read(None, usage.CACHED, path=cache).readout("grok", cat)
        record("2b. a probe that reads a new reset lifts the hold (the vendor reset early)",
               moved.remaining == 1.0 and moved.held_until is None, moved)

        write_doc(cache, [row("grok", None, 1.0, reset_weekly=reset, pace=1.0)], taken_at=now)
        usage.release("grok", path=cache)
        released = usage.read(None, usage.CACHED, path=cache).readout("grok", cat)
        record("2c. a finished run on the Meter releases its hold",
               released.remaining == 1.0 and released.held_until is None, released)

        write_doc(cache, [row("grok", None, 1.0, pace=1.0)], taken_at=now)
        until = usage.hold("grok", "limit", path=cache, now=now)
        record("2d. with no reset known the hold lasts 24 hours",
               until == now + 24 * 3600
               and usage.read(None, usage.CACHED, path=cache).readout("grok", cat).held_until == until,
               until - now)

        usage.hold("grok", "limit", path=cache, now=now - 2 * 86400)
        expired = usage.read(None, usage.CACHED, path=cache).readout("grok", cat)
        record("2e. an expired hold no longer applies",
               expired.remaining == 1.0 and expired.held_until is None, expired)

        blocked = os.path.join(td, "blocked")
        os.makedirs(os.path.join(blocked, "limits.json"))
        try:
            usage.hold("grok", "limit", path=os.path.join(blocked, "usage.json"))
            raised = False
        except OSError:
            raised = True
        record("2f. hold raises OSError when the hold file cannot be written", raised)


def case_validity_legacy_rows_and_the_bare_map():
    with tempfile.TemporaryDirectory() as td:
        now = time.time()
        good = write_doc(os.path.join(td, "good.json"),
                         [row("codex", 0.5, 0.6, pace=1.2), row("grok", None, 0.9, pace=0.9)], taken_at=now - 60)
        snap = usage.read(None, usage.CACHED, path=good)
        record("3a. a valid document reads ok, its Meters in document order, taken when the probe read it",
               snap.status == "ok" and snap.detail is None and snap.names() == ("codex", "grok")
               and snap.taken_at == now - 60 and snap.path == good,
               snap)

        missing = usage.read(None, usage.CACHED, path=os.path.join(td, "absent.json"))
        record("3b. a missing document is status missing, says so, and every Meter is unknown",
               missing.status == "missing" and missing.detail and missing.taken_at is None
               and missing.names() == () and missing.readout("codex", None).remaining is None,
               missing)

        unreadable = usage.read(None, usage.CACHED, path=td)
        record("3c. an unreadable path is status unreadable, not an exception",
               unreadable.status == "unreadable" and unreadable.detail and unreadable.names() == (),
               unreadable)

        for label, text in (("broken JSON", "{broken"),
                            ("a NaN", '{"probed_at": 1, "lanes": [{"meter": "codex", "pace": NaN}]}'),
                            ("an overflowing pace", '{"probed_at": 1, "lanes": [{"meter": "codex", "pace": 1e309}]}'),
                            ("a bad row beside a good one",
                             json.dumps({"probed_at": now, "lanes": [row("codex", 0.5, 0.5, pace=1.0),
                                                                     {"meter": "grok", "r": "bad"}]})),
                            ("no envelope timestamp", json.dumps({"lanes": [row("codex", 0.5, 0.5)]})),
                            ("a boolean timestamp", json.dumps({"probed_at": True, "lanes": []})),
                            ("a fraction past 1", json.dumps({"probed_at": now, "lanes": [row("codex", 0.5, 1.5)]}))):
            path = os.path.join(td, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            bad = usage.read(None, usage.CACHED, path=path)
            record(f"3d. {label} makes the whole document malformed and every Meter unknown",
                   bad.status == "malformed" and bad.detail and bad.taken_at is None
                   and bad.names() == () and bad.readout("codex", None).remaining is None,
                   bad)

        legacy = {"probed_at": now, "lanes": [
            {"lane": "agy-gemini", "harness": "agy", "meter": "gemini", "r": 0.4, "pace": 0.8,
             "remaining_weekly": 0.4, "status": "ok"}]}
        old_row = usage.Snapshot.of(legacy)
        gemini = old_row.readout("agy-gemini", None)
        record("3e. a row written before ticket 25 (`lane`, with the group under `meter`) reads in the current shape",
               old_row.status == "ok" and old_row.names() == ("agy-gemini",)
               and gemini.group == "gemini" and gemini.harness == "agy" and gemini.remaining == 0.4,
               (old_row, gemini))

        bare = usage.Snapshot.of({"codex": {"r": 0.5, "pace": 1.0}})
        record("3f. the legacy bare map reads ok, with no time taken and no path",
               bare.status == "ok" and bare.taken_at is None and bare.path is None
               and bare.readout("codex", None).remaining == 0.5,
               bare)

        record("3g. Snapshot.of a document that is not a usage document is malformed",
               usage.Snapshot.of([1, 2]).status == "malformed"
               and usage.Snapshot.of(None).names() == ())

        try:
            usage.read(None, "eventually", path=good)
            raised = False
        except ValueError:
            raised = True
        record("3h. an unknown freshness raises ValueError", raised)

        bad_stamps = [s for s in (None, float("nan"), "yesterday", True)
                      if usage.Snapshot.of({"lanes": [{"meter": "codex", "r": 0.5}], "probed_at": s}).status
                      != "malformed"]
        record("3j. an envelope needs a finite timestamp; a legacy bare map needs none",
               bad_stamps == [] and usage.Snapshot.of({"codex": {"r": 0.5}}).status == "ok", bad_stamps)

        passed = []
        for key in ("remaining_5h", "remaining_weekly_model", "reset_5h", "reset_weekly", "reset_binding"):
            for bad in ("bad", float("nan"), True, -1):
                doc = {"probed_at": now, "lanes": [row("codex", 0.5, 0.5, pace=1.0, **{key: bad})]}
                if usage.Snapshot.of(doc).status != "malformed":
                    passed.append((key, bad))
        record("3k. a bad Window or reset field makes the whole document malformed", passed == [], passed)

        with open(good, "rb") as f:
            before = f.read()
        usage.read(None, usage.CACHED, path=good)
        with open(good, "rb") as f:
            after = f.read()
        record("3i. a CACHED read writes nothing",
               before == after and not os.path.exists(os.path.join(td, "limits.json")))


def case_figures_derived_from_a_row_that_carries_only_windows():
    """A cache written while agy figures were forced unknown holds the Windows
    beside a null Remaining and Pace. The reading derives them at the moment
    the probe read it, and the superseded agy note gives way to the current one."""
    from harnesses.agy import COMBINED_NOTE, SUPERSEDED_NOTE
    taken_at = time.time() - 86400
    doc = {"probed_at": taken_at, "lanes": [
        {"meter": "agy-gemini", "harness": "agy", "group": "gemini",
         "remaining_5h": 0.8, "remaining_weekly": 0.9, "reset_5h": None,
         "reset_weekly": taken_at + 3.5 * 86400, "r": None, "pace": None,
         "status": "unknown", "note": SUPERSEDED_NOTE},
        {"meter": "codex", "harness": "codex", "remaining_5h": 0.5, "remaining_weekly": 0.7,
         "r": 0.5, "pace": 1.1, "status": "ok"}]}
    snap = usage.Snapshot.of(doc)
    gemini, codex = snap.readout("agy-gemini", None), snap.readout("codex", None)
    record("4. a row with only Windows gets Remaining (the lower Window) and Pace at the time of its reading",
           gemini.remaining == 0.8 and gemini.weekly == 0.9 and gemini.five_h == 0.8
           and gemini.week_left == 0.5 and gemini.pace == 1.8
           and gemini.note == COMBINED_NOTE,
           gemini)
    record("4b. a figure the probe wrote is never recomputed",
           codex.remaining == 0.5 and codex.pace == 1.1, codex)


def case_missing_combined_fields_are_derived_independently():
    """B-1: one supplied figure must not hide the other missing figures."""
    import rank
    taken_at = 1700000000
    reset = taken_at + 3.5 * 86400
    no_remaining = row("codex", 0.05, 0.8, reset_weekly=reset, pace=1.0)
    del no_remaining["r"]
    cat = {"routing": {"gate": 0.1, "margin": 0.2}, "meters": {}, "lanes": {
        "codex-low@codex": {"harness": "codex", "meter": "codex", "tier": 1}}}
    from unittest.mock import patch
    with patch.object(usage.time, "time", return_value=taken_at + 86400):
        snap = usage.Snapshot.of({"probed_at": taken_at, "lanes": [
            no_remaining,
            row("missing-pace", 0.8, 0.5, reset_weekly=reset, r=0.4),
            row("missing-cycle", 0.8, 0.5, reset_weekly=reset, pace=1.2),
            row("supplied", 0.8, 0.5, reset_weekly=reset,
                r=0.4, pace=1.2, cycle_left=0.25)]})
    codex = snap.readout("codex", cat)
    ranked = rank.rank_range(cat, snap, {"codex"})
    record("B-1a. supplied Pace still derives Remaining and the Gate vetoes the Lane",
           codex.remaining == 0.05 and codex.pace == 1.0 and codex.gated
           and ranked[0]["cause"] == "gate" and not ranked[0]["pick"],
           (codex, ranked))
    missing_pace, missing_cycle = (snap.readout(m, None)
                                   for m in ("missing-pace", "missing-cycle"))
    record("B-1b. supplied Remaining still derives Pace and week_left at taken_at",
           missing_pace.remaining == 0.4 and missing_pace.pace == 1.0
           and missing_pace.week_left == 0.5, missing_pace)
    record("B-1c. supplied Remaining and Pace still derive a missing week_left",
           missing_cycle.remaining == 0.5 and missing_cycle.pace == 1.2
           and missing_cycle.week_left == 0.5, missing_cycle)
    supplied = snap.readout("supplied", None)
    record("B-1d. deriving fields preserves every supplied figure",
           supplied.remaining == 0.4 and supplied.pace == 1.2
           and supplied.week_left == 0.25, supplied)


def case_cycle_left_is_an_optional_finite_fraction():
    """B-2: invalid divisors reject every Meter before rank can spend one."""
    import rank
    cat = {"routing": {"gate": 0.1, "margin": 0.2}, "meters": {}, "lanes": {
        "codex-low@codex": {"harness": "codex", "meter": "codex", "tier": 1}}}
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "usage.json")
        for bad in ("bad", True, False, -0.1, 1.1, float("nan"), float("inf"), -float("inf")):
            rows = [row("codex", None, 0.5, pace=1.0, cycle_left=bad),
                    row("grok", None, 0.9, pace=1.0)]
            write_doc(cache, rows, taken_at=1700000000)
            snapshots = [usage.read(None, usage.CACHED, path=cache),
                         usage.Snapshot.of({"probed_at": 1700000000, "lanes": rows}),
                         usage.Snapshot.of({r["meter"]: r for r in rows})]
            record(f"B-2. cycle_left={bad!r} makes the whole document malformed",
                   all(s.status == "malformed" and s.detail and s.names() == ()
                       and s.readout("grok", None).remaining is None for s in snapshots),
                   snapshots)
            try:
                rank.tier_leaders(cat, snapshots[0], {"codex"})
                safe = True
            except TypeError:
                safe = False
            record(f"B-2. cycle_left={bad!r} cannot crash a Tier preview", safe)
    for good in (None, 0, 0.5, 1):
        snap = usage.Snapshot.of({"probed_at": 1700000000, "lanes": [
            row("codex", None, 0.5, pace=1.0, cycle_left=good)]})
        record(f"B-2. optional cycle_left={good!r} remains valid",
               snap.status == "ok" and snap.readout("codex", None).week_left == good, snap)


def case_readout_invariants():
    def cat(gate=0.1, meters_on=True, **meter_defs):
        routing = {"gate": gate, "margin": 0.2}
        if not meters_on:
            routing["meters"] = False
        return {"routing": routing, "meters": meter_defs}

    snap = usage.Snapshot.of({"probed_at": time.time(), "lanes": [
        row("low", 0.3, 0.6, pace=1.0),
        row("edge", 0.1, 0.4, pace=1.0),
        row("under", 0.09, 0.4, pace=1.0),
        row("claude-fable", 0.7, 0.46, pace=0.9, remaining_weekly_model=0.59),
        row("claude-flagged", 0.7, 0.5, pace=0.9),
        row("plain", 0.7, 0.5, pace=0.9)]})
    record("5a. Remaining is the lower Window",
           snap.readout("low", None).remaining == 0.3, snap.readout("low", None))
    record("5b. Remaining equal to the Gate passes; under it is gated",
           not snap.readout("edge", cat()).gated and snap.readout("under", cat()).gated)
    unknown = snap.readout("absent", cat(absent={"harness": "codex", "price_month": 200}))
    record("5c. an unknown Meter is never gated, and still has its catalog plan price",
           unknown.remaining is None and unknown.pace is None and not unknown.gated
           and unknown.held_until is None and unknown.harness == "codex"
           and abs(unknown.week_dollars - 45.9959) < 1e-3,
           unknown)
    record("5d. with metering off or no catalog nothing is gated",
           not snap.readout("under", cat(meters_on=False)).gated
           and not snap.readout("under", None).gated)
    marked = usage.Snapshot.of({"probed_at": time.time(), "lanes": [
        row("codex", 0.5, 0.5, pace=1.0, status="unavailable")]})
    record("5d2. the row's own status never vetoes: only Remaining against the catalog's Gate",
           not marked.readout("codex", cat()).gated and marked.readout("codex", cat(gate=0.6)).gated)
    fable = snap.readout("claude-fable", None)
    flagged = snap.readout("claude-flagged", cat(**{"claude-flagged": {"model_meter": True}}))
    plain = snap.readout("plain", cat(plain={"price_month": 20}))
    record("5e. a Model meter's Weekly figure is the probe's lower week; shares_five_h from the row or the flag",
           fable.weekly == 0.46 and fable.shares_five_h
           and flagged.shares_five_h and not plain.shares_five_h,
           (fable, flagged, plain))
    record("5f. week_dollars is the catalog Meter's monthly price over 30.4375 days times 7, else None",
           abs(plain.week_dollars - 4.5996) < 1e-3 and fable.week_dollars is None,
           (plain.week_dollars, fable.week_dollars))
    nothing = snap.readout(None, cat())
    record("5g. readout of no Meter is unknown",
           nothing.meter is None and nothing.remaining is None and not nothing.gated
           and nothing.week_dollars is None)
    import dataclasses
    record("5h. a Readout carries every field the Meters module names",
           [f.name for f in dataclasses.fields(usage.Readout)] == [
               "meter", "harness", "group", "remaining", "pace", "weekly", "five_h",
               "shares_five_h", "reset_weekly", "reset_5h", "week_left", "gated",
               "week_dollars", "held_until", "note"])
    try:
        hash(snap)
        hashed = True
    except TypeError:
        hashed = False
    record("5i. hashing a Snapshot cannot raise", hashed)


def case_signature_follows_what_ranks():
    with tempfile.TemporaryDirectory() as td:
        now = time.time()
        cache = write_doc(os.path.join(td, "usage.json"), [row("grok", None, 0.9, pace=0.8)], taken_at=now)
        first = usage.read(None, usage.CACHED, path=cache).signature
        again = usage.read(None, usage.CACHED, path=cache).signature
        usage.hold("grok", "limit", path=cache)
        held = usage.read(None, usage.CACHED, path=cache).signature
        usage.release("grok", path=cache)
        released = usage.read(None, usage.CACHED, path=cache).signature
        write_doc(cache, [row("grok", None, 0.5, pace=0.8)], taken_at=now)
        changed = usage.read(None, usage.CACHED, path=cache).signature
        record("6. the signature is equal for two reads alike and changes with a hold, its release or a new reading",
               first == again and held != first and released == first and changed != first,
               (first, held, released, changed))


def case_signature_follows_derived_figures_at_the_reading_time():
    """B-5: legacy Pace changes rank and signature; envelopes stay pinned."""
    import rank
    from unittest.mock import patch
    taken_at = 1700000000
    rows = {"grok": row("grok", None, 0.5, reset_weekly=taken_at + 7 * 86400, r=None),
            "codex": row("codex", None, 0.5, pace=0.75)}
    cat = {"routing": {"gate": 0.1, "margin": 0.2}, "meters": {}, "lanes": {
        "grok-high@grok": {"harness": "grok", "meter": "grok", "tier": 1},
        "codex-low@codex": {"harness": "codex", "meter": "codex", "tier": 1}}}
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "usage.json")
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        with patch.object(usage.time, "time", return_value=taken_at):
            first = usage.read(None, usage.CACHED, path=cache)
        with patch.object(usage.time, "time", return_value=taken_at + 3.5 * 86400):
            later = usage.read(None, usage.CACHED, path=cache)
        picks = [rank.rank_range(cat, s, {"grok", "codex"})[0]["lane"] for s in (first, later)]
        record("B-5a. legacy derived Pace changes the signature when the Pick changes",
               first.readout("grok", None).pace == 0.5 and later.readout("grok", None).pace == 1.0
               and picks == ["codex-low@codex", "grok-high@grok"]
               and first.signature != later.signature,
               (picks, first.signature, later.signature))
        write_doc(cache, list(rows.values()), taken_at=taken_at)
        with patch.object(usage.time, "time", return_value=taken_at):
            pinned = usage.read(None, usage.CACHED, path=cache)
        with patch.object(usage.time, "time", return_value=taken_at + 3.5 * 86400):
            pinned_later = usage.read(None, usage.CACHED, path=cache)
        record("B-5b. enveloped derived figures and signature stay fixed at taken_at",
               pinned.signature == pinned_later.signature
               and pinned.readout("grok", None) == pinned_later.readout("grok", None),
               (pinned.signature, pinned_later.signature))


def case_cache_path():
    saved = {k: os.environ.pop(k, None) for k in ("DELEGATE_CACHE", "CONSULT_CACHE")}
    try:
        default = usage.cache_path()
        os.environ["CONSULT_CACHE"] = "/c/consult.json"
        consult = usage.cache_path()
        os.environ["DELEGATE_CACHE"] = "/c/delegate.json"
        delegate = usage.cache_path()
        explicit = usage.cache_path("/c/explicit.json")
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    record("7. cache_path: the explicit path, else DELEGATE_CACHE, else CONSULT_CACHE, else the default",
           default == os.path.expanduser("~/.cache/delegate/usage.json") and consult == "/c/consult.json"
           and delegate == "/c/delegate.json" and explicit == "/c/explicit.json",
           (default, consult, delegate, explicit))


def case_spend_takes_quota_points_off_the_weekly_figure():
    """readout(spend=x): what one Meter would read with x more of its week
    spent, and every other figure following from it (ticket 17)."""
    def close(a, b):
        return a is not None and b is not None and abs(a - b) < 1e-9

    cat = {"routing": {"gate": 0.35, "margin": 0.2}, "meters": {}}
    snap = usage.Snapshot.of({"probed_at": time.time(), "lanes": [
        row("codex", 0.8, 0.5, pace=1.0, cycle_left=0.5),
        row("tight", 0.2, 0.6, pace=1.2, cycle_left=0.5)]})
    before, spent = snap.readout("codex", cat), snap.readout("codex", cat, spend=0.2)
    record("8a. spend falls the Weekly figure and Remaining by x, Pace follows and the Gate is asked again",
           not before.gated and close(spent.weekly, 0.3) and close(spent.remaining, 0.3)
           and close(spent.pace, 0.6) and spent.gated
           and spent.five_h == 0.8 and spent.week_left == 0.5,
           spent)
    tight = snap.readout("tight", cat, spend=0.1)
    record("8b. spend touches the weekly Window only: a lower 5h Window still binds Remaining",
           close(tight.weekly, 0.5) and close(tight.remaining, 0.2) and close(tight.pace, 1.0),
           tight)
    over = snap.readout("codex", cat, spend=0.7)
    record("8c. spending past the Weekly figure leaves nothing, never less",
           over.weekly == 0.0 and over.remaining == 0.0 and over.pace == 0.0 and over.gated, over)
    record("8d. spend=0 returns the reading itself, and a Meter with no reading stays unknown",
           snap.readout("codex", cat, spend=0) == before
           and snap.readout("absent", cat, spend=0.3).remaining is None)
    raised = []
    for bad in (-0.1, 1.5, float("nan"), True):
        try:
            snap.readout("codex", cat, spend=bad)
        except ValueError:
            raised.append(bad)
    record("8e. a spend outside 0..1 raises ValueError", len(raised) == 4, raised)
    with tempfile.TemporaryDirectory() as td:
        cache = write_doc(os.path.join(td, "usage.json"),
                          [row("codex", 0.8, 0.5, pace=1.0, cycle_left=0.5)])
        usage.hold("codex", "limit", path=cache)
        held = usage.read(None, usage.CACHED, path=cache).readout("codex", cat, spend=0.2)
    record("8f. a held Meter stays at 0 whatever is spent",
           held.weekly == 0.0 and held.remaining == 0.0 and held.pace == 0.0
           and held.held_until is not None and held.gated,
           held)


class counted_probes:
    """Count the probes `usage.read` starts, through the internal seam that
    runs the probe child process, with no harness CLI on PATH: a probe that
    does run writes a document of `absent` rows and reaches no vendor. The
    Ledger and DELEGATE_CACHE point at files of the case's own, so a write to
    either shows."""

    def __init__(self, td):
        self.td = td
        self.paths = []

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("PATH", "DELEGATE_LEDGER", "DELEGATE_CACHE")}
        os.environ["PATH"] = os.path.join(self.td, "no-bin")
        os.environ["DELEGATE_LEDGER"] = self.ledger = os.path.join(self.td, "ledger.jsonl")
        os.environ["DELEGATE_CACHE"] = self.default = os.path.join(self.td, "default", "usage.json")
        self.real = usage._probe

        def counting(path):
            self.paths.append(path)
            return self.real(path)
        usage._probe = counting
        return self

    def __exit__(self, *exc):
        usage._probe = self.real
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    @property
    def count(self):
        return len(self.paths)


def case_freshness_decides_when_a_read_probes():
    """CACHED never probes; FRESH probes only past its age or with no reading;
    FORCED probes now; with metering off neither probes, and routing None (a
    person's own `delegate status --refresh`) has no switch."""
    on, off = {"meters": True, "gate": 0.1}, {"meters": False, "gate": 0.1}
    with tempfile.TemporaryDirectory() as td:
        now = time.time()
        cache = os.path.join(td, "usage.json")
        with counted_probes(td) as probes:
            usage.read(on, usage.CACHED, path=cache)
            record("9a. CACHED never probes, even with no reading",
                   probes.count == 0 and not os.path.exists(cache), probes.paths)

            write_doc(cache, [row("codex", 0.5, 0.5, pace=1.0)], taken_at=now - 5 * 60)
            young = usage.read(on, usage.FRESH, path=cache)
            record("9b. FRESH within its age (10 min by default) probes nothing and reads the reading",
                   probes.count == 0 and young.status == "ok" and young.taken_at == now - 5 * 60
                   and young.readout("codex", None).remaining == 0.5,
                   (probes.paths, young))

            write_doc(cache, [row("codex", 0.5, 0.5, pace=1.0)], taken_at=now - 30 * 60)
            kept = usage.read(on, usage.FRESH, path=cache, max_age_min=60)
            record("9c. max_age_min sets FRESH's age: a reading 30 min old is fresh within 60",
                   probes.count == 0 and kept.taken_at == now - 30 * 60, (probes.paths, kept))

            old = usage.read(on, usage.FRESH, path=cache)
            record("9d. FRESH past its age probes once, and reads what the probe wrote",
                   probes.paths == [cache] and old.status == "ok" and old.taken_at >= now
                   and "codex" in old.names() and old.readout("codex", None).remaining is None,
                   (probes.paths, old))

            os.remove(cache)
            usage.read(on, usage.FRESH, path=cache)
            record("9e. FRESH with no reading probes once",
                   probes.count == 2 and os.path.exists(cache), probes.paths)

            usage.read(on, usage.FORCED, path=cache)
            record("9f. FORCED probes now, however fresh the reading", probes.count == 3, probes.paths)

            os.remove(cache)
            off_fresh = usage.read(off, usage.FRESH, path=cache)
            off_forced = usage.read(off, usage.FORCED, path=cache)
            record("9g. with routing.meters off FRESH and FORCED probe nothing and read as CACHED",
                   probes.count == 3 and off_fresh.status == "missing" and off_forced.status == "missing"
                   and not os.path.exists(cache),
                   (probes.paths, off_fresh, off_forced))

            usage.read(None, usage.FORCED, path=cache)
            record("9h. FORCED with routing None probes: no metering switch applies",
                   probes.count == 4 and os.path.exists(cache), probes.paths)

            elsewhere = os.path.join(td, "elsewhere", "usage.json")
            forced = usage.read(None, usage.FORCED, path=elsewhere)
            record("9i. a FORCED read with path=P writes P, not DELEGATE_CACHE",
                   probes.paths[-1] == elsewhere and forced.path == elsewhere and forced.status == "ok"
                   and os.path.exists(elsewhere) and not os.path.exists(probes.default),
                   (probes.paths, forced))
            record("10a. a probe writes nothing to the Ledger",
                   probes.count == 5 and not os.path.exists(probes.ledger), probes.ledger)


def case_usage_does_not_import_events():
    """The Ledger records Runs only (decision C.2), so the Meters module has
    no way to write one."""
    child = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import usage; print('events' in sys.modules)",
         os.path.abspath(os.path.join(HERE, "..", "scripts"))],
        capture_output=True, text=True)
    record("10b. usage.py does not import events",
           child.returncode == 0 and child.stdout.strip() == "False", child.stdout + child.stderr)


def case_a_probe_past_its_bound_falls_back_only_to_a_fresh_enough_reading():
    """The one 180 s bound (decision B.5) around the probe child: a late or
    failed probe gives the last reading when it is fresh enough, else stale."""
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as td:
        now = time.time()
        cache = write_doc(os.path.join(td, "usage.json"),
                          [row("codex", 0.5, 0.5, pace=1.0)], taken_at=now - 2 * 60)
        late = subprocess.TimeoutExpired("usage.py", 180)
        with patch.object(usage.subprocess, "run", side_effect=late) as runner:
            forced = usage.read(None, usage.FORCED, path=cache)
            bound = runner.call_args.kwargs.get("timeout")
            command = runner.call_args.args[0] if runner.call_args.args else runner.call_args.kwargs.get("args")
        record("11a. a probe past its bound gives the last reading when it is fresh enough",
               forced.status == "ok" and forced.taken_at == now - 2 * 60
               and forced.readout("codex", None).remaining == 0.5,
               forced)
        record("11b. the probe runs in the usage.py child with --cache PATH, under one 180 s bound",
               bound == 180 and list(command[-2:]) == ["--cache", cache] and "--refresh" in command,
               (bound, command))

        write_doc(cache, [row("codex", 0.5, 0.5, pace=1.0)], taken_at=now - 30 * 60)
        with patch.object(usage.subprocess, "run", side_effect=late):
            stale = usage.read({"meters": True}, usage.FRESH, path=cache)
        record("11c. a probe past its bound over a reading too old is stale, every Meter unknown",
               stale.status == "stale" and stale.detail and stale.names() == ()
               and stale.readout("codex", None).remaining is None and stale.path == cache,
               stale)

        class Failed:
            returncode = 1
            stdout = stderr = ""
        with patch.object(usage.subprocess, "run", return_value=Failed()):
            failed = usage.read(None, usage.FORCED, path=cache)
        record("11d. a failed probe over a reading too old is stale too",
               failed.status == "stale" and failed.names() == (), failed)


USAGE_PY = os.path.abspath(os.path.join(HERE, "..", "scripts", "usage.py"))


def case_pretty_prints_one_line_per_meter():
    """`usage.py --pretty` (decision B.4) draws each Meter from its Readout:
    Pace, the Weekly figure, the binding Window and the note, with any hold."""
    with tempfile.TemporaryDirectory() as td:
        now = time.time()
        cache = write_doc(os.path.join(td, "usage.json"), [
            row("codex", 0.5, 0.6, reset_weekly=now + 3 * 86400, pace=1.2, note="plan=pro"),
            row("claude-fable", 0.7, 0.46, pace=0.9, remaining_weekly_model=0.59),
            row("grok", None, 0.9, reset_weekly=now + 86400, pace=0.8)], taken_at=now - 60)
        usage.hold("grok", "limit", path=cache, now=now)
        child = subprocess.run([sys.executable, USAGE_PY, "--pretty", "--max-age-min", "60", "--cache", cache],
                               capture_output=True, text=True,
                               env=dict(os.environ, PATH=os.path.join(td, "no-bin")))
    lines = child.stdout.splitlines()
    by_meter = {line.split()[0]: line for line in lines[1:] if line.strip()}
    codex, fable, grok = (by_meter.get(m, "") for m in ("codex", "claude-fable", "grok"))
    record("12. usage.py --pretty prints one line per Meter",
           child.returncode == 0 and lines[:1] and lines[0].startswith("# usage")
           and list(by_meter) == ["codex", "claude-fable", "grok"] and len(lines) == 4
           and "pace=1.20" in codex and "r= 50%" in codex and "wk= 60%" in codex
           and "binding=5h" in codex and "plan=pro" in codex
           and "wk= 46%" in fable and "binding=weekly" in fable
           and "r=  0%" in grok and "usage limit reached" in grok,
           child.stdout + child.stderr)


def case_a_probe_builds_its_rows_from_the_windows():
    """usage.py builds each row from the Windows an adapter hands over: it
    holds each fraction to 0..1, so an overspent Window reads as nothing left
    rather than failing the whole document, and it gives a Model meter the
    lower of its own week and the harness's week as its Weekly figure."""
    import contextlib
    import io
    from unittest.mock import patch
    import harnesses
    claude = harnesses.get("claude")
    windows = [claude.windows("general", five_h=-0.04, weekly=0.7),
               claude.windows("fable", five_h=-0.04, weekly=0.7, weekly_model=1.2),
               claude.windows("sonnet", five_h=0.6, weekly=0.7, weekly_model=0.04)]
    with tempfile.TemporaryDirectory() as td:
        cache = os.path.join(td, "usage.json")
        saved = os.environ.get("PATH")
        os.environ["PATH"] = os.path.join(td, "no-bin")
        printed = io.StringIO()
        try:
            with patch.object(claude, "installed", return_value=True), \
                 patch.object(claude, "read_meters", return_value=windows), \
                 contextlib.redirect_stdout(printed):
                usage.main(["--refresh", "--cache", cache])
        finally:
            os.environ["PATH"] = saved
        rows = {r["meter"]: r for r in json.loads(printed.getvalue())["lanes"]}
        snap = usage.read(None, usage.CACHED, path=cache)
    general, fable, sonnet = (snap.readout(m, None) for m in ("claude-general", "claude-fable", "claude-sonnet"))
    record("13a. an overspent Window reads as nothing left",
           snap.status == "ok" and general.five_h == 0.0 and general.remaining == 0.0
           and fable.remaining == 0.0 and fable.weekly == 0.7
           and rows["claude-fable"]["remaining_weekly_model"] == 1.0
           and rows["claude-fable"]["r"] == 0.0 and rows["claude-general"]["harness"] == "claude"
           and snap.readout("codex", None).note == "absent",
           (snap, rows))
    record("13b. a Model meter's Weekly figure is the lower of its own week and the harness's week",
           sonnet.weekly == 0.04 and sonnet.remaining == 0.04 and sonnet.shares_five_h
           and rows["claude-sonnet"]["remaining_weekly_model"] == 0.04
           and not general.shares_five_h,
           (sonnet, rows.get("claude-sonnet")))


def case_the_interface_is_only_its_public_names():
    """usage.py's public names are its interface (ticket B4), and MAX_PACE is
    the highest Pace a Meter can read: the whole week over the cycle floor."""
    import ast
    with open(USAGE_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    defined = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            defined.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
    public = sorted(n for n in defined if not n.startswith("_"))
    record("14a. usage.py's public names are exactly its interface",
           public == sorted(["CACHED", "FRESH", "FORCED", "MAX_PACE", "read", "hold", "release",
                             "cache_path", "Snapshot", "Readout", "main"]),
           public)
    top = usage.Snapshot.of({"probed_at": time.time(), "lanes": [
        row("codex", 1.0, 1.0, reset_weekly=time.time() + 60, r=None)]}).readout("codex", None)
    record("14b. MAX_PACE is 50 with today's cycle floor, and a full week read at its reset reaches it",
           usage.MAX_PACE == 50 and top.pace == usage.MAX_PACE, (usage.MAX_PACE, top.pace))


def main():
    case_pretty_prints_one_line_per_meter()
    case_a_probe_builds_its_rows_from_the_windows()
    case_the_interface_is_only_its_public_names()
    case_freshness_decides_when_a_read_probes()
    case_usage_does_not_import_events()
    case_a_probe_past_its_bound_falls_back_only_to_a_fresh_enough_reading()
    case_a_hold_lives_beside_the_document_it_overlays()
    case_a_usage_limit_hold_ends_at_the_reset_a_new_reset_a_finished_run_or_a_day()
    case_validity_legacy_rows_and_the_bare_map()
    case_figures_derived_from_a_row_that_carries_only_windows()
    case_missing_combined_fields_are_derived_independently()
    case_cycle_left_is_an_optional_finite_fraction()
    case_readout_invariants()
    case_signature_follows_what_ranks()
    case_signature_follows_derived_figures_at_the_reading_time()
    case_cache_path()
    case_spend_takes_quota_points_off_the_weekly_figure()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
