"""Basemap: Natural Earth countries (world-atlas TopoJSON) -> SVG paths. Standard library only.

The TopoJSON file is downloaded by the workflow (assets/countries-50m.json);
if it is missing the dashboard still renders, with an empty map.
"""
import json
import math
import os

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "countries-50m.json")

# view name -> (lon_min, lon_max, lat_min, lat_max)
VIEWS = {
    "overview": (-12, 72, 8, 66),
    "ukraine": (18, 50, 40, 57),
    "europe_east": (8, 36, 48, 63),
    "mideast": (28, 64, 10, 40),
}


def load():
    try:
        with open(ASSET) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def decode_arcs(topo):
    sc, tr = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)
    return arcs


def _ring(arcs, idx):
    pts = []
    for i in idx:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def countries(topo):
    """-> [(id, name, [ring, ...])] with rings as lists of (lon, lat)."""
    arcs = decode_arcs(topo)
    out = []
    for g in topo["objects"]["countries"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        rings = [_ring(arcs, r) for poly in polys for r in poly]
        out.append((str(g.get("id", "")), g.get("properties", {}).get("name", ""), rings))
    return out


class Proj:
    """Mercator, fitted to a lon/lat box and a pixel viewport."""

    def __init__(self, box, w, h):
        self.lo, self.hi, self.la0, self.la1 = box
        self.w, self.h = w, h
        self.y0, self.y1 = self._m(self.la1), self._m(self.la0)

    @staticmethod
    def _m(lat):
        lat = max(-85, min(85, lat))
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    def xy(self, lon, lat):
        return ((lon - self.lo) / (self.hi - self.lo) * self.w,
                (self.y0 - self._m(lat)) / (self.y0 - self.y1) * self.h)

    def inside(self, lon, lat, pad=0.0):
        return self.lo - pad <= lon <= self.hi + pad and self.la0 - pad <= lat <= self.la1 + pad


def view_size(box, width=1000):
    """Pixel size (w, h) that keeps a lon/lat box undistorted under Mercator."""
    lo, hi, la0, la1 = box
    y = Proj._m(la1) - Proj._m(la0)
    return width, round(width * y / math.radians(hi - lo))


def paths(topo, proj, level_of=None):
    """-> list of (name, svg_path_d, level_class). Rings wholly outside the view are skipped."""
    out = []
    for cid, name, rings in countries(topo):
        d = []
        for ring in rings:
            lons = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            if max(lons) < proj.lo or min(lons) > proj.hi or max(lats) < proj.la0 or min(lats) > proj.la1:
                continue
            pts, last = [], None
            for lon, lat in ring:
                x, y = proj.xy(lon, lat)
                q = (round(x, 1), round(y, 1))
                if q != last:
                    pts.append(q)
                    last = q
            if len(pts) > 2:
                d.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
        if d:
            out.append((name, "".join(d), (level_of or {}).get(name, "")))
    return out


# ---- one region-wide basemap for the interactive page (the page zooms and pans in the browser) ----
REGION = (-100, 150, -20, 64)   # lon_min, lon_max, lat_min, lat_max: the Americas to the Western Pacific, so every market-moving theatre is on the map
MARGIN = 6


def _area_centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    if abs(a) < 1e-9:
        return None, 0.0
    return (cx / (3 * a), cy / (3 * a)), abs(a) / 2


def region_map(topo, width=3200):
    """-> dict(w, h, proj, countries=[{name, d, cx, cy, area}]) for the whole region.

    Paths use relative moves with one decimal so the page stays small. Points outside
    the region are clamped to a margin; they are off screen so the clamp is invisible."""
    w, h = view_size(REGION, width)
    pr = Proj(REGION, w, h)
    lo, hi, la0, la1 = REGION
    out = []
    for _cid, name, rings in countries(topo):
        parts, best = [], (None, 0.0)
        for ring in rings:
            lons = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            if max(lons) < lo - MARGIN or min(lons) > hi + MARGIN or max(lats) < la0 - MARGIN or min(lats) > la1 + MARGIN:
                continue
            pts, last = [], None
            for lon, lat in ring:
                x, y = pr.xy(min(max(lon, lo - MARGIN), hi + MARGIN), min(max(lat, la0 - MARGIN), la1 + MARGIN))
                q = (round(x, 1), round(y, 1))
                if q != last:
                    pts.append(q)
                    last = q
            if len(pts) < 4:
                continue
            c, area = _area_centroid(pts)
            if c and area > best[1] and lo <= (c[0] / w * (hi - lo) + lo) <= hi:
                best = (c, area)
            d, (px, py) = [f"M{pts[0][0]},{pts[0][1]}"], pts[0]
            for x, y in pts[1:]:
                d.append(f"l{round(x - px, 1)},{round(y - py, 1)}")
                px, py = x, y
            parts.append("".join(d) + "z")
        if parts:
            c = best[0] or (0, 0)
            out.append({"name": name, "d": "".join(parts), "cx": round(c[0], 1), "cy": round(c[1], 1), "area": round(best[1])})
    return {"w": w, "h": h, "proj": pr, "countries": out}
