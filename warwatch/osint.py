"""Open-source enrichment: who owns an aircraft, where is the fleet, what happened at sea.

Pure parsers (testable offline) plus thin fetchers. Standard library only. Every fetcher
is called fail-soft by extras.collect(): a dead source leaves its map layer empty.
"""
import base64
import datetime as dt
import html
import json
import os
import re
import socket
import ssl
import struct
import time
import urllib.parse
import xml.etree.ElementTree as ET

import config as C
import sources as S

# ---------------------------------------------------------------- aircraft: owner, type, class
HEX_RANGES = [   # ICAO 24-bit address blocks by state (start, end, country)
    (0xA00000, 0xAFFFFF, "United States"), (0x140000, 0x15FFFF, "Russia"), (0x400000, 0x43FFFF, "United Kingdom"),
    (0x3C0000, 0x3FFFFF, "Germany"), (0x380000, 0x3BFFFF, "France"), (0x300000, 0x33FFFF, "Italy"), (0x340000, 0x37FFFF, "Spain"),
    (0x480000, 0x487FFF, "Netherlands"), (0x488000, 0x48FFFF, "Poland"), (0x448000, 0x44FFFF, "Belgium"), (0x478000, 0x47FFFF, "Norway"),
    (0x4A8000, 0x4AFFFF, "Sweden"), (0x458000, 0x45FFFF, "Denmark"), (0x460000, 0x467FFF, "Finland"), (0x4B8000, 0x4BFFFF, "Turkey"),
    (0x468000, 0x46FFFF, "Greece"), (0x4A0000, 0x4A7FFF, "Romania"), (0x4B0000, 0x4B7FFF, "Switzerland"), (0x508000, 0x50FFFF, "Ukraine"),
    (0x510000, 0x517FFF, "Belarus"), (0x738000, 0x73FFFF, "Israel"), (0x730000, 0x737FFF, "Iran"), (0x728000, 0x72FFFF, "Iraq"),
    (0x710000, 0x717FFF, "Saudi Arabia"), (0x740000, 0x747FFF, "Jordan"), (0x748000, 0x74FFFF, "Lebanon"), (0x778000, 0x77FFFF, "Syria"),
    (0x896000, 0x896FFF, "United Arab Emirates"), (0x06A000, 0x06AFFF, "Qatar"), (0x894000, 0x894FFF, "Bahrain"), (0x706000, 0x706FFF, "Kuwait"),
    (0x70C000, 0x70CFFF, "Oman"), (0x890000, 0x890FFF, "Yemen"), (0x010000, 0x017FFF, "Egypt"), (0x760000, 0x767FFF, "Pakistan"),
    (0x800000, 0x83FFFF, "India"), (0x780000, 0x7BFFFF, "China"), (0x840000, 0x87FFFF, "Japan"), (0xC00000, 0xC3FFFF, "Canada"),
    (0x7C0000, 0x7FFFFF, "Australia"), (0x502C00, 0x502FFF, "Latvia"), (0x503C00, 0x503FFF, "Lithuania"), (0x511000, 0x5113FF, "Estonia"),
    (0x4C8000, 0x4C83FF, "Cyprus"), (0x4D0000, 0x4D03FF, "Luxembourg"), (0x500000, 0x5003FF, "Croatia"), (0x501000, 0x5013FF, "Bosnia"),
    (0x506000, 0x506FFF, "Slovenia"), (0x504000, 0x5043FF, "Moldova"), (0x4C0000, 0x4C7FFF, "Serbia"), (0x440000, 0x447FFF, "Austria"),
    (0x498000, 0x49FFFF, "Czechia"), (0x4A8000, 0x4A8000, "Sweden"), (0x470000, 0x477FFF, "Hungary"), (0x484000, 0x484FFF, "Poland"),
]
CALL_OPS = [   # callsign prefix -> operator (military call signs are well known)
    ("REACH", "US Air Force, Air Mobility Command"), ("RCH", "US Air Force, Air Mobility Command"), ("CNV", "US Navy transport"),
    ("NAVY", "US Navy"), ("PAT", "US Army priority air transport"), ("SAM", "US Air Force special air mission (VIP)"), ("EXEC", "US government VIP"),
    ("RRR", "UK Royal Air Force"), ("ASCOT", "UK Royal Air Force transport"), ("CFC", "Canadian Armed Forces"), ("GAF", "German Air Force"),
    ("IAM", "Italian Air Force"), ("FAF", "French Air Force"), ("CTM", "French Air Force transport"), ("BAF", "Belgian Air Component"),
    ("NATO", "NATO"), ("PLF", "Polish Air Force"), ("HAF", "Hellenic Air Force"), ("TUAF", "Turkish Air Force"), ("TUR", "Turkish Air Force"),
    ("ETHYL", "US Air Force tanker"), ("HOMER", "US Air Force tanker"), ("PACK", "US Air Force tanker"), ("QUID", "US Air Force"), ("FORTE", "US Air Force RQ-4 surveillance drone"),
    ("JAKE", "US Air Force"), ("DOOM", "US Air Force bomber"), ("TOPCAT", "US Air Force"), ("MOOSE", "US Air Force"), ("SHELL", "US Air Force tanker"),
    ("LAGR", "US Air Force"), ("KING", "US Air Force rescue"), ("COBRA", "US Air Force RC-135"), ("IAF", "Israeli Air Force"), ("RFF", "Russian Air Force"),
]
TYPE_DESC = {
    "C17": "Boeing C-17 Globemaster III (strategic airlifter)", "C130": "Lockheed C-130 Hercules (tactical airlifter)", "C30J": "Lockheed C-130J Super Hercules",
    "K35R": "Boeing KC-135R Stratotanker (aerial tanker)", "K35T": "Boeing KC-135T Stratotanker", "KC10": "McDonnell Douglas KC-10 Extender (tanker)", "KC46": "Boeing KC-46 Pegasus (tanker)",
    "K46": "Boeing KC-46 Pegasus (tanker)", "A332": "Airbus A330 MRTT (tanker/transport)", "A400": "Airbus A400M Atlas (airlifter)", "IL76": "Ilyushin Il-76 (airlifter)",
    "E3TF": "Boeing E-3 Sentry (AWACS)", "E3CF": "Boeing E-3 Sentry (AWACS)", "E3": "Boeing E-3 Sentry (AWACS)", "E6": "Boeing E-6B Mercury (command post)", "E8": "Northrop Grumman E-8 JSTARS",
    "E2": "Northrop Grumman E-2 Hawkeye (early warning)", "E2C": "Northrop Grumman E-2C Hawkeye", "E737": "Boeing E-7 Wedgetail (AWACS)",
    "P8": "Boeing P-8 Poseidon (maritime patrol)", "P3": "Lockheed P-3 Orion (maritime patrol)", "R135": "Boeing RC-135 (signals intelligence)", "RC35": "Boeing RC-135 (signals intelligence)",
    "U2": "Lockheed U-2 (high-altitude reconnaissance)", "Q4": "Northrop Grumman RQ-4 Global Hawk (drone)", "RQ4": "Northrop Grumman RQ-4 Global Hawk (drone)", "MQ9": "General Atomics MQ-9 Reaper (drone)",
    "F16": "General Dynamics F-16 Fighting Falcon", "F15": "McDonnell Douglas F-15 Eagle", "F35": "Lockheed F-35 Lightning II", "F18": "Boeing F/A-18 Hornet", "F18H": "Boeing F/A-18 Hornet",
    "F18S": "Boeing F/A-18E/F Super Hornet", "FA18": "Boeing F/A-18 Hornet", "F22": "Lockheed F-22 Raptor", "EUFI": "Eurofighter Typhoon", "RFAL": "Dassault Rafale", "GRIF": "Saab Gripen",
    "A10": "Fairchild A-10 Thunderbolt II", "TORN": "Panavia Tornado", "F14": "Grumman F-14 Tomcat", "SU27": "Sukhoi Su-27", "SU30": "Sukhoi Su-30", "SU35": "Sukhoi Su-35", "SU34": "Sukhoi Su-34", "MG29": "Mikoyan MiG-29",
    "B52": "Boeing B-52 Stratofortress (bomber)", "B1": "Rockwell B-1B Lancer (bomber)", "B2": "Northrop B-2 Spirit (bomber)", "TU95": "Tupolev Tu-95 Bear (bomber)", "T160": "Tupolev Tu-160 (bomber)",
    "H60": "Sikorsky H-60 Black Hawk / Seahawk", "H47": "Boeing CH-47 Chinook", "H64": "Boeing AH-64 Apache", "H53": "Sikorsky CH-53 (heavy lift helicopter)", "V22": "Bell Boeing V-22 Osprey",
    "B350": "Beechcraft King Air 350 (utility)", "BE20": "Beechcraft King Air (utility)", "GLF5": "Gulfstream V (VIP / special mission)", "GLEX": "Bombardier Global Express (special mission)", "C560": "Cessna Citation",
    "C21": "Learjet C-21 (VIP transport)", "C5": "Lockheed C-5 Galaxy (strategic airlifter)", "C5M": "Lockheed C-5M Super Galaxy", "A124": "Antonov An-124 (heavy airlifter)", "A225": "Antonov An-225", "HAWK": "BAE Hawk (trainer)",
}
BOMBER = {"B52", "B1", "B2", "TU95", "T160", "TU22", "TU16"}
UAV = {"Q4", "RQ4", "MQ9", "MQ1", "Q9", "Q1", "TB2", "HRON"}
SQUAWK = {"7500": ("Hijack", "Squawk 7500 means unlawful interference with the aircraft (hijack)."),
          "7600": ("Radio failure", "Squawk 7600 means the crew has lost radio contact."),
          "7700": ("General emergency", "Squawk 7700 is a general emergency: medical, technical, fuel or security.")}


