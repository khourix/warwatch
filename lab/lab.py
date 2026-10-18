"""Temporary lab: marked base images and the fire-pass image on a runner (network). Removed before the PR is final."""
import datetime as dt, json, os, sys, urllib.request
sys.path.insert(0, "warwatch")
os.environ["WARWATCH_CHIPS"] = "lab/out"
import imagery as I
import basewatch as B
today = dt.datetime.now(dt.timezone.utc).date()
sites = {s["id"]: s for s in B.load_bases()}
res = {}
for sid in sys.argv[1].split(","):
    s = sites[sid]
    try:
        oo = B.optical_rows(s, (today - dt.timedelta(days=90)).isoformat(), today.isoformat(), 6, latest=True, seen=None) or []
    except Exception as e:
        print(sid, "optical failed", repr(e)[:200]); oo = []
    wins = B.windows(s) or [(B.site_bbox(s), [])]
    box = (min(b[0] for b, _ in wins), min(b[1] for b, _ in wins), max(b[2] for b, _ in wins), max(b[3] for b, _ in wins))
    ri = [it for it in I.stac_search("sentinel-1-rtc", box, (today - dt.timedelta(days=70)).isoformat(), today.isoformat()) if I.has(it, "vv")]
    c, mk = B.chips(s, oo, ri)
    res[sid] = {"chips": c, "marks": mk}
    print(sid, json.dumps(res[sid]), flush=True)
json.dump(res, open("lab/out/res.json", "w"), indent=1)
# fire pass image from NASA GIBS
for name, lat, lon, d in (("fire1", 30.55, 47.30, (today - dt.timedelta(days=2)).isoformat()),):
    lay = "VIIRS_SNPP_CorrectedReflectance_TrueColor,VIIRS_SNPP_Thermal_Anomalies_375m_All,VIIRS_NOAA20_Thermal_Anomalies_375m_All,VIIRS_NOAA21_Thermal_Anomalies_375m_All"
    u = f"https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS={lay}&STYLES=&CRS=EPSG:4326&BBOX={lat-.12},{lon-.12},{lat+.12},{lon+.12}&WIDTH=512&HEIGHT=512&FORMAT=image/jpeg&TIME={d}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=I.UA), timeout=60)
        open(f"lab/out/{name}.jpg", "wb").write(r.read()); print(name, r.status, r.headers.get("Content-Type"), r.headers.get("Access-Control-Allow-Origin"))
    except Exception as e:
        print(name, "gibs failed", repr(e)[:300])
