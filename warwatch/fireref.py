#!/usr/bin/env python3
"""Builds the fire reference tables that firecls.py reads (docs/FIRECLASS_PLAN.md, F1). Standard library only, but slow:
it reads the whole NASA FIRMS VIIRS S-NPP archive for the theatre boxes (about 4 GB), so it runs in fireref.yml, not
in the dashboard build.

    python3 warwatch/fireref.py probe                         # are the archive files and site sources reachable?
    python3 warwatch/fireref.py build [--box iran,yemen] [--years 2012-2025] [--cache DIR]
    python3 warwatch/fireref.py sites [--box iran] [--no-osm] # OpenStreetMap + World Bank GGFR + WRI (+ GEM files in data/raw)
    python3 warwatch/fireref.py check                         # spot checks: flares are routine, city centres are not
    python3 warwatch/fireref.py cases                         # the class each case in data/fire_cases.csv gets on its day
    python3 warwatch/fireref.py econ                          # The Economist's war-related fires, last 21 days -> history/cache (every 6 h)
    python3 warwatch/fireref.py replay [--box iran] [--from 2018]   # classify the archive day by day -> backfill/data/firecls/firms_anom_<box>.csv

Archive: https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<year>/viirs-snpp_<year>_<Country>.csv
(standard processing, no key, one file per country and year; the `type` column marks volcanoes, static land sources
such as gas flares, and offshore detections).
"""
import argparse
import array
import bisect
import csv
import datetime as dt
import gzip
import http.client
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402
import firecls as F  # noqa: E402
import osmsource as O  # noqa: E402

UA = {"User-Agent": "warwatch (github.com/khourix/warwatch)"}
ARCHIVE = "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/{y}/viirs-snpp_{y}_{c}.csv"
GGFR = ("https://thedocs.worldbank.org/en/doc/bd2432bbb0e514986f382f61b14b2608-0400072025/related/"
        "2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx")
WRI = "https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv"
FRP_EDGES = [0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 75, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000]
NOTABLE_DAYS = 20      # a cell that burned on this many days in some year keeps its full row (flares, plants, a shelled town)
NOTABLE_TYPES = 3      # ... as does one with this many volcano / static / offshore detections
KEEP_STATIC_DAYS = 60  # a cell burning this many days in a year counts as static for that year's seasonal (coarse) mask
SITE_HEADER = "# Contains data (c) OpenStreetMap contributors (ODbL), World Bank GGFR, WRI Global Power Plant Database and Global Energy Monitor (CC BY 4.0)\n"


def log(*a):
    print(*a, flush=True)


def get(url, data=None, timeout=120, tries=4, headers=None):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=dict(UA, **(headers or {})))
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return f.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or k == tries - 1:
                raise
        except (urllib.error.URLError, OSError, http.client.HTTPException):   # timeouts, resets, cut-off bodies
            if k == tries - 1:
                raise
        time.sleep(5 * 2 ** k)


# ---------------------------------------------------------------- archive files
def archive_file(country, year, cache, sat="snpp"):
    """Local path of the year's country file (downloaded once into the cache), or None when FIRMS has no such file.
    sat: snpp (the reference tables and replay), noaa20 or noaa21 (the other VIIRS satellites the live map also reads)."""
    os.makedirs(cache, exist_ok=True)
    p = os.path.join(cache, f"viirs-{sat}_{year}_{country}.csv")
    if os.path.exists(p):
        return p
    try:
        body = get(ARCHIVE.replace("viirs-snpp", f"viirs-{sat}").format(y=year, c=country), timeout=600)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    with open(p + ".part", "wb") as f:
        f.write(body)
    os.replace(p + ".part", p)
    return p


def rows(path_, skip_low=False):
    """Detections of one archive file as tuples (lat, lon, date, hhmm, frp, daynight, type, bright_ti4). skip_low drops
    low-confidence detections, as the live map does (osint.parse_firms)."""
    with open(path_, newline="", encoding="utf-8", errors="replace") as f:
        head = f.readline().strip().split(",")
        ix = {h: k for k, h in enumerate(head)}
        cf = ix.get("confidence")
        la, lo, d, t, fr, dn, ty, b4 = (ix["latitude"], ix["longitude"], ix["acq_date"], ix["acq_time"], ix["frp"], ix.get("daynight"), ix.get("type"),
                                        ix.get("bright_ti4"))
        for line in f:
            r = line.rstrip("\r\n").split(",")
            if skip_low and cf is not None and cf < len(r) and r[cf].lower() == "l":
                continue
            try:
                yield (float(r[la]), float(r[lo]), r[d], r[t].zfill(4), float(r[fr] or 0), r[dn] if dn is not None else "",
                       int(r[ty]) if ty is not None and r[ty] != "" else 0, float(r[b4] or 0) if b4 is not None else 0.0)
            except (ValueError, IndexError):
                continue


def boxes_for(box_names):
    """[(name, (la0, la1, lo0, lo1))] and {country: [box names]}."""
    by_c = {}
    for b in box_names:
        for c in C.FIRE_COUNTRIES[b]:
            by_c.setdefault(c, []).append(b)
    return [(b, C.FIRMS_BOX[b]) for b in box_names], by_c


def inside(box, lat, lon):
    la0, la1, lo0, lo1 = box
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


# ---------------------------------------------------------------- reduction
def frp_pct(hist, q):
    """Approximate quantile from a histogram over FRP_EDGES (linear within the bin)."""
    n = sum(hist)
    if not n:
        return 0.0
    want, acc = q * n, 0
    for k, c in enumerate(hist):
        if acc + c >= want and c:
            lo = FRP_EDGES[k]
            hi = FRP_EDGES[k + 1] if k + 1 < len(FRP_EDGES) else FRP_EDGES[-1] * 2
            return lo + (hi - lo) * (want - acc) / c
        acc += c
    return float(FRP_EDGES[-1])


