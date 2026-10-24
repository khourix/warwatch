"""Data contract v1: the JSON files the new app reads, written next to the page every run. Standard library only.

    data/v1/brief.json                 first paint: headline, levels, the feed of the last 30 days (about 45 KB)
    data/v1/theatres/<id>.json         one theatre in full
    data/v1/signals/index.json         every signal, with a 40-point spark line
    data/v1/signals/series/<id>.json   one signal's full history, loaded on demand
    data/v1/map/live.json              aircraft, ships, fires, bases, warnings, places
    data/v1/bases/<id>.json            one base in full, with its radar history and image chips
    data/v1/record.json                the forward record, the model's gates, siren tempo, data health
    data/v1/events.json                the labelled event list

Every file carries {"schema": "warwatch/v1", "kind": ..., "generated": ...}. Positions are [lon, lat], as in GeoJSON.
The files are built from the page data (dashboard.build_data), so the old page and the new app always show the same run.
SHAPES below is the contract; validate() checks a file against it and the tests run it on every file.
"""
import datetime as dt
import json
import os
import re

import config as C
import geo
import share

SCHEMA = "warwatch/v1"
GROUPS = {"logistics": "Logistics", "financial": "Markets", "behavioral": "People", "information": "News", "geospatial": "Physical"}

# kind -> {key: type}; a key ending in [] is a list whose items must carry the keys in ITEMS[kind + "." + key]
NUM = (int, float)
OPT_NUM = (int, float, type(None))
SHAPES = {
    "brief": {"generated": str, "headline": str, "counts": dict, "global": dict, "regions[]": list, "theatres[]": list, "feed[]": list, "model": dict},
    "theatre": {"id": str, "name": str, "region": str, "level": str, "score": OPT_NUM, "signals": dict, "tells[]": list, "groups": dict, "official[]": list,
                "history[]": list, "items[]": list, "events[]": list, "center": (list, type(None)), "countries": list},
    "signals": {"generated": str, "groups": dict, "signals[]": list},
    "series": {"id": str, "points": list, "zHistory": list},
    "map": {"theatres": dict, "aircraft[]": list, "ships[]": list, "fires[]": list, "bases[]": list, "warnings[]": list, "cities[]": list,
            "chokepoints[]": list},
    "base": {"id": str, "name": str, "state": str, "ll": list, "radar": list, "why": str, "images": dict, "parts[]": list},
    "record": {"forward": (list, type(None)), "model": (dict, type(None)), "tempo": dict, "health": dict},
    "events": {"through": str, "events[]": list},
}
ITEMS = {
    "brief.regions": {"id": str, "name": str, "theatres": list, "level": str},
    "brief.theatres": {"id": str, "name": str, "region": str, "level": str, "tellsOn": int, "tellsTotal": int, "strong": int, "context": (str, type(None)),
                       "groups": dict},
    "brief.feed": {"date": str, "kind": str, "theatre": str, "title": str, "detail": str, "to": dict},
    "theatre.tells": {"id": str, "name": str, "on": bool, "says": str},
    "theatre.official": {"name": str, "id": str, "date": str, "value": str},
    "theatre.history": list,
    "theatre.items": {"date": str, "kind": str, "text": str},
    "theatre.events": {"date": str, "kind": str, "text": str},
    "signals.signals": {"id": str, "label": str, "group": str, "theatre": str, "z": OPT_NUM, "status": str, "spark": list},
    "map.aircraft": {"ll": list, "call": str, "class": str},
    "map.ships": {"ll": list, "name": str},
    "map.fires": {"ll": list, "mw": NUM, "date": str, "class": str},
    "map.bases": {"id": str, "name": str, "state": str, "ll": list},
    "map.warnings": {"ll": list, "text": str},
    "base.parts": {"part": str, "state": str, "history": list, "images": dict},
    "map.cities": {"ll": list, "name": str, "theatre": str},
    "map.chokepoints": {"ll": list, "name": str},
    "events.events": {"date": str, "theatre": str, "kind": str, "text": str},
}


