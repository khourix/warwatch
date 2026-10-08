#!/usr/bin/env python3
"""One-off runner probe, round 5. Prints a report; changes nothing."""
import collections, datetime as dt, gzip, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warwatch"))
import sources as S, config as C  # noqa: E402
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"}
def hdr(t): print(f"\n===== {t} =====", flush=True)
def get(u, n=4000, h=None):
    return urllib.request.urlopen(urllib.request.Request(u, headers=h or UA), timeout=30).read(n)

hdr("NOTAM: Ukraine, Yemen, Libya by location prefix, and date-window query")
host, tok = S.nms_token(os.environ["FAA_CLIENT_ID"], os.environ["FAA_CLIENT_SECRET"])
items = S.nms_bulk(host, tok)
items = items.get("data", {}).get("geojson", []) if isinstance(items, dict) and isinstance(items.get("data"), dict) else (items.get("features", []) if isinstance(items, dict) else items)
nots = [f["properties"]["coreNOTAMData"]["notam"] for f in items if isinstance(f, dict) and "properties" in f]
cut = str(dt.date.today() - dt.timedelta(days=30))
for name, pref in (("ukraine", "UK"), ("yemen", "OY"), ("libya", "HL"), ("iran", "OI"), ("israel", "LL")):
    m = [n for n in nots if str(n.get("location", ""))[:2] == pref or str(n.get("icaoLocation", ""))[:2] == pref]
    r = [n for n in m if str(n.get("issued", ""))[:10] >= cut]
    print(name, "by location prefix", pref, "total", len(m), "30d", len(r), "firs", collections.Counter(n.get("affectedFir") for n in m).most_common(6),
          "parse_nms", S.parse_nms([{"properties": {"coreNOTAMData": {"notam": n}}} for n in m], dt.date.today()))
    for n in sorted(m, key=lambda n: str(n.get("issued")))[-3:]:
        print("   ", n.get("issued"), n.get("affectedFir"), n.get("location"), n.get("selectionCode"), str(n.get("text"))[:100].replace("\n", " "))
ux = [n for n in nots if n.get("affectedFir") == "UKXX"]
print("UKXX issued:", sorted(str(n.get("issued"))[:10] for n in ux)[:3], "...", sorted(str(n.get("issued"))[:10] for n in ux)[-3:])
print("expiry check: share with effectiveEnd in past:", sum(1 for n in nots if str(n.get("effectiveEnd", "9999"))[:10] < str(dt.date.today())), "of", len(nots))
# does the date-window query return expired/purged notams from earlier weeks?
time.sleep(2)
for s, e in (("2026-09-01T00:00:00Z", "2026-09-08T00:00:00Z"), ("2026-06-01T00:00:00Z", "2026-06-08T00:00:00Z")):
    try:
        q = {"classification": "INTERNATIONAL", "effectiveStartDate": s, "effectiveEndDate": e}
        req = urllib.request.Request(host + "/nmsapi/v1/notams?" + urllib.parse.urlencode(q), headers={"Authorization": "Bearer " + tok, "nmsResponseFormat": "GEOJSON"})
        raw = urllib.request.urlopen(req, timeout=200).read()
        if raw[:2] == b"\x1f\x8b": raw = gzip.decompress(raw)
        j = json.loads(raw); dd = j.get("data", {}).get("geojson", []) if isinstance(j.get("data"), dict) else j.get("features", [])
        iss = sorted(str(f["properties"]["coreNOTAMData"]["notam"].get("issued", ""))[:10] for f in dd if "properties" in f)
        ee = sorted(str(f["properties"]["coreNOTAMData"]["notam"].get("effectiveEnd", ""))[:10] for f in dd if "properties" in f)
        print("window", s[:10], e[:10], "->", len(dd), "issued", iss[:1], iss[-1:], "effEnd min", ee[:1])
    except urllib.error.HTTPError as ex: print("window", s[:10], "HTTP", ex.code, ex.read(200))
    except Exception as ex: print("window", s[:10], "ERR", str(ex)[:100])
    time.sleep(3)

hdr("PizzINT: places and routes")
p = json.loads(get("https://www.pizzint.watch/api/dashboard-data", 400000))
for d in p["data"]: print({k: str(v)[:60] for k, v in d.items() if k in ("name", "place_id", "current_popularity", "percentage_of_usual", "is_spike", "recent_hour_popularity", "category", "type")}, sorted(d.keys())[:14])
html = get("https://www.pizzint.watch/", 600000).decode("utf-8", "replace")
print("routes in homepage:", sorted(set(re.findall(r'/api/[A-Za-z0-9_/\-]+', html)))[:30])
print("mentions bar:", len(re.findall(r'(?i)gay|freddie|bar index', html)))
for sub in ("/api/gdelt", "/api/bars", "/api/gay-bars", "/api/dashboard-data?category=bars"):
    try: print(sub, len(get("https://www.pizzint.watch" + sub, 2000)))
    except Exception as ex: print(sub, str(ex)[:50])

hdr("Ship sources")
for n, u in (("worldmonitor hormuz", "https://www.worldmonitor.app/api/supply-chain/hormuz-tracker"),):
    try: print(n, get(u, 3500).decode("utf-8", "replace"))
    except Exception as ex: print(n, ex)
for n, u in (("shipfinder robots", "https://www.shipfinder.com/robots.txt"), ("tankermap robots", "https://tankermap.com/robots.txt"), ("vesselfinder robots", "https://www.vesselfinder.com/robots.txt")):
    try: print(n, get(u, 600).decode("utf-8", "replace").replace("\n", " | ")[:500])
    except Exception as ex: print(n, str(ex)[:60])
for n, u in (("shipfinder home", "https://www.shipfinder.com/"), ("tankermap home", "https://tankermap.com/")):
    try:
        h = get(u, 300000).decode("utf-8", "replace")
        print(n, "title:", re.findall(r"<title>(.*?)</title>", h, re.S)[:1], "api/ws links:", sorted(set(re.findall(r'(?:https?:)?//[A-Za-z0-9.\-/]*(?:api|ws|wss|stream)[A-Za-z0-9.\-/_?=]*', h)))[:10], "terms:", re.findall(r'(?i)(?:terms|api|developer|free)[^<]{0,60}', h)[:5])
    except Exception as ex: print(n, str(ex)[:60])

hdr("Freight indices (public pages)")
for n, u in (("FBX api guess", "https://fbx.freightos.com/api/lane/FBX01"), ("NY Fed GSCPI csv", "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"),
             ("oilpriceapi demo", "https://api.oilpriceapi.com/v1/demo/prices"), ("SCFI page", "https://en.sse.net.cn/indices/scfinew.jsp"), ("Drewry page", "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry")):
    try:
        b = get(u, 400000); t = b.decode("utf-8", "replace")
        print(f"{n:20} {len(b)}B", re.findall(r"(?i)(?:WCI|SCFI|composite)[^<]{0,80}\d[\d,\.]{2,}", t)[:3] or t[:160].replace("\n", " "))
    except urllib.error.HTTPError as ex: print(f"{n:20} HTTP {ex.code}")
    except Exception as ex: print(f"{n:20} ERR {str(ex)[:60]}")
