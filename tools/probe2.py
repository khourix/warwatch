"""Temporary probe: which other sources cover Iraq's airspace, and how far back the new-theatre feeds can be filled."""
import datetime as dt, json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, "warwatch")
import extras, sources as S, config as C

def call(url, data=None, headers=None):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers=dict({"User-Agent": "warwatch-probe"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(400000)
    except urllib.error.HTTPError as e:
        return e.code, e.read(300)
    except Exception as e:
        return 0, repr(e).encode()

# 1. OpenSky: arrivals at Iraqi airports at several depths, and live states over Iraq
cid, sec = os.environ.get("OPENSKY_CLIENT_ID", ""), os.environ.get("OPENSKY_CLIENT_SECRET", "")
st, raw = call("https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
               {"grant_type": "client_credentials", "client_id": cid, "client_secret": sec})
tok = json.loads(raw).get("access_token") if st == 200 else None
print("opensky token:", bool(tok), st, flush=True)
if tok:
    h = {"Authorization": "Bearer " + tok}
    st, raw = call("https://opensky-network.org/api/states/all?lamin=29&lamax=37.5&lomin=38.5&lomax=48.7", headers=h)
    print("opensky live states over Iraq:", st, len(json.loads(raw).get("states") or []) if st == 200 else raw[:100], flush=True)
    now = int(time.time())
    for label, days in (("2d", 2), ("30d", 30), ("120d", 120), ("400d", 400), ("1000d", 1000), ("2000d", 2000)):
        end = now - 86400 * days
        row = []
        for icao in ("ORBI", "ORER", "ORMM", "OOMS" if False else "ORNI", "OTHH"):
            st, raw = call(f"https://opensky-network.org/api/flights/arrival?airport={icao}&begin={end - 43200}&end={end}", headers=h)
            row.append(f"{icao}:{len(json.loads(raw)) if st == 200 else st}")
            time.sleep(1)
        print("opensky arrivals 12h,", label, "ago:", " ".join(row), flush=True)

# 2. Japan Coast Guard: does the list reach back before this year?
for y in (2018, 2020, 2023, 2025, 2026):
    for kind in extras.JCG_TYPES:
        try:
            import re
            t = extras._jcg_post("warnings.cgi", {"YEAR": str(y), "TYPE": kind, "LANG": "JP"})
            print("jcg", y, kind, "warnings listed:", len(re.findall(r"<tana>(\d+)</tana>", t)), flush=True)
        except Exception as e:
            print("jcg", y, kind, "ERR", str(e)[:80], flush=True)

# 3. Google News RSS: headline counts for old days
for d in ("2018-02-10", "2019-09-14", "2020-01-03", "2022-02-24", "2024-04-13", "2026-09-01"):
    try:
        print("gnews iraq", d, S.gnews_day(C.GNEWS["iraq"], dt.date.fromisoformat(d)), flush=True)
    except Exception as e:
        print("gnews iraq", d, "ERR", str(e)[:100], flush=True)
    time.sleep(2)

# 4. Bluesky search from a runner
st, raw = call("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=iraq&limit=3&since=2024-04-01T00:00:00Z&until=2024-04-02T00:00:00Z")
print("bluesky searchPosts:", st, raw[:160], flush=True)
