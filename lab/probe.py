"""Temporary live probe (branch-only lab workflow). Prints what the plans need to know; writes nothing to the repo."""
import io, json, sys, time, urllib.request, zipfile, re
UA = {"User-Agent": "warwatch-lab (github.com/khourix/warwatch)"}
def get(url, data=None, headers=None, rng=None, timeout=60):
    h = dict(UA, **(headers or {}))
    if rng: h["Range"] = rng
    r = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return f.status, f.headers, f.read()
def try_(label, fn):
    try: fn()
    except Exception as e: print(f"{label}: FAIL {type(e).__name__} {str(e)[:200]}", flush=True)

COUNTRIES = sorted({"Ukraine", "Russia", "Belarus", "Moldova", "Romania", "Poland", "Slovakia", "Hungary", "Lithuania", "Latvia", "Estonia", "Finland", "Sweden",
    "Germany", "Czechia", "Czech_Republic", "Iran", "Iraq", "Kuwait", "Bahrain", "Qatar", "United_Arab_Emirates", "Oman", "Saudi_Arabia", "Syria", "Turkey", "Turkiye",
    "Jordan", "Armenia", "Azerbaijan", "Turkmenistan", "Afghanistan", "Pakistan", "Georgia", "Yemen", "Eritrea", "Ethiopia", "Djibouti", "Somalia", "Sudan", "Egypt",
    "Israel", "Palestine", "Lebanon", "Cyprus", "South_Korea", "North_Korea", "China", "Japan", "Libya", "Tunisia", "Algeria", "Niger", "Chad"})
print("== FIRMS country files")
def firms_country(c, y=2024, prod="viirs-snpp"):
    u = f"https://firms.modaps.eosdis.nasa.gov/data/country/{prod}/{y}/{prod}_{y}_{c}.csv"
    s, h, b = get(u, rng="bytes=0-600")
    print(f"{prod} {y} {c}: {s} len={h.get('Content-Range') or h.get('Content-Length')} head={b.decode('utf-8','replace').splitlines()[0][:200]}", flush=True)
for c in COUNTRIES:
    try_(c, lambda c=c: firms_country(c))
for y in (2012, 2018, 2025, 2026):
    try_(f"year {y}", lambda y=y: firms_country("Qatar", y))
try_("noaa20", lambda: firms_country("Qatar", 2024, "viirs-noaa20"))
try_("index", lambda: print("index:", get("https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/2024/")[2][:1500].decode("utf-8", "replace")))
def zipsize():
    s, h, b = get("https://firms.modaps.eosdis.nasa.gov/data/country/zips/viirs-snpp_2024_all_countries.zip", rng="bytes=0-100")
    print("all-countries zip 2024:", s, h.get("Content-Range"))
try_("zip", zipsize)

print("== GGFR flare xlsx")
def ggfr():
    u = "https://thedocs.worldbank.org/en/doc/bd2432bbb0e514986f382f61b14b2608-0400072025/related/2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx"
    s, h, b = get(u, timeout=120)
    print("status", s, "bytes", len(b))
    z = zipfile.ZipFile(io.BytesIO(b))
    print("parts", [n for n in z.namelist()][:20])
    ss = re.findall(r"<t[^>]*>([^<]*)</t>", z.read("xl/sharedStrings.xml").decode("utf-8", "replace"))
    print("shared strings first 40:", ss[:40])
    sh = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    print("sheet1 rows:", sh.count("<row"), "first 1500 chars:", sh[:1500])
try_("ggfr", ggfr)

print("== WRI power plants")
try_("wri", lambda: print(get("https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv", rng="bytes=0-400")[2].decode()))

print("== Economist output-data listing")
def econ():
    s, h, b = get("https://api.github.com/repos/TheEconomist/the-economist-war-fire-model/contents/output-data")
    for f in json.loads(b):
        print(f["name"], f.get("size"))
try_("econ", econ)
try_("econ tail", lambda: print(get("https://raw.githubusercontent.com/TheEconomist/the-economist-war-fire-model/master/output-data/ukraine_war_fires.csv", rng="bytes=0-700")[2].decode("utf-8", "replace")))

print("== Overpass")
def overpass():
    q = '[out:json][timeout:60];(way["aeroway"="apron"](around:4000,25.117,51.315);way["landuse"="military"](around:4000,25.117,51.315););out center tags;'
    s, h, b = get("https://overpass-api.de/api/interpreter", data=("data=" + urllib.parse.quote(q)).encode(), timeout=120)
    els = json.loads(b)["elements"]
    print("Al Udeid aprons/military ways:", len(els), [ (e.get("tags", {}).get("aeroway") or e.get("tags", {}).get("landuse"), e.get("tags", {}).get("name")) for e in els][:15])
import urllib.parse
try_("overpass", overpass)

print("== Planetary Computer / Earth Search")
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
def stac(url, coll, bbox, dt):
    body = {"collections": [coll], "bbox": bbox, "datetime": dt, "limit": 250}
    s, h, b = get(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, timeout=120)
    return json.loads(b).get("features", [])
SITES = {"al_udeid": (25.117, 51.315), "nsa_bahrain": (26.205, 50.610), "diego_garcia": (-7.313, 72.411), "olenya": (68.152, 33.464), "engels": (51.481, 46.200), "isfahan": (32.751, 51.861)}
for n, (la, lo) in SITES.items():
    bb = [lo - 0.01, la - 0.01, lo + 0.01, la + 0.01]
    def one(n=n, bb=bb):
        for dt in ("2025-05-01T00:00:00Z/2025-07-15T23:59:59Z", "2026-08-15T00:00:00Z/2026-10-15T23:59:59Z"):
            s1 = stac(STAC, "sentinel-1-rtc", bb, dt)
            orb = {}
            for f in s1:
                p = f["properties"]; k = (p.get("sat:orbit_state", "?")[:1].upper() + str(p.get("sat:relative_orbit")))
                orb[k] = orb.get(k, 0) + 1
            print(n, dt[:10], "S1 RTC", len(s1), "orbits", orb, "platforms", sorted({f["properties"].get("platform") for f in s1}), "latest", max((f["properties"]["datetime"][:10] for f in s1), default=None), flush=True)
            if s1: print("   assets", sorted(s1[0]["assets"].keys()))
            s2 = stac(STAC, "sentinel-2-l2a", bb, dt)
            print(n, dt[:10], "S2 L2A", len(s2), "cc<20", sum(1 for f in s2 if f["properties"].get("eo:cloud_cover", 100) < 20), "latest", max((f["properties"]["datetime"][:10] for f in s2), default=None), flush=True)
            if s2: print("   assets", sorted(s2[0]["assets"].keys()))
    try_(n, one)
def es():
    f = stac("https://earth-search.aws.element84.com/v1/search", "sentinel-2-c1-l2a", [51.30, 25.10, 51.33, 25.13], "2026-09-01T00:00:00Z/2026-10-15T23:59:59Z")
    print("earth-search c1 al_udeid", len(f), "latest", max((x["properties"]["datetime"][:10] for x in f), default=None), sorted(f[0]["assets"].keys()) if f else None)
try_("earthsearch", es)
def sign():
    s, h, b = get("https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a")
    print("sas token ok", s, len(b))
try_("sas", sign)
print("== done")