def frp_bin(v):
    return max(0, bisect.bisect_right(FRP_EDGES, v) - 1)


def count_pct(hist, q):
    """Quantile of a histogram of per-day detection counts (index = count, last bin = that many or more)."""
    n = sum(hist)
    if not n:
        return 0.0
    want, acc = q * n, 0
    for k, c in enumerate(hist):
        acc += c
        if acc >= want:
            return float(k)
    return float(len(hist) - 1)


class Acc:
    """Accumulates one box over the archive. First pass: days per cell and year, NASA types, month masks, first years.
    Second pass (notable cells only): FRP and detections-per-day distributions, last date seen."""

    def __init__(self, name, box):
        self.name, self.box = name, box
        self.i0, self.j0, self.rows, self.cols = F.grid_dims(name)
        self.ymask = array.array("H", bytes(2 * self.rows * self.cols))   # per cell: bit k = burned in 2012 + k
        self.days = {}        # (i, j) -> {year: days}
        self.types = {}       # (i, j) -> [t1, t2, t3]
        self.coarse = {}      # (I, J) -> {year: month mask}
        self._year = None
        self.notable = None
        self.frp = {}
        self.per_day = {}
        self.last = {}

    # pass 1
    def start_year(self, y):
        self._year, self._dayset, self._months, self._typed = y, set(), {}, set()

    def add(self, lat, lon, date, frp, typ):
        i, j = F.fine(lat, lon)
        doy = date[5:]
        self._dayset.add((i, j, doy))
        m = self._months.get((i, j))
        bit = 1 << (int(date[5:7]) - 1)
        if m is None:
            I, J = F.coarse(lat, lon)
            self._months[(i, j)] = [bit, I, J]
        else:
            m[0] |= bit
        if typ in (1, 2, 3):
            t = self.types.setdefault((i, j), [0, 0, 0])
            t[typ - 1] += 1
            self._typed.add((i, j))

    def end_year(self):
        y = self._year
        per = {}
        for i, j, _ in self._dayset:
            per[(i, j)] = per.get((i, j), 0) + 1
        for c, n in per.items():
            self.days.setdefault(c, {})[y] = n
            r, k = c[0] - self.i0, c[1] - self.j0
            if 0 <= r < self.rows and 0 <= k < self.cols:
                self.ymask[r * self.cols + k] |= 1 << (y - F.Y0)
        for c, (mask, I, J) in self._months.items():
            if per.get(c, 0) >= KEEP_STATIC_DAYS or c in self._typed:
                continue         # flares, plants, volcanoes and offshore heat do not make an area "seasonal"
            cm = self.coarse.setdefault((I, J), {})
            cm[y] = cm.get(y, 0) | mask
        self._dayset = self._months = self._typed = None

    def pick_notable(self):
        self.notable = {c for c, d in self.days.items() if max(d.values()) >= NOTABLE_DAYS}
        self.notable |= {c for c, t in self.types.items() if sum(t) >= NOTABLE_TYPES}
        return self.notable

    # pass 2
    def start_year2(self):
        self._cnt = {}

    def add2(self, lat, lon, date, frp):
        c = F.fine(lat, lon)
        if c not in self.notable:
            return
        h = self.frp.get(c)
        if h is None:
            h = self.frp[c] = [0] * len(FRP_EDGES) + [0.0]     # last slot: max FRP
        h[frp_bin(frp)] += 1
        h[-1] = max(h[-1], frp)
        k = (c, date)
        self._cnt[k] = self._cnt.get(k, 0) + 1
        if date > self.last.get(c, ""):
            self.last[c] = date

    def end_year2(self):
        for (c, _), n in self._cnt.items():
            h = self.per_day.setdefault(c, [0] * 31)
            h[min(n, 30)] += 1
        self._cnt = None

    def tables(self, years):
        cells = {}
        for c in self.notable:
            t = self.types.get(c, [0, 0, 0])
            h = self.frp.get(c, [0] * (len(FRP_EDGES) + 1))
            cells[c] = {"t1": t[0], "t2": t[1], "t3": t[2], "frp95": frp_pct(h[:-1], 0.95), "frpmax": h[-1],
                        "n95": count_pct(self.per_day.get(c, [0] * 31), 0.95), "last": self.last.get(c, ""), "d": self.days.get(c, {})}
        return cells

    def write(self, out_dir, years):
        os.makedirs(out_dir, exist_ok=True)
        cells = self.tables(years)
        with gzip.open(os.path.join(out_dir, f"fire_cells_{self.name}.csv.gz"), "wt", newline="", compresslevel=9) as f:
            F.write_cells(f, cells, years)
        with gzip.open(os.path.join(out_dir, f"fire_coarse_{self.name}.csv.gz"), "wt", newline="", compresslevel=9) as f:
            F.write_coarse(f, self.coarse, years)
        with gzip.open(os.path.join(out_dir, f"fire_years_{self.name}.bin.gz"), "wb", compresslevel=9) as f:
            f.write(F.write_grid(self.i0, self.j0, self.rows, self.cols, self.ymask))
        sizes = {k: os.path.getsize(os.path.join(out_dir, f"fire_{k}_{self.name}" + (".bin.gz" if k == "years" else ".csv.gz"))) for k in ("cells", "coarse", "years")}
        log(f"{self.name}: {len(cells)} notable cells, {len(self.coarse)} coarse cells, {sum(1 for v in self.ymask if v)} cells ever burned; bytes {sizes}")


