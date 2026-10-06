"""One self-contained HTML file: no server, no build, no cost.

A monitoring wall in the style of World Monitor: dark, map-centred, tabbed,
and sized to the screen so nothing scrolls on a desktop. Tabs are CSS-only
(radio inputs), so the page works with JavaScript off. Phones fall back to a
normal scrolling column.
"""
import html

import config as C
import geo
import scoring

E = html.escape

LEVEL = {
    "Alert": "#ff4d4f",
    "Warning": "#ff8a1f",
    "Watch": "#f5c518",
    "Normal": "#3ddc84",
    "insufficient data": "#6b7a8a",
}
MEANING = {
    "Alert": "Three or more independent signal groups are unusual at once.",
    "Warning": "Two signal groups are unusual at once.",
    "Watch": "One group is strongly unusual, or two are mildly unusual.",
    "Normal": "Nothing is outside its usual range.",
    "insufficient data": "Too few groups have enough history to judge.",
}
ORDER = ["Alert", "Warning", "Watch", "Normal", "insufficient data"]
ZMAX = 6.0
ADV = {1: "lv1", 2: "lv2", 3: "lv3", 4: "lv4"}
VIEWS = {   # tab id -> (title, theatre, map view)
    "ukraine": ("Ukraine", "ukraine", "ukraine"),
    "east": ("Eastern flank", "europe_east", "europe_east"),
    "mideast": ("Middle East", "mideast", "mideast"),
}
CHOKE = {"Hormuz": (26.6, 56.3, "Hormuz"), "Bab": (12.6, 43.3, "Bab el-Mandeb"),
         "Suez": (30.0, 32.5, "Suez"), "Bosporus": (41.1, 29.0, "Bosporus")}
NAME = {"ukraine": "Ukraine", "europe_east": "Eastern flank", "mideast": "Middle East", "global": "Supplier side (US and EU)"}
HUBS_LABEL = {"ukraine": (49.0, 31.5), "europe_east": (56.5, 22.5), "mideast": (30.5, 47.0)}


# ---- small pieces -------------------------------------------------------------------
def zval(s):
    return scoring.directed(s["score"]["z"], s["direction"]) if s["status"] == "ok" and s.get("score") else None


def fmt(v):
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.1f}B"
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    if a >= 1e4:
        return f"{v / 1e3:.0f}k"
    return f"{v:,.0f}" if a >= 100 else f"{v:.2f}".rstrip("0").rstrip(".")


def bar(z):
    frac = max(-1.0, min(1.0, z / ZMAX))
    left, width = (50, frac * 50) if frac >= 0 else (50 + frac * 50, -frac * 50)
    tick = 50 + C.THRESH_SIGNAL / ZMAX * 50
    hot = " hot" if z >= C.THRESH_SIGNAL else ""
    return (f'<span class="bar"><i class="c"></i><i class="t" style="left:{tick:.1f}%"></i>'
            f'<i class="f{hot}" style="left:{left:.1f}%;width:{width:.1f}%"></i></span>')


def srow(s, short=False):
    z = zval(s)
    speed = '<i class="dot lag" title="Published late: confirms, does not lead"></i>' if s["lag"] else \
        '<i class="dot fast" title="Fast source: can lead"></i>'
    if z is not None:
        cell = f'{bar(z)}<b class="v{" hot" if z >= C.THRESH_SIGNAL else ""}">{z:+.1f}</b>'
        cls = " hotrow" if z >= C.THRESH_SIGNAL else ""
        if s.get("stale"):
            cell += '<span class="mini stale" title="Source failed; last good data shown">stale</span>'
    elif s["status"] == "collecting":
        last = s["points"][-1][1] if s["points"] else None
        cell = (f'<span class="muted">now {fmt(last)}</span><span class="mini">{len(s["points"])} pts</span>'
                if last is not None else '<span class="muted">collecting</span>')
        cls = " dim"
    elif s["status"] == "awaiting_key":
        cell, cls = '<span class="mini warn">needs key</span>', " dim"
    else:
        cell, cls = '<span class="mini bad">no data</span>', " dim"
    tip = f'{s["label"]} | {s["why"]}'
    return (f'<div class="sr{cls}" title="{E(tip)}">{speed}<span class="nm">{E(s["label"].split(" (")[0])}</span>'
            f'<span class="cell">{cell}</span></div>')


