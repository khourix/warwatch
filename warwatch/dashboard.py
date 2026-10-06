"""One self-contained HTML file: no server, no build, no cost.

Visual language follows the NVIDIA DESIGN.md (getdesign.md): black chrome and
hero, white body, one green accent, 2px corners, hairline borders, no shadows,
green corner squares on cards. Tabs and filters are CSS-only (radio inputs), so
the page works with JavaScript off.
"""
import html

import config as C
import scoring

E = html.escape

# Level colours come from the design's semantic tokens, never from decoration.
LEVEL = {
    "Alert": ("#e52020", "#ffffff"),
    "Warning": ("#df6500", "#ffffff"),
    "Watch": ("#ef9100", "#000000"),
    "Normal": ("#76b900", "#000000"),
    "insufficient data": ("#a7a7a7", "#000000"),
}
MEANING = {
    "Alert": "Three or more independent signal groups are unusual at the same time.",
    "Warning": "Two signal groups are unusual at the same time.",
    "Watch": "One signal group is strongly unusual, or two are mildly unusual.",
    "Normal": "Nothing is outside its usual range.",
    "insufficient data": "Too few signal groups have enough history to judge.",
}
ORDER = ["Alert", "Warning", "Watch", "Normal", "insufficient data"]
ZMAX = 6.0   # the bar saturates at +/-6 standard deviations; the score itself goes to 12


def spark(points, w=140, h=30):
    vals = [v for _, v in points][-150:]
    if len(vals) < 2:
        return '<span class="nospark">no trend yet</span>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 3 - (v - lo) / rng * (h - 6):.1f}" for i, v in enumerate(vals))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="Recent trend, {len(vals)} points"><polyline fill="none" stroke="currentColor" '
            f'stroke-width="1.5" points="{pts}"/></svg>')


def zbar(z):
    """Diverging bar: centre is normal, right is the warning direction, tick at the signal threshold."""
    frac = max(-1.0, min(1.0, z / ZMAX))
    left, width = (50, frac * 50) if frac >= 0 else (50 + frac * 50, -frac * 50)
    hot = z >= C.THRESH_SIGNAL
    tick = 50 + C.THRESH_SIGNAL / ZMAX * 50
    return (f'<span class="zbar" aria-hidden="true"><i class="zc"></i><i class="zt" style="left:{tick:.1f}%"></i>'
            f'<i class="zf{" hot" if hot else ""}" style="left:{left:.1f}%;width:{width:.1f}%"></i></span>')


def row(s):
    fast = "Leads" if not s["lag"] else "Lags"
    speed = f'<span class="tag {"fast" if not s["lag"] else "slow"}">{fast}</span>'
    if s["status"] == "ok":
        z = scoring.directed(s["score"]["z"], s["direction"])
        hot = z >= C.THRESH_SIGNAL
        value = f'<b class="zv{" hot" if hot else ""}">{z:+.1f}</b>'
        state = ""
        if s.get("stale"):
            state = f'<span class="tag stale" title="The source failed this run; showing the last good data">Stale since {E(s["stale"][:10])}</span>'
        main = zbar(z) + value
    elif s["status"] == "collecting":
        n = len(s["points"])
        main = f'<span class="state">Building history ({n} reading{"s" if n != 1 else ""})</span>'
        state = '<span class="tag wait">Collecting</span>'
    elif s["status"] == "awaiting_key":
        main = '<span class="state">Needs an access key</span>'
        state = '<span class="tag wait">Setup</span>'
    else:
        main = '<span class="state bad">Source did not respond</span>'
        state = '<span class="tag fail">Failed</span>'
    detail = [f'<p>{E(s["why"])}</p>']
    if s["status"] == "ok":
        detail.append(f'<p class="meta">Method: {E(s["score"]["method"])}</p>')
    if s["error"] and s["status"] in ("error", "awaiting_key"):
        detail.append(f'<p class="meta">Detail: {E(s["error"][:160])}</p>')
    if s.get("url"):
        detail.append(f'<p class="meta"><a href="{E(s["url"])}" rel="noopener">Source</a></p>')
    hotrow = " hotrow" if s["status"] == "ok" and scoring.directed(s["score"]["z"], s["direction"]) >= C.THRESH_SIGNAL else ""
    return (f'<details class="sig st-{s["status"]}{" stalerow" if s.get("stale") else ""}{hotrow}" data-fast="{0 if s["lag"] else 1}">'
            f'<summary><span class="nm">{E(s["label"])}</span><span class="vis">{main}</span>'
            f'<span class="spk">{spark(s["points"])}</span><span class="tags">{speed}{state}</span></summary>'
            f'<div class="more">{"".join(detail)}</div></details>')


