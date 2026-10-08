#!/usr/bin/env python3
"""One-off runner probe: which data routes work from a GitHub runner. Prints a report; changes nothing."""
import json, os, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warwatch"))
import sources as S  # noqa: E402

def hdr(t): print(f"\n===== {t} =====", flush=True)

# 1. Yahoo vs FRED
CAND = [("vix", "^VIX", "VIXCLS"), ("diesel_nyh", "HO=F", "DDFUELNYH"), ("brent", "BZ=F", "DCOILBRENTEU"),
        ("eu_gas(TTF)", "TTF=F", "PNGASEUUSDM"), ("wheat", "ZW=F", "PWHEAMTUSDM"), ("copper", "HG=F", "PCOPPUSDM"),
        ("fx_twd", "TWD=X", "DEXTAUS"), ("fx_krw", "KRW=X", "DEXKOUS"), ("fx_inr", "INR=X", "DEXINUS"),
        ("jet_fuel_gulf?", "JET=F", "DJFUELUSGULF"), ("natgas HH", "NG=F", None), ("USO", "USO", None)]
hdr("Yahoo chart endpoint vs FRED (last observation date, rows)")
fk = os.environ.get("FRED_API_KEY", "")
for name, ysym, fred in CAND:
    y = f = "-"
    try:
        p = S.fetch_yahoo(ysym)
        y = f"OK n={len(p)} last={p[-1][0]} v={p[-1][1]:.4g}" if p else "EMPTY"
    except urllib.error.HTTPError as e:
        y = f"HTTP {e.code}"
    except Exception as e:
        y = f"ERR {str(e)[:80]}"
    if fred and fk:
        try:
            q = S.fetch_fred(fred, fk, days=3300); f = f"OK n={len(q)} last={q[-1][0]}" if q else "EMPTY"
        except Exception as e:
            f = f"ERR {str(e)[:60]}"
    print(f"{name:16} yahoo[{ysym:7}] {y:45} | fred[{fred}] {f}", flush=True)
    time.sleep(1)
# long history from Yahoo
hdr("Yahoo range=max depth")
for ysym in ("BZ=F", "^VIX", "TWD=X"):
    try:
        req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?range=max&interval=1d",
                                     headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"})
        p = S.parse_yahoo(json.loads(urllib.request.urlopen(req, timeout=40).read()))
        print(ysym, "n=", len(p), "first", p[0][0], "last", p[-1][0])
    except Exception as e:
        print(ysym, "ERR", str(e)[:100])

# 2. NOTAM
hdr("FAA NMS sign-in")
cid, sec = os.environ.get("FAA_CLIENT_ID", ""), os.environ.get("FAA_CLIENT_SECRET", "")
print("keys present:", bool(cid), bool(sec))
if cid and sec:
    for host in S.NMS_HOSTS:
        try:
            os.environ["NMS_HOST"] = host
            h, tok = S.nms_token(cid, sec)
            print(host, "sign-in OK")
        except Exception as e:
            print(host, "FAIL", str(e)[:150])

# 3. AIS in the three chokepoint regions
hdr("aisstream.io / Open Waters sample (60 s) per region")
import osint  # noqa: E402
BOX = {"hormuz_gulf": (22, 30, 47, 60), "red_sea_aden": (11, 22, 37, 46), "east_med": (30, 37, 26, 37), "suez_bab": (12, 31, 32, 44)}
for label, tok_name, host, path in (("aisstream", "AISSTREAM_API_KEY", "stream.aisstream.io", "/v0/stream"),
                                    ("openwaters", "OPENWATERS_AIS_TOKEN", "ais.openwaters.io", "/v1/stream")):
    key = os.environ.get(tok_name, "")
    if not key:
        print(label, "no key"); continue
    for rn, b in BOX.items():
        try:
            ships = osint.fetch_aisstream(key, [b], seconds=45, host=host, path=path)
            print(f"{label:11} {rn:12} ships={len(ships)}", flush=True)
        except Exception as e:
            print(f"{label:11} {rn:12} ERR {str(e)[:100]}", flush=True)

# 4. Candidate new routes (no key): reachability only
hdr("Reachability of candidate sources")
URLS = {"UCDP api": "https://ucdpapi.pcr.uu.se/api/gedevents/25.1?pagesize=1",
        "Digitraffic AIS": "https://meri.digitraffic.fi/api/ais/v1/locations?from=0",
        "IMF PortWatch chokepoints": "https://portwatch.imf.org/",
        "Kpler/MarineTraffic": "https://www.marinetraffic.com/",
        "Gdelt": "https://api.gdeltproject.org/api/v2/doc/doc?query=hormuz&mode=artlist&format=json&maxrecords=1",
        "Metaculus": "https://www.metaculus.com/api/",
        "Polymarket": "https://gamma-api.polymarket.com/markets?limit=1",
        "EIA": "https://api.eia.gov/v2/", "Stooq": "https://stooq.com/q/d/l/?s=cl.f&i=d",
        "ECB SDW": "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=1&format=jsondata",
        "Cboe VIX csv": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
        "TTF ICE": "https://www.ice.com/", "Sentinel/Copernicus": "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$top=1",
        "GFW": "https://gateway.api.globalfishingwatch.org/v3/datasets"}
for n, u in URLS.items():
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=25)
        print(f"{n:28} {r.status} {len(r.read(2000))}B")
    except urllib.error.HTTPError as e:
        print(f"{n:28} HTTP {e.code}")
    except Exception as e:
        print(f"{n:28} ERR {str(e)[:70]}")

# 5. what the live dashboard currently reports as failing
hdr("Live dashboard: non-ok series")
try:
    d = json.loads(urllib.request.urlopen("https://khourix.github.io/warwatch/index.json", timeout=40).read())
    ser = d.get("series") or d.get("data", {}).get("series") or []
    print("keys:", list(d)[:15], "series:", len(ser))
    bad = [s for s in ser if s.get("status") not in ("ok",)]
    from collections import Counter
    print(Counter(s.get("status") for s in ser))
    for s in bad:
        print(f"{s.get('status'):13} {s.get('id'):26} {str(s.get('error') or s.get('er'))[:110]}")
    stale = [s for s in ser if s.get("stale")]
    print("stale:", [(s["id"], s["stale"]) for s in stale])
except Exception as e:
    print("ERR", e)