def hex_country(hx):
    try:
        n = int(hx, 16)
    except (TypeError, ValueError):
        return ""
    for lo, hi, name in HEX_RANGES:
        if lo <= n <= hi:
            return name
    return ""


def call_operator(call):
    c = (call or "").strip().upper()
    for p, name in CALL_OPS:
        if c.startswith(p) and (len(c) == len(p) or c[len(p)].isdigit() or p in ("REACH", "ASCOT", "NAVY", "FORTE", "COBRA", "KING", "DOOM", "HOMER", "ETHYL", "PACK", "SHELL", "JAKE", "MOOSE", "TOPCAT", "QUID", "LAGR")):
            return name
    return ""


def classify(a):
    t = a.get("t") or ""
    if t in UAV:
        return "uav"
    if t in BOMBER:
        return "bomber"
    if t in S.TANKER:
        return "tanker"
    if t in S.ISR:
        return "isr"
    if t in S.FIGHTER:
        return "fighter"
    if t in S.AIRLIFT:
        return "lift"
    if a.get("category") == "A7" or t.startswith("H") and t[1:].isdigit() or t == "V22":
        return "heli"
    return "other"


def theatre_at(lat, lon):
    for t, (la0, la1, lo0, lo1) in C.BOXES.items():
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return t
    return ""


