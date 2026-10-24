"""The link-preview card (what Twitter, WhatsApp and Slack show when someone shares the page). Standard library only.

run.py writes og-card.html next to the page: a 1200x630 page with today's headline, three counts and a globe centred on
the Middle East with each theatre coloured by its level. The workflow screenshots it into og.jpg with the runner's Chrome;
if that step fails, the static og.jpg from static/ stays in place.
"""
import datetime as dt
import html
import math

import config as C
import geo

W, H = 1200, 630
LEVEL_FILL = {"Watch": "#e9b44c", "Elevated": "#f28a3e", "Critical": "#f0524f"}
WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
SITE = "khourix.github.io/warwatch"


def _level(v):
    return v.get("level") if v.get("level") in LEVEL_FILL else "Normal"


def _tells_on(v):
    return sum(1 for x in v.get("tells") or [] if x.get("on"))


def _join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def summary(data):
    """-> (headline, facts) for the card and the share text. Theatres are in config order, the 'global' row is left out."""
    ths = [(t, data["theatres"][t]) for t in data.get("order", data["theatres"]) if t in data["theatres"] and t != "global"]
    up = sorted([(t, v) for t, v in ths if _level(v) != "Normal"], key=lambda tv: -list(LEVEL_FILL).index(_level(tv[1])))
    tells = sum(_tells_on(v) for _, v in ths)
    if not up:
        a = "Every theatre reads quiet."
    elif len(up) == 1:
        a = f"{up[0][1]['name']} is the only theatre above quiet."
    else:
        a = f"{_join([v['name'] for _, v in up])} are above quiet." if len(up) <= 3 else f"{WORDS[len(up)] if len(up) < len(WORDS) else len(up)} theatres are above quiet, led by {up[0][1]['name']}."
    word = WORDS[tells] if tells < len(WORDS) else str(tells)
    b = f" {word} timing tell{'' if tells == 1 else 's'} fired this week."
    bases = sum(1 for b_ in ((data.get("map") or {}).get("bases") or []) if b_.get("st") in ("out", "in", "changed"))
    signals = sum(1 for s in data.get("series") or [] if not s.get("tf"))
    return a + b, {"tells": tells, "bases": bases, "theatres": len(ths), "signals": signals}


# ---- orthographic globe ----

class Ortho:
    def __init__(self, lon0, lat0, r, cx, cy):
        self.l0, self.p0 = math.radians(lon0), math.radians(lat0)
        self.r, self.cx, self.cy = r, cx, cy

    def cos_c(self, lon, lat):
        p, dl = math.radians(lat), math.radians(lon) - self.l0
        return math.sin(self.p0) * math.sin(p) + math.cos(self.p0) * math.cos(p) * math.cos(dl)

    def xy(self, lon, lat):
        p, dl = math.radians(lat), math.radians(lon) - self.l0
        x = math.cos(p) * math.sin(dl)
        y = math.cos(self.p0) * math.sin(p) - math.sin(self.p0) * math.cos(p) * math.cos(dl)
        return self.cx + self.r * x, self.cy - self.r * y

    def edge(self, a, b):
        """The point where the segment a (visible) -> b (hidden) crosses the horizon, pushed onto the rim."""
        lo, hi = 0.0, 1.0
        for _ in range(18):
            m = (lo + hi) / 2
            q = (a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m)
            lo, hi = (m, hi) if self.cos_c(*q) > 0 else (lo, m)
        x, y = self.xy(a[0] + (b[0] - a[0]) * lo, a[1] + (b[1] - a[1]) * lo)
        ang = math.atan2(y - self.cy, x - self.cx)
        return ang, (self.cx + self.r * math.cos(ang), self.cy + self.r * math.sin(ang))

    def arc(self, a0, a1, steps_per_rad=24):
        d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi   # the shorter way round the rim
        n = max(1, int(abs(d) * steps_per_rad))
        return [(self.cx + self.r * math.cos(a0 + d * i / n), self.cy + self.r * math.sin(a0 + d * i / n)) for i in range(1, n)]


