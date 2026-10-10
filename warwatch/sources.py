"""Free public-data fetchers. Parsers are pure and pinned by tests; response
shapes were verified from a GitHub runner on 2026-10-06 except where a
function's docstring says UNVERIFIED (needs a key nobody has supplied yet).
"""
import datetime as dt
import base64
import csv
import gzip
import io
import re
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import config as C

TIMEOUT = 60
PW = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"


def get(url, data=None, retries=3, raw=False, wait=6, headers=None, timeout=None):
    hdr = {"User-Agent": C.USER_AGENT}
    hdr.update(headers or {})
    if data is not None:
        data = json.dumps(data).encode()
        hdr["Content-Type"] = "application/json"
    err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdr), timeout=timeout or TIMEOUT) as r:
                b = r.read()
                if b[:2] == b"\x1f\x8b":
                    b = gzip.decompress(b)
                body = b.decode("utf-8")
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace").replace("\n", " ")[:160]
            except Exception:
                body = ""
            err = f"{e} {body}"
            if getattr(e, "code", 0) in (400, 401, 403, 404):
                break
            time.sleep(wait * (i + 1))
        except Exception as e:
            err = e
            time.sleep(wait * (i + 1))
    raise RuntimeError(f"{str(err)[:230]} @ {url.split('?')[0][:60]}")


def month_range(n_months=36, today=None):
    t = today or dt.date.today()
    y, m = t.year, t.month
    out = []
    for _ in range(n_months):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted(out)


# ---- USAspending: monthly obligations by PSC or NAICS ------------------------
def parse_usaspending(payload):
    """Fiscal month 1 is October; label with the calendar month."""
    out = []
    for r in payload.get("results", []):
        fy, fm = int(r["time_period"]["fiscal_year"]), int(r["time_period"]["month"])
        year = fy - 1 if fm <= 3 else fy
        out.append((f"{year:04d}-{(fm + 8) % 12 + 1:02d}", float(r.get("aggregated_amount") or 0)))
    return sorted(out)


def fetch_usaspending(psc=None, naics=None, years=6, pop=None, dod=False):
    """pop: ISO-3 country codes of the place of performance; dod: Department of Defense awards only."""
    end = dt.date.today()
    f = {"time_period": [{"start_date": f"{end.year - years}-01-01", "end_date": end.isoformat()}],
         "award_type_codes": ["A", "B", "C", "D"]}
    if psc:
        f["psc_codes"] = psc
    if naics:
        f["naics_codes"] = naics
    if pop:
        f["place_of_performance_locations"] = [{"country": c} for c in pop]
    if dod:
        f["agencies"] = [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}]
    return parse_usaspending(get("https://api.usaspending.gov/api/v2/search/spending_over_time/",
                                 {"group": "month", "filters": f}))


# ---- Eurostat Comext: EU exports by HS product to partner set ----------------
def decode_jsonstat(p):
    """Yield (coords dict, value) for every populated cell of a JSON-stat cube."""
    ids, sizes = p["id"], p["size"]
    inv = []
    for d in ids:
        idx = p["dimension"][d]["category"]["index"]
        inv.append({v: k for k, v in idx.items()} if isinstance(idx, dict) else dict(enumerate(idx)))
    for flat, val in p.get("value", {}).items():
        i, coords = int(flat), {}
        for d, size, names in reversed(list(zip(ids, sizes, inv))):
            coords[d] = names[i % size]
            i //= size
        yield coords, val


def parse_comext(p):
    """Sum over EU member reporters (aggregates such as EU27 are skipped)."""
    by = {}
    for c, v in decode_jsonstat(p):
        if c["reporter"].startswith(("EU", "EA", "EX")):
            continue
        by[c["time"]] = by.get(c["time"], 0.0) + float(v or 0)
    return sorted(by.items())


def fetch_comext(product, partners, since="2022-01"):
    q = [("format", "JSON"), ("lang", "EN"), ("freq", "M"), ("flow", "2"),
         ("product", product), ("indicators", "VALUE_IN_EUROS"), ("sinceTimePeriod", since)]
    q += [("partner", p) for p in partners]
    return parse_comext(get("https://ec.europa.eu/eurostat/api/comext/dissemination/"
                            "statistics/1.0/data/DS-045409?" + urllib.parse.urlencode(q)))


# ---- US Census: exports by HS6 to named partners (needs CENSUS_API_KEY) ------
def parse_census(rows, names):
    """UNVERIFIED live. rows = [header, *data] as the Census API returns."""
    if not rows:
        return []
    h = rows[0]
    ci, vi, ti = h.index("CTY_NAME"), h.index("ALL_VAL_MO"), h.index("time")
    by = {}
    for r in rows[1:]:
        if any(n in r[ci].upper() for n in names):
            by[r[ti]] = by.get(r[ti], 0.0) + float(r[vi] or 0)
    return sorted(by.items())


def fetch_census(hs6_list, names, key, since="2022-01"):
    tot = {}
    now = dt.date.today()
    for hs in hs6_list:
        q = urllib.parse.urlencode({"get": "CTY_CODE,CTY_NAME,ALL_VAL_MO", "COMM_LVL": "HS6",
                                    "E_COMMODITY": hs, "time": f"from {since} to {now.year}-{now.month:02d}",
                                    "key": key})
        for t, v in parse_census(get("https://api.census.gov/data/timeseries/intltrade/exports/hs?" + q), names):
            tot[t] = tot.get(t, 0.0) + v
    return sorted(tot.items())