def _alt(a):
    v = a.get("alt_baro")
    if v == "ground":
        return "ground"
    return int(v) if isinstance(v, (int, float)) else None


def aircraft(a):
    """One adsb.lol record -> the fields the map popup shows."""
    la, lo = a.get("lat"), a.get("lon")
    hx = a.get("hex", "")
    ct = hex_country(hx)
    op = call_operator(a.get("flight"))
    if not op and ct:
        op = f"{ct} armed forces" if a.get("dbFlags") == 1 else ""
    t = a.get("t") or ""
    sq = str(a.get("squawk") or "")
    trk = a.get("track")
    return {"lat": round(la, 3), "lon": round(lo, 3), "t": t, "cls": classify(a), "hex": hx, "call": (a.get("flight") or "").strip(),
            "r": a.get("r") or "", "d": TYPE_DESC.get(t, ""), "o": op, "ct": ct, "alt": _alt(a), "gs": a.get("gs"),
            "trk": int(trk) if isinstance(trk, (int, float)) else None, "sq": sq, "em": (a.get("emergency") or "none") != "none" or sq in SQUAWK,
            "th": theatre_at(la, lo)}


def parse_squawks(payload, code):
    mean, why = SQUAWK[code]
    out = []
    for a in payload.get("ac", []):
        if a.get("lat") is None or a.get("lon") is None or (a.get("alt_baro") == "ground"):
            continue
        x = aircraft(a)
        x.update(sq=code, mean=mean, why=why)
        out.append(x)
    return out


