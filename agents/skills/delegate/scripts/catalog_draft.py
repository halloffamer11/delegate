#!/usr/bin/env python3
"""catalog_draft.py — the Draft: the catalog as setup holds it before save
(deepening F).

A `CatalogDraft` takes the `lanes` and `routing` documents setup starts from
and holds every decision made since: which Lanes are carried, each Lane's Tier,
its place inside that Tier, and the routing keys. `documents()` is what a save
writes, keyed by `catalog_commit.DOCUMENTS` names, so
`catalog_commit.commit(read, draft.documents())` takes it whole; `changes()`
is the field diff between the documents as given and that.

Rules it settles, one place each:

- A Tier as given is numbered by `catalog.carried_in_tier`: Order, then a Lane
  without one after every Lane with one, ties by lane name.
- A Lane that joins a Tier it did not start in goes to its end.
- Undo is exact: a Lane returning to its start Tier goes right after the last
  Lane now in that Tier that came before it when the draft settled; for a Lane
  that was off then, the reference is the documents as given.
- Lines and proposals are decisions, not tie-breaks: their order is the order
  written, even by a focused save where it matches the sequence as given.
- Save scope: `whole=True` (the full wizard) numbers every carried Lane 1 to n
  in its Tier; `whole=False` (a focused screen, `--plain`) writes only the
  fields a decision changed, and numbers a Tier only when its sequence changed
  or lines or a proposal set it.

Pure computation: it never mutates the documents it is given, validates
nothing (the commit does), and costs O(Lanes) per operation.
"""
from __future__ import annotations

import copy
import os
import sys
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Tuple, Union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402

TIERS = (1, 2, 3, 4)


class LaneDecision(NamedTuple):
    carried: bool
    tier: Optional[int]   # None only for a carried Lane the tier pages have not placed yet
    place: Optional[int]  # its place in its Tier, from 1; None when off or not placed
    start_tier: int       # its Tier when the draft last settled


class Change(NamedTuple):
    # ("lanes", lane, "tier"|"order"|"enabled"), ("classes", cls, "floor"|"ceiling"),
    # ("margin",), ("gate",), ("meters",)
    path: Tuple[str, ...]
    old: object            # None when the key is absent
    new: object            # None when the key is absent


