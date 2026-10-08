#!/usr/bin/env python3
"""Ship counts from Sentinel-1 radar over the Gulf and Red Sea, where free AIS has no receivers.

Runs in its own workflow (.github/workflows/sar.yml) because it needs numpy, scipy and rasterio; the dashboard build stays
standard-library only and just reads the cache files this script writes (warwatch/history/cache/sar_<box>.csv).

Source: Sentinel-1 terrain-corrected scenes (Copernicus, open licence) read from Microsoft Planetary Computer with anonymous
signing. ESA WorldCover 10 m masks the land and a 600 m coastal strip. One scene arrives about every two days over each box.

Method: read the VV band at 40 m (average of 4x4 pixels), compare each sea pixel with the mean and spread of the sea around it
(a 2 km window), keep pixels that stand out, join neighbours, keep blobs of 2 to 200 pixels. The count is "candidate vessels":
it also counts oil rigs and buoys, misses small boats, and gives no names. The daily value is candidates per 10,000 km2 of sea
actually seen, so a scene that only clips the box does not look like a quiet day.

    python3 warwatch/sar.py --days 6                 # daily upkeep
    python3 warwatch/sar.py --days 365 --max-scenes 60   # backfill in slices (done scenes are skipped)
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
SCENES = os.path.join(ROOT, "history", "sar_scenes.csv")
BOXES = {   # name: (lon_min, lat_min, lon_max, lat_max)
    "hormuz": (55.3, 25.6, 57.3, 27.2),
    "bab_el_mandeb": (42.6, 11.8, 44.0, 13.6),
    "gulf_of_aden": (45.0, 11.5, 49.0, 13.5),
}
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN = "https://planetarycomputer.microsoft.com/api/sas/v1/sign?href="
DOWN = 4            # read at 40 m: 10 m pixels averaged 4 x 4
COAST_PX = 15       # 600 m strip next to land
BG_PX = 51          # background window, about 2 km
MIN_PX, MAX_PX = 2, 200
MIN_SEA_KM2 = 500.0  # a day needs at least this much sea seen to give a value


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "warwatch"})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


def sign(href):
    return json.loads(urllib.request.urlopen(urllib.request.Request(SIGN + urllib.parse.quote(href, safe=""), headers={"User-Agent": "warwatch"}), timeout=40).read())["href"]


def scenes_for(box, start, end):
    """Sentinel-1 VV+VH terrain-corrected scenes that touch the box between two dates."""
    out, body = [], {"collections": ["sentinel-1-rtc"], "bbox": list(box), "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 200}
    p = _post(STAC, body)
    out += p.get("features", [])
    return out


def detect(db, land_or_invalid, coast_px=COAST_PX, bg_px=BG_PX):
    """-> (candidate vessel count, sea pixels used). db: backscatter in dB; land_or_invalid: True where not usable sea."""
    import numpy as np
    from scipy import ndimage as ndi
    bad = ndi.binary_dilation(land_or_invalid, iterations=coast_px) if coast_px else land_or_invalid
    m = ~bad & np.isfinite(db)
    x = np.where(m, db, 0.0).astype("float64")
    mf = m.astype("float64")
    n = ndi.uniform_filter(mf, bg_px)
    ok = n > 0.3
    mu = np.where(ok, ndi.uniform_filter(x, bg_px) / np.maximum(n, 1e-9), 0.0)
    var = np.where(ok, ndi.uniform_filter(x * x, bg_px) / np.maximum(n, 1e-9) - mu * mu, 1.0)
    sd = np.sqrt(np.maximum(var, 0.25))
    cand = m & ok & (db - mu > 6.0) & ((db - mu) / sd > 5.0)
    cand = ndi.binary_dilation(cand, iterations=1)
    lab, k = ndi.label(cand, structure=np.ones((3, 3)))
    if k == 0:
        return 0, int(m.sum())
    sizes = np.bincount(lab.ravel())[1:]
    return int(((sizes >= MIN_PX) & (sizes <= MAX_PX)).sum()), int(m.sum())


def count_scene(item, box):
    """Candidate vessels and sea area (km2) for one scene inside one box."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import Affine
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds
    b = item["bbox"]
    lo, la, hi, ha = max(box[0], b[0]), max(box[1], b[1]), min(box[2], b[2]), min(box[3], b[3])
    if lo >= hi or la >= ha:
        return 0, 0.0
    with rasterio.open(sign(item["assets"]["vv"]["href"])) as ds:
        wb = transform_bounds("EPSG:4326", ds.crs, lo, la, hi, ha)
        win = from_bounds(*wb, transform=ds.transform).round_offsets().round_lengths().intersection(Window(0, 0, ds.width, ds.height))
        h, w = int(win.height) // DOWN, int(win.width) // DOWN
        if h < 50 or w < 50:
            return 0, 0.0
        vv = ds.read(1, window=win, out_shape=(h, w), resampling=Resampling.average).astype("float64")
        tr = ds.window_transform(win) * Affine.scale(DOWN)
        crs = ds.crs
        nodata = ~np.isfinite(vv) | (vv <= 0)
        db = 10.0 * np.log10(np.where(nodata, 1.0, vv))
        land = np.zeros((h, w), bool)
        wc = _post(STAC, {"collections": ["esa-worldcover"], "bbox": [lo, la, hi, ha], "limit": 20}).get("features", [])
        for f in wc:
            with rasterio.open(sign(f["assets"]["map"]["href"])) as src, WarpedVRT(src, crs=crs, transform=tr, width=w, height=h, resampling=Resampling.nearest) as v:
                lc = v.read(1)
            land |= (lc > 0) & (lc != 80)       # 0 = no data (open sea), 80 = water
        n, px = detect(db, land | nodata)
    return n, px * (DOWN * 10.0 / 1000.0) ** 2


