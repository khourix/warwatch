"""The link-preview cards (what Twitter, WhatsApp and Slack show when someone shares a page). Standard library only.

run.py writes og-card.html next to the page, and og-card-<theatre>.html for each theatre: 1200x630 pages in the app's colours
("Midnight", web/src/styles.css) with today's headline, three counts and a globe drawn in SVG. The workflow screenshots them with
the runner's Chrome into og.jpg and og/<theatre>.jpg; if that fails, the static og.jpg from static/ stays in place.

Fonts are the app's: Switzer and Sentient (Fontshare, ITF Free Font Licence) and JetBrains Mono (OFL). The Fontshare licence lets
the site serve its fonts but not this repository hold them, so the workflow downloads them into web/src/fonts/ (fetch-fonts.mjs)
before run.py, and write_cards copies what it finds there into og-fonts/ next to the cards. A font that is missing falls back
to a system font (Georgia, system-ui, monospace) and the card is still drawn.
"""
import datetime as dt
import html
import math
import os
import re
import shutil

import config as C
import geo

W, H = 1200, 630
# The app's dark tokens. Colour is for data marks only (levels, tripwires, bases); text and numbers stay in the three inks.
INK = {"bg": "#080b11", "fg": "#e8ecf2", "fg2": "#a3adbb", "fg3": "#7b8798", "line2": "rgba(160,190,230,.17)",
       "ocean": "#06090e", "land": "#0f151e", "land2": "#18212e", "border": "#2a3545", "grat": "rgba(160,190,230,.04)"}
LEVEL_FILL = {"Watch": "#f0b03c", "Elevated": "#ff7438", "Critical": "#ff4a45"}   # --z2, --z3, --crit
LAND_MIX = {"Watch": .42, "Elevated": .5, "Critical": .55}   # how strongly a theatre's country takes its level colour (MapView.tsx)
BASE_FILL = {"out": LEVEL_FILL["Elevated"], "in": LEVEL_FILL["Elevated"], "changed": LEVEL_FILL["Watch"]}   # as the app's base diamonds
LEVEL_WORD = {"Normal": "Quiet", "Watch": "Watch", "Elevated": "Elevated", "Critical": "Critical"}
WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"]   # as word() in web/src/data.ts
SITE = "khourix.github.io/warwatch"
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "src", "fonts")
FONTS = (("Switzer", "switzer-normal.woff2", "100 900"), ("Sentient", "sentient-normal.woff2", "200 700"),
         ("JetBrains Mono", "jet-brains-mono-normal.woff2", "100 800"))
FONT_URL = "og-fonts/"   # relative to the card, so the screenshot reads the copies next to it


def _level(v):
    return v.get("level") if v.get("level") in LEVEL_FILL else "Normal"


def _tells_on(v):
    return sum(1 for x in v.get("tells") or [] if x.get("on"))


def _join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def short(name):
    """'South Asia (India-Pakistan)' reads 'South Asia' in sentences and on the map, as in the app (short in web/src/data.ts)."""
    return re.sub(r"\s*\(.*\)", "", name)


def whole(score):
    """The 0 to 100 reading as the app prints it (wholeScore in web/src/data.ts): half up, and a reading under 50 never shows as 50."""
    n = math.floor(score + 0.5)
    return min(49, n) if score < 50 else n


def _strong(series, t):
    """-> (signals reading strong, signals scored) for a theatre: a scored signal 3 SD or more from its usual range."""
    sc = [s for s in series if s.get("t") == t and s.get("st") == "ok" and s.get("z") is not None]
    return sum(1 for s in sc if abs(s["z"]) >= 3), len(sc)


