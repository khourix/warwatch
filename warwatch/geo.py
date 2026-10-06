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
