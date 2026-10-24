#!/usr/bin/env python3
"""Live ships from free AIS (aisstream.io), collected every 30 minutes instead of a 75-second look per build (docs/SHIPS.md).

Each run of .github/workflows/ais.yml listens for about nine minutes and folds what it hears into a small state file kept on the
orphan branch `ais` (one commit, rewritten each run, so main does not grow): every ship's last position, name, type and flag,
the last two days of track for military and law-enforcement ships, the ships seen today per region and class, and today's
crossings of watched straits. When the UTC day turns, yesterday's counts go to main as daily series in the history cache.

Free AIS has receivers in the Baltic, the Black Sea and the Mediterranean, almost none in the Gulf or the Red Sea (one ship at
Hormuz and none in the Red Sea in a four-minute test in October 2026): Global Fishing Watch covers those (gfw.py).

    python3 warwatch/aiswatch.py --state ais_state.json --seconds 540     # one collection run
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import osint  # noqa: E402
import store  # noqa: E402

# Regions counted each day (lat_min, lat_max, lon_min, lon_max) and the theatre each one's series belongs to.
REGIONS = {"baltic": ((53.5, 66.0, 9.0, 31.0), "europe_east"), "blacksea": ((40.5, 47.0, 27.0, 42.0), "ukraine"),
           "eastmed": ((30.0, 37.5, 25.0, 36.5), "israel")}
# Straits watched for crossings: two points across the water; a ship whose consecutive positions (at most 3 hours apart, within
# 30 km of the line's middle) fall on opposite sides has crossed. Named for the direction of a crossing to the left side.
GATES = {"bosporus": ((41.13, 29.03), (41.13, 29.10), "north"), "dardanelles": ((40.20, 26.38), (40.12, 26.42), "north"),
         "oresund": ((55.70, 12.62), (55.62, 12.87), "north"), "great_belt": ((55.35, 10.95), (55.28, 11.10), "north")}
CLASSES = ("navy", "law", "tanker", "cargo", "passenger", "other")
TRACK_H, KEEP_H, TRACK_STEP_S = 48, 48, 600


def boxes():
    """The subscription: the counted regions plus every theatre's waters (so the map still sees what little there is elsewhere)."""
    out = [r for r, _ in REGIONS.values()] + [(30, 46, -6, 36), (12, 32, 32, 45)]
    out += [C.BOXES[t] for t in ("iran", "yemen", "taiwan", "scs", "korea", "venezuela")]
    return out


def klass(t):
    t = int(t or 0)
    return ("navy" if t == 35 else "law" if t == 55 else "tanker" if 80 <= t <= 89 else "cargo" if 70 <= t <= 79
            else "passenger" if 60 <= t <= 69 else "other")


def region_of(la, lo):
    for r, ((la0, la1, lo0, lo1), _) in REGIONS.items():
        if la0 <= la <= la1 and lo0 <= lo <= lo1:
            return r
    return None


def _side(a, b, p):
    return (b[1] - a[1]) * (p[0] - a[0]) - (b[0] - a[0]) * (p[1] - a[1])


def crossed(gate, p0, p1):
    """None, or the direction name when the move p0 -> p1 crosses the gate line between its two points (or near them)."""
    a, b, name = gate
    s0, s1 = _side(a, b, p0), _side(a, b, p1)
    if s0 == 0 or s1 == 0 or (s0 > 0) == (s1 > 0):
        return None
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if max(_km(p0, mid), _km(p1, mid)) > 30:
        return None
    return name if s1 > 0 else "south" if name == "north" else "north"


def _km(p, q):
    import math
    dy = (p[0] - q[0]) * 111.0
    dx = (p[1] - q[1]) * 111.0 * math.cos(math.radians((p[0] + q[0]) / 2))
    return math.hypot(dx, dy)


def new_state():
    return {"v": 1, "updated": "", "day": "", "ships": {}, "today": {}, "cross": {}}


