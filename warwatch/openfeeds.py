"""Open sources found through the Argos Atlas review (November 2026): the Strait of Hormuz from hormuz.now, verified events from
GeoConfirmed, the Ukraine front from DeepStateMap, Canada's and Australia's travel advice, and natural-hazard lists (GDACS,
NASA EONET) for the fire classifier. Every fetcher raises when its source fails, so a gap is never read as "nothing happened".

All series built here are new and untested (catalog.NOT_TESTED): on the page and the forward record, outside the score.
"""
import datetime as dt
import html
import json
import math
import os
import re
import sys

import config as C
import sources as S

_CACHE = {}


def _once(key, fn):
    """Fetch once per run; a failure is kept too, so every series of a source reports the same error without refetching."""
    if key not in _CACHE:
        try:
            _CACHE[key] = fn()
        except Exception as e:
            _CACHE[key] = e
    if isinstance(_CACHE[key], Exception):
        raise RuntimeError(f"{key} failed earlier this run: {str(_CACHE[key])[:150]}")
    return _CACHE[key]


def in_box(lat, lon, box):
    la0, la1, lo0, lo1 = box
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


def rolling(dates, first, today, days=30):
    """Count of dates in the `days` days up to each day from first to today -> [(date, count)]."""
    per = {}
    for d in dates:
        per[d] = per.get(d, 0) + 1
    out, d, win = [], first, 0
    for k, v in per.items():
        if first - dt.timedelta(days=days - 1) <= k < first:
            win += v
    while d <= today:
        win += per.get(d, 0)
        out.append((d.isoformat(), float(win)))
        win -= per.get(d - dt.timedelta(days=days - 1), 0)
        d += dt.timedelta(days=1)
    return out


# ---- hormuz.now: crossings, ships waiting and AIS-silent ships at the Strait of Hormuz (CC BY 4.0, no key) ----
# Free AIS hears about one ship in the Gulf (docs/SHIPS.md); hormuz.now merges several AIS feeds for the strait and publishes
# its counts openly. Its history starts on 19 October 2026, so the series are a forward record, not a backtest.
HORMUZ = "https://hormuz.now"
HORMUZ_CREDIT = "Data: hormuz.now, CC BY 4.0"


def parse_hormuz_daily(payload):
    """/api/daily.json -> [(date, crossings)] for complete days. The newest day is flagged partial while it is still counting."""
    out = []
    for r in payload.get("days") or []:
        d, v = str(r.get("date") or "")[:10], r.get("total")
        if r.get("partial") or not re.match(r"\d{4}-\d{2}-\d{2}$", d) or not isinstance(v, (int, float)):
            continue
        out.append((d, float(v)))
    return sorted(out)


def hormuz_crossings():
    """Ships crossing the strait per day (both ways). Kept in history/cache so the record outlives the source's own window."""
    import store
    got = dict(store.cache_load("hormuz_cross_days"))
    got.update(parse_hormuz_daily(S.get(f"{HORMUZ}/api/daily.json", retries=2)))
    pts = sorted(got.items())
    if not pts:
        raise RuntimeError("hormuz.now daily.json listed no complete day")
    store.cache_save("hormuz_cross_days", pts, stamp=False)
    return pts


def parse_hormuz_areas(payload):
    """/api/areas -> {"silent": ships near the strait whose AIS went quiet, "waiting": ships waiting to cross}."""
    silent = payload.get("aisSilent")
    waiting = (payload.get("waiting") or {}).get("total")
    if not isinstance(silent, list) or not isinstance(waiting, (int, float)):
        raise RuntimeError("hormuz.now areas: aisSilent or waiting.total missing")
    return {"silent": float(len(silent)), "waiting": float(waiting)}


def hormuz_now(key):
    return _once("hormuz_areas", lambda: parse_hormuz_areas(S.get(f"{HORMUZ}/api/areas", retries=2)))[key]