def _ring_path(pr, ring, closed=True):
    """SVG path data for one ring, clipped to the visible hemisphere. Closed rings follow the rim where they leave it."""
    vis = [pr.cos_c(*p) > 0 for p in ring]
    if not any(vis):
        return ""
    pts, out_ang, parts = [], None, []
    for i, p in enumerate(ring):
        if i and vis[i] != vis[i - 1]:
            if vis[i]:   # coming back into view
                ang, q = pr.edge(p, ring[i - 1])
                if closed and out_ang is not None:
                    pts.extend(pr.arc(out_ang, ang))
                elif not closed:
                    parts.append(pts)
                    pts = []
                pts.append(q)
            else:
                ang, q = pr.edge(ring[i - 1], p)
                pts.append(q)
                out_ang = ang
        if vis[i]:
            pts.append(pr.xy(*p))
    parts.append(pts)
    d = []
    for seg in parts:
        last, keep = None, []
        for x, y in seg:   # drop points closer than about a pixel: the 50m outlines are far finer than the card needs
            if last is None or abs(x - last[0]) + abs(y - last[1]) > 1.2:
                keep.append((x, y))
                last = (x, y)
        if len(keep) > (2 if closed else 1):
            d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in keep) + ("Z" if closed else ""))
    return "".join(d)


