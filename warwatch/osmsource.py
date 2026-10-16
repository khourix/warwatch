"""OpenStreetMap data for the fire-site gazetteer and the base registry. Standard library only.

Primary source: QLever's OSM planet SPARQL endpoint (University of Freiburg, https://qlever.dev/osm-planet), which answers
bulk questions ("every military area in this box, with its centroid") in seconds. Fallback: Overpass, with small declared
resources. Why not Overpass first (checked 2026-10-15/16):
  - an Overpass server only admits a query when the memory and time it declares are free; queries declaring 1 GB and
    600 s waited and were rejected (500/504) all day while the servers were busy;
  - overpass-api.de closes connections from some cloud ranges after ~7 s; maps.mail.ru cuts any request at ~60 s;
    overpass.kumi.systems answered 500 to everything; overpass.private.coffee only answers small boxes;
  - the ohsome API counts but refuses element extraction (403) to anonymous clients.

Update 2026-10-16: QLever's osm-planet API answers 403 to GitHub's runners (its wikidata API still answers), and the
public Overpass servers answer 502 "at capacity" to automated clients, so a monthly run that waited on them spent hours
retrying. Bulk site lists now come from Geofabrik's free regional extracts, filtered locally with osmium-tool
(geofabrik_points). The two query services remain for small jobs (base outlines), and each is given up for the rest of
a run after its first hard failure, so a dead service costs seconds, not hours.

    geofabrik_points(groups, bbox)            -> [{id, lat, lon, tags}]      (centroids from extracts; needs osmium)
    points(groups, bbox)                      -> [{id, lat, lon, tags}]      (centroids, for site lists)
    shapes(lat, lon, radius_km, groups)       -> [{type, id, tags, geometry|members}]  (Overpass-like, for base outlines)

A group is (key, values, extra_keys): values is a list of tag values, or None for any value; extra_keys are tags to
return alongside (name and name:en always come back). OSM data (c) OpenStreetMap contributors, ODbL.
"""
import json
import math
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

QLEVER = "https://qlever.dev/api/osm-planet"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
UA = "warwatch/1.0 (https://github.com/khourix/warwatch)"
PREFIX = """PREFIX osmkey: <https://www.openstreetmap.org/wiki/Key:>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
"""
log = print
DOWN = {}   # service -> reason; a service that failed hard is not asked again in this run


class Unavailable(RuntimeError):
    pass


def key_iri(k):
    return "<https://www.openstreetmap.org/wiki/Key:" + urllib.parse.quote(k, safe=":_") + ">"


def lit(v):
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sparql(query, timeout=600, tries=4):
    """SELECT results from QLever as a list of {var: value} dicts."""
    if "qlever" in DOWN:
        raise Unavailable("qlever down for this run: " + DOWN["qlever"])
    body = urllib.parse.urlencode({"query": PREFIX + query}).encode()
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(QLEVER, data=body, headers={"User-Agent": UA, "Accept": "application/sparql-results+json",
                                                                      "Content-Type": "application/x-www-form-urlencoded"})
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return [{v: b[v]["value"] for v in b} for b in d["results"]["bindings"]]
        except urllib.error.HTTPError as e:
            last = e
            log("  qlever failed:", str(e)[:120])
            if e.code in (401, 403, 404):      # refused, not busy: retrying will not help
                break
            time.sleep(10 * 2 ** k)
        except Exception as e:      # timeouts, cut connections
            last = e
            log("  qlever failed:", str(e)[:120])
            time.sleep(10 * 2 ** k)
    DOWN["qlever"] = str(last)[:120]
    raise Unavailable(f"qlever failed: {last}")


def _osm_id(iri):
    """'https://www.openstreetmap.org/way/123' -> ('way', 123)."""
    parts = iri.rstrip("/").split("/")
    return parts[-2], int(parts[-1])


def _pattern(groups, geom_var="?w"):
    """UNION of the tag patterns; binds ?x, the matching ?k/?v, the extras, name, name:en and the WKT."""
    alts = []
    extras = sorted({e for _, _, ex in groups for e in ex} | {"name", "name:en"})
    for key, values, _ in groups:
        if values:
            alts.append("{ VALUES ?v { " + " ".join(lit(v) for v in values) + " } ?x " + key_iri(key) + " ?v . BIND(" + lit(key) + " AS ?k) }")
        else:
            alts.append("{ ?x " + key_iri(key) + " ?v . BIND(" + lit(key) + " AS ?k) }")
    opt = " ".join(f"OPTIONAL {{ ?x {key_iri(e)} ?e{n} }}" for n, e in enumerate(extras))
    return " UNION ".join(alts) + f" ?x geo:hasGeometry/geo:asWKT {geom_var} . " + opt, extras