def fetch_squawks():
    out = []
    for code in SQUAWK:
        try:
            out.extend(parse_squawks(S.get(f"https://api.adsb.lol/v2/sqk/{code}", retries=2, wait=3), code))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------- US Navy fleet tracker (USNI News)
REGIONS = {   # name -> (lat, lon) approximate centre used to place fleet units on the map
    "Eastern Mediterranean": (34.5, 29.5), "Mediterranean Sea": (35.5, 18.0), "Mediterranean": (35.5, 18.0), "Black Sea": (43.3, 34.0),
    "Baltic Sea": (57.0, 19.5), "North Sea": (56.0, 3.0), "Norwegian Sea": (68.0, 5.0), "Red Sea": (20.0, 38.5), "Gulf of Aden": (12.3, 47.0),
    "Arabian Sea": (16.0, 64.0), "Gulf of Oman": (24.5, 58.5), "Persian Gulf": (27.0, 51.5), "Indian Ocean": (-2.0, 70.0), "Atlantic Ocean": (35.0, -20.0),
    "Bay of Biscay": (45.0, -6.0), "Adriatic Sea": (42.5, 16.0),
}
SHIP_RE = re.compile(r"USS\s+([A-Z][A-Za-z.'\- ]+?)\s*\((CVN|LHA|LHD|LPD|LSD|DDG|CG|LCS|SSN|SSGN)-(\d+)\)")
HDR_RE = re.compile(r"\bIn (?:the )?(" + "|".join(sorted((re.escape(k) for k in REGIONS), key=len, reverse=True)) + r")\b")


