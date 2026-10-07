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
import engine
import extras
import geo
import osint
import scoring
import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MAXPTS = {"daily": 180, "monthly": 60}
ZH_N = 60
CLS_NAMES = {"lift": "Airlift", "tanker": "Tanker", "isr": "Surveillance / AWACS", "fighter": "Fighter", "bomber": "Bomber", "uav": "Drone", "heli": "Helicopter", "other": "Other military"}
UNAVAILABLE = [
    ("NOTAMs (airspace closure notices)", "The FAA and ICAO feeds refuse automated requests from cloud servers, and the FAA API needs an account. In their place the dashboard reads GPSJam (daily share of aircraft reporting degraded GPS, per theatre), US NGA hazard warnings, EASA airspace bulletins and live airliner counts."),
    ("Live ship positions in the Gulf, Red Sea and East Mediterranean", "The free live AIS networks (aisstream.io, and Open Waters, which mirrors it) have no receivers there: zero ships in Hormuz or the Gulf of Aden while 2,300 appear worldwide. Warships often switch AIS off anyway. Instead the dashboard scores Global Fishing Watch vessel-hours per day (satellite AIS, about four days late), IMF PortWatch transits, UKMTO incidents and the weekly USNI fleet tracker; Baltic, North Sea, Black Sea and Western Mediterranean AIS is live."),
    ("Conflict event data (ACLED API)", "The ACLED account authenticates but its data API is closed at the open tier. ACLED events arrive through the open HDX HAPI feed instead, about two months late. UCDP (Uppsala) is the planned second source once its access token arrives."),
    ("Aircraft routes and owners", "Public ADS-B carries no flight plan for military aircraft. Owner is inferred from the aircraft's address block and call sign, and shown as such."),
    ("Strava heat maps, lobster and steak orders, strip-club traffic, freight-forwarder leaks, Telegram channels", "No open data, or only through private apps and terms of service that forbid scraping. Not used."),
]


