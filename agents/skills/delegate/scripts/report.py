#!/usr/bin/env python3
"""report.py — the two tables the session prints after delegating.

Deterministic rendering, so every report has the same shape:

  report.py limits            Markdown table of every meter: weekly and 5h
                              remaining, the model each meter runs, both resets.
                              Then a plan-consumption table for this cycle.
  report.py log ...           append one adjudicated dispatch to the run ledger.
  report.py log --run DIR     same, plus token cost from DIR/dispatch.json.
  report.py runs [--last N]   Markdown table of recent dispatches + the roll-up.
  report.py cost DIR          token-cost breakdown for one run.

Two ledgers exist and they are not the same file:
  ledger.jsonl  machine events from delegate.py / usage.py, for the monitor TUI.
  runs.jsonl    what the LEAD concluded after verifying a dispatch — the work
                label and whether the definition of done was met. Only the lead
                knows this, so only the lead writes it.
Run ledger path: $DELEGATE_RUNS else ~/.cache/delegate/runs.jsonl.
"""
import argparse, json, os, re, shutil, sys, time
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

try:
    from catalog import load_catalog, CatalogError, meters_enabled
    from harnesses import NAMES as HARNESSES, installed as installed_harnesses
except ImportError:
    from .catalog import load_catalog, CatalogError, HARNESSES, installed_harnesses, meters_enabled

try:
    from rank import rank, tier_leaders, eligible_order, choose
except ImportError:
    from .rank import rank, tier_leaders, eligible_order, choose

try:
    import usage
except ImportError:
    from . import usage

try:
    import orchestrators
except ImportError:
    from . import orchestrators

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.environ.get("DELEGATE_RUNS") or os.path.expanduser("~/.cache/delegate/runs.jsonl")
CACHE = usage.get_cache_path()
# Flag file: while it exists, `statusline` prints no rows.
SWITCH = os.environ.get("DELEGATE_STATUSLINE_SWITCH") or os.path.expanduser("~/.cache/delegate/statusline.off")
VERDICTS = ("clean", "findings", "partial", "failed")
DAYS_PER_MONTH = 30.4375
WEEK_DAYS = 7
INPUT_KEYS = ("input_tokens", "inputTokens", "prompt_tokens", "promptTokens")
OUTPUT_KEYS = ("output_tokens", "outputTokens", "completion_tokens", "completionTokens")
CACHE_READ_KEYS = ("cache_read_input_tokens", "cachedInputTokens", "cached_tokens", "cache_read_tokens")
CACHE_WRITE_KEYS = ("cache_creation_input_tokens", "cacheCreationInputTokens")


# ---------------------------------------------------------------- shared
def md_table(headers, rows):
    """Left-aligned Markdown table, columns padded to the widest cell."""
    w = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
         for i, h in enumerate(headers)]
    out = ["| " + " | ".join(str(h).ljust(w[i]) for i, h in enumerate(headers)) + " |",
           "|" + "|".join("-" * (w[i] + 2) for i in range(len(headers))) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).ljust(w[i]) for i, c in enumerate(r)) + " |")
    return "\n".join(out)


def pct(x):
    return "—" if x is None else f"{int(round(x * 100))}%"


def when(epoch, now=None):
    """'Sep 8 14:59 (5d)' — absolute plus how long is left to spend the window."""
    if not epoch:
        return "—"
    now = now or time.time()
    left = epoch - now
    if left < 0:
        span = "due"
    elif left < 3600:
        span = f"{max(1, round(left / 60))}m"
    elif round(left / 3600) < 24:
        span = f"{round(left / 3600)}h"     # round, not floor: 2.0 days must not read 1d
    else:
        span = f"{round(left / 86400)}d"
    return f"{datetime.fromtimestamp(epoch).strftime('%b %-d %H:%M')} ({span})"


def secs_cell(secs):
    """Plain seconds, always. One unit keeps the column scannable; the roll-up
    line under the table carries the minutes."""
    return f"{int(secs)}s"


def money(amount):
    """Format dollars as $12.34, rounding half-up to the cent."""
    q = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"${q}"


def plain_num(x):
    """Trim trailing zeros so 0.445 and 0.025 stay exact in the cost table."""
    return f"{x:.6f}".rstrip("0").rstrip(".")


def load_catalog_or_die(config_dir):
    try:
        return load_catalog(config_dir=config_dir)
    except CatalogError as e:
        sys.stderr.write(f"report: {e}\n")
        sys.exit(1)


# ---------------------------------------------------------------- limits
def models_by_meter(catalog):
    """meter name -> the model slugs catalog lanes actually dispatch on it."""
    out = {}
    for lane in catalog["lanes"].values():
        out.setdefault(lane["meter"], []).append(lane["model"])
    return out


def model_cell(lane_row, by_meter):
    """What runs on this meter. Claude meters are this session, not a lane."""
    slugs = by_meter.get(lane_row["lane"])
    if slugs:
        return ", ".join(sorted(set(slugs)))
    m = lane_row.get("group") or "general"
    return "this session (all models)" if m == "general" else f"this session ({m})"


def ignored(lane_row, by_meter):
    """A meter no lane can spend, on a harness no orchestrator runs in-process, is
    ignored on purpose — agy's Claude/GPT group after Opus was dropped. A harness
    an orchestrator profile runs natively keeps its Meters: the session itself
    spends them. Derived, not listed: add a lane on that meter to the catalog and
    it returns to the table."""
    return (not by_meter.get(lane_row["lane"])
            and lane_row["harness"] not in orchestrators.native_harnesses())


