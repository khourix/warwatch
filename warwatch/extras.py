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
    """Military aircraft with a position -> osint.aircraft() records (owner, type, altitude, squawk, theatre)."""
    import osint
    return [osint.aircraft(a) for a in payload.get("ac", []) if a.get("lat") is not None and a.get("lon") is not None]


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


def czib_recent(days=30, today=None, box=None):
    """Active zones (inside `box`, if given) whose bulletin was revised in the last `days`: airlines are being told something changed."""
    if "czib" not in _CACHE:
        _CACHE["czib"] = fetch_czib()
    cut = str((today or dt.date.today()) - dt.timedelta(days=days))
    return float(sum(1 for z in _CACHE["czib"] if z["updated"] >= cut and (box is None or in_box(z["lat"], z["lon"], box))))


# ---- Prediction markets (display only, never scored) and the Pentagon pizza index -----------
KEYS = {   # theatre -> words that tie a market to it
    "ukraine": r"Ukrain|Russia|Putin|Zelensk|Crimea|Donbas",
    "europe_east": r"NATO|Baltic|Poland|Lithuania|Latvia|Estonia|Kaliningrad|Finland|Suwalki",
    "iran": r"\bIran|Hormuz|Tehran|Khamenei",
    "yemen": r"Houthi|Yemen|Red Sea|Bab el|Sanaa",
    "israel": r"Israel|Hezbollah|Lebanon|Gaza|Netanyahu|Hamas",
}


def theatre_of_text(text):
    for t, pat in KEYS.items():
        if re.search(pat, text or "", re.I):
            return t
    return ""


WAR = re.compile(r"\bwar\b|military|strike|invade|invasion|attack|missile|nuclear|ceasefire|cease-fire|troops|nato|bomb|conflict|houthi|hezbollah|hamas|"
                 r"drone|airstrike|blockade|hormuz|regime|offensive|escalat|annex|capture|peace deal|peace agreement|sanction|iran|russia|ukrain|taiwan|gaza|israel|"
                 r"article 5|martial law|draft|mobiliz|coup|assassinat|kharg|invade|enter .* city|control of", re.I)
EXCLUDE = re.compile(r"\b(nba|nfl|nhl|mlb|ufc|fifa|world cup|super bowl|oscar|grammy|bitcoin|ethereum|\bbtc\b|album|movie|box office|tweet|elon|temperature|weather|mvp|ballon|"
                     r"stanley cup|premier league|champions league|f1|formula 1)\b", re.I)


def is_war(q):
    return bool(WAR.search(q or "")) and not EXCLUDE.search(q or "")


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
            q = m.get("question") or e.get("title", "")
            if not is_war(q + " " + e.get("title", "")):
                continue
            out.append({"q": q, "p": p, "vol": vol, "end": (m.get("endDate") or e.get("endDate") or "")[:10],
                        "src": "Polymarket", "theatre": theatre_of_text(q),
                        "url": "https://polymarket.com/event/" + (e.get("slug") or "")})
    return out


def fetch_poly(queries=("Iran war", "Iran strike", "Hormuz", "Ukraine ceasefire", "Russia NATO", "Israel Hezbollah", "Houthi", "Taiwan invasion", "nuclear", "military action")):
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
    return out


def parse_kalshi(payload, min_volume=5000):
    out = []
    for e in payload.get("events", []):
        title = e.get("title", "")
        th = theatre_of_text(title)
        if not th or not is_war(title):
            continue
        best = None
        for m in e.get("markets", []):
            try:
                p = float(m.get("last_price_dollars") or 0)
                vol = float(m.get("volume_fp") or 0)
            except (TypeError, ValueError):
                continue
            if vol >= min_volume and 0.005 < p < 0.995 and (best is None or vol > best[1]):
                best = (m, vol, p)
        if best:
            m, vol, p = best
            sub = m.get("yes_sub_title") or ""
            out.append({"q": title + (f": {sub}" if sub and sub.lower() not in title.lower() else ""), "p": p, "vol": vol,
                        "end": (m.get("close_time") or "")[:10], "src": "Kalshi", "theatre": th,
                        "url": "https://kalshi.com/markets/" + (e.get("event_ticker") or "").lower()})
    return out