def validate(obj):
    """-> list of problems; empty when the file matches its kind's shape."""
    out = []
    if obj.get("schema") != SCHEMA:
        return [f"schema is {obj.get('schema')!r}, not {SCHEMA!r}"]
    kind = obj.get("kind")
    if kind not in SHAPES:
        return [f"unknown kind {kind!r}"]
    for key, typ in SHAPES[kind].items():
        name = key[:-2] if key.endswith("[]") else key
        if name not in obj:
            out.append(f"{kind}: missing {name}")
            continue
        if not isinstance(obj[name], typ):
            out.append(f"{kind}.{name}: {type(obj[name]).__name__}, expected {typ}")
            continue
        item = ITEMS.get(f"{kind}.{name}")
        if key.endswith("[]") and item:
            for i, x in enumerate(obj[name]):
                if isinstance(item, type):
                    if not isinstance(x, item):
                        out.append(f"{kind}.{name}[{i}]: {type(x).__name__}, expected {item.__name__}")
                    continue
                for k, t in item.items():
                    if k not in x:
                        out.append(f"{kind}.{name}[{i}]: missing {k}")
                    elif not isinstance(x[k], t):
                        out.append(f"{kind}.{name}[{i}].{k}: {type(x[k]).__name__}, expected {t}")
                if len(out) > 20:
                    return out
    for k in ("ll", "center"):   # positions are [lon, lat]
        v = obj.get(k)
        if isinstance(v, list) and len(v) == 2 and not (-180 <= v[0] <= 180 and -90 <= v[1] <= 90):
            out.append(f"{kind}.{k}: {v} is not [lon, lat]")
    return out


def _head(kind, generated, **body):
    return dict({"schema": SCHEMA, "kind": kind, "generated": generated}, **body)


def _r(x, n=3):
    return None if x is None else round(x, n)


class _LL:
    """Page pixels (the region-wide Mercator in geo.region_map) -> [lon, lat]."""

    def __init__(self, m):
        self.p = geo.Proj(geo.REGION, m["w"], m["h"]) if m else None

    def __call__(self, xy):
        if not self.p or not xy:
            return None
        lon, lat = self.p.lonlat(*xy)
        return [round(lon, 3), round(lat, 3)]


def _box_center(t):
    if t not in C.BOXES:
        return None
    la0, la1, lo0, lo1 = C.BOXES[t]
    return [round((lo0 + lo1) / 2, 3), round((la0 + la1) / 2, 3)]


def _view(t):
    v = C.THEATRES.get(t, {}).get("view")
    return [[v[0], v[2]], [v[1], v[3]]] if v else None


def _region_of(data):
    return {k: r for r in data.get("regions") or [] for k in r["kids"]}


def _scored(series, t):
    return [s for s in series if s["t"] == t and s.get("z") is not None and s["st"] == "ok"]


def _groups(data, t, top=0):
    th = data["theatres"][t]
    out = {}
    for d, name in GROUPS.items():
        v = th["doms"].get(d) or {}
        g = {"z": v.get("z"), "fast": bool(v.get("fast"))}
        if top:
            best = sorted([s for s in _scored(data["series"], t) if s["d"] == d], key=lambda s: -abs(s["z"]))[:top]
            g.update(history=v.get("h") or [], top=[{"id": s["id"], "label": s["l"], "z": s["z"]} for s in best])
        out[name] = g
    return out


def _ctx(t):
    return (C.CONTEXT.get(t) or (None, None)) if hasattr(C, "CONTEXT") else (None, None)


PART_THINGS = {"apron": "aircraft", "harbour": "ships", "ground": "vehicles"}


FEED_DAYS = 30    # the strip under the map shows 30 days; the bell, the last 7


def _num(m):
    return f"{round(float(m.group()), 1):g}"


def _fire_items(data, since):
    """Unusual fires, one item per theatre and day: the live map for the days it covers, the 21-day cluster cache
    (history/cache/fire_anoms.csv, read with the imagery review) for the days before."""
    import firecls
    import store
    fires = (data.get("map") or {}).get("fires") or []
    first = min((f["d"] for f in fires if f.get("d")), default="9999")
    by = {}
    for f in fires:
        if f.get("c") in firecls.ANOMALY and f.get("d", "") >= since:
            by.setdefault((f.get("th", ""), f["d"]), []).append((f.get("p") or 0, f.get("site", "")))
    rev = firecls.load_review()
    for r in store.cache_rows(firecls.ANOMS):
        if len(r) != 9 or r[0] == "cid":
            continue
        day, c, rv = r[4][:10], r[8], rev.get(r[0]) or {}
        if not since <= day < first or c not in firecls.ANOMALY:
            continue
        v, lc = rv.get("verdict"), rv.get("lc")
        if (v == "scar" and lc == "cropland") or (lc == "water" and v in ("none", "unclear")) or (v == "none" and c == "anom" and int(r[7]) - 10 < firecls.ANOM_AT):
            continue     # the satellite image explained it (burnt field, flare on water) or took it below the anomaly bar
        by.setdefault((r[1], day), []).append((float(r[6] or 0), ""))
    out = []
    for (t, d), L in by.items():
        mw, site = max(L)
        site = site or next((x for _, x in L if x), "")
        title = (("Heat " + (f"near {site}" if site else "with no usual source")) if len(L) == 1
                 else f"{len(L)} unusual fires" + (f", one near {site}" if site else ""))
        out.append({"date": d, "kind": "fire", "theatre": t, "title": title, "detail": f"Strongest {round(mw)} MW, NASA VIIRS",
                    "to": {"view": "theatre", "id": t, "tab": "ground"}})
    return out