def globe_svg(topo, data, cx=900, cy=315, r=380, lon0=40, lat0=26, focus=None):
    """focus: a theatre id. Its countries are outlined in radar blue and it alone keeps a label."""
    pr = Ortho(lon0, lat0, r, cx, cy)
    mine = C.THEATRES.get(focus, {}).get("countries", []) if focus else []   # the first is the theatre itself, the rest are drawn in
    fill = {}   # country -> (level, primary): the theatre's first country carries its colour, the rest a faint tint
    for t, th in C.THEATRES.items():
        lv = _level(data["theatres"].get(t) or {})
        for i, name in enumerate(th.get("countries", [])):
            old = fill.get(name, ("Normal", False))
            rank = lambda x: (list(LEVEL_FILL).index(x[0]) + 1 if x[0] in LEVEL_FILL else 0, x[1])
            fill[name] = max(old, (lv, i == 0), key=rank) if name in fill else (lv, i == 0)
    land = []
    for _cid, name, rings in geo.countries(topo) if topo else []:
        if name in geo.SKIP:
            continue
        d = "".join(_ring_path(pr, ring) for ring in rings)
        if not d:
            continue
        lv, primary = fill.get(name, (None, False))
        if name == (mine or [None])[0]:
            col = LEVEL_FILL.get(_level(data["theatres"].get(focus) or {}))
            land.append(f'<path d="{d}" fill="{col or "#2a3446"}" fill-opacity="{".75" if col else "1"}" stroke="#7da8ff" stroke-width="1.8"/>')
        elif name in mine:
            land.append(f'<path d="{d}" fill="#1f2632" stroke="#7da8ff" stroke-opacity=".45" stroke-width=".8"/>')
        elif lv in LEVEL_FILL:
            land.append(f'<path d="{d}" fill="{LEVEL_FILL[lv]}" fill-opacity="{".7" if primary else ".12"}" stroke="#2b3342" stroke-width=".6"/>')
        else:
            land.append(f'<path d="{d}" fill="{"#1f2632" if lv else "#161b23"}" stroke="#2b3342" stroke-width=".6"/>')
    grat = []
    for lon in range(-180, 180, 20):
        grat.append(_ring_path(pr, [(lon, la) for la in range(-80, 81, 2)], closed=False))
    for la in range(-60, 61, 20):
        grat.append(_ring_path(pr, [(lo, la) for lo in range(-180, 181, 2)], closed=False))
    dots, cand = [], []
    for t in C.THEATRES:
        v = data["theatres"].get(t) or {}
        if t not in C.BOXES:
            continue
        la0, la1, lo0, lo1 = C.BOXES[t]
        lon, lat = (lo0 + lo1) / 2, (la0 + la1) / 2
        if pr.cos_c(lon, lat) < 0.35:
            continue
        x, y = pr.xy(lon, lat)
        if not (0 < x < W and 0 < y < H - 90):   # off the card, or under the footer line
            continue
        lv, n = _level(v), _tells_on(v)
        if focus and t != focus:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{LEVEL_FILL.get(lv, "#7a8597")}" fill-opacity=".8"/>')
        elif lv == "Normal" and not n and t != focus:
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#7a8597" fill-opacity=".8"/>')
        else:
            cand.append((-(list(LEVEL_FILL).index(lv) + 1 if lv in LEVEL_FILL else 0), -n, x, y, lv, n, v.get("name", t)))
    chips, boxes = [], []
    for _, _, x, y, lv, n, name in sorted(cand):   # the highest level keeps its label; one that would overlap it becomes a dot
        w = 40 + len(name) * 8.6 + (30 if n else 0)
        box = (x - 14, y - 15, x - 14 + w, y + 15)
        if any(box[0] < o[2] + 4 and o[0] < box[2] + 4 and box[1] < o[3] + 4 and o[1] < box[3] + 4 for o in boxes):
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{LEVEL_FILL.get(lv, "#7a8597")}"/>')
            continue
        boxes.append(box)
        chips.append(f'<div class="chip" style="left:{box[0]:.0f}px;top:{box[1]:.0f}px"><i style="background:{LEVEL_FILL.get(lv, "#7a8597")}"></i>'
                     f'{html.escape(name)}{f"<em>{n}</em>" if n else ""}</div>')
    return (f'<svg class="globe" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="IBM Plex Sans">'
            f'<defs><radialGradient id="glow"><stop offset=".6" stop-color="#7da8ff" stop-opacity=".10"/><stop offset="1" stop-color="#7da8ff" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="sea" cx=".42" cy=".38"><stop offset="0" stop-color="#0d1119"/><stop offset="1" stop-color="#07090c"/></radialGradient>'
            f'<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="#090b0f"/><stop offset=".45" stop-color="#090b0f" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="fade2" x1="0" x2="1"><stop offset="0" stop-color="#090b0f" stop-opacity=".9"/><stop offset=".5" stop-color="#090b0f" stop-opacity=".72"/><stop offset="1" stop-color="#090b0f" stop-opacity="0"/></linearGradient></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 1.18:.0f}" fill="url(#glow)"/><circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#sea)" stroke="#2b3342"/>'
            f'<path d="{"".join(grat)}" fill="none" stroke="rgba(148,163,190,.07)"/>{"".join(land)}'
            + (f'<rect x="0" y="0" width="900" height="{H}" fill="url(#fade2)"/>' if focus else f'<rect x="{cx - r - 2}" y="0" width="{r * 1.2:.0f}" height="{H}" fill="url(#fade)"/>')
            + f'{"".join(dots)}</svg>'
            + "".join(chips))


MARK = ('<svg width="44" height="44" viewBox="0 0 32 32" fill="none"><path d="M3 9.5 9.6 24 16 13.6 22.4 24 26.2 15.4" stroke="#e9edf3" '
        'stroke-width="3.1" stroke-linecap="round" stroke-linejoin="round"/><circle cx="28" cy="10.4" r="3.1" fill="#7da8ff"/></svg>')


def _when(data):
    gen = data.get("generated", "")
    try:
        g = dt.datetime.strptime(gen, "%Y-%m-%d %H:%M UTC")
        return f"{g.day} {g:%b %Y} · {g:%H:%M} UTC"
    except ValueError:
        return gen