def unprobed_meters(catalog, obs_map):
    """Catalog Meters a lane spends that got no probe row, though their
    harness's probe read a figure for another Meter.

    Such a Meter has an unknown Remaining, which the Gate never vetoes, so a
    probe that renamed its row (`Current week (Fable 5.2)`) would switch its
    Gate off without a word. A harness whose probe read nothing (absent, failed,
    or with no usage source, as Kiro's) says so in its own row instead.
    """
    read = {L.get("harness") for L in obs_map.values()
            if isinstance(L, dict) and L.get("r") is not None}
    spent = {lane.get("meter") for lane in catalog["lanes"].values()}
    return sorted(name for name, meter in catalog["meters"].items()
                  if name in spent and name not in obs_map and meter.get("harness") in read)


def usage_doc(refresh=False, max_age_min=None, routing=None):
    if refresh:
        return usage.acquire(refresh=True, max_age_min=max_age_min, timeout=180)
    if routing is not None and not meters_enabled(routing):
        return usage.load_cached()
    return usage.acquire(refresh=refresh, max_age_min=max_age_min, timeout=180)


def month_cell(price_month):
    if isinstance(price_month, int) or price_month == int(price_month):
        return f"${int(price_month)}"
    return f"${price_month}"


def plan_row(lane_row, meters):
    """One Plan consumption row. Unknown meters dash the last two columns."""
    name = lane_row["lane"]
    meter = meters.get(name)
    used = None if lane_row.get("remaining_weekly") is None else 1 - lane_row["remaining_weekly"]
    if not meter:
        return [name, "—", "—", "—", "—"]
    if used is None:
        return [name, meter["plan"], month_cell(meter["price_month"]), "—", "—"]
    dollars = meter["price_month"] * (WEEK_DAYS / DAYS_PER_MONTH) * used
    return [name, meter["plan"], month_cell(meter["price_month"]), pct(used), money(dollars)]


def cmd_limits(a):
    catalog = load_catalog_or_die(a.config_dir)
    routing = catalog.get("routing", {})
    metering = meters_enabled(routing)
    doc = usage_doc(a.refresh, a.max_age_min, routing=routing)
    gate = routing["gate"]
    obs_map = usage.observations(doc) or {}
    by_meter = models_by_meter(catalog)
    lanes = sorted((dict(L, lane=name, harness=L.get("harness"))
                    for name, L in obs_map.items()),
                   key=lambda L: (L.get("remaining_weekly") is None,
                                  -(L.get("remaining_weekly") or 0)))
    skipped = [L["lane"] for L in lanes if ignored(L, by_meter)]
    shown = [L for L in lanes
             if (a.all or not ignored(L, by_meter))
             and (not a.eligible or not metering or usage.eligible(obs_map.get(L["lane"]), gate))]
    rows = [[L["lane"], model_cell(L, by_meter), pct(L.get("remaining_weekly")),
             pct(L.get("remaining_5h")), when(L.get("reset_weekly")), when(L.get("reset_5h"))]
            for L in shown]
    stamp = doc.get("probed_at")
    age = int((time.time() - stamp) / 60) if isinstance(stamp, (int, float)) else None
    print("**Current limits:**\n")
    print(md_table(["Lane", "Model", "Weekly", "5h", "Weekly reset", "5h reset"], rows))
    plan_rows = []
    seen = set()
    for L in lanes:
        name = L["lane"]
        if name in seen:
            continue
        seen.add(name)
        if name in catalog["meters"]:
            plan_rows.append(plan_row(L, catalog["meters"]))
        elif a.all or not ignored(L, by_meter):
            plan_rows.append(plan_row(L, catalog["meters"]))
    if plan_rows:
        print("\n**Plan consumption this cycle:**\n")
        print(md_table(
            ["Meter", "Plan", "$/month", "Weekly used", "Plan $ used this cycle"],
            plan_rows,
        ))
        print("\nPlan $ used this cycle is the weekly slice of the monthly fee times the share used.")
    unknown = [L["lane"] for L in shown if L.get("remaining_weekly") is not None
               and not L.get("reset_weekly")]
    if unknown:
        print(f"\nWeekly reset unread for: {', '.join(unknown)}.")
    if skipped and not a.all:
        print(f"\nIgnored, no lane spends them: {', '.join(skipped)}.")
    unprobed = unprobed_meters(catalog, obs_map)
    if unprobed:
        print(f"\nNo probe row for: {', '.join(unprobed)}; the Gate never vetoes their lanes.")
    gate_pct = f"{int(round(gate * 100))}%"
    age_label = f"{age} min ago" if age is not None else "at an unknown time"
    if metering:
        print(f"\nProbed {age_label}. A meter under {gate_pct} remaining is skipped by rank.py.")
    else:
        print(f"\nCached {age_label}. Metering is off; ranking does not skip by Gate.")


# ---------------------------------------------------------------- cost
def _first_present(obj, keys):
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return None