def feed(data):
    """What happened on each of the last FEED_DAYS days, newest first: timing tells fired, US and UK travel steps, CrisisWatch
    ratings and strike waves (data["hist"], built from the hash-chained records), base changes on satellite radar (every pass
    replayed), unusual fires (one item per theatre and day) and CrisisWatch alerts."""
    day = data["generated"][:10]
    since = (dt.date.fromisoformat(day) - dt.timedelta(days=FEED_DAYS - 1)).isoformat()
    out, seen = [], set()

    def add(item):
        key = (item["date"][:10], item["theatre"], item["kind"], item["title"])
        if item["date"][:10] >= since and key not in seen:
            seen.add(key)
            out.append(item)
    for t, v in data["theatres"].items():
        for x in v.get("tells") or []:
            if x.get("on") and x.get("date"):
                rec = x.get("rec") or {}
                detail = (f"Timing tell. Fired before {rec['caught']} of {rec['events']} past events" if rec.get("events")
                          else "Timing tell. New, no history to test yet")
                add({"date": x["date"], "kind": "tell", "theatre": t, "title": x["n"], "detail": detail, "to": {"view": "theatre", "id": t}})
    for t, h in (data.get("hist") or {}).items():
        if t not in data["theatres"] or t == "global":
            continue
        for i in h.get("items") or []:
            d, k, text = i[0] + ("-01" if len(i[0]) == 7 else ""), i[1], i[2]
            to = {"view": "theatre", "id": t}
            if k == "tell":
                add({"date": d, "kind": "tell", "theatre": t, "title": text, "detail": "Timing tell", "to": to})
            elif k == "wave":
                add({"date": d, "kind": "tell", "theatre": t, "title": "Strike wave", "detail": text.split(": ", 1)[-1].capitalize(), "to": to})
            elif k == "advisory":
                head, _, rest = text.partition(": ")
                add({"date": d, "kind": "official", "theatre": t, "title": head, "detail": re.sub(r"\d+\.\d+", _num, rest).capitalize() + ". US State Department", "to": to})
            elif k == "advice":
                add({"date": d, "kind": "official", "theatre": t, "title": text, "detail": "UK Foreign Office", "to": to})
            elif k == "rating" and d[:7] >= since[:7]:
                add({"date": d, "kind": "official", "theatre": t, "title": text, "detail": "Crisis Group, monthly", "to": to})
    m = data.get("map") or {}
    words = {"out": "fewer {} than usual", "in": "more {} than usual", "changed": "one pass differed"}
    for b in m.get("bases") or []:
        what = PART_THINGS.get(b.get("mp") or "", "objects")
        name = b["n"].split(",")[0]
        to = {"view": "base", "id": b["id"]}
        last = b.get("last") or ""
        if b.get("st") in words:
            add({"date": last, "kind": "base", "theatre": b.get("th", ""), "title": f"{name}: {words[b['st']].format(what)}", "detail": "Satellite radar, two passes", "to": to})
        for d, st in b.get("ev") or []:
            near = last and b.get("st") in words and abs((dt.date.fromisoformat(d) - dt.date.fromisoformat(last[:10])).days) <= 1
            if st in words and not near:
                add({"date": d, "kind": "base", "theatre": b.get("th", ""), "title": f"{name}: {words[st].format(what)}",
                     "detail": "Satellite radar, one pass" if st == "changed" else "Satellite radar, two passes", "to": to})
    for f in _fire_items(data, since):
        add(f)
    for t, v in data["theatres"].items():
        for o in v.get("official") or []:
            if o["n"].startswith("CrisisWatch") and re.search(r"alert|deteriorated", o["v"]):
                d = o["d"] + ("-01" if len(o["d"]) == 7 else "")
                if not any(x["theatre"] == t and x["title"].startswith("CrisisWatch") and x["date"][:7] == d[:7] for x in out):
                    add({"date": d, "kind": "official", "theatre": t, "title": f"CrisisWatch: {o['v']}", "detail": "Crisis Group, monthly", "to": {"view": "theatre", "id": t}})
    return sorted(out, key=lambda f: f["date"], reverse=True)