def _style(size):
    """The card's fonts and layout, shared by the site card and the theatre cards."""
    font = lambda fam, fn, wt: f'@font-face{{font-family:"{fam}";src:url({fn}) format("woff2");font-weight:{wt}}}'
    fonts = "".join([font("IBM Plex Sans", "plex-sans-latin-400.woff2", 400), font("IBM Plex Sans", "plex-sans-latin-500.woff2", 500),
                     font("IBM Plex Sans", "plex-sans-latin-600.woff2", 600), font("IBM Plex Mono", "plex-mono-latin-400.woff2", 400),
                     font("Source Serif 4", "source-serif-latin-400.woff2", 400)])
    return f"""{fonts}
*{{box-sizing:border-box}}body{{margin:0;width:{W}px;height:{H}px;background:#090b0f;color:#e9edf3;font-family:"IBM Plex Sans",sans-serif;overflow:hidden;position:relative}}
.globe{{position:absolute;left:0;top:0}}
.wm{{position:absolute;left:72px;top:60px;display:flex;align-items:center;gap:14px;font-size:30px;font-weight:600;letter-spacing:-.015em}}
h1{{font-family:"Source Serif 4",Georgia,serif;font-weight:400;font-size:{size}px;line-height:1.12;letter-spacing:-.01em;margin:0;position:absolute;left:72px;top:150px;width:640px}}
.chip{{position:absolute;display:flex;align-items:center;gap:8px;height:30px;padding:0 12px 0 10px;border-radius:15px;background:rgba(15,18,24,.92);border:1px solid rgba(148,163,190,.3);font-size:15px;font-weight:500;white-space:nowrap}}
.chip i{{width:8px;height:8px;border-radius:50%}}.chip em{{font-style:normal;font-size:12px;font-weight:600;color:#e9b44c;background:rgba(233,180,76,.18);border-radius:5px;padding:1px 5px}}
.facts{{position:absolute;left:72px;top:398px;display:flex;gap:44px}}.facts div{{font-size:20px;color:#a5aebd;line-height:1.3}}
.facts b{{display:block;font-size:44px;font-weight:500;font-variant-numeric:tabular-nums}}
.foot{{position:absolute;left:72px;right:72px;bottom:54px;display:flex;justify-content:space-between;font-family:"IBM Plex Mono",monospace;font-size:20px;color:#7a8597}}"""


def _fact(n, label, col="#e9edf3"):
    return f'<div><b style="color:{col}">{n}</b>{label}</div>'


def card_html(data, topo, fallback=False):
    """fallback: the timeless card committed as static/og.jpg, shown if the workflow cannot screenshot today's card."""
    head, f = summary(data)
    when = _when(data)
    if fallback:
        data = dict(data, theatres={t: {"name": v.get("name", t)} for t, v in data["theatres"].items()})
        head, when = f"Early warning for {f['theatres']} war theatres, from {f['signals'] // 50 * 50}+ public signals.", "Updated every 30 minutes"
    size = 54 if len(head) <= 64 else 48 if len(head) <= 96 else 42
    fact = _fact
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>WarWatch share card</title><style>{_style(size)}
</style></head><body>{globe_svg(topo, data)}<div class="wm">{MARK}WarWatch</div><h1>{html.escape(head)}</h1>
<div class="facts"{' style="display:none"' if fallback else ''}>{fact(f["tells"], "timing tells<br>this week", "#e9b44c" if f["tells"] else "#e9edf3")}{fact(f["bases"], "bases changed<br>on radar", "#f28a3e" if f["bases"] else "#e9edf3")}{fact(f["theatres"], f"theatres,<br>{f['signals']} signals")}</div>
<div class="foot"><span>{SITE}</span><span>{html.escape(when)}</span></div></body></html>
"""


# ---- one card per theatre, for /warwatch/<theatre>/ ----

LEVEL_WORD = {"Normal": "Quiet", "Watch": "Watch", "Elevated": "Elevated", "Critical": "Critical"}


def theatre_headline(name, level, tells):
    """'Iran reads quiet. No timing tells fired this week.' Also the share text on the theatre's page (pages.py)."""
    lv = level if level in LEVEL_FILL else "Normal"
    word = WORDS[tells] if tells < len(WORDS) else str(tells)
    return (f"{name} reads quiet." if lv == "Normal" else f"{name} reads {lv.lower()}.") + f" {word} timing tell{'' if tells == 1 else 's'} fired this week."


