"""One self-contained interactive HTML file: no server, no build, no cost.

Python scores and lays out the data; the page template (page.html) draws it in the
browser: a zoomable map with layers, five clickable signal groups per theatre and a
detail view for every signal (description, links, raw values, history, standard deviations).
The data travels as one JSON block inside the page.
"""
import datetime as dt
import json
import os
import statistics

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
    ("NASA FIRMS fires and thermal detections", "every 30 minutes, last 7 days", "All three VIIRS satellites, so a pass about every 50 minutes; free limit is 5,000 requests per 10 minutes, we use about 55."),
    ("Fire classes: NASA FIRMS archive (2012 on), OpenStreetMap (Geofabrik extracts), World Bank flare list, WRI power plants, Global Energy Monitor trackers", "rebuilt monthly", "Which places burn every day (gas flares, plants) or every season (farm fires). OpenStreetMap data (c) OpenStreetMap contributors, ODbL; WRI and Global Energy Monitor CC BY 4.0."),
    ("Satellite images: Copernicus Sentinel-1 radar and Sentinel-2 (ESA)", "every 6 hours", "Free and open, via Microsoft Planetary Computer and Element 84 Earth Search. Contains modified Copernicus Sentinel data. Base outlines (c) OpenStreetMap contributors, ODbL."),
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
    label = s["label"] + {"chg": f", {stats.CHANGE_LAG[kind]}-{'day' if kind == 'daily' else 'month'} % change",
                          "step": f", scored on its change over {stats.STEP_DAYS} days" if kind == "daily" else ", scored on its change"}.get(s.get("transform"), "")
    d = {"id": s["id"], "l": label, "d": s["domain"], "s": s.get("sub", ""), "t": s["theatre"], "lag": bool(s["lag"]),
         "dir": s["direction"], "why": s["why"], "url": s.get("url", ""), "st": s["status"], "er": s.get("error", ""),
         "stale": s.get("stale", ""), "kind": kind, "n": len(pts), "need": stats.min_points(kind, s.get("transform")),
         "needs": s.get("needs", []), "z": None, "w0": not s.get("scored", True)}
    if s.get("transform") in ("step", "event"):     # actions and ratings: the page shows them as what happened, not as SD
        d["tf"] = s["transform"]
        if _seam(s["id"]):
            d["seam"] = _seam(s["id"])
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
        raw = stats.history_z(s["points"], kind, ZH_N, transform=s.get("transform"), scale=s.get("scale"))
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


def theatre_json(t, v, res_series, base=None, change=None, tells=None):
    doms = {}
    for dom in C.DOMAINS:
        x = v["doms"][dom]
        doms[dom] = {"z": None if x["z"] is None else round(x["z"], 2), "n": x["n"], "fast": x["fast"],
                     "drivers": x["drivers"], "w": x["w"], "c": x["contrib"]}
    return {"name": C.THEATRES[t]["name"], "level": v["level"], "firing": v["firing"], "scorable": v["scorable"],
            "basis": v["basis"], "doms": doms, "score": v["score"], "zc": v["zc"], "index": v["index"], "imb": v["imbalance"],
            "worst": v["worst"], "conf": v["confidence"], "confl": v["conf_label"], "miss": v["missing"], "th": v["th"],
            "p": _r(v.get("p"), 4), "plo": _r(v.get("p_lo"), 4), "phi": _r(v.get("p_hi"), 4), "why": _why(t, v.get("p_why", []), res_series), "aft": bool(v.get("p_aftermath")),
            "lvc": v.get("level_composite"), "pb": _r(base, 4), "pd": change,
            "xu": _r(v["p"] / base, 2) if v.get("p") is not None and base else None,      # standing risk: times this theatre's usual
            "tells": tells or []}


STRIP_DAYS = 60


def _day(generated):
    try:
        return dt.date.fromisoformat(str(generated)[:10])
    except ValueError:
        return dt.datetime.now(dt.timezone.utc).date()