UPDATES = [   # (source, how often it is read, why that is enough / the free limit)
    ("Aircraft positions, emergency squawks (adsb.lol)", "every 30 minutes", "Community feed with no stated cap; one call per layer per run."),
    ("US Navy fleet (USNI Fleet Tracker)", "every 30 minutes, changes weekly", "USNI publishes once a week, usually Monday or Thursday."),
    ("UKMTO incidents and maritime news", "every 30 minutes", "Incidents are posted within hours of the report."),
    ("Vessel presence (Global Fishing Watch)", "every 12 hours", "Free token; posts daily about four days late, one call per sea box."),
    ("Ships (aisstream.io, Finnish Digitraffic)", "every 30 minutes, 75-second sample", "Free key; streams only while connected. Baltic needs no key."),
    ("NASA FIRMS fires and thermal detections", "every 30 minutes", "Satellite passes update every ~3 hours; free limit is 5,000 requests per 10 minutes, we use about 15."),
    ("Prediction-market odds and history", "every 30 minutes", "Polymarket and Kalshi public APIs; about 60 calls per run."),
    ("Hazard warnings (NGA), airspace bulletins (EASA), GPS-jamming and airliner counts", "every 30 minutes, averaged per day", "Snapshots are appended and averaged into a daily value."),
    ("Share prices (Yahoo Finance), FRED, ECB rates", "every 6 hours", "These publish one close per day; Yahoo needs no key and we use about 25 requests. Twelve Data is the fallback if Yahoo blocks the runner."),
    ("Internet outage data (IODA), UK travel advice", "every 3 to 12 hours", "Changes slowly; the source keeps history."),
    ("Headline counts (Google News) and GDELT events", "every 6 hours", "GDELT publishes daily files; news counts are backfilled a few days per run to stay polite."),
    ("US contract awards, trade, EU tenders, ACLED-derived conflict counts", "once a day", "Monthly data with a 1 to 3 month publishing delay; more frequent reads add nothing."),
    ("GPS interference (GPSJam), port calls (IMF PortWatch)", "every 6 hours / every 12 hours", "GPSJam posts a daily file two days late; PortWatch posts weekly. History was backfilled on first run."),
    ("Cloudflare Radar, OONI, Energy-Charts power prices, GIE gas storage", "every 3 to 12 hours", "Free token or key (Radar, GIE); OONI and Energy-Charts need none. Daily values."),
    ("SAM.gov tenders", "once a day, rate-limited", "Free key allows 10 requests a day, so it runs in its own job."),
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
         "needs": s.get("needs", []), "z": None, "w0": not s.get("scored", True)}
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
        x = v["doms"][dom]
        doms[dom] = {"z": None if x["z"] is None else round(x["z"], 2), "n": x["n"], "fast": x["fast"],
                     "drivers": x["drivers"], "w": x["w"], "c": x["contrib"]}
    return {"name": C.THEATRES[t]["name"], "level": v["level"], "firing": v["firing"], "scorable": v["scorable"],
            "basis": v["basis"], "doms": doms, "score": v["score"], "zc": v["zc"], "index": v["index"], "imb": v["imbalance"],
            "worst": v["worst"], "conf": v["confidence"], "confl": v["conf_label"], "miss": v["missing"], "th": v["th"]}


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
            "mil": [dict(xy=xy(m["lat"], m["lon"]), c=m["cls"], call=m["call"], t=m["t"], trk=m["trk"], hex=m["hex"], th=m.get("th", ""), o=m.get("o", ""),
                         ct=m.get("ct", ""), d=m.get("d", ""), r=m.get("r", ""), alt=m.get("alt"), gs=m.get("gs"), sq=m.get("sq", ""), em=bool(m.get("em")),
                         rt=m.get("rt", "")) for m in ex.get("mil", [])],
            "sqk": [dict(xy=xy(m["lat"], m["lon"]), sq=m["sq"], mean=m["mean"], why=m["why"], call=m["call"], hex=m["hex"], t=m["t"], o=m.get("o", ""),
                         ct=m.get("ct", ""), d=m.get("d", ""), r=m.get("r", ""), alt=m.get("alt"), trk=m.get("trk"), th=m.get("th", ""), rt=m.get("rt", "")) for m in ex.get("sqk", [])],
            "ships": [dict(xy=xy(m["lat"], m["lon"]), n=m["n"], k=m["k"], loc=m.get("loc", ""), g=m.get("g", ""), d=m.get("d", ""), tx=m.get("tx", ""), u=m.get("u", ""),
                           flag=m.get("flag", ""), dest=m.get("dest", ""), spd=m.get("spd"), note=m.get("note", ""), th=m.get("th", "")) for m in ex.get("ships", [])],
            "inc": [dict(xy=xy(m["lat"], m["lon"]), t=m["t"], d=m["d"], src=m["src"], u=m["u"], loc=m["loc"], th=m["th"], tx=m.get("tx", "")) for m in ex.get("inc", [])],
            "fires": [dict(xy=xy(m["lat"], m["lon"]), p=m["frp"], d=m["date"], th=m.get("th", "")) for m in ex.get("fires", [])],
            "seas": [{"n": n, "xy": xy(la, lo)} for n, la, lo in C.SEAS],
            "nga": [{"xy": xy(m["lat"], m["lon"]), "id": m["id"], "tx": m["text"], "iss": m["issued"], "th": osint.theatre_at(m["lat"], m["lon"])} for m in ex.get("nga", [])],
            "czib": [{"xy": xy(z["lat"], z["lon"]), "n": z["name"], "u": z["updated"], "th": osint.theatre_at(z["lat"], z["lon"])} for z in ex.get("czib", [])],
            "levels": levels_by_country}


def regions_json(regions):
    return [{k: r.get(k) for k in ("id", "name", "kids", "level", "score", "index", "lead")} for r in regions]


def build_data(res, generated, demo, ex, topo):
    ex = ex or {}
    data = {
        "generated": generated, "demo": bool(demo),
        "domains": [{"id": k, "name": v, "help": C.GROUP_HELP[k]} for k, v in C.DOMAINS.items()],
        "thresholds": [C.THRESH_WATCH, C.THRESH_SIGNAL], "levels": list(engine.LEVELS),
        "theatres": {t: theatre_json(t, v, res["series"]) for t, v in res["theatres"].items()},
        "order": list(C.THEATRES),
        "regions": regions_json(res["regions"]), "global": res["global"], "weights": res["weights_version"],
        "series": [series_json(s) for s in res["series"]],
        "markets": ex.get("markets", []), "pizza": ex.get("pizza"), "errors": ex.get("errors", []),
        "unavailable": [{"n": a, "w": b} for a, b in UNAVAILABLE], "updates": [{"s": a, "e": b, "l": c} for a, b, c in UPDATES], "clsnames": CLS_NAMES,
        "map": map_json(topo, ex, ex.get("levels", {})) if topo else None,
    }
    return data


def render(result, generated, demo=False, extras=None, topo=None):
    data = build_data(result, generated, demo, extras, topo)
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028")
    with open(os.path.join(HERE, "page.html"), encoding="utf-8") as f:
        page = f.read()
    return page.replace("__DATA__", blob).replace("__GENERATED__", generated)