def summary(data):
    """-> (headline, facts) for the card, brief.json and the share text. Theatres are in config order, the 'global' row is left out.

    On a quiet day, while the forecast model is off (so the line of 50 sets the level), the headline names the quiet theatre
    closest to that line before the tripwire count, worded as the app's dispatch words it (watch.tsx)."""
    ths = [(t, data["theatres"][t]) for t in data.get("order", data["theatres"]) if t in data["theatres"] and t != "global"]
    up = sorted([(t, v) for t, v in ths if _level(v) != "Normal"], key=lambda tv: -list(LEVEL_FILL).index(_level(tv[1])))
    tells = sum(_tells_on(v) for _, v in ths)
    near = None   # the quiet theatre with the highest reading; the first in config order on a tie, as the app sorts
    for _, v in ths:
        if _level(v) == "Normal" and v.get("score") is not None and (near is None or v["score"] > near["score"]):
            near = v
    if not up:
        a = "Every theatre reads quiet."
    elif len(up) == 1:
        a = f"{short(up[0][1]['name'])} is the only theatre above quiet."
    else:
        a = f"{_join([short(v['name']) for _, v in up])} are above quiet." if len(up) <= 3 else f"{WORDS[len(up)] if len(up) < len(WORDS) else len(up)} theatres are above quiet, led by {short(up[0][1]['name'])}."
    word = WORDS[tells] if tells < len(WORDS) else str(tells)
    b = f" {word} tripwire{'' if tells == 1 else 's'} fired this week."
    if not up and near is not None and not (data.get("model") or {}).get("active") and near["score"] < 50:
        b = f" {short(near['name'])} comes closest to Watch, at {whole(near['score'])} against a line of 50." + b
    bases = sum(1 for b_ in ((data.get("map") or {}).get("bases") or []) if b_.get("st") in ("out", "in", "changed"))
    signals = sum(1 for s in data.get("series") or [] if not s.get("tf"))
    strong = sum(_strong(data.get("series") or [], t)[0] for t, _ in ths)
    return a + b, {"tells": tells, "bases": bases, "theatres": len(ths), "signals": signals, "strong": strong}


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


def _mix(a, b, t):
    """Colour a laid over b at strength t, in sRGB, as the app tints a country by its level (mix in MapView.tsx)."""
    pa, pb = (int(a[i:i + 2], 16) for i in (1, 3, 5)), (int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}" for x, y in zip(pa, pb))