def parse_usni(item_xml, link="", pub=""):
    """One Fleet and Marine Tracker article -> [{n, k, loc, g, d, tx, u, lat, lon}] for ships in mapped regions."""
    m = re.search(r"<content:encoded>(.*?)</content:encoded>", item_xml, re.S)
    body = m.group(1) if m else item_xml
    body = re.sub(r"<!\[CDATA\[|\]\]>", "", body)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))
    pm = re.search(r"as of ([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
    when = pm.group(1) if pm else pub
    heads = [(h.start(), h.group(1)) for h in HDR_RE.finditer(text)]
    out, seen = [], set()
    for i, (pos, region) in enumerate(heads):
        seg = text[pos:(heads[i + 1][0] if i + 1 < len(heads) else len(text))]
        sent = re.search(r"([^.]*(?:operating|conducting|deployed|in support)[^.]*\.)", seg)
        tx = sent.group(1).strip()[:260] if sent else ""
        lat, lon = REGIONS[region]
        n_here = 0
        for sm in SHIP_RE.finditer(seg):
            name, hull, num = sm.group(1).strip(), sm.group(2), sm.group(3)
            key = (name, hull, num)
            if key in seen:
                continue
            seen.add(key)
            kind = "carrier" if hull == "CVN" else "amphib" if hull in ("LHA", "LHD") else "navy"
            if kind == "navy" and n_here >= 6:
                continue
            ang = n_here * 2.4
            n_here += 1
            out.append({"n": f"USS {name} ({hull}-{num})", "k": kind, "loc": region, "g": "US Navy, " + (when and "as of " + when or "latest tracker"),
                        "d": when, "tx": tx, "u": link, "lat": lat + 0.9 * (n_here % 3 - 1) * (1 if n_here % 2 else -1), "lon": lon + ang * 0.35 - 1.5,
                        "th": theatre_at(lat, lon), "note": "Approximate position: the US Navy publishes a region, not coordinates. Updated weekly by USNI News."})
    return out


def fetch_usni():
    t = S.get("https://news.usni.org/category/fleet-tracker/feed", raw=True)
    t = t.decode("utf-8", "replace") if isinstance(t, bytes) else t
    items = re.findall(r"<item>.*?</item>", t, re.S)
    if not items:
        return []
    it = items[0]
    link = (re.search(r"<link>(.*?)</link>", it) or [None, ""])[1]
    pub = (re.search(r"<pubDate>(.*?)</pubDate>", it) or [None, ""])[1]
    return parse_usni(it, link, pub[:16])


# ---------------------------------------------------------------- maritime incidents (UKMTO and shipping news)
PLACES = [   # keyword -> (lat, lon, name); longest names first so specific places beat regions
    ("bab el-mandeb", 12.6, 43.3, "Bab el-Mandeb"), ("bab al-mandab", 12.6, 43.3, "Bab el-Mandeb"), ("hodeidah", 14.8, 42.95, "Hodeidah"),
    ("hodeida", 14.8, 42.95, "Hodeidah"), ("mocha", 13.3, 43.25, "Mocha, Yemen"), ("gulf of aden", 12.3, 47.0, "Gulf of Aden"), ("aden", 12.8, 45.0, "Aden"),
    ("strait of hormuz", 26.6, 56.3, "Strait of Hormuz"), ("hormuz", 26.6, 56.3, "Strait of Hormuz"), ("fujairah", 25.1, 56.4, "Fujairah"),
    ("gulf of oman", 24.5, 58.5, "Gulf of Oman"), ("kharg", 29.25, 50.3, "Kharg Island"), ("bandar abbas", 27.2, 56.3, "Bandar Abbas"),
    ("persian gulf", 27.0, 51.5, "Persian Gulf"), ("arabian gulf", 27.0, 51.5, "Persian Gulf"), ("red sea", 18.0, 40.0, "Red Sea"),
    ("eilat", 29.55, 34.95, "Eilat"), ("suez", 30.0, 32.5, "Suez"), ("eastern mediterranean", 34.5, 30.0, "Eastern Mediterranean"),
    ("black sea", 43.5, 34.0, "Black Sea"), ("odesa", 46.5, 30.7, "Odesa"), ("odessa", 46.5, 30.7, "Odesa"), ("novorossiysk", 44.7, 37.8, "Novorossiysk"),
    ("baltic", 57.0, 20.0, "Baltic Sea"), ("gulf of finland", 59.8, 25.0, "Gulf of Finland"), ("houthi", 15.0, 42.0, "Red Sea (Houthi area)"),
]
INC_RE = re.compile(r"tanker|vessel|ship|merchant|cargo|boat|ukmto|drone|missile|attack|struck|hit by|seiz|board|mine|explosion|projectile|hijack", re.I)


def parse_incident_news(xml, today=None, days=14):
    today = today or dt.date.today()
    out, seen = [], set()
    for it in re.findall(r"<item>.*?</item>", xml, re.S):
        title = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", (re.search(r"<title>(.*?)</title>", it, re.S) or [None, ""])[1])).strip()
        if not title or not INC_RE.search(title):
            continue
        low = title.lower()
        spot = next(((la, lo, nm) for kw, la, lo, nm in PLACES if kw in low), None)
        if not spot:
            continue
        key = re.sub(r"\W+", " ", low)[:60]
        if key in seen:
            continue
        seen.add(key)
        pm = (re.search(r"<pubDate>(.*?)</pubDate>", it) or [None, ""])[1]
        try:
            d = dt.datetime.strptime(pm[5:16], "%d %b %Y").date()
        except ValueError:
            continue
        if (today - d).days > days:
            continue
        link = html.unescape((re.search(r"<link>(.*?)</link>", it) or [None, ""])[1])
        src = html.unescape((re.search(r"<source[^>]*>(.*?)</source>", it, re.S) or [None, "News"])[1])
        la, lo, nm = spot
        out.append({"t": title, "d": d.isoformat(), "src": ("UKMTO (via " + src + ")") if "ukmto" in low else src, "u": link, "loc": nm, "lat": la, "lon": lo,
                    "th": theatre_at(la, lo), "uk": "ukmto" in low})
    return sorted(out, key=lambda x: (not x["uk"], x["d"]), reverse=False)[:60]


def fetch_incidents():
    out, seen = [], set()
    for q in ("UKMTO when:14d", "tanker attacked OR vessel struck Hormuz OR \"Red Sea\" OR \"Gulf of Aden\" when:14d", "ship drone attack Black Sea OR Odesa OR Baltic when:14d"):
        try:
            xml = S.get("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}), raw=True, retries=2, wait=3)
        except Exception:
            continue
        xml = xml.decode("utf-8", "replace") if isinstance(xml, bytes) else xml
        for x in parse_incident_news(xml):
            k = x["t"][:60]
            if k not in seen:
                seen.add(k)
                out.append(x)
    out.sort(key=lambda x: x["d"], reverse=True)
    return out[:40]


# ---------------------------------------------------------------- NASA FIRMS thermal detections
def parse_firms(text):
    """VIIRS CSV -> [{lat, lon, date, frp}] without low-confidence hits."""
    out = []
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].startswith("latitude"):
        return out
    head = lines[0].split(",")
    ix = {h: i for i, h in enumerate(head)}
    for ln in lines[1:]:
        f = ln.split(",")
        try:
            if f[ix["confidence"]].lower() == "l":
                continue
            out.append({"lat": float(f[ix["latitude"]]), "lon": float(f[ix["longitude"]]), "date": f[ix["acq_date"]], "frp": float(f[ix["frp"]] or 0)})
        except (ValueError, IndexError, KeyError):
            continue
    return out


def firms_url(key, box, days, date=None):
    la0, la1, lo0, lo1 = box
    u = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{lo0},{la0},{lo1},{la1}/{days}"
    return u + (f"/{date}" if date else "")


def firms_counts(key, theatre, days=150, max_calls=None, today=None):
    """Daily detection counts for a theatre box, five days per call, newest first. Cached rows [date, theatre, n, mw]."""
    import store
    today = today or dt.date.today()
    cap = max_calls if max_calls is not None else int(os.environ.get("FIRMS_MAX", "6"))
    rows = store.cache_rows("firms_events")
    have = {r[0] for r in rows if r[1] == theatre}
    box = C.BOXES[theatre]
    new, calls = [], 0
    d = today
    while (today - d).days < days and calls < cap:
        win = [d - dt.timedelta(days=i) for i in range(5)]
        if all(x.isoformat() in have for x in win):
            d -= dt.timedelta(days=5)
            continue
        start = win[-1]
        try:
            t = S.get(firms_url(key, box, 5, start.isoformat()), raw=True, retries=2, wait=4)
            pts = parse_firms(t.decode("utf-8", "replace") if isinstance(t, bytes) else t)
        except Exception:
            break
        calls += 1
        by = {}
        for p in pts:
            c = by.setdefault(p["date"], [0, 0.0])
            c[0] += 1
            c[1] += p["frp"]
        for x in win:
            if x.isoformat() not in have and x < today:
                c = by.get(x.isoformat(), [0, 0.0])
                new.append([x.isoformat(), theatre, str(c[0]), f"{c[1]:.0f}"])
        d -= dt.timedelta(days=5)
    if new:
        store.cache_rows_save("firms_events", rows + new)
    return calls


def firms_series(theatre):
    import store
    out = {}
    for d, th, n, mw in store.cache_rows("firms_events"):
        if th == theatre:
            out[d] = float(n)
    return sorted(out.items())


def fetch_fires(key, boxes, top=500):
    """Last two days of detections across the theatre boxes for the map layer (strongest first)."""
    pts = []
    for th, box in boxes.items():
        try:
            t = S.get(firms_url(key, box, 2), raw=True, retries=2, wait=4)
            for p in parse_firms(t.decode("utf-8", "replace") if isinstance(t, bytes) else t):
                p["th"] = th
                pts.append(p)
        except Exception:
            continue
    pts.sort(key=lambda p: -p["frp"])
    return pts[:top]


# ---------------------------------------------------------------- AIS: Baltic (Digitraffic, no key) and global (aisstream, free key)
MID = {"230": "Finland", "231": "Faroe Is.", "219": "Denmark", "220": "Denmark", "265": "Sweden", "266": "Sweden", "257": "Norway", "258": "Norway", "259": "Norway",
       "273": "Russia", "275": "Latvia", "277": "Lithuania", "276": "Estonia", "261": "Poland", "211": "Germany", "218": "Germany", "272": "Ukraine", "232": "United Kingdom",
       "233": "United Kingdom", "234": "United Kingdom", "235": "United Kingdom", "338": "United States", "366": "United States", "367": "United States", "368": "United States",
       "369": "United States", "422": "Iran", "428": "Israel", "403": "Saudi Arabia", "470": "UAE", "461": "Oman", "466": "Qatar", "408": "Bahrain", "447": "Kuwait", "473": "Yemen",
       "271": "Turkey", "212": "Cyprus", "209": "Cyprus", "249": "Malta", "256": "Malta", "351": "Panama", "352": "Panama", "353": "Panama", "370": "Panama", "371": "Panama",
       "372": "Panama", "636": "Liberia", "637": "Liberia", "538": "Marshall Is.", "477": "Hong Kong", "412": "China", "413": "China", "414": "China", "245": "Netherlands", "205": "Belgium",
       "227": "France", "228": "France", "247": "Italy", "237": "Greece", "239": "Greece", "240": "Greece", "241": "Greece", "248": "Malta", "311": "Bahamas", "255": "Madeira", "253": "Luxembourg"}


def ship_kind(t):
    t = int(t or 0)
    return "navy" if t == 35 else "tanker" if 80 <= t <= 89 else "cargo" if 70 <= t <= 79 else "other"


def parse_digitraffic(loc, vessels, box):
    """Digitraffic latest positions + vessel register -> military and law-enforcement ships inside the box (others counted)."""
    la0, la1, lo0, lo1 = box
    meta = {v.get("mmsi"): v for v in vessels}
    ships, total = [], 0
    for f in loc.get("features", []):
        try:
            lon, lat = f["geometry"]["coordinates"][:2]
        except (KeyError, TypeError, ValueError):
            continue
        if not (la0 <= lat <= la1 and lo0 <= lon <= lo1):
            continue
        total += 1
        mm = f.get("mmsi") or (f.get("properties") or {}).get("mmsi")
        v = meta.get(mm) or {}
        st = int(v.get("shipType") or 0)
        if st not in (35, 55):
            continue
        p = f.get("properties") or {}
        flag = MID.get(str(mm)[:3], "")
        ships.append({"n": (v.get("name") or str(mm)).strip(), "k": "navy", "loc": f"{lat:.2f}N {lon:.2f}E", "g": "Military ship (AIS type 35)" if st == 35 else "Law enforcement vessel (AIS type 55)",
                      "lat": lat, "lon": lon, "flag": flag, "dest": (v.get("destination") or "").strip(), "spd": p.get("sog"), "d": "live", "th": theatre_at(lat, lon),
                      "note": "AIS position from Finnish Transport Infrastructure Agency (Digitraffic). Warships often switch AIS off."})
    return ships, total


def fetch_digitraffic(box=None):
    hdr = {"Accept-Encoding": "gzip", "Digitraffic-User": "warwatch"}
    loc = S.get("https://meri.digitraffic.fi/api/ais/v1/locations", headers=hdr, retries=2, wait=4)
    ves = S.get("https://meri.digitraffic.fi/api/ais/v1/vessels", headers=hdr, retries=2, wait=4)
    return parse_digitraffic(loc, ves if isinstance(ves, list) else [], box or C.BOXES["europe_east"])


# minimal RFC 6455 client, enough for aisstream.io
def ws_frame(payload, opcode=1):
    b = payload if isinstance(payload, bytes) else payload.encode()
    mask = os.urandom(4)
    n = len(b)
    head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n))
    return head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(b))