def domain_block(label, d, mine):
    fire = d["z"] is not None and d["z"] >= C.THRESH_SIGNAL
    z = "not enough data" if d["z"] is None else f'{d["z"]:+.1f}'
    badge = '<span class="tag fire">Unusual</span>' if fire else ""
    live = sum(1 for s in mine if s["status"] == "ok")
    return (f'<section class="dom{" fire" if fire else ""}"><header><h3>{E(label)}</h3>'
            f'<span class="dz">Group score {z}</span>{badge}'
            f'<span class="cnt">{live} of {len(mine)} signals live</span></header>'
            f'{"".join(row(s) for s in mine)}</section>')


def panel(t, view, series):
    blocks = []
    for dom, label in C.DOMAINS.items():
        mine = [s for s in series if s["domain"] == dom and s["theatre"] in (t, "global")]
        if mine:
            blocks.append(domain_block(label, view["domains"][dom], mine))
    return "".join(blocks)


def movers(series, n=6):
    out = []
    for s in series:
        if s["status"] == "ok":
            z = scoring.directed(s["score"]["z"], s["direction"])
            out.append((z, s))
    out.sort(key=lambda x: -x[0])
    return out[:n]


def theatre_card(t, name, v, series):
    lv = v["level"]
    bg, fg = LEVEL[lv]
    firing = ", ".join(C.DOMAINS[d] for d in v["firing"]) or "none"
    live = sum(1 for s in series if s["status"] == "ok" and s["theatre"] in (t, "global"))
    total = sum(1 for s in series if s["theatre"] in (t, "global"))
    lag = '<p class="warn">Only slow-moving data is unusual, so this is a confirmation, not an early signal.</p>' \
        if "lagging" in (v.get("basis") or "") else ""
    return (f'<label class="tcard" for="t-{t}"><span class="cs"></span><span class="tn">{E(name)}</span>'
            f'<span class="lvlbadge" style="background:{bg};color:{fg}">{E(lv)}</span>'
            f'<span class="tm">{E(MEANING[lv])}</span><span class="tf">Unusual groups: {E(firing)}</span>'
            f'<span class="tf">{live} of {total} signals live</span>{lag}</label>')