def dom_strips(res, ser_json, generated, days=STRIP_DAYS):
    """{theatre: {group: [z or None, one per day, oldest first]}} for the ladder strips. Each day is built the way
    engine.theatre_composite builds today: every series' own score history (zh) carried forward to that day, kept in the
    warning direction and cut to a quarter for late data, correlated series averaged, then the strongest of them combined.
    The groups are today's. Display only: no level, chance or record reads it."""
    import bisect
    zh = {}
    for s in ser_json:
        h = s.get("zh") or []
        zh[s["id"]] = ([p[0] for p in h], [p[1] for p in h])
    end = _day(generated)
    labels = [(end - dt.timedelta(days=days - 1 - k)).isoformat() for k in range(days)]

    def at(i, day):
        labs, vals = zh.get(i["id"], ([], []))
        j = bisect.bisect_right(labs, day if i["kind"] == "daily" else day[:7]) - 1
        if j < 0 or (i["kind"] == "daily" and (dt.date.fromisoformat(day) - dt.date.fromisoformat(labs[j])).days > 30):
            return None
        return max(0.0, vals[j]) * i["k"]       # zh is already turned to the warning direction

    out = {}
    for t in res["theatres"]:
        items, per = engine.theatre_items(res["series"], t), {}
        for dom in C.DOMAINS:
            grp, _ = engine.groups_of([i for i in items if i["domain"] == dom])
            row = []
            for day in labels:
                zs = []
                for g in grp:
                    v = [x for x in (at(i, day) for i in g) if x is not None]
                    if v:
                        zs.append(sum(v) / len(v))
                row.append(round(engine.domain_score(zs)[0], 2) if zs else None)
            per[dom] = row
        out[t] = per
    return out


def fire_json(m, xy):
    """One map fire: position, heat, time, class (c), score (a), plain reason (why), nearby site, and the Sentinel-2 chips
    when the imagery review has them. r = 1 for explained classes (industry, farm burning, volcano, offshore)."""
    d = dict(xy=xy(m["lat"], m["lon"]), ll=[round(m["lat"], 3), round(m["lon"], 3)], p=m["frp"], d=m["date"], ts=m.get("ts", ""),
             r=int(bool(m.get("routine"))), th=m.get("th", ""), c=m.get("c", "unex"), a=m.get("a", 0), why=m.get("why", ""), site=m.get("site", ""),
             dn=m.get("daynight", ""))
    rv = m.get("rv")
    if rv and rv.get("verdict") in ("scar", "none", "unclear") and m.get("cid"):
        b = f"img/fires/{m['cid']}"
        d["img"] = {"b": b + "_b.jpg", "a": b + "_a.jpg", "s": b + "_s.jpg", "bd": rv.get("bd", ""), "ad": rv.get("ad", ""), "v": rv["verdict"]}
    return d


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
            "fires": [fire_json(m, xy) for m in ex.get("fires", [])],
            "bases": [dict({k: v for k, v in b.items() if k not in ("lat", "lon")}, xy=xy(b["lat"], b["lon"]), ll=[round(b["lat"], 3), round(b["lon"], 3)],
                           th=(b.get("ths") or [""])[0]) for b in ex.get("bases", [])],
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
        "theatres": {t: theatre_json(t, v, res["series"], ((res.get("model") or {}).get("theatres") or {}).get(t, {}).get("base"), chg.get(t),
                                     (res.get("tells") or {}).get(t))
                     for t, v in res["theatres"].items()},
        "order": list(C.THEATRES), "sub": C.SUBTHEATRES, "spill": C.SPILLOVER,
        "regions": regions_json(res["regions"]), "global": res["global"], "weights": res["weights_version"],
        "model": model_json(res.get("model")),
        "series": [series_json(s) for s in res["series"]],
        "markets": ex.get("markets", []), "pizza": ex.get("pizza"), "errors": ex.get("errors", []),
        "unavailable": [{"n": a, "w": b} for a, b in UNAVAILABLE], "updates": [{"s": a, "e": b, "l": c} for a, b, c in UPDATES], "clsnames": CLS_NAMES,
        "map": map_json(topo, ex, ex.get("levels", {})) if topo else None,
        "adsb": adsb_recent(),
        "forward": None if demo else forward_json(res["series"]),
        "events": events_json(),
    }
    by_id = {s["id"]: s for s in res["series"]}
    data["tempo"] = tempo_json(by_id)
    data["hist"] = {} if demo else hist_json(res, by_id)
    strips = dom_strips(res, data["series"], generated)
    for t, v in data["theatres"].items():
        v["official"] = official_json(by_id, t)
        for dom, row in strips.get(t, {}).items():
            v["doms"][dom]["h"] = row
    data["strip_end"] = _day(generated).isoformat()
    return data


