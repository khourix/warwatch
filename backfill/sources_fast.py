"""Back-fills for FRED volatility, NASA FIRMS fires, Global Fishing Watch vessels and NGA warnings."""
import csv
import datetime as dt
import io
import os
import time
import urllib.parse

import common as K
import config as C

GFW = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
# the live catalogue's vessel-presence boxes (catalog.GFW_BOX), kept in step by tests/test_backfill.py
GFW_BOX = {"iran": (23, 29, 48, 60), "yemen": (11, 22, 37, 46), "israel": (31, 36, 29, 36), "ukraine": (41, 46, 27, 41), "taiwan": (21, 27, 117, 124),
           "scs": (5, 20, 108, 121), "korea": (33, 40, 124, 131), "venezuela": (8, 14, -74, -60)}


# ---------------------------------------------------------------- FRED: implied volatility
FRED = {"vol_ovx": "OVXCLS", "vol_gvz": "GVZCLS", "vol_vix": "VIXCLS", "vol_vix3m": "VXVCLS"}


def parse_fred(payload):
    out = {}
    for o in payload.get("observations", []):
        try:
            out[o["date"]] = float(o["value"])
        except (KeyError, ValueError):
            pass      # "." marks a holiday
    return out


def cmd_fred(key):
    got = {}
    for sid, fred_id in FRED.items():
        q = urllib.parse.urlencode({"series_id": fred_id, "api_key": key, "file_type": "json", "observation_start": "2007-01-01"})
        got[sid] = parse_fred(K.get("https://api.stlouisfed.org/fred/series/observations?" + q))
        K.log(sid, K.save(sid, got[sid]), "rows")
    # VIX over its 3-month sibling: above 1 means the front is priced above the back, which is stress
    term = {d: v / got["vol_vix3m"][d] for d, v in got["vol_vix"].items() if got["vol_vix3m"].get(d)}
    K.log("vol_vix_term", K.save("vol_vix_term", term), "rows")


# ---------------------------------------------------------------- FIRMS: thermal detections
def parse_firms_counts(text):
    """FIRMS area CSV -> {date: (detections, summed FRP in MW)}."""
    by = {}
    for r in csv.DictReader(io.StringIO(text)):
        try:
            c = by.setdefault(r["acq_date"], [0, 0.0])
            c[0] += 1
            c[1] += float(r.get("frp") or 0)
        except (KeyError, ValueError):
            pass
    return by


def firms_get(url, patience=60):
    """The key is limited to 5000 transactions per 10 minutes across all theatres at once: wait out the window instead of failing."""
    for i in range(patience):
        try:
            return K.get(url, raw=True, timeout=180).decode("utf-8", "replace")
        except RuntimeError as e:
            if "transaction limit" not in str(e):
                raise
            K.log("FIRMS limit reached, waiting 90 s", i)
            time.sleep(90)
    raise RuntimeError("FIRMS transaction limit did not clear")


def cmd_firms(key, theatre, start, end):
    """Standard-processing VIIRS (S-NPP) archive, five days per call. SP lags real time by about three months;
    the live feed's own cache covers the recent months, so the end date is capped at the archive's last day."""
    la0, la1, lo0, lo1 = C.FIRMS_BOX[theatre]
    avail = {r.split(",")[0]: r.split(",") for r in K.get(
        f"https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{key}/ALL", raw=True).decode().splitlines()}
    last = dt.date.fromisoformat(avail["VIIRS_SNPP_SP"][2])
    end = min(end, last)
    have = K.load(f"firms_{theatre}")
    cnt, frp = {}, {}
    d = start
    calls = 0
    while d <= end:
        win = [d + dt.timedelta(days=i) for i in range(5) if d + dt.timedelta(days=i) <= end]
        if all(x.isoformat() in have for x in win):
            d += dt.timedelta(days=5)
            continue
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_SP/{lo0},{la0},{lo1},{la1}/5/{d.isoformat()}"
        by = parse_firms_counts(firms_get(url))
        for x in win:
            c = by.get(x.isoformat(), [0, 0.0])
            cnt[x.isoformat()], frp[x.isoformat()] = c[0], c[1]
        calls += 1
        if calls % 40 == 0:
            K.log(theatre, d, "calls", calls)
            K.save(f"firms_{theatre}", cnt)
            K.save(f"firms_frp_{theatre}", frp)
        d += dt.timedelta(days=5)
    K.log(theatre, "firms rows", K.save(f"firms_{theatre}", cnt), K.save(f"firms_frp_{theatre}", frp), "calls", calls, "last day", last)