class CatalogDraft:
    """The catalog the pages started from, plus the carry, Tier, Order and
    routing decisions made since."""

    def __init__(self, lanes_doc: dict, routing_doc: dict, *, whole: bool) -> None:
        self._lanes_given = copy.deepcopy(lanes_doc)
        self._routing_given = copy.deepcopy(routing_doc)
        self._whole = bool(whole)
        records = self._lanes_given["lanes"]
        self._carried = {name: _is_carried(lane) for name, lane in records.items()}
        self._tier = {name: lane.get("tier") for name, lane in records.items()}
        self._seq = {tier: catalog.carried_in_tier(records, tier) for tier in TIERS}
        self._routing = copy.deepcopy(self._routing_given)
        # Tiers whose sequence lines or a proposal set: a decision, which a
        # focused save writes even where it matches the sequence as given
        self._decided = set()
        self._start_tier = dict(self._tier)
        self.settle()

    # decisions

    def carry(self, lane: str, on: bool) -> None:
        """Off: the Lane leaves its Tier's sequence and goes back to its start
        Tier. On: it returns to its start Tier at its starting place. Either
        on a Lane already in that state does nothing."""
        on = bool(on)
        if self._carried[lane] == on:
            return
        start = self._start_tier[lane]
        if on:
            self._carried[lane] = True
            self._insert(lane, start, self._starting_place(lane, start))
        else:
            self._unplace(lane)
            self._carried[lane] = False
            self._tier[lane] = start

    def place(self, lane: str, tier: Optional[int], at: Union[None, int, str] = None) -> None:
        """Put a carried Lane in `tier`. With `at=None` a Lane already there
        stays, a Lane returning to its start Tier takes back its starting
        place, and any other goes to the end; an int `at` is its place,
        clamped to the Tier's places; "end" puts it last. `tier=None` takes a
        carried Lane out of its Tier unplaced. For an off Lane, only its Tier
        is set."""
        carried = self._carried[lane]
        if tier is not None:
            _tier(tier)
        if not (at is None or at == "end" or type(at) is int):
            raise ValueError(f"at must be None, a place from 1 or 'end', got {at!r}")
        if not carried:
            if tier is None:
                raise ValueError(f"lane '{lane}' is off; an off Lane takes a Tier, never none")
            self._tier[lane] = tier
            return
        if tier is None:
            self._unplace(lane)
            return
        if at is None:
            if self._tier[lane] == tier:
                return
            self._unplace(lane)
            if tier == self._start_tier[lane]:
                self._insert(lane, tier, self._starting_place(lane, tier))
            else:
                self._insert(lane, tier, len(self._seq[tier]))
            return
        self._unplace(lane)
        last = len(self._seq[tier])
        index = last if at == "end" else min(max(at, 1), last + 1) - 1
        self._insert(lane, tier, index)

    def apply(self, pairs: Union[Mapping[str, object], Iterable[Tuple[str, object]]],
              unnamed: str) -> List[str]:
        """Take `(lane, 1-4 | "off")` pairs in order (a mapping's items count
        as pairs). Each named Lane takes its value, and the Lanes named for one
        Tier come first in it, in the pairs' order. `unnamed="off"` (tier
        lines) switches off every carried Lane the pairs do not name and
        returns those Lanes; `unnamed="keep"` (the tier proposal) leaves every
        other Lane in its Tier, after the named ones, in its current order.
        Pairs that name no Lane change nothing and return []."""
        if unnamed not in ("off", "keep"):
            raise ValueError(f"unnamed must be 'off' or 'keep', got {unnamed!r}")
        items = pairs.items() if isinstance(pairs, Mapping) else pairs
        decided = {}
        for lane, value in items:
            if lane not in self._carried:
                raise KeyError(lane)
            if value != "off":
                _tier(value)
            # a Lane named twice keeps its first place and its last value
            decided[lane] = value
        if not decided:
            return []
        dropped = []
        if unnamed == "off":
            dropped = [name for name, on in self._carried.items() if on and name not in decided]
        for name in dropped + [lane for lane, value in decided.items() if value == "off"]:
            self.carry(name, False)
        named = {tier: [lane for lane, value in decided.items() if value == tier] for tier in TIERS}
        for tier in TIERS:
            for lane in named[tier]:
                self._carried[lane] = True
                self._unplace(lane)
        for tier in TIERS:
            if named[tier]:
                self._seq[tier] = named[tier] + self._seq[tier]
                for lane in named[tier]:
                    self._tier[lane] = tier
                self._decided.add(tier)
        return dropped

    def set_routing(self, key: str, value: object, cls: Optional[str] = None) -> None:
        """Set `floor` or `ceiling` of Class `cls`, or `margin`, `gate` or
        `meters`. `meters` on removes the key when the routing as given had
        none. The caller clamps; the commit validates."""
        if key in ("floor", "ceiling"):
            if cls is None:
                raise ValueError(f"routing key '{key}' needs a Class")
            self._routing["classes"][cls][key] = value
            return
        if key not in ("margin", "gate", "meters"):
            raise ValueError(f"routing key must be floor, ceiling, margin, gate or meters, got {key!r}")
        if cls is not None:
            raise ValueError(f"routing key '{key}' takes no Class")
        if key == "meters" and value and "meters" not in self._routing_given:
            self._routing.pop("meters", None)
        else:
            self._routing[key] = bool(value) if key == "meters" else value

    def settle(self) -> None:
        """Make the decisions as they stand the draft's start: each Lane's
        start Tier and starting place, and what `is_settled` compares with."""
        for name, tier in self._tier.items():
            if tier is not None:
                self._start_tier[name] = tier
        self._start_carried = dict(self._carried)
        self._start_seq = copy.deepcopy(self._seq)
        self._settled = self._decisions()

    # answers

    def is_settled(self) -> bool:
        """False after any carry, Tier, Order or routing change since the
        draft last settled that has not been undone."""
        return self._decisions() == self._settled

    def lane(self, name: str) -> LaneDecision:
        carried, tier = self._carried[name], self._tier[name]
        place = None
        if carried and tier is not None:
            place = self._seq[tier].index(name) + 1
        return LaneDecision(carried, tier, place, self._start_tier[name])

    def tier_lanes(self, tier: int) -> List[str]:
        return list(self._seq[_tier(tier)])

    def documents(self) -> Dict[str, dict]:
        """{"lanes": ..., "routing": ...}: what a save writes."""
        lanes = copy.deepcopy(self._lanes_given)
        records = lanes["lanes"]
        given = self._lanes_given["lanes"]
        renumber = {tier for tier in TIERS
                    if self._whole or tier in self._decided
                    or self._seq[tier] != catalog.carried_in_tier(given, tier)}
        for name, record in records.items():
            carried, tier = self._carried[name], self._tier[name]
            if not carried:
                record["tier"] = tier
                if self._whole or _is_carried(given[name]):
                    record["enabled"] = False
                    record.pop("order", None)
                continue
            if self._whole or not _is_carried(given[name]):
                record.pop("enabled", None)
            if tier is None:
                # not placed yet: its Tier as given, and no place
                record.pop("order", None)
                continue
            record["tier"] = tier
            if tier in renumber:
                record["order"] = self._seq[tier].index(name) + 1
        return {"lanes": lanes, "routing": copy.deepcopy(self._routing)}

    def changes(self) -> List[Change]:
        """The field diff between the documents as given and `documents()`:
        each Lane's tier, order and enabled in catalog order, then each
        Class's floor and ceiling, then margin, gate and meters."""
        docs = self.documents()
        out = []

        def compare(path, old, new):
            if old != new:
                out.append(Change(path, old, new))

        given = self._lanes_given["lanes"]
        for name, record in docs["lanes"]["lanes"].items():
            for key in ("tier", "order", "enabled"):
                compare(("lanes", name, key), given[name].get(key), record.get(key))
        given_classes = self._routing_given.get("classes") or {}
        for cls, rng in (docs["routing"].get("classes") or {}).items():
            for key in ("floor", "ceiling"):
                compare(("classes", cls, key), (given_classes.get(cls) or {}).get(key), rng.get(key))
        for key in ("margin", "gate", "meters"):
            compare((key,), self._routing_given.get(key), docs["routing"].get(key))
        return out

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CatalogDraft):
            return NotImplemented
        return self._state() == other._state()

    # a draft compares by value and changes in place: never a dict key or set member
    __hash__ = None  # type: ignore[assignment]

    def _state(self):
        return (self._whole, self._lanes_given, self._routing_given, self._carried, self._tier,
                self._seq, self._decided, self._routing, self._start_tier, self._start_carried,
                self._start_seq, self._settled)

    def _decisions(self):
        orders = {name: record.get("order")
                  for name, record in self.documents()["lanes"]["lanes"].items()}
        return copy.deepcopy((self._carried, self._tier, self._seq, self._routing, orders))

    # the sequences

    def _unplace(self, lane):
        tier = self._tier[lane]
        if tier is not None and lane in self._seq[tier]:
            self._seq[tier].remove(lane)
        self._tier[lane] = None

    def _insert(self, lane, tier, index):
        self._seq[tier].insert(index, lane)
        self._tier[lane] = tier

    def _starting_place(self, lane, tier):
        """Where `lane` goes back into its start Tier `tier`: right after the
        last Lane now there that came before it when the draft settled. For a
        Lane off then, the reference is the documents as given."""
        if self._start_carried[lane]:
            reference = self._start_seq[tier]
        else:
            records = dict(self._lanes_given["lanes"])
            record = dict(records[lane])
            record.pop("enabled", None)
            if record.get("tier") != tier:
                record.pop("order", None)
                record["tier"] = tier
            records[lane] = record
            reference = catalog.carried_in_tier(records, tier)
        before = set(reference[:reference.index(lane)]) if lane in reference else set()
        index = 0
        for i, name in enumerate(self._seq[tier]):
            if name in before:
                index = i + 1
        return index


def _is_carried(record):
    return record.get("enabled", True) is not False


def _tier(tier):
    """A Tier from 1 to 4, or ValueError."""
    if type(tier) is not int or tier not in TIERS:
        raise ValueError(f"tier must be 1 to 4, got {tier!r}")
    return tier