def level_pill(lv):
    return f'<b class="pill" style="--c:{LEVEL[lv]}">{E(lv)}</b>'


def domain_rows(view):
    out = []
    for dom, label in C.DOMAINS.items():
        d = view["domains"][dom]
        if d["z"] is None:
            body = '<span class="muted">no data yet</span>'
        else:
            body = f'{bar(d["z"])}<b class="v{" hot" if d["z"] >= C.THRESH_SIGNAL else ""}">{d["z"]:+.1f}</b>'
        out.append(f'<div class="sr"><i class="dot {"fast" if d["fast"] else "lag"}"></i>'
                   f'<span class="nm">{E(label)}</span><span class="cell">{body}</span></div>')
    return "".join(out)


def top_signals(series, theatre, n=9):
    pool = [(zval(s), s) for s in series if s["theatre"] in (theatre, "global") and zval(s) is not None]
    pool.sort(key=lambda x: -x[0])
    return "".join(srow(s) for _, s in pool[:n]) or '<div class="sr dim"><span class="nm">No signal has enough history yet.</span></div>'


def level_card(name, v, big=True):
    lv = v["level"]
    firing = ", ".join(C.DOMAINS[d] for d in v["firing"]) or "none"
    note = ""
    if "lagging" in (v.get("basis") or ""):
        note = '<p class="note">Only slow data is unusual: a confirmation, not an early signal.</p>'
    return (f'<div class="lvl" style="--c:{LEVEL[lv]}"><div class="lh"><span class="ln">{E(name)}</span>{level_pill(lv)}</div>'
            f'<p>{E(MEANING[lv])}</p><p class="sub">Unusual groups: {E(firing)}</p>{note}</div>')


# ---- maps ---------------------------------------------------------------------------------
def theatre_of(box_name):
    return {"overview": None, "ukraine": "ukraine", "europe_east": "europe_east", "mideast": "mideast"}[box_name]