def compute_cost(usage, lane_name, catalog):
    """Token dollars for one dispatch. Unmeasured when the relay sent no counts.

    A Lane with no input or output price is unpriced, not free: the wizard
    creates every new Lane with null prices, and reading them as $0 would
    under-report spend. Its tokens are kept and it is never measured. A null
    cache price is only unpublished (codex has no cache-write price) and adds 0.
    """
    if not isinstance(usage, dict):
        return {"measured": False, "reason": "relay reported no token usage"}
    input_raw = _first_present(usage, INPUT_KEYS)
    output_raw = _first_present(usage, OUTPUT_KEYS)
    if input_raw is None and output_raw is None:
        return {"measured": False, "reason": "relay reported no token usage"}
    lane = catalog["lanes"].get(lane_name)
    if not lane:
        return {"measured": False, "reason": "lane not in catalog"}
    price = lane["price"]
    tokens = {
        "in": 0 if input_raw is None else input_raw,
        "out": 0 if output_raw is None else output_raw,
        "cache_read": _first_present(usage, CACHE_READ_KEYS) or 0,
        "cache_write": _first_present(usage, CACHE_WRITE_KEYS) or 0,
    }
    missing = [k for k in ("in", "out") if price.get(k) is None]
    if missing:
        return {
            "measured": False,
            "unpriced": True,
            "reason": f"unpriced lane {lane_name}: no {' or '.join(missing)} price",
            "input_tokens": tokens["in"],
            "output_tokens": tokens["out"],
            "cache_read_tokens": tokens["cache_read"],
            "cache_write_tokens": tokens["cache_write"],
        }
    usd = {}
    unpublished = []
    for key, n in tokens.items():
        p = price.get(key)
        if p is None:
            usd[key] = 0
            unpublished.append(key)
        else:
            usd[key] = n / 1_000_000 * p
    note = ""
    if unpublished:
        note = "unpublished price: " + ", ".join(unpublished)
    return {
        "measured": True,
        "input_tokens": tokens["in"],
        "output_tokens": tokens["out"],
        "cache_read_tokens": tokens["cache_read"],
        "cache_write_tokens": tokens["cache_write"],
        "usd_in": usd["in"],
        "usd_out": usd["out"],
        "usd_cache_read": usd["cache_read"],
        "usd_cache_write": usd["cache_write"],
        "usd_total": usd["in"] + usd["out"] + usd["cache_read"] + usd["cache_write"],
        "note": note,
    }


def read_dispatch(run_dir):
    path = os.path.join(os.path.expanduser(run_dir), "dispatch.json")
    try:
        with open(path) as f:
            doc = json.load(f)
    except FileNotFoundError:
        sys.exit(f"report: {path}: file is missing")
    except json.JSONDecodeError as e:
        sys.exit(f"report: {path}: JSON syntax error: {e.msg}")
    except OSError as e:
        sys.exit(f"report: {path}: {e}")
    if not isinstance(doc, dict):
        sys.exit(f"report: {path}: dispatch.json must be an object")
    return doc


def price_cell(p):
    return "—" if p is None else plain_num(p)


def cmd_cost(a):
    catalog = load_catalog_or_die(a.config_dir)
    dispatch = read_dispatch(a.run_dir)
    lane = dispatch.get("lane")
    cost = compute_cost(dispatch.get("usage"), lane, catalog)
    if not cost.get("measured"):
        word = "unpriced" if cost.get("unpriced") else "unmeasured"
        print(f"{word}: {cost.get('reason', '')}")
        return
    price = catalog["lanes"].get(lane, {}).get("price") or {}
    rows = [
        ["input", cost["input_tokens"], price_cell(price.get("in")), plain_num(cost["usd_in"])],
        ["output", cost["output_tokens"], price_cell(price.get("out")), plain_num(cost["usd_out"])],
        ["cache_read", cost["cache_read_tokens"], price_cell(price.get("cache_read")),
         plain_num(cost["usd_cache_read"])],
        ["cache_write", cost["cache_write_tokens"], price_cell(price.get("cache_write")),
         plain_num(cost["usd_cache_write"])],
        ["total", "", "", plain_num(cost["usd_total"])],
    ]
    print(md_table(["Component", "Tokens", "$/M", "$"], rows))
    if cost.get("note"):
        print(f"\n{cost['note']}")


# ---------------------------------------------------------------- runs
def append_run(rec):
    os.makedirs(os.path.dirname(RUNS), exist_ok=True)
    with open(RUNS, "a") as f:
        f.write(json.dumps(rec) + "\n")


def cmd_log(a):
    if a.verdict not in VERDICTS:
        sys.exit(f"verdict must be one of {', '.join(VERDICTS)}")
    dispatch = read_dispatch(a.run_dir) if a.run_dir else None
    lane = a.lane or (dispatch or {}).get("lane")
    if not lane:
        sys.exit("report: --lane is required unless --run names a dispatch.json with lane")
    if a.secs is not None:
        secs = int(a.secs)
    else:
        ds = None if dispatch is None else dispatch.get("secs")
        if ds is None:
            sys.exit("report: --secs is required unless --run names a dispatch.json with secs")
        secs = int(ds)
    status = a.status if a.status is not None else ((dispatch or {}).get("status") or "done")
    thread = a.thread if a.thread is not None else (None if dispatch is None else dispatch.get("thread_id"))
    rec = {"v": 1, "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
           "work": a.work, "lane": lane, "class": a.klass, "secs": secs,
           "rc": a.rc, "status": status, "verdict": a.verdict, "outcome": a.outcome,
           "thread_id": thread, "batch": a.batch}
    if a.run_dir:
        catalog = load_catalog_or_die(a.config_dir)
        rec["cost"] = compute_cost((dispatch or {}).get("usage"), lane, catalog)
    append_run(rec)
    extra = ""
    if "cost" in rec:
        extra = " " + cost_cell(rec)
    print(f"logged: {a.work} → {lane} {secs_cell(secs)} {a.verdict}{extra}")


def read_runs():
    try:
        with open(RUNS) as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def cost_cell(rec):
    c = rec.get("cost")
    if not c:
        return "—"
    if c.get("unpriced"):
        return "unpriced"
    if not c.get("measured"):
        return "unmeasured"
    total = c.get("usd_total") or 0
    if 0 < total < 0.01:
        return "<$0.01"
    return money(total)


