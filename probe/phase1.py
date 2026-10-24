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
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": S.C.USER_AGENT if hasattr(S, "C") else "warwatch/0.3"})
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


@step("gfw_presence_vessels")
def _():
    prm = {"spatial-resolution": "HIGH", "temporal-resolution": "ENTIRE", "group-by": "VESSEL_ID", "datasets[0]": "public-global-presence:latest",
           "date-range": f"{END - dt.timedelta(days=7)},{END}", "format": "JSON"}
    p = post("https://gateway.api.globalfishingwatch.org/v3/4wings/report?" + urllib.parse.urlencode(prm), {"geojson": {"type": "Polygon", "coordinates": HORMUZ}}, GFW, 180)
    rows = [x for e in p.get("entries", []) for v in e.values() for x in v]
    return {"rows": len(rows), "sample": rows[:3], "keys": sorted({k for r in rows[:50] for k in r})}


json.dump(OUT, open(os.path.join(ROOT, "probe", "out.json"), "w"), indent=1, default=str)
