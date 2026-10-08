#!/usr/bin/env python3
"""One-off runner probe, round 2. Prints a report; changes nothing."""
import csv, io, json, os, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warwatch"))
import sources as S  # noqa: E402
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"}
def hdr(t): print(f"\n===== {t} =====", flush=True)
def get(u, n=3000):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read(n)

hdr("Twelve Data free key: which symbols answer")
key = os.environ.get("TWELVEDATA_API_KEY", "")
for sym in ("USD/TWD", "WEAT", "CPER", "BNO", "VIX", "XBR/USD", "TTF", "SPY"):
    try:
        p = S.fetch_twelvedata(sym, key)
        print(f"{sym:9} OK n={len(p)} last={p[-1]}", flush=True)
    except Exception as e:
        print(f"{sym:9} FAIL {str(e)[:110]}", flush=True)

hdr("Cboe VIX history csv")
try:
    t = urllib.request.urlopen(urllib.request.Request("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", headers=UA), timeout=40).read().decode()
    r = list(csv.reader(io.StringIO(t))); print(len(r), r[0], r[-1])
except Exception as e: print("ERR", e)

hdr("Frankfurter (ECB) currencies")
try:
    print(json.loads(get("https://api.frankfurter.dev/v1/currencies"))) 
except Exception as e: print("ERR", e)

hdr("EIA open data (no key)")
for u in ("https://api.eia.gov/v2/petroleum/pri/spt/data/?frequency=daily&data[0]=value&facets[series][]=RBRTE&length=1",
          "https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls"):
    try: print(u[:70], "->", len(get(u)))
    except urllib.error.HTTPError as e: print(u[:70], "HTTP", e.code)
    except Exception as e: print(u[:70], "ERR", str(e)[:60])

hdr("OpenWaters handshake")
import osint  # noqa: E402
tok = os.environ.get("OPENWATERS_AIS_TOKEN", "")
import socket, ssl, base64
for host, path in (("ais.openwaters.io", "/v1/stream"), ("ais.openwaters.io", "/")):
    try:
        ctx = ssl.create_default_context(); s = ctx.wrap_socket(socket.create_connection((host, 443), timeout=15), server_hostname=host)
        k = base64.b64encode(os.urandom(16)).decode()
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {k}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        print(host, path, s.recv(600)[:300])
    except Exception as e: print(host, path, "ERR", str(e)[:80])

hdr("Live dashboard: non-ok and stale series")
d = json.loads(get("https://khourix.github.io/warwatch/index.json", 5_000_000))
ser = d["series"]; print(type(ser), list(ser)[:3] if isinstance(ser, dict) else "")
items = ser.items() if isinstance(ser, dict) else [(x.get("id"), x) for x in ser]
from collections import Counter
print(Counter((v.get("status") if isinstance(v, dict) else "?") for _, v in items))
for k, v in items:
    if isinstance(v, dict) and (v.get("status") not in ("ok", None) or v.get("stale")):
        print(f"{str(v.get('status')):14} {k:28} {str(v.get('error') or v.get('er') or '')[:90]} stale={v.get('stale')}")
