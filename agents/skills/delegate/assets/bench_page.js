// Inlined into the benchmark page by scripts/bench_page.py; never loaded on
// its own. It draws one score-against-cost plot per panel from the JSON in
// #bench-data, and beside the plots a panel of the tiers drawn on this page.
// Every decision in that JSON (which lane a point is, what the pre-screen
// proposes off, which effort beats which, the order lanes are listed in) was
// made in Python; this file only filters what is shown, finds the frontier of
// it, lays it out, and holds the page's own tier choices, which live in this
// browser's localStorage under the catalog's key and are written nowhere else
// (ticket 26). A lane may also be turned off here, and "Copy as lines" gives
// every decision as `<lane> <1-4|off>` for the wizard's review page to paste;
// the sensitivity table and "beaten by" are display aids drawn from the page's
// own tiers (ticket 27). The pure functions have no DOM, so tests/test_bench_page.py
// runs them under node. Text from a benchmark page is set with textContent
// only, never as markup.
(function () {
  "use strict";

  const EFFORT_ORDER = ["none", "low", "medium", "high", "xhigh", "max", "ultra"];
  const W = 880, H = 500;
  const PAD = { l: 58, r: 18, t: 14, b: 50 };
  const CHAR_PX = 6.6, LABEL_H = 12;
  const NO_HARNESS = "none";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const TIERS = [4, 3, 2, 1];
  // what a lane turned off on this page holds in place of a tier
  const OFF = "off";
  // meter name -> { name, harness, shade }, from the page's data; set at boot
  let SHADES = new Map();
  function setShades(meters) { SHADES = new Map((meters || []).map((m) => [m.name, m])); }

  // --- numbers and axes ------------------------------------------------------

  function effortIndex(effort) {
    const i = EFFORT_ORDER.indexOf(effort);
    return i < 0 ? EFFORT_ORDER.length : i;
  }

  function logTicks(lo, hi) {
    const pick = (mantissas) => {
      const out = [];
      for (let e = Math.floor(Math.log10(lo)) - 1; Math.pow(10, e) <= hi; e++) {
        for (const m of mantissas) {
          const v = +(m * Math.pow(10, e)).toPrecision(6);
          if (v >= lo * 0.9999 && v <= hi * 1.0001) out.push(v);
        }
      }
      return out;
    };
    let ticks = pick([1, 2, 5]);
    if (ticks.length < 3) ticks = pick([1, 1.5, 2, 3, 4, 5, 6, 8]);
    if (ticks.length < 3) ticks = pick([1, 1.2, 1.4, 1.6, 1.8, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 9]);
    return ticks;
  }

  // A round bound just outside the data on each side, with finer mantissas
  // than the ticks, so a board ending at $9,604 is not drawn to $20,000.
  function logDomain(values) {
    let lo = Math.min(...values), hi = Math.max(...values);
    if (hi / lo < 1.5) {
      const mid = Math.sqrt(lo * hi);
      lo = mid / 1.35;
      hi = mid * 1.35;
    }
    let loBound = null, hiBound = null;
    for (let e = Math.floor(Math.log10(lo)) - 1; Math.pow(10, e) <= hi * 10; e++) {
      for (const m of [1, 1.5, 2, 3, 4, 5, 6, 8]) {
        const v = +(m * Math.pow(10, e)).toPrecision(6);
        if (v <= lo * 0.92) loBound = v;
        if (v >= hi * 1.08 && hiBound === null) hiBound = v;
      }
    }
    return [loBound || lo * 0.8, hiBound || hi * 1.25];
  }

  // The score axis fits the points shown, not zero: a board whose scores all
  // sit between 0.6 and 0.9 is drawn across the whole height.
  function niceLinear(lo, hi, target) {
    target = target || 6;
    if (lo === hi) {
      const d = Math.abs(lo) * 0.1 || 1;
      lo -= d;
      hi += d;
    }
    const pad = (hi - lo) * 0.05;
    lo -= pad;
    hi += pad;
    const raw = (hi - lo) / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw * 0.999);
    const nlo = Math.floor(lo / step) * step, nhi = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let v = nlo; v <= nhi + step * 1e-6; v += step) ticks.push(+v.toFixed(10));
    return { lo: nlo, hi: nhi, step, ticks };
  }

  function decimalsFor(step) {
    let d = 0;
    while (d < 6 && Math.abs(Math.round(step * Math.pow(10, d)) - step * Math.pow(10, d)) > 1e-6) d++;
    return d;
  }

  function fmtMoney(v) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 100) return "$" + Math.round(v).toLocaleString("en-US");
    if (a >= 10) return "$" + v.toFixed(1);
    if (a >= 0.1) return "$" + v.toFixed(2).replace(/\.?0+$/, "");
    return "$" + String(+v.toPrecision(2));
  }

  function fmtTickMoney(v) {
    if (v >= 1000) return "$" + Math.round(v).toLocaleString("en-US");
    if (v >= 1) return "$" + String(+v.toPrecision(6));
    return "$" + String(+v.toPrecision(3));
  }

  // Fractions (every AA component) read to three places, points to one.
  function scoreDecimals(board) {
    return board.points.every((p) => p.score === null || Math.abs(p.score) <= 1.5) ? 3 : 1;
  }

  function fmtScore(v, unit, decimals) {
    if (v === null || v === undefined) return "—";
    return v.toFixed(decimals) + (unit === "%" ? "%" : "");
  }

  // --- what is shown, and its frontier ----------------------------------------

  function harnessKeys(p) {
    return p.harness && p.harness.length ? p.harness : [NO_HARNESS];
  }

  function isShown(p, st) {
    if (!p.plotted) return false;
    if (st.hiddenModels.has(p.model)) return false;
    if (st.hiddenEfforts.has(p.effort)) return false;
    return harnessKeys(p).some((h) => !st.hiddenHarness.has(h));
  }

  // The points nothing else beats: walking from cheapest to dearest, each one
  // scores more than every point to its left. A point that scores the same as
  // a cheaper one is not on it.
  function frontier(points) {
    const sorted = points.slice().sort((a, b) => a.cost - b.cost || b.score - a.score);
    const out = [];
    let best = -Infinity;
    for (const p of sorted) {
      if (p.score > best) {
        out.push(p);
        best = p.score;
      }
    }
    return out;
  }

  function frontierCandidates(shown, mode) {
    if (mode === "off") return [];
    if (mode === "lanes") return shown.filter((p) => p.lanes.length);
    return shown;
  }

  function labelText(p) {
    const weak = p.weak ? "?" : "";
    if (p.lanes.length) {
      return p.lanes[0].name + (p.lanes.length > 1 ? ` +${p.lanes.length - 1}` : "") + weak;
    }
    return `${p.name} ${p.effort}${weak}`;
  }

  function boxesClear(placed, box) {
    const [x0, y0, x1, y1] = box;
    return !placed.some(([a0, b0, a1, b1]) => x0 < a1 && a0 < x1 && y0 < b1 && b0 < y1);
  }

  // A label beside its point that lands on no other label and no point, or
  // null. A label that does not fit is dropped, never printed over another:
  // the tooltip and the tables still carry it.
  function place(text, cx, cy, placed, frame) {
    const width = text.length * CHAR_PX + 4;
    const [fx0, fy0, fx1, fy1] = frame;
    const slots = [[9, 4, "start"], [-9, 4, "end"], [9, -8, "start"], [-9, -8, "end"],
                   [9, 15, "start"], [-9, 15, "end"], [0, -11, "middle"], [0, 20, "middle"]];
    for (const [dx, dy, anchor] of slots) {
      const x = cx + dx, y = cy + dy;
      const x0 = anchor === "start" ? x : anchor === "end" ? x - width : x - width / 2;
      const box = [x0, y - LABEL_H + 3, x0 + width, y + 3];
      if (box[0] < fx0 || box[2] > fx1 || box[1] < fy0 || box[3] > fy1) continue;
      if (boxesClear(placed, box)) {
        placed.push(box);
        return { x, y, anchor, box };
      }
    }
    return null;
  }

  const KIND_RANK = { comparator: 0, own_other: 1, lane: 2, lane_off: 3 };

  // One wheel step about the pointer: the cost and score under (x, y) stay
  // under it, and every edge moves toward it by `factor` (below 1 zooms in).
  // Cost is on a log axis, so the cost edges move in log space. No DOM.
  function zoomAbout(d, p, x, y, factor) {
    const lx0 = Math.log10(d.xlo), lx1 = Math.log10(d.xhi);
    const fx = (x - p.x0) / (p.x1 - p.x0), fy = (p.y1 - y) / (p.y1 - p.y0);
    const lc = lx0 + fx * (lx1 - lx0), s = d.ylo + fy * (d.yhi - d.ylo);
    return { c0: Math.pow(10, lc + (lx0 - lc) * factor), c1: Math.pow(10, lc + (lx1 - lc) * factor),
             s0: s + (d.ylo - s) * factor, s1: s + (d.yhi - s) * factor };
  }

  // A drag of (dx, dy) SVG pixels while zoomed: the content follows the
  // pointer, so the domain moves the other way, in log space on the cost axis.
  function panBy(d, p, dx, dy) {
    const lx0 = Math.log10(d.xlo), lx1 = Math.log10(d.xhi);
    const sx = dx / (p.x1 - p.x0) * (lx1 - lx0), sy = dy / (p.y1 - p.y0) * (d.yhi - d.ylo);
    return { c0: Math.pow(10, lx0 - sx), c1: Math.pow(10, lx1 - sx), s0: d.ylo + sy, s1: d.yhi + sy };
  }

  // Whether a zoom shows at least the whole full view, so zooming out past it
  // is the full view again rather than empty margin around it.
  function covers(z, full) {
    return z.c0 <= full.xlo && z.c1 >= full.xhi && z.s0 <= full.ylo && z.s1 >= full.yhi;
  }

  // --- the tiers drawn on this page (pure) ------------------------------------

  // Score thresholds belong to one benchmark, whose scale is independent.
  function bandTier(score, lines) {
    if (!lines || lines.length !== 3) return null;
    return 1 + lines.filter((line) => score >= line).length;
  }

  function defaultLines(scores) {
    const values = scores.filter(Number.isFinite);
    if (!values.length) return null;
    let lo = Math.min(...values), hi = Math.max(...values);
    if (lo === hi) { lo -= Math.abs(lo) * 0.1 || 1; hi += Math.abs(hi) * 0.1 || 1; }
    return [0.25, 0.5, 0.75].map((f) => lo + f * (hi - lo));
  }

  function applyBands(board, lines, lanes, tiers, manual) {
    const carried = new Set(lanes.filter((l) => l.carried).map((l) => l.name));
    for (const p of board.points) {
      if (!p.plotted) continue;
      for (const lane of p.lanes) {
        if (carried.has(lane.name) && !manual[lane.name]) tiers[lane.name] = bandTier(p.score, lines);
      }
    }
  }

  function boardKey(board) { return JSON.stringify([board.source, board.benchmark]); }

  // The tier this page gives a point: its lanes' tier when they have one.
  // An off lane has no tier.
  function pointTier(p, tiers) {
    for (const lane of p.lanes || []) {
      const t = (tiers || {})[lane.name];
      if (TIERS.includes(t)) return t;
    }
    return null;
  }

  // Whether every lane of a point is turned off on this page.
  function pointOff(p, tiers) {
    return !!(p.lanes && p.lanes.length) && p.lanes.every((lane) => (tiers || {})[lane.name] === OFF);
  }

  // `ordered` regrouped by model: each group sits where its first lane sat,
  // and lists its efforts from most to least. The same rule as
  // bench.group_lanes, applied here to an order only the page knows.
  function groupLanes(ordered) {
    const groups = new Map();
    for (const lane of ordered) {
      if (!groups.has(lane.group)) groups.set(lane.group, []);
      groups.get(lane.group).push(lane);
    }
    const out = [];
    for (const members of groups.values()) {
      out.push(...members.slice().sort((a, b) => effortIndex(b.effort) - effortIndex(a.effort)));
    }
    return out;
  }

  // The review page's order, given these tiers: best tier first, then the
  // benchmark order, then each model's group where its first lane sits.
  function reviewOrder(lanes, tiers) {
    const ordered = lanes.slice().sort((a, b) => ((tiers[b.name] || 0) - (tiers[a.name] || 0)) || (a.rank - b.rank));
    return groupLanes(ordered);
  }

  // One line per decided lane, `<lane> <1-4|off>`: the placed lanes in the
  // review page's order, then the off lanes, which the review page does not
  // list, in benchmark order grouped by model. A lane not placed is not written.
  // tier_lines.parse_tier_lines reads exactly this.
  function tierLinesText(lanes, tiers) {
    const placed = lanes.filter((l) => TIERS.includes(tiers[l.name]));
    const off = lanes.filter((l) => tiers[l.name] === OFF).sort((a, b) => a.rank - b.rank);
    return reviewOrder(placed, tiers).map((l) => `${l.name} ${tiers[l.name]}`)
      .concat(groupLanes(off).map((l) => `${l.name} ${OFF}`)).join("\n");
  }

  // The lanes still carried on this page: carried in the catalog, not off here.
  function carriedNames(lanes, tiers) {
    return new Set(lanes.filter((l) => l.carried && (tiers || {})[l.name] !== OFF).map((l) => l.name));
  }

  // The lanes this page may place (ticket 35). A tier is picked on a dot, and a
  // dot is a lane with rows, so a lane the catalog does not carry is placeable
  // as soon as a board draws it: the wizard carries whatever a line names. A
  // carried lane with no rows stays listed, because it still takes a tier.
  // `ultra` is never placeable — `parse_tier_lines` refuses it, so offering it
  // would only write a line the wizard throws away.
  function placeable(lanes) {
    return (lanes || []).filter((l) => (l.carried || l.rows) && l.effort !== "ultra");
  }

  // At least the score for no more money, and strictly better in one of the
  // two: the pre-screen's comparison (carry.beats), here across models.
  function beats(o, q) {
    return o.score >= q.score && o.cost <= q.cost && (o.score > q.score || o.cost < q.cost);
  }

  // {lane: the carried lane that beats it on this one board}. A display aid
  // like the frontier (ticket 27, item 5): any model may beat any other, costs
  // are compared only inside the board, and the carry rule is not this. When
  // several beat a lane, the one named scores most, then costs least.
  function beatenByLane(board, carried) {
    const carriedOf = (p) => p.lanes.filter((l) => carried.has(l.name)).map((l) => l.name);
    const pts = board.points.filter((p) => p.plotted && carriedOf(p).length);
    const out = {};
    for (const q of pts) {
      const own = carriedOf(q);
      let best = null;
      for (const o of pts) {
        if (o === q || carriedOf(o).some((n) => own.includes(n)) || !beats(o, q)) continue;
        if (!best || o.score > best.score || (o.score === best.score
            && (o.cost < best.cost || (o.cost === best.cost && carriedOf(o)[0] < carriedOf(best)[0])))) best = o;
      }
      if (best) for (const name of own) out[name] = carriedOf(best)[0];
    }
    return out;
  }

  // The tier panel's grouping, which the sensitivity table follows: tiers 4
  // to 1, then off, then not placed; inside each, one group per meter in the
  // page's meter order; inside that, benchmark order grouped by model.
  function panelGroups(lanes, tiers, meters) {
    const order = (meters || []).map((m) => m.name);
    return TIERS.concat([OFF, null]).map((tier) => {
      const mine = placeable(lanes).filter((l) => ((tiers || {})[l.name] || null) === tier);
      const names = order.concat([...new Set(mine.map((l) => l.meter))].filter((m) => !order.includes(m)));
      const groups = [];
      for (const meter of names) {
        const ms = mine.filter((l) => l.meter === meter).sort((a, b) => a.rank - b.rank);
        if (ms.length) groups.push({ meter, lanes: groupLanes(ms) });
      }
      return { tier, count: mine.length, meters: groups };
    });
  }

  // The tier each board alone would give each placed lane (ticket 27, item 4):
  // the board ranks the placed lanes it measured by score (a lane on two points
  // takes its best) and cuts that ranking in the proportions of the page's tier
  // counts, tier 4 first. Lanes that tie on score take the better tier. A
  // board's composite index is shown and never counted in `agree`.
  function sensitivity(boards, lanes, tiers, meters) {
    const groups = panelGroups(lanes, tiers, meters).filter((g) => TIERS.includes(g.tier));
    const counts = {};
    for (const g of groups) counts[g.tier] = g.count;
    const placed = groups.flatMap((g) => g.meters.flatMap((m) => m.lanes));
    const names = new Set(placed.map((l) => l.name));
    const given = {};
    for (const b of boards) {
      const mine = given[b.id] = {};
      for (const [name, c] of cutBoard(b, names, counts, placed.length)) mine[name] = c.tier;
    }
    const row = (l) => {
      const tier = tiers[l.name];
      const cells = boards.map((b) => {
        const t = given[b.id][l.name];
        return t === undefined ? null : { tier: t, differs: t !== tier };
      });
      const counted = cells.filter((c, i) => c && !boards[i].composite);
      return { name: l.name, meter: l.meter, tier, cells,
               agree: counted.filter((c) => !c.differs).length, measured: counted.length };
    };
    return { counts,
             columns: boards.map((b) => ({ id: b.id, benchmark: b.benchmark, source: b.source, composite: !!b.composite })),
             groups: groups.map((g) => ({ tier: g.tier, count: g.count, rows: g.meters.flatMap((m) => m.lanes.map(row)) })) };
  }

  // A ranking cut in the proportions `counts` gives out of `total`, tier 4
  // first: [[name, value]], best first, in, and a Map of name -> tier out.
  // Entries that tie on value take the better tier. Shared by a board's cut
  // and a view's (`viewTiers`).
  function cutRanked(ranked, counts, total) {
    const ends = [];
    let cum = 0;
    for (const t of TIERS) {
      cum += counts[t] || 0;
      ends.push([t, total ? Math.round(ranked.length * cum / total) : 0]);
    }
    const out = new Map();
    let tieStart = 0;
    ranked.forEach(([name, value], i) => {
      if (i > 0 && value !== ranked[i - 1][1]) tieStart = i;
      out.set(name, (ends.find(([, end]) => tieStart < end) || ends[ends.length - 1])[0]);
    });
    return out;
  }

  // One board's cut, for the sensitivity table: the lanes in `names` the board
  // measured, each at its best plotted point, ranked by score and cut by
  // `cutRanked`. A Map, best first, of lane -> { tier, score, cost }.
  function cutBoard(board, names, counts, total) {
    const best = new Map();
    for (const p of board ? board.points : []) {
      if (!p.plotted) continue;
      for (const l of p.lanes) {
        if (!names.has(l.name)) continue;
        const was = best.get(l.name);
        if (!was || p.score > was.score || (p.score === was.score && p.cost < was.cost)) {
          best.set(l.name, { score: p.score, cost: p.cost, effort: p.effort });
        }
      }
    }
    const ranked = [...best.entries()].sort((x, y) => y[1].score - x[1].score || x[1].cost - y[1].cost
                                                     || (x[0] < y[0] ? -1 : 1));
    const tiers = cutRanked(ranked.map(([name, at]) => [name, at.score]), counts, total);
    return new Map(ranked.map(([name, at]) => [name, Object.assign({ tier: tiers.get(name) }, at)]));
  }

  // --- the views (benchmark-views ticket 05) -----------------------------------------

  // The tier each lane holds for the views: the one drawn on this page, else
  // the catalog's own. A lane off on this page holds none, and so does a lane
  // with neither.
  function heldTiers(lanes, tiers) {
    const out = {};
    for (const l of placeable(lanes)) {
      const t = (tiers || {})[l.name];
      if (t === OFF) continue;
      if (TIERS.includes(t)) out[l.name] = t;
      else if (l.carried && TIERS.includes(l.tier)) out[l.name] = l.tier;
    }
    return out;
  }

  // A view is one kind of job (coding, knowledge work, automation; the overall
  // index for reference) and the boards views.json lists for it, one zoomable
  // plot each. A series is a Model on a Harness: its efforts joined in effort
  // order, coloured by the Harness and shaped by the Model. Under the plots a
  // table gives each series' score range across its efforts on every board.
  // Which Models are picked, the effort filter and the reference Models drawn
  // are how the page is read, not what it holds, so none of it is saved; the
  // tier a view gives a lane is a display aid, and nothing writes it.

  const HARNESS_ORDER = ["codex", "claude", "kiro", "agy", "grok"];
  const SHAPES = ["circle", "square", "diamond", "triangle", "down"];
  // a lower effort within this many percentile points of a Model's best is the
  // one a view favours
  const FAVOUR_MARGIN = 5;

  // A click picks one; shift-click adds or removes one; a click on the only
  // pick clears it.
  function pick(set, value, shift) {
    if (shift) {
      if (set.has(value)) set.delete(value);
      else set.add(value);
    } else if (set.size === 1 && set.has(value)) {
      set.clear();
    } else {
      set.clear();
      set.add(value);
    }
    return set;
  }

  // One series per Model (the lanes' `group`) on each Harness that runs it. A
  // Model's primary Harness is the one with the most lanes, Kiro last as it
  // re-runs Models other Harnesses run, and it draws every effort a board
  // measured; another Harness draws only the efforts it has lanes for. Each
  // Model has a shape within its Harness. `ultra` is never a series' effort.
  function viewSeries(lanes) {
    const seen = [...new Set((lanes || []).map((l) => l.harness).filter(Boolean))];
    const order = HARNESS_ORDER.filter((h) => seen.includes(h))
      .concat(seen.filter((h) => !HARNESS_ORDER.includes(h)).sort());
    const byModel = new Map();
    for (const l of lanes || []) {
      if (!l.group || !l.harness || l.effort === "ultra") continue;
      if (!byModel.has(l.group)) byModel.set(l.group, new Map());
      const hs = byModel.get(l.group);
      if (!hs.has(l.harness)) hs.set(l.harness, []);
      hs.get(l.harness).push(l);
    }
    const list = [];
    for (const [group, hs] of byModel) {
      const ranked = [...hs.keys()].sort((a, b) => (hs.get(b).length - hs.get(a).length)
        || ((a === "kiro") - (b === "kiro")) || (order.indexOf(a) - order.indexOf(b)));
      ranked.forEach((h, i) => {
        const own = new Map();
        for (const l of hs.get(h)) if (!own.has(l.effort)) own.set(l.effort, l);
        const first = hs.get(h)[0];
        list.push({ id: `${group}@${h}`, group, harness: h, primary: i === 0,
                    label: first.label || group, lanes: own });
      });
    }
    for (const h of order) {
      const models = [...new Set(list.filter((s) => s.harness === h).map((s) => s.group))].sort();
      for (const s of list) if (s.harness === h) s.shape = SHAPES[models.indexOf(s.group) % SHAPES.length];
    }
    list.sort((a, b) => (order.indexOf(a.harness) - order.indexOf(b.harness)) || a.label.localeCompare(b.label));
    return { order, list };
  }

  // One board as a view reads it: its scored points by Model and effort (the
  // best when two rows share one), the plotted ones, their frontier, the
  // median cost, whether the scores are fractions, and the full extent of its
  // plot in log cost and score.
  function indexBoard(board) {
    const scored = board.points.filter((p) => p.score !== null && p.score !== undefined);
    const pts = scored.filter((p) => p.cost > 0);
    const at = new Map();
    for (const p of scored) {
      if (!p.group) continue;
      const key = `${p.group}|${p.effort}`, was = at.get(key);
      if (!was || p.score > was.score) at.set(key, p);
    }
    const front = [];
    let best = -Infinity;
    for (const p of pts.slice().sort((a, c) => a.cost - c.cost || c.score - a.score)) {
      if (p.score > best) { front.push(p); best = p.score; }
    }
    const costs = pts.map((p) => p.cost).sort((a, c) => a - c);
    let home = null;
    if (pts.length) {
      const lx = pts.map((p) => Math.log10(p.cost)), ys = pts.map((p) => p.score);
      const px = (Math.max(...lx) - Math.min(...lx)) * 0.06 || 0.5, py = (Math.max(...ys) - Math.min(...ys)) * 0.07 || 1;
      home = { x0: Math.min(...lx) - px, x1: Math.max(...lx) + px, y0: Math.min(...ys) - py, y1: Math.max(...ys) + py };
    }
    return { board, scored, pts, at, front, onFront: new Set(front), home,
             scores: scored.map((p) => p.score).sort((a, c) => a - c),
             med: costs.length ? costs[Math.floor((costs.length - 1) / 2)] : null,
             frac: board.unit !== "%" && scored.every((p) => Math.abs(p.score) <= 1.5) };
  }

  // The share of a board's other rows a score beats, ties counting half, 0 to 100.
  function percentile(sorted, score) {
    let lo = 0, eq = 0;
    for (const v of sorted) {
      if (v < score) lo++;
      else if (v === score) eq++;
    }
    return sorted.length > 1 ? 100 * (lo + Math.max(eq - 1, 0) / 2) / (sorted.length - 1) : 50;
  }

  // A series at one effort across a view's boards: how many measured it, its
  // mean percentile over those, and its cost against each board's median cost,
  // as a geometric mean. A series off its primary Harness counts only the
  // efforts it has lanes for.
  function viewScore(boards, s, effort) {
    if (!s.primary && !s.lanes.has(effort)) return { n: 0 };
    const got = [];
    for (const x of boards) {
      const p = x.at.get(`${s.group}|${effort}`);
      if (p) got.push({ pct: percentile(x.scores, p.score), rc: x.med && p.cost > 0 ? p.cost / x.med : null });
    }
    if (!got.length) return { n: 0 };
    const rcs = got.map((g) => g.rc).filter((v) => v !== null);
    return { n: got.length, mean: got.reduce((a, g) => a + g.pct, 0) / got.length,
             rc: rcs.length ? Math.exp(rcs.reduce((a, v) => a + Math.log(v), 0) / rcs.length) : null };
  }

  // The lowest effort, of `efforts` in effort order, whose mean percentile is
  // within FAVOUR_MARGIN of the series' best. Null when nothing measured it.
  function favouredEffort(boards, s, efforts) {
    const cand = efforts.map((e) => Object.assign({ e }, viewScore(boards, s, e))).filter((c) => c.n);
    if (!cand.length) return null;
    const top = Math.max(...cand.map((c) => c.mean));
    return cand.find((c) => c.mean >= top - FAVOUR_MARGIN).e;
  }

  // The tier a view gives each lane that holds one (`heldTiers`): the held
  // lanes it measured at their own effort, ranked by mean percentile, the
  // cheaper first on a tie, and cut in the proportions the held tiers make
  // (`cutRanked`, as a board's cut in the sensitivity table). `thin` when the
  // view's boards measured the lane on fewer than half, or on one of several.
  // A Map of lane -> row; a held lane no board measured has `n` 0 and no tier.
  function viewTiers(boards, series, held) {
    const counts = {};
    for (const t of Object.values(held)) counts[t] = (counts[t] || 0) + 1;
    const rows = [];
    for (const s of series) {
      for (const l of s.lanes.values()) {
        if (held[l.name] === undefined) continue;
        rows.push(Object.assign({ name: l.name, group: s.group, harness: s.harness, effort: l.effort,
                                  held: held[l.name] }, viewScore(boards, s, l.effort)));
      }
    }
    const cost = (r) => (r.rc === null || r.rc === undefined ? Infinity : r.rc);
    const ranked = rows.filter((r) => r.n)
      .sort((a, c) => c.mean - a.mean || cost(a) - cost(c) || (a.name < c.name ? -1 : 1));
    const tiers = cutRanked(ranked.map((r) => [r.name, r.mean]), counts, Object.keys(held).length);
    const N = boards.length;
    ranked.forEach((r, i) => {
      const tie = i > 0 && ranked[i - 1].mean === r.mean;
      r.tier = tiers.get(r.name);
      r.rank = tie ? ranked[i - 1].rank : i + 1;
      r.thin = N > 1 && (r.n < N / 2 || r.n === 1);
    });
    return new Map(rows.map((r) => [r.name, r]));
  }

  // The zoom that shows one tier: its band between the tier lines when there
  // are lines, else the points this page gives that tier. Hand assignments
  // remain in view even outside their score band. Null when there is nothing to show.
  function focusDomain(board, st, tier) {
    const shown = board.points.filter((p) => isShown(p, st));
    const mine = shown.filter((p) => p.lanes.length && pointTier(p, st.tiers) === tier);
    const lines = st.tierLines;
    let pool = mine, scores;
    if (lines && lines.length === 3) {
      const lo = tier > 1 ? lines[tier - 2] : Math.min(...shown.map((p) => p.score));
      const hi = tier < 4 ? lines[tier - 1] : Math.max(...shown.map((p) => p.score));
      pool = shown.filter((p) => bandTier(p.score, lines) === tier);
      pool = [...new Set([...pool, ...mine])];
      scores = [lo, hi, ...mine.map((p) => p.score)];
    } else scores = mine.map((p) => p.score);
    if (!pool.length) return null;
    const [xlo, xhi] = logDomain(pool.map((p) => p.cost));
    const lin = niceLinear(Math.min(...scores), Math.max(...scores));
    return { c0: xlo, c1: xhi, s0: lin.lo, s1: lin.hi };
  }

  // Everything one plot draws, in SVG coordinates, from one board and one
  // panel's settings. `st.tiers`, `st.tierLines` and `st.focusTier` are the
  // page's, passed in so this stays pure. No DOM.
  function layout(board, st) {
    const shown = board.points.filter((p) => isShown(p, st));
    const out = { shown, points: [], labels: [], sweeps: [], frontier: [], xTicks: [], yTicks: [],
                  lines: [], bands: [], steps: "", wash: "", domain: null, plot: null };
    if (!shown.length) return out;
    const H = st.height || 500;
    const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
    out.plot = { x0: PAD.l, y0: PAD.t, x1: W - PAD.r, y1: H - PAD.b };
    let xlo, xhi, ylo, yhi, yticks;
    if (st.zoom) {
      ({ c0: xlo, c1: xhi, s0: ylo, s1: yhi } = st.zoom);
      yticks = niceLinear(ylo, yhi).ticks.filter((v) => v >= ylo - 1e-9 && v <= yhi + 1e-9);
    } else {
      [xlo, xhi] = logDomain(shown.map((p) => p.cost));
      const lin = niceLinear(Math.min(...shown.map((p) => p.score)), Math.max(...shown.map((p) => p.score)));
      [ylo, yhi, yticks] = [lin.lo, lin.hi, lin.ticks];
    }
    out.domain = { xlo, xhi, ylo, yhi };
    const lxlo = Math.log10(xlo), lxhi = Math.log10(xhi);
    const X = (c) => PAD.l + (Math.log10(c) - lxlo) / (lxhi - lxlo) * iw;
    const Y = (s) => PAD.t + ih - (s - ylo) / (yhi - ylo) * ih;
    const ystep = yticks.length > 1 ? yticks[1] - yticks[0] : Math.abs(yhi - ylo) / 5;
    const yd = decimalsFor(+ystep.toPrecision(6));
    out.xTicks = logTicks(xlo, xhi).map((v) => ({ x: X(v), text: fmtTickMoney(v) }));
    out.yTicks = yticks.map((v) => ({ y: Y(v), text: v.toFixed(yd) + (board.unit === "%" ? "%" : "") }));

    const fr = frontier(frontierCandidates(shown, st.frontier));
    const onFrontier = new Set(fr);
    out.frontier = fr;
    if (fr.length) {
      const right = W - PAD.r, bottom = H - PAD.b;
      let steps = `M${X(fr[0].cost).toFixed(1)},${Y(fr[0].score).toFixed(1)}`;
      for (const p of fr.slice(1)) steps += ` H${X(p.cost).toFixed(1)} V${Y(p.score).toFixed(1)}`;
      steps += ` H${right}`;
      out.steps = steps;
      out.wash = `M${X(fr[0].cost).toFixed(1)},${bottom} V${Y(fr[0].score).toFixed(1)}`
        + steps.slice(steps.indexOf(" ")) + ` V${bottom} Z`;
    }

    if (st.lines) {
      const byModel = new Map();
      for (const p of shown) {
        if (!byModel.has(p.model)) byModel.set(p.model, []);
        byModel.get(p.model).push(p);
      }
      for (const [model, rows] of byModel) {
        if (rows.length < 2) continue;
        rows.sort((a, b) => effortIndex(a.effort) - effortIndex(b.effort));
        out.sweeps.push({ model, ours: rows[0].ours,
                          points: rows.map((p) => `${X(p.cost).toFixed(1)},${Y(p.score).toFixed(1)}`).join(" ") });
      }
    }

    // the tier lines, and the name of each band they cut the axis into
    const tierLines = st.tierLines && st.tierLines.length === 3 ? st.tierLines : null;
    if (tierLines) {
      out.lines = tierLines.map((score, index) => ({ score, index, y: Y(score), inside: score >= ylo && score <= yhi }));
      const edges = [ylo, ...tierLines, yhi].map((s) => Math.min(Math.max(s, ylo), yhi));
      out.bands = TIERS.slice().reverse().map((tier, i) => ({ tier, y0: Y(edges[i + 1]), y1: Y(edges[i]) }))
        .filter((b) => b.y1 - b.y0 > 14);
    }

    const tiers = st.tiers || {};
    const inFrame = shown.filter((p) => p.cost >= xlo && p.cost <= xhi && p.score >= ylo && p.score <= yhi);
    out.points = inFrame
      .map((p) => {
        const tier = pointTier(p, tiers);
        return { p, x: X(p.cost), y: Y(p.score), frontier: onFrontier.has(p), tier, off: pointOff(p, tiers),
                 band: bandTier(p.score, tierLines), dim: !!st.focusTier && tier !== st.focusTier };
      })
      .sort((a, b) => KIND_RANK[a.p.kind] - KIND_RANK[b.p.kind] || a.frontier - b.frontier);

    const placed = out.points.map((q) => [q.x - 7, q.y - 7, q.x + 7, q.y + 7]);
    const frame = [PAD.l + 2, PAD.t + (out.bands.length ? 14 : 0), W - PAD.r, H - PAD.b];
    const byScore = (a, b) => b.p.score - a.p.score;
    const queue = [];
    if (st.labels !== "none") {
      queue.push(...out.points.filter((q) => q.frontier).sort((a, b) => a.p.cost - b.p.cost));
      if (st.labels === "lanes" || st.labels === "all") {
        queue.push(...out.points.filter((q) => !q.frontier && q.p.lanes.length).sort(byScore));
      }
      if (st.labels === "all") {
        queue.push(...out.points.filter((q) => !q.frontier && !q.p.lanes.length).sort(byScore));
      }
    }
    for (const q of queue) {
      const text = labelText(q.p);
      const slot = place(text, q.x, q.y, placed, frame);
      if (!slot) continue;
      out.labels.push({ x: slot.x, y: slot.y, anchor: slot.anchor, text, box: slot.box,
                        model: q.p.model, frontier: q.frontier, off: q.p.kind === "lane_off",
                        ours: q.p.ours, dim: q.dim });
    }
    return out;
  }

  // --- drawing ----------------------------------------------------------------

  function svg(tag, attrs, parent) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function el(tag, attrs, text, parent) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    if (text !== undefined && text !== null) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }

  function harnessColour(harness) {
    return `var(--h-${harness}, var(--accent))`;
  }

  // Colour is the meter (ticket 27): a meter takes its harness's colour, and a
  // second meter on one harness a shade of it (`--h-claude-1`). A shade the
  // style does not define falls back to the harness colour.
  function meterColour(meter) {
    const m = SHADES.get(meter);
    if (!m) return "var(--accent)";
    return m.shade ? `var(--h-${m.harness}-${m.shade}, var(--h-${m.harness}, var(--accent)))` : harnessColour(m.harness);
  }

  function pointColour(p) {
    if (p.kind === "comparator") return "var(--muted)";
    if (p.meter && p.meter.length && SHADES.has(p.meter[0])) return meterColour(p.meter[0]);
    return harnessColour(harnessKeys(p)[0]);
  }

  // Shape and fill carry the kind, a dashed outline weak provenance, colour
  // the meter, and in the tier view the digit inside a lane's dot is the
  // tier this page gives it; a hollow dot there has none yet, and a struck one
  // is off. Never colour alone.
  function marker(g, p, cx, cy, view) {
    const colour = pointColour(p);
    const dash = p.weak ? { "stroke-dasharray": "2.5 2" } : {};
    const tierView = view && view.tierView;
    if (p.kind === "comparator") {
      const r = 5.5;
      svg("path", Object.assign({ d: `M${cx},${cy - r} L${cx + r},${cy} L${cx},${cy + r} L${cx - r},${cy} Z`,
                                  fill: "var(--surface)", stroke: colour, "stroke-width": 1.6, class: "mk" }, dash), g);
    } else if (p.kind === "own_other" || p.weak) {
      svg("circle", Object.assign({ cx, cy, r: 4.8, fill: "var(--surface)", stroke: colour,
                                    "stroke-width": 2, class: "mk" }, dash), g);
    } else if (tierView) {
      const tier = view.tier;
      if (tier) {
        svg("circle", { cx, cy, r: 8.5, fill: colour, stroke: "var(--surface)", "stroke-width": 1.5, class: "mk" }, g);
        svg("text", { x: cx, y: cy + 3.8, class: "digit" }, g).textContent = String(tier);
      } else if (view.off) {
        svg("circle", { cx, cy, r: 6.5, fill: "var(--surface)", stroke: colour, "stroke-width": 1.5, class: "mk" }, g);
        svg("path", { d: `M${cx - 8},${cy} L${cx + 8},${cy}`, stroke: "var(--off)", "stroke-width": 2.2,
                      "stroke-linecap": "round" }, g);
      } else {
        svg("circle", { cx, cy, r: 7.5, fill: "var(--surface)", stroke: colour, "stroke-width": 2, class: "mk" }, g);
      }
      if (p.kind === "lane_off") svg("circle", { cx, cy, r: 11, fill: "none", stroke: "var(--off)", "stroke-width": 1.5 }, g);
    } else if (p.kind === "lane_off") {
      svg("circle", { cx, cy, r: 6.5, fill: colour, stroke: "var(--surface)", "stroke-width": 1.5, class: "mk" }, g);
      const k = 3;
      svg("path", { d: `M${cx - k},${cy - k} L${cx + k},${cy + k} M${cx - k},${cy + k} L${cx + k},${cy - k}`,
                    stroke: "var(--surface)", "stroke-width": 1.8, "stroke-linecap": "round" }, g);
    } else {
      svg("circle", { cx, cy, r: 6, fill: colour, stroke: "var(--surface)", "stroke-width": 1.5, class: "mk" }, g);
    }
  }

  function glyph(p, view) {
    const s = svg("svg", { viewBox: "0 0 24 24", width: 22, height: 22, "aria-hidden": "true", class: "key" });
    marker(s, p, 12, 12, view);
    return s;
  }

  function tipLines(p, board, decimals, page, tierLines, beaten) {
    const lines = [[`${p.name} ${p.effort}`, "tip-head"],
                   [`${fmtScore(p.score, board.unit, decimals)} for ${fmtMoney(p.cost)}`, ""]];
    if (p.lanes.length) {
      for (const lane of p.lanes) {
        const here = page.tiers[lane.name];
        lines.push([`${lane.name}: ${here === OFF ? "off here" : here ? `tier ${here} here` : "no tier here yet"}, `
                    + `${lane.tier ?? "—"} in the catalog`, "mono"]);
      }
      for (const lane of p.lanes) {
        if (beaten && beaten[lane.name]) lines.push([`beaten by ${beaten[lane.name]} on this board`, "beaten"]);
      }
      const band = bandTier(p.score, tierLines);
      if (band) lines.push([`the band proposes tier ${band}`, "quiet"]);
    } else if (p.ours) {
      lines.push(["no lane runs this effort", "quiet"]);
    } else {
      lines.push(["not in your catalog", "quiet"]);
    }
    // each Lane's own verdict: a point two harnesses share can keep one Lane
    // and propose the other off (bench_page._annotate)
    for (const lane of p.lanes) {
      if (lane.off) lines.push([`pre-screen proposes ${lane.name} off: ${lane.off}`, "off"]);
    }
    if (p.weak) lines.push([`weak provenance: ${p.provenance}`, "flag"]);
    if (p.published && p.published !== p.name) lines.push([`published as ${p.published}`, "quiet"]);
    return lines;
  }

  // Four boxes, one per tier, and off beside them, at most one pressed: the
  // review page's marker, on the page, with the carry decision after it.
  function tierBoxes(parent, names, page, size) {
    const boxes = el("span", { class: "boxes", role: "group", "aria-label": "Tier or off" }, null, parent);
    const current = page.tiers[names[0]] || null;
    for (const t of TIERS.concat([OFF])) {
      const b = el("button", { type: "button", class: t === OFF ? "box off-box" : "box", "aria-pressed": String(current === t),
                               "aria-label": t === OFF ? "off" : `tier ${t}` }, String(t), boxes);
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        page.setTier(names, current === t ? null : t);
      });
    }
    return boxes;
  }

  function makePanel(data, host, index, boardId, onRemove, everyPanel, page) {
    const boards = new Map(data.boards.map((b) => [b.id, b]));
    const st = { board: boardId, frontier: "lanes", labels: "lanes", lines: true,
                 hiddenModels: new Set(), hiddenHarness: new Set(), hiddenEfforts: new Set(),
                 zoom: null, pinned: null, filter: "" };
    const root = el("section", { class: "plot", "aria-label": "Score against cost plot" }, null, host);
    let last = null, pickerOpen = false;
    let H = 500;

    // head: which board, what its dollar is, and the sentence it says
    const head = el("div", { class: "plot-head" }, null, root);
    const pickLabel = el("label", { class: "pick" }, null, head);
    el("span", {}, "Benchmark", pickLabel);
    const select = el("select", {}, null, pickLabel);
    const bySource = new Map();
    for (const b of data.boards) {
      if (!bySource.has(b.source)) bySource.set(b.source, []);
      bySource.get(b.source).push(b);
    }
    for (const [source, list] of bySource) {
      const group = el("optgroup", { label: `${source}, ${list[0].basis}` }, null, select);
      for (const b of list) {
        el("option", { value: b.id }, b.benchmark + (b.composite ? " (composite)" : ""), group);
      }
    }
    const remove = el("button", { type: "button", class: "quiet-button" }, "Remove this plot", head);
    remove.addEventListener("click", () => onRemove(panel));
    const meta = el("p", { class: "meta" }, null, root);
    // what the chosen board measures, quoted from its source; redrawn with the board
    const about = el("div", { class: "about" }, null, root);
    const finding = el("p", { class: "finding" }, null, root);

    const body = el("div", { class: "plot-body" }, null, root);
    const wrap = el("div", { class: "chart" }, null, body);
    const canvas = el("div", { class: "plot-canvas" }, null, wrap);
    const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" }, canvas);
    const tip = el("div", { class: "tip", role: "status" }, null, wrap);
    tip.hidden = true;
    const picker = el("div", { class: "picker" }, null, wrap);
    picker.hidden = true;
    // Always on screen, so the way back from a zoom never has to be found. It
    // sits under the plot, not over it, where it would cover the top-right labels.
    const hint = el("div", { class: "hint" }, null, wrap);
    const reset = el("button", { type: "button", class: "reset" }, "Reset zoom", hint);
    reset.addEventListener("click", () => { st.zoom = null; page.clearFocus(); draw(); });
    el("span", {}, "Scroll over the plot to zoom about the pointer, or drag across it to zoom to a box; "
      + "once zoomed, a drag pans. Click a dot, then press 1 to 4 for its tier. Drag a tier line to move it.", hint);
    const legend = el("div", { class: "plot-legend" }, null, root);
    const table = el("div", { class: "frontier-table" }, null, root);

    // the rail: every setting for this one plot
    const rail = el("form", { class: "rail", "aria-label": "Plot settings" }, null, body);
    rail.addEventListener("submit", (e) => e.preventDefault());
    function radios(title, key, options) {
      const fs = el("fieldset", {}, null, rail);
      el("legend", {}, title, fs);
      const row = el("div", { class: "radios" }, null, fs);
      for (const [value, text] of options) {
        const lab = el("label", {}, null, row);
        const input = el("input", { type: "radio", name: `${key}-${index}`, value }, null, lab);
        input.checked = st[key] === value;
        input.addEventListener("change", () => { st[key] = value; draw(); });
        lab.appendChild(document.createTextNode(text));
      }
      return fs;
    }
    radios("Frontier of", "frontier", [["lanes", "your lanes"], ["shown", "every point shown"], ["off", "none"]]);
    radios("Labels on", "labels", [["frontier", "the frontier"], ["lanes", "the frontier and your lanes"],
                                   ["all", "every point"], ["none", "nothing"]]);
    const linesLabel = el("label", { class: "check" }, null, rail);
    const linesBox = el("input", { type: "checkbox" }, null, linesLabel);
    linesBox.checked = st.lines;
    linesBox.addEventListener("change", () => { st.lines = linesBox.checked; draw(); });
    linesLabel.appendChild(document.createTextNode("Join each model's efforts"));

    // Each benchmark has its own score scale and thresholds.
    const tiersFs = el("fieldset", {}, null, rail);
    el("legend", {}, "Tier lines", tiersFs);
    const tierLinesLabel = el("label", { class: "check" }, null, tiersFs);
    const tierLinesBox = el("input", { type: "checkbox" }, null, tierLinesLabel);
    tierLinesLabel.appendChild(document.createTextNode("Draw the three lines on this benchmark's score axis"));
    tierLinesBox.addEventListener("change", () => {
      const board = boards.get(st.board);
      if (tierLinesBox.checked) {
        if (!page.lines[boardKey(board)]) {
          const scores = board.points.filter((p) => isShown(p, st) && p.lanes.length).map((p) => p.score);
          const lines = defaultLines(scores.length ? scores : board.points.filter((p) => isShown(p, st)).map((p) => p.score));
          if (lines) page.lines[boardKey(board)] = lines;
        }
      } else {
        delete page.lines[boardKey(board)];
      }
      page.save();
      page.redraw();
    });
    const bandsButton = el("button", { type: "button", class: "quiet-button bands-button" },
                           "Give every lane on this plot its band's tier", tiersFs);
    bandsButton.addEventListener("click", () => {
      const board = boards.get(st.board);
      const lines = page.lines[boardKey(board)];
      if (!lines) return;
      applyBands(board, lines, data.lanes, page.tiers, page.manual);
      page.save();
      page.redraw();
    });

    function chips(title, values, hidden, words) {
      const fs = el("fieldset", {}, null, rail);
      el("legend", {}, title, fs);
      const row = el("div", { class: "chips" }, null, fs);
      const buttons = [];
      for (const v of values) {
        const b = el("button", { type: "button", class: "chip", "data-value": v }, words ? words(v) : v, row);
        b.addEventListener("click", () => {
          if (hidden.has(v)) hidden.delete(v); else hidden.add(v);
          draw();
        });
        buttons.push(b);
      }
      return () => buttons.forEach((b) => b.setAttribute("aria-pressed", String(!hidden.has(b.dataset.value))));
    }
    const syncHarness = chips("Harness", data.harnesses.concat([NO_HARNESS]), st.hiddenHarness,
                              (v) => (v === NO_HARNESS ? "not in catalog" : v));
    const syncEfforts = chips("Effort", data.efforts, st.hiddenEfforts);

    const models = el("fieldset", { class: "models" }, null, rail);
    el("legend", {}, "Models", models);
    const modelTools = el("div", { class: "model-tools" }, null, models);
    const filter = el("input", { type: "search", placeholder: "Filter by name", "aria-label": "Filter models by name" },
                      null, modelTools);
    filter.addEventListener("input", () => { st.filter = filter.value.toLowerCase(); fillModels(); });
    const bulk = el("div", { class: "bulk" }, null, models);
    for (const [text, how] of [["All", "all"], ["Your catalog", "ours"], ["None", "none"]]) {
      const b = el("button", { type: "button", class: "quiet-button" }, text, bulk);
      b.addEventListener("click", () => {
        for (const p of boards.get(st.board).points) {
          const hide = how === "none" || (how === "ours" && !p.ours);
          if (hide) st.hiddenModels.add(p.model); else st.hiddenModels.delete(p.model);
        }
        draw();
      });
    }
    const modelList = el("div", { class: "model-list" }, null, models);
    const copy = el("button", { type: "button", class: "quiet-button wide" }, "Use these settings on every plot", rail);
    copy.addEventListener("click", () => everyPanel((other) => other !== panel && other.adopt(st)));

    function modelsOfBoard(board) {
      const seen = new Map();
      for (const p of board.points) {
        const m = seen.get(p.model) || { model: p.model, name: p.name, ours: p.ours, harness: harnessKeys(p)[0], best: -Infinity };
        if (p.score !== null && p.score > m.best) m.best = p.score;
        seen.set(p.model, m);
      }
      return [...seen.values()].sort((a, b) => (b.ours - a.ours) || (b.best - a.best) || a.name.localeCompare(b.name));
    }

    function fillModels() {
      modelList.textContent = "";
      const all = modelsOfBoard(boards.get(st.board));
      let group = null;
      for (const m of all) {
        if (st.filter && !m.name.toLowerCase().includes(st.filter)) continue;
        const heading = m.ours ? "In your catalog" : "Not in your catalog";
        if (heading !== group) {
          el("p", { class: "group" }, heading, modelList);
          group = heading;
        }
        const lab = el("label", { class: "model-row", "data-m": m.model }, null, modelList);
        const box = el("input", { type: "checkbox" }, null, lab);
        box.checked = !st.hiddenModels.has(m.model);
        box.addEventListener("change", () => {
          if (box.checked) st.hiddenModels.delete(m.model); else st.hiddenModels.add(m.model);
          draw();
        });
        el("span", { class: m.ours ? "nm mono" : "nm" }, m.name, lab);
        if (m.ours) el("span", { class: "tag" }, m.harness, lab);
        lab.addEventListener("mouseenter", () => focus(m.model));
        lab.addEventListener("mouseleave", () => focus(null));
      }
    }

    function focus(model) {
      const hot = model || st.pinned;
      chart.classList.toggle("focusing", !!hot);
      for (const node of chart.querySelectorAll("[data-m]")) {
        node.classList.toggle("hot", node.getAttribute("data-m") === hot);
      }
      for (const row of table.querySelectorAll("tr[data-m]")) {
        row.classList.toggle("hot", row.getAttribute("data-m") === hot);
      }
    }

    function drawLegend(board) {
      legend.textContent = "";
      const items = [];
      const sample = (kind, extra) => Object.assign({ kind, weak: false, harness: [], meter: [], tier: null, lanes: [] }, extra);
      const view = { tierView: page.tierView, tier: page.tierView ? 2 : null };
      const one = data.harnesses.length ? [data.harnesses[0]] : [];
      const meters = data.meters || [];
      for (const m of meters) items.push([sample("lane", { harness: [m.harness], meter: [m.name] }), `a ${m.name} lane`, view]);
      if (!meters.length) for (const h of data.harnesses) items.push([sample("lane", { harness: [h] }), `a ${h} lane`, view]);
      if (page.tierView) {
        items.push([sample("lane", { harness: one }), "the digit is the tier drawn here", view],
                   [sample("lane", { harness: one }), "hollow: no tier here yet", { tierView: true, tier: null }],
                   [sample("lane", { harness: one }), "struck: off here", { tierView: true, tier: null, off: true }]);
      }
      items.push([sample("lane_off", { harness: one }), "a lane the pre-screen proposes off", view],
                 [sample("own_other", { harness: one }), "your model at an effort no lane runs", view],
                 [sample("comparator"), "not in your catalog", view],
                 [sample("own_other", { weak: true, harness: one }), "weak provenance", view]);
      for (const [p, words, v] of items) {
        const item = el("span", { class: "item" }, null, legend);
        item.appendChild(glyph(p, v));
        el("span", {}, words, item);
      }
      if (st.frontier !== "off") {
        const item = el("span", { class: "item" }, null, legend);
        const s = svg("svg", { viewBox: "0 0 22 16", width: 22, height: 16, "aria-hidden": "true", class: "key" }, item);
        svg("rect", { x: 0, y: 8, width: 22, height: 8, fill: "var(--frontier)", opacity: 0.12 }, s);
        svg("path", { d: "M1,12 H8 V5 H21", fill: "none", stroke: "var(--frontier)", "stroke-width": 2.2 }, s);
        el("span", {}, st.frontier === "lanes" ? "frontier of your lanes; the shade under it is beaten"
                                               : "frontier of every point shown; the shade under it is beaten", item);
      }
      if (page.lines[boardKey(board)]) {
        el("span", { class: "item note" }, "Dragging a score line assigns bands. Hand-set tiers stay until cleared.", legend);
      }
      if (board.composite) el("span", { class: "item note" }, "A composite index: shown, never counted by the pre-screen.", legend);
    }

    function drawTable(board, lay, decimals) {
      table.textContent = "";
      if (st.frontier === "off") return;
      const fr = lay.frontier;
      const title = st.frontier === "lanes" ? "Your lanes on the frontier" : "Every point shown on the frontier";
      el("h3", {}, title, table);
      el("p", { class: "quiet" }, fr.length
        ? "Cheapest first. Each row scores more than every row above it; the step column is what the extra money buys."
        : "No point shown is eligible. Turn on more models, harnesses or efforts.", table);
      if (!fr.length) return;
      const scroll = el("div", { class: "scroll" }, null, table);
      const t = el("table", { class: "frontier" }, null, scroll);
      const hr = el("tr", {}, null, el("thead", {}, null, t));
      for (const [h, num] of [["Cost", 1], ["Score", 1], ["Model", 0], ["Effort", 0], ["Lane", 0], ["Tier here", 1], ["Step", 1]]) {
        el("th", num ? { class: "num" } : {}, h, hr);
      }
      const tb = el("tbody", {}, null, t);
      let prev = null;
      for (const p of fr) {
        const tr = el("tr", { "data-m": p.model, class: p.kind === "lane_off" ? "off-row" : "" }, null, tb);
        el("td", { class: "num" }, fmtMoney(p.cost), tr);
        el("td", { class: "num" }, fmtScore(p.score, board.unit, decimals), tr);
        el("td", { class: p.ours ? "mono" : "" }, p.name, tr);
        el("td", {}, p.effort, tr);
        const lane = el("td", {}, null, tr);
        if (p.lanes.length) {
          el("span", { class: "mono" }, p.lanes.map((l) => l.name).join(", "), lane);
          for (const l of p.lanes) {
            const who = p.lanes.length > 1 ? `${l.name} ` : "";
            if (l.off) el("span", { class: "sub off" }, `${who}proposed off: ${l.off}`, lane);
          }
        } else {
          el("span", { class: "quiet" }, p.ours ? "no lane at this effort" : "not in catalog", lane);
        }
        el("td", { class: "num" }, p.lanes.length ? p.lanes.map((l) => page.tiers[l.name] ?? "—").join(", ") : "", tr);
        el("td", { class: "num quiet" }, prev
          ? `+${fmtScore(p.score - prev.score, board.unit, decimals)} for +${fmtMoney(p.cost - prev.cost)}` : "", tr);
        tr.addEventListener("mouseenter", () => focus(p.model));
        tr.addEventListener("mouseleave", () => focus(null));
        prev = p;
      }
    }

    function selectedKey() {
      return page.selected ? page.selected.key : null;
    }

    function pointKey(p) {
      return `${p.model} ${p.effort}`;
    }

    function drawChart(board, lay, decimals) {
      chart.textContent = "";
      chart.setAttribute("aria-label", `Score against ${board.basis} on ${board.benchmark} from ${board.source}. `
        + `${lay.shown.length} points shown. ${board.finding} The frontier table follows.`);
      svg("rect", { x: 0, y: 0, width: W, height: H, fill: "var(--surface)" }, chart);
      if (!lay.plot) {
        const t = svg("text", { x: W / 2, y: H / 2, "text-anchor": "middle", class: "empty" }, chart);
        t.textContent = "Nothing shown. Turn on a model, a harness or an effort.";
        return;
      }
      const clipId = `plot-clip-${index}`;
      const clip = svg("clipPath", { id: clipId }, svg("defs", {}, chart));
      svg("rect", { x: PAD.l, y: PAD.t, width: W - PAD.l - PAD.r, height: H - PAD.t - PAD.b }, clip);
      for (const t of lay.yTicks) {
        svg("line", { x1: PAD.l, x2: W - PAD.r, y1: t.y, y2: t.y, class: "grid" }, chart);
        svg("text", { x: PAD.l - 8, y: t.y + 3.5, "text-anchor": "end", class: "tick" }, chart).textContent = t.text;
      }
      for (const t of lay.xTicks) {
        svg("line", { x1: t.x, x2: t.x, y1: PAD.t, y2: H - PAD.b, class: "grid" }, chart);
        svg("text", { x: t.x, y: H - PAD.b + 17, "text-anchor": "middle", class: "tick" }, chart).textContent = t.text;
      }
      svg("line", { x1: PAD.l, x2: W - PAD.r, y1: H - PAD.b, y2: H - PAD.b, class: "axis" }, chart);
      svg("text", { x: PAD.l + (W - PAD.l - PAD.r) / 2, y: H - 10, "text-anchor": "middle", class: "axis-title" }, chart)
        .textContent = `${board.basis}, dollars, log scale. Left is cheaper.`;
      svg("text", { x: 14, y: PAD.t + (H - PAD.t - PAD.b) / 2, "text-anchor": "middle", class: "axis-title",
                    transform: `rotate(-90 14 ${PAD.t + (H - PAD.t - PAD.b) / 2})` }, chart)
        .textContent = `score${board.unit === "%" ? ", percent" : ""}. Up is better.`;
      const clipped = svg("g", { "clip-path": `url(#${clipId})` }, chart);
      if (lay.wash) svg("path", { d: lay.wash, class: "wash" }, clipped);
      for (const s of lay.sweeps) {
        svg("polyline", { points: s.points, class: s.ours ? "sweep ours" : "sweep", "data-m": s.model }, clipped);
      }
      if (lay.steps) svg("path", { d: lay.steps, class: "steps" }, clipped);
      for (const b of lay.bands) {
        svg("text", { x: W - PAD.r - 5, y: (b.y0 + b.y1) / 2, "text-anchor": "end", class: "band-name" }, chart)
          .textContent = `tier ${b.tier}`;
      }
      for (const l of lay.lines) {
        if (!l.inside) continue;
        const g = svg("g", { class: "tier-handle", "data-line": l.index }, chart);
        svg("line", { x1: PAD.l, x2: W - PAD.r, y1: l.y, y2: l.y, class: "tier-grip" }, g);
        svg("line", { x1: PAD.l, x2: W - PAD.r, y1: l.y, y2: l.y, class: "tier-line" }, g);
        g.addEventListener("pointerdown", (e) => {
          if (e.button !== 0) return;
          e.stopPropagation();
          e.preventDefault();
          lineDrag = { index: l.index, key: boardKey(board) };
          g.querySelector(".tier-line").classList.add("held");
          try { chart.setPointerCapture(e.pointerId); } catch (_err) { /* still drags inside the plot */ }
        });
      }
      const selected = selectedKey();
      for (const q of lay.points) {
        const g = svg("g", { class: "pt" + (q.dim ? " dim" : ""), "data-m": q.p.model }, chart);
        if (q.frontier) svg("circle", { cx: q.x, cy: q.y, r: 10, class: "halo" }, g);
        if (selected && pointKey(q.p) === selected) svg("circle", { cx: q.x, cy: q.y, r: 14, class: "sel" }, g);
        svg("circle", { cx: q.x, cy: q.y, r: 11, fill: "transparent", class: "hit" }, g);
        marker(g, q.p, q.x, q.y, { tierView: page.tierView, tier: q.tier, off: q.off });
        g.addEventListener("pointerenter", () => showTip(q, board, decimals));
        g.addEventListener("pointerleave", () => { tip.hidden = true; focus(null); });
        g.addEventListener("pointerdown", (e) => { if (e.button === 0) downOnPoint = q; });
      }
      for (const l of lay.labels) {
        const cls = "label" + (l.frontier ? " fr" : "") + (l.off ? " off" : "") + (l.ours ? "" : " cmp") + (l.dim ? " dim" : "");
        svg("text", { x: l.x, y: l.y, "text-anchor": l.anchor, class: cls, "data-m": l.model }, chart).textContent = l.text;
      }
      band = svg("rect", { class: "band", x: 0, y: 0, width: 0, height: 0 }, chart);
      band.style.display = "none";
    }

    function drawAbout(board) {
      about.textContent = "";
      const a = board.about;
      if (!a) {
        el("p", { class: "cite" }, board.aboutMissing, about);
        return;
      }
      el("p", { class: "measures" }, a.measures, about);
      const dl = el("dl", {}, null, about);
      for (const [term, value] of [["Tasks", a.tasks], ["Score", a.score], ["Number shown", a.scale],
                                   ["Cost", a.cost], ["Speaks to", a.speaks_to]]) {
        if (!value) continue;
        el("dt", {}, term, dl);
        el("dd", {}, value, dl);
      }
      const cite = el("p", { class: "cite" }, "Quoted from ", about);
      el("a", { href: a.url }, a.url, cite);
      cite.appendChild(document.createTextNode(`, fetched ${a.fetched}. Number shown, cost and speaks to `
        + "are the wizard's reading, not the source's words."));
    }

    function placeNear(box, q) {
      const scale = chart.clientWidth / W;
      const left = q.x * scale, top = q.y * scale;
      const bw = box.offsetWidth, wrapW = wrap.clientWidth;
      box.style.left = `${left + 14 + bw > wrapW ? left - 14 - bw : left + 14}px`;
      box.style.top = `${Math.max(4, top - 12)}px`;
    }

    function showTip(q, board, decimals) {
      if (pickerOpen && selectedKey() === pointKey(q.p)) return;
      tip.textContent = "";
      const beaten = beatenByLane(board, carriedNames(data.lanes, page.tiers));
      for (const [text, cls] of tipLines(q.p, board, decimals, page, page.lines[boardKey(board)], beaten)) {
        el("div", cls ? { class: cls } : {}, text, tip);
      }
      tip.hidden = false;
      placeNear(tip, q);
      focus(q.p.model);
    }

    // The picker beside the selected dot: the lane's name, four boxes and
    // what the band proposes. Digits do the same from the keyboard.
    function drawPicker(board) {
      picker.textContent = "";
      const key = selectedKey();
      const q = key && last && last.points.find((c) => pointKey(c.p) === key);
      if (!pickerOpen || !q || !q.p.lanes.length) {
        picker.hidden = true;
        return;
      }
      el("div", { class: "who" }, q.p.lanes.map((l) => l.name).join(", "), picker);
      const row = el("div", { class: "row" }, null, picker);
      tierBoxes(row, q.p.lanes.map((l) => l.name), page);
      const none = el("button", { type: "button", class: "quiet-button" }, "none", row);
      none.addEventListener("click", (e) => { e.stopPropagation(); page.setTier(q.p.lanes.map((l) => l.name), null); });
      const band = bandTier(q.p.score, page.lines[boardKey(board)]);
      el("p", { class: "quiet" }, band ? `Press 1 to 4, or o for off. The band proposes tier ${band}.`
                                       : "Press 1 to 4, or o for off.", picker);
      picker.hidden = false;
      placeNear(picker, q);
      tip.hidden = true;
    }

    // drag to zoom or pan, click to select a dot, double-click to reset
    let band = null, drag = null, downOnPoint = null, lineDrag = null, frame = null;
    function toSvg(e) {
      const r = chart.getBoundingClientRect(), scale = chart.clientWidth / W;
      return [(e.clientX - r.left) / scale, (e.clientY - r.top) / scale];
    }
    function costAt(x) {
      const { xlo, xhi } = last.domain, p = last.plot;
      const f = (Math.min(Math.max(x, p.x0), p.x1) - p.x0) / (p.x1 - p.x0);
      return Math.pow(10, Math.log10(xlo) + f * (Math.log10(xhi) - Math.log10(xlo)));
    }
    function scoreAt(y) {
      const { ylo, yhi } = last.domain, p = last.plot;
      return ylo + (p.y1 - Math.min(Math.max(y, p.y0), p.y1)) / (p.y1 - p.y0) * (yhi - ylo);
    }
    function soon(fn) {
      if (frame) return;
      frame = requestAnimationFrame(() => { frame = null; fn(); });
    }
    chart.addEventListener("pointerdown", (e) => {
      if (!last || !last.plot || lineDrag) return;
      if (e.button !== 0 && e.button !== 1) return;
      const [x, y] = toSvg(e);
      // a left drag pans once zoomed and boxes a zoom before; the middle
      // button pans either way
      const pan = e.button === 1 || !!st.zoom;
      drag = { x, y, x1: x, y1: y, pan, moved: false, domain: last.domain, plot: last.plot, point: downOnPoint };
      downOnPoint = null;
      if (pan) e.preventDefault();
      try {
        chart.setPointerCapture(e.pointerId);
      } catch (_err) {
        // a pointer the browser no longer tracks; the drag still works inside the plot
      }
    });
    chart.addEventListener("mousedown", (e) => { if (e.button === 1) e.preventDefault(); });
    chart.addEventListener("auxclick", (e) => { if (e.button === 1) e.preventDefault(); });
    chart.addEventListener("pointermove", (e) => {
      if (lineDrag) {
        if (!last || !last.plot) return;
        const [, y] = toSvg(e);
        const lines = page.lines[lineDrag.key];
        if (!lines) return;
        let score = scoreAt(y);
        const i = lineDrag.index;
        if (i > 0) score = Math.max(score, lines[i - 1] + (last.domain.yhi - last.domain.ylo) * 0.001);
        if (i < 2) score = Math.min(score, lines[i + 1] - (last.domain.yhi - last.domain.ylo) * 0.001);
        lines[i] = score;
        applyBands(boards.get(st.board), lines, data.lanes, page.tiers, page.manual);
        soon(() => page.redraw());
        return;
      }
      if (!drag) return;
      const [x, y] = toSvg(e);
      const dx = x - drag.x1, dy = y - drag.y1;
      [drag.x1, drag.y1] = [x, y];
      if (!drag.moved && (Math.abs(x - drag.x) > 4 || Math.abs(y - drag.y) > 4)) {
        drag.moved = true;
        if (drag.pan) chart.classList.add("panning");
      }
      if (!drag.moved) return;
      if (drag.pan) {
        // from the domain pending, not the one drawn: two moves can land
        // between frames, and the second must not undo the first
        const from = st.zoom ? { xlo: st.zoom.c0, xhi: st.zoom.c1, ylo: st.zoom.s0, yhi: st.zoom.s1 } : last.domain;
        st.zoom = panBy(from, last.plot, dx, dy);
        tip.hidden = true;
        soon(draw);
      } else {
        band.style.display = "";
        band.setAttribute("x", Math.min(drag.x, drag.x1));
        band.setAttribute("y", Math.min(drag.y, drag.y1));
        band.setAttribute("width", Math.abs(drag.x1 - drag.x));
        band.setAttribute("height", Math.abs(drag.y1 - drag.y));
      }
    });
    function endDrag() {
      if (lineDrag) {
        lineDrag = null;
        page.save();
        page.redraw();
        return;
      }
      if (!drag) return;
      const d = drag;
      drag = null;
      chart.classList.remove("panning");
      if (band) band.style.display = "none";
      if (d.moved && !d.pan && Math.abs(d.x1 - d.x) > 10 && Math.abs(d.y1 - d.y) > 10) {
        st.zoom = { c0: costAt(Math.min(d.x, d.x1)), c1: costAt(Math.max(d.x, d.x1)),
                    s0: scoreAt(Math.max(d.y, d.y1)), s1: scoreAt(Math.min(d.y, d.y1)) };
        draw();
        return;
      }
      if (d.moved) {
        if (d.pan) {
          const full = layout(boards.get(st.board), pageState({ zoom: null })).domain;
          if (full && covers(st.zoom, full)) st.zoom = null;
          draw();
        }
        return;
      }
      // a press that did not move is a click: on a dot it selects the dot
      if (d.point && d.point.p.lanes.length) {
        const key = pointKey(d.point.p);
        if (selectedKey() === key && pickerOpen) {
          page.select(null);
        } else {
          pickerOpen = true;
          page.select({ key, lanes: d.point.p.lanes.map((l) => l.name) }, panel);
        }
      } else if (d.point) {
        st.pinned = d.point.p.model !== st.pinned ? d.point.p.model : null;
        focus(null);
      } else {
        page.select(null);
      }
    }
    chart.addEventListener("pointerup", endDrag);
    chart.addEventListener("pointercancel", endDrag);
    chart.addEventListener("dblclick", () => { st.zoom = null; page.clearFocus(); draw(); });
    // The wheel zooms only over the plotting area; over the axes and margins it
    // scrolls the page as usual, so a reader scrolling past a plot is not caught.
    chart.addEventListener("wheel", (e) => {
      if (!last || !last.plot || drag) return;
      const [x, y] = toSvg(e), p = last.plot;
      if (x < p.x0 || x > p.x1 || y < p.y0 || y > p.y1) return;
      e.preventDefault();
      const step = e.deltaY * (e.deltaMode === 1 ? 0.05 : e.deltaMode === 2 ? 1 : 0.0015);
      const next = zoomAbout(last.domain, p, x, y, Math.exp(Math.max(-0.5, Math.min(0.5, step))));
      const full = layout(boards.get(st.board), pageState({ zoom: null })).domain;
      st.zoom = full && covers(next, full) ? null : next;
      draw();
    }, { passive: false });

    // this panel's settings with the page's tiers, lines and focus beside them
    function pageState(extra) {
      const board = boards.get(st.board);
      return Object.assign({}, st, { height: H, tiers: page.tiers, tierLines: page.lines[boardKey(board)] || null,
                                     focusTier: page.focusTier }, extra || {});
    }

    function draw() {
      const board = boards.get(st.board);
      select.value = st.board;
      meta.textContent = "";
      if (board.url) el("a", { href: board.url }, board.source, meta);
      else meta.appendChild(document.createTextNode(board.source));
      meta.appendChild(document.createTextNode(`, ${board.basis}, observed ${board.when}. `
        + `${board.rows} rows, ${board.models} models.`
        + (board.unplotted.length ? ` Not drawn, no usable score or cost: ${board.unplotted.join(", ")}.` : "")));
      drawAbout(board);
      finding.textContent = board.finding;
      const decimals = scoreDecimals(board);
      H = Math.max(PAD.t + PAD.b + 50, chart.clientHeight / (chart.clientWidth || W) * W);
      chart.setAttribute("viewBox", `0 0 ${W} ${H}`);
      last = layout(board, pageState());
      drawChart(board, last, decimals);
      drawLegend(board);
      drawTable(board, last, decimals);
      fillModels();
      syncHarness();
      syncEfforts();
      tierLinesBox.checked = !!page.lines[boardKey(board)];
      bandsButton.disabled = !page.lines[boardKey(board)];
      reset.setAttribute("aria-disabled", String(!st.zoom && !page.focusTier));
      tip.hidden = true;
      drawPicker(board);
      remove.hidden = host.querySelectorAll("section.plot").length < 2;
      focus(null);
      highlightLane();
    }

    select.addEventListener("change", () => {
      st.board = select.value;
      st.zoom = null;
      st.pinned = null;
      draw();
      // the panel's "beaten by" is judged on the boards shown
      if (page.boardChanged) page.boardChanged();
    });

    function highlightLane() {
      chart.querySelectorAll(".lane-highlight").forEach((n) => n.remove());
      const names = page.hovered ? [page.hovered] : (page.selected ? page.selected.lanes : []);
      for (const q of (last ? last.points : [])) {
        if (!q.p.lanes.some((l) => names.includes(l.name))) continue;
        const g = svg("g", { class: "lane-highlight", "pointer-events": "none" }, chart);
        svg("circle", { cx: q.x, cy: q.y, r: 14, class: "sel" }, g);
        const text = names.filter((n) => q.p.lanes.some((l) => l.name === n)).join(", ");
        const x = Math.min(W - PAD.r - text.length * CHAR_PX, Math.max(PAD.l, q.x + 16));
        svg("text", { x, y: Math.max(PAD.t + 14, q.y - 16), class: "label hot" }, g).textContent = text;
      }
    }
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(() => { if (last) draw(); }).observe(canvas);
    }

    const panel = {
      root,
      highlightLane,
      board: () => st.board,
      source: () => boards.get(st.board).source,
      draw,
      // the selection changed elsewhere: this panel's picker closes unless
      // it is the one the click landed on
      selected(owner) {
        pickerOpen = owner === panel && !!page.selected;
        draw();
      },
      // zoom to a tier's band, or back to the full view
      focusTier(tier) {
        st.zoom = tier ? focusDomain(boards.get(st.board), pageState(), tier) : null;
        draw();
      },
      adopt(other) {
        for (const key of ["frontier", "labels", "lines"]) st[key] = other[key];
        for (const key of ["hiddenModels", "hiddenHarness", "hiddenEfforts"]) {
          st[key].clear();
          other[key].forEach((v) => st[key].add(v));
        }
        for (const input of rail.querySelectorAll("input[type=radio]")) {
          input.checked = st[input.name.replace(/-\d+$/, "")] === input.value;
        }
        linesBox.checked = st.lines;
        draw();
      },
    };
    return panel;
  }

  // --- the tier panel beside the plots -------------------------------------------

  function makeTierPanel(data, page, host, sensHost) {
    host.hidden = false;
    const lanes = placeable(data.lanes);
    const meters = (data.meters || []).filter((m) => lanes.some((l) => l.meter === m.name));
    el("h2", {}, "Tiers drawn here", host);
    const note = el("p", { class: "note" }, null, host);
    const counts = el("table", { class: "counts", "aria-label": "Lanes per tier and meter" }, null, host);
    const tools = el("div", { class: "tier-tools" }, null, host);
    const viewButton = el("button", { type: "button", class: "reset", "aria-pressed": "false" }, "Show tiers on the plots", tools);
    viewButton.addEventListener("click", () => {
      page.tierView = !page.tierView;
      page.save();
      page.redraw();
    });
    const copyButton = el("button", { type: "button", class: "reset" }, "Copy as lines", tools);
    // It drops drawn work, so it asks first, once (ticket 36).
    const resetButton = el("button", { type: "button", class: "reset" }, "Reset every tier", tools);
    resetButton.addEventListener("click", () => {
      const drawn = Object.keys(page.tiers).length;
      const asked = typeof window !== "undefined" && window.confirm
        ? window.confirm(drawn
            ? `Clear the ${drawn} tier${drawn === 1 ? "" : "s"} drawn here, and every tier line? `
              + "The catalog's own tiers are not touched."
            : "Clear every tier line drawn here? The catalog's own tiers are not touched.")
        : true;
      if (!asked) return;
      page.resetAll();
      page.redraw();
    });
    const copyBox = el("textarea", { rows: 6, readonly: "", "aria-label": "Decisions as lines, lane then tier or off" }, null, host);
    copyBox.hidden = true;
    const copyNote = el("p", { class: "empty" }, null, host);
    copyNote.hidden = true;
    copyButton.addEventListener("click", () => {
      const text = tierLinesText(lanes, page.tiers);
      copyBox.value = text;
      copyBox.hidden = false;
      copyNote.hidden = false;
      copyBox.focus();
      copyBox.select();
      const lines = text ? text.split("\n") : [];
      const lineCount = lines.length;
      const offCount = lines.filter((line) => line.endsWith(` ${OFF}`)).length;
      const said = (how) => {
        copyNote.textContent = lineCount
          ? `${lineCount} lines, ${lineCount - offCount} with a tier and ${offCount} off, in the review page's order, ${how}. `
            + "On the wizard's review page, press v to apply them; or save them to a file for setup.py --tiers-from."
          : "No lane has a tier or is off yet.";
      };
      if (lineCount && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => said("copied"), () => said("selected: copy them"));
      } else {
        said("selected: copy them");
      }
    });
    const sections = el("div", {}, null, host);

    // One row per meter, one column per tier, best first, the way the boxes
    // run, then off: how many lanes each meter has at each tier, how many are
    // off, and how many are not placed yet. Counts, not judgements.
    function countsTable() {
      counts.textContent = "";
      const hr = el("tr", {}, null, el("thead", {}, null, counts));
      el("th", {}, "", hr);
      for (const tier of TIERS) el("th", { class: "h" }, `T${tier}`, hr);
      el("th", { class: "h" }, "off", hr);
      el("th", { class: "h unset" }, "none", hr);
      el("th", { class: "h" }, "all", hr);
      const tb = el("tbody", {}, null, counts);
      const rows = meters.map((m) => [m.name, lanes.filter((l) => l.meter === m.name)]).concat([["all", lanes]]);
      for (const [label, mine] of rows) {
        const tr = el("tr", { class: label === "all" ? "tot" : "" }, null, tb);
        const th = el("th", {}, null, tr);
        if (label !== "all") el("span", { class: "swatch", style: `background:${meterColour(label)}` }, null, th);
        th.appendChild(document.createTextNode(label));
        for (const tier of TIERS.concat([OFF, null])) {
          const n = mine.filter((l) => (page.tiers[l.name] || null) === tier).length;
          el("td", { class: (n ? "" : "zero") + (tier ? "" : " unset") }, String(n), tr);
        }
        el("td", { class: "tot" }, String(mine.length), tr);
      }
    }

    // {lane: [{by, benchmark}]} over the boards the plots show, each board once
    function beatenOnShown() {
      const carried = carriedNames(data.lanes, page.tiers);
      const out = {};
      for (const board of page.shownBoards ? page.shownBoards() : []) {
        for (const [name, by] of Object.entries(beatenByLane(board, carried))) {
          (out[name] = out[name] || []).push({ by, benchmark: board.benchmark });
        }
      }
      return out;
    }

    function laneRow(lane, parent, beaten) {
      const isOff = page.tiers[lane.name] === OFF;
      const row = el("div", { class: "lane-row" + (isOff ? " is-off" : ""), "data-lane": lane.name }, null, parent);
      tierBoxes(row, [lane.name], page);
      const name = el("button", { type: "button", class: "nm", title: `${lane.model} ${lane.effort}` }, lane.name, row);
      name.addEventListener("click", () => {
        page.select({ key: `${lane.model} ${lane.effort}`, lanes: [lane.name] }, null);
      });
      if (!lane.rows) el("span", { class: "tag" }, "no rows", row);
      // the page places a lane the catalog does not carry (ticket 35), and says
      // so, because a line that carries it is a change the wizard will make
      if (!lane.carried) {
        el("span", { class: "tag", title: "the catalog does not carry this lane; a tier here carries it" },
           "not carried", row);
      }
      if (lane.off) el("span", { class: "tag off", title: lane.off }, "proposed off", row);
      const by = beaten[lane.name];
      if (by) {
        el("span", { class: "tag beaten", title: by.map((b) => `on ${b.benchmark}: beaten by ${b.by}`).join("\n") },
           `beaten by ${[...new Set(by.map((b) => b.by))].join(", ")}`, row);
      }
    }

    function section(group, beaten) {
      const tier = group.tier;
      const sec = el("section", { class: "tier" }, null, sections);
      const h = el("h3", {}, null, sec);
      h.appendChild(document.createTextNode(tier === OFF ? "Off" : tier ? `Tier ${tier}` : "Not placed"));
      el("span", { class: "n" }, `${group.count} lane${group.count === 1 ? "" : "s"}`, h);
      if (TIERS.includes(tier)) {
        const focusButton = el("button", { type: "button", class: "quiet-button focus",
                                           "aria-pressed": String(page.focusTier === tier) }, "Focus", h);
        focusButton.addEventListener("click", () => page.focus(page.focusTier === tier ? null : tier));
        if (page.focusTier === tier) focusButton.textContent = "Focused";
      }
      if (!group.count) {
        el("p", { class: "empty" }, tier === OFF ? "No lane is off. Press off on a lane's line, or click a dot and press o."
          : tier ? "No lane yet. Click a dot and press " + tier + ", or press a box here."
          : "Every lane here has a tier or is off.", sec);
        return;
      }
      for (const m of group.meters) {
        const h4 = el("h4", {}, null, sec);
        el("span", { class: "swatch", style: `background:${meterColour(m.meter)}` }, null, h4);
        h4.appendChild(document.createTextNode(m.meter));
        el("span", { class: "n" }, String(m.lanes.length), h4);
        for (const lane of m.lanes) laneRow(lane, sec, beaten);
      }
    }

    // The sensitivity table under the plots: what each board alone would give.
    function drawSensitivity() {
      if (!sensHost) return;
      sensHost.hidden = false;
      sensHost.textContent = "";
      el("h2", {}, "What each board alone would give", sensHost);
      const s = sensitivity(data.boards, lanes, page.tiers, data.meters);
      if (!s.groups.some((g) => g.count)) {
        el("p", { class: "lede" }, "Give lanes a tier and this table shows, for each board, the tier its "
          + "ranking alone would give each of them in the proportions you chose.", sensHost);
        return;
      }
      const shares = TIERS.map((t) => `${s.counts[t] || 0} on tier ${t}`).join(", ");
      el("p", { class: "lede" }, "Each board ranks the placed lanes it measured by score and cuts them in "
        + `the proportions you gave: ${shares}. A marked cell differs from your tier; a dash is a board `
        + "that did not measure the lane. The last column counts the boards that agree out of the boards "
        + "that measured the lane; a shaded column is a composite index, shown and never counted.", sensHost);
      const scroll = el("div", { class: "scroll" }, null, sensHost);
      const t = el("table", { class: "sens" }, null, scroll);
      const hr = el("tr", {}, null, el("thead", {}, null, t));
      el("th", { class: "lane" }, "Lane", hr);
      el("th", { class: "cell" }, "Yours", hr);
      for (const c of s.columns) {
        const th = el("th", { class: "cell" + (c.composite ? " composite" : ""), title: `${c.benchmark}, ${c.source}` },
                      c.benchmark, hr);
        el("span", { class: "sub" }, c.composite ? `${c.source}, not counted` : c.source, th);
      }
      el("th", { class: "cell" }, "Agree", hr);
      const tb = el("tbody", {}, null, t);
      for (const g of s.groups) {
        if (!g.rows.length) continue;
        const gh = el("th", { colspan: String(s.columns.length + 3) }, `Tier ${g.tier}`, el("tr", { class: "grp" }, null, tb));
        el("span", { class: "n" }, `${g.count} lane${g.count === 1 ? "" : "s"}`, gh);
        for (const r of g.rows) {
          const tr = el("tr", { "data-lane": r.name }, null, tb);
          const td = el("td", { class: "lane" }, null, tr);
          el("span", { class: "swatch", style: `background:${meterColour(r.meter)}` }, null, td);
          td.appendChild(document.createTextNode(r.name));
          el("td", { class: "mine" }, String(r.tier), tr);
          r.cells.forEach((cell, i) => {
            const comp = s.columns[i].composite ? " composite" : "";
            if (!cell) {
              el("td", { class: "cell none" + comp }, "—", tr);
              return;
            }
            const attrs = { class: "cell" + (cell.differs ? " diff" : "") + comp };
            if (cell.differs) attrs.title = `${s.columns[i].benchmark} alone: tier ${cell.tier}; yours: tier ${r.tier}`;
            el("span", {}, String(cell.tier), el("td", attrs, null, tr));
          });
          el("td", { class: "agree" }, r.measured ? `${r.agree}/${r.measured}` : "—", tr);
          tr.addEventListener("mouseenter", () => page.highlight(r.name));
          tr.addEventListener("mouseleave", () => page.highlight(null));
        }
      }
    }

    function draw() {
      note.textContent = page.storage === "unavailable"
        ? "This browser keeps nothing for a file page, so these tiers last until the tab closes. "
          + "The wizard is where tiers are written."
        : "Kept in this browser for this catalog until you paste them into the wizard, which is where "
          + "tiers are written. Counts are per meter, and judge nothing.";
      viewButton.setAttribute("aria-pressed", String(page.tierView));
      countsTable();
      sections.textContent = "";
      const beaten = beatenOnShown();
      for (const group of panelGroups(lanes, page.tiers, data.meters)) section(group, beaten);
      drawSensitivity();
      page.highlight(page.hovered);
      for (const row of sections.querySelectorAll(".lane-row")) {
        row.addEventListener("mouseenter", () => page.highlight(row.getAttribute("data-lane")));
        row.addEventListener("mouseleave", () => page.highlight(null));
      }
    }
    return { draw };
  }

  // --- the views: one tab per kind of job (benchmark-views ticket 05) ----------------

  const VM = { l: 42, r: 92, t: 10, b: 30 };

  function svgText(parent, attrs, text) {
    const node = svg("text", attrs, parent);
    node.textContent = text;
    return node;
  }

  function linearTicks(lo, hi, n) {
    const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((m) => m >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toPrecision(12));
    return out;
  }

  // Dollar ticks between two log10 costs: decades first, then 1-2-5, then
  // finer, until at least three fit.
  function costTicks(l0, l1, n) {
    let out = [];
    for (const ms of [[1], [1, 2, 5], [1, 1.5, 2, 3, 5, 7]]) {
      out = [];
      for (let k = Math.floor(l0); k <= Math.ceil(l1); k++) {
        for (const m of ms) {
          const v = m * Math.pow(10, k), lv = Math.log10(v);
          if (lv >= l0 && lv <= l1) out.push(v);
        }
      }
      if (out.length >= Math.min(3, n)) break;
    }
    if (out.length < 3) out = linearTicks(Math.pow(10, l0), Math.pow(10, l1), n).filter((v) => v > 0);
    return out;
  }

  function fmtCostTick(v) {
    if (v < 1) return "$" + String(+v.toPrecision(2));
    if (v < 1000) return "$" + String(+v.toPrecision(3));
    return "$" + (v / 1000).toPrecision(3).replace(/\.?0+$/, "") + "k";
  }

  function shapeAt(parent, kind, x, y, r, attrs) {
    if (kind === "square") {
      const q = r * 0.86;
      return svg("rect", Object.assign({ x: x - q, y: y - q, width: 2 * q, height: 2 * q, rx: q * 0.25 }, attrs), parent);
    }
    let d = null;
    if (kind === "diamond") { const q = r * 1.22; d = `M${x},${y - q}L${x + q},${y}L${x},${y + q}L${x - q},${y}Z`; }
    if (kind === "triangle") d = `M${x},${y - r * 1.18}L${x + r * 1.1},${y + r * 0.8}L${x - r * 1.1},${y + r * 0.8}Z`;
    if (kind === "down") d = `M${x},${y + r * 1.18}L${x + r * 1.1},${y - r * 0.8}L${x - r * 1.1},${y - r * 0.8}Z`;
    if (d) return svg("path", Object.assign({ d }, attrs), parent);
    return svg("circle", Object.assign({ cx: x, cy: y, r }, attrs), parent);
  }

  // The views' state, drawing and events. `show(id)` draws a view the first
  // time its tab shows (so its plots are laid out at their real width) and
  // every time after; `redraw()` draws the shown one again, when the page's
  // tiers change. Null when no view has a board on this page.
  function makeViews(data, page) {
    const byId = new Map(data.boards.map((b) => [b.id, b]));
    const views = (data.views || []).map((v) => Object.assign({}, v, { boards: v.boards.filter((id) => byId.has(id)) }))
      .filter((v) => v.boards.length);
    if (!views.length) return null;
    const { order: HS, list: SERIES } = viewSeries(data.lanes);
    const GROUPS = new Set(SERIES.map((s) => s.group));
    const EFF = (data.efforts || []).slice().sort((a, b) => effortIndex(a) - effortIndex(b));
    const index = new Map();
    const boardOf = (id) => {
      if (!index.has(id)) index.set(id, indexBoard(byId.get(id)));
      return index.get(id);
    };
    const st = { view: null, sel: new Set(), hide: new Set(), eff: new Set(), ref: new Set(), ctx: true,
                 wide: null, sort: null, hover: null, refOpen: false };
    let shown = [];
    let carried = carriedNames(data.lanes, page.tiers);

    // #tab=coding&m=<group>,<group>&eff=high,max&ref=<name>&zoom=<board>:x0,x1,y0,y1
    for (const part of (location.hash || "").replace(/^#/, "").split("&")) {
      const eq = part.indexOf("=");
      if (eq < 0) continue;
      const key = part.slice(0, eq), list = decodeURIComponent(part.slice(eq + 1)).split(",").filter(Boolean);
      if (key === "m") st.sel = new Set(list);
      else if (key === "eff") st.eff = new Set(list);
      else if (key === "ref") st.ref = new Set(list);
      else if (key === "zoom" && list.length) {
        const [id, q] = list.join(",").split(":");
        const nums = (q || "").split(",").map(Number);
        if (byId.has(id) && nums.length === 4 && nums.every(Number.isFinite)) boardOf(id).view = { x0: nums[0], x1: nums[1], y0: nums[2], y1: nums[3] };
      }
    }

    const effOk = (e) => !st.eff.size || st.eff.has(e);
    const nameOf = (s) => s.label + (s.primary ? "" : ` · ${s.harness}`);
    const isCarried = (s, e) => { const l = s.lanes.get(e); return !!(l && carried.has(l.name)); };
    const ownPoints = (x, s) => EFF.map((e) => x.at.get(`${s.group}|${e}`))
      .filter((p) => p && (s.primary || s.lanes.has(p.effort)));
    const fmtViewScore = (x, v) => (x.frac ? (100 * v).toFixed(1) + "%" : v.toFixed(1) + (x.board.unit === "%" ? "%" : ""));
    const fmtShort = (x, v) => (x.frac ? String(Math.round(100 * v)) : ((x.thi - x.tlo) < 10 ? v.toFixed(1) : String(Math.round(v))));
    const fmtTimes = (v) => (v < 1 ? v.toFixed(2) : v.toFixed(1)) + "×";
    const bodyOf = (id) => [...document.querySelectorAll("[data-view-body]")].find((n) => n.dataset.viewBody === id);

    const tip = el("div", { class: "v-tip" }, null, document.body);
    tip.hidden = true;
    function placeTip(e) {
      tip.hidden = false;
      tip.style.left = Math.max(8, Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8)) + "px";
      tip.style.top = Math.max(8, Math.min(e.clientY + 14, window.innerHeight - tip.offsetHeight - 8)) + "px";
    }
    const hideTip = () => { tip.hidden = true; };
    function tipLine(text, cls) {
      const line = el("div", cls ? { class: cls } : {}, null, tip);
      if (text) line.textContent = text;
      return line;
    }

    // with Models picked, a plot opens fitted to them (and to any reference
    // Model drawn); Reset and a double-click return there
    function fitView(x) {
      if (!st.sel.size) return Object.assign({}, x.home);
      const pts = [];
      for (const s of SERIES) {
        if (!st.sel.has(s.group) || st.hide.has(s.harness)) continue;
        for (const p of ownPoints(x, s)) if (p.cost > 0 && effOk(p.effort)) pts.push(p);
      }
      for (const p of x.pts) if (p.ref && st.ref.has(p.ref) && effOk(p.effort)) pts.push(p);
      if (!pts.length) return Object.assign({}, x.home);
      const h = x.home, lx = pts.map((p) => Math.log10(p.cost)), ys = pts.map((p) => p.score);
      const px = Math.max((Math.max(...lx) - Math.min(...lx)) * 0.12, 0.18);
      const py = Math.max((Math.max(...ys) - Math.min(...ys)) * 0.14, (h.y1 - h.y0) * 0.04);
      return { x0: Math.max(h.x0, Math.min(...lx) - px), x1: Math.min(h.x1, Math.max(...lx) + px),
               y0: Math.max(h.y0, Math.min(...ys) - py), y1: Math.min(h.y1, Math.max(...ys) + py) };
    }

    function drawPlot(x) {
      const box = x.box;
      box.textContent = "";
      if (!x.home) {
        el("p", { class: "aside" }, "No row on this board has both a score and a cost, so there is nothing to plot.", box);
        return;
      }
      const v = x.view, h = x.home;
      const W0 = Math.max(300, Math.round(box.clientWidth)), H0 = Math.round(Math.min(460, Math.max(280, W0 * 0.62)));
      const iw = W0 - VM.l - VM.r, ih = H0 - VM.t - VM.b;
      const X = (c) => VM.l + (Math.log10(c) - v.x0) / (v.x1 - v.x0) * iw;
      const Y = (s) => VM.t + (v.y1 - s) / (v.y1 - v.y0) * ih;
      // how far in the plot is zoomed: marks and lines thin as it grows
      const k = Math.sqrt(((h.x1 - h.x0) / (v.x1 - v.x0)) * ((h.y1 - h.y0) / (v.y1 - v.y0)));
      const R = Math.max(2.4, 5.2 * Math.pow(k, -0.32)), LW = Math.max(0.9, 1.7 * Math.pow(k, -0.25));
      const inView = (px, py) => px >= VM.l - 2 && px <= VM.l + iw + 2 && py >= VM.t - 2 && py <= VM.t + ih + 2;
      const root = svg("svg", { width: W0, height: H0, viewBox: `0 0 ${W0} ${H0}`, role: "img",
                                "aria-label": `${x.board.benchmark}: score against cost` }, box);
      const clipId = `vc-${st.view}-${x.board.id}`;
      svg("rect", { x: VM.l, y: VM.t - 2, width: iw + 4, height: ih + 4 }, svg("clipPath", { id: clipId }, svg("defs", {}, root)));
      for (const t of linearTicks(v.y0, v.y1, Math.max(3, Math.round(ih / 70)))) {
        svg("line", { class: t === 0 ? "v-zl" : "v-gl", x1: VM.l, x2: VM.l + iw, y1: Y(t), y2: Y(t) }, root);
        svgText(root, { x: VM.l - 6, y: Y(t) + 3.5, "text-anchor": "end" }, x.frac ? String(+(t * 100).toPrecision(3)) : String(t));
      }
      for (const t of costTicks(v.x0, v.x1, Math.max(3, Math.round(iw / 110)))) {
        svgText(root, { x: X(t), y: VM.t + ih + 16, "text-anchor": "middle" }, fmtCostTick(t));
      }
      svgText(root, { x: VM.l + iw, y: H0 - 2, "text-anchor": "end" }, `${x.board.basis || "cost"} →`);
      const clip = svg("g", { "clip-path": `url(#${clipId})` }, root);
      const outside = svg("g", {}, root);
      x.overlay = svg("g", {}, root);
      // the frontier: a soft band behind everything, and rings on its points
      if (x.front.length) {
        let d = `M${X(x.front[0].cost)},${Y(x.front[0].score)}`;
        for (const p of x.front.slice(1)) d += `H${X(p.cost)}V${Y(p.score)}`;
        svg("path", { class: "v-frb", "stroke-width": Math.max(4, 7 * Math.pow(k, -0.3)), d: d + `H${VM.l + iw + 40}` }, clip);
      }
      const hits = [], marks = [], ends = [];
      const line = (pts) => "M" + pts.map((p) => `${X(p.cost).toFixed(1)},${Y(p.score).toFixed(1)}`).join("L");
      if (st.ctx) {
        for (const p of x.pts) {
          if (GROUPS.has(p.group) || st.ref.has(p.ref) || !effOk(p.effort)) continue;
          const px = X(p.cost), py = Y(p.score);
          if (!inView(px, py)) continue;
          svg("circle", { class: "v-ctx", cx: px, cy: py, r: Math.max(1.6, R * 0.48) }, clip);
          hits.push({ x: px, y: py, p, s: null });
        }
      }
      for (const key of st.ref) {
        const own = x.pts.filter((p) => p.ref === key)
          .sort((a, c) => (effortIndex(a.effort) - effortIndex(c.effort)) || a.cost - c.cost);
        if (!own.length) continue;
        const g = svg("g", { class: "v-s v-other" }, clip);
        if (own.length > 1) {
          const attrs = { class: "v-ln", "stroke-width": LW, "stroke-dasharray": `${LW * 2} ${LW * 2}`, d: line(own) };
          if (st.eff.size) attrs.opacity = 0.25;
          svg("path", attrs, g);
        }
        let last = null;
        for (const p of own) {
          const px = X(p.cost), py = Y(p.score);
          if (!inView(px, py) || !effOk(p.effort)) continue;
          svg("circle", { class: "v-mk", cx: px, cy: py, r: R * 0.9, "stroke-width": Math.max(1, LW * 0.9), "stroke-dasharray": "2 1.5" }, g);
          hits.push({ x: px, y: py, p, s: null });
          marks.push({ x: px, y: py, r: R, p, s: null, on: true, run: false });
          if (!last || p.cost > last.p.cost) last = { x: px, y: py, p };
        }
        if (last) ends.push({ name: key, x: last.x, y: last.y, on: true });
      }
      for (const s of SERIES) {
        if (st.hide.has(s.harness) || (st.sel.size && !st.sel.has(s.group))) continue;
        const own = ownPoints(x, s).filter((p) => p.cost > 0);
        if (!own.length) continue;
        const on = st.sel.has(s.group);
        const g = svg("g", { class: "v-s" + (on ? " on" : ""), style: `--c:${harnessColour(s.harness)}` }, clip);
        if (own.length > 1) {
          const attrs = { class: "v-ln", "stroke-width": on ? LW * 1.5 : LW, d: line(own) };
          if (!s.primary) attrs["stroke-dasharray"] = `${LW * 3} ${LW * 2.5}`;
          if (st.eff.size) attrs.opacity = 0.2;
          svg("path", attrs, g);
        }
        let last = null;
        for (const p of own) {
          const px = X(p.cost), py = Y(p.score);
          if (!inView(px, py) || !effOk(p.effort)) continue;
          const run = isCarried(s, p.effort), r = s.primary ? R : R * 1.45;
          if (x.onFront.has(p)) svg("circle", { class: "v-frr", cx: px, cy: py, r: r + 2.6, "stroke-width": Math.max(0.8, LW * 0.7) }, g);
          shapeAt(g, s.shape, px, py, r, { class: `v-mk ${run && s.primary ? "run" : "out"}`, "stroke-width": Math.max(1, LW * 0.9) });
          hits.push({ x: px, y: py, p, s });
          marks.push({ x: px, y: py, r, p, s, on, run });
          if (!last || p.cost > last.p.cost) last = { x: px, y: py, p };
        }
        if (last) ends.push({ s, x: last.x, y: last.y, on });
      }
      // the names at the right edge, kept apart, then effort labels where they fit
      const boxes = marks.map((m) => ({ x: m.x - m.r, y: m.y - m.r, w: 2 * m.r, h: 2 * m.r }));
      const free = (b) => !boxes.some((o) => b.x < o.x + o.w && o.x < b.x + b.w && b.y < o.y + o.h && o.y < b.y + b.h);
      ends.sort((a, c) => a.y - c.y);
      const gap = 12, top = VM.t + 5, bottom = VM.t + ih;
      ends.forEach((e, i) => { e.ly = Math.max(e.y + 3.5, i ? ends[i - 1].ly + gap : top); });
      for (let i = ends.length - 1; i >= 0; i--) ends[i].ly = Math.min(ends[i].ly, i === ends.length - 1 ? bottom : ends[i + 1].ly - gap);
      const lx = VM.l + iw + 8;
      const groupFor = (parent, s, on) => (s ? svg("g", { class: "v-s" + (on ? " on" : ""), style: `--c:${harnessColour(s.harness)}` }, parent)
                                             : svg("g", { class: "v-s v-other" }, parent));
      for (const e of ends) {
        const g = groupFor(outside, e.s, e.on);
        svg("line", { class: "v-ld", "stroke-width": 0.7, x1: e.x + 4, y1: e.y, x2: lx - 2, y2: e.ly - 3.5 }, g);
        svgText(g, { class: "v-tl nm", x: lx, y: e.ly }, e.s ? nameOf(e.s) : e.name);
      }
      const all = k > 1.7;
      const ranked = marks.slice().sort((a, c) => (c.on - a.on) || (c.run - a.run) || (c.p.score - a.p.score));
      for (const m of ranked) {
        if (!(m.on || all) || (m.s && !m.s.primary)) continue;
        const t = m.p.effort, w = t.length * 5.8 + 2;
        for (const [dx, dy, a] of [[m.r + 3, -m.r - 1, "start"], [m.r + 3, m.r + 9, "start"], [-m.r - 3, -m.r - 1, "end"],
                                   [-m.r - 3, m.r + 9, "end"], [-w / 2, -m.r - 4, "mid"]]) {
          const x0 = a === "end" ? m.x + dx - w : m.x + dx, b = { x: x0, y: m.y + dy - 9, w, h: 11 };
          if (b.x < VM.l || b.x + b.w > VM.l + iw || b.y < VM.t || !free(b)) continue;
          boxes.push(b);
          svgText(groupFor(clip, m.s, m.on), { class: "v-tl", x: x0, y: m.y + dy }, t);
          break;
        }
      }
      const f = fitView(x);
      const zoomed = Math.abs(f.x0 - v.x0) + Math.abs(f.x1 - v.x1) > 1e-6 || Math.abs(f.y0 - v.y0) + Math.abs(f.y1 - v.y1) > 1e-6;
      x.reset.hidden = !zoomed;
      x.hint.hidden = zoomed;
      Object.assign(x, { hits, X, Y, iw, ih });
      if (st.hover) markHover();
    }

    function toData(x, px, py) {
      const v = x.view;
      return [v.x0 + (px - VM.l) / x.iw * (v.x1 - v.x0), v.y1 - (py - VM.t) / x.ih * (v.y1 - v.y0)];
    }
    function animate(x, to) {
      const from = Object.assign({}, x.view), t0 = performance.now(), still = window.matchMedia
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      cancelAnimationFrame(x.raf);
      const step = (now) => {
        const t = still ? 1 : Math.min(1, (now - t0) / 260), e = 1 - Math.pow(1 - t, 3);
        for (const key of ["x0", "x1", "y0", "y1"]) x.view[key] = from[key] + (to[key] - from[key]) * e;
        drawPlot(x);
        if (t < 1) x.raf = requestAnimationFrame(step);
      };
      x.raf = requestAnimationFrame(step);
    }
    function zoomAt(x, px, py, factor) {
      const [dx, dy] = toData(x, px, py), v = x.view, h = x.home;
      const nv = { x0: dx - (dx - v.x0) * factor, x1: dx + (v.x1 - dx) * factor, y0: dy - (dy - v.y0) * factor, y1: dy + (v.y1 - dy) * factor };
      x.view = nv.x1 - nv.x0 > h.x1 - h.x0 ? Object.assign({}, h) : nv;
      drawPlot(x);
    }
    const local = (node, e) => { const r = node.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    function nearest(x, px, py) {
      let best = null, bd = 16 * 16;
      for (const hit of x.hits || []) {
        const d = (hit.x - px) ** 2 + (hit.y - py) ** 2;
        if (d < bd) { bd = d; best = hit; }
      }
      return best;
    }
    function pointTip(e, x, n) {
      const p = n.p, s = n.s;
      tip.textContent = "";
      const head = tipLine(null, "v-tip-head");
      el("b", {}, fmtViewScore(x, p.score), head);
      head.appendChild(document.createTextNode(` · ${fmtMoney(p.cost)}`));
      const who = tipLine(null);
      el("span", { class: "k", style: `--c:${s ? harnessColour(s.harness) : "var(--refc)"}` }, null, who);
      who.appendChild(document.createTextNode(s ? `${s.label} on ${s.harness} · ${p.effort}` : `${p.published || p.model} · ${p.effort}`));
      const lane = s && s.lanes.get(p.effort);
      const note = !s ? "reference only: no lane runs this model · click to draw it"
        : lane && carried.has(lane.name) ? `you carry ${lane.name}`
        : lane ? `${lane.name}, in the catalog, not carried` : "measured; no lane at this effort";
      tipLine(note + (x.onFront.has(p) ? " · on the frontier" : ""), "quiet");
      placeTip(e);
    }
    function wire(x) {
      const box = x.box;
      let drag = null;
      box.addEventListener("pointerdown", (e) => {
        if (e.button) return;
        box.setPointerCapture(e.pointerId);
        const [px, py] = local(box, e);
        drag = { x: px, y: py, x2: px, y2: py };
      });
      box.addEventListener("pointermove", (e) => {
        const [px, py] = local(box, e);
        if (!x.overlay) return;
        if (drag) {
          drag.x2 = px;
          drag.y2 = py;
          if (Math.abs(px - drag.x) + Math.abs(py - drag.y) > 6) {
            hideTip();
            x.overlay.textContent = "";
            svg("rect", { class: "v-brush", x: Math.min(drag.x, px), y: Math.min(drag.y, py),
                          width: Math.abs(px - drag.x), height: Math.abs(py - drag.y) }, x.overlay);
          }
          return;
        }
        const n = nearest(x, px, py);
        x.overlay.textContent = "";
        if (!n) { hideTip(); return; }
        svg("circle", { class: "v-hov", cx: n.x, cy: n.y, r: 9 }, x.overlay);
        pointTip(e, x, n);
      });
      box.addEventListener("pointerleave", () => {
        if (drag) return;
        hideTip();
        if (x.overlay) x.overlay.textContent = "";
      });
      box.addEventListener("pointerup", (e) => {
        if (!drag || !x.home) { drag = null; return; }
        const d = drag;
        drag = null;
        if (Math.abs(d.x2 - d.x) > 8 && Math.abs(d.y2 - d.y) > 8) {
          const [a0, b0] = toData(x, Math.min(d.x, d.x2), Math.max(d.y, d.y2));
          const [a1, b1] = toData(x, Math.max(d.x, d.x2), Math.min(d.y, d.y2));
          animate(x, { x0: a0, x1: a1, y0: b0, y1: b1 });
          return;
        }
        const n = nearest(x, d.x, d.y);
        if (n && n.s) pick(st.sel, n.s.group, e.shiftKey);
        else if (n && n.p.ref) pick(st.ref, n.p.ref, true);
        else if (!e.shiftKey && st.sel.size) st.sel.clear();
        else return;
        render();
      });
      box.addEventListener("dblclick", () => { if (x.home) animate(x, fitView(x)); });
      box.addEventListener("wheel", (e) => {
        if (!(e.ctrlKey || e.metaKey) || !x.home) return;
        e.preventDefault();
        const [px, py] = local(box, e);
        zoomAt(x, px, py, Math.exp(e.deltaY * 0.01));
      }, { passive: false });
    }

    function chip(parent, text, attrs, on, extra) {
      const b = el("button", Object.assign({ type: "button", class: "v-mc" + (on ? " on" : "") + (extra || ""),
                                             "aria-pressed": String(!!on) }, attrs), null, parent);
      if (text !== null) b.appendChild(document.createTextNode(text));
      return b;
    }
    function seriesGlyph(s, filled) {
      const g = svg("svg", { width: 12, height: 12, viewBox: "0 0 12 12", style: `--c:${harnessColour(s.harness)}`, "aria-hidden": "true" });
      shapeAt(svg("g", { class: "v-s" }, g), s.shape, 6, 6, 4, { class: `v-mk ${filled ? "run" : "out"}`, "stroke-width": 1.4 });
      return g;
    }
    const hasData = (boards, s) => boards.some((x) => ownPoints(x, s).length);

    function drawBar(boards, bar) {
      const r1 = el("div", { class: "v-row" }, null, bar);
      el("span", { class: "lab" }, "Effort", r1);
      chip(r1, "all", { "data-eff": "" }, !st.eff.size);
      for (const e of EFF.filter((e) => boards.some((x) => x.scored.some((p) => p.effort === e)))) {
        chip(r1, e, { "data-eff": e }, st.eff.has(e));
      }
      el("span", { class: "sp" }, null, r1);
      el("span", { class: "how2" }, "click shows one · shift-click adds or removes", r1);
      el("button", { type: "button", class: "ghost", "data-clear": "" }, "Clear filters", r1);
      const r2 = el("div", { class: "v-row v-groups" }, null, bar);
      el("span", { class: "lab" }, "Lanes", r2);
      for (const h of HS) {
        const ss = SERIES.filter((s) => s.harness === h && hasData(boards, s));
        if (!ss.length) continue;
        const off = st.hide.has(h);
        const g = el("span", { class: "v-hg" + (off ? " off" : ""), style: `--c:${harnessColour(h)}` }, null, r2);
        const hh = el("button", { type: "button", class: "v-hh", "data-h": h, "aria-pressed": String(!off),
                                  title: `Show or hide every ${h} lane` }, null, g);
        el("i", {}, null, hh);
        hh.appendChild(document.createTextNode(h));
        for (const s of ss) {
          const b = chip(g, null, { "data-m": s.group }, st.sel.has(s.group), st.sel.size && !st.sel.has(s.group) ? " out" : "");
          b.appendChild(seriesGlyph(s, true));
          b.appendChild(document.createTextNode(s.label));
        }
      }
      const names = [...new Set(boards.flatMap((x) => x.scored.filter((p) => p.ref).map((p) => p.ref)))]
        .sort((a, c) => a.localeCompare(c));
      if (!names.length) return;
      const d = el("details", { class: "v-refs" }, null, bar);
      d.open = st.refOpen || st.ref.size > 0;
      d.addEventListener("toggle", () => { st.refOpen = d.open; });
      const sum = el("summary", {}, null, d);
      el("b", {}, "Reference", sum);
      sum.appendChild(document.createTextNode(` · ${names.length} models with no lane, for comparison only. They never enter the ranking.`));
      const label = el("label", { class: "how2" }, null, sum);
      const box = el("input", { type: "checkbox", "data-ctx": "" }, null, label);
      box.checked = st.ctx;
      label.appendChild(document.createTextNode(" show as grey dots"));
      const list = el("div", { class: "v-rl" }, null, d);
      for (const n of names) el("button", { type: "button", class: "v-rc" + (st.ref.has(n) ? " on" : ""), "data-ref": n,
                                            "aria-pressed": String(st.ref.has(n)) }, n, list);
    }

    function drawCards(view, boards, grid) {
      const sig = [[...st.sel], [...st.ref], [...st.eff], [...st.hide]].map((xs) => xs.join(",")).join("|");
      for (const x of boards) {
        const id = x.board.id;
        const card = el("article", { class: "v-card" + (st.wide === id ? " wide" : "") }, null, grid);
        const head = el("header", {}, null, card);
        const title = el("span", {}, null, head);
        el("h3", {}, x.board.benchmark, title);
        el("span", { class: "v-sub" }, ` ${x.board.source} · ${x.scored.length} rows · ${x.frac || x.board.unit === "%" ? "score %" : "score"}`, title);
        const tools = el("span", { class: "tools" }, null, head);
        x.hint = el("span", { class: "v-hint" }, "drag a box to zoom · double-click resets", tools);
        x.reset = el("button", { type: "button" }, "Reset", tools);
        x.reset.hidden = true;
        const wide = el("button", { type: "button" }, st.wide === id ? "Smaller" : "Expand", tools);
        x.box = el("div", { class: "v-plot" }, null, card);
        if (x.home && x.sig !== sig) {
          if (x.sig !== undefined || st.sel.size || !x.view) x.view = fitView(x);
          x.sig = sig;
        }
        if (x.home && !x.view) x.view = Object.assign({}, x.home);
        x.reset.addEventListener("click", () => animate(x, fitView(x)));
        wide.addEventListener("click", () => { st.wide = st.wide === id ? null : id; render(); });
      }
      for (const x of boards) { drawPlot(x); wire(x); }
    }

    function drawTable(view, boards, host) {
      for (const x of boards) {
        const ours = x.scored.filter((p) => GROUPS.has(p.group)).map((p) => p.score);
        const lo = ours.length ? Math.min(...ours) : 0, hi = ours.length ? Math.max(...ours) : 1;
        const pad = (hi - lo) * 0.04 || Math.abs(hi) * 0.05 || 0.05;
        x.tlo = lo - pad;
        x.thi = hi + pad;
      }
      const tiers = viewTiers(boards, SERIES, heldTiers(data.lanes, page.tiers));
      const N = boards.length;
      const rows = [];
      for (const s of SERIES) {
        if (st.hide.has(s.harness)) continue;
        const cells = boards.map((x) => {
          const pts = ownPoints(x, s);
          if (!pts.length) return null;
          const run = pts.filter((p) => isCarried(s, p.effort)).map((p) => p.score);
          const scores = pts.map((p) => p.score);
          return { x, pts, lo: Math.min(...scores), hi: Math.max(...scores), best: run.length ? Math.max(...run) : null };
        });
        if (!cells.some(Boolean)) continue;
        const lanes = [...s.lanes.values()].filter((l) => tiers.has(l.name))
          .sort((a, c) => effortIndex(a.effort) - effortIndex(c.effort)).map((l) => tiers.get(l.name));
        const best = lanes.filter((r) => r.n).sort((a, c) => a.rank - c.rank)[0] || null;
        rows.push({ s, cells, lanes, best, fav: favouredEffort(boards, s, EFF) });
      }
      const key = (r) => {
        if (st.sort === null) return r.best ? -r.best.rank : -Infinity;
        if (st.sort === "cost") return r.best && r.best.rc !== null ? -r.best.rc : -Infinity;
        const c = r.cells[st.sort];
        return c ? (c.best !== null ? c.best : c.hi - 1e6) : -Infinity;
      };
      rows.sort((a, c) => key(c) - key(a));
      const table = el("table", { class: st.sel.size ? "dim" : "" }, null, host);
      const hr = el("tr", {}, null, el("thead", {}, null, table));
      const sortButton = (parent, k, text) => el("button", { type: "button", "data-sort": String(k),
        class: String(st.sort) === String(k) || (k === "rank" && st.sort === null) ? "on" : "" }, text, parent);
      sortButton(el("th", { class: "n" }, null, hr), "rank", "#");
      el("th", {}, "Model on harness", hr);
      boards.forEach((x, i) => {
        const th = el("th", { class: "bm" }, null, hr);
        sortButton(th, i, x.board.benchmark);
        el("span", { class: "src" }, ` ${x.board.source}`, th);
        const scale = el("div", { class: "scl" }, null, th);
        el("span", {}, fmtShort(x, x.tlo), scale);
        el("span", {}, x.frac || x.board.unit === "%" ? "score %" : "score", scale);
        el("span", {}, fmtShort(x, x.thi), scale);
      });
      const mean = el("th", { class: "num" }, "Mean pct", hr);
      el("small", {}, `n/${N}`, mean);
      sortButton(el("th", { class: "num" }, null, hr), "cost", "Rel. cost");
      const tierHead = el("th", {}, "Tier now→here", hr);
      el("small", {}, "each lane with a tier", tierHead);
      el("th", {}, "Favours", hr);
      const tbody = el("tbody", {}, null, table);
      for (const r of rows) {
        const s = r.s, colour = harnessColour(s.harness);
        const tr = el("tr", { class: "r" + (st.sel.has(s.group) ? " on" : ""), "data-m": s.group }, null, tbody);
        el("td", { class: "n" }, r.best ? String(r.best.rank) : "–", tr);
        const who = el("span", { class: "who" }, null, el("td", {}, null, tr));
        who.appendChild(seriesGlyph(s, true));
        el("b", {}, s.label, who);
        el("small", {}, s.harness, who);
        for (const c of r.cells) {
          if (!c) { el("span", { class: "na" }, "not measured", el("td", {}, null, tr)); continue; }
          const x = c.x, at = (v) => Math.max(1, Math.min(99, (v - x.tlo) / ((x.thi - x.tlo) || 1) * 100));
          const g = svg("svg", { "aria-hidden": "true" }, el("td", { class: "rg" }, null, tr));
          svg("line", { x1: `${at(c.lo)}%`, x2: `${at(c.hi)}%`, y1: 7, y2: 7, stroke: colour, "stroke-width": 2,
                        "stroke-linecap": "round", opacity: 0.5 }, g);
          for (const p of c.pts) {
            const run = isCarried(s, p.effort);
            svg("circle", { class: "ed", cx: `${at(p.score)}%`, cy: 7, r: run ? 4.2 : 3.3, fill: run ? colour : "var(--surface)",
                            stroke: run ? "var(--surface)" : colour, "stroke-width": 1.4, opacity: effOk(p.effort) ? 1 : 0.25,
                            "data-m": s.group, "data-e": p.effort, "data-b": String(boards.indexOf(x)) }, g);
          }
          const a = at(c.lo), z = at(c.hi);
          if (z - a < 22) {
            svgText(g, { x: `${(a + z) / 2}%`, y: 21, "text-anchor": "middle" },
                    c.lo === c.hi ? fmtShort(x, c.lo) : `${fmtShort(x, c.lo)}–${fmtShort(x, c.hi)}`);
          } else {
            svgText(g, { x: `${a}%`, y: 21, "text-anchor": "middle" }, fmtShort(x, c.lo));
            svgText(g, { x: `${z}%`, y: 21, "text-anchor": "middle" }, fmtShort(x, c.hi));
          }
        }
        const B = r.best;
        const meanCell = el("td", { class: "num" }, B ? null : "–", tr);
        if (B) {
          el("b", {}, `${B.thin ? "~" : ""}${Math.round(B.mean)}`, meanCell);
          meanCell.appendChild(document.createTextNode(" "));
          el("small", {}, `${B.n}/${N}`, meanCell);
        }
        el("td", { class: "num" }, B && B.rc !== null && B.rc !== undefined ? fmtTimes(B.rc) : "–", tr);
        const tz = el("td", { class: "tzs" }, null, tr);
        if (!r.lanes.length) el("span", { class: "na" }, "none held", tz);
        for (const t of r.lanes) {
          const span = el("span", { class: "tz" + (t === B ? " b" : ""), title: t.name }, null, tz);
          el("span", { class: "m" }, t.effort, span);
          if (!t.n) { span.appendChild(document.createTextNode(` ${t.held}→?`)); continue; }
          span.appendChild(document.createTextNode(` ${t.held}→${t.tier}`));
          if (t.tier !== t.held) el("span", { class: "d" }, t.tier > t.held ? "▲" : "▼", span);
          if (t.thin) span.appendChild(document.createTextNode("?"));
        }
        const fav = el("td", {}, r.fav || "–", tr);
        if (r.fav && !isCarried(s, r.fav)) el("small", { class: "na" }, " not carried", fav);
      }
      if (!rows.length) el("p", { class: "aside" }, "No model you have a lane for is measured here.", host);
    }

    // pointing at an effort in the table rings the same point in every plot
    function markHover() {
      for (const x of shown) {
        if (!x.overlay || !x.X) continue;
        x.overlay.textContent = "";
        const h = st.hover, p = h && x.at.get(`${h.group}|${h.effort}`);
        if (!p || !(p.cost > 0)) continue;
        svg("circle", { class: "v-hov", cx: x.X(p.cost), cy: x.Y(p.score), r: 10 }, x.overlay);
        svg("circle", { class: "v-hov", cx: x.X(p.cost), cy: x.Y(p.score), r: 15, opacity: 0.35 }, x.overlay);
      }
    }

    function render() {
      const view = views.find((v) => v.id === st.view);
      const body = view && bodyOf(view.id);
      if (!body) return;
      carried = carriedNames(data.lanes, page.tiers);
      hideTip();
      shown = view.boards.map(boardOf);
      body.textContent = "";
      drawBar(shown, el("div", { class: "v-bar" }, null, body));
      drawCards(view, shown, el("div", { class: "v-grid" }, null, body));
      const head = el("div", { class: "v-sec" }, null, body);
      el("h3", {}, `${view.title}: score range across the efforts`, head);
      el("span", { class: "v-sub" }, "One row per model on a harness. Each cell is the board's own score axis: one dot per "
        + "measured effort, filled where you carry it. Point at a dot to find it in the plots.", head);
      const host = el("div", { class: "v-tbl" }, null, body);
      drawTable(view, shown, host);
      host.addEventListener("pointermove", (e) => {
        const c = e.target.closest && e.target.closest("circle[data-e]");
        const h = c ? { group: c.dataset.m, effort: c.dataset.e } : null;
        if (JSON.stringify(h) !== JSON.stringify(st.hover)) { st.hover = h; markHover(); }
        if (!c) { hideTip(); return; }
        const x = shown[Number(c.dataset.b)], p = x && x.at.get(`${h.group}|${h.effort}`);
        if (!p) return;
        tip.textContent = "";
        el("b", {}, fmtViewScore(x, p.score), tipLine(null, "v-tip-head")).after(document.createTextNode(` · ${fmtMoney(p.cost)}`));
        tipLine(`${x.board.benchmark} · ${p.effort}`);
        placeTip(e);
      });
      host.addEventListener("pointerleave", () => { st.hover = null; markHover(); hideTip(); });
    }

    // one listener per view body: the filters, the picks and the table's sort
    for (const v of views) {
      const body = bodyOf(v.id);
      if (!body) continue;
      body.addEventListener("click", (e) => {
        const t = e.target.closest("[data-h],[data-ctx],[data-eff],[data-m],[data-ref],[data-sort],[data-clear]");
        if (!t || !body.contains(t)) return;
        const d = t.dataset;
        if (d.h !== undefined) { if (st.hide.has(d.h)) st.hide.delete(d.h); else st.hide.add(d.h); }
        else if (d.ctx !== undefined) st.ctx = t.checked;
        else if (d.clear !== undefined) { st.sel.clear(); st.eff.clear(); st.hide.clear(); st.ref.clear(); }
        else if (d.eff !== undefined) { if (d.eff) pick(st.eff, d.eff, e.shiftKey); else st.eff.clear(); }
        else if (d.ref !== undefined) pick(st.ref, d.ref, true);
        else if (d.sort !== undefined) st.sort = d.sort === "rank" ? null : d.sort === "cost" ? "cost" : Number(d.sort);
        else if (d.m !== undefined) pick(st.sel, d.m, e.shiftKey);
        render();
      });
    }
    let resizing = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizing);
      resizing = setTimeout(() => { if (st.view) render(); }, 120);
    });

    return {
      ids: views.map((v) => v.id),
      show(id) {
        const known = views.some((v) => v.id === id);
        if (known && st.view !== id) { st.wide = null; st.sort = null; }
        st.view = known ? id : null;
        if (known) render();
        else hideTip();
      },
      redraw() { if (st.view) render(); },
    };
  }

  // --- the tabs ---------------------------------------------------------------------

  // One flat row: each view, then All boards, Prices and Numbers. The tab is
  // kept in the hash (`#tab=<id>`) and with the page's own state; the page
  // opens on the first view.
  function makeTabs(page, first, onShow) {
    const tabs = [...document.querySelectorAll("nav.tabs .tab")];
    const sections = [...document.querySelectorAll("[data-view]")].filter((n) => !n.classList.contains("tab"));
    const known = new Set(tabs.map((t) => t.dataset.view));
    const aside = document.getElementById("tiers");
    function show(id, push) {
      if (!known.has(id)) id = first;
      page.view = id;
      for (const t of tabs) {
        const on = t.dataset.view === id;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
      }
      for (const n of sections) n.hidden = n.dataset.view !== id;
      // the board grid holds the workbench of free plots and the tier panel
      const grid = document.querySelector(".board");
      if (grid) grid.hidden = id !== "boards";
      if (aside) aside.classList.toggle("tucked", id !== "boards");
      if (push && history.replaceState) history.replaceState(null, "", `#tab=${id}`);
      page.saveView(id);
      onShow(id);
    }
    for (const t of tabs) {
      t.addEventListener("click", (e) => { e.preventDefault(); show(t.dataset.view, true); });
      t.addEventListener("keydown", (e) => {
        const i = tabs.indexOf(t);
        const to = e.key === "ArrowRight" ? tabs[(i + 1) % tabs.length] : e.key === "ArrowLeft" ? tabs[(i + tabs.length - 1) % tabs.length] : null;
        if (to) { e.preventDefault(); to.focus(); show(to.dataset.view, true); }
      });
    }
    // the hash may carry a view's picks after the tab (`#tab=coding&m=...`)
    const fromHash = (location.hash || "").replace(/^#(tab=|view-)/, "").split("&")[0];
    show(known.has(fromHash) ? fromHash : (page.savedView && known.has(page.savedView) ? page.savedView : first), false);
    // the hash names a tab, not a place to scroll to
    if (fromHash) setTimeout(() => window.scrollTo(0, 0), 0);
    return { show };
  }

  // Light unless this browser asked for dark (`#theme=dark` asks too); the
  // choice is kept for every page, not per catalog, when storage allows.
  const THEME_KEY = "delegate-bench-page:theme";
  function bootTheme() {
    const button = document.getElementById("theme");
    if (!button) return;
    const set = (theme, keep) => {
      document.documentElement.setAttribute("data-theme", theme);
      button.textContent = theme === "dark" ? "Light mode" : "Dark mode";
      if (!keep) return;
      try { localStorage.setItem(THEME_KEY, theme); } catch (_err) { /* stays for this visit */ }
    };
    let theme = "light";
    try { if (localStorage.getItem(THEME_KEY) === "dark") theme = "dark"; } catch (_err) { /* light */ }
    const asked = /(?:^#|&)theme=(dark|light)(?:&|$)/.exec(location.hash || "");
    set(asked ? asked[1] : theme, false);
    button.hidden = false;
    button.addEventListener("click", () => set(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark", true));
  }

  // --- the page's own state, kept in this browser -----------------------------------

  function makeStore(data) {
    const key = `delegate-bench-page:${data.catalogKey}`;
    let saved = {};
    try {
      saved = JSON.parse(localStorage.getItem(key) || "{}") || {};
    } catch (_err) {
      saved = {};
    }
    const known = new Set(data.lanes.map((l) => l.name));
    const tiers = {};
    for (const [name, t] of Object.entries(saved.tiers || {})) {
      if (known.has(name) && (TIERS.includes(t) || t === OFF)) tiers[name] = t;
    }
    const manual = {};
    for (const name of Object.keys(tiers)) {
      if (saved.version !== 2 || (saved.manual || {})[name]) manual[name] = true;
    }
    const lines = {};
    for (const [key, xs] of Object.entries(saved.version === 2 ? saved.lines || {} : {})) {
      if (data.boards.some((b) => boardKey(b) === key) && Array.isArray(xs) && xs.length === 3
          && xs.every(Number.isFinite) && xs[0] < xs[1] && xs[1] < xs[2]) lines[key] = xs.slice();
    }
    const page = { tiers, lines, manual, hovered: null, tierView: !!saved.tierView, focusTier: null, selected: null,
                   storage: "ok", savedView: typeof saved.view === "string" ? saved.view : null, view: null };
    page.saveView = (id) => { page.savedView = id; page.save(); };
    page.save = () => {
      try {
        localStorage.setItem(key, JSON.stringify({ version: 2, tiers, lines, manual, tierView: page.tierView,
                                                   view: page.savedView }));
        page.storage = "ok";
      } catch (_err) {
        page.storage = "unavailable";
      }
    };
    // Everything this page holds for this catalog, gone: every tier and off
    // drawn, every manual mark, and the three lines on every board, which go
    // back to undrawn and are recomputed from the scores when they are asked
    // for again. What stays is the tier view toggle, which is how the page is
    // read rather than what it holds. The focused tier goes too: there is
    // nothing left to focus on, and a page still hiding dots for it would read
    // as empty. Nothing outside the browser is touched, as nothing here ever is
    // (ticket 36).
    page.resetAll = () => {
      for (const holder of [tiers, manual, lines]) {
        for (const name of Object.keys(holder)) delete holder[name];
      }
      page.focusTier = null;
      page.save();
    };
    page.save();
    return page;
  }

  // --- price per model ---------------------------------------------------------
  // One row per model, two dots on one log axis: what the vendor lists per 1M
  // tokens in and out (ticket 36). Efforts collapsed, because every effort of a
  // model is charged the same. Colour is the meter, as everywhere else here;
  // identity is the row's own name beside it, so colour carries nothing alone.
  // Input is an open dot and output a filled one, the two marks a row needs,
  // rather than a second hue for the same money.

  const PRICE_ROW = 26, PRICE_PAD = { l: 200, r: 64, t: 10, b: 34 };
  // the page's surface, for an open dot's fill and a filled dot's ring
  const SURFACE = "var(--surface, #ffffff)";

  // A list price, short and in one form the whole chart over: $50, $12, $2,
  // $0.75, $0.125. `fmtMoney` is the page's figure for a measured cost, where a
  // trailing place carries information; a price is the vendor's own round
  // number, and "$10.0" beside "$2" reads as two different kinds of number.
  function fmtPrice(v) {
    if (v === null || v === undefined || !isFinite(v)) return "\u2014";
    const a = Math.abs(v);
    if (a >= 1000) return "$" + Math.round(v).toLocaleString("en-US");
    return "$" + String(+v.toFixed(a >= 10 ? 0 : a >= 1 ? 2 : 3));
  }

  function priceValues(rows) {
    const out = [];
    for (const row of rows) {
      for (const key of ["in", "out"]) {
        if (typeof row[key] === "number" && row[key] > 0) out.push(row[key]);
        const span = row[`${key}_range`];
        if (Array.isArray(span)) for (const v of span) if (v > 0) out.push(v);
      }
    }
    return out;
  }

  function drawPrices(rows, host) {
    host.textContent = "";
    const values = priceValues(rows);
    const height = PRICE_PAD.t + rows.length * PRICE_ROW + PRICE_PAD.b;
    const frame = svg("svg", {
      viewBox: `0 0 ${W} ${height}`, class: "price-plot", role: "img",
      "aria-label": "List price per 1M tokens, input and output, per model, on a log scale",
    }, host);
    if (!values.length) return frame;
    const [lo, hi] = logDomain(values);
    const x0 = PRICE_PAD.l, x1 = W - PRICE_PAD.r;
    const at = (v) => x0 + (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)) * (x1 - x0);
    const bottom = height - PRICE_PAD.b;

    for (const tick of logTicks(lo, hi)) {
      const x = at(tick);
      svg("line", { x1: x, y1: PRICE_PAD.t, x2: x, y2: bottom, class: "grid" }, frame);
      svg("text", { x, y: bottom + 16, class: "tick mid" }, frame).textContent = fmtTickMoney(tick);
    }
    svg("text", { x: (x0 + x1) / 2, y: bottom + 30, class: "axis-title mid" }, frame)
      .textContent = "USD per 1M tokens (log)";

    rows.forEach((row, index) => {
      const y = PRICE_PAD.t + index * PRICE_ROW + PRICE_ROW / 2;
      const colour = meterColour(row.meter);
      const name = svg("text", { x: x0 - 12, y: y + 4, class: "price-name" + (row.carried ? "" : " quiet"),
                                 "text-anchor": "end" }, frame);
      // the gutter is fixed, so a name too long for it is cut rather than drawn
      // off the edge; the row's own tooltip still says it whole
      const room = Math.floor((x0 - 16) / CHAR_PX);
      name.textContent = row.model.length > room ? row.model.slice(0, room - 1) + "\u2026" : row.model;
      const said = [`${row.model}: ${row.efforts.length} effort${row.efforts.length === 1 ? "" : "s"}`,
                    row.meter ? `meter ${row.meter}` : null,
                    row.carried ? "carried" : "not carried",
                    `in ${fmtPrice(row.in)}`, `out ${fmtPrice(row.out)}`].filter(Boolean);
      svg("title", {}, svg("rect", { x: 0, y: y - PRICE_ROW / 2, width: W, height: PRICE_ROW,
                                     class: "price-hit" }, frame)).textContent = said.join(" · ");
      if (row.in === null && row.out === null) {
        svg("text", { x: x0, y: y + 4, class: "price-none" }, frame).textContent = "no published price";
        return;
      }
      if (row.in !== null && row.out !== null) {
        svg("line", { x1: at(row.in), y1: y, x2: at(row.out), y2: y,
                      class: "price-link", stroke: colour }, frame);
      }
      for (const key of ["in", "out"]) {
        const value = row[key];
        if (value === null) continue;
        const span = row[`${key}_range`];
        if (span) {
          svg("line", { x1: at(span[0]), y1: y, x2: at(span[1]), y2: y,
                        class: "price-span", stroke: colour }, frame);
        }
        // the filled dot takes its 2px ring from the surface in CSS, so it stays
        // legible where two rows' dots meet; the open one is the meter's colour
        const dot = svg("circle", { cx: at(value), cy: y, r: 5,
                                    class: key === "out" ? "price-dot out" : "price-dot in",
                                    fill: key === "out" ? colour : SURFACE }, frame);
        if (key === "in") dot.setAttribute("stroke", colour);
        svg("title", {}, dot).textContent =
          `${row.model} · ${key === "out" ? "output" : "input"} ${fmtPrice(value)} per 1M tokens`
          + (span ? ` · efforts disagree: ${fmtPrice(span[0])} to ${fmtPrice(span[1])}` : "");
        // The cheaper end labels left and the dearer right, so the two never sit
        // on top of each other however close the prices are. A disagreement
        // reads as the range itself, which is the whole of what there is to say
        // about it.
        const text = span ? `${fmtPrice(span[0])}\u2013${fmtPrice(span[1])}` : fmtPrice(value);
        const other = key === "in" ? row.out : row.in;
        const cheaper = other !== null && value <= other;
        // The cheapest model of all sits against the left end of the axis, where
        // its label may not fit beside it. That label goes above its dot, never
        // to the right, where the link to the other dot runs: a label lying over
        // its own line is unreadable, and the row has the height to spare.
        if (cheaper && at(value) - 10 - (text.length * CHAR_PX + 6) < x0 - 4) {
          svg("text", { x: at(value), y: y - 9, class: "price-value mid" }, frame).textContent = text;
        } else {
          svg("text", { x: at(value) + (cheaper ? -10 : 10), y: y + 4, class: "price-value",
                        "text-anchor": cheaper ? "end" : "start" }, frame).textContent = text;
        }
      }
    });
    return frame;
  }

  function bootPrices() {
    const source = document.getElementById("price-data");
    const host = document.getElementById("price-chart");
    if (!source || !host) return;
    const data = JSON.parse(source.textContent);
    if (!SHADES.size) setShades(data.meters);
    const key = el("p", { class: "price-key" }, null, host);
    svg("circle", { cx: 6, cy: 6, r: 4, class: "price-dot in", fill: SURFACE, stroke: "var(--muted)" },
        svg("svg", { viewBox: "0 0 12 12", class: "key", "aria-hidden": "true" }, key));
    key.appendChild(document.createTextNode(" input  "));
    svg("circle", { cx: 6, cy: 6, r: 4, class: "price-dot out", fill: "var(--muted)" },
        svg("svg", { viewBox: "0 0 12 12", class: "key", "aria-hidden": "true" }, key));
    key.appendChild(document.createTextNode(" output"));
    drawPrices(data.rows || [], el("div", { class: "price-body" }, null, host));
  }

  function boot() {
    bootTheme();
    bootPrices();
    const source = document.getElementById("bench-data");
    const host = document.getElementById("plots");
    if (!source || !host) return;
    const data = JSON.parse(source.textContent);
    if (!data.boards.length) return;
    data.lanes = (data.lanes || []).map((l, rank) => Object.assign({ rank }, l));
    setShades(data.meters);
    const page = makeStore(data);
    const panels = [];
    let count = 0;
    const every = (fn) => panels.forEach(fn);
    const tierHost = document.getElementById("tiers");
    const tierPanel = tierHost ? makeTierPanel(data, page, tierHost, document.getElementById("sensitivity")) : null;
    page.shownBoards = () => {
      const ids = new Set(panels.map((p) => p.board()));
      return data.boards.filter((b) => ids.has(b.id));
    };
    page.boardChanged = () => { if (tierPanel) tierPanel.draw(); };

    const views = makeViews(data, page);
    page.redraw = (onlySource) => {
      every((p) => { if (!onlySource || p.source() === onlySource) p.draw(); });
      if (tierPanel && !onlySource) tierPanel.draw();
      if (!onlySource && views) views.redraw();
    };
    page.setTiers = (changes) => {
      for (const [names, tier] of changes) {
        for (const name of names) {
          if (tier) { page.tiers[name] = tier; page.manual[name] = true; }
          else { delete page.tiers[name]; delete page.manual[name]; }
        }
      }
      page.save();
      page.redraw();
    };
    page.setTier = (names, tier) => page.setTiers([[names, tier]]);
    page.select = (selection, owner) => {
      page.selected = selection;
      every((p) => p.selected(owner));
      page.highlight(null);
    };
    page.focus = (tier) => {
      page.focusTier = tier;
      every((p) => p.focusTier(tier));
      if (tierPanel) tierPanel.draw();
    };
    page.clearFocus = () => {
      if (!page.focusTier) return;
      page.focusTier = null;
      every((p) => p.draw());
      if (tierPanel) tierPanel.draw();
    };
    page.highlight = (laneName) => {
      page.hovered = laneName;
      every((p) => p.highlightLane());
      const names = page.selected ? page.selected.lanes : [];
      for (const row of tierHost.querySelectorAll(".lane-row")) {
        row.classList.toggle("selected", names.includes(row.dataset.lane));
      }
    };

    const remove = (panel) => {
      if (panels.length < 2) return;
      panels.splice(panels.indexOf(panel), 1);
      panel.root.remove();
      every((p) => p.draw());
      page.boardChanged();
    };
    const add = (boardId) => {
      const panel = makePanel(data, host, count++, boardId, remove, every, page);
      panels.push(panel);
      every((p) => p.draw());
      return panel;
    };
    for (const id of data.defaults) add(id);
    if (tierPanel) tierPanel.draw();
    // a view is drawn when its tab shows, so its plots are laid out at their
    // real width; All boards' panels redraw when theirs does
    makeTabs(page, views ? views.ids[0] : "boards", (id) => {
      if (views) views.show(id);
      every((p) => { if (p.root.offsetParent !== null) p.draw(); });
    });
    const more = document.getElementById("add-plot");
    if (more) {
      more.hidden = false;
      more.addEventListener("click", () => {
        const used = new Set(panels.map((p) => p.board()));
        const next = data.boards.find((b) => !used.has(b.id)) || data.boards[0];
        const still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        add(next.id).root.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
        page.boardChanged();
      });
    }
    // 1 to 4 set the selected lane's tier, o turns it off, 0 clears it, Escape lets go
    document.addEventListener("keydown", (e) => {
      const tag = e.target && e.target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (!page.selected) return;
      if (/^[1-4]$/.test(e.key)) {
        page.setTier(page.selected.lanes, Number(e.key));
        e.preventDefault();
      } else if (e.key === "o" || e.key === "O") {
        page.setTier(page.selected.lanes, OFF);
        e.preventDefault();
      } else if (e.key === "0" || e.key === "Backspace" || e.key === "Delete") {
        page.setTier(page.selected.lanes, null);
        e.preventDefault();
      } else if (e.key === "Escape") {
        page.select(null);
      }
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { layout, frontier, logTicks, logDomain, niceLinear, fmtMoney, fmtTickMoney, place,
                       zoomAbout, covers, panBy, bandTier, defaultLines, pointTier, groupLanes, reviewOrder,
                       tierLinesText, focusDomain, applyBands, makeStore, boardKey, pointOff, carriedNames,
                       placeable, beatenByLane, panelGroups, sensitivity, meterColour, setShades,
                       cutRanked, cutBoard, heldTiers, pick, viewSeries, indexBoard, percentile, viewScore,
                       favouredEffort, viewTiers, linearTicks, costTicks, fmtCostTick,
                       priceValues, drawPrices, fmtPrice, OFF, W, H, PAD };
  } else if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
    else boot();
  }
})();