def _tags(row, extras):
    t = {row["k"]: row["v"]}
    for n, e in enumerate(extras):
        if f"e{n}" in row:
            t[e] = row[f"e{n}"]
    return t


def points(groups, bbox):
    """Centroids of every element matching the groups inside bbox (la0, la1, lo0, lo1) -> [{id, lat, lon, tags}]."""
    la0, la1, lo0, lo1 = bbox
    pat, extras = _pattern(groups)
    q = ("SELECT ?x ?k ?v ?c " + " ".join(f"?e{n}" for n in range(len(extras))) + " WHERE { " + pat +
         " BIND(geof:centroid(?w) AS ?c) BIND(geof:latitude(?c) AS ?la) BIND(geof:longitude(?c) AS ?lo)"
         f" FILTER(?la >= {la0} && ?la <= {la1} && ?lo >= {lo0} && ?lo <= {lo1}) }}")
    try:
        rows = sparql(q)
    except Exception as e:
        log("  qlever unavailable, trying Overpass:", str(e)[:100])
        return points_overpass(groups, bbox)
    out = {}
    for r in rows:
        m = re.match(r"POINT\(([-\d.eE]+) ([-\d.eE]+)\)", r.get("c", ""))
        if not m:
            continue
        typ, oid = _osm_id(r["x"])
        rec = out.setdefault((typ, oid), {"id": f"osm:{typ[0]}{oid}", "lat": float(m.group(2)), "lon": float(m.group(1)), "tags": {}})
        rec["tags"].update(_tags(r, extras))
    return list(out.values())


# ---------------------------------------------------------------- WKT -> Overpass-like elements
def _coords(s):
    return [[float(a), float(b)] for a, b in (p.split()[:2] for p in s.split(","))]


def parse_wkt(w):
    """-> ('point'|'line'|'polygon', [rings or lines]). Polygons give outer rings only (holes dropped)."""
    w = w.strip()
    head = w.split("(", 1)[0].strip().upper()
    if head == "POINT":
        return "point", [_coords(w[w.index("(") + 1:w.rindex(")")])]
    if head == "LINESTRING":
        return "line", [_coords(w[w.index("(") + 1:w.rindex(")")])]
    if head == "MULTILINESTRING":
        return "line", [_coords(x) for x in re.findall(r"\(([^()]+)\)", w)]
    if head == "POLYGON":
        rings = re.findall(r"\(([^()]+)\)", w)
        return "polygon", [_coords(rings[0])] if rings else []
    if head == "MULTIPOLYGON":
        polys = re.findall(r"\(\(([^()]+)\)", w)       # the first ring of each polygon is its outer ring
        return "polygon", [_coords(p) for p in polys]
    return "unknown", []


def _element(typ, oid, tags, wkt):
    kind, parts = parse_wkt(wkt)
    if kind == "polygon" and len(parts) == 1 and typ == "way":
        return {"type": "way", "id": oid, "tags": tags, "geometry": [{"lon": x, "lat": y} for x, y in parts[0]]}
    if kind == "polygon":
        return {"type": "relation", "id": oid, "tags": tags,
                "members": [{"role": "outer", "geometry": [{"lon": x, "lat": y} for x, y in ring]} for ring in parts]}
    if kind == "line":
        return {"type": "way", "id": oid, "tags": tags, "geometry": [{"lon": x, "lat": y} for x, y in parts[0]]}
    if kind == "point":
        return {"type": "node", "id": oid, "tags": tags, "lat": parts[0][0][1], "lon": parts[0][0][0]}
    return None