def cmd_runs(a):
    recs = read_runs()
    if a.batch:
        recs = [r for r in recs if r.get("batch") == a.batch]
    recs = recs[-a.last:] if a.last else recs
    if not recs:
        print("No runs logged yet.")
        return
    rows = [[r["work"], r["lane"], secs_cell(r["secs"]), cost_cell(r),
             r.get("outcome") or r["verdict"]] for r in recs]
    total = sum(r["secs"] for r in recs)
    bad = [r for r in recs if r["verdict"] in ("partial", "failed") or r.get("rc")]
    head = (f"{len(recs)} dispatches, all rc=0, zero failed lanes."
            if not bad else
            f"{len(recs)} dispatches, {len(bad)} needing a second pass.")
    print(head + "\n")
    print(md_table(["Work", "Lane", "Wall time", "Cost", "Outcome"], rows))
    line = (f"\n~{round(total / 60)} minutes of lane wall-time"
            f" across {len({r['lane'] for r in recs})} lanes, mostly in parallel.")
    costed = [r for r in recs if r.get("cost")]
    if costed:
        measured = [r for r in costed if r["cost"].get("measured")]
        n_unpriced = sum(1 for r in costed if r["cost"].get("unpriced"))
        n_unm = sum(1 for r in costed if not r["cost"].get("measured")) - n_unpriced
        usd = sum(r["cost"].get("usd_total") or 0 for r in measured)
        line += f"; {money(usd)} measured across {len(measured)} runs"
        if n_unpriced:
            line += f", {n_unpriced} unpriced"
        line += f", {n_unm} unmeasured"
    print(line)


# ---------------------------------------------------------------- statusline
ANSI = re.compile(r"\033\[[0-9;]*m")
TIER_GLYPH = {1: "①", 2: "②", 3: "③", 4: "④"}


def vis(s):
    return len(ANSI.sub("", s))


def pad(s, w):
    return s + " " * max(0, w - vis(s))


def rpad(s, w):
    return " " * max(0, w - vis(s)) + s


def get_colors(no_color):
    if no_color:
        return {
            "R": "", "BOLD": "", "DIM": "",
            "GRN": "", "CYAN": "", "YEL": "", "MAG": "",
            "RED": "", "MUTE": "", "FG": "",
            "TIER_COL": {1: "", 2: "", 3: "", 4: ""}
        }
    def rgb(h):
        return f"\033[38;2;{int(h[0:2], 16)};{int(h[2:4], 16)};{int(h[4:6], 16)}m"
    grn = rgb("78bd74")
    cyan = rgb("1fb5bc")
    yel = rgb("c68f32")
    mag = rgb("be80ca")
    red = rgb("d76563")
    mute = rgb("8d8d89")
    fg = rgb("e7e7e7")
    return {
        "R": "\033[0m", "BOLD": "\033[1m", "DIM": "\033[2m",
        "GRN": grn, "CYAN": cyan, "YEL": yel, "MAG": mag,
        "RED": red, "MUTE": mute, "FG": fg,
        "TIER_COL": {1: grn, 2: cyan, 3: yel, 4: mag}
    }


def dur_short(t, now):
    """Coarse: largest whole unit, floored — 4d, 2h, 46m."""
    if t is None:
        return ""
    s = max(0, int(t - now))
    return f"{s // 86400}d" if s >= 86400 else f"{s // 3600}h" if s >= 3600 else f"{s // 60}m"


def bar(u, n=5, gated=False, c=None):
    """Remaining as a fuel gauge: full cells from the left."""
    if u is None:
        return f"{c['MUTE']}{'·' * n}{c['R']}"
    blocks = " ▏▎▍▌▋▊▉█"
    full = min(n, int(u * n))
    eighth = round((u * n - full) * 8) if full < n else 0
    part = blocks[eighth] if eighth else ""
    col = c["RED"] if gated else c["FG"]
    return f"{col}{'█' * full}{part}{c['R']}{c['MUTE']}{'░' * (n - full - len(part))}{c['R']}"


def pct_cell(u, gated=False, c=None):
    if u is None:
        return f"{c['MUTE']}—{c['R']}"
    col = c["RED"] if gated else c["FG"]
    return f"{col}{round(u * 100)}%{c['R']}"


def num(u, reset, now, gated=False, c=None):
    """'58%·2h', or a lone dash when the meter has no such window."""
    if u is None:
        return rpad(pct_cell(u, gated, c), 4)
    d = dur_short(reset, now)
    return f"{rpad(pct_cell(u, gated, c), 4)}{c['DIM']}·{d}{c['R']}"


def gauge(u, reset, now, gated=False, c=None):
    return f"{bar(u, gated=gated, c=c)} {num(u, reset, now, gated=gated, c=c)}"


def get_meter_label(m_key, meter_def, all_meters):
    harness = meter_def.get("harness") or m_key
    harness_meters = [k for k, m in all_meters.items() if m.get("harness") == harness]
    if len(harness_meters) <= 1:
        return harness
    suffix = m_key.split("-", 1)[1] if "-" in m_key else m_key
    if suffix == "general":
        return harness
    return suffix


def format_label(lbl, won_tiers, c):
    won = sorted(won_tiers)
    col = c["TIER_COL"][won[0]] if won else c["MUTE"]
    return f"{col}{c['BOLD']}{lbl}{c['R']}"


def format_badge(won_tiers, c):
    # Claude Code trims leading whitespace off every status line row, so an
    # unbadged row keeps its column with a dim placeholder, never with spaces.
    if not won_tiers:
        return f"{c['MUTE']}·{c['R']}"
    return "".join(f"{c['TIER_COL'][t]}{TIER_GLYPH[t]}{c['R']}" for t in sorted(won_tiers))


def statusline_switch(state):
    """on / off / toggle / status for the rows; the switch is a flag file."""
    path = SWITCH
    if state == "status":
        print("off" if os.path.exists(path) else "on")
        return
    if state == "toggle":
        state = "on" if os.path.exists(path) else "off"
    if state == "off":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("delegate status line rows are off; remove this file or run "
                    "`report.py statusline on` to show them\n")
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    print(f"delegate rows {state}")


