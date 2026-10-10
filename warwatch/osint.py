"""Open-source enrichment: who owns an aircraft, where is the fleet, what happened at sea.

Pure parsers (testable offline) plus thin fetchers. Standard library only. Every fetcher
is called fail-soft by extras.collect(): a dead source leaves its map layer empty.
"""
import base64
import datetime as dt
import html
import json
import math
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


BASES = [("Ramstein AB, Germany", 49.44, 7.6), ("Spangdahlem AB, Germany", 49.97, 6.7), ("RAF Lakenheath / Mildenhall, UK", 52.4, 0.55), ("Aviano AB, Italy", 46.03, 12.6),
         ("NAS Sigonella, Italy", 37.4, 14.9), ("Souda Bay, Greece", 35.53, 24.15), ("Incirlik AB, Turkey", 37.0, 35.43), ("RAF Akrotiri, Cyprus", 34.59, 32.99),
         ("Rzeszow-Jasionka, Poland", 50.11, 22.02), ("Powidz AB, Poland", 52.38, 17.85), ("Lask AB, Poland", 51.55, 19.18), ("Mihail Kogalniceanu, Romania", 44.36, 28.49),
         ("Siauliai AB, Lithuania", 55.89, 23.4), ("Amari AB, Estonia", 59.26, 24.2), ("Al Udeid AB, Qatar", 25.12, 51.32), ("Al Dhafra AB, UAE", 24.25, 54.55),
         ("Ali Al Salem AB, Kuwait", 29.35, 47.52), ("Isa AB / NSA Bahrain", 25.92, 50.59), ("Prince Sultan AB, Saudi Arabia", 24.06, 47.58), ("Muwaffaq Salti AB, Jordan", 31.83, 36.78),
         ("Ovda / Nevatim, Israel", 30.6, 34.9), ("Camp Lemonnier, Djibouti", 11.55, 43.15), ("Diego Garcia", -7.31, 72.41), ("Duqm / Thumrait, Oman", 19.5, 57.3),
         ("Ben Gurion, Israel", 32.01, 34.89), ("Tehran, Iran", 35.69, 51.31), ("Moscow, Russia", 55.75, 37.6), ("Kyiv, Ukraine", 50.45, 30.52), ("Kaliningrad, Russia", 54.7, 20.5)]


def _bearing(la1, lo1, la2, lo2):
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _dist_nm(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 3440.065 * 2 * math.asin(math.sqrt(a))


def heading_toward(lat, lon, trk, max_nm=1400):
    """Nearest known air base or capital lying within 20 degrees of the aircraft's track: an inference from heading, not a flight plan."""
    if trk is None:
        return ""
    best = None
    for name, la, lo in BASES:
        d = _dist_nm(lat, lon, la, lo)
        if d < 25 or d > max_nm:
            continue
        off = abs((_bearing(lat, lon, la, lo) - trk + 180) % 360 - 180)
        if off <= 20 and (best is None or d < best[0]):
            best = (d, name)
    return f"heading towards {best[1]}, about {int(round(best[0], -1))} nm ahead (inferred from track, not a flight plan)" if best else ""


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
            "th": theatre_at(la, lo), "rt": heading_toward(la, lo, trk) if a.get("alt_baro") != "ground" else ""}


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


UKMTO_API = "https://sccd.royalnavy.mod.uk/api/ukmto/all"   # the endpoint the ukmto.org incident map itself calls


def parse_ukmto(rows, today=None, days=120):
    """Official UKMTO incident list -> map markers, newest first."""
    today = today or dt.date.today()
    out = []
    for r in rows:
        try:
            d = dt.date.fromisoformat(str(r.get("utcDateOfIncident"))[:10])
            la, lo = float(r["locationLatitude"]), float(r["locationLongitude"])
        except (ValueError, KeyError, TypeError):
            continue
        if (today - d).days > days:
            continue
        kind = (r.get("incidentTypeName") or "Incident").strip()
        vt = (r.get("vesselType") or "").strip()
        vn = (r.get("vesselName") or "").strip(". ")
        det = re.sub(r"\s+", " ", (r.get("otherDetails") or "")).strip()
        m = re.search(r"UKMTO has received.*", det)
        det = (m.group(0) if m else det)[:700]
        flags = []
        if r.get("vesselUnderPirateControl"):
            flags.append("vessel under pirate control")
        if r.get("crewHeld"):
            flags.append(f"{r['crewHeld']} crew held")
        place = (r.get("place") or "").strip()
        out.append({"t": f"UKMTO {r.get('incidentNumber', '')}: {kind}" + (f", {vt}" if vt else "") + (f" {vn}" if vn else "") + (f" near {place}" if place else ""),
                    "d": d.isoformat(), "src": "UKMTO (official)", "u": "https://www.ukmto.org/recent-incidents", "loc": place, "lat": la, "lon": lo,
                    "th": theatre_at(la, lo), "uk": True, "tx": det + (" " + "; ".join(flags) + "." if flags else ""), "pin": r.get("pinColour", ""),
                    "lvl": r.get("incidentTypeLevel", 0)})
    return sorted(out, key=lambda x: x["d"], reverse=True)


