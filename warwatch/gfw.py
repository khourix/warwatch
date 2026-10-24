"""Ships from Global Fishing Watch, where free live AIS has no receivers (the Gulf, the Red Sea): dark ships on satellite radar,
loitering and port calls per theatre waters box (docs/SHIPS.md). Standard library only; needs GFW_TOKEN (free, non-commercial).

    darkships_<t>   Sentinel-1 radar detections of vessels with no matching AIS signal, per pass day (public-global-sar-presence,
                    matched='false'). Passes come every few days, so days without a pass have no value, not zero.
    darkshare_<t>   the same detections as a percent of all detections that day: robust to how much of the box a pass saw.
    loiter_<t>      loitering events that started that day (carrier vessels slowing or drifting at sea for hours).
    portcalls_<t>   port visits that started that day.

Each series keeps its whole history in the cache (the radar counts in the table gfw_sar_<t>): the first run reads from 2023-09-01 in
half-year slices, later runs re-read the last 45 days (GFW revises recent days and posts about four days late) and merge. The same calls leave the newest pass's dark-ship
cells and the last ten days' loitering events in the cache tables gfw_dark and gfw_loiter, which the map reads.
"""
import datetime as dt
import os
import urllib.parse

import store

API = "https://gateway.api.globalfishingwatch.org/v3"
START = dt.date(2023, 9, 1)
SLICE = 180          # days per 4Wings request
REREAD = 45
# Waters boxes (lat_min, lat_max, lon_min, lon_max): the Gulf and Hormuz sit in iran's box, the Red Sea and Bab el-Mandeb in yemen's.
BOX = {"iran": (23, 29, 48, 60), "yemen": (11, 22, 37, 46), "israel": (31, 36, 29, 36), "ukraine": (41, 46, 27, 41), "taiwan": (21, 27, 117, 124),
       "scs": (5, 20, 108, 121), "korea": (33, 40, 124, 131), "venezuela": (8, 14, -74, -60)}
DARK_CELLS = 150     # cells kept per theatre for the map, most detections first
LOITER_LIST = 40