def years_arg(s):
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def build(box_names, years, cache, out_dir=F.DATA):
    boxes, by_c = boxes_for(box_names)
    acc = {b: Acc(b, box) for b, box in boxes}
    have = []
    for y in years:
        for a in acc.values():
            a.start_year(y)
        got = 0
        for c, bs in sorted(by_c.items()):
            p = archive_file(c, y, cache)
            if not p:
                log(f"{y} {c}: no file")
                continue
            got += 1
            n = 0
            targets = [(acc[b], acc[b].box) for b in bs]
            for lat, lon, date, _, frp, _, typ, _ in rows(p):
                for a, box in targets:
                    if inside(box, lat, lon):
                        a.add(lat, lon, date, frp, typ)
                        n += 1
            log(f"{y} {c}: {n} detections in boxes")
        for a in acc.values():
            a.end_year()
        if got:
            have.append(y)
    for a in acc.values():
        log(a.name, "notable cells:", len(a.pick_notable()))
    for y in have:
        for a in acc.values():
            a.start_year2()
        for c, bs in sorted(by_c.items()):
            p = archive_file(c, y, cache)
            if not p:
                continue
            targets = [(acc[b], acc[b].box) for b in bs]
            for lat, lon, date, _, frp, _, _, _ in rows(p):
                for a, box in targets:
                    if inside(box, lat, lon):
                        a.add2(lat, lon, date, frp)
        for a in acc.values():
            a.end_year2()
        log(f"{y}: second pass done")
    for a in acc.values():
        a.write(out_dir, have)


# ---------------------------------------------------------------- sites
GROUPS = [   # osmsource groups (key, values, extra tags); osm_kind() sorts each element into a site kind
    ("man_made", ["flare", "works", "offshore_platform"], ["product"]),
    ("industrial", ["refinery", "oil", "gas", "petrochemical", "oil_refinery", "steelmaker", "steel", "steel_mill", "cement", "port"], []),
    ("landuse", ["military", "port"], []),
    ("military", ["airfield", "base", "naval_base", "barracks", "range"], []),
    ("aeroway", ["aerodrome"], []),
    ("power", ["plant", "substation"], ["plant:source", "voltage"]),
]
TANKS = [("man_made", ["storage_tank"], ["content", "substance"])]   # the heaviest tag: its own query
FUEL_WORDS = ("oil", "fuel", "gas", "petrol", "diesel", "crude", "kerosene", "lpg", "lng", "naphtha")


def osm_kind(t):
    """Site kind for an OSM element's tags, or None. Mirrors TAGS (one union query per tile, sorted here)."""
    g = lambda k: (t.get(k) or "").lower()
    if g("man_made") == "flare":
        return "flare"
    if g("man_made") == "offshore_platform":
        return "platform"
    if g("industrial") in ("refinery", "oil", "gas", "petrochemical", "oil_refinery") or (g("man_made") == "works" and re.search("oil|gas|petrol", g("product"))):
        return "oilgas"
    if g("industrial") in ("steelmaker", "steel", "steel_mill") or (g("man_made") == "works" and re.search("steel|iron", g("product"))):
        return "steel"
    if g("power") == "plant" and re.search("gas|oil|coal|diesel", g("plant:source")):
        return "power"
    if g("industrial") == "cement" or (g("man_made") == "works" and "cement" in g("product")):
        return "cement"
    if g("military") in ("airfield", "base", "naval_base", "barracks", "range") or g("landuse") == "military":
        return "military"
    if g("aeroway") == "aerodrome":
        return "airfield"
    if g("industrial") == "port" or g("landuse") == "port":
        return "port"
    if g("man_made") == "storage_tank":
        return "fuel"
    if g("power") == "substation":
        v = re.findall(r"\d+", g("voltage"))
        return "substation" if v and max(int(x) for x in v) >= 220000 else None
    return None


def osm_sites(box):
    """All site kinds for a box from OpenStreetMap -> (sites, failed groups). With osmium installed (fireref.yml) they come
    from Geofabrik's extracts in one pass; otherwise from osmsource's query services (QLever, Overpass as fallback), with
    storage tanks as their own query. A failed group does not lose the one that worked."""
    out, failed = [], []
    if O.geofabrik_ready():
        try:
            jobs = [("all", O.geofabrik_points(GROUPS + TANKS, box))]
        except Exception as e:
            log(f"  geofabrik failed: {str(e)[:160]}")
            return [], [(box, "other"), (box, "fuel")]
    else:
        jobs = [("other", GROUPS), ("fuel", TANKS)]
    for name, groups in jobs:
        try:
            pts = groups if name == "all" else O.points(groups, box)
        except Exception as e:
            log(f"  {name} failed: {str(e)[:120]}")
            failed.append((box, name))
            continue
        n = 0
        for p in pts:
            t = p["tags"]
            kind = osm_kind(t)
            if kind is None:
                continue
            n += 1
            out.append({"id": p["id"], "name": (t.get("name:en") or t.get("name") or "")[:80], "kind": kind, "lat": p["lat"], "lon": p["lon"],
                        "src": "osm", "content": (t.get("content", "") + " " + t.get("substance", "")).lower()})
        log(f"  {name}: {len(pts)} elements, {n} sites")
    return merge_tanks(out), failed