def load_done():
    try:
        with open(SCENES, newline="") as f:
            return [r for r in csv.reader(f) if len(r) == 5]
    except OSError:
        return []


def rebuild(rows):
    """Daily series per box: candidates per 10,000 km2 of sea seen, over days with enough sea in view."""
    by = {}
    for sid, box, day, km2, n in rows:
        d = by.setdefault(box, {}).setdefault(day, [0.0, 0.0])
        d[0] += float(n)
        d[1] += float(km2)
    for box, days in by.items():
        pts = sorted((d, v[0] / v[1] * 10000.0) for d, v in days.items() if v[1] >= MIN_SEA_KM2)
        if pts:
            store.cache_save(f"sar_{box}", pts, stamp=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=6)
    ap.add_argument("--boxes", default=",".join(BOXES))
    ap.add_argument("--max-scenes", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    a = ap.parse_args(argv)
    end = dt.date.today()
    start = end - dt.timedelta(days=a.days)
    rows = load_done()
    seen = {(r[0], r[1]) for r in rows}
    new, budget = [], a.max_scenes
    for name in [b for b in a.boxes.split(",") if b in BOXES]:
        box = BOXES[name]
        # backfills go in 30-day slices so one search never returns thousands of scenes
        s = start
        while s < end and budget > 0:
            e = min(s + dt.timedelta(days=30), end)
            try:
                items = scenes_for(box, str(s), str(e))
            except Exception as ex:
                print(name, "search failed:", ex, flush=True)
                break
            for it in sorted(items, key=lambda i: i["properties"]["datetime"]):
                if budget <= 0:
                    break
                if (it["id"], name) in seen or "vv" not in it["assets"]:
                    continue
                try:
                    n, km2 = count_scene(it, box)
                except Exception as ex:
                    print(name, it["id"][:40], "failed:", repr(ex)[:160], flush=True)
                    continue
                row = [it["id"], name, it["properties"]["datetime"][:10], f"{km2:.0f}", str(n)]
                print(name, row[2], f"sea {km2:.0f} km2", f"candidates {n}", flush=True)
                new.append(row)
                seen.add((it["id"], name))
                budget -= 1
            s = e
    if a.dry_run or not new:
        return 0
    os.makedirs(os.path.dirname(SCENES), exist_ok=True)
    with open(SCENES, "a", newline="") as f:
        csv.writer(f).writerows(new)
    rebuild(rows + new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