def ws_read(buf):
    """-> (opcode, payload, rest) or None when the buffer holds no complete server frame."""
    if len(buf) < 2:
        return None
    op, ln, pos = buf[0] & 0x0F, buf[1] & 0x7F, 2
    if ln == 126:
        if len(buf) < 4:
            return None
        ln, pos = struct.unpack(">H", buf[2:4])[0], 4
    elif ln == 127:
        if len(buf) < 10:
            return None
        ln, pos = struct.unpack(">Q", buf[2:10])[0], 10
    if len(buf) < pos + ln:
        return None
    return op, buf[pos:pos + ln], buf[pos + ln:]


def parse_ais_messages(msgs):
    """aisstream messages -> {mmsi: ship dict} merged from position reports and static data."""
    ships = {}
    for m in msgs:
        meta = m.get("MetaData") or {}
        mm = str(meta.get("MMSI") or "")
        if not mm:
            continue
        s = ships.setdefault(mm, {"mmsi": mm, "n": (meta.get("ShipName") or "").strip(), "lat": meta.get("latitude"), "lon": meta.get("longitude"), "type": 0, "dest": "", "spd": None})
        body = m.get("Message") or {}
        if "PositionReport" in body:
            s["spd"] = body["PositionReport"].get("Sog")
        if "ShipStaticData" in body:
            sd = body["ShipStaticData"]
            s["type"] = sd.get("Type") or s["type"]
            s["dest"] = (sd.get("Destination") or "").strip()
            s["n"] = (sd.get("Name") or s["n"] or "").strip()
    return ships


