"""Shared satellite-image helpers for the imagery workflow (docs/BASEWATCH_PLAN.md, S0): STAC search, signed reads on a
lon/lat grid, Sentinel-2 cloud share, and small JPEG chips. Needs numpy, rasterio and Pillow, so only imagery.yml,
basespike.py, basewatch.py and firereview.py import it; the dashboard build never does.

Sources (free, no key): Microsoft Planetary Computer STAC with anonymous SAS signing (Sentinel-1 RTC, Sentinel-2 L2A,
ESA WorldCover), with Element 84 Earth Search (sentinel-2-c1-l2a) as the Sentinel-2 fallback. Copernicus Sentinel data
is free and open; every chip is captioned "Contains modified Copernicus Sentinel data".
"""
import datetime as dt
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_SIGN = "https://planetarycomputer.microsoft.com/api/sas/v1/sign?href="
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/"
ES_STAC = "https://earth-search.aws.element84.com/v1/search"
ES_BAND = {"B02": "blue", "B03": "green", "B04": "red", "B08": "nir", "B8A": "nir08", "B11": "swir16", "B12": "swir22", "SCL": "scl"}
CLEAR_SCL = (4, 5, 6, 7, 11)      # vegetation, bare, water, unclassified, snow: everything except cloud, shadow, no data
UA = {"User-Agent": "warwatch (github.com/khourix/warwatch)"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHIPS = os.environ.get("WARWATCH_CHIPS", os.path.join(ROOT, "chips"))


def _open(req, timeout=90):
    """urlopen + JSON with waits on 429 and 5xx, as sar.py does."""
    for wait in (0, 5, 20, 60):
        time.sleep(wait)
        try:
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or wait == 60:
                raise
        except (urllib.error.URLError, TimeoutError):
            if wait == 60:
                raise
    raise RuntimeError("unreachable")


def _post(url, body):
    return _open(urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(UA, **{"Content-Type": "application/json"})))


_SIGNED = {}
_TOKENS = {}      # (storage account, container) -> (SAS token, expiry as epoch seconds)