# ---- TED (EU tenders): notices per month for a CPV code ----------------------
def ted_query(cpv, month):
    y, m = int(month[:4]), int(month[5:])
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return (f"classification-cpv={cpv} AND publication-date>={y}{m:02d}01 "
            f"AND publication-date<={y}{m:02d}{last:02d}")


def parse_ted_count(p):
    return int(p["totalNoticeCount"])


def _ted_month(cpvs, mo):
    return (mo, float(sum(parse_ted_count(get("https://api.ted.europa.eu/v3/notices/search",
                                              {"query": ted_query(c, mo), "fields": ["publication-number"], "limit": 1}))
                          for c in cpvs)))


def fetch_ted(cpvs, months=48):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        return sorted(ex.map(lambda mo: _ted_month(cpvs, mo), month_range(months)))


# ---- SAM.gov US tenders per month (needs SAM_API_KEY) ------------------------
def parse_sam(p):
    """-> {day: count} from opportunitiesData postedDate."""
    by = {}
    for o in p.get("opportunitiesData", []) or []:
        d = (o.get("postedDate") or "")[:10]
        if len(d) == 10:
            by[d] = by.get(d, 0) + 1
    return by


def fetch_sam(ccodes, key, days=360):
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    by = {}
    for cc in ccodes:
        off = 0
        while off < 5000:
            q = urllib.parse.urlencode({"api_key": key, "limit": 1000, "offset": off, "ccode": cc,
                                        "postedFrom": start.strftime("%m/%d/%Y"),
                                        "postedTo": end.strftime("%m/%d/%Y")})
            p = get("https://api.sam.gov/opportunities/v2/search?" + q)
            for m, n in parse_sam(p).items():
                by[m] = by.get(m, 0) + n
            off += 1000
            if off >= int(p.get("totalRecords", 0)):
                break
    # days with no postings are real zeros, so fill them between the first and last day
    out, d = [], dt.date.fromisoformat(min(by)) if by else None
    while by and d <= dt.date.fromisoformat(max(by)):
        out.append((d.isoformat(), float(by.get(d.isoformat(), 0))))
        d += dt.timedelta(days=1)
    return out


# ---- IMF PortWatch: daily chokepoint transits ---------------------------------
def parse_portwatch(p):
    return sorted((f["attributes"]["date"], float(f["attributes"]["n_total"]))
                  for f in p.get("features", []))


def fetch_portwatch(name_fragment, days=900):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    where = f"portname LIKE '%{name_fragment}%' AND date >= DATE '{since}'"
    q = urllib.parse.urlencode({"where": where, "outFields": "date,portname,n_total",
                                "returnGeometry": "false", "orderByFields": "date ASC",
                                "resultRecordCount": 2000, "f": "json"})
    return parse_portwatch(get(PW + "Daily_Chokepoints_Data/FeatureServer/0/query?" + q))


def fetch_portwatch_ports(iso3, names=(), field="portcalls", days=300):
    """Daily vessel calls summed over the named ports of one country (all its ports if no name). IMF PortWatch, keyless."""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    where = f"ISO3 = '{iso3}' AND date >= DATE '{since}'"
    if names:
        where += " AND (" + " OR ".join(f"portname LIKE '%{n}%'" for n in names) + ")"
    by, offset = {}, 0
    while True:
        q = urllib.parse.urlencode({"where": where, "outFields": f"date,{field}", "returnGeometry": "false", "orderByFields": "date ASC",
                                    "resultOffset": offset, "resultRecordCount": 2000, "f": "json"})
        p = get(PW + "Daily_Ports_Data/FeatureServer/0/query?" + q)
        feats = p.get("features", [])
        for f in feats:
            a = f["attributes"]
            d = a["date"]
            if isinstance(d, (int, float)):
                d = dt.datetime.fromtimestamp(d / 1000, dt.timezone.utc).date().isoformat()
            by[d] = by.get(d, 0) + float(a.get(field) or 0)
        if not p.get("exceededTransferLimit") or not feats:
            break
        offset += len(feats)
    return sorted(by.items())


# ---- Advisories ---------------------------------------------------------------
def fcdo_daily(p, days=900, today=None):
    """FCDO advice updates per day, rebuilt from the page's own change history."""
    today = today or dt.date.today()
    by = {}
    for h in p["details"].get("change_history", []):
        d = h["public_timestamp"][:10]
        by[d] = by.get(d, 0) + 1
    return [((today - dt.timedelta(days=i)).isoformat(),
             float(by.get((today - dt.timedelta(days=i)).isoformat(), 0)))
            for i in range(days, -1, -1)]


def fetch_fcdo(slugs):
    tot = {}
    for s in slugs:
        for d, v in fcdo_daily(get(f"https://www.gov.uk/api/content/foreign-travel-advice/{s}")):
            tot[d] = tot.get(d, 0.0) + v
    return sorted(tot.items())


def _norm_country(t):
    t = re.sub(r"[^a-z ]", " ", t.lower()).split()
    return " ".join(w for w in t if w != "the")