def merge_tanks(sites, r_km=0.4, min_untagged=5):
    """Storage tanks closer than 400 m become one fuel site at their mean position. Tagged fuel tanks always count; a
    cluster of untagged tanks counts when it has at least `min_untagged` of them."""
    tanks = [s for s in sites if s["kind"] == "fuel"]
    rest = [s for s in sites if s["kind"] != "fuel"]
    cell = 0.01
    groups, grid = [], {}
    for s in sorted(tanks, key=lambda s: (s["lat"], s["lon"])):
        bi, bj = int(s["lat"] // cell), int(s["lon"] // cell)
        hit = None
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                for g in grid.get((bi + a, bj + b), ()):
                    if F.km(s["lat"], s["lon"], g["lat"], g["lon"]) <= r_km:
                        hit = g
                        break
                if hit:
                    break
            if hit:
                break
        fuel = any(w in s.get("content", "") for w in FUEL_WORDS)
        if hit:
            hit["n"] += 1
            hit["lat"] += (s["lat"] - hit["lat"]) / hit["n"]
            hit["lon"] += (s["lon"] - hit["lon"]) / hit["n"]
            hit["fuel"] = hit["fuel"] or fuel
            hit["name"] = hit["name"] or s["name"]
        else:
            g = dict(s, n=1, fuel=fuel)
            groups.append(g)
            grid.setdefault((bi, bj), []).append(g)
    for g in groups:
        if g["fuel"] or g["n"] >= min_untagged:
            rest.append({"id": g["id"], "name": g["name"] or "Fuel tanks", "kind": "fuel", "lat": g["lat"], "lon": g["lon"], "src": "osm"})
    return rest


def xlsx_sheets(body):
    """Numbers of the worksheets in an xlsx (sheet1.xml, sheet2.xml, ...), in order."""
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    return sorted(int(m.group(1)) for n in names for m in [re.match(r"xl/worksheets/sheet(\d+)\.xml$", n)] if m)


def xlsx_rows(body, sheet=1):
    """One sheet of an xlsx (the first by default) as lists of cell values (strings or floats). Standard library only."""
    z = zipfile.ZipFile(io.BytesIO(body))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        x = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        for si in re.findall(r"<si>(.*?)</si>", x, re.S):
            ss.append("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si)).replace("&amp;", "&").strip())
    sheet = z.read(f"xl/worksheets/sheet{sheet}.xml").decode("utf-8", "replace")
    out = []
    for row in re.finditer(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        vals = {}
        for m in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row.group(1), re.S):
            col, attrs, inner = m.group(1), m.group(2), m.group(3) or ""
            if 't="inlineStr"' in attrs:
                vals[col] = "".join(re.findall(r"<t[^>]*>([^<]*)</t>", inner)).replace("&amp;", "&").strip()
                continue
            v = re.search(r"<v>([^<]*)</v>", inner)
            if not v:
                continue
            v = v.group(1)
            vals[col] = ss[int(v)] if 't="s"' in attrs else (float(v) if re.match(r"^-?[\d.eE+-]+$", v) else v)
        if vals:
            width = max(_colnum(c) for c in vals) + 1
            out.append([vals.get(_colname(k), "") for k in range(width)])
    return out


def _colnum(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _colname(k):
    s = ""
    k += 1
    while k:
        k, r = divmod(k - 1, 26)
        s = chr(65 + r) + s
    return s


def ggfr_sites(boxes):
    rows_ = xlsx_rows(get(GGFR, timeout=300))
    head = [str(h).strip().lower() for h in rows_[0]]
    ix = {h: k for k, h in enumerate(head)}
    la, lo, yr, fld = ix["latitude"], ix["longitude"], ix["year"], ix.get("field name")
    best = {}
    for r in rows_[1:]:
        try:
            lat, lon, y = float(r[la]), float(r[lo]), int(float(r[yr]))
        except (ValueError, IndexError, TypeError):
            continue
        if not any(inside(b, lat, lon) for b in boxes):
            continue
        k = (round(lat / 0.005), round(lon / 0.005))
        if k not in best or y > best[k][2]:
            name = str(r[fld]).strip() if fld is not None and fld < len(r) else ""
            best[k] = (lat, lon, y, name)
    return [{"id": f"ggfr:{k[0]}_{k[1]}", "name": (f"{n} field" if n and n.upper() != "NA" else ""), "kind": "flare", "lat": a, "lon": b, "src": "ggfr"}
            for k, (a, b, _, n) in best.items()]


def wri_sites(boxes):
    out = []
    for r in csv.DictReader(io.StringIO(get(WRI, timeout=300).decode("utf-8", "replace"))):
        try:
            lat, lon, cap = float(r["latitude"]), float(r["longitude"]), float(r["capacity_mw"] or 0)
        except ValueError:
            continue
        if r["primary_fuel"] in ("Gas", "Oil", "Coal", "Petcoke") and cap >= 50 and any(inside(b, lat, lon) for b in boxes):
            out.append({"id": f"wri:{r['gppd_idnr']}", "name": r["name"][:80], "kind": "power", "lat": lat, "lon": lon, "src": "wri"})
    return out


def gem_sites(boxes, raw=os.path.join(F.DATA, "raw")):
    """Optional Global Energy Monitor tracker files the owner downloads by hand (free form) into data/raw/gem_*.csv|xlsx.

    None when there are no such files (as on the GitHub runner), so sites() keeps the GEM rows already in fire_sites.csv."""
    out = []
    try:
        names = sorted(n for n in os.listdir(raw) if n.startswith("gem_"))
    except OSError:
        names = []
    if not names:
        return None
    for n in names:
        body = open(os.path.join(raw, n), "rb").read()
        tabs = ([xlsx_rows(body, k) for k in xlsx_sheets(body)] if n.endswith(".xlsx")
                else [list(csv.reader(io.StringIO(body.decode("utf-8", "replace"))))])
        kind = "steel" if "steel" in n else "cement" if "cement" in n else "power" if ("coal" in n or "power" in n) else "oilgas"
        got = 0
        for tab in tabs:   # GEM workbooks open with an "About" sheet; use every sheet that has coordinates
            if not tab:
                continue
            head = [str(h).strip().lower() for h in tab[0]]
            col = lambda *hs: next((head.index(h) for h in hs if h in head), None)
            la, lo, xy = col("latitude"), col("longitude"), col("coordinates")
            if (la is None or lo is None) and xy is None:
                continue
            nm = col("plant name", "plant name (english)", "terminalname", "project name", "unit name", "name")
            st = col("status", "operating status")
            off = col("onshore/offshore")
            for r in tab[1:]:
                cell = lambda c: str(r[c]).strip() if c is not None and c < len(r) else ""
                try:
                    lat, lon = (float(r[la]), float(r[lo])) if la is not None else map(float, cell(xy).split(","))
                except (ValueError, IndexError, TypeError):
                    continue
                status = cell(st).lower()
                if status not in ("", "unknown") and not re.search("operat|construct|storage", status):
                    continue   # cancelled, retired, mothballed, proposed and undeveloped sites do not burn
                if any(inside(b, lat, lon) for b in boxes):
                    k = "platform" if kind == "oilgas" and cell(off).lower() == "offshore" else kind
                    out.append({"id": f"gem:{n}:{len(out)}", "name": cell(nm)[:80], "kind": k, "lat": lat, "lon": lon, "src": "gem"})
                    got += 1
        if not got:
            log("GEM file with no usable rows (no Latitude/Longitude or Coordinates column, or none in the boxes):", n)
    return out


def write_sites(sites, p=os.path.join(F.DATA, "fire_sites.csv")):
    seen, keep = set(), []
    for s in sites:
        k = (s["kind"], round(s["lat"], 4), round(s["lon"], 4))
        if k not in seen:
            seen.add(k)
            keep.append(s)
    with open(p, "w", newline="", encoding="utf-8") as f:
        f.write(SITE_HEADER)
        w = csv.writer(f, lineterminator="\n")
        w.writerow(F.SITE_COLS)
        for s in sorted(keep, key=lambda s: (s["kind"], s["lat"], s["lon"])):
            w.writerow([s["id"], s["name"].replace("\n", " "), s["kind"], f"{s['lat']:.5f}", f"{s['lon']:.5f}", s["src"]])
    return keep


def sites(box_names, osm=True):
    boxes = [C.FIRMS_BOX[b] for b in box_names]
    old = []
    try:
        with open(os.path.join(F.DATA, "fire_sites.csv"), newline="", encoding="utf-8") as f:
            old = [dict(r, lat=float(r["lat"]), lon=float(r["lon"])) for r in csv.DictReader(l for l in f if not l.startswith("#"))]
    except OSError:
        pass
    # keep rows outside the boxes rebuilt now, so one box can be refreshed at a time
    out = [s for s in old if not any(inside(b, s["lat"], s["lon"]) for b in boxes)]
    for name, fn in (("ggfr", ggfr_sites), ("wri", wri_sites), ("gem", gem_sites)):
        try:
            got = fn(boxes)
            if got is None:
                got = [s for s in old if s.get("src") == name and any(inside(b, s["lat"], s["lon"]) for b in boxes)]
                log(name, "no source files; kept", len(got), "earlier rows")
            else:
                log(name, len(got))
            out += got
        except Exception as e:
            log(name, "failed:", str(e)[:160])
            out += [s for s in old if s.get("src") == name and any(inside(b, s["lat"], s["lon"]) for b in boxes)]
    if osm:
        for b in box_names:
            log("osm", b)
            got, failed = osm_sites(C.FIRMS_BOX[b])
            out += got
            # keep earlier OSM rows inside the tiles that failed this time (fuel tiles keep fuel sites, other tiles the rest)
            for (la0, la1, lo0, lo1), grp in failed:
                out += [s for s in old if s.get("src") == "osm" and la0 <= s["lat"] <= la1 and lo0 <= s["lon"] <= lo1
                        and (s["kind"] == "fuel") == (grp == "fuel")]
            log("osm", b, len(got), "sites,", len(failed), "tiles failed")
            write_sites(out + [s for s in old if s.get("src") == "osm" and any(inside(C.FIRMS_BOX[x], s["lat"], s["lon"]) for x in box_names[box_names.index(b) + 1:])])
    else:   # --no-osm: refresh GGFR, WRI and GEM only, and keep the OpenStreetMap rows already in the list
        out += [s for s in old if s.get("src") == "osm" and any(inside(b, s["lat"], s["lon"]) for b in boxes)]
    keep = write_sites(out)
    by = {}
    for s in keep:
        by[s["kind"]] = by.get(s["kind"], 0) + 1
    log("sites written:", len(keep), dict(sorted(by.items())))


def osm_part(box, path):
    """One box's OpenStreetMap sites to a CSV (for parallel runner jobs); failed tiles are listed in the log."""
    got, failed = osm_sites(C.FIRMS_BOX[box])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(F.SITE_COLS)
        for s_ in got:
            w.writerow([s_["id"], s_["name"].replace("\n", " "), s_["kind"], f"{s_['lat']:.5f}", f"{s_['lon']:.5f}", "osm"])
    log(box, len(got), "OSM sites,", len(failed), "tiles failed:", failed)


def merge_osm(paths):
    """fire_sites.csv = the current non-OSM rows (GGFR, WRI, GEM) + the OSM parts; boxes without a part keep their old OSM rows."""
    try:
        with open(os.path.join(F.DATA, "fire_sites.csv"), newline="", encoding="utf-8") as f:
            old = [dict(r, lat=float(r["lat"]), lon=float(r["lon"])) for r in csv.DictReader(l for l in f if not l.startswith("#"))]
    except OSError:
        old = []
    out = [r for r in old if r.get("src") != "osm"]
    covered = set()
    for p in paths:
        box = os.path.basename(p).split("osm_")[-1].rsplit(".", 1)[0]
        covered.add(box)
        with open(p, newline="", encoding="utf-8") as f:
            out += [dict(r, lat=float(r["lat"]), lon=float(r["lon"])) for r in csv.DictReader(f)]
    out += [r for r in old if r.get("src") == "osm" and not any(inside(C.FIRMS_BOX[b], r["lat"], r["lon"]) for b in covered)]
    keep = write_sites(out)
    by = {}
    for r in keep:
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    log("sites written:", len(keep), dict(sorted(by.items())))


# ---------------------------------------------------------------- checks
CHECKS = [   # name, box, lat, lon, expect routine (True) or not (False); static checks search the nearest static cell within 3 km
    ("Baba Gurgur flame, Kirkuk", "iran", 35.535, 44.358, True),
    ("Rumaila field flares, Basra", "iran", 30.36, 47.34, True),
    ("South Pars / Assaluyeh flares", "iran", 27.48, 52.61, True),
    ("Isfahan city centre", "iran", 32.655, 51.668, False),
    ("Tehran city centre", "iran", 35.700, 51.400, False),
    ("Kyiv city centre", "ukraine", 50.450, 30.523, False),
]


def check():
    log(f"{'place':34} {'box':8} {'static cell within 3 km':24} expected")
    bad = 0
    for name, box, la, lo, want in CHECKS:
        ref = F.load(box)
        if ref is None:
            log(f"{name:34} {box:8} no reference tables")
            bad += 1
            continue
        i, j = F.fine(la, lo)
        found = None
        for a in range(-3, 4):
            for b in range(-3, 4):
                r = ref.cells.get((i + a, j + b))
                if r and F.static_row(r, dt.date.today().year):
                    d = F.km(la, lo, (i + a) * F.FINE, (j + b) * F.FINE)
                    if found is None or d < found[0]:
                        found = (d, r)
        got = found is not None
        ok = got == want
        bad += not ok
        log(f"{name:34} {box:8} {('yes, %.1f km t2=%d' % (found[0], found[1]['t2'])) if got else 'no':24} {'static' if want else 'not static'}  {'OK' if ok else 'CHECK'}")
    return bad


# ---------------------------------------------------------------- replay (FIRECLASS F4)
def replay(box_names, start, years, cache, out_dir=None):
    """Classifies every archive detection from `start` day by day with firecls (which only uses reference years before each
    day's year) and writes the daily count of anom + hot to backfill/data/firecls/firms_anom_<box>.csv, plus the daily count per class."""
    out_dir = out_dir or F.REPLAY_DIR    # a subfolder, so the studies that glob backfill/data/*.csv do not pick these up
    boxes, by_c = boxes_for(box_names)
    for b, box in boxes:
        ref = F.load(b)
        if ref is None:
            log(b, "has no reference tables; run build first")
            continue
        counts = {}
        for y in [y for y in years if y >= int(start[:4])]:
            by_day = {}
            for c in C.FIRE_COUNTRIES[b]:
                p = archive_file(c, y, cache)
                if not p:
                    continue
                for lat, lon, date, hhmm, frp, dn, _, b4 in rows(p, skip_low=True):
                    if date >= start and inside(box, lat, lon):
                        by_day.setdefault(date, []).append({"lat": lat, "lon": lon, "date": date, "ts": f"{date}T{hhmm[:2]}:{hhmm[2:]}Z", "frp": frp,
                                                            "daynight": dn, "bright_ti4": b4})
            for date in sorted(by_day):
                pts = F.classify(by_day[date], b, ref=ref)
                k = counts.setdefault(date, {})
                for p in pts:
                    k[p["c"]] = k.get(p["c"], 0) + 1
                    if p["c"] in F.ANOMALY and (p.get("esite") or p["c"] == "hot"):
                        k["esite"] = k.get("esite", 0) + 1      # unusual at an energy or industrial site (map rule of 2026-10-17)
            log(b, y, "days", len(by_day))
        os.makedirs(out_dir, exist_ok=True)
        if not counts:
            continue
        d0, d1 = dt.date.fromisoformat(min(counts)), dt.date.fromisoformat(max(counts))
        days = [(d0 + dt.timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]
        with open(os.path.join(out_dir, f"firms_anom_{b}.csv"), "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            for d in days:
                k = counts.get(d, {})
                w.writerow([d, k.get("anom", 0) + k.get("hot", 0)])
        cls = ["anom", "hot", "unex", "seas", "ind", "volc", "off", "esite"]
        with open(os.path.join(out_dir, f"firms_cls_{b}.csv"), "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["date"] + cls)
            for d in days:
                w.writerow([d] + [counts.get(d, {}).get(c, 0) for c in cls])
        log(b, "replay written:", len(days), "days")


# ---------------------------------------------------------------- case checks (FIRECLASS F4)
def cases(cache, path=os.path.join(F.DATA, "fire_cases.csv")):
    """For each case in data/fire_cases.csv: classify that day's archive detections in the box and report the classes found
    within 3 km of the place. -> [(case row, [(class, score, frp, reason)])]."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        rows_ = list(csv.DictReader(f))
    for r in rows_:
        la, lo, box, day = float(r["lat"]), float(r["lon"]), r["box"], r["date"]
        y = int(day[:4])
        pts = []
        for c in C.FIRE_COUNTRIES[box]:
            p = archive_file(c, y, cache)
            if not p:
                continue
            for lat, lon, date, hhmm, frp, dn, _, b4 in rows(p, skip_low=True):
                if date == day and inside(C.FIRMS_BOX[box], lat, lon):
                    pts.append({"lat": lat, "lon": lon, "date": date, "ts": f"{date}T{hhmm[:2]}:{hhmm[2:]}Z", "frp": frp, "daynight": dn, "bright_ti4": b4})
        F.classify(pts, box)
        near = sorted(((p["c"], p["a"], p["frp"], p["why"]) for p in pts if F.km(la, lo, p["lat"], p["lon"]) <= 3.0), key=lambda x: -x[1])
        ok = any(c in r["expect"].split("|") for c, *_ in near)
        log(f"{r['date']} {r['name'][:50]:50} expect {r['expect']:9} got {sorted({c for c, *_ in near}) or 'no detection'} {'OK' if ok else 'CHECK'}")
        for c, a, frp, why in near[:2]:
            log(f"    {c} {a} {frp:.0f} MW  {why[:150]}")
        out.append((r, near))
    return out


# ---------------------------------------------------------------- energy-site tuning (2026-10-17, docs/FIRE_ENERGY_TUNING.md)
SATS = ("snpp", "noaa20", "noaa21")
TUNE_CASES = os.path.join(F.DATA, "fire_energy_cases.csv")
CALM_YEARS = (2018, 2019, 2020, 2021)
GRID = {"usual_days": (0, 5, 10, 20, 40, 80), "site": (25, 30, 35), "similar": ((2.0, 20), (1.5, 10), (99, 0)),
        "hot": ((3.0, 100), (2.0, 50)), "energy_sens": (0, 1)}


def _energy_index():
    kinds = F.INDUSTRIAL + F.ENERGY
    return F.Sites([s for s in F.load_sites() if s["kind"] in kinds]), kinds


def tune_points(cases, cache, log_=None):
    """Detections the tuning needs, from all three VIIRS satellites: around each case on its day and the next, and within 4 km
    of an energy or industrial site on every day of the calm years (case days +-3 left out)."""
    idx, kinds = _energy_index()
    days = {}
    for k, c in enumerate(cases):
        d = dt.date.fromisoformat(c["date"])
        for x in (d, d + dt.timedelta(1)):
            days.setdefault((c["box"], x.isoformat()), []).append(k)
    skip = {(c["box"], (dt.date.fromisoformat(c["date"]) + dt.timedelta(k)).isoformat()) for c in cases for k in range(-3, 4)}
    years = sorted(set(CALM_YEARS) | {int(c["date"][:4]) for c in cases})
    case_pts = {k: [] for k in range(len(cases))}
    calm = {}
    for y in years:
        for b in sorted({c["box"] for c in cases}):      # the boxes with cases; their calm years give the false alarms
            box = C.FIRMS_BOX[b]
            for sat in SATS:
                for ctry in C.FIRE_COUNTRIES[b]:
                    p = archive_file(ctry, y, cache, sat)
                    if not p:
                        continue
                    for lat, lon, date, hhmm, frp, dn, _, b4 in rows(p, skip_low=True):
                        if not inside(box, lat, lon):
                            continue
                        pt = None
                        for k in days.get((b, date), ()):
                            c = cases[k]
                            if F.km(lat, lon, float(c["lat"]), float(c["lon"])) <= 6.0:
                                pt = pt or {"lat": lat, "lon": lon, "date": date, "ts": f"{date}T{hhmm[:2]}:{hhmm[2:]}Z|{sat}", "frp": frp, "daynight": dn, "bright_ti4": b4}
                                case_pts[k].append(pt)
                        if y in CALM_YEARS and (b, date) not in skip and idx.near(lat, lon, kinds, 4.0)[0]:
                            pt = pt or {"lat": lat, "lon": lon, "date": date, "ts": f"{date}T{hhmm[:2]}:{hhmm[2:]}Z|{sat}", "frp": frp, "daynight": dn, "bright_ti4": b4}
                            calm.setdefault((b, date), []).append(pt)
            (log_ or log)(y, b, "case points", sum(len(v) for v in case_pts.values()), "calm days", len(calm))
    # same-pass neighbours are counted once on the wide set; only the points that can count are kept
    for k, pts in case_pts.items():
        n = F._same_pass(pts)
        c = cases[k]
        case_pts[k] = [dict(p, _n=n[id(p)]) for p in pts if F.km(float(c["lat"]), float(c["lon"]), p["lat"], p["lon"]) <= 3.0]
    for key, pts in list(calm.items()):
        n = F._same_pass(pts)
        calm[key] = [dict(p, _n=n[id(p)]) for p in pts if idx.near(p["lat"], p["lon"], kinds, 2.0)[0]]
    return case_pts, calm


def _classify_raw(pts, ref):
    for p in pts:
        F.classify_one(p, ref, p["_n"], dt.date.fromisoformat(p["date"]))
    return pts


class _MemoSites:
    """The site lookups of one box, remembered across the settings of the grid (the sites do not change between them)."""
    def __init__(self, sites):
        self.s, self.m, self.b = sites, {}, sites.b

    def near(self, lat, lon, kinds, r_km):
        k = (lat, lon, kinds, r_km)
        if k not in self.m:
            self.m[k] = self.s.near(lat, lon, kinds, r_km)
        return self.m[k]


def tune_score(cases, case_pts, calm, refs, setting):
    """-> (case hits, cases seen, calm flags per year, [(case, best class, score)]) for one setting of the energy rule."""
    old = dict(F.W)
    F.W.update(setting)
    try:
        hits, seen, detail = 0, 0, []
        for k, c in enumerate(cases):
            la, lo = float(c["lat"]), float(c["lon"])
            pts = [dict(p) for p in case_pts[k]]
            _classify_raw(pts, refs[c["box"]])
            near = pts
            seen += bool(near)
            best = max(near, key=lambda p: (p["c"] in F.ANOMALY, p["a"]), default=None)
            hit = bool(best and best["c"] in F.ANOMALY)
            hits += hit
            detail.append((c, best["c"] if best else "none", best["a"] if best else 0))
        flags = set()
        for (b, date), pts in calm.items():
            pts = [dict(p) for p in pts]
            _classify_raw(pts, refs[b])
            for p in pts:
                if p["c"] in F.ANOMALY:
                    flags.add((b, date, round(p["lat"] / 0.02), round(p["lon"] / 0.02)))
        return hits, seen, len(flags) / len(CALM_YEARS), detail
    finally:
        F.W.clear()
        F.W.update(old)


def tune(cache, out=None):
    with open(TUNE_CASES, newline="", encoding="utf-8") as f:
        cases = [r for r in csv.DictReader(f) if r["box"] in C.FIRMS_BOX]
    refs = {b: F.load(b) for b in C.FIRMS_BOX}
    for r in refs.values():
        r.ceiling("power")                  # fills the similar-plant table before the lookups are wrapped
        r.sites = _MemoSites(r.sites)
    case_pts, calm = tune_points(cases, cache)
    res = []
    import itertools
    for ud, sw, (sx, sa), (hx, ha), es in itertools.product(GRID["usual_days"], GRID["site"], GRID["similar"], GRID["hot"], GRID["energy_sens"]):
        st = {"usual_days": ud, "site": sw, "similar_x": sx, "similar_add": sa, "hot_x": hx, "hot_add": ha, "energy_sens": es}
        h, s, fl, det = tune_score(cases, case_pts, calm, refs, st)
        res.append((st, h, s, fl, det))
        log(f"usual_days {ud:3} site {sw} similar {sx}x+{sa} hot {hx}x+{ha} energy_sens {es}: hits {h}/{len(cases)} (seen {s}), calm flags/yr {fl:.0f}")
    with open(out or os.path.join(os.path.dirname(HERE), "backtest", "fire_energy_tuning.json"), "w") as f:
        json.dump({"cases": len(cases), "runs": [{"setting": st, "hits": h, "seen": s, "calm_flags_per_year": fl,
                                                   "detail": [[c["date"], c["name"], cl, a] for c, cl, a in det]} for st, h, s, fl, det in res]}, f, indent=1)
    return res


# ---------------------------------------------------------------- probe
def probe():
    bad = 0
    for c in sorted({c for v in C.FIRE_COUNTRIES.values() for c in v}):
        try:
            h = get(ARCHIVE.format(y=2024, c=c), headers={"Range": "bytes=0-300"}, tries=2).decode("utf-8", "replace").splitlines()[0]
            ok = all(k in h for k in ("latitude", "acq_date", "frp", "daynight", "type"))
            log(f"{c}: {'OK' if ok else 'columns missing: ' + h}")
            bad += not ok
        except Exception as e:
            log(f"{c}: FAIL {e}")
            bad += 1
    for name, url in (("GGFR", GGFR), ("WRI", WRI)):
        try:
            get(url, headers={"Range": "bytes=0-100"}, tries=2)
            log(name, "OK")
        except Exception as e:
            log(name, "FAIL", e)
            bad += 1
    try:
        n = sum(1 for e in O.shapes(25.117, 51.315, 4.0, [("aeroway", ["apron"], [])]) if e["tags"].get("aeroway") == "apron")
        log("OpenStreetMap (QLever) OK,", n, "aprons at Al Udeid")
    except Exception as e:
        log("OpenStreetMap FAIL", e)
        bad += 1
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "build", "sites", "check", "replay", "econ", "cases", "osm-part", "merge-osm", "tune"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--box", default=",".join(C.FIRMS_BOX))
    ap.add_argument("--years", default=f"2012-{dt.date.today().year - 1}")
    ap.add_argument("--cache", default=os.environ.get("FIRMS_ARCHIVE_CACHE", os.path.join(os.path.dirname(HERE), ".firms_archive")))
    ap.add_argument("--from", dest="start", default="2018-01-01")
    ap.add_argument("--no-osm", action="store_true")
    a = ap.parse_args(argv)
    names = [b for b in a.box.split(",") if b in C.FIRMS_BOX]
    if a.cmd == "probe":
        return 1 if probe() else 0
    if a.cmd == "build":
        build(names, years_arg(a.years), a.cache)
    elif a.cmd == "sites":
        sites(names, osm=not a.no_osm)
    elif a.cmd == "check":
        return 1 if check() else 0
    elif a.cmd == "osm-part":
        osm_part(names[0], a.paths[0])
    elif a.cmd == "merge-osm":
        merge_osm(a.paths)
    elif a.cmd == "cases":
        cases(a.cache)
    elif a.cmd == "econ":
        log("Economist war fires, last 21 days:", F.econ_refresh())
    elif a.cmd == "tune":
        tune(a.cache)
    elif a.cmd == "replay":
        replay(names, a.start, years_arg(a.years), a.cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