def running_glyphs(running_tiers, c):
    return "".join(
        f"{c['TIER_COL'][t]}{TIER_GLYPH[t] * running_tiers[t]}{c['R']}"
        for t in sorted(running_tiers)
        if running_tiers[t] > 0
    )


def cmd_statusline(a):
    if a.state:
        statusline_switch(a.state)
        return
    # The switch hides the rows under the Claude Code status line only; the
    # Herdr popup asks for them with --popup and always gets them.
    if os.path.exists(SWITCH) and not a.popup:
        return
    no_color = a.no_color or bool(os.environ.get("NO_COLOR"))
    c = get_colors(no_color)
    catalog = load_catalog_or_die(a.config_dir)

    cache_path = usage.get_cache_path()
    if not os.path.exists(cache_path):
        return
    usage_doc = usage.load_cached(cache_path)
    obs_map = usage.observations(usage_doc)
    if obs_map is None:
        return
    if not isinstance(usage_doc, dict) or not isinstance(usage_doc.get("lanes"), list):
        return

    now = time.time()
    present = installed_harnesses()
    routing = catalog.get("routing", {})
    classes = routing.get("classes", {})
    gate_threshold = routing["gate"]
    metering = meters_enabled(routing)

    won_by_meter = {}
    picks = {}
    for cls in classes:
        try:
            rows = rank(cls, catalog, usage_doc, present)
        except Exception:
            continue
        if rows and rows[0].get("pick"):
            picked = rows[0]
            m_name = picked.get("meter")
            tier = picked.get("tier")
            if m_name and tier is not None:
                won_by_meter.setdefault(m_name, set()).add(tier)
            picks[cls] = picked

    ledger_path = os.environ.get("DELEGATE_LEDGER") or os.path.expanduser("~/.cache/delegate/ledger.jsonl")
    running_by_lane = Counter()
    if os.path.exists(ledger_path):
        try:
            starts = {}
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    k = e.get("kind")
                    tid = e.get("thread_id")
                    if k == "dispatch.start" and tid:
                        starts[tid] = e
                    elif k == "dispatch.finish" and tid:
                        starts.pop(tid, None)
            for e in starts.values():
                ts_str = e.get("ts")
                timeout_s = e.get("timeout_s") or 0
                if ts_str:
                    try:
                        t = datetime.fromisoformat(ts_str).timestamp()
                    except Exception:
                        continue
                    if now <= t + timeout_s:
                        lane_name = e.get("lane")
                        if lane_name:
                            running_by_lane[lane_name] += 1
        except Exception:
            return

    by_meter = usage.observations(usage_doc) or {}
    all_meters = catalog.get("meters", {})
    catalog_order = list(all_meters.keys())

    def sort_key(m_key):
        won = won_by_meter.get(m_key)
        has_badge = bool(won)
        min_t = min(won) if has_badge else 99
        cat_idx = catalog_order.index(m_key) if m_key in catalog_order else 999
        return (0 if has_badge else 1, min_t, cat_idx)

    sorted_meters = sorted(catalog_order, key=sort_key)

    out_lines = []
    if not metering:
        out_lines.append(f"{c['DIM']}meters off{c['R']}")
    for m_key in sorted_meters:
        m_def = all_meters.get(m_key, {})
        lbl = get_meter_label(m_key, m_def, all_meters)
        u_row = by_meter.get(m_key, {})
        rem5 = u_row.get("remaining_5h")
        reset5 = u_row.get("reset_5h")
        remw = u_row.get("remaining_weekly")
        resetw = u_row.get("reset_weekly")
        model_remw = u_row.get("remaining_weekly_model")
        # A model Meter has a weekly Window of its own and shares its harness's
        # 5h Window, so its row leaves 5h blank. The catalog says so; a probe row
        # with a per-model weekly figure says so too.
        shares5 = bool(m_def.get("model_meter")) or model_remw is not None
        if model_remw is not None:
            remw = model_remw

        is_gated = metering and not usage.eligible(obs_map.get(m_key, u_row), gate_threshold)

        won_tiers = won_by_meter.get(m_key, set())
        badge_str = format_badge(won_tiers, c)
        label_str = format_label(lbl, won_tiers, c)

        if shares5:
            five_str = " " * 15
        else:
            five_str = f"{c['DIM']}5h{c['R']} {gauge(rem5, reset5, now, gated=False, c=c)}"

        gate_char = f"{c['RED']}{c['BOLD']}✗{c['R']}" if is_gated else ""
        wk_str = f"{c['DIM']}wk{c['R']} {gauge(remw, resetw, now, gated=is_gated, c=c)}{gate_char}"

        line = f"{pad(badge_str, 3)}{pad(label_str, 7)}{pad(five_str, 17)}{pad(wk_str, 17)}"

        if not a.no_running:
            running_tiers = Counter()
            for lane_name, count in running_by_lane.items():
                lane_def = catalog.get("lanes", {}).get(lane_name)
                if lane_def and lane_def.get("meter") == m_key:
                    running_tiers[lane_def["tier"]] += count
            glyphs = running_glyphs(running_tiers, c)
            if glyphs:
                line += " " + glyphs

        out_lines.append(line.rstrip())

    if a.popup and metering and present:
        # The popup's own layout (ticket 40): Pace as its calculation, then
        # each Tier on the same Pace axis. With Meters off there is no Pace to
        # draw, and with no CLI on PATH no Tier has a lane, so those keep the
        # rows above and the plain lane block.
        width = a.width or shutil.get_terminal_size((118, 24)).columns
        out_lines = popup_lines(catalog, usage_doc, present, picks, won_by_meter, c, width, now)
    elif a.popup:
        out_lines += lane_lines(catalog, usage_doc, present, picks, c)

    for l in out_lines:
        print(l)