def state_country_item(items, code, name=None):
    """-> (level, item) for one country's main advisory (Title 'X - Level 3: ...'), or (None, None) when the feed has none.
    Several items under one code: the one titled with the country's name; failing that, the highest."""
    got = []
    for it in items:
        if code not in it.get("Category", []):
            continue
        title = it.get("Title", "")
        try:
            lv = int(title.split("Level ")[1][0])
        except (IndexError, ValueError):
            continue
        got.append((_norm_country(title.split(" - ")[0]), lv, it))
    if not got:
        return None, None
    if name:
        named = [(lv, it) for t, lv, it in got if t == _norm_country(name)]
        if named:
            return named[0]
    lv, it = max(((lv, it) for _, lv, it in got), key=lambda x: x[0])
    return lv, it


def state_country_level(items, code, name=None):
    return state_country_item(items, code, name)[0]


DEPART = re.compile(r"(?:ordered|authori[sz]ed)\s+(?:the\s+)?departure", re.I)    # as backfill/sources_slow.py reads the archived pages


def state_departures(items, iso_list, names=None):
    """Countries whose main US advisory mentions an ordered or an authorised departure of staff or families."""
    names = names if names is not None else C.STATE_NAME
    n = 0
    for c in iso_list:
        it = state_country_item(items, c, names.get(c))[1]
        n += bool(it and DEPART.search(f"{it.get('Title', '')} {it.get('Summary', '')}"))
    return float(n)


def state_levels(items, iso_list, names=None):
    """Sum over the countries of each one's main US advisory level: the same quantity the archived country pages
    give for the history (backfill/sources_slow.py), so the live series continues it without a step."""
    names = names if names is not None else C.STATE_NAME
    return float(sum(state_country_level(items, c, names.get(c)) or 0 for c in iso_list))


_STATE = {}


def fetch_state():
    """One download per run: thirteen theatres read the same feed, and the host throttles repeat calls."""
    if "v" not in _STATE:
        _STATE["v"] = get("https://cadataapi.state.gov/api/TravelAdvisories")
    return _STATE["v"]


# ---- ADS-B: military aircraft in a box (snapshot only; history is stored) ----
AIRLIFT = {"C17", "C130", "C30J", "A400", "K35R", "KC10", "K35T", "A332", "IL76", "B752"}


def adsb_counts(p, box):
    la0, la1, lo0, lo1 = box
    tot = lift = 0
    for a in p.get("ac", []):
        la, lo = a.get("lat"), a.get("lon")
        if la is None or lo is None or not (la0 <= la <= la1 and lo0 <= lo <= lo1):
            continue
        tot += 1
        lift += a.get("t") in AIRLIFT
    return float(tot), float(lift)


_ADSB = {}


TANKER = {"K35R", "KC10", "K35T", "KC46", "K46", "A332", "A310", "MRTT"}
ISR = {"P8", "E3TF", "E3CF", "E3", "E6", "E737", "R135", "RC35", "E8", "Q4", "MQ9", "U2", "E2", "E2C", "P3", "RC12", "RQ4", "GLEX", "C560"}
ISR = ISR - {"C560"}
FIGHTER = {"F16", "F15", "F35", "F18", "F18H", "F18S", "FA18", "F22", "EUFI", "RFAL", "GRIF", "A10", "TORN", "F14", "SU27", "SU30", "SU35", "MG29", "SU34"}


def adsb_classes(p, box):
    """Military aircraft in a lat/lon box by role -> dict(mil, lift, tanker, isr, fighter)."""
    la0, la1, lo0, lo1 = box
    out = {"mil": 0.0, "lift": 0.0, "tanker": 0.0, "isr": 0.0, "fighter": 0.0}
    for a in p.get("ac", []):
        la, lo = a.get("lat"), a.get("lon")
        if la is None or lo is None or not (la0 <= la <= la1 and lo0 <= lo <= lo1):
            continue
        t = a.get("t")
        out["mil"] += 1
        out["lift"] += t in AIRLIFT
        out["tanker"] += t in TANKER
        out["isr"] += t in ISR
        out["fighter"] += t in FIGHTER
    return out


def fetch_adsb():
    """One call per run: every ADS-B series reads the same snapshot."""
    if "mil" not in _ADSB:
        _ADSB["mil"] = get("https://api.adsb.lol/v2/mil")
    return _ADSB["mil"]


# ---- Google News RSS: headline counts for warning phrases, rebuilt day by day -----
def parse_gnews_count(xml):
    """Number of <item> headlines in a Google News RSS response (a query returns at most 100)."""
    return float(xml.count("<item>"))


