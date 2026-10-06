"""Free public-data fetchers. Parsers are pure and pinned by tests; response
shapes were verified from a GitHub runner on 2026-10-06 except where a
function's docstring says UNVERIFIED (needs a key nobody has supplied yet).
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import config as C

TIMEOUT = 60
PW = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"


def get(url, data=None, retries=3, raw=False, wait=6):
    hdr = {"User-Agent": C.USER_AGENT}
    if data is not None:
        data = json.dumps(data).encode()
        hdr["Content-Type"] = "application/json"
    err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdr), timeout=TIMEOUT) as r:
                body = r.read().decode("utf-8")
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


def fetch_usaspending(psc=None, naics=None, years=6):
    end = dt.date.today()
    f = {"time_period": [{"start_date": f"{end.year - years}-01-01", "end_date": end.isoformat()}],
         "award_type_codes": ["A", "B", "C", "D"]}
    if psc:
        f["psc_codes"] = psc
    if naics:
        f["naics_codes"] = naics
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
    """UNVERIFIED live. -> {month: count} from opportunitiesData postedDate."""
    by = {}
    for o in p.get("opportunitiesData", []) or []:
        d = (o.get("postedDate") or "")[:7]
        if len(d) == 7:
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
    return sorted((m, float(n)) for m, n in by.items())


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


def state_levels(items, iso_list):
    """Sum of US advisory levels for the countries (Title 'X - Level 3: ...')."""
    tot = 0
    for it in items:
        if set(it.get("Category", [])) & set(iso_list):
            try:
                tot += int(it["Title"].split("Level ")[1][0])
            except (IndexError, ValueError):
                pass
    return float(tot)


def fetch_state():
    return get("https://cadataapi.state.gov/api/TravelAdvisories")


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


# ---- FRED (needs FRED_API_KEY) -------------------------------------------------
def parse_fred(p):
    out = []
    for o in p.get("observations", []):
        try:
            out.append((o["date"], float(o["value"])))
        except ValueError:    # FRED uses "." for missing
            pass
    return out


def fetch_fred(series, key):
    start = (dt.date.today() - dt.timedelta(days=900)).isoformat()
    q = urllib.parse.urlencode({"series_id": series, "api_key": key, "file_type": "json", "observation_start": start})
    return parse_fred(get("https://api.stlouisfed.org/fred/series/observations?" + q))