def fold(state, msgs, now=None):
    """Adds aisstream messages to the state: positions, static data, today's sets and strait crossings. Returns ships heard."""
    now = now or time.time()
    day = dt.datetime.fromtimestamp(now, dt.timezone.utc).date().isoformat()
    if state.get("day") and state["day"] != day:
        state["closed"] = {"day": state["day"], "today": state["today"], "cross": state["cross"]}
        state["today"], state["cross"] = {}, {}
    state["day"] = day
    heard = set()
    for m in msgs:
        meta = m.get("MetaData") or {}
        mm = str(meta.get("MMSI") or "")
        if not mm:
            continue
        s = state["ships"].setdefault(mm, {"n": "", "t": 0, "f": osint.MID.get(mm[:3], ""), "dest": ""})
        body = m.get("Message") or {}
        if "ShipStaticData" in body:
            sd = body["ShipStaticData"]
            s["t"] = sd.get("Type") or s["t"]
            s["dest"] = (sd.get("Destination") or "").strip()
            s["n"] = (sd.get("Name") or s["n"] or "").strip()
        s["n"] = s["n"] or (meta.get("ShipName") or "").strip()
        la, lo = meta.get("latitude"), meta.get("longitude")
        if la is None or lo is None or not (-90 <= la <= 90 and -180 <= lo <= 180):
            continue
        heard.add(mm)
        if "PositionReport" in body:
            s["sog"] = body["PositionReport"].get("Sog")
        last = (s.get("la"), s.get("lo"), s.get("ts", 0))
        if last[0] is not None and 0 < now - last[2] <= 3 * 3600:
            for g, gate in GATES.items():
                d = crossed(gate, (last[0], last[1]), (la, lo))
                if d:
                    state["cross"].setdefault(g, {}).setdefault(d, [])
                    if mm not in state["cross"][g][d]:
                        state["cross"][g][d].append(mm)
        s["la"], s["lo"], s["ts"] = round(la, 4), round(lo, 4), int(now)
        if klass(s["t"]) in ("navy", "law"):
            trk = s.setdefault("trk", [])
            if not trk or now - trk[-1][0] >= TRACK_STEP_S:
                trk.append([int(now), round(la, 3), round(lo, 3)])
            s["trk"] = [p for p in trk if now - p[0] <= TRACK_H * 3600]
    for mm in heard:
        s = state["ships"][mm]
        r = region_of(s["la"], s["lo"])
        if r:
            lst = state["today"].setdefault(r, {}).setdefault(klass(s["t"]), [])
            if mm not in lst:
                lst.append(mm)
    state["ships"] = {k: v for k, v in state["ships"].items() if now - v.get("ts", now) <= KEEP_H * 3600}
    state["updated"] = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    return heard


def counts(today, cross):
    """{series id: value} for one day: ships seen per region and class, and strait crossings per direction."""
    out = {}
    for r in REGIONS:
        for k in CLASSES:
            out[f"aisday_{k}_{r}"] = float(len((today.get(r) or {}).get(k) or []))
    for g, (_, _, name) in GATES.items():
        other = "south" if name == "north" else "north"
        for d in (name, other):
            out[f"strait_{g}_{d}"] = float(len((cross.get(g) or {}).get(d) or []))
    return out


def close_day(state):
    """Writes the finished day's counts into the history cache (one point per series). Returns the day, or None."""
    c = state.pop("closed", None)
    if not c:
        return None
    for sid, v in counts(c["today"], c["cross"]).items():
        pts = dict(store.cache_load(sid))
        pts[c["day"]] = v
        store.cache_save(sid, sorted(pts.items()), stamp=False)
    return c["day"]


def map_ships(state, hours=6, now=None):
    """Military and law-enforcement ships heard in the last few hours, for the map (shaped like extras' ship items)."""
    now = now or time.time()
    out = []
    for mm, s in (state.get("ships") or {}).items():
        k = klass(s.get("t"))
        if k not in ("navy", "law") or now - s.get("ts", 0) > hours * 3600 or s.get("la") is None:
            continue
        age = int((now - s["ts"]) / 60)
        out.append({"n": s.get("n") or mm, "k": "navy", "loc": f'{s["la"]:.2f}, {s["lo"]:.2f}', "lat": s["la"], "lon": s["lo"],
                    "g": "Military ship (AIS)" if k == "navy" else "Law enforcement vessel (AIS)", "flag": s.get("f", ""), "dest": s.get("dest", ""),
                    "spd": s.get("sog"), "d": "live" if age < 60 else f"{age // 60} h ago", "th": osint.theatre_at(s["la"], s["lo"]),
                    "note": "AIS from aisstream.io, collected every 30 minutes.", "tr": [[p[1], p[2]] for p in s.get("trk") or []][-48:]})
    return out


def load(path):
    try:
        with open(path) as f:
            st = json.load(f)
        return st if st.get("v") == 1 else new_state()
    except (OSError, ValueError):
        return new_state()


def save(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="ais_state.json")
    ap.add_argument("--seconds", type=int, default=540)
    a = ap.parse_args()
    key = os.environ.get("AISSTREAM_API_KEY")
    if not key:
        sys.exit("AISSTREAM_API_KEY is not set")
    state = load(a.state)
    batch, n, heard, t0 = [], 0, set(), time.time()
    try:
        for m in osint.ais_messages(key, boxes(), a.seconds):
            batch.append(m)
            n += 1
            if len(batch) >= 2000:
                heard |= fold(state, batch)
                batch = []
    except Exception as e:      # a dropped connection keeps what was heard
        print("stream ended:", str(e)[:120])
    heard |= fold(state, batch)
    day = close_day(state)
    save(a.state, state)
    per = {r: {k: len(v) for k, v in d.items()} for r, d in state["today"].items()}
    print(f"ais: {n} messages in {time.time() - t0:.0f}s, {len(heard)} ships heard, {len(state['ships'])} kept; today {per}; "
          f"crossings {state['cross'] and {g: {d: len(v) for d, v in x.items()} for g, x in state['cross'].items()}}; closed day {day}")


if __name__ == "__main__":
    main()
