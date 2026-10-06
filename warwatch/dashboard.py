"""One self-contained interactive HTML file: no server, no build, no cost.

Python scores and lays out the data; the page template (page.html) draws it in the
browser: a zoomable map with layers, five clickable signal groups per theatre and a
detail view for every signal (description, links, raw values, history, standard deviations).
The data travels as one JSON block inside the page.
"""
import datetime as dt
import json
import os

import config as C
import extras
import geo
import scoring
import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MAXPTS = {"daily": 180, "monthly": 60}
ZH_N = 60
CLS_NAMES = {"lift": "Airlift", "tanker": "Tanker", "isr": "Surveillance / AWACS", "fighter": "Fighter", "other": "Other military"}
UNAVAILABLE = [
    ("NOTAMs (airspace closure notices)", "The FAA and ICAO feeds refuse automated requests from cloud servers (403/404). A free FAA NOTAM API key would let it through; in its place the dashboard reads US NGA hazard warnings, EASA airspace bulletins and live airliner counts."),
    ("UKMTO maritime incident reports", "The site is a script-driven page with no open feed. Covered instead by IMF PortWatch ship transits at Hormuz, Bab el-Mandeb and Suez, and NGA navigational warnings."),
    ("GDELT live news API", "Blocked from GitHub servers. The dashboard now reads GDELT's published daily event files instead, which are not blocked."),
    ("Satellite imagery, fires and thermal anomalies", "NASA FIRMS needs a free map key; it is next on the list."),
    ("Conflict event data (ACLED)", "Needs a free account; it is next on the list."),
    ("Strava heat maps, lobster and steak orders, strip-club traffic, freight-forwarder leaks, Telegram channels", "No open data, or only through private apps and terms of service that forbid scraping. Not used."),
]


def _directed_pts(zh, direction):
    return [[lab, round(scoring.directed(z, direction), 2)] for lab, z in zh]


def series_json(s):
    ok = s["status"] == "ok" and s.get("score")
    pts = s["points"]
    sc = s.get("score") or {}
    kind = s["kind"]
    d = {"id": s["id"], "l": s["label"], "d": s["domain"], "s": s.get("sub", ""), "t": s["theatre"], "lag": bool(s["lag"]),
         "dir": s["direction"], "why": s["why"], "url": s.get("url", ""), "st": s["status"], "er": s.get("error", ""),
         "stale": s.get("stale", ""), "kind": kind, "n": len(pts), "need": 40 if kind == "monthly" else 84,
         "needs": s.get("needs", []), "z": None}
    if pts:
        d["pts"] = [[lab, round(v, 3)] for lab, v in pts[-MAXPTS[kind]:]]
        d["last"] = pts[-1][0]
    if ok:
        d["z"] = round(scoring.directed(sc["z"], s["direction"]), 2)
        d["rz"] = round(sc["z"], 2)
        d["val"] = round(sc["value"], 3)
        d["method"] = sc["method"]
        if "base_med" in sc:
            d["base"] = {"med": round(sc["base_med"], 3), "sd": round(sc["base_sd"], 3), "n": sc["base_n"]}
        raw = stats.history_z(pts, kind, ZH_N)
        d["zh"] = _directed_pts(raw, s["direction"])
    return d


def theatre_json(t, v, res_series):
    doms = {}
    for dom in C.DOMAINS:
        x = v["domains"][dom]
        doms[dom] = {"z": None if x["z"] is None else round(x["z"], 2), "n": x["n"], "fast": x["fast"],
                     "drivers": x["drivers"]}
    return {"name": C.THEATRES[t]["name"], "level": v["level"], "firing": v["firing"], "scorable": v["scorable"],
            "basis": v["basis"], "doms": doms}


def map_json(topo, ex, levels_by_country):
    rm = geo.region_map(topo)
    pr = rm["proj"]
    w, h = rm["w"], rm["h"]
    xy = lambda lat, lon: [round(c, 1) for c in pr.xy(lon, lat)]
    theatres = {}
    for t, th in C.THEATRES.items():
        la0, la1, lo0, lo1 = C.BOXES[t] if t in C.BOXES else (-6, 74, -26, 76)
        v0, v1, a0, a1 = th["view"]
        x0, y0 = pr.xy(v0, a1)
        x1, y1 = pr.xy(v1, a0)
        cx, cy = pr.xy((lo0 + lo1) / 2, (la0 + la1) / 2)
        theatres[t] = {"view": [round(x0), round(y0), round(x1), round(y1)], "pin": [round(cx), round(cy)],
                       "countries": th["countries"]}
    cities = [{"n": n, "t": t, "xy": xy(la, lo)} for t, lst in C.CITIES.items() for n, la, lo in lst]
    choke = [{"n": nm, "t": C.CHOKEPOINTS[f], "xy": xy(la, lo), "k": f} for f, (la, lo, nm) in C.CHOKE_XY.items()]
    hubs = []
    for t, lst in C.HUBS.items():
        for la, lo, r in lst:
            x, y = pr.xy(lo, la)
            _, y2 = pr.xy(lo, la + r / 60.0)
            hubs.append({"t": t, "xy": [round(x, 1), round(y, 1)], "r": round(abs(y - y2), 1), "nm": r})
    return {"w": w, "h": h, "countries": rm["countries"], "theatres": theatres, "cities": cities, "choke": choke, "hubs": hubs,
            "mil": [{"xy": xy(m["lat"], m["lon"]), "c": m["cls"], "call": m["call"], "t": m["t"], "trk": m["trk"], "hex": m["hex"]}
                    for m in ex.get("mil", [])],
            "nga": [{"xy": xy(m["lat"], m["lon"]), "id": m["id"], "tx": m["text"], "iss": m["issued"]} for m in ex.get("nga", [])],
            "czib": [{"xy": xy(z["lat"], z["lon"]), "n": z["name"], "u": z["updated"]} for z in ex.get("czib", [])],
            "levels": levels_by_country}


def build_data(res, generated, demo, ex, topo):
    ex = ex or {}
    data = {
        "generated": generated, "demo": bool(demo),
        "domains": [{"id": k, "name": v, "help": C.GROUP_HELP[k]} for k, v in C.DOMAINS.items()],
        "thresholds": [C.THRESH_WATCH, C.THRESH_SIGNAL],
        "theatres": {t: theatre_json(t, v, res["series"]) for t, v in res["theatres"].items()},
        "order": list(C.THEATRES),
        "series": [series_json(s) for s in res["series"]],
        "markets": ex.get("markets", []), "pizza": ex.get("pizza"), "errors": ex.get("errors", []),
        "unavailable": [{"n": a, "w": b} for a, b in UNAVAILABLE], "clsnames": CLS_NAMES,
        "map": map_json(topo, ex, ex.get("levels", {})) if topo else None,
    }
    return data


def render(result, generated, demo=False, extras=None, topo=None):
    data = build_data(result, generated, demo, extras, topo)
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028")
    with open(os.path.join(HERE, "page.html"), encoding="utf-8") as f:
        page = f.read()
    return page.replace("__DATA__", blob).replace("__GENERATED__", generated)
