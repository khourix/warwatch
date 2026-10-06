"""Map and panel data that is not a scored series: live aircraft positions,
active naval/air hazard warnings with coordinates, prediction-market odds and
US advisory levels by country. Every fetcher fails soft: a missing source
leaves its layer empty and the dashboard says so.
"""
import datetime as dt
import json
import re
import time
import urllib.parse

import config as C
import sources as S

# Navigational-warning text that signals military activity or interference.
HAZARD = re.compile(r"MISSILE|ROCKET|LIVE FIR|FIRING|GUNNERY|NAVAL EXERCISE|MILITARY EXERCISE|EXERCISES?|"
                    r"GPS|GNSS|INTERFERENCE|JAMMING|MINES?\b|MINEFIELD|DRONE|UNMANNED|MILITARY|NAVAL OPERATION",
                    re.I)
COORD = re.compile(r"(\d{1,2})-(\d{2}(?:\.\d+)?)([NS])\s+(\d{1,3})-(\d{2}(?:\.\d+)?)([EW])")


def parse_coords(text):
    """All 'DD-MM.mN DDD-MM.mE' pairs in a warning text -> [(lat, lon)]."""
    out = []
    for la, lam, ns, lo, lom, ew in COORD.findall(text or ""):
        lat = int(la) + float(lam) / 60
        lon = int(lo) + float(lom) / 60
        out.append((-lat if ns == "S" else lat, -lon if ew == "W" else lon))
    return out


MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def parse_issue(text):
    """NGA 'issueDate' such as '071541Z SEP 2023' -> date, or None."""
    m = re.match(r"\s*(\d{2})\d{4}Z\s+([A-Z]{3})\s+(\d{4})", text or "")
    try:
        return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    except (AttributeError, KeyError, ValueError):
        return None


def parse_nga(warnings):
    """Active broadcast warnings -> hazard markers [{id, lat, lon, text}], one per warning (first position)."""
    out = []
    for w in warnings:
        text = w.get("text", "")
        if not HAZARD.search(text):
            continue
        pos = parse_coords(text)
        if not pos:
            continue
        out.append({"id": f"{w.get('navArea', '')}-{w.get('msgNumber', '')}/{w.get('msgYear', '')}",
                    "lat": round(pos[0][0], 2), "lon": round(pos[0][1], 2),
                    "text": " ".join(text.split())[:160], "issued": str(parse_issue(w.get("issueDate")) or "")})
    return out


_CACHE = {}


def nga_recent(theatre, days=30, today=None):
    """Hazard warnings issued in the last `days` whose position falls in the theatre box."""
    if "nga" not in _CACHE:
        _CACHE["nga"] = fetch_nga()
    cut = str((today or dt.date.today()) - dt.timedelta(days=days))
    box = C.THEATRE_BOX[theatre]
    return float(sum(1 for m in _CACHE["nga"] if m["issued"] >= cut and in_box(m["lat"], m["lon"], box)))


def hub_stats(theatre):
    """(aircraft with a position, aircraft with degraded navigation accuracy) over the theatre's hubs."""
    n = bad = 0
    for lat, lon, r in C.HUBS[theatre]:
        key = ("hub", lat, lon)
        if key not in _CACHE:
            _CACHE[key] = fetch_hub(lat, lon, r)
        a, b = parse_nav(_CACHE[key])
        n += a
        bad += b
    return n, bad


def fetch_nga(areas=("A", "P", "12", "4")):
    out = []
    for a in areas:
        q = urllib.parse.urlencode({"output": "json", "status": "active", "navArea": a})
        try:
            p = S.get("https://msi.nga.mil/api/publications/broadcast-warn?" + q)
        except Exception:
            continue
        out.extend(parse_nga(p.get("broadcast-warn", [])))
    return out


def in_box(lat, lon, box):
    la0, la1, lo0, lo1 = box
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


# ---- ADS-B: military and airlift positions for the map ----------------------------
def mil_positions(payload):
    out = []
    for a in payload.get("ac", []):
        la, lo = a.get("lat"), a.get("lon")
        if la is None or lo is None:
            continue
        out.append({"lat": round(la, 2), "lon": round(lo, 2), "t": a.get("t", ""),
                    "lift": a.get("t") in S.AIRLIFT, "hex": a.get("hex", "")})
    return out