def shapes(lat, lon, radius_km, groups):
    """Full geometries of elements matching the groups whose centroid lies within radius_km of the point, as Overpass-like
    elements (ways with 'geometry', multipolygon relations with outer 'members')."""
    dla = radius_km / 110.574
    dlo = radius_km / (111.320 * max(0.05, math.cos(math.radians(lat))))
    pat, extras = _pattern(groups)
    q = ("SELECT ?x ?k ?v ?w " + " ".join(f"?e{n}" for n in range(len(extras))) + " WHERE { " + pat +
         " BIND(geof:centroid(?w) AS ?c) BIND(geof:latitude(?c) AS ?la) BIND(geof:longitude(?c) AS ?lo)"
         f" FILTER(?la >= {lat - dla} && ?la <= {lat + dla} && ?lo >= {lon - dlo} && ?lo <= {lon + dlo}) }}")
    try:
        rows = sparql(q)
    except Exception as e:
        log("  qlever unavailable, trying Overpass:", str(e)[:100])
        return shapes_overpass(lat, lon, radius_km, groups)
    merged = {}
    for r in rows:
        typ, oid = _osm_id(r["x"])
        m = merged.setdefault((typ, oid), {"typ": typ, "oid": oid, "tags": {}, "w": r["w"]})
        m["tags"].update(_tags(r, extras))
    return [e for e in (_element(m["typ"], m["oid"], m["tags"], m["w"]) for m in merged.values()) if e]


