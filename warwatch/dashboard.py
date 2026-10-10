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
    ("NOTAMs (airspace closure notices)", "The FAA NOTAM service (NMS-API, production) supplies counts of fresh airspace-restriction notices for each theatre's flight information regions; ICAO's feed refuses automated requests. Alongside it the dashboard reads GPSJam (daily share of aircraft reporting degraded GPS, per theatre), US NGA hazard warnings (NGA's current feed, since its old one stopped in May 2024), EASA airspace bulletins and live airliner counts."),
    ("Live ship positions in the Gulf and Red Sea", "The free live AIS networks (aisstream.io, and Open Waters, which mirrors it) have no receivers there: a 45-second test in October 2026 saw zero ships in the Gulf, the Strait of Hormuz and the Red Sea, but about 36 in the East Mediterranean. Warships often switch AIS off anyway. Instead the dashboard counts ships on Sentinel-1 radar images (about every two days, ships with transponders off included, small boats missed) and scores Global Fishing Watch vessel-hours per day (satellite AIS, about four days late), IMF PortWatch transits, UKMTO incidents and the weekly USNI fleet tracker; Baltic, North Sea, Black Sea and Western Mediterranean AIS is live."),
    ("Conflict event data (ACLED API)", "The ACLED account authenticates but its data API is closed at the open tier. ACLED events arrive through the open HDX HAPI feed instead, about two months late. UCDP (Uppsala) event data is the second source, with deaths per month in each theatre box, about two to three months late."),
    ("Aircraft routes and owners", "Public ADS-B carries no flight plan for military aircraft. Owner is inferred from the aircraft's address block and call sign, and shown as such."),
    ("Strava heat maps, lobster and steak orders, strip-club traffic, freight-forwarder leaks, Telegram channels", "No open data, or only through private apps and terms of service that forbid scraping. Not used."),
]


UPDATES = [   # (source, how often it is read, why that is enough / the free limit)
    ("Radar ship counts (Sentinel-1 via Microsoft Planetary Computer)", "Every night", "Free, no account. A scene passes over each sea box about every two days; the job counts bright ship-sized targets and stores one value per day."),
    ("FAA NOTAM service (NMS-API)", "Every 6 hours", "Free with an FAA account (production keys); counts of new airspace-restriction notices per flight information region."),
    ("Aircraft positions, emergency squawks (adsb.lol)", "every 30 minutes", "Community feed with no stated cap; one call per layer per run."),
    ("US Navy fleet (USNI Fleet Tracker)", "every 30 minutes, changes weekly", "USNI publishes once a week, usually Monday or Thursday."),
    ("UKMTO incidents and maritime news", "every 30 minutes", "Incidents are posted within hours of the report."),
    ("Vessel presence (Global Fishing Watch)", "every 12 hours", "Free token; posts daily about four days late, one call per sea box."),
    ("Ships (aisstream.io, Finnish Digitraffic)", "every 30 minutes, 75-second sample", "Free key; streams only while connected. Baltic needs no key."),
    ("NASA FIRMS fires and thermal detections", "every 30 minutes, last 7 days", "Satellite passes update every ~3 hours; free limit is 5,000 requests per 10 minutes, we use about 25."),
    ("Prediction-market odds and history", "every 30 minutes", "Polymarket and Kalshi public APIs; about 60 calls per run."),
    ("Hazard warnings (NGA), airspace bulletins (EASA), GPS-jamming and airliner counts", "every 30 minutes, averaged per day", "Snapshots are appended and averaged into a daily value."),
    ("Share prices (Yahoo Finance, else Twelve Data), Cboe VIX, FRED, ECB rates", "every 6 hours", "These publish one close per day; Yahoo refuses GitHub's runners (it answers 429 to every request), so Twelve Data does the work in practice."),
    ("Internet outage data (IODA), UK travel advice", "every 3 to 12 hours", "Changes slowly; the source keeps history."),
    ("Headline counts (Google News) and GDELT events", "every 6 hours", "GDELT publishes daily files; news counts are backfilled a few days per run to stay polite."),
    ("US contract awards, trade, EU tenders, ACLED- and UCDP-derived conflict counts", "once a day", "Monthly data with a 1 to 3 month publishing delay; more frequent reads add nothing."),
    ("GPS interference (GPSJam), port calls (IMF PortWatch)", "every 6 hours / every 12 hours", "GPSJam posts a daily file two days late; PortWatch posts weekly. History was backfilled on first run."),
    ("Cloudflare Radar, OONI, Energy-Charts power prices, GIE gas storage", "every 3 to 12 hours", "Free token or key (Radar, GIE); OONI and Energy-Charts need none. Daily values."),
    ("SAM.gov tenders", "once a day, rate-limited", "Free key allows 10 requests a day, so it runs in its own job."),
]