# ---- ADS-B: civil traffic and navigation degradation near a hub -------------------
def parse_nav(payload):
    """-> (aircraft with a position, aircraft reporting degraded navigation accuracy).
    NACp below 8 means position error above ~93 m: the signature of GNSS interference."""
    n = bad = 0
    for a in payload.get("ac", []):
        if a.get("lat") is None or a.get("lon") is None:
            continue
        n += 1
        nac = a.get("nac_p")
        if isinstance(nac, int) and nac < 8:
            bad += 1
    return n, bad


def fetch_hub(lat, lon, radius=250):
    return S.get(f"https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}", retries=2, wait=5)


# ---- EASA conflict-zone information bulletins (airline airspace risk notices) -------------
def parse_czib(payload):
    """EASA CZIB export -> [{name, lat, lon, updated}] for active zones with a position."""
    rows = payload if isinstance(payload, list) else next(iter(payload.values()), [])
    out = []
    for r in rows:
        if str(r.get("status", "")).lower() != "active":
            continue
        try:
            lat, lon = (float(x) for x in str(r.get("coordinates", "")).split(","))
        except ValueError:
            continue
        m = re.search(r"\d{4}-\d{2}-\d{2}", str(r.get("updated", "")))
        out.append({"name": r.get("name", ""), "lat": round(lat, 2), "lon": round(lon, 2), "updated": m.group(0) if m else ""})
    return out


def fetch_czib():
    return parse_czib(S.get("https://www.easa.europa.eu/en/domains/air-operations/czibs/export-json?page&_format=json"))


def czib_recent(days=30, today=None):
    """Active zones whose bulletin was revised in the last `days`: airlines are being told something changed."""
    if "czib" not in _CACHE:
        _CACHE["czib"] = fetch_czib()
    cut = str((today or dt.date.today()) - dt.timedelta(days=days))
    return float(sum(1 for z in _CACHE["czib"] if z["updated"] >= cut))


# ---- Polymarket: what traders price (display only, never scored) ---------------------
def parse_poly(payload, min_volume=50000):
    out = []
    for e in payload.get("events", []):
        for m in e.get("markets", []):
            if m.get("closed") or not m.get("active", True):
                continue
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
                p = float(prices[0])
                vol = float(m.get("volume") or 0)
            except (ValueError, IndexError, TypeError):
                continue
            if vol < min_volume or not (0.005 < p < 0.995):
                continue
            out.append({"q": m.get("question") or e.get("title", ""), "p": p, "vol": vol,
                        "end": (m.get("endDate") or e.get("endDate") or "")[:10]})
    return out


def fetch_poly(queries=("Iran", "Ukraine", "Russia NATO", "Israel", "Hezbollah", "Houthi")):
    seen, out = set(), []
    for q in queries:
        try:
            p = S.get("https://gamma-api.polymarket.com/public-search?"
                      + urllib.parse.urlencode({"q": q, "limit_per_type": 6}), retries=2, wait=3)
        except Exception:
            continue
        for m in parse_poly(p):
            if m["q"] not in seen:
                seen.add(m["q"])
                out.append(m)
        time.sleep(0.5)
    return sorted(out, key=lambda m: -m["vol"])[:10]


# ---- US advisory level by country (map shading) --------------------------------------
ALIAS = {"Türkiye": "Turkey", "Burma (Myanmar)": "Myanmar", "Congo, Democratic Republic of the": "Dem. Rep. Congo",
         "Israel, The West Bank and Gaza": "Israel", "South Sudan": "S. Sudan", "Bosnia and Herzegovina": "Bosnia and Herz."}


def country_levels(items):
    out = {}
    for it in items:
        t = it.get("Title", "")
        if " - Level " not in t:
            continue
        name, rest = t.split(" - Level ", 1)
        try:
            out[ALIAS.get(name.strip(), name.strip())] = int(rest[0])
        except ValueError:
            pass
    return out


def collect():
    """All map and panel layers; any failure leaves that layer empty."""
    ex = {"mil": [], "nga": [], "poly": [], "levels": {}, "czib": [], "errors": []}
    def nga():
        if "nga" not in _CACHE:
            _CACHE["nga"] = fetch_nga()
        return _CACHE["nga"]
    def czib():
        if "czib" not in _CACHE:
            _CACHE["czib"] = fetch_czib()
        return _CACHE["czib"]
    for key, fn in (("mil", lambda: mil_positions(S.fetch_adsb())),
                    ("nga", nga),
                    ("czib", czib),
                    ("poly", fetch_poly),
                    ("levels", lambda: country_levels(S.fetch_state()))):
        try:
            ex[key] = fn()
        except Exception as e:
            ex["errors"].append(f"{key}: {str(e)[:80]}")
    return ex
