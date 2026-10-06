"""One self-contained HTML file: no server, no JS, no cost. Tabs are CSS-only."""
import html

import config as C
import scoring

COL = {"Alert": "#b3261e", "Warning": "#c75b12", "Watch": "#8a6d00", "Normal": "#2e7d32",
       "insufficient data": "#5f6368"}
E = html.escape


def spark(points, w=200, h=36):
    vals = [v for _, v in points][-150:]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 3 - (v - lo) / rng * (h - 6):.1f}" for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="trend">'
            f'<polyline fill="none" stroke="var(--line2)" stroke-width="1.5" points="{pts}"/></svg>')


def card(s):
    tag = "lags ~months" if s["lag"] else "fast"
    if s["status"] == "ok":
        z = scoring.directed(s["score"]["z"], s["direction"])
        body = f'<b class="z{" hot" if z >= C.THRESH_SIGNAL else ""}">{z:+.1f}</b> <span>{E(s["score"]["method"])}</span>'
    elif s["status"] == "collecting":
        body = f'<span class="muted">collecting history ({len(s["points"])} points)</span>'
    elif s["status"] == "awaiting_key":
        body = f'<span class="muted">awaiting key: {E(s["error"])}</span>'
    else:
        body = f'<span class="err">fetch failed: {E(s["error"][:90])}</span>'
    return (f'<div class="s"><div class="t">{E(s["label"])}</div>{body} <i>{tag}</i>'
            f'<div class="why">{E(s["why"])}</div>{spark(s["points"])}</div>')


def panel(t, view, series):
    lv = view["level"]
    basis = f" ({view['basis']})" if view["basis"] else ""
    head = (f'<div class="lvl" style="border-color:{COL[lv]}"><h2 style="color:{COL[lv]}">{E(lv)}{E(basis)}</h2>'
            f'{len(view["firing"])} domain(s) firing: {E(", ".join(C.DOMAINS[d] for d in view["firing"]) or "none")}'
            f' · {view["scorable"]} of {len(C.DOMAINS)} domains scorable</div>')
    secs = []
    for dom, label in C.DOMAINS.items():
        mine = [s for s in series if s["domain"] == dom and s["theatre"] in (t, "global")]
        if not mine:
            continue
        d = view["domains"][dom]
        z = "n/a" if d["z"] is None else f'{d["z"]:+.1f}'
        fire = " fire" if d["z"] is not None and d["z"] >= C.THRESH_SIGNAL else ""
        secs.append(f'<section class="dom{fire}"><h3>{E(label)} <span>{z}</span></h3>'
                    f'<div class="g">{"".join(card(s) for s in mine)}</div></section>')
    return head + "".join(secs)


def render(result, generated, demo=False):
    series, th = result["series"], result["theatres"]
    tabs, panels, css = [], [], []
    for i, (t, name) in enumerate(C.THEATRES.items()):
        lv = th[t]["level"]
        tabs.append(f'<input type="radio" name="tab" id="t-{t}"{" checked" if i == 0 else ""}>'
                    f'<label for="t-{t}" style="--c:{COL[lv]}">{E(name)}<b>{E(lv)}</b></label>')
        panels.append(f'<div class="panel p-{t}">{panel(t, th[t], series)}</div>')
        css.append(f'#t-{t}:checked~.p-{t}{{display:block}}#t-{t}:checked+label{{background:var(--card);box-shadow:inset 0 -3px var(--c)}}')
    stat = {}
    for s in series:
        stat.setdefault(s["status"], []).append(s["id"])
    foot = " · ".join(f"{len(v)} {k.replace('_', ' ')}" for k, v in sorted(stat.items()))
    banner = '<p class="demo">DEMO: synthetic data, not real observations.</p>' if demo else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Warwatch</title><style>
:root{{--bg:#fff;--fg:#1f1f1f;--card:#f1f3f6;--line:#d8dbe0;--line2:#1a73e8}}
@media(prefers-color-scheme:dark){{:root{{--bg:#15171b;--fg:#e8e8e8;--card:#22252b;--line:#363a42;--line2:#6ea8fe}}}}
body{{margin:0 auto;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;max-width:1100px}}
input[name=tab]{{display:none}} label{{display:inline-block;padding:8px 14px;cursor:pointer;border-bottom:1px solid var(--line);margin-right:2px}}
label b{{display:block;font-size:.8rem;color:var(--c)}} .panel{{display:none}}
{"".join(css)}
.lvl{{border-left:8px solid;padding:8px 14px;background:var(--card);margin-top:12px}} .lvl h2{{margin:0}}
.dom{{margin-top:16px;border-top:1px solid var(--line)}} .dom.fire h3{{color:#b3261e}} h3 span{{font-weight:400;opacity:.7}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}}
.s{{background:var(--card);padding:8px 10px;border-radius:6px;font-size:.86rem}} .t{{font-weight:600}}
.z{{font-size:1.1rem}} .z.hot{{color:#b3261e}} i{{opacity:.6;font-size:.75rem}} .why{{opacity:.7;font-size:.78rem}}
.muted{{opacity:.7}} .err{{color:#b3261e}} .demo{{background:#fff3cd;color:#5c4400;padding:6px 10px;border-radius:6px}}
small{{opacity:.7}}</style></head><body>
<h1 style="margin:0">Warwatch</h1><small>Updated {E(generated)} · public data only · decision support, not a prediction</small>
{banner}<div>{"".join(tabs)}{"".join(panels)}</div>
<p><small>Sources: {E(foot)}. A level counts domains moving together, not a probability of war.
Procurement and trade series lag by months; only fast series can lead. Verify with primary sources.</small></p>
</body></html>"""
