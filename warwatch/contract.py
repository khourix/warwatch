"""Data contract v1: the JSON files the new app reads, written next to the page every run. Standard library only.

    data/v1/brief.json                 first paint: headline, levels, the week's feed (about 20 KB)
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
    "base": {"id": str, "name": str, "state": str, "ll": list, "radar": list, "why": str},
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


def feed(data):
    """What changed this week, newest first: timing tells, bases that changed on radar, unexplained fires, CrisisWatch alerts."""
    out = []
    for t, v in data["theatres"].items():
        for x in v.get("tells") or []:
            if x.get("on") and x.get("date"):
                rec = x.get("rec") or {}
                detail = (f"Timing tell. Fired before {rec['caught']} of {rec['events']} past events" if rec.get("events")
                          else "Timing tell. New, no history to test yet")
                out.append({"date": x["date"], "kind": "tell", "theatre": t, "title": x["n"], "detail": detail, "to": {"view": "theatre", "id": t}})
    m = data.get("map") or {}
    words = {"out": "fewer aircraft than usual", "in": "more aircraft than usual", "changed": "one pass differed"}
    for b in m.get("bases") or []:
        if b.get("st") in words:
            out.append({"date": b.get("last") or "", "kind": "base", "theatre": b.get("th", ""), "title": f"{b['n'].split(',')[0]}: {words[b['st']]}",
                        "detail": "Satellite radar, two passes", "to": {"view": "base", "id": b["id"]}})
    for f in m.get("fires") or []:
        if f.get("c") == "anom":
            out.append({"date": f["d"], "kind": "fire", "theatre": f.get("th", ""), "title": "Heat " + (f"near {f['site']}" if f.get("site") else "with no usual source"),
                        "detail": f"{round(f['p'])} MW at night, NASA VIIRS", "to": {"view": "theatre", "id": f.get("th", ""), "tab": "ground"}})
    for t, v in data["theatres"].items():
        for o in v.get("official") or []:
            if o["n"].startswith("CrisisWatch") and re.search(r"alert|deteriorated", o["v"]):
                out.append({"date": o["d"] + ("-01" if len(o["d"]) == 7 else ""), "kind": "official", "theatre": t, "title": f"CrisisWatch: {o['v']}",
                            "detail": "Crisis Group, monthly", "to": {"view": "theatre", "id": t}})
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
                 theatres=ths, feed=feed(data)[:40],
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
                    "why": s.get("why", ""), "url": s.get("url", ""), "event": s.get("tf"),
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
        aircraft=[dict(ll=ll(a["xy"]), call=a.get("call", ""), **{"class": a.get("c", "")}, **keep(a, "t", "trk", "hex", "th", "o", "ct", "alt", "gs", "sq", "rt"),
                       emergency=bool(a.get("em"))) for a in m.get("mil") or []],
        squawks=[dict(ll=ll(a["xy"]), **keep(a, "sq", "mean", "why", "call", "hex", "t", "o", "ct", "alt", "trk", "th")) for a in m.get("sqk") or []],
        ships=[dict(ll=ll(s["xy"]), name=s.get("n", ""), **keep(s, "k", "loc", "g", "d", "tx", "u", "flag", "dest", "spd", "note", "th")) for s in m.get("ships") or []],
        incidents=[dict(ll=ll(i["xy"]), **keep(i, "t", "d", "src", "u", "loc", "th", "tx")) for i in m.get("inc") or []],
        fires=[dict(ll=[f["ll"][1], f["ll"][0]], mw=f["p"], date=f["d"], time=f.get("ts", ""), **{"class": f.get("c", "")}, score=f.get("a", 0),
                    why=f.get("why", ""), site=f.get("site", ""), theatre=f.get("th", ""), night=f.get("dn") == "N", images=f.get("img")) for f in m.get("fires") or []],
        bases=[{"id": b["id"], "name": b["n"], "kind": b.get("k", ""), "side": b.get("side", ""), "theatres": b.get("ths", []), "state": b.get("st", ""),
                "z": b.get("z"), "last": b.get("last", ""), "ll": [b["ll"][1], b["ll"][0]]} for b in m.get("bases") or []],
        warnings=[{"ll": ll(w["xy"]), "id": w.get("id", ""), "text": w.get("tx", ""), "issued": w.get("iss", ""), "theatre": w.get("th", "")} for w in m.get("nga") or []],
        conflictZones=[{"ll": ll(z["xy"]), "name": z.get("n", ""), "updated": z.get("u", ""), "theatre": z.get("th", "")} for z in m.get("czib") or []],
        cities=[{"ll": ll(c["xy"]), "name": c["n"], "theatre": c["t"]} for c in m.get("cities") or []],
        chokepoints=[{"ll": ll(c["xy"]), "name": c["n"], "theatre": c["t"], "id": c.get("k", "")} for c in m.get("choke") or []],
        hubs=[{"ll": ll(h["xy"]), "theatre": h["t"], "radiusNm": h.get("nm")} for h in m.get("hubs") or []],
        seas=[{"ll": ll(s["xy"]), "name": s["n"]} for s in m.get("seas") or []])


def base(data, b):
    return _head("base", data["generated"], id=b["id"], name=b["n"], type=b.get("k", ""), side=b.get("side", ""), theatres=b.get("ths", []),
                 state=b.get("st", ""), z=b.get("z"), last=b.get("last", ""), previous=b.get("lo", ""), ll=[b["ll"][1], b["ll"][0]],
                 radar=b.get("pts") or [], why=b.get("why", ""), note=b.get("note", ""), images=b.get("img") or {})


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