CSS = """
:root{--primary:#76b900;--primary-dark:#5a8d00;--ink:#000;--canvas:#fff;--dark:#000;--soft:#f7f7f7;--elev:#1a1a1a;
--hair:#ccc;--hair-strong:#5e5e5e;--body:#1a1a1a;--mute:#757575;--stone:#898989;--on-dark:#fff;--on-dark-mute:rgba(255,255,255,.7);
--link:#0046a4;--error:#e52020;--warn:#df6500;--ok-deep:#3f8500;
--font:'Inter','NVIDIA-EMEA',Arial,Helvetica,sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--canvas);color:var(--ink);font:400 16px/1.5 var(--font);-webkit-font-smoothing:antialiased}
a{color:var(--link)}
:focus-visible{outline:2px solid var(--primary);outline-offset:2px}
.wrap{max-width:1280px;margin:0 auto;padding:0 24px}
/* chrome */
.nav{position:sticky;top:0;z-index:20;background:var(--dark);color:var(--on-dark);border-bottom:1px solid var(--hair-strong);box-shadow:0 5px 5px rgba(0,0,0,.2)}
.nav .wrap{display:flex;align-items:center;gap:16px;height:56px}
.brand{font-weight:700;font-size:16px;letter-spacing:.08em;text-transform:uppercase;display:flex;align-items:center;gap:10px}
.brand i{width:12px;height:12px;background:var(--primary);display:inline-block}
.nav .upd{margin-left:auto;font-size:12px;color:var(--on-dark-mute)}
.nav a.jump{color:var(--on-dark);font-weight:700;font-size:14px;text-decoration:none;padding:8px 12px;border:1px solid var(--hair-strong);border-radius:2px}
.nav a.jump:hover{border-color:var(--primary)}
.hero{background:var(--dark);color:var(--on-dark);padding:48px 0 40px}
.hero h1{font-size:40px;line-height:1.25;margin:0 0 12px;font-weight:700;max-width:760px}
.hero p.lead{font-size:18px;color:var(--on-dark-mute);margin:0 0 32px;max-width:760px}
.demo{background:var(--accent,#feeeb2);color:#000;padding:10px 14px;border-radius:2px;font-weight:700;margin:0 0 24px}
.tgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
input.r{position:absolute;opacity:0;pointer-events:none}
.tcard{position:relative;display:flex;flex-direction:column;gap:8px;padding:24px;background:var(--elev);border:1px solid var(--hair-strong);border-radius:2px;cursor:pointer;min-height:200px;color:var(--on-dark)}
.tcard:hover{border-color:var(--primary)}
.tcard .cs{position:absolute;top:0;left:0;width:12px;height:12px;background:var(--primary)}
.tn{font-weight:700;font-size:20px;line-height:1.25}
.lvlbadge{align-self:flex-start;font-weight:700;font-size:14px;text-transform:uppercase;letter-spacing:.4px;padding:4px 10px;border-radius:2px}
.tm{font-size:15px;color:var(--on-dark)}
.tf{font-size:13px;color:var(--on-dark-mute)}
.warn{font-size:13px;color:#ef9100;margin:0}
/* sub-nav */
.sub{background:var(--soft);border-bottom:1px solid var(--hair);position:sticky;top:56px;z-index:10}
.sub .wrap{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding-top:10px;padding-bottom:10px}
.sub .lab{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--mute);margin-right:4px}
.pill{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:2px;border:1px solid var(--hair);background:var(--canvas);font-weight:700;font-size:14.4px;cursor:pointer;min-height:44px}
.pill b{font-size:12px;padding:2px 6px;border-radius:2px}
.sep{width:1px;align-self:stretch;background:var(--hair);margin:0 8px}
.chip{padding:10px 14px;border-radius:2px;border:1px solid var(--hair);background:var(--canvas);font-weight:700;font-size:13px;cursor:pointer;min-height:44px;display:inline-flex;align-items:center}
/* panels */
.panel{display:none;padding:40px 0 24px}
main{padding-bottom:24px}
.phead h2{font-size:28px;line-height:1.25;margin:0 0 8px}
.phead p{margin:0 0 24px;color:var(--body);max-width:820px}
.movers{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin:0 0 32px}
.mv{position:relative;border:1px solid var(--hair);border-radius:2px;padding:16px 16px 16px 20px}
.mv::before{content:"";position:absolute;top:0;left:0;width:12px;height:12px;background:var(--primary)}
.mv b{display:block;font-size:28px;line-height:1.25}.mv b.hot{color:var(--error)}
.mv span{font-size:14px;color:var(--body)}
.dom{border:1px solid var(--hair);border-radius:2px;margin:0 0 24px;position:relative;background:var(--canvas)}
.dom::before{content:"";position:absolute;top:-1px;left:-1px;width:12px;height:12px;background:var(--primary)}
.dom.fire{border-color:var(--error)}
.dom header{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px;padding:20px 24px 12px 28px}
.dom h3{margin:0;font-size:20px;line-height:1.25}
.dz{font-size:14px;color:var(--mute)}.cnt{font-size:13px;color:var(--mute);margin-left:auto}
.sig{border-top:1px solid var(--hair)}
.sig summary{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2.2fr) 150px minmax(0,1.5fr);gap:16px;align-items:center;padding:12px 24px 12px 28px;cursor:pointer;list-style:none;min-height:56px}
.sig summary::-webkit-details-marker{display:none}
.sig summary:hover{background:var(--soft)}
.nm{font-size:15px;font-weight:700;line-height:1.4}
.vis{display:flex;align-items:center;gap:10px}
.zbar{position:relative;display:inline-block;width:150px;height:10px;background:var(--soft);border:1px solid var(--hair);border-radius:2px;flex:none}
.zbar i{position:absolute;top:0;bottom:0}
.zc{left:50%;width:1px;background:var(--stone)}
.zt{width:1px;background:var(--warn);opacity:.7}
.zf{background:var(--stone)}.zf.hot{background:var(--error)}
.zv{font-size:16px;min-width:46px;text-align:right}.zv.hot{color:var(--error)}
.state{font-size:14px;color:var(--mute)}.state.bad{color:var(--error);font-weight:700}
.spk{color:var(--mute)}.nospark{font-size:12px;color:var(--stone)}
.tags{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}
.tag{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;padding:3px 8px;border-radius:2px;background:var(--soft);color:var(--body);border:1px solid var(--hair);line-height:1.2}
.tag.fast{background:#000;color:var(--primary);border-color:#000}
.tag.fire{background:var(--error);color:#fff;border-color:var(--error)}
.tag.fail{background:#fff;color:var(--error);border-color:var(--error)}
.tag.stale{background:#feeeb2;border-color:#ef9100;color:#000}
.more{padding:4px 28px 18px;background:var(--soft);border-top:1px solid var(--hair)}
.more p{margin:8px 0 0;font-size:15px;max-width:820px}.more .meta{font-size:13px;color:var(--mute)}
.sig.st-error summary .nm,.sig.st-awaiting_key summary .nm,.sig.st-collecting summary .nm{font-weight:400;color:var(--body)}
/* filters (CSS only) */
#f-moving:checked~main .sig:not(.hotrow){display:none}
#f-problems:checked~main .sig.st-ok:not(.stalerow){display:none}
#f-fast:checked~main .sig[data-fast="0"]{display:none}
#f-fast:checked~main .dom:not(:has(.sig[data-fast="1"])){display:none}
#f-moving:checked~main .dom:not(:has(.hotrow)){display:none}
#f-problems:checked~main .dom:not(:has(.sig:not(.st-ok))):not(:has(.stalerow)){display:none}
.sub .chip,.sub .pill{position:relative}
.health{margin:40px 0 0}
.health h2,.method h2{font-size:28px;line-height:1.25;margin:0 0 8px}
.hstats{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin:16px 0}
.hs{border:1px solid var(--hair);border-radius:2px;padding:16px;position:relative}
.hs::before{content:"";position:absolute;top:0;left:0;width:12px;height:12px;background:var(--primary)}
.hs b{display:block;font-size:28px;line-height:1.25}.hs span{font-size:14px;color:var(--mute)}
.method{background:var(--soft);border-top:1px solid var(--hair);padding:48px 0;margin-top:40px}
.method ul{margin:12px 0 0;padding-left:20px;max-width:820px}.method li{margin:6px 0}
footer{background:var(--dark);color:var(--on-dark-mute);padding:48px 0;font-size:14px}
footer p{max-width:820px;margin:0 0 12px}
@media(max-width:1024px){.tgrid{grid-template-columns:repeat(2,1fr)}.sig summary{grid-template-columns:1fr 1fr;gap:8px 16px}.spk{display:none}.tags{justify-content:flex-start}}
@media(max-width:600px){.sub .wrap{flex-wrap:nowrap;overflow-x:auto;white-space:nowrap}.wrap{padding:0 16px}.hero h1{font-size:28px}.hero p.lead{font-size:16px}.tgrid{grid-template-columns:1fr}.nav .upd{display:none}
.sig summary{grid-template-columns:1fr}.zbar{width:100%;max-width:220px}.dom header{padding:16px 16px 8px 20px}.sig summary,.more{padding-left:20px;padding-right:16px}.cnt{margin-left:0}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def render(result, generated, demo=False):
    series, th = result["series"], result["theatres"]
    # mark rows that are unusual right now so the "Moving" filter can find them
    out_series = []
    for s in series:
        out_series.append(s)
    names = list(C.THEATRES.items())
    inputs, tabs, panels, rules = [], [], [], []
    for i, (t, name) in enumerate(names):
        bg, fg = LEVEL[th[t]["level"]]
        inputs.append(f'<input class="r" type="radio" name="tab" id="t-{t}"{" checked" if i == 0 else ""}>')
        tabs.append(f'<label class="pill" for="t-{t}">{E(name)} <b style="background:{bg};color:{fg}">{E(th[t]["level"])}</b></label>')
        v = th[t]
        top = movers([s for s in series if s["theatre"] in (t, "global")])
        mv = "".join(f'<div class="mv"><b class="{"hot" if z >= C.THRESH_SIGNAL else ""}">{z:+.1f}</b>'
                     f'<span>{E(s["label"])}</span></div>' for z, s in top)
        lv = v["level"]
        panels.append(
            f'<div class="panel p-{t}"><div class="wrap"><div class="phead"><h2>{E(name)}: {E(lv)}</h2>'
            f'<p>{E(MEANING[lv])} Scores show how far each signal is from its own recent normal, in standard '
            f'deviations. Above +{C.THRESH_SIGNAL:.1f} counts as unusual.</p></div>'
            f'<h3 style="margin:0 0 12px;font-size:20px">Biggest movers</h3><div class="movers">{mv or "<p>No signals have enough history yet.</p>"}</div>'
            f'{panel(t, v, series)}</div></div>')
        rules.append(f'#t-{t}:checked~main .p-{t}{{display:block}}'
                     f'#t-{t}:checked~.sub label[for=t-{t}]{{background:var(--ink);color:var(--on-dark);border-color:var(--ink)}}')
    for f in ("all", "moving", "fast", "problems"):
        rules.append(f'#f-{f}:checked~.sub label[for=f-{f}]{{background:var(--primary);color:#000;border-color:var(--primary)}}')
    cards = "".join(theatre_card(t, name, th[t], series) for t, name in names)
    stat = {}
    for s in series:
        key = "stale" if s.get("stale") else s["status"]
        stat[key] = stat.get(key, 0) + 1
    hs = [("ok", "Live"), ("stale", "Stale (last good data)"), ("collecting", "Building history"),
          ("awaiting_key", "Need a key"), ("error", "Failed")]
    health = "".join(f'<div class="hs"><b>{stat.get(k, 0)}</b><span>{lbl}</span></div>' for k, lbl in hs)
    banner = '<p class="demo">DEMO: this page shows synthetic data, not real observations.</p>' if demo else ""
    worst = min((th[t]["level"] for t in th), key=ORDER.index)
    headline = {
        "Alert": "Several signal groups are unusual together.",
        "Warning": "Two signal groups are unusual together.",
        "Watch": "One area needs a closer look.",
        "Normal": "No theatre is showing unusual activity.",
        "insufficient data": "Not enough history yet to judge.",
    }[worst]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Warwatch: early-warning dashboard</title>
<meta name="description" content="Public-data early-warning indicators for the US, EU, Ukraine and the Middle East.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}{"".join(rules)}</style></head><body>
{"".join(inputs)}
<input class="r" type="radio" name="flt" id="f-all" checked><input class="r" type="radio" name="flt" id="f-moving">
<input class="r" type="radio" name="flt" id="f-fast"><input class="r" type="radio" name="flt" id="f-problems">
<header class="nav"><div class="wrap"><div class="brand"><i></i>Warwatch</div>
<span class="upd">Updated {E(generated)}</span><a class="jump" href="#health">Data health</a></div></header>
<section class="hero"><div class="wrap">{banner}<h1>{E(headline)}</h1>
<p class="lead">A watch-list built only from public data. It counts how many independent signal groups (kit, vehicles, medical, infrastructure, flows, attention, markets) are unusual at once. It is decision support, not a forecast.</p>
<div class="tgrid">{cards}</div></div></section>
<nav class="sub" aria-label="Theatre and filters"><div class="wrap"><span class="lab">Theatre</span>{"".join(tabs)}
<span class="sep"></span><span class="lab">Show</span>
<label class="chip" for="f-all">All</label><label class="chip" for="f-moving">Unusual only</label>
<label class="chip" for="f-fast">Early signals only</label><label class="chip" for="f-problems">Problems only</label></div></nav>
<main>{"".join(panels)}
<div class="wrap health" id="health"><h2>Data health</h2><p>Every source is checked on each refresh. A failed source keeps its last good data and is marked stale; it is never read as calm.</p>
<div class="hstats">{health}</div></div></main>
<section class="method"><div class="wrap"><h2>How to read this</h2><ul>
<li><b>Score.</b> How far a signal is from its own usual range for that time of year, in standard deviations. About 1 in 100 calm readings crosses +{C.THRESH_SIGNAL:.1f} by chance.</li>
<li><b>Levels.</b> Watch: one group strongly unusual, or two mildly. Warning: two groups. Alert: three or more. The level counts agreeing groups; it is not a probability of war.</li>
<li><b>Leads or lags.</b> Contract awards and trade statistics are published weeks to months late and can only confirm. Tenders, news, flights, shipping and attention data are fast and can lead.</li>
<li><b>Coverage.</b> US and EU supply data first, then Ukraine and the Middle East. Global signals appear in every theatre.</li>
<li><b>Limits.</b> No backtest against past conflicts has been run yet. Treat a Watch as a reason to look at primary sources, not as a conclusion.</li></ul></div></section>
<footer><div class="wrap"><p>Public data only: USAspending, Eurostat Comext, TED, US Census, SAM.gov, IMF PortWatch, FCDO and US State Department advisories, GDELT, Wikipedia, ADS-B, FRED and others. No private or client data.</p>
<p>Open source: github.com/khourix/warwatch</p></div></footer>
</body></html>"""