def brief(data):
    head, counts = share.summary(data)
    reg = _region_of(data)
    order = [t for t in data.get("order", data["theatres"]) if t in data["theatres"] and t != "global"]
    ths = []
    for t in order:
        v = data["theatres"][t]
        ctx, ctxd = _ctx(t)
        sc = _scored(data["series"], t)
        ths.append({"id": t, "name": v["name"], "region": reg[t]["id"] if t in reg else "", "level": v["level"], "score": v.get("score"),
                    "standingRisk": v.get("xu"), "tellsOn": sum(1 for x in v.get("tells") or [] if x.get("on")), "tellsTotal": len(v.get("tells") or []),
                    "strong": sum(1 for s in sc if abs(s["z"]) >= 3), "context": ctx, "contextChecked": ctxd,
                    "spillover": t in (data.get("spill") or {}), "parents": (data.get("spill") or {}).get(t, []), "center": _box_center(t),
                    "groups": {k: g["z"] for k, g in _groups(data, t).items()}})
    mo = data.get("model") or {}
    g = data.get("global") or {}
    return _head("brief", data["generated"], demo=bool(data.get("demo")), eventsThrough=(data.get("events") or {}).get("through", ""),
                 headline=head, counts=dict(counts, strong=sum(x["strong"] for x in ths)), **{"global": {"level": g.get("level"), "score": g.get("score"), "lead": g.get("lead")}},
                 regions=[{"id": r["id"], "name": r["name"], "theatres": r["kids"], "level": r["level"], "lead": r.get("lead")} for r in data.get("regions") or []],
                 theatres=ths, feed=feed(data)[:400],
                 model={"version": mo.get("v"), "fitted": mo.get("fitted"), "active": bool(mo.get("active")), "gates": mo.get("gates")})


def theatre(data, t):
    v = data["theatres"][t]
    reg = _region_of(data)
    ctx, ctxd = _ctx(t)
    ev = (data.get("events") or {}).get("list") or []
    hist = (data.get("hist") or {}).get(t) or {}
    sc = _scored(data["series"], t)
    return _head("theatre", data["generated"], id=t, name=v["name"], region=reg[t]["name"] if t in reg else "", level=v["level"], score=v.get("score"),
                 signals={"scored": len(sc), "total": sum(1 for s in data["series"] if s["t"] == t), "strong": sum(1 for s in sc if abs(s["z"]) >= 3)},
                 standingRisk=v.get("xu"), chance={"p": v.get("p"), "lo": v.get("plo"), "hi": v.get("phi"), "usual": v.get("pb"), "change": v.get("pd")},
                 confidence=v.get("confl"), context=ctx, contextChecked=ctxd, spillover=t in (data.get("spill") or {}),
                 parents=(data.get("spill") or {}).get(t, []), center=_box_center(t), view=_view(t), countries=C.THEATRES.get(t, {}).get("countries", []),
                 tells=[{"id": x.get("id", ""), "name": x["n"], "on": bool(x.get("on")), "date": x.get("date"), "says": x.get("says", ""),
                         "cases": x.get("cases", ""), "record": x.get("rec")} for x in v.get("tells") or []],
                 groups=_groups(data, t, top=4),
                 official=[{"name": o["n"], "id": o["id"], "date": o["d"], "value": o["v"]} for o in v.get("official") or []],
                 history=hist.get("risk") or [],
                 items=[{"date": i[0], "kind": i[1], "text": i[2], "signal": i[3] if len(i) > 3 else ""} for i in hist.get("items") or []],
                 aircraft48h=(data.get("adsb") or {}).get(t, {}),
                 events=[{"date": e[0], "kind": e[3], "text": e[4]} for e in ev if t in (e[1], e[2])][-60:],
                 activity=v.get("act"))