def globe_svg(topo, data, cx=900, cy=330, r=520, lon0=40, lat0=24, focus=None, left=640):
    """The globe, with the theatres labelled as the app labels them on its map. Nothing is marked left of `left`, where the text
    sits on flat background. focus: a theatre id; its country is outlined and its label is the selected one."""
    pr = Ortho(lon0, lat0, r, cx, cy)
    mine = C.THEATRES.get(focus, {}).get("countries", []) if focus else []   # the first is the theatre itself, the rest are drawn in
    rank = lambda lv: list(LEVEL_FILL).index(lv) + 1 if lv in LEVEL_FILL else 0
    fill = {}   # country -> (level, primary): the theatre's first country carries its colour, the rest a faint tint
    for t, th in C.THEATRES.items():
        lv = _level(data["theatres"].get(t) or {})
        for i, name in enumerate(th.get("countries", [])):
            new = (lv, i == 0)
            fill[name] = max(fill[name], new, key=lambda x: (rank(x[0]), x[1])) if name in fill else new
    land = []
    for _cid, name, rings in geo.countries(topo) if topo else []:
        if name in geo.SKIP:
            continue
        d = "".join(_ring_path(pr, ring) for ring in rings)
        if not d:
            continue
        lv, primary = fill.get(name, (None, False))
        if name == (mine or [None])[0]:
            flv = _level(data["theatres"].get(focus) or {})
            col = _mix(LEVEL_FILL[flv], INK["land"], LAND_MIX[flv]) if flv in LEVEL_FILL else INK["land2"]
            land.append(f'<path d="{d}" fill="{col}" stroke="{INK["fg"]}" stroke-opacity=".55" stroke-width="1.5"/>')
        elif name in mine:
            land.append(f'<path d="{d}" fill="{INK["land2"]}" stroke="{INK["border"]}" stroke-width=".7"/>')
        elif lv in LEVEL_FILL:
            col = _mix(LEVEL_FILL[lv], INK["land"], LAND_MIX[lv] if primary else .08)
            land.append(f'<path d="{d}" fill="{col}" stroke="{INK["border"]}" stroke-width=".6"/>')
        else:
            land.append(f'<path d="{d}" fill="{INK["land"]}" stroke="{INK["border"]}" stroke-width=".6"/>')
    grat = []
    for lon in range(-180, 180, 20):
        grat.append(_ring_path(pr, [(lon, la) for la in range(-80, 81, 2)], closed=False))
    for la in range(-60, 61, 20):
        grat.append(_ring_path(pr, [(lo, la) for lo in range(-180, 181, 2)], closed=False))
    on_card = lambda x, y, m=0: left + m < x < W - m and m < y < H - 80 - m   # right of the text, above the footer line
    marks = []   # bases that changed on radar, as the app's diamonds: amber for one pass that differed, orange for fewer or more
    for b in ((data.get("map") or {}).get("bases") or []):
        ll = b.get("ll")
        if b.get("st") not in BASE_FILL or not ll or (focus and b.get("th") != focus) or pr.cos_c(ll[1], ll[0]) < .1:
            continue
        x, y = pr.xy(ll[1], ll[0])
        if on_card(x, y, 6):
            marks.append(f'<path d="M{x:.1f},{y - 6:.1f}L{x + 6:.1f},{y:.1f}L{x:.1f},{y + 6:.1f}L{x - 6:.1f},{y:.1f}Z" fill="{BASE_FILL[b["st"]]}" stroke="{INK["bg"]}" stroke-width="1.2"/>')
    cand = []
    for t in C.THEATRES:
        v = data["theatres"].get(t) or {}
        if t not in C.BOXES or t == "global":
            continue
        la0, la1, lo0, lo1 = C.BOXES[t]
        lon, lat = (lo0 + lo1) / 2, (la0 + la1) / 2
        if pr.cos_c(lon, lat) < 0.35:
            continue
        x, y = pr.xy(lon, lat)
        lv, n, sc = _level(v), _tells_on(v), v.get("score")
        cand.append(((t != focus, -rank(lv), -n, -(sc or 0)), x, y, t, lv, n, sc, short(v.get("name", t))))
    dots, chips, boxes = [], [], []
    for _, x, y, t, lv, n, sc, name in sorted(cand, key=lambda c: c[0]):   # the selected theatre, then the highest level, keeps its label
        w = 24 + len(name) * 7.9 + (len(str(whole(sc))) * 8 + 7 if sc is not None else 0) + (13 if n else 0)
        box = (x - w / 2, y - 14, x + w / 2, y + 14)
        if not on_card(x, y):
            continue
        if not on_card(box[0], box[1]) or not on_card(box[2], box[3]) or any(
                box[0] < o[2] + 6 and o[0] < box[2] + 6 and box[1] < o[3] + 4 and o[1] < box[3] + 4 for o in boxes):
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{LEVEL_FILL.get(lv, INK["fg3"])}"/>')
            continue
        boxes.append(box)
        cls = "chip on" if t == focus else "chip dim" if focus else "chip"
        edge = f";border-color:{LEVEL_FILL[lv]}" if lv in LEVEL_FILL and t != focus else ""
        chips.append(f'<div class="{cls}" style="left:{box[0]:.0f}px;top:{box[1]:.0f}px{edge}">{"<i></i>" if n else ""}{html.escape(name)}'
                     f'{f"<em>{whole(sc)}</em>" if sc is not None else ""}</div>')
    return (f'<svg class="globe" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<defs><linearGradient id="fade" x1="0" x2="1"><stop offset=".38" stop-color="{INK["bg"]}"/><stop offset=".62" stop-color="{INK["bg"]}" stop-opacity="0"/></linearGradient></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{INK["ocean"]}" stroke="{INK["border"]}"/>'
            f'<path d="{"".join(grat)}" fill="none" stroke="{INK["grat"]}"/>{"".join(land)}'
            f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#fade)"/>{"".join(marks)}{"".join(dots)}</svg>'
            + "".join(chips))


MARK = (f'<svg width="40" height="40" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M3 9.5 9.6 24 16 13.6 22.4 24 26.2 15.4" stroke="{INK["fg"]}" '
        f'stroke-width="3.1" stroke-linecap="round" stroke-linejoin="round"/><circle cx="28" cy="10.4" r="3.1" fill="{INK["fg"]}"/></svg>')


def _when(data):
    gen = data.get("generated", "")
    try:
        g = dt.datetime.strptime(gen, "%Y-%m-%d %H:%M UTC")
        return f"{g.day} {g:%b %Y} · {g:%H:%M} UTC"
    except ValueError:
        return gen