# ---- GeoConfirmed: events geolocated from photo or video by volunteers (public read API, no key) ----
# One file per conflict; an event carries an id, a date (day only), a position and a short description. Volunteers
# geolocate days or weeks after the event, so the newest days are low until they catch up (catalog drop).
GEOCONF = "https://geoconfirmed.org/api/Placemark/{}"
GEOCONF_CONFLICTS = ("ukraine", "israel", "iran", "yemen", "syria", "africa", "drc", "indpak", "ven", "pac", "world")
GEOCONF_FROM = dt.date(2023, 1, 1)     # Ukraine runs from 2013, most other conflicts from 2023


def parse_geoconf(payload):
    """/api/Placemark/<conflict> -> [(id, date, lat, lon)]. Events with no date are skipped."""
    out = []
    for fac in payload or []:
        for ic in fac.get("icons") or []:
            for p in ic.get("placemarks") or []:
                try:
                    d = dt.date.fromisoformat(str(p.get("date") or "")[:10])
                    la, lo = float(p["la"]), float(p["lo"])
                except (KeyError, TypeError, ValueError):
                    continue
                out.append((str(p.get("id") or f"{d}:{la:.4f}:{lo:.4f}"), d, la, lo))
    return out


def fetch_geoconf():
    """Every conflict file, merged by event id (an event can sit in a theatre file and the world file)."""
    ev = {}
    for c in GEOCONF_CONFLICTS:
        for e in parse_geoconf(S.get(GEOCONF.format(c), retries=2, timeout=180)):
            ev[e[0]] = e
    if not ev:
        raise RuntimeError("GeoConfirmed returned no events")
    return list(ev.values())


def geoconf_events():
    return _once("geoconf", fetch_geoconf)


GEOCONF_NOT = {"europe_east": ("ukraine",)}   # the eastern-flank box takes in western Ukraine: those events are Ukraine's


def geoconf_series(theatre, today=None, events=None):
    """Verified (geolocated) events in the last 30 days inside the theatre box -> [(date, count)] from GEOCONF_FROM."""
    box = C.THEATRE_BOX[theatre]
    nots = [C.THEATRE_BOX[t] for t in GEOCONF_NOT.get(theatre, ())]
    ev = events if events is not None else geoconf_events()
    today = today or dt.date.today()
    mine = [d for _, d, la, lo in ev if in_box(la, lo, box) and not any(in_box(la, lo, b) for b in nots) and d <= today]
    return rolling(mine, GEOCONF_FROM, today)


def geoconf_near(lat, lon, day, km=25.0, days=1, events=None):
    """GeoConfirmed events within km and days of a place and day (for the event desk's evidence grade)."""
    ev = events if events is not None else geoconf_events()
    out = []
    for i, d, la, lo in ev:
        if abs((d - day).days) <= days and _km(lat, lon, la, lo) <= km:
            out.append(i)
    return out


def _km(la1, lo1, la2, lo2):
    dy = (la1 - la2) * 111.0
    dx = (lo1 - lo2) * 111.0 * math.cos(math.radians((la1 + la2) / 2))
    return math.hypot(dx, dy)


# ---- DeepStateMap: the Ukraine front, one map version per update (public API) ----
# /api/history/public lists every version (id = its unix time); /api/history/<id>/areas gives the km² of each kind of area.
# Reuse confirmed with the project by Anthony on 26 November 2026.
DEEPSTATE = "https://deepstatemap.live/api/history"
OCCUPIED = ("occupied_after_24_02_2022", "occupied_to_24_02_2022")


def parse_deepstate_list(payload):
    """/api/history/public -> [(id, date)], one per version, oldest first."""
    out = []
    for r in payload or []:
        try:
            i = int(r["id"])
            d = (str(r.get("createdAt") or "")[:10]) or dt.datetime.fromtimestamp(i, dt.timezone.utc).date().isoformat()
            dt.date.fromisoformat(d)
        except (KeyError, TypeError, ValueError):
            continue
        out.append((i, d))
    return sorted(out)