def build_map(view, topo, extras, series, th):
    box = geo.VIEWS[view]
    w, h = geo.view_size(box, 1000)
    proj = geo.Proj(box, w, h)
    lv = {name: ADV.get(n, "") for name, n in (extras or {}).get("levels", {}).items()}
    land = ""
    if topo:
        land = "".join(f'<path class="cty {c}" d="{d}"><title>{E(n)}</title></path>' for n, d, c in geo.paths(topo, proj, lv))
    parts = [f'<svg class="map" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img" '
             f'aria-label="Map of {view}"><rect width="{w}" height="{h}" class="sea"/>{land}']
    ex = extras or {}
    la0, la1, lo0, lo1 = box[2], box[3], box[0], box[1]
    for a in ex.get("mil", []):
        if lo0 <= a["lon"] <= lo1 and la0 <= a["lat"] <= la1:
            x, y = proj.xy(a["lon"], a["lat"])
            parts.append(f'<circle class="ac {"lift" if a["lift"] else "mil"}" cx="{x:.1f}" cy="{y:.1f}" r="{3.4 if a["lift"] else 2.4}">'
                         f'<title>{"Airlift or tanker" if a["lift"] else "Military aircraft"} {E(a["t"])}</title></circle>')
    for m in ex.get("nga", []):
        if lo0 <= m["lon"] <= lo1 and la0 <= m["lat"] <= la1:
            x, y = proj.xy(m["lon"], m["lat"])
            parts.append(f'<rect class="hz" x="{x - 3.5:.1f}" y="{y - 3.5:.1f}" width="7" height="7" '
                         f'transform="rotate(45 {x:.1f} {y:.1f})"><title>{E(m["text"])}</title></rect>')
    for z in ex.get("czib", []):
        if lo0 <= z["lon"] <= lo1 and la0 <= z["lat"] <= la1:
            x, y = proj.xy(z["lon"], z["lat"])
            parts.append(f'<circle class="cz" cx="{x:.1f}" cy="{y:.1f}" r="6"><title>EASA conflict-zone bulletin: {E(z["name"])}</title></circle>')
    for frag, (lat, lon, nm) in CHOKE.items():
        if lo0 <= lon <= lo1 and la0 <= lat <= la1:
            s = next((s for s in series if s["id"] == f"portwatch_{frag.lower()}"), None)
            z = zval(s) if s else None
            col = "#6b7a8a" if z is None else ("#ff4d4f" if z >= C.THRESH_SIGNAL else "#3ddc84")
            x, y = proj.xy(lon, lat)
            tag = "no data" if z is None else f"{z:+.1f}"
            parts.append(f'<g class="ck"><circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="none" stroke="{col}" stroke-width="2"/>'
                         f'<text x="{x + 11:.1f}" y="{y + 4:.1f}">{E(nm)} {tag}</text></g>')
    for t, (lat, lon) in HUBS_LABEL.items():
        if lo0 <= lon <= lo1 and la0 <= lat <= la1 and view == "overview":
            x, y = proj.xy(lon, lat)
            col = LEVEL[th[t]["level"]]
            parts.append(f'<g class="tl"><rect x="{x - 56:.1f}" y="{y - 14:.1f}" width="112" height="28" rx="3" '
                         f'style="stroke:{col}"/><text x="{x:.1f}" y="{y - 1:.1f}" class="a">{E(NAME[t])}</text>'
                         f'<text x="{x:.1f}" y="{y + 10:.1f}" class="b" fill="{col}">{E(th[t]["level"].upper())}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def legend(extras, topo):
    ex = extras or {}
    n_mil = sum(1 for a in ex.get("mil", []) if not a["lift"])
    n_lift = sum(1 for a in ex.get("mil", []) if a["lift"])
    bits = [f'<span><i class="sw ac mil"></i>Military aircraft ({n_mil})</span>',
            f'<span><i class="sw ac lift"></i>Airlift / tanker ({n_lift})</span>',
            f'<span><i class="sw hz"></i>Naval-air hazard warnings ({len(ex.get("nga", []))})</span>',
            f'<span><i class="sw cz"></i>EASA airspace bulletin ({len(ex.get("czib", []))})</span>',
            '<span><i class="sw lv2"></i>US advisory level 2</span><span><i class="sw lv3"></i>3</span>'
            '<span><i class="sw lv4"></i>4 (do not travel)</span>']
    miss = []
    if not topo:
        miss.append("basemap")
    miss += [e.split(":")[0] for e in ex.get("errors", [])]
    if extras is None:
        miss.append("live layers (demo)")
    note = f'<span class="miss">Layer unavailable this run: {E(", ".join(miss))}</span>' if miss else ""
    return f'<div class="legend">{"".join(bits)}{note}</div>'


def hazard_strip(extras, view):
    box = geo.VIEWS[view]
    items = [m for m in (extras or {}).get("nga", []) if box[0] <= m["lon"] <= box[1] and box[2] <= m["lat"] <= box[3]][:3]
    if not items:
        return '<div class="hzs"><b>Hazard warnings</b><span class="muted">None active in this view (NGA broadcast warnings).</span></div>'
    return '<div class="hzs"><b>Hazard warnings</b>' + "".join(f'<span title="{E(m["text"])}">{E(m["id"])}: {E(m["text"][:95])}</span>' for m in items) + '</div>'


# ---- views -----------------------------------------------------------------------------------
def poly_list(extras, n=5):
    mk = (extras or {}).get("poly", [])[:n]
    if not mk:
        return '<div class="sr dim"><span class="nm">Prediction markets unavailable this run.</span></div>'
    return "".join(f'<div class="sr" title="{E(m["q"])} | volume ${m["vol"]:,.0f}, ends {E(m["end"])}">'
                   f'<span class="nm">{E(m["q"])}</span><span class="cell"><b class="v">{m["p"] * 100:.0f}%</b></span></div>' for m in mk)


def theatre_view(tid, title, theatre, view, th, series, topo, extras):
    v = th[theatre]
    return (f'<section class="view v-{tid}"><div class="mapcol"><div class="mapbox">{build_map(view, topo, extras, series, th)}'
            f'{legend(extras, topo)}</div>{hazard_strip(extras, view)}</div>'
            f'<aside class="side">{level_card(title, v)}<h4>Signal groups</h4>{domain_rows(v)}'
            f'<h4>Most unusual signals</h4>{top_signals(series, theatre)}</aside></section>')


def overview_view(th, series, topo, extras):
    cards = "".join(f'<div class="tc">{level_card(NAME[t], th[t])}</div>'
                    for t in ("ukraine", "europe_east", "mideast", "global"))
    pool = [(zval(s), s) for s in series if zval(s) is not None]
    pool.sort(key=lambda x: -x[0])
    movers = "".join(srow(s) for _, s in pool[:8]) or '<div class="sr dim"><span class="nm">No signal has enough history yet.</span></div>'
    return (f'<section class="view v-overview"><div class="mapcol"><div class="mapbox">{build_map("overview", topo, extras, series, th)}'
            f'{legend(extras, topo)}</div></div>'
            f'<aside class="side"><div class="tcs">{cards}</div><h4>Most unusual signals, everywhere</h4>{movers}'
            f'<h4>What traders price (Polymarket, not scored)</h4>{poly_list(extras)}</aside></section>')


def supply_view(series):
    def col(dom):
        rows = [s for s in series if s["domain"] == dom]
        rows.sort(key=lambda s: -(zval(s) if zval(s) is not None else -99))
        live = sum(1 for s in rows if s["status"] == "ok")
        return (f'<h4>{E(C.DOMAINS[dom])} <span class="muted">{live}/{len(rows)} live</span></h4>'
                + "".join(srow(s) for s in rows))
    cols = [f'<div class="col">{col("kit")}</div>',
            f'<div class="col">{col("vehicles")}{col("infrastructure")}</div>',
            f'<div class="col">{col("medical")}{col("markets")}</div>']
    return (f'<section class="view v-supply"><div class="cols">{"".join(cols)}</div>'
            '<p class="foot">Supplier-side data: what the US and EU are buying and shipping. Most of it is published weeks late, '
            'so it confirms a build-up; the map tabs carry the fast signals. Grey dot = confirms, green dot = can lead.</p></section>')


def system_view(series, generated, demo):
    stat = {}
    for s in series:
        k = "stale" if s.get("stale") else s["status"]
        stat[k] = stat.get(k, 0) + 1
    hs = [("ok", "Live"), ("stale", "Stale"), ("collecting", "Building history"), ("awaiting_key", "Need a key"), ("error", "Failed")]
    cards = "".join(f'<div class="hs"><b>{stat.get(k, 0)}</b><span>{lbl}</span></div>' for k, lbl in hs)
    bad = [s for s in series if s["status"] in ("error", "awaiting_key")][:10]
    badl = "".join(f'<div class="sr dim" title="{E(s["error"])}"><span class="nm">{E(s["label"])}</span>'
                   f'<span class="cell"><span class="mini bad">{E(s["error"][:46])}</span></span></div>' for s in bad) \
        or '<div class="sr"><span class="nm">Every source answered.</span></div>'
    how = (f'<ul><li><b>Score.</b> Distance of each signal from its own usual range for the season, in standard deviations. '
           f'Above +{C.THRESH_SIGNAL:.1f} is unusual; about 1 calm reading in 100 does that by chance.</li>'
           '<li><b>Level.</b> Counts independent groups that agree: Watch (one strong or two mild), Warning (two), Alert (three or more). It is not a probability of war.</li>'
           '<li><b>Leads or lags.</b> Green dot: fast source that can lead (flights, warnings, news, shipping, markets). Grey dot: published weeks late, so it only confirms.</li>'
           '<li><b>Snapshot signals</b> (aircraft, hazard warnings, navigation jamming) have no history yet. They show their latest value until about 12 weeks are stored, then score.</li>'
           '<li><b>Limits.</b> No backtest against past conflicts has been run. Public data cannot see covert moves. Treat a Watch as a reason to read primary sources.</li></ul>')
    gaps = [("GDELT news", "blocks every cloud IP address; replaced by Google News headline counts"),
            ("ISW, UKMTO, OREF alerts", "block automated access; no free machine feed"),
            ("GPS-jamming map (gpsjam)", "needs a hex-grid decoder; aircraft accuracy reports used instead"),
            ("Satellite fire detection (NASA FIRMS)", "free; needs a map key from you"),
            ("Conflict events (ACLED)", "free for research; needs an account from you"),
            ("Port-level shipping, UN Comtrade", "queued; trade data is the slowest source anyway")]
    gap = "".join(f'<div class="sr"><span class="nm" title="{E(b)}"><b>{E(a)}</b> <span class="muted">{E(b)}</span></span></div>' for a, b in gaps)
    demo_note = '<p class="demo">DEMO: synthetic data, not real observations.</p>' if demo else ""
    return (f'<section class="view v-system"><div class="sysg"><div><h4>Data health</h4><div class="hstats">{cards}</div>'
            f'<h4>Sources not answering</h4>{badl}<h4>Not covered yet, and why</h4>{gap}</div><div><h4>How to read this</h4>{how}{demo_note}'
            f'<p class="foot">Public data only: USAspending, Eurostat, TED, US Census, SAM.gov, IMF PortWatch, FCDO, US State Dept, '
            f'NGA, adsb.lol, Google News, Polymarket, FRED. Updated {E(generated)}. Source: github.com/khourix/warwatch</p></div></div></section>')


# ---- page --------------------------------------------------------------------------------------
CSS = """
:root{--bg:#0a0f0a;--panel:#10170f;--panel2:#141d13;--line:#223020;--ink:#e6efe4;--mute:#8a9c88;--acc:#3ddc84;--warn:#ff8a1f;--bad:#ff4d4f;
--mono:ui-monospace,'SF Mono','Cascadia Mono',Menlo,Consolas,monospace;--sans:Inter,system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.35 var(--sans);overflow:hidden}
input.r{position:absolute;opacity:0;pointer-events:none}
.app{height:100vh;display:grid;grid-template-rows:46px minmax(0,1fr)}
.top{display:flex;align-items:center;gap:14px;padding:0 14px;background:var(--panel);border-bottom:1px solid var(--line)}
.brand{font-weight:800;letter-spacing:.14em;font-size:13px;display:flex;align-items:center;gap:8px}
.brand i{width:9px;height:9px;background:var(--acc);border-radius:50%;box-shadow:0 0 8px var(--acc)}
.tabs{display:flex;gap:2px;margin-left:8px;height:100%}
.tabs label{display:flex;align-items:center;gap:7px;padding:0 14px;cursor:pointer;color:var(--mute);font-weight:600;border-bottom:2px solid transparent;font-size:12.5px;white-space:nowrap}
.tabs label:hover{color:var(--ink)}
.tabs label b{width:8px;height:8px;border-radius:50%;background:var(--c,#6b7a8a)}
.gl{margin-left:auto;display:flex;align-items:center;gap:10px;color:var(--mute);font-size:12px}
.pill{display:inline-block;padding:2px 9px;border-radius:3px;background:var(--c);color:#06100a;font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-weight:800}
.stage{min-height:0;position:relative}
.view{display:none;position:absolute;inset:0;padding:10px;gap:10px;min-height:0}
.v-overview,.v-ukraine,.v-east,.v-mideast{grid-template-columns:minmax(0,1.55fr) minmax(330px,1fr)}
.mapcol{display:flex;flex-direction:column;gap:8px;min-height:0;min-width:0}
.mapbox{position:relative;flex:1;min-height:0;background:#06100f;border:1px solid var(--line);border-radius:4px;overflow:hidden;display:flex}
.map{width:100%;height:100%}
.sea{fill:#071312}
.cty{fill:#162216;stroke:#2c4129;stroke-width:.7}
.cty.lv2{fill:#3a3512}.cty.lv3{fill:#5a2f12}.cty.lv4{fill:#5c1a1c}
.ac.mil{fill:#f5c518;opacity:.9}.ac.lift{fill:#37d5ff;stroke:#06100a;stroke-width:.6}
.hz{fill:#ff4d4f;opacity:.9}.cz{fill:none;stroke:#c792ff;stroke-width:1.6;opacity:.9}
.ck text{fill:#d6e2d3;font:600 12px var(--sans);paint-order:stroke;stroke:#06100a;stroke-width:3px}
.tl rect{fill:#0c150c;fill-opacity:.88;stroke-width:1.5}.tl text{text-anchor:middle;font-family:var(--sans)}
.tl .a{fill:#e6efe4;font-size:11px;font-weight:600}.tl .b{font-size:11px;font-weight:800;letter-spacing:.08em}
.legend{position:absolute;left:8px;bottom:8px;right:8px;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:11px;color:var(--mute);background:rgba(6,16,15,.82);padding:5px 9px;border-radius:3px}
.legend span{display:inline-flex;align-items:center;gap:5px}.legend .miss{color:var(--warn);margin-left:auto}
.sw{width:9px;height:9px;display:inline-block;border-radius:50%}
.sw.cz{border:2px solid #c792ff;background:none}.sw.mil{background:#f5c518}.sw.lift{background:#37d5ff}.sw.hz{background:#ff4d4f;border-radius:0;transform:rotate(45deg) scale(.85)}
.sw.lv2{background:#3a3512;border:1px solid #6d6320;border-radius:2px}.sw.lv3{background:#5a2f12;border:1px solid #8b4a1d;border-radius:2px}.sw.lv4{background:#5c1a1c;border:1px solid #8f2c2f;border-radius:2px}
.hzs{display:flex;gap:14px;align-items:baseline;font-size:11.5px;color:var(--mute);background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:6px 10px;overflow:hidden;white-space:nowrap}
.hzs b{color:var(--ink);flex:none}.hzs span{overflow:hidden;text-overflow:ellipsis;min-width:0}
.side{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:10px 12px;min-height:0;overflow:hidden;display:flex;flex-direction:column}
h4{margin:10px 0 5px;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);font-weight:700;display:flex;justify-content:space-between}
h4:first-child{margin-top:0}
.lvl{border-left:3px solid var(--c);background:var(--panel2);padding:8px 10px;border-radius:3px}
.lvl .lh{display:flex;align-items:center;justify-content:space-between;gap:8px}.lvl .ln{font-weight:700;font-size:14px}
.lvl p{margin:3px 0 0;color:var(--ink)}.lvl .sub{color:var(--mute);font-size:11.5px}.lvl .note{color:var(--warn);font-size:11.5px}
.tcs{display:grid;grid-template-columns:1fr 1fr;gap:8px}.tc .lvl{height:100%}
.tc .lvl p{font-size:11.5px}.tc .lvl .sub{display:none}
.sr{display:grid;grid-template-columns:8px minmax(0,1fr) auto;gap:8px;align-items:center;min-height:24px;border-bottom:1px solid #1a261a}
.sr:has(.dot)>.nm{grid-column:2}.sr:not(:has(.dot)){grid-template-columns:minmax(0,1fr) auto}
.nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.cell{display:flex;align-items:center;gap:7px;justify-content:flex-end}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block}.dot.fast{background:var(--acc)}.dot.lag{background:#5b6b59}
.bar{position:relative;width:84px;height:7px;background:#0a110a;border:1px solid var(--line);border-radius:2px;flex:none}
.bar i{position:absolute;top:0;bottom:0}.bar .c{left:50%;width:1px;background:#4b5e49}.bar .t{width:1px;background:var(--warn);opacity:.8}
.bar .f{background:#5f7a5c}.bar .f.hot{background:var(--bad)}
.v{font:700 12px var(--mono);min-width:38px;text-align:right}.v.hot{color:var(--bad)}
.hotrow .nm{color:#fff;font-weight:600}
.dim .nm{color:var(--mute)}.muted{color:var(--mute);font-size:11.5px}
.mini{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--mute);border:1px solid var(--line);padding:0 5px;border-radius:2px}
.mini.stale{color:#f5c518;border-color:#5b4d10}.mini.bad{color:var(--bad);border-color:#5c1a1c;text-transform:none;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mini.warn{color:var(--warn);border-color:#5a3512}
.cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;height:calc(100% - 30px);min-height:0}
.col{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:10px 12px;overflow:hidden;min-height:0}

.v-supply{display:none;flex-direction:column;gap:8px}.foot{margin:0;color:var(--mute);font-size:11.5px}
.sysg{display:grid;grid-template-columns:1fr 1.2fr;gap:10px;height:100%;min-height:0}
.sysg>div{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:12px 14px;overflow:hidden;min-height:0}
.hstats{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:6px}
.hs{background:var(--panel2);border:1px solid var(--line);border-radius:3px;padding:8px}.hs b{display:block;font:700 22px var(--mono)}.hs span{font-size:11px;color:var(--mute)}
.sysg ul{margin:0 0 8px;padding-left:16px}.sysg li{margin:5px 0}
.demo{background:#f5c518;color:#000;padding:6px 9px;border-radius:3px;font-weight:700}
"""


def render(result, generated, demo=False, extras=None, topo=None):
    series, th = result["series"], result["theatres"]
    worst = min((th[t]["level"] for t in th if t != "global"), key=ORDER.index)
    tabs_def = [("overview", "Overview", worst)]
    for tid, (title, theatre, _) in VIEWS.items():
        tabs_def.append((tid, title, th[theatre]["level"]))
    tabs_def += [("supply", "Supply chain", None), ("system", "System", None)]
    inputs = "".join(f'<input class="r" type="radio" name="tab" id="t-{t}"{" checked" if i == 0 else ""}>'
                     for i, (t, _, _) in enumerate(tabs_def))
    def dot(lv):
        return f"<b style='--c:{LEVEL[lv]}'></b>" if lv else ""
    labels = "".join(f'<label for="t-{t}">{E(n)}{dot(lv)}</label>' for t, n, lv in tabs_def)
    rules = "".join(f'#t-{t}:checked~.app .v-{t}{{display:{"flex" if t == "supply" else "grid"}}}'
                    f'#t-{t}:checked~.app label[for=t-{t}]{{color:var(--ink);border-bottom-color:var(--acc);background:var(--panel2)}}'
                    for t, _, _ in tabs_def)
    views = (overview_view(th, series, topo, extras)
             + "".join(theatre_view(tid, title, theatre, view, th, series, topo, extras) for tid, (title, theatre, view) in VIEWS.items())
             + supply_view(series) + system_view(series, generated, demo))
    banner = '<span class="pill" style="--c:#f5c518">DEMO DATA</span>' if demo else ""
    responsive = ("@media(max-width:900px),(max-height:520px){body{overflow:auto}.app{height:auto;display:block}.top{flex-wrap:wrap;padding:8px}"
                  ".stage{position:static}.view{position:static;padding:8px}.sysg{display:block}"
                  ".mapbox{height:60vh}.cols{grid-template-columns:1fr;height:auto}.tabs{order:3;width:100%;overflow-x:auto;margin:0}.gl{margin-left:auto}"
                  ".view{grid-template-columns:1fr!important}}")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Warwatch early-warning monitor</title>
<meta name="description" content="Public-data early-warning monitor for the US, EU, Ukraine and the Middle East.">
<style>{CSS}{rules}{responsive}</style></head><body>
{inputs}
<div class="app"><header class="top"><div class="brand"><i></i>WARWATCH</div><nav class="tabs" aria-label="Views">{labels}</nav>
<div class="gl">{banner}<span>Updated {E(generated)}</span>{level_pill(worst)}</div></header>
<main class="stage">{views}</main></div></body></html>"""
