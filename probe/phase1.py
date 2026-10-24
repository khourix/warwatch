"""Temporary probe for the data-coverage Phase 1 (removed before the PR). Prints shapes and counts, never secrets."""
import datetime as dt
import gzip
import io
import json
import os
import sys
import tarfile
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "warwatch"))
import osint  # noqa: E402
import sources as S  # noqa: E402

OUT = {}
HORMUZ = [[[55.0, 25.0], [57.5, 25.0], [57.5, 27.5], [55.0, 27.5], [55.0, 25.0]]]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"


def step(name):
    def wrap(fn):
        t0 = time.time()
        try:
            OUT[name] = fn()
        except Exception as e:  # noqa: BLE001
            OUT[name] = {"error": repr(e)[:400]}
        print(f"== {name} ({time.time() - t0:.0f}s)\n" + json.dumps(OUT[name], indent=1, default=str)[:6000], flush=True)
        return fn
    return wrap


def post(url, body, token, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


GFW = os.environ.get("GFW_TOKEN", "")
END = dt.date.today()
START = END - dt.timedelta(days=60)


@step("gfw_event_stats")
def _():
    out = {}
    for ds in ("gaps", "encounters", "loitering", "port-visits"):
        try:
            p = post("https://gateway.api.globalfishingwatch.org/v3/events/stats",
                     {"datasets": [f"public-global-{ds}-events:latest"], "startDate": str(START), "endDate": str(END),
                      "geometry": {"type": "Polygon", "coordinates": HORMUZ}, "timeseriesInterval": "DAY", "includes": ["TOTAL_COUNT", "TIME_SERIES"]}, GFW)
            ts = p.get("timeseries") or []
            out[ds] = {"keys": list(p), "numEvents": p.get("numEvents"), "numVessels": p.get("numVessels"), "ts_len": len(ts), "ts_tail": ts[-5:]}
        except Exception as e:  # noqa: BLE001
            body = getattr(e, "read", lambda: b"")()[:300]
            out[ds] = {"error": repr(e)[:200], "body": body.decode("utf-8", "replace")}
    return out


@step("gfw_event_list")
def _():
    out = {}
    for ds in ("gaps", "encounters"):
        q = urllib.parse.urlencode({"limit": 3, "offset": 0})
        p = post("https://gateway.api.globalfishingwatch.org/v3/events?" + q,
                 {"datasets": [f"public-global-{ds}-events:latest"], "startDate": str(START), "endDate": str(END),
                  "geometry": {"type": "Polygon", "coordinates": HORMUZ}}, GFW)
        out[ds] = {"keys": list(p), "total": p.get("total"), "nextOffset": p.get("nextOffset"), "first": (p.get("entries") or [None])[0]}
    return out


@step("gfw_sar")
def _():
    out = {}
    for filt in (None, "matched='false'", "matched='true'"):
        prm = {"spatial-resolution": "LOW", "temporal-resolution": "DAILY", "datasets[0]": "public-global-sar-presence:latest",
               "date-range": f"{END - dt.timedelta(days=40)},{END}", "format": "JSON"}
        if filt:
            prm["filters[0]"] = filt
        try:
            p = post("https://gateway.api.globalfishingwatch.org/v3/4wings/report?" + urllib.parse.urlencode(prm), {"geojson": {"type": "Polygon", "coordinates": HORMUZ}}, GFW, 180)
            rows = [x for e in p.get("entries", []) for v in e.values() for x in v]
            by = {}
            for x in rows:
                by[x.get("date")] = by.get(x.get("date"), 0) + (x.get("detections") or 0)
            out[str(filt)] = {"rows": len(rows), "sample": rows[:2], "by_day_tail": sorted(by.items())[-8:]}
        except Exception as e:  # noqa: BLE001
            body = getattr(e, "read", lambda: b"")()[:300]
            out[str(filt)] = {"error": repr(e)[:200], "body": body.decode("utf-8", "replace")}
    return out


@step("aisstream")
def _():
    key = os.environ.get("AISSTREAM_API_KEY", "")
    boxes = {"hormuz": (24.5, 27.8, 54.5, 58.0), "red_sea_south": (11.5, 16.5, 41.5, 45.0), "east_med": (31.0, 36.5, 32.0, 36.5),
             "black_sea": (41.0, 46.8, 27.5, 41.8), "taiwan": (21.5, 26.5, 117.0, 122.5), "baltic": (53.5, 60.5, 10.0, 30.0)}
    ships = osint.fetch_aisstream(key, list(boxes.values()), seconds=240, max_msgs=200000)
    out = {"ships": len(ships)}
    for nm, (la0, la1, lo0, lo1) in boxes.items():
        inb = [s for s in ships.values() if s["lat"] is not None and la0 <= s["lat"] <= la1 and lo0 <= s["lon"] <= lo1]
        kinds = {}
        for s in inb:
            kinds[osint.ship_kind(s["type"]) if s["type"] else "unknown"] = kinds.get(osint.ship_kind(s["type"]) if s["type"] else "unknown", 0) + 1
        out[nm] = {"n": len(inb), "kinds": kinds}
    return out


def get_text(url, headers=None):
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read(3000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(600).decode("utf-8", "replace")


@step("adsb_archive_headers")
def _():
    tok = os.environ.get("GITHUB_TOKEN", "")
    rel = S.get("https://api.github.com/repos/adsblol/globe_history_2026/releases?per_page=3", headers={"Authorization": "Bearer " + tok})
    r = rel[0]
    assets = sorted([a for a in r["assets"] if ".tar." in a["name"]], key=lambda a: a["name"])
    url = assets[0]["browser_download_url"]
    resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "warwatch"}), timeout=120)
    tf = tarfile.open(fileobj=resp, mode="r|")
    out = {"tag": r["tag_name"], "assets": [(a["name"], a["size"]) for a in assets], "samples": []}
    n = 0
    for m in tf:
        if not m.isfile() or "trace_full" not in m.name:
            continue
        b = tf.extractfile(m).read()
        if b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        d = json.loads(b)
        n += 1
        tr = d.get("trace", [])
        det = next((p for p in tr if len(p) > 8 and isinstance(p[8], dict)), None)
        if len(out["samples"]) < 6 and d.get("t"):
            out["samples"].append({"keys": [k for k in d if k != "trace"], "hdr": {k: d[k] for k in d if k != "trace"}, "n": len(tr), "p0": tr[:2], "det": det,
                                   "ground": sum(1 for p in tr if p[3] == "ground")})
        if n >= 400:
            break
    out["read"] = n
    return out


@step("opensky_arrivals")
def _():
    import extras  # noqa: F401
    cid, sec = os.environ.get("OPENSKY_CLIENT_ID", ""), os.environ.get("OPENSKY_CLIENT_SECRET", "")
    req = urllib.request.Request("https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
                                 data=urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": cid, "client_secret": sec}).encode())
    tok = json.loads(urllib.request.urlopen(req, timeout=40).read())["access_token"]
    t1 = int(time.time()) - 86400 * 2
    rows = S.get(f"https://opensky-network.org/api/flights/arrival?airport=OTHH&begin={t1}&end={t1 + 43200}", headers={"Authorization": "Bearer " + tok})
    return {"n": len(rows), "sample": rows[:2]}


json.dump(OUT, open(os.path.join(ROOT, "probe", "out.json"), "w"), indent=1, default=str)
