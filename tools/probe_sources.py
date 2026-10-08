#!/usr/bin/env python3
"""One-off runner probe, round 4. Prints a report; changes nothing."""
import collections, datetime as dt, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warwatch"))
import sources as S, config as C  # noqa: E402
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"}
def hdr(t): print(f"\n===== {t} =====", flush=True)
def get(u, n=4000, h=None):
    return urllib.request.urlopen(urllib.request.Request(u, headers=h or UA), timeout=30).read(n)

hdr("NOTAM bulk diagnosis")
cid, sec = os.environ.get("FAA_CLIENT_ID", ""), os.environ.get("FAA_CLIENT_SECRET", "")
try:
    host, tok = S.nms_token(cid, sec)
    items = S.nms_bulk(host, tok)
    if isinstance(items, dict):
        items = items.get("data", {}).get("geojson", []) if isinstance(items.get("data"), dict) else items.get("features", [])
    print("total items", len(items))
    nots = []
    for f in items:
        try: nots.append(f["properties"]["coreNOTAMData"]["notam"])
        except Exception: pass
    print("notams", len(nots), "sample keys", sorted(nots[0].keys()) if nots else None)
    issued = sorted(str(n.get("issued", ""))[:10] for n in nots if n.get("issued"))
    print("issued min/max", issued[:1], issued[-1:])
    byy = collections.Counter(d[:7] for d in issued); print("issued by month (last 14):", sorted(byy.items())[-14:])
    fir = collections.Counter(n.get("affectedFir") for n in nots)
    print("distinct affectedFir", len(fir), "none:", fir.get(None))
    for th, locs in C.FIRS.items():
        mine = [n for n in nots if n.get("affectedFir") in locs]
        r30 = [n for n in mine if str(n.get("issued", ""))[:10] >= str(dt.date.today() - dt.timedelta(days=30))]
        print(f"{th:12} fir_hits={ {l: fir.get(l, 0) for l in locs} } 30d={len(r30)} parse_nms={S.parse_nms([{'properties':{'coreNOTAMData':{'notam':n}}} for n in mine], dt.date.today())}")
    print("FIR codes that start with UK/OY/HL/OI/OS/RK in the load:", {k: v for k, v in fir.items() if k and k[:2] in ("UK", "OY", "HL", "OI", "OS", "RK", "UM", "LL")})
    uk = [n for n in nots if str(n.get("affectedFir", "")).startswith("UK") or str(n.get("location", "")).startswith("UK")]
    print("UK* notams by affectedFir/location:", collections.Counter((n.get("affectedFir"), n.get("location")) for n in uk).most_common(8))
    for n in uk[:3]: print({k: (str(v)[:120]) for k, v in n.items() if k in ("id", "issued", "affectedFir", "location", "selectionCode", "type", "text")})
    # does the API accept a start-date filter for older ones?
    for q in ({"classification": "INTERNATIONAL", "effectiveStartDate": "2026-09-01T00:00:00Z"},
              {"classification": "INTERNATIONAL", "lastUpdatedDate": "2026-09-01T00:00:00Z"},
              {"location": "UKBV"}, {"location": "OYSC"}, {"location": "HLLL"}):
        try:
            req = urllib.request.Request(host + "/nmsapi/v1/notams?" + urllib.parse.urlencode(q), headers={"Authorization": "Bearer " + tok, "nmsResponseFormat": "GEOJSON"})
            raw = urllib.request.urlopen(req, timeout=120).read()
            import gzip
            if raw[:2] == b"\x1f\x8b": raw = gzip.decompress(raw)
            j = json.loads(raw); dd = j.get("data", {}).get("geojson", []) if isinstance(j.get("data"), dict) else j.get("features", [])
            iss = sorted(str(f["properties"]["coreNOTAMData"]["notam"].get("issued", ""))[:10] for f in dd if "properties" in f)
            print("query", q, "->", len(dd), "issued range", iss[:1], iss[-1:], "top keys", list(j)[:6])
        except urllib.error.HTTPError as e:
            print("query", q, "-> HTTP", e.code, e.read(200))
        except Exception as e:
            print("query", q, "-> ERR", str(e)[:120])
except Exception as e:
    print("NOTAM probe failed:", e)