EVENTS = os.path.join(HERE, "data", "events.csv")
EVENTS_THROUGH = os.path.join(HERE, "data", "events_through.txt")
FORWARD_DIR = os.path.join(os.path.dirname(HERE), "forward")
HIST_DAYS = 90
TEMPO = {"israel": ("tzeva_israel", "Siren waves (Tzeva Adom)"), "ukraine": ("uaair_ukraine", "Air-raid alert waves (alerts.in.ua)")}
CW_WORDS = ["no alert", "deteriorated", "conflict-risk alert", "conflict-risk alert, deteriorated"]


def _csv(path):
    import csv
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def events_json(path=EVENTS, through=EVENTS_THROUGH):
    """The event list the model is fitted and scored on: [[date, theatre, site theatre, type, description, market moving]],
    and the date it is complete to (forecasts after it cannot be scored until the list is brought up to date)."""
    rows = [[r["date"], r["theatre"], r.get("site_theatre") or "", r.get("type") or "", r.get("description") or "",
             r.get("market_moving") == "True"] for r in _csv(path) if r.get("date")]
    if not rows:
        return None
    try:
        with open(through) as f:
            thr = f.read().strip() or None
    except OSError:
        thr = None
    return {"through": thr, "list": sorted(rows)}


def tempo_json(by_id, weeks=12):
    """For wars under way: the 7-day alert-wave count on each of the last `weeks` weeks, with the strike-wave tell's
    threshold on that day (twice the median of the 90 days before, and at least 5). A hidden model's input, shown as tempo."""
    import tells
    out = {}
    for t, (sid, name) in TEMPO.items():
        s = by_id.get(sid)
        if not s:
            continue
        pts = [tuple(p) for p in s.get("points") or []]
        o = {"id": sid, "n": name, "st": s["status"], "needs": s.get("needs", []), "w": []}
        if pts:
            last = dt.date.fromisoformat(pts[-1][0])
            for k in range(weeks - 1, -1, -1):
                day = (last - dt.timedelta(days=7 * k)).isoformat()
                now = tells._vals(pts, day, 1)
                base = tells._before(pts, day, 1, 90)
                thr = max(5.0, 2 * statistics.median(base)) if len(base) >= 30 else None
                o["w"].append([day, round(now[0], 1) if now else None, _r(thr, 1)])
        out[t] = o
    return out


def _seam(sid):
    """The first day of the live advisory readings (one level per country, from October 2026). The archive before it summed
    every item filed under a code, so a step on that day is the change of method, not a change of advice."""
    if not sid.startswith("state_"):
        return None
    import store
    live = store.daily("state_dep_main_" + sid[len("state_dep_"):] if sid.startswith("state_dep_") else "state_main_" + sid[len("state_"):])
    return live[0][0][:10] if live else None


def _steps(pts, since, seam=None):
    """(day, before, after) for every change of value on or after `since` in a flat series, leaving out the `seam` day."""
    out = []
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if d1 >= since and v1 != v0 and d1[:10] != seam:
            out.append((d1, v0, v1))
    return out


def _n(v):
    return f"{v:g}"