def signals(data):
    out = []
    for s in data["series"]:
        pts = s.get("pts") or []
        out.append({"id": s["id"], "label": s["l"], "group": GROUPS.get(s["d"], s["d"]), "sub": s.get("s", ""), "theatre": s["t"], "z": s.get("z"),
                    "status": s["st"], "stale": s.get("stale", ""), "last": s.get("last", ""), "lagging": bool(s.get("lag")), "kind": s["kind"],
                    "why": s.get("why", ""), "url": s.get("url", ""), "event": s.get("tf"), "untested": bool(s.get("ut")),
                    "spark": [_r(p[1]) if isinstance(p[1], (int, float)) else None for p in pts[-40:]]})
    return _head("signals", data["generated"], groups={GROUPS[k]: C.GROUP_HELP.get(k, "") for k in GROUPS},
                 signals=out)


def series(data, s):
    return _head("series", data["generated"], id=s["id"], points=s.get("pts") or [], zHistory=s.get("zh") or [])


def live_map(data):
    m = data.get("map") or {}
    ll = _LL(m)
    keep = lambda x, *ks: {k: x.get(k) for k in ks if x.get(k) not in (None, "")}
    return _head(
        "map", data["generated"],
        theatres={t: {"center": _box_center(t), "view": _view(t), "countries": th.get("countries", [])} for t, th in C.THEATRES.items()},
        aircraft=[dict(ll=ll(a["xy"]), call=a.get("call", ""), **{"class": a.get("c", "")}, **keep(a, "t", "d", "r", "trk", "hex", "th", "o", "ct", "alt", "gs", "sq", "rt"),
                       emergency=bool(a.get("em"))) for a in m.get("mil") or []],
        squawks=[dict(ll=ll(a["xy"]), **keep(a, "sq", "mean", "why", "call", "hex", "t", "o", "ct", "alt", "trk", "th")) for a in m.get("sqk") or []],
        ships=[dict(ll=ll(s["xy"]), name=s.get("n", ""), **keep(s, "k", "loc", "g", "d", "tx", "u", "flag", "dest", "spd", "note", "th"),
                    **({"trail": [ll(p) for p in s["tr"]]} if s.get("tr") else {})) for s in m.get("ships") or []],
        # Added October 2026, optional (docs/FLIGHTS.md, docs/SHIPS.md): theatre airports, diversions and turnbacks (archive, a day
        # behind), dark-ship radar cells and loitering ships (Global Fishing Watch, about five days behind).
        airports=[{"ll": ll(a["xy"]), "icao": a["icao"], "name": a["n"], "theatre": a["th"], "date": a["d"], "departures": a["dep"], "usual": a["usual"],
                   "divertedAway": a["div_away"], "divertedIn": a["div_in"], "turnbacks": a["turnback"], "holds": a["hold"],
                   "bizjets": a["bizjet_dep"], "bizjetsOut": a["bizjet_out"]} for a in m.get("air") or []],
        diversions=[{"ll": ll(e["xy"]), "kind": e["k"], "call": e["call"], "type": e["type"], "from": e["from"], "planned": e["planned"],
                     "landed": e["landed"], "time": e["t"], "date": e["d"], "theatre": e["th"]} for e in m.get("div") or []],
        darkShips=[{"ll": ll(c["xy"]), "count": c["n"], "date": c["d"], "theatre": c["th"]} for c in m.get("dark") or []],
        loitering=[{"ll": ll(x["xy"]), "name": x["n"], "flag": x["flag"], "type": x["k"], "hours": x["h"], "start": x["d"], "theatre": x["th"]}
                   for x in m.get("loiter") or []],
        incidents=[dict(ll=ll(i["xy"]), **keep(i, "t", "d", "src", "u", "loc", "th", "tx")) for i in m.get("inc") or []],
        fires=[dict(ll=[f["ll"][1], f["ll"][0]], mw=f["p"], date=f["d"], time=f.get("ts", ""), **{"class": f.get("c", "")}, score=f.get("a", 0),
                    why=f.get("why", ""), site=f.get("site", ""), theatre=f.get("th", ""), night=f.get("dn") == "N", images=f.get("img")) for f in m.get("fires") or []],
        bases=[{"id": b["id"], "name": b["n"], "kind": b.get("k", ""), "side": b.get("side", ""), "theatres": b.get("ths", []), "state": b.get("st", ""),
                "z": b.get("z"), "last": b.get("last", ""), "ll": [b["ll"][1], b["ll"][0]], "why": b.get("why", ""), "radar": (b.get("pts") or [])[-30:],
                "thumb": (b.get("img") or {}).get("r") or (b.get("img") or {}).get("a") or "", "part": b.get("mp", ""),
                "bounds": b.get("bb")} for b in m.get("bases") or []],
        warnings=[{"ll": ll(w["xy"]), "id": w.get("id", ""), "text": w.get("tx", ""), "issued": w.get("iss", ""), "theatre": w.get("th", "")} for w in m.get("nga") or []],
        conflictZones=[{"ll": ll(z["xy"]), "name": z.get("n", ""), "updated": z.get("u", ""), "theatre": z.get("th", "")} for z in m.get("czib") or []],
        cities=[{"ll": ll(c["xy"]), "name": c["n"], "theatre": c["t"]} for c in m.get("cities") or []],
        chokepoints=[{"ll": ll(c["xy"]), "name": c["n"], "theatre": c["t"], "id": c.get("k", "")} for c in m.get("choke") or []],
        hubs=[{"ll": ll(h["xy"]), "theatre": h["t"], "radiusNm": h.get("nm")} for h in m.get("hubs") or []],
        seas=[{"ll": ll(s["xy"]), "name": s["n"]} for s in m.get("seas") or []])