_UK = {}


def ukmto_all():
    if "all" not in _UK:
        _UK["all"] = S.get(UKMTO_API, headers={"Accept": "application/json", "Origin": "https://www.ukmto.org", "Referer": "https://www.ukmto.org/"}, retries=2, wait=3)
    return _UK["all"]


def ukmto_archive(rows):
    """Folds the feed's incidents into history/cache/ukmto_inc.csv (incident, date, lat, lon), which keeps what the feed later drops. -> [(date, lat, lon)]"""
    import store
    kept = {r[0]: r for r in store.cache_rows("ukmto_inc")}
    for x in rows:
        k = f"{x['t']} {x['d']}"
        kept[k] = [k, x["d"], f"{x['lat']}", f"{x['lon']}"]
    out = sorted(kept.values(), key=lambda r: (r[1], r[0]))
    store.cache_rows_save("ukmto_inc", out)
    return [(r[1], float(r[2]), float(r[3])) for r in out]


def ukmto_series(theatre, days=30, today=None):
    """The 30-day incident count for every day the archive covers completely. The feed keeps only the last ~100 days, so the archive
    starts there and grows daily; a window that reaches back past the oldest archived incident is left out rather than undercounted.
    -> [(date, count)]"""
    today = today or dt.date.today()
    inc = ukmto_archive(parse_ukmto(ukmto_all(), today, 100000))
    if not inc:
        return []
    first = dt.date.fromisoformat(inc[0][0]) + dt.timedelta(days=days)
    mine = [dt.date.fromisoformat(d) for d, la, lo in inc if theatre_at(la, lo) == theatre]
    out, d = [], first
    while d <= today:
        out.append((d.isoformat(), float(sum(1 for m in mine if 0 <= (d - m).days <= days))))
        d += dt.timedelta(days=1)
    return out


TZEVA_API = "https://api.tzevaadom.co.il/alerts-history"   # Tzeva Adom's mirror of Home Front Command alerts; oref.org.il itself refuses non-Israeli addresses
TZEVA_HOSTILE = {0: "rockets and missiles", 2: "infiltration", 5: "hostile aircraft"}   # 1 hazmat, 3 earthquake, 4 tsunami: not attacks