def fetch_aisstream(key, boxes, seconds=75, max_msgs=20000):
    ctx = ssl.create_default_context()
    sock = ctx.wrap_socket(socket.create_connection(("stream.aisstream.io", 443), timeout=20), server_hostname="stream.aisstream.io")
    k = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(f"GET /v0/stream HTTP/1.1\r\nHost: stream.aisstream.io\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {k}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += sock.recv(4096)
    head, buf = buf.split(b"\r\n\r\n", 1)
    if b" 101 " not in head.split(b"\r\n")[0]:
        raise RuntimeError("aisstream refused the connection")
    sub = {"APIKey": key, "BoundingBoxes": [[[b[0], b[2]], [b[1], b[3]]] for b in boxes], "FilterMessageTypes": ["PositionReport", "ShipStaticData"]}
    sock.sendall(ws_frame(json.dumps(sub)))
    sock.settimeout(10)
    msgs, t0 = [], time.time()
    while time.time() - t0 < seconds and len(msgs) < max_msgs:
        try:
            d = sock.recv(65536)
        except socket.timeout:
            continue
        if not d:
            break
        buf += d
        while True:
            fr = ws_read(buf)
            if not fr:
                break
            op, pl, buf = fr
            if op == 1:
                try:
                    msgs.append(json.loads(pl))
                except ValueError:
                    pass
            elif op == 9:
                sock.sendall(ws_frame(pl, 10))
            elif op == 8:
                return parse_ais_messages(msgs)
    sock.close()
    return parse_ais_messages(msgs)