def theatre_summary(data, t):
    """-> (headline, facts) for one theatre's card and share text."""
    v = data["theatres"][t]
    lv, n = _level(v), _tells_on(v)
    name = v.get("name", t)
    strong = sum(1 for s in data.get("series") or [] if s.get("t") == t and s.get("st") == "ok" and s.get("z") is not None and abs(s["z"]) >= 3)
    bases = sum(1 for b_ in ((data.get("map") or {}).get("bases") or []) if b_.get("th") == t and b_.get("st") in ("out", "in", "changed"))
    ctx = (getattr(C, "CONTEXT", {}).get(t) or (None,))[0]
    return theatre_headline(name, lv, n), {"tells": n, "strong": strong, "bases": bases, "level": lv, "context": ctx, "name": name}


def theatre_card_html(data, topo, t):
    head, f = theatre_summary(data, t)
    view = C.THEATRES[t].get("view") or (20, 60, 10, 40)
    lon0, lat0 = (view[0] + view[1]) / 2, (view[2] + view[3]) / 2
    span = math.radians(max(view[1] - view[0], 8)) * max(math.cos(math.radians(lat0)), .3)
    r = min(3200, max(380, 470 / span))   # the theatre's usual view about fills the right half of the card
    col = LEVEL_FILL.get(f["level"], "#a5aebd")
    pill = (f'<span class="lv" style="color:{col};border-color:{col}">{LEVEL_WORD[f["level"]]}</span>'
            + (f'<span class="ctx">{html.escape(f["context"])}</span>' if f["context"] else ""))
    fact = _fact
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>WarWatch share card: {html.escape(f["name"])}</title><style>{_style(40)}
h1{{top:196px;width:600px}}.name{{position:absolute;left:72px;top:128px;display:flex;align-items:center;gap:14px;font-size:22px;color:#a5aebd}}
.name b{{font-size:22px;font-weight:600;color:#e9edf3}}.lv{{border:1.5px solid;border-radius:8px;padding:2px 10px;font-size:17px;font-weight:600}}.ctx{{font-size:18px}}
</style></head><body>{globe_svg(topo, data, cx=860, cy=315, r=r, lon0=lon0, lat0=lat0, focus=t)}<div class="wm">{MARK}WarWatch</div>
<div class="name"><b>{html.escape(f["name"])}</b>{pill}</div><h1>{html.escape(head)}</h1>
<div class="facts">{fact(f["tells"], "timing tells<br>this week", "#e9b44c" if f["tells"] else "#e9edf3")}{fact(f["strong"], "strong readings<br>3 SD or more", "#f28a3e" if f["strong"] else "#e9edf3")}{fact(f["bases"], "bases changed<br>on radar", "#f28a3e" if f["bases"] else "#e9edf3")}</div>
<div class="foot"><span>{SITE}/{t}</span><span>{html.escape(_when(data))}</span></div></body></html>
"""


def write_cards(out_dir, data, topo):
    """og-card.html for the site and og-card-<theatre>.html for each theatre, next to the page. The workflow screenshots them
    into og.jpg and og/<theatre>.jpg. A theatre whose card fails is skipped; its page then falls back to og.jpg."""
    import os
    with open(os.path.join(out_dir, "og-card.html"), "w", encoding="utf-8") as f:
        f.write(card_html(data, topo))
    n = 1
    for t in data["theatres"]:
        if t == "global" or t not in C.THEATRES:
            continue
        try:
            with open(os.path.join(out_dir, f"og-card-{t}.html"), "w", encoding="utf-8") as f:
                f.write(theatre_card_html(data, topo, t))
            n += 1
        except Exception as e:
            print(f"share card {t} skipped:", str(e)[:200])
    return n