def _style(size):
    """The cards' fonts and layout, shared by the site card and the theatre cards."""
    fonts = "".join(f'@font-face{{font-family:"{fam}";src:url({FONT_URL}{fn}) format("woff2");font-weight:{wt}}}' for fam, fn, wt in FONTS)
    mono = '"JetBrains Mono",ui-monospace,Menlo,monospace'
    k = INK
    return f"""{fonts}
*{{box-sizing:border-box}}body{{margin:0;width:{W}px;height:{H}px;background:{k["bg"]};color:{k["fg"]};font-family:Switzer,system-ui,sans-serif;overflow:hidden;position:relative;-webkit-font-smoothing:antialiased}}
.globe{{position:absolute;left:0;top:0}}
.wm{{position:absolute;left:64px;top:52px;display:flex;align-items:center;gap:12px;font-size:28px;font-weight:600;letter-spacing:-.02em}}
.eb{{position:absolute;left:64px;top:132px;font:400 15px/1.2 {mono};letter-spacing:.14em;text-transform:uppercase;color:{k["fg3"]}}}
h1{{position:absolute;left:64px;top:180px;width:620px;margin:0;font:400 {size}px/1.16 Sentient,Georgia,serif;letter-spacing:-.015em}}
.facts{{position:absolute;left:64px;top:412px;display:flex}}
.facts div{{padding-right:34px;margin-right:34px;border-right:1px solid {k["line2"]};font-size:17px;line-height:1.3;color:{k["fg2"]}}}
.facts div:last-child{{border:0;margin:0;padding:0}}
.facts b{{display:block;margin-bottom:6px;font-size:44px;font-weight:500;line-height:1.1;letter-spacing:-.03em;font-variant-numeric:tabular-nums;color:{k["fg"]}}}
.foot{{position:absolute;left:64px;right:64px;bottom:44px;display:flex;justify-content:space-between;font:400 16px {mono};color:{k["fg3"]}}}
.chip{{position:absolute;display:flex;align-items:center;gap:7px;height:28px;padding:0 11px;border-radius:14px;background:rgba(8,11,17,.82);border:1px solid {k["line2"]};color:{k["fg"]};font-size:15px;font-weight:500;white-space:nowrap}}
.chip i{{width:6px;height:6px;border-radius:50%;background:{LEVEL_FILL["Watch"]};box-shadow:0 0 6px {LEVEL_FILL["Watch"]}}}
.chip em{{font:400 13px {mono};color:{k["fg3"]}}}.chip.dim{{opacity:.8}}
.chip.on{{background:{k["fg"]};border-color:{k["fg"]};color:{k["bg"]}}}.chip.on em{{color:{k["bg"]};opacity:.7}}"""


def _fact(n, one, many):
    """One of the three counts: always in ink, never in a data colour."""
    return f'<div><b>{n}</b>{one if n == 1 else many}</div>'


def _size(head):
    return 46 if len(head) <= 64 else 42 if len(head) <= 96 else 38


def card_html(data, topo, fallback=False):
    """fallback: the timeless card committed as static/og.jpg, shown if the workflow cannot screenshot today's card."""
    head, f = summary(data)
    eyebrow, right = f"Dispatch · {_when(data)}", f"{f['theatres']} theatres · {f['signals']} public signals"
    if fallback:
        data = dict(data, theatres={t: {"name": v.get("name", t)} for t, v in data["theatres"].items()}, map={})
        head = f"Early warning for {f['theatres']} war theatres, from {f['signals'] // 50 * 50}+ public signals."
        eyebrow, right = "Early warning from public data", "Updated every 30 minutes"
    facts = (_fact(f["tells"], "tripwire fired<br>this week", "tripwires fired<br>this week") + _fact(f["bases"], "base changed<br>on radar", "bases changed<br>on radar")
             + _fact(f["strong"], "signal reading<br>strong", "signals reading<br>strong"))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>WarWatch share card</title><style>{_style(_size(head))}
</style></head><body>{globe_svg(topo, data)}<div class="wm">{MARK}WarWatch</div><div class="eb">{html.escape(eyebrow)}</div><h1>{html.escape(head)}</h1>
<div class="facts"{' style="display:none"' if fallback else ''}>{facts}</div>
<div class="foot"><span>{SITE}</span><span>{html.escape(right)}</span></div></body></html>
"""


# ---- one card per theatre, for /warwatch/<theatre>/ ----

def theatre_headline(name, level, tells):
    """'Iran reads quiet. No tripwires fired this week.' Also the share text on the theatre's page (pages.py)."""
    lv = level if level in LEVEL_FILL else "Normal"
    word = WORDS[tells] if tells < len(WORDS) else str(tells)
    name = short(name)
    return (f"{name} reads quiet." if lv == "Normal" else f"{name} reads {lv.lower()}.") + f" {word} tripwire{'' if tells == 1 else 's'} fired this week."