def parse_deepstate_areas(payload):
    """/api/history/<id>/areas -> km² held by Russia (occupied since and before 24 February 2022)."""
    got = [float(a.get("area") or 0) for a in payload or [] if a.get("type") in OCCUPIED]
    if not got:
        raise RuntimeError("DeepStateMap areas: no occupied area listed")
    return sum(got)


def deepstate_update(max_new=150, get=None, sleep=None):
    """Reads the areas of versions not yet kept (at most max_new per run, so the first runs fill the history over a few days).
    Rows in history/cache/deepstate_areas.csv: id, date, occupied km². -> rows."""
    import store
    import time
    get = get or S.get
    sleep = time.sleep if sleep is None else sleep
    rows = {int(r[0]): r for r in store.cache_rows("deepstate_areas") if len(r) == 3}
    todo = [(i, d) for i, d in parse_deepstate_list(get(f"{DEEPSTATE}/public", retries=2)) if i not in rows]
    for i, d in todo[-max_new:]:          # newest first, so the live end is never behind
        rows[i] = [str(i), d, f"{parse_deepstate_areas(get(f'{DEEPSTATE}/{i}/areas', retries=2)):.1f}"]
        sleep(0.5)
    out = sorted(rows.values(), key=lambda r: int(r[0]))
    store.cache_rows_save("deepstate_areas", out)
    return out


def deepstate_series():
    """Km² Russia gained over 7 days (catalog deepstate_gain_ukraine), reading new map versions first."""
    return deepstate_gain(_once("deepstate", deepstate_update))


def deepstate_gain(rows, days=7):
    """Km² Russia gained (negative: lost) over the last `days` days, per day with a map version -> [(date, km²)]."""
    last = {}
    for _, d, v in sorted(rows, key=lambda r: int(r[0])):
        last[d] = float(v)                 # the day's last version
    days_ = sorted(last)
    out = []
    for d in days_:
        back = (dt.date.fromisoformat(d) - dt.timedelta(days=days)).isoformat()
        prior = [x for x in days_ if x <= back]
        if prior:
            out.append((d, round(last[d] - last[prior[-1]], 1)))
    return out


# ---- Canada and Australia travel advice (a third and fourth government beside the US and the UK) ----
# Canada's levels: 0 normal precautions, 1 high degree of caution, 2 avoid non-essential travel, 3 avoid all travel.
# Australia's (Smartraveller, CC BY 4.0): exercise normal safety precautions, high degree of caution, reconsider, do not travel.
CA_URL = "https://data.international.gc.ca/travel-voyage/index-alpha-eng.json"
AU_URL = "https://www.smartraveller.gov.au/destinations"
AU_EXPORT = "https://www.smartraveller.gov.au/destinations-export"   # Smartraveller's public JSON export, one row per destination
ISO2 = {"ukraine": ["UA", "BY", "MD"], "europe_east": ["PL", "LT", "LV", "EE", "FI"], "iran": ["IR", "IQ"], "iraq": ["IQ"],
        "gulf": ["SA", "AE", "QA", "BH", "KW", "OM"], "lebanon": ["LB"], "syria": ["SY"], "yemen": ["YE", "SA", "OM", "DJ"],
        "israel": ["IL", "LB", "JO", "EG"], "taiwan": ["TW"], "scs": ["PH", "VN"], "korea": ["KR", "KP"], "southasia": ["IN", "PK"],
        "libya": ["LY"], "sudan": ["SD", "SS"], "drc": ["CD"], "venezuela": ["VE", "CO", "CU"]}   # as C.STATE_ISO, in ISO codes