# ---------------------------------------------------------------- Overpass fallback (small declared resources)
def overpass(q, tries=6):
    if "overpass" in DOWN:
        raise Unavailable("overpass down for this run: " + DOWN["overpass"])
    body = ("data=" + urllib.parse.quote(q)).encode()
    last = None
    for k in range(tries):
        url = OVERPASS[k % len(OVERPASS)]
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
            return json.loads(urllib.request.urlopen(req, timeout=200).read())
        except Exception as e:
            last = e
            log("  overpass", url.split("/")[2], "failed:", str(e)[:100])
            time.sleep(10 * (1 + k // len(OVERPASS)))
    DOWN["overpass"] = str(last)[:120]
    raise Unavailable(f"overpass failed: {last}")


def _ov_filters(groups):
    out = []
    for key, values, _ in groups:
        if values:
            out.append(f'nwr["{key}"~"^({"|".join(re.escape(v) for v in values)})$"]')
        else:
            out.append(f'nwr["{key}"]')
    return out


def points_overpass(groups, bbox, step=1.0):
    """Overpass in 1-degree tiles, each declaring 120 s and 128 MB so a busy server still admits it."""
    la0, la1, lo0, lo1 = bbox
    out, a = [], la0
    flt = "".join(f + ";" for f in _ov_filters(groups))
    while a < la1:
        b = lo0
        while b < lo1:
            q = f"[out:json][timeout:120][maxsize:134217728][bbox:{a},{b},{min(a + step, la1)},{min(b + step, lo1)}];({flt});out center tags;"
            for e in overpass(q).get("elements", []):
                la = e.get("lat", e.get("center", {}).get("lat"))
                lo = e.get("lon", e.get("center", {}).get("lon"))
                if la is not None:
                    out.append({"id": f"osm:{e['type'][0]}{e['id']}", "lat": la, "lon": lo, "tags": e.get("tags", {})})
            b += step
        a += step
    return out


def shapes_overpass(lat, lon, radius_km, groups):
    r = int(radius_km * 1000)
    flt = "".join(f.replace("nwr", "nwr", 1) + f"(around:{r},{lat},{lon});" for f in _ov_filters(groups))
    return overpass(f"[out:json][timeout:120][maxsize:134217728];({flt});out geom tags;").get("elements", [])


# ---------------------------------------------------------------- Geofabrik extracts + osmium (bulk site lists)
GEOFABRIK = "https://download.geofabrik.de/index-v1.json"
_GF = {"index": None, "regions": {}}   # region id -> [{id, lat, lon, tags}] filtered for the groups below


def geofabrik_ready():
    return shutil.which("osmium") is not None


GF_SKIP = {"dach", "alps", "britain-and-ireland", "us"}   # composite extracts that repeat smaller ones (12 GB for "us")


def _gf_leaves():
    """Geofabrik's smallest extracts (regions with no sub-regions, composites skipped) with one bounding box per polygon
    (two for a polygon that crosses the antimeridian; one box for it would cover the whole globe) and their .pbf URLs."""
    if _GF["index"] is None:
        req = urllib.request.Request(GEOFABRIK, headers={"User-Agent": UA})
        feats = json.loads(urllib.request.urlopen(req, timeout=120).read())["features"]
        parents = {f["properties"].get("parent") for f in feats}
        out = []
        for f in feats:
            pr, g = f["properties"], f.get("geometry")
            if pr["id"] in parents or pr["id"] in GF_SKIP or not g or "pbf" not in pr.get("urls", {}):
                continue
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            boxes = []
            for poly in polys:
                xs = [c[0] for c in poly[0]]
                ys = [c[1] for c in poly[0]]
                if not xs:
                    continue
                if max(xs) - min(xs) <= 180:
                    boxes.append((min(ys), max(ys), min(xs), max(xs)))
                else:   # crosses the antimeridian: one box on each side
                    boxes += [(min(ys), max(ys), min(x for x in xs if x >= 0), 180.0), (min(ys), max(ys), -180.0, max(x for x in xs if x < 0))]
            if boxes:
                out.append({"id": pr["id"], "url": pr["urls"]["pbf"], "boxes": boxes})
        _GF["index"] = out
    return _GF["index"]


def gf_regions(bbox):
    la0, la1, lo0, lo1 = bbox
    return [r for r in _gf_leaves() if any(b[0] <= la1 and b[1] >= la0 and b[2] <= lo1 and b[3] >= lo0 for b in r["boxes"])]


def _osmium_filters(groups):
    return [f"nwr/{key}" + ("=" + ",".join(values) if values else "") for key, values, _ in groups]


def _centroid(geom):
    pts = []
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            pts.append(c)
        else:
            for x in c:
                walk(x)
    walk(geom["coordinates"][0] if geom["type"] in ("Polygon", "MultiPolygon") else geom["coordinates"])
    if not pts:
        return None
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def _gf_region(r, groups, cache):
    """Download one extract, keep the elements with the groups' tags, export them and return their centroids."""
    os.makedirs(cache, exist_ok=True)
    raw, flt, js = (os.path.join(cache, r["id"].replace("/", "_") + x) for x in (".osm.pbf", ".f.osm.pbf", ".geojsonseq"))
    if not os.path.exists(js):
        t0 = time.time()
        req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as resp, open(raw, "wb") as f:
            shutil.copyfileobj(resp, f, 1 << 20)
        mb = os.path.getsize(raw) / 1e6
        subprocess.run(["osmium", "tags-filter", "--overwrite", "-o", flt, raw] + _osmium_filters(groups), check=True, capture_output=True)
        os.remove(raw)
        subprocess.run(["osmium", "export", "--overwrite", "-f", "geojsonseq", "-a", "type,id", "-o", js, flt], check=True, capture_output=True)
        os.remove(flt)
        log(f"  geofabrik {r['id']}: {mb:.0f} MB in {time.time() - t0:.0f} s")
    out = []
    with open(js, encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            ft = json.loads(line)
            pr = ft.get("properties", {})
            c = _centroid(ft.get("geometry") or {"type": "Point", "coordinates": []})
            if not c:
                continue
            typ = {"n": "n", "w": "w", "r": "r", "node": "n", "way": "w", "relation": "r", "area": "w"}.get(str(pr.get("@type", "n")), "n")
            tags = {k: v for k, v in pr.items() if not k.startswith("@")}
            out.append({"id": f"osm:{typ}{pr.get('@id')}", "lat": c[0], "lon": c[1], "tags": tags})
    return out


def geofabrik_points(groups, bbox, cache=None):
    """Centroids of the elements matching the groups inside bbox, from every Geofabrik extract that touches it. Each
    extract is downloaded and filtered once per run (the filtered file stays in the cache). Raises if any extract fails,
    so the caller can keep its earlier rows for this box."""
    cache = cache or os.environ.get("OSM_PBF_CACHE", "/tmp/osm-pbf")
    la0, la1, lo0, lo1 = bbox
    want = {(k, v) for k, vs, _ in groups for v in (vs or [None])}
    out, seen = [], set()
    for r in gf_regions(bbox):
        if r["id"] not in _GF["regions"]:
            _GF["regions"][r["id"]] = _gf_region(r, groups, cache)
        for p in _GF["regions"][r["id"]]:
            if p["id"] in seen or not (la0 <= p["lat"] <= la1 and lo0 <= p["lon"] <= lo1):
                continue
            if any(k in p["tags"] and (v is None or p["tags"][k] == v) for k, v in want):
                seen.add(p["id"])
                out.append(p)
    return out