def fetch_kalshi(pages=4):
    out, cursor = [], ""
    for _ in range(pages):
        q = {"limit": 200, "status": "open", "with_nested_markets": "true"}
        if cursor:
            q["cursor"] = cursor
        try:
            p = S.get("https://api.elections.kalshi.com/trade-api/v2/events?" + urllib.parse.urlencode(q), retries=2, wait=3)
        except Exception:
            break
        out.extend(parse_kalshi(p))
        cursor = p.get("cursor") or ""
        if not cursor:
            break
    return out


def fetch_markets():
    return sorted(fetch_poly() + fetch_kalshi(), key=lambda m: -m["vol"])[:40]


def parse_pizza(payload):
    """PizzINT (a third-party scrape of Google 'popular times' for pizza places near the Pentagon).
    -> (index 0-100, active spikes, places with a reading now)."""
    spikes = payload.get("active_spikes")
    idx = payload.get("overall_index")
    live = sum(1 for d in payload.get("data", []) if d.get("current_popularity") is not None)
    return (float(idx) if idx is not None else None, int(spikes or 0), live)


def fetch_pizza():
    return parse_pizza(S.get("https://www.pizzint.watch/api/dashboard-data", retries=2, wait=3))


def pizza_now():
    if "pizza" not in _CACHE:
        _CACHE["pizza"] = fetch_pizza()
    return _CACHE["pizza"]


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
    import os
    import osint
    ex = {"mil": [], "sqk": [], "ships": [], "inc": [], "fires": [], "nga": [], "markets": [], "levels": {}, "czib": [], "pizza": None, "errors": []}
    def nga():
        if "nga" not in _CACHE:
            _CACHE["nga"] = fetch_nga()
        return _CACHE["nga"]
    def czib():
        if "czib" not in _CACHE:
            _CACHE["czib"] = fetch_czib()
        return _CACHE["czib"]
    def ships():
        out = []
        try:
            out.extend(osint.fetch_usni())
        except Exception as e:
            ex["errors"].append(f"usni: {str(e)[:80]}")
        try:
            out.extend(osint.fetch_digitraffic()[0])
        except Exception as e:
            ex["errors"].append(f"digitraffic: {str(e)[:80]}")
        key = os.environ.get("AISSTREAM_API_KEY")
        if key:
            try:
                boxes = [C.BOXES[t] for t in ("iran", "yemen", "israel", "ukraine")]
                for m in osint.fetch_aisstream(key, boxes).values():
                    if m["lat"] is None or int(m["type"] or 0) not in (35, 55):
                        continue
                    out.append({"n": m["n"] or m["mmsi"], "k": "navy", "loc": f'{m["lat"]:.2f}, {m["lon"]:.2f}', "g": "Military ship (AIS)", "lat": m["lat"], "lon": m["lon"],
                                "flag": osint.MID.get(m["mmsi"][:3], ""), "dest": m["dest"], "spd": m["spd"], "d": "live", "th": osint.theatre_at(m["lat"], m["lon"]),
                                "note": "AIS position from aisstream.io."})
            except Exception as e:
                ex["errors"].append(f"aisstream: {str(e)[:80]}")
        return out
    def fires():
        key = os.environ.get("FIRMS_MAP_KEY")
        if not key:
            return []
        return osint.fetch_fires(key, {t: C.BOXES[t] for t in ("ukraine", "europe_east", "iran", "yemen", "israel")})
    for key, fn in (("mil", lambda: mil_positions(S.fetch_adsb())),
                    ("sqk", osint.fetch_squawks),
                    ("ships", ships),
                    ("inc", osint.fetch_incidents),
                    ("fires", fires),
                    ("nga", nga),
                    ("czib", czib),
                    ("markets", fetch_markets),
                    ("pizza", pizza_now),
                    ("levels", lambda: country_levels(S.fetch_state()))):
        try:
            ex[key] = fn()
        except Exception as e:
            ex["errors"].append(f"{key}: {str(e)[:80]}")
    # squawks seen anywhere: also surface any military aircraft in the main list that squawk an emergency
    seen = {m["hex"] for m in ex["sqk"]}
    for m in ex["mil"]:
        if m.get("sq") in osint.SQUAWK and m["hex"] not in seen:
            mean, why = osint.SQUAWK[m["sq"]]
            ex["sqk"].append(dict(m, mean=mean, why=why))
    return ex