def theatre_summary(data, t):
    """-> (headline, facts) for one theatre's card and share text."""
    v = data["theatres"][t]
    lv, n = _level(v), _tells_on(v)
    name = v.get("name", t)
    strong, scored = _strong(data.get("series") or [], t)
    bases = sum(1 for b_ in ((data.get("map") or {}).get("bases") or []) if b_.get("th") == t and b_.get("st") in ("out", "in", "changed"))
    ctx = (getattr(C, "CONTEXT", {}).get(t) or (None,))[0]
    return theatre_headline(name, lv, n), {"tells": n, "strong": strong, "scored": scored, "bases": bases, "level": lv, "context": ctx, "name": name}


def theatre_card_html(data, topo, t):
    head, f = theatre_summary(data, t)
    view = C.THEATRES[t].get("view") or (20, 60, 10, 40)
    lon0, lat0 = (view[0] + view[1]) / 2, (view[2] + view[3]) / 2
    span = math.radians(max(view[1] - view[0], 8)) * max(math.cos(math.radians(lat0)), .3)
    r = min(3200, max(380, 470 / span))   # the theatre's usual view about fills the right half of the card
    col = LEVEL_FILL.get(f["level"], INK["fg2"])
    name = (f'<div class="name">{html.escape(short(f["name"]))}<span class="lv" style="color:{col}">{LEVEL_WORD[f["level"]]}</span>'
            + (f'<i>{html.escape(f["context"])}</i>' if f["context"] else "") + "</div>")
    facts = (_fact(f["tells"], "tripwire fired<br>this week", "tripwires fired<br>this week")
             + _fact(f["strong"], f"strong reading<br>of {f['scored']} scored", f"strong readings<br>of {f['scored']} scored")
             + _fact(f["bases"], "base changed<br>on radar", "bases changed<br>on radar"))
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>WarWatch share card: {html.escape(f["name"])}</title><style>{_style(_size(head))}
h1{{top:190px}}.name{{position:absolute;left:64px;top:126px;display:flex;align-items:center;gap:14px;font-size:24px;font-weight:600;letter-spacing:-.01em}}
.lv{{font-size:15px;font-weight:500;border:1px solid {INK["line2"]};border-radius:999px;padding:3px 12px}}
.name i{{font:400 15px "JetBrains Mono",ui-monospace,Menlo,monospace;font-style:normal;letter-spacing:.14em;text-transform:uppercase;color:{INK["fg3"]}}}
</style></head><body>{globe_svg(topo, data, cx=900, cy=315, r=r, lon0=lon0, lat0=lat0, focus=t)}<div class="wm">{MARK}WarWatch</div>
{name}<h1>{html.escape(head)}</h1>
<div class="facts">{facts}</div>
<div class="foot"><span>{SITE}/{t}</span><span>{html.escape(_when(data))}</span></div></body></html>
"""


def copy_fonts(out_dir, font_dir=FONT_DIR):
    """Copy the card fonts found in font_dir into out_dir/og-fonts/. -> how many are in place. Never raises: a card whose fonts
    are missing is drawn in system fonts."""
    n = 0
    for _fam, fn, _wt in FONTS:
        try:
            with open(os.path.join(font_dir, fn), "rb") as f:
                if f.read(4) != b"wOF2":   # a cut-off download or an error page
                    continue
            os.makedirs(os.path.join(out_dir, FONT_URL), exist_ok=True)
            shutil.copyfile(os.path.join(font_dir, fn), os.path.join(out_dir, FONT_URL, fn))
            n += 1
        except OSError:
            pass
    return n


def write_cards(out_dir, data, topo, font_dir=FONT_DIR):
    """og-card.html for the site and og-card-<theatre>.html for each theatre, next to the page, with their fonts in og-fonts/.
    The workflow screenshots them into og.jpg and og/<theatre>.jpg. A theatre whose card fails is skipped; its page then falls
    back to og.jpg. -> the number of cards written."""
    print(f"share card fonts: {copy_fonts(out_dir, font_dir)} of {len(FONTS)} in place")
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