AU_SLUG = {"UA": "ukraine", "BY": "belarus", "MD": "moldova", "PL": "poland", "LT": "lithuania", "LV": "latvia", "EE": "estonia",
           "FI": "finland", "IR": "iran", "IQ": "iraq", "SA": "saudi-arabia", "AE": "united-arab-emirates", "QA": "qatar", "BH": "bahrain",
           "KW": "kuwait", "OM": "oman", "LB": "lebanon", "SY": "syria", "YE": "yemen", "DJ": "djibouti", "IL": "israel", "JO": "jordan",
           "EG": "egypt", "TW": "taiwan", "PH": "philippines", "VN": "vietnam", "KR": "south-korea-republic-korea", "KP": "north-korea-democratic-peoples-republic-korea", "IN": "india",
           "PK": "pakistan", "LY": "libya", "SD": "sudan", "SS": "south-sudan", "CD": "democratic-republic-congo", "VE": "venezuela",
           "CO": "colombia", "CU": "cuba"}
AU_LEVEL = (("do not travel", 4), ("reconsider your need to travel", 3), ("high degree of caution", 2), ("normal safety precautions", 1))


def parse_canada(payload):
    """index-alpha-eng.json -> {ISO2: level 1 to 4} (Canada's 0 to 3, plus 1, to read like the US scale)."""
    out = {}
    for code, r in ((payload or {}).get("data") or {}).items():
        v = r.get("advisory-state")
        if isinstance(v, int) and 0 <= v <= 3:
            out[code.upper()] = v + 1
    return out


def parse_smartraveller(page):
    """The destinations table -> {slug: level 1 to 4}. Each row links /destinations/<region>/<slug> and names the overall level."""
    out = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page or "", re.S | re.I):
        m = re.search(r'href="/destinations/[^"/]+/([^"/?#]+)"', row)
        lv = re.search(r'views-field-field-overall-advice-level[^>]*>(.*?)</td>', row, re.S | re.I)
        if not (m and lv):
            continue
        text = html.unescape(re.sub(r"<[^>]+>", " ", lv.group(1))).lower()
        for words, n in AU_LEVEL:
            if words in text:
                out[m.group(1).lower()] = n
                break
    return out


def parse_smartraveller_export(rows):
    """destinations-export JSON -> {slug: level 1 to 4}. The slug is the last part of field_url, as on the destinations page."""
    out = {}
    for r in rows or []:
        slug = str(r.get("field_url") or "").rstrip("/").rsplit("/", 1)[-1].lower()
        text = html.unescape(str(r.get("field_overall_advice_level") or "")).lower()
        for words, n in AU_LEVEL:
            if slug and words in text:
                out[slug] = n
                break
    return out


def level_sum(levels, codes, slug=None):
    """Sum of the levels of a theatre's countries. Raises when one is missing, so a renamed country never reads as a fall."""
    keys = [slug[c] for c in codes] if slug else codes
    missing = [k for k in keys if k not in levels]
    if missing:
        raise RuntimeError(f"no advisory level for {', '.join(missing)}")
    return float(sum(levels[k] for k in keys))


def canada_level(theatre):
    return level_sum(_once("canada", lambda: parse_canada(S.get(CA_URL, retries=2))), ISO2[theatre])


# Smartraveller does not answer GitHub's runners, so the home runner (khourix/warwatch-collect, workflow smartraveller.yml)
# reads it every 6 hours and pushes the levels here. The build reads that file while it is fresh and tries the site itself if not.
AU_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "smartraveller.json")
AU_FRESH_H = 36


def smartraveller_fetch():
    """Reads the JSON export (the destinations page if that fails) -> {slug: level}. Raises unless every country WarWatch
    uses has a level. The page timed out from GitHub and from the home runner on 27 Nov 2026; the export is a lighter 300 KB."""
    try:
        levels = parse_smartraveller_export(S.get(AU_EXPORT, retries=2, timeout=90))
    except Exception as e:
        try:
            levels = parse_smartraveller(S.get(AU_URL, retries=1, raw=True, timeout=60))
        except Exception as e2:
            raise RuntimeError(f"Smartraveller export: {str(e)[:120]}; page: {str(e2)[:120]}")
    missing = sorted(set(AU_SLUG.values()) - set(levels))
    if missing:
        raise RuntimeError(f"Smartraveller parsed {len(levels)} countries, missing {', '.join(missing)}")
    return levels