def sign(href):
    """Signed URL for a Planetary Computer blob. One SAS token per storage container, kept until 5 minutes before it expires:
    the anonymous signing service rate-limits per IP, and signing each file (six bands a scene) from a shared GitHub runner
    met 429s and the 85 s of waits after them on every other read. Per-file signing remains the fallback."""
    u = urllib.parse.urlparse(href)
    if u.netloc.endswith(".blob.core.windows.net") and u.path.count("/") >= 2:
        key = (u.netloc.split(".")[0], u.path.split("/")[1])
        tok = _TOKENS.get(key)
        if not tok or tok[1] - time.time() < 300:
            try:
                d = _open(urllib.request.Request(PC_TOKEN + "/".join(key), headers=UA), 40)
                exp = dt.datetime.strptime(d["msft:expiry"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
                tok = _TOKENS[key] = (d["token"], exp)
            except Exception:
                tok = None
        if tok:
            return href + ("&" if u.query else "?") + tok[0]
    if href not in _SIGNED:
        _SIGNED[href] = _open(urllib.request.Request(PC_SIGN + urllib.parse.quote(href, safe=""), headers=UA), 40)["href"]
    return _SIGNED[href]


def stac_search(collection, bbox, start, end, limit=250):
    """Items of a collection touching bbox (lon0, lat0, lon1, lat1) between two ISO dates, oldest first. Each item gets _src
    = 'pc' or 'es'. Sentinel-2 falls back to Earth Search when Planetary Computer fails."""
    body = {"collections": [collection], "bbox": list(bbox), "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": limit}
    try:
        items = _post(PC_STAC, body).get("features", [])
        for it in items:
            it["_src"] = "pc"
    except Exception:
        if not collection.startswith("sentinel-2"):
            raise
        items = []
    if collection.startswith("sentinel-2") and not items:
        body["collections"] = ["sentinel-2-c1-l2a"]
        items = _post(ES_STAC, body).get("features", [])
        for it in items:
            it["_src"] = "es"
    return sorted(items, key=lambda i: i["properties"]["datetime"])


def href(item, band):
    """Readable URL of a band ('vv', 'vh', 'B04', 'SCL', 'map'...)."""
    if item.get("_src") == "es":
        return item["assets"][ES_BAND.get(band, band.lower())]["href"]
    return sign(item["assets"][band]["href"])


def has(item, band):
    a = item.get("assets", {})
    return (ES_BAND.get(band, band.lower()) in a) if item.get("_src") == "es" else band in a


def box_around(lat, lon, half_km):
    dlat = half_km / 110.574
    dlon = half_km / (111.320 * max(0.05, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def grid(bbox, res_m):
    """(width, height) of a lon/lat grid over bbox with pixels about res_m metres."""
    lo0, la0, lo1, la1 = bbox
    mid = (la0 + la1) / 2
    w = max(8, round((lo1 - lo0) * 111320 * math.cos(math.radians(mid)) / res_m))
    h = max(8, round((la1 - la0) * 110574 / res_m))
    return w, h


# remote COG reads: no sidecar-file listing on open (a listing of a signed blob URL only costs time), bounded HTTP waits
for _k, _v in (("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR"), ("GDAL_HTTP_TIMEOUT", "60"), ("GDAL_HTTP_MAX_RETRY", "3"),
               ("GDAL_HTTP_RETRY_DELAY", "2"), ("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES"), ("VSI_CACHE", "TRUE")):
    os.environ.setdefault(_k, _v)


def read(url, bbox, w, h, resampling="bilinear", band=1):
    """One band resampled onto a w x h lon/lat grid over bbox (float64, NaN where the scene has no data)."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.vrt import WarpedVRT
    tr = from_bounds(*bbox, w, h)
    with rasterio.open(url) as src, WarpedVRT(src, crs="EPSG:4326", transform=tr, width=w, height=h,
                                              resampling=getattr(Resampling, resampling), src_nodata=src.nodata, nodata=np.nan if src.dtypes[0].startswith("float") else 0) as v:
        a = v.read(band).astype("float64")
        if not src.dtypes[0].startswith("float"):
            nod = v.read_masks(band) == 0
            a[nod] = np.nan
    return a


def transform(bbox, w, h):
    from rasterio.transform import from_bounds
    return from_bounds(*bbox, w, h)


def mask(geoms, bbox, w, h, buffer_px=0):
    """Boolean mask of lon/lat polygons (lists of rings) and lines on the grid; lines and buffer_px > 0 are dilated."""
    import numpy as np
    from rasterio.features import rasterize
    from scipy import ndimage as ndi
    shapes = []
    for g in geoms:
        if len(g) >= 4 and g[0] == g[-1]:
            shapes.append({"type": "Polygon", "coordinates": [g]})
        elif len(g) >= 2:
            shapes.append({"type": "LineString", "coordinates": g})
    if not shapes:
        return np.zeros((h, w), bool)
    m = rasterize([(s, 1) for s in shapes], out_shape=(h, w), transform=transform(bbox, w, h), fill=0, all_touched=True, dtype="uint8").astype(bool)
    return ndi.binary_dilation(m, iterations=buffer_px) if buffer_px else m


def clear_share(item, bbox, region=None):
    """Share of the area (or of `region`, a mask on a 20 m grid) that Sentinel-2's scene classification calls clear."""
    import numpy as np
    w, h = grid(bbox, 20)
    scl = read(href(item, "SCL"), bbox, w, h, "nearest")
    sel = region if region is not None and region.shape == scl.shape else np.ones(scl.shape, bool)
    if not sel.any():
        return 0.0
    ok = np.isin(np.nan_to_num(scl, nan=0), CLEAR_SCL)
    return float(ok[sel].mean())


def s2_bands(item, bbox, bands, res_m=10):
    """{band: reflectance array} on one grid (Sentinel-2 L2A digital numbers / 10000; the processing-baseline offset is ignored,
    which shifts every scene alike and does not change differences)."""
    w, h = grid(bbox, res_m)
    return {b: read(href(item, b), bbox, w, h, "bilinear") / 10000.0 for b in bands}


def stretch(a, lo=2, hi=98):
    import numpy as np
    v = a[np.isfinite(a)]
    if v.size == 0:
        return np.zeros(a.shape, "uint8")
    p0, p1 = np.percentile(v, [lo, hi])
    if p1 <= p0:
        p1 = p0 + 1e-6
    return (np.clip((np.nan_to_num(a, nan=p0) - p0) / (p1 - p0), 0, 1) * 255).astype("uint8")


def save_jpeg(rgb_or_grey, path, size=256):
    """Writes a size x size JPEG (quality 80) from an RGB stack (3, h, w) or a single band (h, w) of uint8."""
    import numpy as np
    from PIL import Image
    a = np.asarray(rgb_or_grey)
    img = Image.fromarray(np.moveaxis(a, 0, -1), "RGB") if a.ndim == 3 else Image.fromarray(a, "L")
    img = img.resize((size, size), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=80, optimize=True)
    return path


def chip_s2(item, bbox, path, kind="true"):
    """True colour (B04, B03, B02) or SWIR (B12, B8A, B04: burn scars red-brown, active fire bright) chip."""
    import numpy as np
    bands = ("B04", "B03", "B02") if kind == "true" else ("B12", "B8A", "B04")
    arr = s2_bands(item, bbox, bands, 10)
    # one stretch for all three bands keeps colours true
    stack = np.stack([arr[b] for b in bands])
    v = stack[np.isfinite(stack)]
    if v.size == 0:
        return None
    p0, p1 = np.percentile(v, [2, 98])
    rgb = (np.clip((np.nan_to_num(stack, nan=p0) - p0) / max(1e-6, p1 - p0), 0, 1) * 255).astype("uint8")
    return save_jpeg(rgb, path)


def chip_radar(db, path, lo=-25.0, hi=5.0):
    import numpy as np
    g = (np.clip((np.nan_to_num(db, nan=lo) - lo) / (hi - lo), 0, 1) * 255).astype("uint8")
    return save_jpeg(g, path)


def db(a):
    import numpy as np
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(np.where(a > 0, a, np.nan))


def orbit(item):
    """'A101' / 'D137': pass direction + relative orbit. Scenes are only comparable within one orbit (same geometry)."""
    p = item["properties"]
    return (p.get("sat:orbit_state", "?")[:1].upper()) + str(p.get("sat:relative_orbit", "?"))


def day(item):
    return item["properties"]["datetime"][:10]


def worldcover_class(lat, lon, radius_m=300):
    """Majority ESA WorldCover 2021 class within radius_m -> plain name."""
    import numpy as np
    names = {10: "tree", 20: "shrub", 30: "grass", 40: "cropland", 50: "built", 60: "bare", 70: "snow", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss"}
    bbox = box_around(lat, lon, radius_m / 1000.0)
    items = stac_search("esa-worldcover", bbox, "2021-01-01", "2021-12-31", 5)
    if not items:
        return "other"
    w, h = grid(bbox, 10)
    a = read(href(items[-1], "map"), bbox, w, h, "nearest")
    v = a[np.isfinite(a) & (a > 0)].astype(int)
    if v.size == 0:
        return "other"
    return names.get(int(np.bincount(v).argmax()), "other")