def parse_tzeva(groups):
    """Tzeva Adom history (alert groups, each a list of {time, cities, threat, isDrill}) -> [[id, utc time, threats, cities]] for groups
    with at least one real hostile alert. A group is one attack wave: a salvo sets off sirens in many towns within a few minutes."""
    out = []
    for g in groups or []:
        al = [a for a in g.get("alerts") or [] if not a.get("isDrill") and a.get("threat") in TZEVA_HOSTILE and a.get("time")]
        if not al:
            continue
        t = dt.datetime.fromtimestamp(min(a["time"] for a in al), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
        out.append([str(g.get("id")), t, "|".join(sorted({str(a["threat"]) for a in al})), str(len({c for a in al for c in a.get("cities") or []}))])
    return out


_TZ = {}


def tzeva_archive(rows):
    """Folds the feed's attack waves into history/cache/tzeva_alerts.csv, which keeps what the feed later drops. -> all rows, oldest first."""
    import store
    kept = {r[0]: r for r in store.cache_rows("tzeva_alerts")}
    for r in rows:
        kept[r[0]] = r
    out = sorted(kept.values(), key=lambda r: (r[1], r[0]))
    store.cache_rows_save("tzeva_alerts", out)
    return out


def alert_waves(times, gap=10):
    """Alert times (datetimes) -> the start of each attack wave: sirens less than `gap` minutes apart belong to one wave."""
    out, last = [], None
    for t in sorted(times):
        if last is None or (t - last).total_seconds() > gap * 60:
            out.append(t)
        last = t
    return out


def weekly_waves(waves, first, today, days=7):
    """Waves in the `days` up to each day from `first` -> [(date, count)]."""
    ds = [w.date() for w in waves]
    out, d = [], first
    while d <= today:
        out.append((d.isoformat(), float(sum(1 for w in ds if 0 <= (d - w).days < days))))
        d += dt.timedelta(days=1)
    return out


OREF_MIRROR = "https://raw.githubusercontent.com/dleshem/israel-alerts-data/main/israel-alerts.csv"   # Home Front Command history since July 2014 (Apache 2.0)
OREF_HOSTILE = ("ירי רקטות וטילים", "חדירת כלי טיס עוין", "חדירת מחבלים")   # rockets and missiles, hostile aircraft, infiltration


def parse_oref_csv(text):
    """The Home Front Command history mirror (one row per alert message: data, date, time, alertDate, category, category_desc, ...)
    -> alert times of real attacks. Drills, all-clears and early-warning notices are left out."""
    import csv
    import io
    try:
        from zoneinfo import ZoneInfo
        il = ZoneInfo("Asia/Jerusalem")
    except Exception:   # no time-zone database: winter time, an hour off in summer
        il = dt.timezone(dt.timedelta(hours=2))
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        desc = r.get("category_desc") or ""
        if desc not in OREF_HOSTILE:
            continue
        try:
            out.append(dt.datetime.fromisoformat(r["alertDate"][:16]).replace(tzinfo=il).astimezone(dt.timezone.utc))
        except (KeyError, ValueError):
            continue
    return out


def tzeva_series(days=7, today=None):
    """Attack waves that set off sirens in Israel in the `days` up to each day. The feed holds only its latest waves, so the live part
    starts `days` after the oldest archived one; days before that come from the Home Front Command history mirror (backfill.py alerts),
    counted the same way. -> [(date, count)]"""
    import store
    if "all" not in _TZ:
        _TZ["all"] = S.get(TZEVA_API, headers={"Accept": "application/json", "Referer": "https://www.tzevaadom.co.il/"}, retries=2, wait=3)
    rows = tzeva_archive(parse_tzeva(_TZ["all"]))
    if not rows:
        return store.backfill("tzeva_israel")
    waves = alert_waves(dt.datetime.fromisoformat(r[1]).replace(tzinfo=dt.timezone.utc) for r in rows)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    return store.seed("tzeva_israel", weekly_waves(waves, waves[0].date() + dt.timedelta(days=days), today, days))


def ukmto_recent(theatre, days=30, today=None):
    """Official UKMTO incidents in the last `days` inside a theatre box."""
    return float(sum(1 for x in parse_ukmto(ukmto_all(), today, days) if x["th"] == theatre))


def fetch_incidents():
    out = []
    try:
        out.extend(parse_ukmto(ukmto_all()))
    except Exception:
        pass
    seen = {x["t"][:60] for x in out}
    for q in ("UKMTO when:7d", "tanker attacked OR vessel struck Hormuz OR \"Red Sea\" OR \"Gulf of Aden\" when:7d", "ship drone attack Black Sea OR Odesa OR Baltic when:7d"):
        try:
            xml = S.get("https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}), raw=True, retries=2, wait=3)
        except Exception:
            continue
        xml = xml.decode("utf-8", "replace") if isinstance(xml, bytes) else xml
        for x in parse_incident_news(xml, days=7):
            if x["t"][:60] not in seen:
                seen.add(x["t"][:60])
                x["tx"] = ""
                out.append(x)
    out.sort(key=lambda x: x["d"], reverse=True)
    return out[:80]


# ---------------------------------------------------------------- Crisis Group CrisisWatch, read from its RSS feed
# crisisgroup.org/crisiswatch refuses GitHub and home connections alike (Cloudflare), but the site's RSS feed answers and carries the
# whole monthly CrisisWatch page, including its lists of conflict-risk alerts and deteriorated situations.
CRISISGROUP_RSS = "https://www.crisisgroup.org/rss.xml"
CW_LISTS = {"alert": "Conflict Risk Alerts", "resolution": "Resolution Opportunities", "deteriorated": "Deteriorated Situations", "improved": "Improved Situations"}
CW_THEATRE = {   # CrisisWatch entry slugs -> theatre
    "ukraine": r"ukraine|russia|belarus|moldova", "europe_east": r"poland|baltic|lithuania|latvia|estonia|finland",
    "iran": r"iran|iraq", "yemen": r"yemen|saudi|red-sea|gulf", "israel": r"israel|palestin|lebanon|syria|jordan",
    "taiwan": r"taiwan", "scs": r"south-china-sea|philippines", "korea": r"korea", "southasia": r"india|pakistan|kashmir",
    "libya": r"libya", "sudan": r"sudan", "drc": r"congo", "venezuela": r"venezuela|colombia|guyana|cuba",
}
MONTHS_EN = {m: i + 1 for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"))}


def parse_crisiswatch(rss):
    """Crisis Group RSS -> [(alert month 'YYYY-MM-01', list name, entry slug)] for each monthly CrisisWatch issue in the feed. An issue titled
    'September Trends and October Alerts 2026' is filed under October 2026: its alerts look ahead to that month."""
    out = []
    for item in re.findall(r"<item>.*?</item>", rss, re.S):
        m = re.search(r"<title>\s*(\w+) Trends and (\w+) Alerts (\d{4})\s*</title>", item)
        if not m or m.group(2).lower() not in MONTHS_EN:
            continue
        mon, yr = MONTHS_EN[m.group(2).lower()], int(m.group(3))
        body = html.unescape(item)
        for key, head in CW_LISTS.items():
            k = body.find(head + "</h4>")
            if k < 0:
                continue
            seg = body[k: body.find("</p>", k)]
            out += [(f"{yr:04d}-{mon:02d}-01", key, slug) for slug in re.findall(r'data-entry-target="([\w-]+)"', seg)]
    return out


def crisiswatch_archive(rows):
    """Folds each issue's lists into history/cache/crisiswatch.csv (month, list, slug); the feed keeps only its last ten posts."""
    import store
    kept = {tuple(r) for r in store.cache_rows("crisiswatch")}
    kept |= {tuple(r) for r in rows}
    out = sorted(kept)
    store.cache_rows_save("crisiswatch", [list(r) for r in out])
    return out


_CW = {}


def crisiswatch_series(theatre):
    """Per CrisisWatch issue: 2 for a conflict-risk alert on a country in the theatre, plus 1 for a deteriorated situation there. -> [(month, score)]"""
    if "rows" not in _CW:
        _CW["rows"] = crisiswatch_archive(parse_crisiswatch(S.get(CRISISGROUP_RSS, raw=True, retries=2, wait=5)))
    pat = re.compile(CW_THEATRE[theatre])
    months = sorted({r[0] for r in _CW["rows"]})
    mine = {(r[0], r[1]) for r in _CW["rows"] if pat.search(r[2])}
    return [(m, 2.0 * ((m, "alert") in mine) + 1.0 * ((m, "deteriorated") in mine)) for m in months]


# ---------------------------------------------------------------- Bluesky posts, sampled from the Jetstream firehose
JETSTREAM = ("jetstream2.us-east.bsky.network", "jetstream1.us-east.bsky.network", "jetstream1.us-west.bsky.network", "jetstream2.us-west.bsky.network")
BSKY_WAR = re.compile(r"\b(war|military|troops|strikes?|airstrikes?|missiles?|rockets?|drones?|shelling|bomb\w*|attack\w*|invasion|invade\w*|mobili[sz]\w*|"
                      r"evacuat\w*|sirens?|air raid|warships?|navy|blockade|escalat\w*|ceasefire|nuclear|explosions?|offensive)\b", re.I)


def bsky_tally(posts):
    """[(text, langs)] -> (English posts, {theatre: English posts that name the theatre and use war vocabulary})."""
    import extras
    pats = {t: re.compile(r"\b(?:" + p + ")", re.I) for t, p in extras.KEYS.items()}
    n, hits = 0, {}
    for text, langs in posts:
        if "en" not in (langs or ()):
            continue
        n += 1
        if not BSKY_WAR.search(text or ""):
            continue
        for t, pat in pats.items():
            if pat.search(text):
                hits[t] = hits.get(t, 0) + 1
    return n, hits


def jetstream_window(start_us, seconds=60, host=JETSTREAM[0], wall=120):
    """New posts in the `seconds` after start_us (microseconds), replayed from Jetstream's buffer of the last day or so. -> [(text, langs)]"""
    ctx = ssl.create_default_context()
    sock = ctx.wrap_socket(socket.create_connection((host, 443), timeout=20), server_hostname=host)
    path = f"/subscribe?wantedCollections=app.bsky.feed.post&cursor={int(start_us)}"
    k = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {C.USER_AGENT}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 f"Sec-WebSocket-Key: {k}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = sock.recv(4096)
        if not d:
            raise RuntimeError("jetstream closed the connection")
        buf += d
    head, buf = buf.split(b"\r\n\r\n", 1)
    if b" 101 " not in head.split(b"\r\n")[0]:
        raise RuntimeError("jetstream refused the connection: " + head.split(b"\r\n")[0].decode("latin-1")[:80])
    end, out, t0 = start_us + seconds * 1_000_000, [], time.time()
    sock.settimeout(10)
    try:
        while time.time() - t0 < wall:
            try:
                d = sock.recv(262144)
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
                if op == 9:
                    sock.sendall(ws_frame(pl, 10))
                    continue
                if op == 8:
                    return out
                if op != 1:
                    continue
                try:
                    ev = json.loads(pl)
                except ValueError:
                    continue
                if ev.get("time_us", 0) >= end:
                    return out
                c = ev.get("commit") or {}
                if ev.get("kind") == "commit" and c.get("operation") == "create":
                    r = c.get("record") or {}
                    out.append((r.get("text") or "", r.get("langs") or ()))
    finally:
        sock.close()
    raise RuntimeError(f"jetstream window not finished in {wall}s ({len(out)} posts)")


_BS = {}


def bsky_sample(hours=None, step_min=30, seconds=300, budget=900, now=None):
    """Samples five minutes of posts every half hour over the last `hours` (env BSKY_HOURS, default 7), skipping windows already in
    history/cache/bsky_windows.csv (start, English posts, 'theatre:hits ...'). Jetstream keeps about a day, so a 6-hourly job misses nothing.
    -> all archived rows."""
    import store
    if "rows" in _BS:
        return _BS["rows"]
    hours = float(hours or os.environ.get("BSKY_HOURS") or 7)
    kept = {r[0]: r for r in store.cache_rows("bsky_windows")}
    now = now or dt.datetime.now(dt.timezone.utc)
    t = now.replace(minute=(now.minute // step_min) * step_min, second=0, microsecond=0) - dt.timedelta(minutes=step_min)
    starts = []
    while t >= now - dt.timedelta(hours=hours):
        starts.append(t)
        t -= dt.timedelta(minutes=step_min)
    t0, errs = time.time(), []
    for st in starts:
        key = st.strftime("%Y-%m-%dT%H:%M")
        if key in kept or time.time() - t0 > budget:
            continue
        for host in JETSTREAM:
            try:
                n, hits = bsky_tally(jetstream_window(int(st.timestamp() * 1_000_000), seconds, host))
            except Exception as e:
                errs.append(f"{host}: {e}"[:120])
                continue
            if n:
                kept[key] = [key, str(n), " ".join(f"{k}:{v}" for k, v in sorted(hits.items()))]
            break
    out = sorted(kept.values())
    if not out:
        raise RuntimeError("no Bluesky sample: " + "; ".join(errs[:3]))
    store.cache_rows_save("bsky_windows", out)
    _BS["rows"] = out
    return out


def bsky_series(theatre, min_posts=10000):
    """War-vocabulary posts naming the theatre per 10,000 English Bluesky posts, per UTC day with at least `min_posts` sampled -> [(date, rate)]."""
    by = {}
    for key, n, hits in bsky_sample():
        tot = by.setdefault(key[:10], [0, 0])
        tot[0] += int(n)
        tot[1] += sum(int(v) for k, v in (h.split(":") for h in hits.split()) if k == theatre)
    return [(d, 1e4 * h / n) for d, (n, h) in sorted(by.items()) if n >= min_posts]


# ---------------------------------------------------------------- NASA FIRMS thermal detections
def parse_firms(text, keep_low=False):
    """VIIRS CSV -> [{lat, lon, date, ts, frp}] without low-confidence hits (unless keep_low). ts is the satellite pass time, UTC."""
    out = []
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].startswith("latitude"):
        return out
    head = lines[0].split(",")
    ix = {h: i for i, h in enumerate(head)}
    for ln in lines[1:]:
        f = ln.split(",")
        try:
            if not keep_low and f[ix["confidence"]].lower() == "l":
                continue
            p = {"lat": float(f[ix["latitude"]]), "lon": float(f[ix["longitude"]]), "date": f[ix["acq_date"]], "frp": float(f[ix["frp"]] or 0)}
            hm = f[ix["acq_time"]].strip().zfill(4) if "acq_time" in ix else ""
            p["ts"] = f"{p['date']}T{hm[:2]}:{hm[2:]}Z" if len(hm) == 4 and hm.isdigit() else ""
            out.append(p)
        except (ValueError, IndexError, KeyError):
            continue
    return out


FIRE_CELL = 0.02          # degrees (about 2 km): VIIRS pixels are 375 m, and a flare's detections scatter within a few hundred metres
ROUTINE_DAYS = 3          # a cell (or a neighbour) that burns on this many of the days read is a routine source: gas flare, refinery, steel works


def mark_routine(pts, days=ROUTINE_DAYS):
    """Sets p['routine'] on each detection whose 3 x 3 cell neighbourhood has detections on at least `days` distinct dates."""
    cells = {}
    for p in pts:
        cells.setdefault((round(p["lat"] / FIRE_CELL), round(p["lon"] / FIRE_CELL)), set()).add(p["date"])
    for p in pts:
        i, j = round(p["lat"] / FIRE_CELL), round(p["lon"] / FIRE_CELL)
        seen = set()
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                seen |= cells.get((i + di, j + dj), set())
        p["routine"] = len(seen) >= days
    return pts


def firms_url(key, box, days, date=None):
    la0, la1, lo0, lo1 = box
    u = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{lo0},{la0},{lo1},{la1}/{days}"
    return u + (f"/{date}" if date else "")


def _fkey(theatre):
    return theatre + "@" + "_".join(str(v) for v in C.FIRMS_BOX[theatre]) + "#all"   # "#all": low-confidence hits included, like backfill/data


def firms_counts(key, theatre, days=150, max_calls=None, today=None):
    """Daily detection counts for a theatre box, five days per call, newest first. Cached rows [date, theatre, n, mw]."""
    import store
    today = today or dt.date.today()
    cap = max_calls if max_calls is not None else int(os.environ.get("FIRMS_MAX", "6"))
    rows = store.cache_rows("firms_events")
    have = {r[0] for r in rows if r[1] == theatre}
    box = C.FIRMS_BOX[theatre]
    theatre = _fkey(theatre)
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
            pts = parse_firms(t.decode("utf-8", "replace") if isinstance(t, bytes) else t, keep_low=True)   # every detection, as the archive back-fill counts them
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
        if th == _fkey(theatre):
            out[d] = float(n)
    return sorted(out.items())


def fetch_fires(key, boxes, top=300, days=7, today=None):
    """Last `days` days of detections across the theatre boxes for the map layer, each with its pass time and a routine flag.
    FIRMS serves at most 5 days per call, so 7 days take two calls per box. Per box the newest unusual detections come
    first, then the strongest routine ones."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    pts, seen = [], set()
    for th, box in boxes.items():
        got, left, end = [], days, today
        while left > 0:
            n = min(5, left)
            start = end - dt.timedelta(days=n - 1)
            try:
                t = S.get(firms_url(key, box, n, start.isoformat()), raw=True, retries=2, wait=4)
                for p in parse_firms(t.decode("utf-8", "replace") if isinstance(t, bytes) else t):
                    k = (round(p["lat"], 3), round(p["lon"], 3), p["date"], p.get("ts", ""))
                    if k in seen:
                        continue
                    seen.add(k)
                    p["th"] = theatre_at(p["lat"], p["lon"]) or th
                    got.append(p)
            except Exception:
                pass
            left -= n
            end = start - dt.timedelta(days=1)
        mark_routine(got)
        new = sorted((p for p in got if not p["routine"]), key=lambda p: (p.get("ts") or p["date"], p["frp"]), reverse=True)
        old = sorted((p for p in got if p["routine"]), key=lambda p: -p["frp"])
        pts.extend(new[:top] + old[:top // 3])
    return pts


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


def fetch_aisstream(key, boxes, seconds=75, max_msgs=20000, host="stream.aisstream.io", path="/v0/stream"):
    """Reads an aisstream-compatible websocket (aisstream.io, or Open Waters at ais.openwaters.io /v1/stream)."""
    ctx = ssl.create_default_context()
    sock = ctx.wrap_socket(socket.create_connection((host, 443), timeout=20), server_hostname=host)
    k = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {k}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
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
            if op in (1, 2):   # aisstream sends JSON in binary frames
                try:
                    m = json.loads(pl)
                except ValueError:
                    continue
                if "error" in m or "Error" in m:
                    raise RuntimeError("aisstream: " + str(m.get("error") or m.get("Error"))[:100])
                msgs.append(m)
            elif op == 9:
                sock.sendall(ws_frame(pl, 10))
            elif op == 8:
                return parse_ais_messages(msgs)
    sock.close()
    return parse_ais_messages(msgs)