def smartraveller_save(path=AU_FILE, now=None, fetch=None):
    """Home runner: fetch and write {"fetched": UTC time, "levels": {slug: level}}. -> number of countries."""
    levels = (fetch or smartraveller_fetch)()
    now = now or dt.datetime.now(dt.timezone.utc)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"fetched": now.strftime("%Y-%m-%dT%H:%MZ"), "source": AU_URL, "licence": "CC BY 4.0",
                   "levels": dict(sorted(levels.items()))}, f, indent=0)
        f.write("\n")
    return len(levels)


def smartraveller_saved(path=AU_FILE, now=None):
    """The levels the home runner saved, or None when the file is missing or older than AU_FRESH_H hours."""
    try:
        with open(path) as f:
            got = json.load(f)
        when = dt.datetime.strptime(got["fetched"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc)
    except (OSError, ValueError, KeyError):
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    return got.get("levels") if now - when <= dt.timedelta(hours=AU_FRESH_H) else None


def australia_level(theatre):
    return level_sum(_once("smartraveller", lambda: smartraveller_saved() or smartraveller_fetch()), ISO2[theatre], AU_SLUG)


# ---- WarSpotting: Russian equipment losses documented with photo or video (public API, named User-Agent required) ----
# /api/losses/russia/<date>/<page> lists up to 100 losses lost on that day per page. Losses are documented days to weeks after
# they happen, so recent days are re-read on every update and the newest week is dropped from the score (catalog drop).
# The service asks for at most 10 requests per 10 seconds. Only Russian losses are counted.
WARSPOT = "https://ukr.warspotting.net/api/losses/russia/{}/{}"
WARSPOT_FROM = dt.date(2022, 2, 24)
WARSPOT_UA = {"User-Agent": C.USER_AGENT, "Accept": "application/json"}


def warspot_day(day, get, sleep):
    """Losses dated `day`, all pages."""
    n, page = 0, 1
    while True:
        got = (get(WARSPOT.format(day.isoformat(), page), retries=2, headers=WARSPOT_UA) or {}).get("losses")
        if not isinstance(got, list):
            raise RuntimeError("WarSpotting: no losses list in the answer")
        sleep(1.1)
        n += len(got)
        if len(got) < 100:
            return n
        page += 1


def warspot_update(today=None, recent=21, older=40, get=None, sleep=None):
    """Re-reads the last `recent` days and fills up to `older` days of history not yet kept (the history fills over a few weeks).
    Rows in history/cache/warspot_days.csv: date, losses. -> {date: losses}."""
    import store
    import time
    get = get or S.get
    sleep = time.sleep if sleep is None else sleep
    today = today or dt.datetime.now(dt.timezone.utc).date()
    have = {r[0]: float(r[1]) for r in store.cache_rows("warspot_days") if len(r) == 2}
    todo = [today - dt.timedelta(days=i) for i in range(recent)]
    d, gaps = today - dt.timedelta(days=recent), []
    while d >= WARSPOT_FROM and len(gaps) < older:
        if d.isoformat() not in have:
            gaps.append(d)
        d -= dt.timedelta(days=1)
    for day in todo + gaps:
        have[day.isoformat()] = float(warspot_day(day, get, sleep))
    store.cache_rows_save("warspot_days", [[k, f"{v:.0f}"] for k, v in sorted(have.items())])
    return have


def warspot_series(today=None, days=7, have=None):
    """Documented losses dated in the last 7 days -> [(date, count)], from the first day with the whole week kept."""
    have = have if have is not None else _once("warspot", warspot_update)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    out, d = [], WARSPOT_FROM + dt.timedelta(days=days - 1)
    while d <= today:
        week = [(d - dt.timedelta(days=i)).isoformat() for i in range(days)]
        if all(w in have for w in week):
            out.append((d.isoformat(), float(sum(have[w] for w in week))))
        d += dt.timedelta(days=1)
    if not out:
        raise C.Pending("archive building: no full week of losses kept yet")
    return out


# ---- Natural hazards for the fire classifier: GDACS (CC BY 4.0) and NASA EONET wildfires and volcanoes ----
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=WF;VO&fromDate={}&toDate={}"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=all&category=wildfires,volcanoes&days={}"


def _point(geom):
    """A GeoJSON point, or the mean of a polygon's first ring -> (lat, lon), or None."""
    try:
        t, c = geom.get("type"), geom.get("coordinates")
        if t == "Point":
            return float(c[1]), float(c[0])
        if t == "Polygon":
            ring = c[0]
            return sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def parse_gdacs(payload):
    """GDACS event list (GeoJSON) -> rows [from, to, lat, lon, kind, name, source] for wildfires (fire) and volcanoes (volc)."""
    out = []
    for f in (payload or {}).get("features") or []:
        p, pt = f.get("properties") or {}, _point(f.get("geometry") or {})
        kind = {"WF": "fire", "VO": "volc"}.get(p.get("eventtype"))
        a, b = str(p.get("fromdate") or "")[:10], str(p.get("todate") or p.get("fromdate") or "")[:10]
        if not (kind and pt and re.match(r"\d{4}-\d{2}-\d{2}$", a) and re.match(r"\d{4}-\d{2}-\d{2}$", b)):
            continue
        out.append([a, b, f"{pt[0]:.4f}", f"{pt[1]:.4f}", kind, (p.get("name") or p.get("eventname") or "")[:80], "GDACS"])
    return out


def parse_eonet(payload):
    """EONET v3 events -> rows like parse_gdacs's, one per event, spanning its first to last geometry date."""
    out = []
    for e in (payload or {}).get("events") or []:
        cats = {c.get("id") for c in e.get("categories") or []}
        kind = "volc" if "volcanoes" in cats else "fire" if "wildfires" in cats else None
        geo = [(str(g.get("date") or "")[:10], _point(g)) for g in e.get("geometry") or []]
        geo = [(d, p) for d, p in geo if p and re.match(r"\d{4}-\d{2}-\d{2}$", d)]
        if not (kind and geo):
            continue
        geo.sort()
        la = sum(p[0] for _, p in geo) / len(geo)
        lo = sum(p[1] for _, p in geo) / len(geo)
        out.append([geo[0][0], geo[-1][0], f"{la:.4f}", f"{lo:.4f}", kind, (e.get("title") or "")[:80], "NASA EONET"])
    return out


HAZARDS = "natural_hazards"   # history/cache rows: from, to, lat, lon, kind, name, source (last 30 days)


def hazards_refresh(today=None, days=30, get=None):
    """Fetches both lists and keeps the last `days` days in history/cache/natural_hazards.csv. Runs in imagery.yml. -> rows kept.
    One list failing keeps the other; both failing raises."""
    import store
    get = get or S.get
    today = today or dt.datetime.now(dt.timezone.utc).date()
    a = (today - dt.timedelta(days=days)).isoformat()
    rows, errs = [], []
    for name, url, parse in (("GDACS", GDACS_URL.format(a, today.isoformat()), parse_gdacs), ("EONET", EONET_URL.format(days), parse_eonet)):
        try:
            rows += parse(get(url, retries=2))
        except Exception as e:
            errs.append(f"{name}: {str(e)[:100]}")
    if len(errs) == 2:
        raise RuntimeError("; ".join(errs))
    rows = sorted(r for r in rows if r[1] >= a)
    store.cache_rows_save(HAZARDS, rows)
    return len(rows), errs


if __name__ == "__main__":
    if sys.argv[1:2] == ["smartraveller"]:
        print("smartraveller: countries saved", smartraveller_save(*sys.argv[2:3]))
    else:
        sys.exit("usage: python3 warwatch/openfeeds.py smartraveller [out.json]   # the home runner, every 6 hours")