def gnews_day(query, day):
    q = urllib.parse.urlencode({"q": f"{query} after:{day} before:{day + dt.timedelta(days=1)}",
                                "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return parse_gnews_count(get("https://news.google.com/rss/search?" + q, raw=True, retries=2, wait=10))


def fetch_gnews(sid, query, days=120, max_requests=None, today=None):
    """Daily headline counts for `query`. The cache (history/cache/<sid>.csv) is extended
    by whichever days are missing, newest first, at most `max_requests` per run, so the
    history fills over a few runs and needs only a handful of calls afterwards."""
    import store
    today = today or dt.date.today()
    cap = max_requests if max_requests is not None else int(os.environ.get("GNEWS_MAX", "12"))
    have = dict(store.cache_load(sid))
    want = [today - dt.timedelta(days=i) for i in range(1, days + 1)]
    for d in [d for d in want if d.isoformat() not in have][:cap]:
        try:
            have[d.isoformat()] = gnews_day(query, d)
        except Exception:
            break
        time.sleep(1.5)
    return sorted(have.items())[-days:]


# ---- GDELT 1.0 daily event files (data.gdeltproject.org is not blocked, unlike the DOC API) ----
GDELT_ROOTS = ("13", "15", "18", "19")   # 13 threaten, 15 exhibit military posture, 18 assault, 19 fight
_GDELT_DONE = {}


def gdelt_url(day):
    return f"http://data.gdeltproject.org/events/{day:%Y%m%d}.export.CSV.zip"


def parse_gdelt_events(rows, ccs):
    """rows: tab-split GDELT 1.0 event lines -> {(cc, root): events, (cc, "all"): all events}. ActionGeo country is column 51, root code 28."""
    out = {}
    for r in rows:
        if len(r) > 51 and r[51] in ccs:
            k = (r[51], "all")
            out[k] = out.get(k, 0) + 1
            if r[28] in GDELT_ROOTS:
                k = (r[51], r[28])
                out[k] = out.get(k, 0) + 1
    return out


def gdelt_day(day, ccs):
    import csv
    import io
    import zipfile
    err = None
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(gdelt_url(day), headers={"User-Agent": C.USER_AGENT}), timeout=120) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rd = csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"), delimiter="\t")
            return parse_gdelt_events(rd, ccs)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(f"GDELT file for {day} not published yet")
            err = e
        except Exception as e:
            err = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"GDELT {day}: {str(err)[:120]}")


GDELT_HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backtest", "history", "gdelt_country_day.csv.gz")
_GH = {}


def gdelt_history():
    """The committed daily history (2018 on; columns day, country, root, events; roots 13, 15, 18, 19 and all) as
    {(cc, root): {day: events}}. Read once per process."""
    if "v" not in _GH:
        import csv
        import gzip
        import io
        idx = {}
        try:
            with gzip.open(GDELT_HISTORY, "rt", newline="") as f:
                for d, cc, root, n in csv.reader(f):
                    idx.setdefault((cc, root), {})[d] = float(n)
        except OSError:
            pass
        _GH["v"] = idx
    return _GH["v"]


def gdelt_update(days=150, max_days=None, today=None):
    """Extend history/cache/gdelt_events.csv by the days after the committed history (newest first, at most max_days per run).
    A day counts as missing while any watched country has no 'all' row for it, so adding a theatre back-fills it."""
    import store
    if _GDELT_DONE.get("v"):
        return
    _GDELT_DONE["v"] = True
    today = today or dt.date.today()
    cap = max_days if max_days is not None else int(os.environ.get("GDELT_MAX", "6"))
    ccs = {c for v in C.GDELT_CC.values() for c in v}
    last = max((d for days_ in gdelt_history().values() for d in days_), default="")
    rows = store.cache_rows("gdelt_events")
    have = {}
    for r in rows:
        if r[2] == "all":
            have.setdefault(r[0], set()).add(r[1])
    want = [today - dt.timedelta(days=i) for i in range(1, days + 1)]
    new = []
    for d in [d for d in want if d.isoformat() > last and not ccs <= have.get(d.isoformat(), set())][:cap]:
        try:
            counts = gdelt_day(d, ccs)
        except RuntimeError:
            continue
        rows = [r for r in rows if r[0] != d.isoformat()]   # a day cached before 'all' counts existed is replaced whole
        for cc in sorted(ccs):
            for root in GDELT_ROOTS + ("all",):
                new.append([d.isoformat(), cc, root, str(counts.get((cc, root), 0))])
    if new:
        store.cache_rows_save("gdelt_events", rows + new)


def gdelt_series(theatre, roots, share=False):
    """Daily event count for a theatre's countries and CAMEO root codes: the committed history, then the cache for later days.
    share=True gives events per 1,000 of all events coded in those countries (days with at least 50 events)."""
    import store
    ccs = C.GDELT_CC[theatre]
    idx = {k: dict(v) for k, v in gdelt_history().items() if k[0] in ccs}
    for d, cc, root, n in store.cache_rows("gdelt_events"):
        if cc in ccs:
            idx.setdefault((cc, root), {})[d] = float(n)
    tot, allv = {}, {}
    for (cc, root), days_ in idx.items():
        for d, n in days_.items():
            if root in roots:
                tot[d] = tot.get(d, 0.0) + n
            elif root == "all":
                allv[d] = allv.get(d, 0.0) + n
    if not share:
        return sorted(tot.items())
    return sorted((d, 1000.0 * tot.get(d, 0.0) / allv[d]) for d in allv if allv[d] >= 50)


# ---- Global Fishing Watch vessel presence (AIS from terrestrial and satellite receivers; token needed; ~5 days late) ----------
GFW = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"


def parse_gfw_presence(payload):
    """4wings report -> [(date, vessel-hours)] summed over flags and cells."""
    by = {}
    for e in payload.get("entries", []):
        for rows in e.values():
            for x in rows:
                by[x["date"]] = by.get(x["date"], 0.0) + float(x.get("hours") or 0)
    return sorted(by.items())