def hist_json(res, by_id, days=HIST_DAYS, fwd=FORWARD_DIR):
    """Per theatre, the last `days` days: the standing risk from the forward record ([[day, times usual, chance, level]])
    and a timeline ([[day, kind, text, series id]]) of tells fired, advisory steps, UK advice updates, CrisisWatch ratings
    and strike waves. Built from the hash-chained records and the stored series, so it is the same on every run."""
    import tells
    last = max((s["points"][-1][0] for s in res["series"] if s.get("points") and s["kind"] == "daily"), default=None)
    if not last:
        return {}
    since = (dt.date.fromisoformat(last[:10]) - dt.timedelta(days=days)).isoformat()
    out = {t: {"risk": [], "items": []} for t in res["theatres"]}
    for r in _csv(os.path.join(fwd, "log.csv")):
        t = r.get("theatre")
        if t in out and r.get("date", "") >= since and r.get("p"):
            p, b = float(r["p"]), float(r["base"]) if r.get("base") else None
            out[t]["risk"].append([r["date"], round(p / b, 2) if b else None, round(p, 4), r.get("level") or ""])
    names = {x["id"]: x["name"] for x in tells.TELLS}
    seen = {}
    for r in _csv(os.path.join(fwd, "tells.csv")):
        t, k = r.get("theatre"), r.get("tell")
        on = r.get("on") == "1"
        if t in out and on and not seen.get((t, k)) and r.get("date", "") >= since:
            out[t]["items"].append([r.get("fired") or r["date"], "tell", names.get(k, k), r.get("src") or None])
        seen[(t, k)] = on
    for t, L in (res.get("tells") or {}).items():    # today's firings, before the record has them
        for x in L:
            if t in out and x.get("on") and x.get("date") and not any(i[1] == "tell" and i[2] == x["n"] for i in out[t]["items"]):
                out[t]["items"].append([x["date"], "tell", x["n"], x.get("src")])
    for t in out:
        it = out[t]["items"]
        s = by_id.get(f"state_{t}")
        for d, a, b in _steps(s.get("points") or [], since, _seam(s["id"])) if s else []:
            it.append([d, "advisory", f"US travel advisories {'raised' if b > a else 'lowered'}: level sum {_n(a)} to {_n(b)}", s["id"]])
        s = by_id.get(f"state_dep_{t}")
        for d, a, b in _steps(s.get("points") or [], since, _seam(s["id"])) if s else []:
            it.append([d, "advisory", f"US ordered or authorised departures: {_n(a)} to {_n(b)} countr{'y' if b == 1 else 'ies'}", s["id"]])
        s = by_id.get(f"fcdo_{t}")
        wk = {}    # UK advice is rewritten often: one line per week, on its latest day
        for d, v in (s.get("points") or []) if s else []:
            if d >= since and v > 0:
                wk.setdefault(dt.date.fromisoformat(d[:10]).isocalendar()[:2], []).append(d)
        for days_ in wk.values():
            it.append([max(days_), "advice", "UK travel advice updated" + (f" on {len(days_)} days that week" if len(days_) > 1 else ""), s["id"]])
        s = by_id.get(f"crisiswatch_{t}")
        for d, v in (s.get("points") or []) if s else []:
            if d >= since[:7] and v > 0:
                it.append([d[:7], "rating", "CrisisWatch: " + CW_WORDS[max(0, min(3, int(round(v))))], s["id"]])
        if t in TEMPO and by_id.get(TEMPO[t][0]):
            s = by_id[TEMPO[t][0]]
            for d in (x.isoformat() for x in tells.wave_onsets([tuple(p) for p in s.get("points") or []])):
                if d >= since:
                    it.append([d, "wave", "Strike wave: alert waves doubled against their usual count", s["id"]])
        it.sort(key=lambda i: i[0], reverse=True)
    return out


def official_json(by_id, t):
    """What governments and Crisis Group say about the theatre now: [{n: what, v: reading, d: date, id}]."""
    out = []
    s = by_id.get(f"state_{t}")
    if s and s.get("points"):
        p = s["points"]
        st = _steps(p, p[0][0], _seam(s["id"]))
        n = len(C.STATE_ISO.get(t, []))
        out.append({"n": "US travel advisories", "id": s["id"], "d": st[-1][0] if st else None,
                    "v": f"level sum {_n(p[-1][1])} across {n} countr{'y' if n == 1 else 'ies'} (each 1 to 4)" +
                         (f"; last step {'up' if st[-1][2] > st[-1][1] else 'down'} from {_n(st[-1][1])}" if st else "; no step on record")})
    s = by_id.get(f"state_dep_{t}")
    if s and s.get("points"):
        v = s["points"][-1][1]
        out.append({"n": "US ordered or authorised departures", "id": s["id"], "d": s["points"][-1][0],
                    "v": f"{_n(v)} countr{'y' if v == 1 else 'ies'}" if v else "none now"})
    s = by_id.get(f"fcdo_{t}")
    if s and s.get("points"):
        up = [d for d, v in s["points"] if v > 0]
        last = s["points"][-1][0]
        recent = sum(1 for d in up if d >= (dt.date.fromisoformat(last) - dt.timedelta(days=30)).isoformat())
        out.append({"n": "UK travel advice", "id": s["id"], "d": up[-1] if up else None,
                    "v": (f"updated on {recent} day{'' if recent == 1 else 's'} in the last 30" if recent else "no update in the last 30 days")})
    s = by_id.get(f"crisiswatch_{t}")
    if s and s.get("points"):
        d, v = s["points"][-1]
        out.append({"n": "CrisisWatch (Crisis Group)", "id": s["id"], "d": d[:7], "v": CW_WORDS[max(0, min(3, int(round(v))))]})
    return out


