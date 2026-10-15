#!/usr/bin/env python3
"""Base registry for the satellite base watch (docs/BASEWATCH_PLAN.md, B1). Standard library only.

    python3 warwatch/basesites.py build     # data/bases_seed.csv + OpenStreetMap outlines -> data/bases.json, docs/BASES_REVIEW.md

For each seed site it asks Overpass for the military or aerodrome outline, the aprons (aeroway=apron) and, for naval
sites, piers and quays. Hand-drawn shapes in data/bases_manual.geojson (properties: id, part = outline|apron|harbour)
replace OSM's for that site and part. OSM data (c) OpenStreetMap contributors, ODbL.
"""
import csv
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fireref  # noqa: E402  (Overpass client with retries across mirrors)

DATA = os.path.join(HERE, "data")
SEED = os.path.join(DATA, "bases_seed.csv")
OUT = os.path.join(DATA, "bases.json")
MANUAL = os.path.join(DATA, "bases_manual.geojson")
REVIEW = os.path.join(os.path.dirname(HERE), "docs", "BASES_REVIEW.md")
SRC = "OpenStreetMap contributors (ODbL)"


def seeds(path=SEED):
    with open(path, newline="", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
            r["theatres"] = [t for t in r["theatres"].split(";") if t]
            out.append(r)
        return out


# ---------------------------------------------------------------- geometry (lon/lat rings, local metres)
def _xy(lat0):
    k = math.cos(math.radians(lat0))
    return lambda lo, la: (lo * 111320.0 * k, la * 110540.0)


def area_m2(ring):
    if len(ring) < 3:
        return 0.0
    f = _xy(ring[0][1])
    pts = [f(lo, la) for lo, la in ring]
    return abs(sum(pts[k][0] * pts[k - 1][1] - pts[k - 1][0] * pts[k][1] for k in range(len(pts)))) / 2.0


def centroid(ring):
    n = len(ring) - 1 if ring[0] == ring[-1] else len(ring)
    return sum(p[0] for p in ring[:n]) / n, sum(p[1] for p in ring[:n]) / n


def contains(ring, lon, lat):
    inside = False
    for k in range(len(ring)):
        (x1, y1), (x2, y2) = ring[k - 1], ring[k]
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def simplify(line, tol_m=5.0):
    """Douglas-Peucker in local metres; keeps the first and last points."""
    if len(line) < 4:
        return line
    f = _xy(line[0][1])
    pts = [f(*p) for p in line]

    def rec(a, b):
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, None
        for k in range(a + 1, b):
            d = abs(dy * pts[k][0] - dx * pts[k][1] + x2 * y1 - y2 * x1) / L
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol_m:
            return rec(a, idx)[:-1] + rec(idx, b)
        return [a, b]
    return [[round(line[k][0], 5), round(line[k][1], 5)] for k in rec(0, len(line) - 1)]


def km(la1, lo1, la2, lo2):
    x = math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
    return 6371.0 * math.hypot(x, math.radians(la2 - la1))


# ---------------------------------------------------------------- OSM
def query(s):
    la, lo = s["lat"], s["lon"]
    q = (f"[out:json][timeout:180];("
         f'way["landuse"="military"](around:4000,{la},{lo});relation["landuse"="military"](around:4000,{la},{lo});'
         f'way["military"](around:4000,{la},{lo});relation["military"](around:4000,{la},{lo});'
         f'way["aeroway"="aerodrome"](around:4000,{la},{lo});relation["aeroway"="aerodrome"](around:4000,{la},{lo});'
         f'way["aeroway"="apron"](around:5000,{la},{lo});'
         f'way["man_made"~"^(pier|quay|breakwater)$"](around:3000,{la},{lo});way["landuse"="harbour"](around:3000,{la},{lo});'
         f");out geom tags;")
    return fireref.overpass(q).get("elements", [])


def rings(e):
    """Closed rings (lists of [lon, lat]) of a way or of a relation's outer members."""
    if e["type"] == "way":
        g = [[p["lon"], p["lat"]] for p in e.get("geometry", [])]
        return [g] if len(g) >= 4 and g[0] == g[-1] else []
    out = []
    for m in e.get("members", []):
        if m.get("role") in ("outer", "") and m.get("geometry"):
            g = [[p["lon"], p["lat"]] for p in m["geometry"]]
            if len(g) >= 4 and g[0] == g[-1]:
                out.append(g)
    return out


def pick(s, els):
    """-> dict(outline=[rings], aprons=[rings], piers=[lines], harbour=[rings], ids=[osm ids])."""
    la, lo = s["lat"], s["lon"]
    cand = []
    for e in els:
        t = e.get("tags", {})
        if t.get("landuse") == "military" or t.get("military") or t.get("aeroway") == "aerodrome":
            for r in rings(e):
                cand.append((e, r))
    containing = [(e, r) for e, r in cand if contains(r, lo, la)]
    if containing:
        outline = containing
    else:
        near = sorted(cand, key=lambda x: km(la, lo, centroid(x[1])[1], centroid(x[1])[0]))
        outline = [x for x in near[:1] if km(la, lo, centroid(x[1])[1], centroid(x[1])[0]) <= 3.0]
    # keep the largest rings: a base often has an aerodrome outline and a military one that overlap
    outline = sorted(outline, key=lambda x: -area_m2(x[1]))[:3]
    oring = [r for _, r in outline]
    aprons, piers, harbour = [], [], []
    for e in els:
        t = e.get("tags", {})
        if t.get("aeroway") == "apron":
            for r in rings(e):
                cx, cy = centroid(r)
                if any(contains(o, cx, cy) for o in oring) or (not oring and km(la, lo, cy, cx) <= 3.0):
                    aprons.append(r)
        elif t.get("man_made") in ("pier", "quay", "breakwater") and e["type"] == "way":
            g = [[p["lon"], p["lat"]] for p in e.get("geometry", [])]
            if g and min(km(la, lo, p[1], p[0]) for p in g) <= 2.5:
                piers.append(g)
        elif t.get("landuse") == "harbour":
            harbour += rings(e)
    ids = [f"{e['type'][0]}{e['id']}" for e, _ in outline]
    return {"outline": oring, "aprons": aprons, "piers": piers, "harbour": harbour, "ids": ids}


def manual(path=MANUAL):
    """{(id, part): [geometries]} from the hand-drawn GeoJSON, if any."""
    try:
        with open(path, encoding="utf-8") as f:
            fc = json.load(f)
    except OSError:
        return {}
    out = {}
    for ft in fc.get("features", []):
        p, g = ft.get("properties", {}), ft.get("geometry", {})
        key = (p.get("id"), p.get("part"))
        if g.get("type") == "Polygon":
            out.setdefault(key, []).append(g["coordinates"][0])
        elif g.get("type") == "LineString":
            out.setdefault(key, []).append(g["coordinates"])
    return out


def record(s, got, man):
    for part in ("outline", "aprons", "harbour", "piers"):
        k = (s["id"], part.rstrip("s") if part in ("aprons", "piers") else part)
        if k in man:
            got[part] = man[k]
    aprons = [simplify(r) for r in got["aprons"]]
    rec = {"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "kind": s["kind"], "side": s["side"], "theatres": s["theatres"], "why": s["why"],
           "outline": [simplify(r) for r in got["outline"]], "aprons": aprons, "harbour": [simplify(r) for r in got["harbour"]],
           "piers": [simplify(l) for l in got["piers"]], "apron_m2": round(sum(area_m2(r) for r in got["aprons"])),
           "osm": got.get("ids", []), "src": SRC}
    return rec


def needs_review(r):
    why = []
    if not r["outline"]:
        why.append("no outline")
    if "air" in r["kind"] and not r["aprons"]:
        why.append("no aprons")
    if r["kind"] in ("naval", "air+naval", "port") and not (r["piers"] or r["harbour"]):
        why.append("no piers or harbour")
    return why


def copernicus(lat, lon, zoom=14):
    return (f"https://browser.dataspace.copernicus.eu/?zoom={zoom}&lat={lat:.4f}&lng={lon:.4f}&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS"
            f"&layerId=1_TRUE_COLOR")


def write_review(recs, path=REVIEW):
    lines = ["# Base registry review", "",
             "Built by `python3 warwatch/basesites.py build` from `warwatch/data/bases_seed.csv` and OpenStreetMap. Check each row against the",
             "satellite image (link). Where OSM has no aprons, piers or outline, draw them in `warwatch/data/bases_manual.geojson`",
             "(properties `id` and `part` = outline, apron, harbour or pier) and rebuild. Mark the last column when a row is right.", "",
             "| Site | Kind | Outline polygons | Aprons (count, km²) | Piers / harbour | Flags | Image | OK? |", "|---|---|---|---|---|---|---|---|"]
    for r in recs:
        flags = ", ".join(needs_review(r)) or ""
        lines.append(f"| {r['name']} | {r['kind']} | {len(r['outline'])} | {len(r['aprons'])}, {r['apron_m2'] / 1e6:.2f} | {len(r['piers'])} / {len(r['harbour'])} | {flags} |"
                     f" [Copernicus]({copernicus(r['lat'], r['lon'])}) | |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def build():
    man = manual()
    try:
        with open(OUT, encoding="utf-8") as f:
            old = {r["id"]: r for r in json.load(f)}
    except OSError:
        old = {}
    recs = []
    for s in seeds():
        try:
            got = pick(s, query(s))
            r = record(s, got, man)
            print(s["id"], "outline", len(r["outline"]), "aprons", len(r["aprons"]), f"{r['apron_m2']/1e6:.2f} km2", "piers", len(r["piers"]), flush=True)
        except Exception as e:
            print(s["id"], "OSM failed:", str(e)[:120], "- keeping the old record" if s["id"] in old else "", flush=True)
            if s["id"] not in old:
                continue
            r = dict(old[s["id"]], **{k: s[k] for k in ("name", "lat", "lon", "kind", "side", "theatres", "why")})
        recs.append(r)
        time.sleep(4)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(recs, f, separators=(",", ":"), ensure_ascii=False)
    write_review(recs)
    print("written", len(recs), "sites;", sum(1 for r in recs if needs_review(r)), "need review")


if __name__ == "__main__":
    if sys.argv[1:] != ["build"]:
        print(__doc__)
        sys.exit(2)
    build()