hdr("Tiingo")
tk = os.environ.get("TIINGO_API_KEY", "")
print("key present:", bool(tk))
if tk:
    def tj(u):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u + ("&" if "?" in u else "?") + "token=" + tk, headers={"Content-Type": "application/json"}), timeout=30).read())
        except urllib.error.HTTPError as e: return f"HTTP {e.code} {e.read(120)}"
        except Exception as e: return f"ERR {e}"
    for sym in ("SPY", "BNO", "USO", "WEAT", "CPER", "UNG", "STNG", "ZIM", "GLD", "VIXY", "^VIX", "VIX", "BZ=F", "CL", "TTF"):
        r = tj(f"https://api.tiingo.com/tiingo/daily/{sym}/prices?startDate=2026-09-25")
        print(f"daily {sym:6}", (f"n={len(r)} last={r[-1]['date'][:10]} close={r[-1]['close']}" if isinstance(r, list) and r else r if isinstance(r, str) else r), flush=True)
    for sym in ("usdtwd", "usdkrw", "usdinr", "usdils", "usdpln", "eurusd", "xauusd", "xagusd", "usdcny", "usdsek", "usdrub"):
        r = tj(f"https://api.tiingo.com/tiingo/fx/{sym}/prices?startDate=2026-09-25&resampleFreq=1day")
        print(f"fx    {sym:7}", (f"n={len(r)} last={r[-1]['date'][:10]} close={r[-1].get('close')}" if isinstance(r, list) and r else r), flush=True)
    r = tj("https://api.tiingo.com/tiingo/fx/top?tickers=usdtwd,usdkrw")
    print("fx top", str(r)[:300])
    r = tj("https://api.tiingo.com/api/test"); print("test", str(r)[:100])
    r = tj("https://api.tiingo.com/tiingo/daily/BNO/prices?startDate=2018-01-01"); print("BNO since 2018 n=", len(r) if isinstance(r, list) else r)

hdr("PizzINT payload (what places and categories exist)")
try:
    p = json.loads(get("https://www.pizzint.watch/api/dashboard-data", 400000))
    print("top keys", list(p)[:20])
    def walk(o, d=0, path=""):
        if d > 3: return
        if isinstance(o, dict):
            for k, v in list(o.items())[:12]:
                print("  " * d + f"{path}{k}: {type(v).__name__} {str(v)[:90] if not isinstance(v,(dict,list)) else len(v)}")
                if isinstance(v, (dict, list)) and d < 2: walk(v, d + 1)
        elif isinstance(o, list) and o: 
            print("  " * d + "[0]:", str(o[0])[:300])
    walk(p)
except Exception as e: print("ERR", e)

hdr("Reachability of ship and freight candidates")
URLS = {"worldmonitor hormuz": "https://www.worldmonitor.app/api/supply-chain/hormuz-tracker",
        "worldmonitor ais": "https://www.worldmonitor.app/api/ais-snapshot",
        "AISHub": "https://www.aishub.net/", "VesselFinder": "https://www.vesselfinder.com/",
        "TankerMap": "https://tankermap.com/", "ShipGPS": "https://www.shipgps.com/", "ShipFinder": "https://www.shipfinder.com/",
        "SeaNavigator": "https://seanavigator.weathernews.com/", "SeaVantage": "https://www.seavantage.com/strait-of-hormuz-24-7-live-monitoring",
        "Freightos FBX": "https://fbx.freightos.com/", "Drewry WCI": "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry",
        "Flexport OTI": "https://www.flexport.com/data/ocean-timeliness-indicator/", "NY Fed GSCPI": "https://www.newyorkfed.org/research/policy/gscpi",
        "IMF PortWatch hormuz": "https://portwatch.imf.org/", "Copernicus": "https://dataspace.copernicus.eu/",
        "Google Maps popular times via pizzint": "https://www.pizzint.watch/", "SerpApi": "https://serpapi.com/", "Outscraper": "https://outscraper.com/",
        "Shanghai SCFI": "https://en.sse.net.cn/indices/scfinew.jsp", "Baltic (BDI) via Stooq": "https://stooq.com/q/?s=bdi"}
for n, u in URLS.items():
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20); b = r.read(1500)
        print(f"{n:34} {r.status} {len(b)}B {r.headers.get('content-type','')[:30]} {b[:90]!r}")
    except urllib.error.HTTPError as e: print(f"{n:34} HTTP {e.code}")
    except Exception as e: print(f"{n:34} ERR {str(e)[:60]}")