def _pic(img, k):
    return {"src": img[k], "date": img.get(k + "d", "")} if img.get(k) else None


def base(data, b):
    """One base. images: the whole-site chips (radar and optical, latest and earlier pass), which cover bounds (west, south,
    east, north). parts: apron, harbour or ground, each
    with its own state, counts against the usual band, the last 30 passes [date, count, usual, low, high] and its marked radar chip."""
    img = b.get("img") or {}
    parts = [{"part": x["p"], "what": x.get("w", ""), "where": x.get("wh", ""), "state": x.get("st", ""), "z": x.get("z"), "dates": x.get("d", ""),
              "note": x.get("s", ""), "tested": bool(x.get("t")), "now": x.get("now"), "usual": x.get("u"), "low": x.get("lo"), "high": x.get("hi"),
              "history": x.get("h") or [],
              "marks": {"date": mk["d"], "before": mk["b"], "objects": mk["n"], "new": mk["new"], "gone": mk["gone"]} if (mk := x.get("mk")) else None,
              "images": {"marked": _pic(x.get("img") or {}, "m"), "before": _pic(x.get("img") or {}, "rb")}} for x in b.get("pr") or []]
    return _head("base", data["generated"], id=b["id"], name=b["n"], type=b.get("k", ""), side=b.get("side", ""), theatres=b.get("ths", []),
                 state=b.get("st", ""), z=b.get("z"), last=b.get("last", ""), previous=b.get("lo", ""), ll=[b["ll"][1], b["ll"][0]],
                 radar=b.get("pts") or [], why=b.get("why", ""), about=b.get("wy", ""), note=b.get("note", ""), mainPart=b.get("mp", ""), bounds=b.get("bb"),
                 images={"radar": _pic(img, "r"), "radarBefore": _pic(img, "rb"), "optical": _pic(img, "a"), "opticalBefore": _pic(img, "b")},
                 parts=parts)


def record(data):
    return _head("record", data["generated"], forward=data.get("forward"), model=data.get("model"), tempo=data.get("tempo") or {},
                 health={"errors": data.get("errors") or [], "unavailable": data.get("unavailable") or [], "updates": data.get("updates") or [],
                         "statuses": _statuses(data["series"])})


def _statuses(series):
    out = {}
    for s in series:
        out[s["st"]] = out.get(s["st"], 0) + 1
    return out


def events(data):
    ev = data.get("events") or {}
    return _head("events", data["generated"], through=ev.get("through", ""),
                 events=[{"date": e[0], "theatre": e[1], "site": e[2], "kind": e[3], "text": e[4], "flag": bool(e[5]) if len(e) > 5 else False}
                         for e in ev.get("list") or []])


def files(data):
    """-> {relative path: object} for the whole contract."""
    out = {"brief.json": brief(data), "signals/index.json": signals(data), "map/live.json": live_map(data), "record.json": record(data),
           "events.json": events(data)}
    for t in data["theatres"]:
        if t != "global":
            out[f"theatres/{t}.json"] = theatre(data, t)
    for s in data["series"]:
        if s.get("pts"):
            out[f"signals/series/{s['id']}.json"] = series(data, s)
    for b in (data.get("map") or {}).get("bases") or []:
        out[f"bases/{b['id']}.json"] = base(data, b)
    return out


def write(out_dir, data):
    """Writes data/v1/ under out_dir. Returns the number of files written."""
    root = os.path.join(out_dir, "data", "v1")
    n = 0
    for rel, obj in files(data).items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        n += 1
    return n
