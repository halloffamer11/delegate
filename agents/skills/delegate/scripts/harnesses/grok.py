"""Grok: `grok`, xAI's CLI."""
import json
import os
import re
import subprocess
import time

from .base import Harness


class Grok(Harness):
    name = "grok"
    # `grok --help` documents `--reasoning-effort <EFFORT>` with no values, and
    # `grok --reasoning-effort bogus models` exits 0, so the CLI checks nothing
    # locally. Only high is proven: it is the effort grok46-high@grok has run
    # at. A probe that proves more costs a paid run (checked 2026-09-12).
    efforts = ("high",)
    vendor = "grok"
    list_command = ["grok", "models"]
    fixture_file = "grok-models.txt"

    def parse_models(self, raw):
        """Parses plain text prose from `grok models`.

        Extracts slugs from bullet lines under 'Available models:',
        stripping leading bullets ('*', '-') and ' (default)' suffix. Every
        model takes the harness's efforts.
        """
        models = parse_listing(raw)
        for model in models:
            model["efforts"] = list(self.efforts)
        return models

    def read_meters(self):
        """Weekly meter via the Agent Client Protocol: `grok agent stdio`, then the
        `_x.ai/billing` extension method (what the TUI's /usage dialog calls). Zero
        model tokens. Payload fields (serde list in the binary, 1.0.13):
        creditUsagePercent, currentPeriod{type,start,end}, includedUsed, totalUsed,
        monthlyLimit, onDemandCap/Used, prepaidBalance, subscription_tier. Zero-valued
        fields are omitted, so a missing creditUsagePercent means 0% used."""
        import usage
        p = subprocess.Popen(["grok", "agent", "stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True)
        def send(i, method, params):
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}) + "\n"); p.stdin.flush()
        def recv(i, timeout=25):
            t0 = time.time()
            while time.time() - t0 < timeout:
                line = p.stdout.readline()
                if not line: break
                try: m = json.loads(line)
                except ValueError: continue
                if m.get("id") == i: return m
            return None
        try:
            send(1, "initialize", {"protocolVersion": 1, "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
                                    "_meta": {"clientType": "delegate-usage", "clientVersion": "0.1"}})
            if not recv(1): raise RuntimeError("no initialize response")
            send(2, "_x.ai/billing", {})
            m = recv(2)
        finally:
            p.terminate()
        if not m or "result" not in m: raise RuntimeError(f"billing: {(m or {}).get('error')}")
        res = m["result"]; cfg = res.get("config") or {}
        pct = cfg.get("creditUsagePercent")
        if isinstance(pct, dict): pct = pct.get("val")
        pct = float(pct or 0)
        period = cfg.get("currentPeriod") or {}
        end = usage.iso(period.get("end") or cfg.get("billingPeriodEnd") or "")
        ptype = (period.get("type") or "").replace("USAGE_PERIOD_TYPE_", "").lower() or "weekly"
        tier = res.get("subscription_tier")
        # single rolling meter (weekly on SuperGrok); no 5h window exists
        return [usage.lane(self.name, None, None, 1 - pct / 100.0, None, end,
                           note=f"tier={tier}; {ptype} meter only ({pct:g}% used); via _x.ai/billing")]

    def blocked_reason(self, run_dir):
        """A permission gate that cancelled the run, from grok's event stream.

        grok records a gate refusal as a failed tool_call_update whose text
        says the execution was cancelled, then an end event with
        stopReason=cancelled. Both must hold: a cancel with no cancelled tool
        is some other stop, and the run reads as it would without this. The
        relay calls such a run completed, but the worker did not finish, and
        reading it as partial hides the cause (ticket 14).
        """
        tool = gate_cancelled_tool(run_dir)
        if tool is None:
            return None
        return "permission gate cancelled the run" + (f" at {tool}" if tool else "")


def gate_cancelled_tool(run_dir):
    """The tool a permission gate cancelled ("" if the call was never
    announced), or None when the run did not end at the gate."""
    events_path = os.path.join(run_dir, "events.jsonl")
    if not os.path.isfile(events_path):
        return None
    tool_names = {}
    cancelled_tool = None
    stop_reason = None
    with open(events_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            kind = ev.get("type")
            if kind == "tool_call":
                tool_names[ev.get("toolCallId")] = ev.get("toolName") or ev.get("title") or ""
            elif kind == "tool_call_update" and ev.get("status") == "failed":
                if "cancel" in json.dumps(ev.get("content")).lower():
                    cancelled_tool = tool_names.get(ev.get("toolCallId"), "")
            elif kind == "end":
                stop_reason = ev.get("stopReason")
    if stop_reason == "cancelled" and cancelled_tool is not None:
        return cancelled_tool
    return None


def parse_listing(text):
    models = []
    in_available = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Available models:"):
            in_available = True
            continue
        if in_available:
            m = re.match(r"^[\*\-]\s+(.*?)(?:\s+\(default\))?$", line)
            if m:
                slug = m.group(1).strip()
                if slug:
                    models.append({
                        "slug": slug,
                        "display_name": slug,
                    })
    return models


HARNESS = Grok()