def lane_lines(catalog, usage_doc, present, picks, c):
    """The popup's lane block: each Tier leader, then the Classes that pick it.

    A Class Pick that is not its Tier's leader gets its own line under that
    Tier, so every Class appears once.
    """
    try:
        previews = tier_leaders(catalog, usage_doc, present)
    except Exception:
        return []
    by_lane = {}
    for cls, row in picks.items():
        by_lane.setdefault(row["lane"], []).append(cls)
    lanes = [row["lane"] for row in picks.values()] + [p["leader"] for p in previews if p["leader"]]
    w = max([len(l) for l in lanes] or [0])
    lines = ["", f"{c['DIM']}lanes: Tier leader, then the Classes that pick it{c['R']}"]
    if not present:
        # Every Lane is vetoed without its harness; say why instead of four
        # "no eligible lane" lines.
        lines.append(f"{c['RED']}no harness CLI on PATH ({', '.join(HARNESSES)}){c['R']}")
        return lines
    for p in previews:
        t = p["tier"]
        glyph = f"{c['TIER_COL'][t]}{TIER_GLYPH[t]}{c['R']}"
        tier_lanes = [p["leader"]] if p["leader"] else []
        tier_lanes += [l for l in dict.fromkeys(r["lane"] for r in picks.values() if r["tier"] == t)
                       if l not in tier_lanes]
        if not tier_lanes:
            lines.append(f"{glyph}  {c['MUTE']}no eligible lane{c['R']}")
            continue
        for i, lane in enumerate(tier_lanes):
            lead = glyph if i == 0 else f"{c['MUTE']}·{c['R']}"
            col = c["TIER_COL"][t] if lane == p["leader"] else c["FG"]
            classes = " ".join(by_lane.get(lane, []))
            text = f"{col}{c['BOLD']}{lane:<{w}}{c['R']}"
            if classes:
                text += f"  {c['DIM']}{classes}{c['R']}"
            lines.append(f"{lead}  {text}".rstrip())
    return lines


# ------------------------------------------------------------- popup
# The Herdr popup (ticket 40, layout D): each Meter's weekly Pace as its
# calculation, then each Tier's Lanes on the same Pace axis with the steal line
# (leader Pace + Margin) and how far the leader's Meter can fall before the Tier
# hands over. Everything reads the cached Meters at the moment of display: no
# usage history and no burn rate (ADR 0001), so a distance is in quota points at
# today's readings, never a time.
POPUP_LEGEND = ("Pace = weekly Remaining ÷ share of the week left: 1 on track, above 1 spend it"
                " · ┊ = the Pace that Meter needs to lead the Tier")
POPUP_NUM_HEAD = "Pace = left ÷ time  5h      resets"
POPUP_NUM_W = 36
POPUP_LANE_W = 16
POPUP_METER_W = 7
HANDOVER_STEP = 0.005