def _poly(box):
    la0, la1, lo0, lo1 = box
    return {"type": "Polygon", "coordinates": [[[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]]}


def _post(path, body, token, query=None):
    import sources as S
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    return S.get(url, data=body, headers={"Authorization": "Bearer " + token}, timeout=180, retries=2)


def _slices(start, end):
    d = start
    while d <= end:
        e = min(end, d + dt.timedelta(days=SLICE - 1))
        yield d, e
        d = e + dt.timedelta(days=1)


def _window(sid, today):
    """(start, end, history kept) for a series: everything from START when the cache is empty, else the last REREAD days."""
    old = dict(store.cache_load(sid))
    end = today - dt.timedelta(days=1)
    start = START if not old else max(START, end - dt.timedelta(days=REREAD))
    return start, end, {d: v for d, v in old.items() if d < start.isoformat()}


def parse_sar(payload):
    """4Wings report rows -> {day: detections}, [(day, lat, lon, detections)]."""
    by, cells = {}, []
    for e in payload.get("entries") or []:
        for rows in e.values():
            for r in rows or []:
                d, n = (r.get("date") or "")[:10], r.get("detections") or 0
                if not d or not n:
                    continue
                by[d] = by.get(d, 0) + n
                cells.append((d, r.get("lat"), r.get("lon"), n))
    return by, cells


def _sar(th, token, start, end, matched):
    tot, cells = {}, []
    for a, b in _slices(start, end):
        q = {"spatial-resolution": "LOW", "temporal-resolution": "DAILY", "datasets[0]": "public-global-sar-presence:latest",
             "filters[0]": f"matched='{matched}'", "date-range": f"{a},{b}", "format": "JSON"}
        by, c = parse_sar(_post("/4wings/report", {"geojson": _poly(BOX[th])}, token, q))
        tot.update(by)
        cells += c
    return tot, cells


_SAR = {}


def sar(th, token, today=None):
    """{day: (dark, all)} for the theatre box, its history kept in the table gfw_sar_<t>; saves the newest pass's dark cells for the map."""
    if th in _SAR:
        return _SAR[th]
    today = today or dt.datetime.now(dt.timezone.utc).date()
    rows = {r[0]: (float(r[1]), float(r[2])) for r in store.cache_rows(f"gfw_sar_{th}") if len(r) >= 3}
    end = today - dt.timedelta(days=1)
    start = START if not rows else max(START, end - dt.timedelta(days=REREAD))
    out = {d: v for d, v in rows.items() if d < start.isoformat()}
    dark, cells = _sar(th, token, start, end, "false")
    lit, _ = _sar(th, token, start, end, "true")
    for d in set(dark) | set(lit):
        out[d] = (float(dark.get(d, 0)), float(dark.get(d, 0) + lit.get(d, 0)))
    store.cache_rows_save(f"gfw_sar_{th}", [[d, f"{dk:g}", f"{a:g}"] for d, (dk, a) in sorted(out.items())])
    cells = [c for c in cells if c[1] is not None and c[2] is not None]
    if cells:
        last = max(c[0] for c in cells)
        top = sorted((c for c in cells if c[0] == last), key=lambda c: -c[3])[:DARK_CELLS]
        keep = [r for r in store.cache_rows("gfw_dark") if r and r[0] != th]
        store.cache_rows_save("gfw_dark", keep + [[th, d, f"{la:.2f}", f"{lo:.2f}", str(n)] for d, la, lo, n in top])
    _SAR[th] = out
    return out


def darkships(th, token):
    return sorted((d, dk) for d, (dk, _) in sar(th, token).items())


def darkshare(th, token):
    return sorted((d, 100.0 * dk / a) for d, (dk, a) in sar(th, token).items() if a >= 5)


def parse_stats(payload):
    """Events stats time series -> {day: count}, zeros filled between the first and last day reported."""
    by = {(r.get("date") or "")[:10]: float(r.get("value") or 0) for r in payload.get("timeseries") or [] if r.get("date")}
    if not by:
        return {}
    d, last = dt.date.fromisoformat(min(by)), dt.date.fromisoformat(max(by))
    while d <= last:
        by.setdefault(d.isoformat(), 0.0)
        d += dt.timedelta(days=1)
    return by


def events(kind, th, token, today=None):
    """Daily count of loitering ('loitering') or port-visit ('port-visits') events in the box, with the cached history."""
    sid = {"loitering": "loiter", "port-visits": "portcalls"}[kind] + "_" + th
    today = today or dt.datetime.now(dt.timezone.utc).date()
    start, end, keep = _window(sid, today)
    out = dict(keep)
    for a, b in _slices(start, end):
        body = {"datasets": [f"public-global-{kind}-events:latest"], "startDate": str(a), "endDate": str(b + dt.timedelta(days=1)),
                "geometry": _poly(BOX[th]), "timeseriesInterval": "DAY", "includes": ["TIME_SERIES"]}
        out.update(parse_stats(_post("/events/stats", body, token)))
    if kind == "loitering":
        _loiter_list(th, token, end)
    return sorted(out.items())


def _loiter_list(th, token, end):
    body = {"datasets": ["public-global-loitering-events:latest"], "startDate": str(end - dt.timedelta(days=10)),
            "endDate": str(end + dt.timedelta(days=1)), "geometry": _poly(BOX[th])}
    p = _post("/events", body, token, {"limit": LOITER_LIST, "offset": 0, "sort": "-start"})
    rows = [r for r in store.cache_rows("gfw_loiter") if r and r[0] != th]
    for e in p.get("entries") or []:
        pos, v = e.get("position") or {}, e.get("vessel") or {}
        if pos.get("lat") is None:
            continue
        hours = (dt.datetime.fromisoformat(e["end"].replace("Z", "+00:00")) - dt.datetime.fromisoformat(e["start"].replace("Z", "+00:00"))).total_seconds() / 3600
        rows.append([th, e["start"][:16], f"{pos['lat']:.3f}", f"{pos['lon']:.3f}", v.get("name") or "", v.get("flag") or "", v.get("type") or "", f"{hours:.0f}"])
    store.cache_rows_save("gfw_loiter", rows)


def map_items():
    """Cached rows for the map: newest-pass dark-ship cells and recent loitering events."""
    dark = [{"lat": float(r[2]), "lon": float(r[3]), "n": int(r[4]), "d": r[1], "th": r[0]} for r in store.cache_rows("gfw_dark") if len(r) >= 5]
    loiter = [{"lat": float(r[2]), "lon": float(r[3]), "d": r[1], "th": r[0], "n": r[4], "flag": r[5], "k": r[6], "h": int(float(r[7] or 0))}
              for r in store.cache_rows("gfw_loiter") if len(r) >= 8]
    return dark, loiter


def token():
    return os.environ.get("GFW_TOKEN", "")