# ---------------------------------------------------------------- Global Fishing Watch
def gfw_report(token, dataset, box, a, b):
    la0, la1, lo0, lo1 = box
    q = urllib.parse.urlencode({"spatial-resolution": "LOW", "temporal-resolution": "DAILY", "group-by": "FLAG",
                                "datasets[0]": dataset, "date-range": f"{a},{b}", "format": "JSON"})
    body = {"geojson": {"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}}
    return K.get(GFW + "?" + q, data=body, headers={"Authorization": "Bearer " + token}, timeout=300, retries=3, wait=20)


def parse_gfw(payload, field):
    """4wings report -> {date: sum of `field` (hours for presence, detections for SAR)} over flags and cells."""
    by = {}
    for e in payload.get("entries", []):
        for rows in e.values():
            for x in rows:
                by[x["date"]] = by.get(x["date"], 0.0) + float(x.get(field) or 0)
    return by


def cmd_gfw(token, theatre, start, end):
    """AIS vessel-hours (`ais_presence_<th>`, same id as the live series) and SAR vessel detections (`sar_<th>`), 90 days a call."""
    box = GFW_BOX[theatre]
    for sid, dataset, field in (("ais_presence_" + theatre, "public-global-presence:latest", "hours"),
                                ("sar_" + theatre, "public-global-sar-presence:latest", "detections")):
        have = K.load(sid)
        d = max(start, dt.date(2017, 1, 1)) if field == "detections" else start
        out = {}
        while d <= end:
            e = min(d + dt.timedelta(days=89), end)
            if all(x.isoformat() in have for x in K.days(d, e)):
                d = e + dt.timedelta(days=1)
                continue
            by = parse_gfw(gfw_report(token, dataset, box, d.isoformat(), e.isoformat()), field)
            for x in K.days(d, e):
                out[x.isoformat()] = by.get(x.isoformat(), 0.0)    # a day with no rows is a day with no vessels
            K.log(sid, d, e, len(by), "days with data")
            K.save(sid, out)
            d = e + dt.timedelta(days=1)
        K.log(sid, "rows", K.save(sid, out))


# ---------------------------------------------------------------- NGA broadcast warnings
def cmd_nga(start, end):
    """Hazard warnings (missile, live-fire, gunnery, exercises, GPS interference, mines, drones) per theatre per day of issue.
    Active and cancelled warnings for every year are fetched, so closure areas that expired long ago are counted.
    Writes `nga_new_<th>` (issued that day) and `nga_<th>` (issued in the trailing 30 days: the live series' definition)."""
    import extras
    seen, warns = set(), []
    for year in range(start.year, end.year + 1):
        for area in ("A", "P", "12", "4"):
            for status in ("active", "cancelled"):
                q = urllib.parse.urlencode({"output": "json", "status": status, "navArea": area, "msgYear": year})
                try:
                    p = K.get("https://msi.nga.mil/api/publications/broadcast-warn?" + q, timeout=240)
                except RuntimeError as e:
                    K.log("miss", year, area, status, str(e)[:100])
                    continue
                rows = p.get("broadcast-warn", [])
                new = [w for w in rows if (w.get("navArea"), w.get("msgYear"), w.get("msgNumber")) not in seen]
                seen.update((w.get("navArea"), w.get("msgYear"), w.get("msgNumber")) for w in new)
                warns.extend(extras.parse_nga(new))
                K.log("nga", year, area, status, len(rows), "returned", len(new), "new")
    # The NGA warning database stops at 2024-05-10 (probe of 2026-10-07: nothing issued later is returned for any status or navarea),
    # so days after the newest warning are unknown, not quiet. Never write zeros for them.
    newest = max((m["issued"] for m in warns if m["issued"]), default=None)
    if newest:
        end = min(end, dt.date.fromisoformat(newest))
        K.log("NGA newest warning", newest, "- series end clipped to it")
    for th, box in C.THEATRE_BOX.items():
        per = {}
        for m in warns:
            if m["issued"] and extras.in_box(m["lat"], m["lon"], box):
                per[m["issued"]] = per.get(m["issued"], 0) + 1
        daily = {d.isoformat(): float(per.get(d.isoformat(), 0)) for d in K.days(start, end)}
        roll = {}
        for d in K.days(start, end):
            roll[d.isoformat()] = sum(daily.get((d - dt.timedelta(days=i)).isoformat(), 0.0) for i in range(30))
        # rewritten, not merged: an earlier run may have left zero-filled days after the database stops
        K.write_csv(K.path(f"nga_new_{th}"), daily)
        K.write_csv(K.path(f"nga_{th}"), {d: v for d, v in roll.items() if d >= (start + dt.timedelta(days=29)).isoformat()})
        K.log(th, "warnings", sum(per.values()))
