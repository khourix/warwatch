import json, time, urllib.request, datetime as dt
UA = {"User-Agent": "warwatch-probe", "Content-Type": "application/json"}
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
BOX = [55.5, 25.5, 57.5, 27.3]
start = (dt.date.today() - dt.timedelta(days=20)).isoformat()
found = {}
for col in ("sentinel-1-rtc", "sentinel-1-grd"):
    body = json.dumps({"collections": [col], "bbox": BOX, "datetime": f"{start}T00:00:00Z/..", "limit": 30}).encode()
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(STAC, data=body, headers=UA), timeout=60).read())
        fs = r.get("features", [])
        print(col, "items", len(fs))
        for f in fs[:6]:
            p = f["properties"]
            print("  ", f["id"][:60], p.get("datetime"), p.get("platform"), p.get("sar:instrument_mode"), p.get("sar:polarizations"), list(f["assets"])[:8])
        found[col] = fs
    except Exception as e:
        print(col, "ERR", e)
import numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
for col in ("sentinel-1-rtc", "sentinel-1-grd"):
    fs = found.get(col) or []
    if not fs: continue
    f = fs[0]; href = f["assets"]["vv"]["href"]
    try:
        s = json.loads(urllib.request.urlopen("https://planetarycomputer.microsoft.com/api/sas/v1/sign?href=" + urllib.request.quote(href, safe=""), timeout=30).read())
        t0 = time.time()
        with rasterio.open(s["href"]) as ds:
            print(col, "open ok", ds.crs, ds.shape, ds.res, "gcps", len(ds.gcps[0]) if ds.gcps else 0, "dtype", ds.dtypes[0], "bounds", ds.bounds)
            if ds.crs and not ds.gcps:
                b = transform_bounds("EPSG:4326", ds.crs, 56.0, 26.3, 56.6, 26.9)
                w = from_bounds(*b, transform=ds.transform)
                a = ds.read(1, window=w, boundless=False)
                print("  window", a.shape, "min/median/p99/max", float(a.min()), float(np.median(a)), float(np.percentile(a, 99)), float(a.max()), "secs", round(time.time() - t0, 1))
    except Exception as e:
        print(col, "read ERR", repr(e)[:300])
