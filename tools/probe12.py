import os, sys, traceback
sys.path.insert(0, "warwatch")
import sources as S
tok = os.environ.get("CLOUDFLARE_API_TOKEN", "")
for name, fn in [("http", lambda: S.fetch_radar("http/timeseries", "UA", tok)), ("flows", lambda: S.fetch_radar("netflows/timeseries", "UA", tok)),
                 ("l7", lambda: S.fetch_radar("attacks/layer7/timeseries", "UA", tok)), ("gas_ua", lambda: S.fetch_agsi("UA")), ("gas_eu", lambda: S.fetch_agsi("eu"))]:
    try:
        r = fn(); print("OK", name, len(r), r[:2], r[-2:])
    except Exception as e:
        print("ERR", name, repr(e)[:300])
import urllib.request, urllib.parse
u = "https://api.cloudflare.com/client/v4/radar/http/timeseries?" + urllib.parse.urlencode({"location": "UA", "dateRange": "24w", "aggInterval": "1d", "format": "json"})
try:
    print(urllib.request.urlopen(urllib.request.Request(u, headers={"Authorization": "Bearer " + tok, "User-Agent": "Mozilla/5.0"})).read()[:200])
except Exception as e:
    print("RAW", e, getattr(e, "read", lambda: b"")()[:300])
u = "https://agsi.gie.eu/api?country=UA&from=2026-01-01&to=2026-10-05&size=300&page=1"
try:
    print(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})).read()[:200])
except Exception as e:
    print("RAWG", e, getattr(e, "read", lambda: b"")()[:300])