def clip(s, w):
    """Cut a coloured line to w visible cells, keeping its colour codes."""
    out, n, i = [], 0, 0
    while i < len(s):
        m = ANSI.match(s, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        if n < w:
            out.append(s[i])
            n += 1
        i += 1
    return "".join(out)


def popup_meters(catalog, by_meter, won_by_meter, now):
    """One entry per Meter a Lane spends, in the statusline's order."""
    used = {l.get("meter") for l in catalog.get("lanes", {}).values() if l.get("enabled", True)}
    all_meters = catalog.get("meters", {})
    order = list(all_meters)
    out = []
    for key in order:
        if key not in used:
            continue
        row = by_meter.get(key) or {}
        weekly = row.get("remaining_weekly")
        reset = row.get("reset_weekly")
        left = row.get("cycle_left")
        if left is None and reset:
            left = min(1.0, max(usage.CYCLE_FLOOR, (reset - now) / (WEEK_DAYS * 86400)))
        shares5 = bool(all_meters[key].get("model_meter")) or row.get("remaining_weekly_model") is not None
        out.append({"key": key, "label": get_meter_label(key, all_meters[key], all_meters),
                    "weekly": weekly, "left": left, "pace": row.get("pace"), "reset": reset,
                    "f5": None if shares5 else row.get("remaining_5h"),
                    "reset5": None if shares5 else row.get("reset_5h"),
                    "won": won_by_meter.get(key, set())})
    out.sort(key=lambda m: (0 if m["won"] else 1, min(m["won"] or {99}), order.index(m["key"])))
    return out


def handover(preview, meter, margin, gate):
    """How far the Tier leader's Meter can fall before another Lane leads.

    Replays rank's choice (`rank.choose`) with only the leader's Meter
    spending: its weekly Remaining drops in small steps, the Pace of every Lane
    on it follows, and the first step where the Pick changes, or the Meter
    falls under the Gate, is the answer. Returns (points, new leader or None),
    or None when the leader's Meter has no weekly figure to spend.
    """
    rows = [r for r in preview["rows"] if r["eligible"]]
    lead = next((r for r in rows if r["lane"] == preview["leader"]), None)
    if lead is None or not meter or meter["weekly"] is None or not meter["left"]:
        return None
    others = [r for r in rows if r["meter"] != lead["meter"]]
    five = meter["f5"]
    spent = 0.0
    while True:
        spent += HANDOVER_STEP
        weekly = meter["weekly"] - spent
        remaining = weekly if five is None else min(five, weekly)
        if remaining < gate:
            # the leader's Meter is vetoed: the rest of the Tier decides
            pool = sorted(others, key=lambda r: eligible_order(r, True))
            return min(spent, meter["weekly"]), (choose(pool, margin, True)[0]["lane"] if pool else None)
        trial = [dict(r, pace=weekly / meter["left"]) if r["meter"] == lead["meter"] else r for r in rows]
        trial.sort(key=lambda r: eligible_order(r, True))
        pick = choose(trial, margin, True)[0]["lane"]
        if pick != lead["lane"]:
            return spent, pick


def pace_to_lead(preview, meter_key, top):
    """The lowest Pace at which a Lane on `meter_key` would lead the Tier, by
    rank's own choice (Pace order, then a steal by the Margin across Order),
    with every other Meter as it reads now; None when none up to `top` does."""
    rows = [r for r in preview["rows"] if r["eligible"]]
    margin = preview.get("margin", 0)
    pace = 0.0
    while pace <= top:
        trial = [dict(r, pace=pace) if r["meter"] == meter_key else r for r in rows]
        trial.sort(key=lambda r: eligible_order(r, True))
        if choose(trial, margin, True)[0]["meter"] == meter_key:
            return pace
        pace = round(pace + 0.01, 2)
    return None


def pace_axis(paces, width):
    """(top of the scale, value -> cell) for a Pace axis `width` cells wide."""
    top = max(3.0, min(8.0, float(int(max([p for p in paces if p is not None] + [1]) + 1))))
    return top, (lambda v: min(width - 1, max(0, round(v / top * (width - 1)))))


def axis_labels(top, x, width, c):
    cells = [" "] * width
    for k in range(int(top) + 1):
        text = str(k)
        pos = min(width - len(text), x(k))
        cells[pos:pos + len(text)] = list(text)
    return c["DIM"] + "".join(cells) + c["R"]


def track(top, x, width, c, dot=None, steal=None, steal_col=""):
    """One row of the Pace axis: the grid, Pace 1 as │, the steal line, the dot."""
    cells = [(c["MUTE"], "─")] * width
    for k in range(int(top) + 1):
        cells[x(k)] = (c["MUTE"], "│" if k == 1 else "┼")
    if steal is not None:
        cells[x(steal)] = (steal_col, "┊")
    if dot is not None and dot[0] is not None:
        cells[x(dot[0])] = (dot[1], dot[2])
    return "".join(f"{col}{ch}{c['R']}" for col, ch in cells)


def when_short(t):
    return time.strftime("%a %H:%M", time.localtime(t)) if t else "—"


def popup_lines(catalog, usage_doc, present, picks, won_by_meter, c, width, now):
    routing = catalog.get("routing", {})
    margin, gate = routing["margin"], routing["gate"]
    by_meter = usage.observations(usage_doc) or {}
    meters = popup_meters(catalog, by_meter, won_by_meter, now)
    by_key = {m["key"]: m for m in meters}
    try:
        previews = tier_leaders(catalog, usage_doc, present)
    except Exception:
        previews = []

    left_w = 2 + POPUP_METER_W + POPUP_LANE_W + 1
    axis_w = max(24, width - left_w - 2 - POPUP_NUM_W)
    steals = [r["pace"] + margin for p in previews for r in p["rows"]
              if r["lane"] == p["leader"] and r["pace"] is not None]
    top, x = pace_axis([m["pace"] for m in meters] + steals, axis_w)

    age = dur_short(now, usage_doc.get("probed_at") or now) or "0m"
    lines = [f"{c['BOLD']}delegate usage{c['R']}  {c['DIM']}read {age} ago · Margin {margin:.2f} · "
             f"Gate {gate:.0%}{c['R']}",
             f"{c['DIM']}{POPUP_LEGEND}{c['R']}",
             f"{c['DIM']}{'Meter':<{left_w}}{c['R']}{axis_labels(top, x, axis_w, c)}  "
             f"{c['DIM']}{POPUP_NUM_HEAD}{c['R']}"]
    for m in meters:
        won = sorted(m["won"])
        col = c["TIER_COL"][won[0]] if won else c["FG"]
        label = pad(format_badge(m["won"], c), 3) + f"{col}{c['BOLD']}{m['label']}{c['R']}"
        pace = "  ?" if m["pace"] is None else f"{m['pace']:.2f}"
        calc = ("" if m["weekly"] is None or m["left"] is None
                else f"= {m['weekly']:.0%} ÷ {m['left']:.0%}")
        five = (f"{c['MUTE']}—{c['R']}" if m["f5"] is None
                else f"{pct_cell(m['f5'], c=c)}{c['DIM']}·{dur_short(m['reset5'], now)}{c['R']}")
        lines.append(f"{pad(label, left_w)}{track(top, x, axis_w, c, (m['pace'], col + c['BOLD'], '●'))}  "
                     f"{c['BOLD']}{pace:>5}{c['R']} {c['DIM']}{calc:<12}{c['R']} {pad(five, 8)}"
                     f"{c['DIM']}{when_short(m['reset'])}{c['R']}")
    lines.append("")
    for p in previews:
        lines += tier_block(p, by_key, margin, gate, c, top, x, axis_w)
    lines.append(classes_line(picks, routing.get("classes", {}), c))
    return [clip(l, width).rstrip() for l in lines]


def tier_block(preview, by_key, margin, gate, c, top, x, axis_w):
    """A Tier's header (its leader and what changes next), then one row per
    Meter with Lanes in the Tier: the leader's Meter first, then by Pace."""
    t = preview["tier"]
    tc = c["TIER_COL"][t]
    head = f"{tc}{c['BOLD']}{TIER_GLYPH[t]} Tier {t}{c['R']}  "
    rows = [r for r in preview["rows"] if r["veto"] in (None, "gate", "cli")]
    if not rows:
        return [head + f"{c['MUTE']}no eligible lane{c['R']}"]
    lead = next((r for r in rows if r["lane"] == preview["leader"]), None)
    preview = dict(preview, margin=margin)
    out = [head + f"{c['DIM']}leader{c['R']} {tc}{c['BOLD']}{preview['leader'] or 'none'}{c['R']}  "
           f"{c['DIM']}{handover_note(preview, lead, by_key, margin, gate)}{c['R']}"]
    groups = {}
    for r in rows:
        groups.setdefault(r["meter"], []).append(r)
    keys = sorted(groups, key=lambda k: (0 if lead and k == lead["meter"] else 1,
                                         -(groups[k][0]["pace"] or 0), str(k)))
    for key in keys:
        group = groups[key]
        r = group[0]
        is_lead = lead is not None and r["lane"] == lead["lane"]
        col = tc if is_lead else c["FG"]
        bold = c["BOLD"] if is_lead else ""
        name = r["lane"].split("@")[0] + (f" +{len(group) - 1}" if len(group) > 1 else "")
        dot = (r["pace"], c["RED"], "✗") if r["veto"] == "gate" else (r["pace"], col + c["BOLD"], "●")
        need = None
        if r["veto"] == "gate":
            note = f"{c['RED']}under the Gate{c['R']}"
        elif r["veto"] == "cli":
            note = "no CLI here"
        elif is_lead or lead is None or r["pace"] is None:
            note = ""
        else:
            need = pace_to_lead(preview, key, top)
            note = "cannot lead on Pace" if need is None else f"needs {need:.2f} (+{max(0.0, need - r['pace']):.2f})"
        if len(group) > 1:
            note = (note + " · " if note else "") + "with " + ", ".join(o["lane"].split("@")[0] for o in group[1:])
        label = by_key[key]["label"] if key in by_key else str(key)
        cell = f"  {c['DIM']}{label[:POPUP_METER_W - 1]:<{POPUP_METER_W}}{c['R']}{col}{bold}{name[:POPUP_LANE_W - 1]:<{POPUP_LANE_W}}{c['R']}"
        pace = "  ?" if r["pace"] is None else f"{r['pace']:.2f}"
        out.append(f"{cell} {track(top, x, axis_w, c, dot, need, tc)}  {bold}{pace:>5}{c['R']}  "
                   f"{c['DIM']}{note}{c['R']}")
    return out


def handover_note(preview, lead, by_key, margin, gate):
    if lead is None:
        return ""
    meter = by_key.get(lead["meter"])
    found = handover(preview, meter, margin, gate)
    if found is None:
        return ""
    points, new = found
    label = meter["label"]
    if new is None:
        return f"only lane · {label} is {points * 100:.0f} pts above the Gate"
    return f"→ {new} leads after {label} drops {points * 100:.1f} pts"


def classes_line(picks, classes, c):
    parts = []
    for cls, row in picks.items():
        t = row.get("tier")
        floor = (classes.get(cls) or {}).get("floor")
        up = f"{c['RED']}↑{c['R']}" if floor and t and t > floor else ""
        parts.append(f"{cls} {c['TIER_COL'].get(t, '')}{TIER_GLYPH.get(t, '?')}{c['R']}{up}")
    return (f"{c['DIM']}classes{c['R']}  " + "  ".join(parts)
            + f"   {c['DIM']}↑ = Pace pulled it above its floor Tier{c['R']}")


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cfg = argparse.ArgumentParser(add_help=False)
    cfg.add_argument("--config-dir", default=None,
                     help="catalog directory (default ~/.config/delegate)")

    lim = sub.add_parser("limits", parents=[cfg], help="the Current limits table")
    lim.add_argument("--refresh", action="store_true", help="force a re-probe")
    lim.add_argument("--max-age-min", type=float, help="cache TTL override")
    lim.add_argument("--eligible", action="store_true", help="drop meters rank.py would skip")
    lim.add_argument("--all", action="store_true", help="include meters no lane can spend")
    lim.set_defaults(fn=cmd_limits)

    log = sub.add_parser("log", parents=[cfg], help="append one adjudicated dispatch")
    log.add_argument("--work", required=True, help="what the child was asked to do, 2-4 words")
    log.add_argument("--lane", default=None)
    log.add_argument("--secs", default=None, type=int, help="wall time from the dispatch line")
    log.add_argument("--verdict", required=True, choices=VERDICTS, help="the LEAD's adjudication")
    log.add_argument("--outcome", default="", help="one phrase, e.g. '4 findings, all real'")
    log.add_argument("--class", dest="klass", default=None)
    log.add_argument("--rc", type=int, default=0)
    log.add_argument("--status", default=None, help="status field of the out file")
    log.add_argument("--thread", default=None, help="thread_id from the delegate-metrics: line")
    log.add_argument("--batch", default=None, help="tag grouping one fan-out")
    log.add_argument("--run", dest="run_dir", default=None,
                     help="run directory; read lane, usage, secs, status, thread_id from dispatch.json")
    log.set_defaults(fn=cmd_log)

    run = sub.add_parser("runs", parents=[cfg], help="the dispatch table")
    run.add_argument("--last", type=int, default=0)
    run.add_argument("--batch", default=None)
    run.set_defaults(fn=cmd_runs)

    cost = sub.add_parser("cost", parents=[cfg], help="token cost for one run")
    cost.add_argument("run_dir", help="run directory with dispatch.json")
    cost.set_defaults(fn=cmd_cost)

    sl = sub.add_parser("statusline", parents=[cfg], help="Claude Code statusline meter rows")
    sl.add_argument("--no-color", action="store_true", help="strip ANSI color escapes")
    sl.add_argument("--no-running", action="store_true", help="suppress the running agents column")
    sl.add_argument("--popup", action="store_true",
                    help="the Herdr popup view: ignore the off switch; Pace per Meter and per Tier")
    sl.add_argument("--width", type=int, default=None,
                    help="popup width in columns (default: the terminal's)")
    sl.add_argument("state", nargs="?", choices=["on", "off", "toggle", "status"],
                    help="switch the rows instead of printing them (flag file ~/.cache/delegate/statusline.off)")
    sl.set_defaults(fn=cmd_statusline)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