def fetch_gfw_presence(box, token, days=150, today=None):
    """box = (lat_min, lat_max, lon_min, lon_max). Vessel-hours of AIS presence per day inside the box."""
    la0, la1, lo0, lo1 = box
    end = (today or dt.date.today()) - dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
    q = urllib.parse.urlencode({"spatial-resolution": "LOW", "temporal-resolution": "DAILY", "group-by": "FLAG", "datasets[0]": "public-global-presence:latest",
                                "date-range": f"{start},{end}", "format": "JSON"})
    body = {"geojson": {"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}}
    return parse_gfw_presence(get(GFW + "?" + q, data=body, headers={"Authorization": "Bearer " + token}, timeout=180, retries=2))


# ---- IODA (Georgia Tech internet outage detection, no key) --------------------------------------
def parse_ioda(payload):
    """-> {day: mean value} for the first returned signal (visible prefixes or responsive /24 blocks)."""
    s = payload["data"][0][0]
    step, t0 = s["step"], s["from"]
    by = {}
    for i, v in enumerate(s["values"]):
        if v is None:
            continue
        d = dt.datetime.fromtimestamp(t0 + i * step, dt.timezone.utc).date().isoformat()
        by.setdefault(d, []).append(float(v))
    return {d: sum(v) / len(v) for d, v in by.items()}


def fetch_ioda(cc, source="bgp", days=150):
    """Daily mean of an IODA signal for a country. The API refuses very long ranges, so ask in 60-day chunks."""
    now = int(time.time())
    today = dt.datetime.fromtimestamp(now, dt.timezone.utc).date().isoformat()
    tot = {}
    end = now
    for _ in range(-(-days // 60)):
        start = end - 60 * 86400
        q = urllib.parse.urlencode({"from": start, "until": end, "datasource": source})
        tot.update(parse_ioda(get(f"https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/country/{cc}?" + q)))
        end = start
    tot.pop(today, None)    # today is partial
    return sorted(tot.items())[-days:]


# ---- OONI: share of web tests showing interference per country (no key) ----------------------------
def parse_ooni(p, min_n=50):
    return sorted((r["measurement_start_day"], r["anomaly_count"] / r["measurement_count"])
                  for r in p.get("result", []) if r.get("measurement_count", 0) >= min_n)


def fetch_ooni(cc, days=150):
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    until = dt.date.today().isoformat()
    q = urllib.parse.urlencode({"probe_cc": cc, "test_name": "web_connectivity", "since": since, "until": until,
                                "axis_x": "measurement_start_day"})
    return parse_ooni(get("https://api.ooni.io/api/v1/aggregation?" + q))[:-1]    # today is partial


# ---- Cloudflare Radar (free API token, CLOUDFLARE_API_TOKEN) -----------------------------------------
def parse_radar(p):
    """-> [(day, value)] from a Radar timeseries answer."""
    s = p["result"]["serie_0"]
    out = {}
    for t, v in zip(s["timestamps"], s.get("values") or s.get("total") or []):
        if v is None:
            continue
        out.setdefault(t[:10], []).append(float(v))
    return sorted((d, sum(v) / len(v)) for d, v in out.items())


def fetch_radar(path, cc, token, chunks=5):
    """Radar refuses daily buckets over long ranges, so ask for 28-day windows and stitch them."""
    out = {}
    end = dt.date.today()
    for _ in range(chunks):
        start = end - dt.timedelta(days=28)
        q = urllib.parse.urlencode({"location": cc, "dateStart": start.isoformat() + "T00:00:00Z", "dateEnd": end.isoformat() + "T00:00:00Z",
                                    "aggInterval": "1d", "format": "json"})
        out.update(dict(parse_radar(get(f"https://api.cloudflare.com/client/v4/radar/{path}?{q}", headers={"Authorization": "Bearer " + token}))))
        end = start
    return sorted(out.items())[:-1]


# ---- Energy-Charts (Fraunhofer ISE; keyless; replaces ENTSO-E) ---------------------------------------
def fetch_energycharts_price(bzn, days=200):
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    p = get(f"https://api.energy-charts.info/price?bzn={urllib.parse.quote(bzn)}&start={start}&end={dt.date.today().isoformat()}")
    by = {}
    for t, v in zip(p["unix_seconds"], p["price"]):
        if v is not None:
            by.setdefault(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), []).append(float(v))
    return sorted((d, sum(v) / len(v)) for d, v in by.items())[:-1]


# ---- GIE AGSI+ gas storage (keyless for the public pages) -------------------------------------------
def fetch_agsi(area, key_value, field="gasInStorage", days=300):
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    key = {"eu": "continent=eu"}.get(area, "country=" + area)
    out, page = {}, 1
    while page <= 14:
        p = get(f"https://agsi.gie.eu/api?{key}&from={start}&to={dt.date.today().isoformat()}&page={page}", headers={"x-key": key_value})
        if p.get("error"):
            raise RuntimeError("AGSI: " + str(p.get("message") or p["error"]))
        for r in p.get("data", []):
            try:
                out[r["gasDayStart"]] = float(r[field])
            except (KeyError, TypeError, ValueError):
                pass
        if page >= int(p.get("last_page", 1)):
            break
        page += 1
    return sorted(out.items())


# ---- GPSJam: daily share of aircraft reporting degraded GPS, per theatre box (keyless; needs the h3 package) ----
_GPSJAM_DONE = False


def parse_gpsjam(text, boxes, centre, min_aircraft=20):
    """-> {theatre: percent of aircraft with bad GPS} for one day's CSV (hex,count_good_aircraft,count_bad_aircraft)."""
    tot = {t: [0, 0] for t in boxes}
    lines = text.splitlines()[1:]
    for ln in lines:
        p = ln.split(",")
        if len(p) < 3:
            continue
        try:
            good, bad = int(p[1]), int(p[2])
        except ValueError:
            continue
        la, lo = centre(p[0])
        for t, (la0, la1, lo0, lo1) in boxes.items():
            if la0 <= la <= la1 and lo0 <= lo <= lo1:
                tot[t][0] += good
                tot[t][1] += bad
    return {t: 100.0 * b / (g + b) for t, (g, b) in tot.items() if g + b >= min_aircraft}


def gpsjam_update(boxes, store, per_run=None, keep=150):
    """Fills one cache per theatre from gpsjam.org's daily files, a few missing days per run, newest first."""
    global _GPSJAM_DONE
    per_run = per_run or int(os.environ.get("GPSJAM_MAX", "25"))
    if _GPSJAM_DONE:
        return
    _GPSJAM_DONE = True
    try:
        import h3
    except ImportError:
        return      # the build installs h3; without it only the cache is read
    cell = getattr(h3, "cell_to_latlng", None) or h3.h3_to_geo
    memo = {}

    def centre(hx):
        if hx not in memo:
            memo[hx] = cell(hx)
        return memo[hx]
    have = {t: dict(store.cache_load(f"gpsjam_{t}")) for t in boxes}
    today = dt.date.today()
    todo = [d.isoformat() for d in (today - dt.timedelta(days=i) for i in range(2, keep + 2)) if d.isoformat() not in have[next(iter(boxes))]]
    for day in todo[:per_run]:
        try:
            raw = get(f"https://gpsjam.org/data/{day}-h3_4.csv", raw=True, timeout=120, retries=2)
        except Exception:
            continue
        for t, v in parse_gpsjam(raw, boxes, centre).items():
            have[t][day] = v
        for t in boxes:       # a day with too few aircraft is stored as missing, not zero
            have[t].setdefault(day, None)
    for t in boxes:
        store.cache_save(f"gpsjam_{t}", sorted((d, v) for d, v in have[t].items() if v is not None))


# ---- Frankfurter (ECB reference rates, no key) and Twelve Data (free key) ------------------------
def parse_frankfurter(p, ccy):
    return sorted((d, float(v[ccy])) for d, v in p.get("rates", {}).items() if ccy in v)


def fetch_frankfurter(ccy, days=420, base="EUR"):
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    return parse_frankfurter(get(f"https://api.frankfurter.dev/v1/{start}..?from={base}&to={ccy}"), ccy)


def parse_cboe_vix(text):
    """Cboe's public history file: DATE (mm/dd/yyyy), OPEN, HIGH, LOW, CLOSE -> sorted (iso date, close)."""
    out = []
    for r in csv.reader(io.StringIO(text)):
        try:
            m, d, y = r[0].split("/")
            out.append((f"{y}-{int(m):02d}-{int(d):02d}", float(r[4])))
        except (ValueError, IndexError):
            continue    # header or blank line
    return sorted(out)


def fetch_cboe_vix(days=900):
    """VIX close straight from Cboe: no key, posted the same evening (FRED's copy runs two days behind)."""
    req = urllib.request.Request("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
                                 headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"})
    with urllib.request.urlopen(req, timeout=40) as r:
        pts = parse_cboe_vix(r.read().decode("utf-8", "replace"))
    cut = str(dt.date.today() - dt.timedelta(days=days))
    return [p for p in pts if p[0] >= cut]


def parse_twelvedata(p):
    if p.get("status") == "error" or "values" not in p:
        raise ValueError("Twelve Data: " + str(p.get("message", p))[:120])
    return sorted((v["datetime"][:10], float(v["close"])) for v in p["values"])


_TD = {"last": 0.0}


def fetch_twelvedata(symbol, key):
    wait = 8.0 - (time.time() - _TD["last"])   # free plan: 8 requests a minute
    if wait > 0 and _TD["last"]:
        time.sleep(wait)
    _TD["last"] = time.time()
    q = urllib.parse.urlencode({"symbol": symbol, "interval": "1day", "outputsize": 420, "apikey": key})
    return parse_twelvedata(get("https://api.twelvedata.com/time_series?" + q))


def parse_yahoo(p):
    r = (p.get("chart", {}).get("result") or [None])[0]
    if not r:
        raise ValueError("Yahoo: " + str((p.get("chart", {}).get("error") or {}).get("description", "no result"))[:100])
    ts, cl = r.get("timestamp") or [], (r["indicators"]["quote"][0].get("close") or [])
    out = {}
    for t, c in zip(ts, cl):
        if c is not None:
            out[dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()] = float(c)
    return sorted(out.items())


def fetch_yahoo(symbol, rng="2y"):
    """Daily closes from Yahoo Finance's chart endpoint (the one the yfinance package uses): no key, no extra package."""
    q = urllib.parse.urlencode({"range": rng, "interval": "1d"})
    req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{q}",
                                 headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return parse_yahoo(json.loads(r.read().decode("utf-8")))


def fetch_market(symbol):
    """Yahoo first; Twelve Data (free key) only if Yahoo refuses the runner."""
    global _YAHOO_DEAD
    if not _YAHOO_DEAD:
        try:
            pts = fetch_yahoo(symbol)
            if len(pts) > 30:
                return pts
        except urllib.error.HTTPError as e:
            if e.code == 429:    # GitHub runners are rate-limited by Yahoo; stop asking for the rest of this run
                _YAHOO_DEAD = True
            if not os.environ.get("TWELVEDATA_API_KEY"):
                raise
        except Exception:
            if not os.environ.get("TWELVEDATA_API_KEY"):
                raise
    return fetch_twelvedata(symbol, os.environ["TWELVEDATA_API_KEY"])


_YAHOO_DEAD = False


def fetch_fx_current(td_symbol, fred_series, fred_key):
    """A daily exchange rate from Twelve Data (current to yesterday); FRED's H.10 copy (about a week late) if Twelve Data fails."""
    try:
        if not os.environ.get("TWELVEDATA_API_KEY"):
            raise RuntimeError("no Twelve Data key")
        return fetch_twelvedata(td_symbol, os.environ["TWELVEDATA_API_KEY"])
    except Exception:
        if not fred_key:
            raise
        return fetch_fred(fred_series, fred_key)


# ---- FRED (needs FRED_API_KEY) -------------------------------------------------
def parse_fred(p):
    out = []
    for o in p.get("observations", []):
        try:
            out.append((o["date"], float(o["value"])))
        except ValueError:    # FRED uses "." for missing
            pass
    return out


def fetch_fred(series, key, days=900):
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    q = urllib.parse.urlencode({"series_id": series, "api_key": key, "file_type": "json", "observation_start": start})
    return parse_fred(get("https://api.stlouisfed.org/fred/series/observations?" + q))


# ---- HDX HAPI: ACLED conflict-event counts (monthly, by admin area), free with a self-made app identifier ----
_HAPI = {}


def hapi_ident():
    if "id" not in _HAPI:
        _HAPI["id"] = get("https://hapi.humdata.org/api/v2/encode_app_identifier?" + urllib.parse.urlencode(
            {"application": "warwatch", "email": "warwatch@users.noreply.github.com"}))["encoded_app_identifier"]
    return _HAPI["id"]


def parse_hapi_events(rows, types):
    """HAPI conflict-events rows -> [(YYYY-MM, events)] summed over admin areas for the wanted event types."""
    by = {}
    for r in rows:
        if r.get("event_type") in types:
            m = str(r.get("reference_period_start"))[:7]
            by[m] = by.get(m, 0.0) + float(r.get("events") or 0)
    return sorted(by.items())


def fetch_hapi_events(locations, types):
    tot = {}
    for loc in locations:
        off = 0
        while off < 200000:
            p = get("https://hapi.humdata.org/api/v2/coordination-context/conflict-events?" + urllib.parse.urlencode(
                {"app_identifier": hapi_ident(), "location_code": loc, "output_format": "json", "limit": 10000, "offset": off}))
            rows = p.get("data", [])
            for m, v in parse_hapi_events(rows, types):
                tot[m] = tot.get(m, 0.0) + v
            if len(rows) < 10000:
                break
            off += 10000
    return sorted(tot.items())


# ---- FAA NOTAM Management Service (NMS-API, OAuth2 client credentials) ----
NMS_RESTRICT = re.compile(
    r"PROHIBIT|RESTRICTED AREA|DANGER AREA|AIRSPACE (?:CLOSED|CLSD|SAFETY|SECURITY|WARNING)|NOT TO ENTER|DO NOT ENTER"
    r"|MISSILE|ROCKET|LIVE FIRING|MILITARY|GNSS|GPS|JAMM|SPOOF|UAV|DRONE|CLSD|CLOSED|WARNING|CAUTION", re.I)


def parse_nms(items, today, days=30):
    """NOTAMs issued in the last `days` that restrict or warn about airspace (Q-code R/W areas, or warning words in the text)."""
    cut = str(today - dt.timedelta(days=days))
    seen = set()
    n = 0
    for f in items:
        try:
            nt = f["properties"]["coreNOTAMData"]["notam"]
        except (KeyError, TypeError):
            continue
        nid = nt.get("id")
        if nid in seen or nt.get("type") == "C" or str(nt.get("issued", ""))[:10] < cut:
            continue
        seen.add(nid)
        code = str(nt.get("selectionCode", ""))
        if code[:2] in ("QR", "QW") or NMS_RESTRICT.search(str(nt.get("text", ""))):
            n += 1
    return float(n)


NMS_HOSTS = ("https://api-nms.aim.faa.gov", "https://api-staging.cgifederal-aim.com")   # production first, test environment as fallback


def nms_token(client_id, client_secret):
    """(host, bearer token) from the first environment that accepts the keys."""
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    err = None
    for host in ([os.environ["NMS_HOST"]] if os.environ.get("NMS_HOST") else NMS_HOSTS):
        req = urllib.request.Request(host + "/v1/auth/token", data=b"grant_type=client_credentials", headers={
            "Content-Type": "application/x-www-form-urlencoded", "Authorization": "Basic " + auth})
        try:
            return host, json.loads(urllib.request.urlopen(req, timeout=40).read())["access_token"]
        except (urllib.error.URLError, ValueError, KeyError) as e:
            err = e
    raise RuntimeError(f"NMS sign-in refused: {err}")


def nms_bulk(host, token, classification="INTERNATIONAL"):
    """The full active load for one classification: one call a day is within the FAA's usage rule."""
    req = urllib.request.Request(host + "/nmsapi/v1/notams?" + urllib.parse.urlencode({"classification": classification}),
                                 headers={"Authorization": "Bearer " + token, "nmsResponseFormat": "GEOJSON"})
    raw = urllib.request.urlopen(req, timeout=300).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def nms_select(items, firs, prefix=None):
    """Notices for a theatre: filed under one of its flight information regions, or (prefix) at an airport or airspace with that
    ICAO prefix. Ukraine's closed airspace is filed under the placeholder region UKXX, so the region alone misses it."""
    out, seen = [], set()
    for f in items:
        try:
            nt = f["properties"]["coreNOTAMData"]["notam"]
        except (KeyError, TypeError):
            continue
        loc = str(nt.get("location") or "")
        if nt.get("affectedFir") in firs or (prefix and len(loc) == 4 and loc.startswith(prefix)):
            if nt.get("id") not in seen:
                seen.add(nt.get("id"))
                out.append(f)
    return out


def nms_update(firs, store, today=None, cid=None, secret=None):
    """Once a day: pull the international load, count each theatre's fresh restriction NOTAMs by flight information region."""
    cid = cid or os.environ.get("FAA_CLIENT_ID", "")
    secret = secret or os.environ.get("FAA_CLIENT_SECRET", "")
    today = today or dt.date.today()
    if not (cid and secret) or all(str(today) in dict(store.cache_load(f"notam_{th}")) for th in firs):
        return
    host, tok = nms_token(cid, secret)
    items = nms_bulk(host, tok)
    if isinstance(items, dict):
        items = items.get("data", {}).get("geojson", []) if isinstance(items.get("data"), dict) else items.get("features", [])
    for th, locs in firs.items():
        mine = nms_select(items, locs, C.NOTAM_PREFIX.get(th))
        if not mine:
            continue
        have = dict(store.cache_load(f"notam_{th}"))
        have[str(today)] = parse_nms(mine, today)
        store.cache_save(f"notam_{th}", sorted(have.items()))


# ---- UCDP Georeferenced Event Dataset (Uppsala), token in the x-ucdp-access-token header; 5,000 requests a day ----
UCDP_API = "https://ucdpapi.pcr.uu.se/api/gedevents/"
UCDP_YEARLY = "26.1"   # annual release; runs to the end of 2025. Monthly "candidate" releases (26.0.N) carry the months since.


def _ucdp_pages(version, token, start):
    out, page = [], 0
    while page < 200:
        p = get(f"{UCDP_API}{version}?pagesize=1000&page={page}&StartDate={start}", headers={"x-ucdp-access-token": token}, timeout=90)
        out += p.get("Result") or []
        if not p.get("NextPageUrl"):
            break
        page += 1
    return out


def parse_ucdp(events, box):
    """GED events -> [(YYYY-MM, best-estimate deaths)] for events inside box = (lat_min, lat_max, lon_min, lon_max)."""
    la0, la1, lo0, lo1 = box
    by = {}
    for e in events:
        try:
            lat, lon = float(e["latitude"]), float(e["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            m = str(e["date_start"])[:7]
            by[m] = by.get(m, 0.0) + float(e.get("best") or 0)
    return sorted(by.items())


def ucdp_events(token, start="2018-01-01"):
    """Annual release plus every monthly candidate release for the months after it ends."""
    ev = _ucdp_pages(UCDP_YEARLY, token, start)
    last = max((str(e["date_start"])[:10] for e in ev), default=start)
    seen = {e.get("id") for e in ev}
    for n in range(1, 15):   # each candidate release (26.0.1, 26.0.2, ...) carries its own slice of months, not a running total
        try:
            more = _ucdp_pages(f"26.0.{n}", token, last)
        except Exception:
            continue
        for e in more:
            if str(e["date_start"])[:10] > last and e.get("id") not in seen:
                seen.add(e.get("id"))
                ev.append(e)
    return ev


_UCDP = {}


def ucdp_months(events, box):
    """Every month the global dataset covers, 0 where the box had no deaths: GED codes the whole world,
    so a month without events in the box is a real zero, not a gap (Taiwan and Korea are all zeros)."""
    months = sorted({str(e.get("date_start"))[:7] for e in events if e.get("date_start")})
    if not months:
        return []
    have = dict(parse_ucdp(events, box))
    y, m = int(months[0][:4]), int(months[0][5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= months[-1]:
        k = f"{y:04d}-{m:02d}"
        out.append((k, have.get(k, 0.0)))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def fetch_ucdp(box, token):
    if not token:
        raise RuntimeError("UCDP_TOKEN not set")
    if "ev" not in _UCDP:
        _UCDP["ev"] = ucdp_events(token)
    return ucdp_months(_UCDP["ev"], box)