def _directed_pts(zh, direction):
    return [[lab, round(scoring.directed(z, direction), 2)] for lab, z in zh]


def series_json(s):
    ok = s["status"] == "ok" and s.get("score")
    kind = s["kind"]
    pts = stats.transformed(s["points"], kind, s.get("transform"))    # a price scored on its change is charted as that change
    sc = s.get("score") or {}
    label = s["label"] + (f", {stats.CHANGE_LAG[kind]}-{'day' if kind == 'daily' else 'month'} % change" if s.get("transform") else "")
    d = {"id": s["id"], "l": label, "d": s["domain"], "s": s.get("sub", ""), "t": s["theatre"], "lag": bool(s["lag"]),
         "dir": s["direction"], "why": s["why"], "url": s.get("url", ""), "st": s["status"], "er": s.get("error", ""),
         "stale": s.get("stale", ""), "kind": kind, "n": len(pts), "need": 40 if kind == "monthly" else stats.MIN_DAILY,
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
        raw = stats.history_z(pts, kind, ZH_N, scale=None if s.get("transform") else s.get("scale"))
        d["zh"] = _directed_pts(raw, s["direction"])
    return d


def _r(x, n):
    return None if x is None else round(x, n)


def _why(t, contrib, res_series):
    """Family contributions to the 30-day log-odds, labelled with the family's series name in this theatre."""
    import model
    lab = {model.WORLD: "World tempo (markets, defence orders and tenders: the same for every theatre)"}
    for s in res_series:
        if s["theatre"] in (t, "global"):
            lab.setdefault(model.family(s["id"]), s["label"])
    return [[lab.get(f, f), c] for f, c in contrib]


def theatre_json(t, v, res_series, base=None, change=None):
    doms = {}
    for dom in C.DOMAINS:
        x = v["doms"][dom]
        doms[dom] = {"z": None if x["z"] is None else round(x["z"], 2), "n": x["n"], "fast": x["fast"],
                     "drivers": x["drivers"], "w": x["w"], "c": x["contrib"]}
    return {"name": C.THEATRES[t]["name"], "level": v["level"], "firing": v["firing"], "scorable": v["scorable"],
            "basis": v["basis"], "doms": doms, "score": v["score"], "zc": v["zc"], "index": v["index"], "imb": v["imbalance"],
            "worst": v["worst"], "conf": v["confidence"], "confl": v["conf_label"], "miss": v["missing"], "th": v["th"],
            "p": _r(v.get("p"), 4), "plo": _r(v.get("p_lo"), 4), "phi": _r(v.get("p_hi"), 4), "why": _why(t, v.get("p_why", []), res_series), "aft": bool(v.get("p_aftermath")),
            "lvc": v.get("level_composite"), "pb": _r(base, 4), "pd": change}


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
    lo0, lo1, la0, la1 = geo.HOME
    hx0, hy0 = pr.xy(lo0, la1)
    hx1, hy1 = pr.xy(lo1, la0)
    return {"w": w, "h": h, "home": [round(hx0), round(hy0), round(hx1), round(hy1)], "countries": rm["countries"], "theatres": theatres, "cities": cities, "choke": choke, "hubs": hubs,
            "mil": [dict(xy=xy(m["lat"], m["lon"]), c=m["cls"], call=m["call"], t=m["t"], trk=m["trk"], hex=m["hex"], th=m.get("th", ""), o=m.get("o", ""),
                         ct=m.get("ct", ""), d=m.get("d", ""), r=m.get("r", ""), alt=m.get("alt"), gs=m.get("gs"), sq=m.get("sq", ""), em=bool(m.get("em")),
                         rt=m.get("rt", "")) for m in ex.get("mil", [])],
            "sqk": [dict(xy=xy(m["lat"], m["lon"]), sq=m["sq"], mean=m["mean"], why=m["why"], call=m["call"], hex=m["hex"], t=m["t"], o=m.get("o", ""),
                         ct=m.get("ct", ""), d=m.get("d", ""), r=m.get("r", ""), alt=m.get("alt"), trk=m.get("trk"), th=m.get("th", ""), rt=m.get("rt", "")) for m in ex.get("sqk", [])],
            "ships": [dict(xy=xy(m["lat"], m["lon"]), n=m["n"], k=m["k"], loc=m.get("loc", ""), g=m.get("g", ""), d=m.get("d", ""), tx=m.get("tx", ""), u=m.get("u", ""),
                           flag=m.get("flag", ""), dest=m.get("dest", ""), spd=m.get("spd"), note=m.get("note", ""), th=m.get("th", "")) for m in ex.get("ships", [])],
            "inc": [dict(xy=xy(m["lat"], m["lon"]), t=m["t"], d=m["d"], src=m["src"], u=m["u"], loc=m["loc"], th=m["th"], tx=m.get("tx", "")) for m in ex.get("inc", [])],
            "fires": [dict(xy=xy(m["lat"], m["lon"]), p=m["frp"], d=m["date"], ts=m.get("ts", ""), r=int(bool(m.get("routine"))), th=m.get("th", "")) for m in ex.get("fires", [])],
            "seas": [{"n": n, "xy": xy(la, lo)} for n, la, lo in C.SEAS],
            "nga": [{"xy": xy(m["lat"], m["lon"]), "id": m["id"], "tx": m["text"], "iss": m["issued"], "th": osint.theatre_at(m["lat"], m["lon"])} for m in ex.get("nga", [])],
            "czib": [{"xy": xy(z["lat"], z["lon"]), "n": z["name"], "u": z["updated"], "th": osint.theatre_at(z["lat"], z["lon"])} for z in ex.get("czib", [])],
            "levels": levels_by_country}


def regions_json(regions):
    return [{k: r.get(k) for k in ("id", "name", "kids", "level", "score", "index", "lead")} for r in regions]


def p_change(now, path=None, days=7):
    """{theatre: [change in the 30-day chance (probability units), days back]} against the forward record: the newest
    logged day at least `days` before the latest one, else the oldest logged day. None when there is no earlier day."""
    import csv
    import model
    try:
        with open(path or model.FORWARD, newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("p")]
    except OSError:
        return {}
    by = {}
    for r in rows:
        by.setdefault(r["theatre"], {})[r["date"]] = float(r["p"])
    out = {}
    for t, p in (now or {}).items():
        hist = by.get(t, {})
        if p is None or not hist:
            continue
        last = dt.date.fromisoformat(max(hist))
        older = [d for d in hist if dt.date.fromisoformat(d) < last]
        if not older:
            continue
        cut = [d for d in older if (last - dt.date.fromisoformat(d)).days >= days]
        ref = max(cut) if cut else min(older)
        out[t] = [round(p - hist[ref], 4), (last - dt.date.fromisoformat(ref)).days]
    return out


def adsb_recent(hours=48, cls=("mil", "fighter", "isr", "lift", "tanker")):
    """{theatre: {class: [[UTC stamp, count], ...]}} for the last `hours` of the ADS-B snapshots, for the Activity page."""
    import store
    out = {}
    for t in C.BOXES:
        for c in cls:
            pts = store.load(f"adsb_{t}_{c}")
            if not pts:
                continue
            end = dt.datetime.fromisoformat(pts[-1][0])
            keep = [[a, round(b, 1)] for a, b in pts if (end - dt.datetime.fromisoformat(a)).total_seconds() <= hours * 3600]
            out.setdefault(t, {})[c] = keep
    return out


def build_data(res, generated, demo, ex, topo):
    ex = ex or {}
    chg = p_change({t: v.get("p") for t, v in res["theatres"].items()})
    data = {
        "generated": generated, "demo": bool(demo),
        "domains": [{"id": k, "name": v, "help": C.GROUP_HELP[k]} for k, v in C.DOMAINS.items()],
        "thresholds": [C.THRESH_WATCH, C.THRESH_SIGNAL], "levels": list(engine.LEVELS),
        "theatres": {t: theatre_json(t, v, res["series"], ((res.get("model") or {}).get("theatres") or {}).get(t, {}).get("base"), chg.get(t))
                     for t, v in res["theatres"].items()},
        "order": list(C.THEATRES),
        "regions": regions_json(res["regions"]), "global": res["global"], "weights": res["weights_version"],
        "model": model_json(res.get("model")),
        "series": [series_json(s) for s in res["series"]],
        "markets": ex.get("markets", []), "pizza": ex.get("pizza"), "errors": ex.get("errors", []),
        "unavailable": [{"n": a, "w": b} for a, b in UNAVAILABLE], "updates": [{"s": a, "e": b, "l": c} for a, b, c in UPDATES], "clsnames": CLS_NAMES,
        "map": map_json(topo, ex, ex.get("levels", {})) if topo else None,
        "adsb": adsb_recent(),
    }
    return data


def model_json(m):
    if not m:
        return None
    g = m["global"]
    return {"v": m["version"], "fitted": m["fitted"], "active": m["active"], "bands": m["bands"], "gates": m["gates"],
            "any": _r(g["p_any"], 4), "mm": _r(g["p_market_moving"], 4), "clim": g["clim"]}


def render(result, generated, demo=False, extras=None, topo=None):
    data = build_data(result, generated, demo, extras, topo)
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028")
    with open(os.path.join(HERE, "page.html"), encoding="utf-8") as f:
        page = f.read()
    return page.replace("__DATA__", blob).replace("__GENERATED__", generated)
