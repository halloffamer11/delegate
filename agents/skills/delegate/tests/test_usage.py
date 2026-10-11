#!/usr/bin/env python3
"""test_usage.py — the Meters module at its interface: usage.read, the Meter
snapshot and its Readouts, and the usage-limit hold (usage.hold, usage.release).

No probe and no network: every case reads a usage document it wrote into a
temporary directory."""
import json
import os
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
            # The reader this module replaces (gone with ticket 18) looks for
            # the hold beside $DELEGATE_CACHE, so it shows A's codex unheld.
            old = {r["meter"]: r for r in usage.load_cached(paths["A"])["lanes"]}
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
               and old["codex"]["r"] == 0.5
               and released.remaining == 0.5 and released.held_until is None,
               f"until={until - now} held={held} default={default} old={old} released={released}")


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
         "status": "unknown", "note": SUPERSEDED_NOTE}]}
    gemini = usage.Snapshot.of(doc).readout("agy-gemini", None)
    record("4. a row with only Windows gets Remaining (the lower Window) and Pace at the time of its reading",
           gemini.remaining == 0.8 and gemini.weekly == 0.9 and gemini.five_h == 0.8
           and gemini.week_left == 0.5 and gemini.pace == 1.8
           and gemini.note == COMBINED_NOTE,
           gemini)


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


def main():
    case_a_hold_lives_beside_the_document_it_overlays()
    case_a_usage_limit_hold_ends_at_the_reset_a_new_reset_a_finished_run_or_a_day()
    case_validity_legacy_rows_and_the_bare_map()
    case_figures_derived_from_a_row_that_carries_only_windows()
    case_readout_invariants()
    case_signature_follows_what_ranks()
    case_cache_path()
    case_spend_takes_quota_points_off_the_weekly_figure()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