def feed_items(data, days=8):
    """The This-week list, as the page builds it: tells fired, official steps and ratings, and the strongest fast readings."""
    out = []
    gen = data["generated"][:10]
    cut = (dt.date.fromisoformat(gen) - dt.timedelta(days=days)).isoformat() if gen[:4].isdigit() else ""
    name = {t: v.get("name", t) for t, v in data["theatres"].items()}
    for t, v in data["theatres"].items():
        for x in v.get("tells") or []:
            if x.get("on"):
                out.append({"d": x.get("date") or gen, "t": t, "title": f"{name[t]}: {x['n']}", "sub": "Timing tell. " + x["says"], "hot": 1})
    for t, h in (data.get("hist") or {}).items():
        for d, kind, text, sid in h["items"]:
            if kind in ("advisory", "rating", "wave") and d >= cut[:len(d)]:
                out.append({"d": d, "t": t, "title": f"{name.get(t, t)}: {text}", "sub": "Official signal" if kind != "wave" else "Tempo", "hot": 0})
    strong = [s for s in data["series"] if s.get("z") is not None and s["z"] >= C.THRESH_SIGNAL and not s["lag"] and not s.get("stale")
              and not s.get("tf") and s["t"] != "global" and s.get("last", "") >= cut]
    for s in sorted(strong, key=lambda s: -s["z"])[:6]:
        out.append({"d": s["last"], "t": s["t"], "title": f"{name.get(s['t'], s['t'])}: {s['l']}", "sub": f"Strong reading, +{s['z']:.1f} SD from normal", "hot": 0})
    out.sort(key=lambda f: (f["hot"], f["d"]), reverse=True)
    return out


def feed_xml(data, site="https://khourix.github.io/warwatch/"):
    """An RSS 2.0 feed of the This-week items, written next to the page so anyone can subscribe without a server."""
    from email.utils import format_datetime
    from xml.sax.saxutils import escape

    def when(d):
        try:
            return format_datetime(dt.datetime.fromisoformat(d[:10] if len(d) >= 10 else d + "-01").replace(tzinfo=dt.timezone.utc))
        except ValueError:
            return ""
    items = "".join(
        f"<item><title>{escape(f['title'])}</title><link>{escape(site)}#{escape(f['t'])}</link><description>{escape(f['sub'])}</description>"
        f"<guid isPermaLink=\"false\">{escape(f['t'] + '|' + f['d'] + '|' + f['title'])}</guid><pubDate>{when(f['d'])}</pubDate></item>"
        for f in feed_items(data))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>WarWatch: this week</title>'
            f"<link>{escape(site)}</link><description>Timing tells, official steps and strong readings for 17 theatres in 6 regions. "
            f"Built {escape(data['generated'])}.</description>{items}</channel></rss>\n")


def forward_json(series):
    """The track-record panel (forward_score.scorecard); the page must build without it."""
    try:
        import forward_score
        return forward_score.scorecard(series)
    except Exception as e:
        print("forward scorecard skipped:", str(e)[:200])
        return None


def model_json(m):
    if not m:
        return None
    g = m["global"]
    return {"v": m["version"], "fitted": m["fitted"], "active": m["active"], "bands": m["bands"], "gates": m["gates"],
            "any": _r(g["p_any"], 4), "mm": _r(g["p_market_moving"], 4), "clim": g["clim"]}


def render(result, generated, demo=False, extras=None, topo=None):
    return page_html(build_data(result, generated, demo, extras, topo), generated)


INLINE_PTS = 60     # points per series kept in the page; the rest are in series.json


def split_series(data):
    """Moves each series' older points and its score history out of the page data and returns them as {id: {pts, zh}},
    for series.json. Actions and ratings keep their whole history inline: the page words their steps from it."""
    full = {}
    for s in data["series"]:
        if s.get("tf"):
            continue
        x = {}
        if len(s.get("pts") or []) > INLINE_PTS:
            x["pts"] = s["pts"]
            s["pts"] = s["pts"][-INLINE_PTS:]
        if s.get("zh"):
            x["zh"] = s.pop("zh")
        if x:
            full[s["id"]] = x
    return full


def page_html(data, generated, out_dir=None):
    """The page with its data inlined. With out_dir, the full series histories go to out_dir/series.json, which the page
    loads after its first paint, so the first load carries about a third of the data."""
    if out_dir:
        import copy
        from urllib.parse import quote
        data = copy.deepcopy(data)
        with open(os.path.join(out_dir, "series.json"), "w", encoding="utf-8") as f:
            json.dump(split_series(data), f, separators=(",", ":"), ensure_ascii=False)
        data["split"] = "series.json?v=" + quote(generated, safe="")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028")
    with open(os.path.join(HERE, "page.html"), encoding="utf-8") as f:
        page = f.read()
    return page.replace("__DATA__", blob).replace("__GENERATED__", generated)
