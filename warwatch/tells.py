"""Timing tells: costly, hard-to-reverse actions that came days before strikes in the cases analysts cite
(assessment part 1). Rule based, and the page says so: each tell is yes or no for the last 7 days, with its source,
the day it fired, and its own record on our history (how often it came before an event within 7 days, and how
often it fired without one). The tells never set a level or enter the model; they gain weight only by passing the
model's gates on the forward record, which `forward_append` starts on day one.

    python3 warwatch/tells.py record     # replay every rule over the stored history -> data/tells_record.json, docs/TELLS.md
"""
import bisect
import csv
import datetime as dt
import hashlib
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402

DATA = os.path.join(HERE, "data")
RECORD = os.path.join(DATA, "tells_record.json")
FORWARD = os.path.join(os.path.dirname(HERE), "forward", "tells.csv")
WINDOW = 7          # a tell counts when it fired in the last 7 days; an event within 7 days after a firing is a hit
QUIET = 7           # a firing that follows 7 quiet days starts a new episode


_KEYS = {}


def _keys(points):
    """Sorted day labels of a points list, cached by identity (the replay asks thousands of times per list)."""
    k = _KEYS.get(id(points))
    if k is None or k[0] is not points:
        k = _KEYS[id(points)] = (points, [d for d, _ in points])
    return k[1]


def _vals(points, day, n):
    """The last n daily values up to and including `day` (missing days skipped)."""
    i = bisect.bisect_right(_keys(points), day)
    return [v for _, v in points[max(0, i - n):i]]


def _before(points, day, lo, hi):
    """Values from day-hi to day-lo (inclusive), by calendar day."""
    d0 = (dt.date.fromisoformat(day) - dt.timedelta(days=hi)).isoformat()
    d1 = (dt.date.fromisoformat(day) - dt.timedelta(days=lo)).isoformat()
    k = _keys(points)
    return [v for _, v in points[bisect.bisect_left(k, d0):bisect.bisect_right(k, d1)]]


def rose(points, day, days=WINDOW):
    """The value on `day` is above the last value at least `days` earlier (a step up within the window)."""
    now = _vals(points, day, 1)
    old = _before(points, day, days + 1, days + 60)
    return bool(now and old and now[0] > old[-1])


def surge(points, day, mult, floor, recent=3, base=90, need=30):
    """Mean of the last `recent` days at least `mult` times the median of the `base` days before them, and at least `floor`."""
    r = _before(points, day, 0, recent - 1)
    b = _before(points, day, recent, recent + base - 1)
    if len(r) < max(1, recent - 1) or len(b) < need:
        return False
    m = statistics.fmean(r)
    return m >= floor and m >= mult * statistics.median(b)


def slump(points, day, frac, recent=7, base=60, need=30):
    """Mean of the last `recent` days at most `frac` of the median of the `base` days before them."""
    r = _before(points, day, 0, recent - 1)
    b = _before(points, day, recent, recent + base - 1)
    if len(r) < recent - 2 or len(b) < need:
        return False
    med = statistics.median(b)
    return med > 0 and statistics.fmean(r) <= frac * med


# One row per tell: id, name, the series it reads (theatre substituted), the rule, and a plain sentence of the rule.
# "watch": None means no source watches it yet; it is still listed so the page shows what is missing.
TELLS = [
    {"id": "departure", "name": "US staff or families ordered or authorised to leave",
     "series": ["state_dep_{t}"], "rule": lambda p, d: rose(p, d),
     "says": "A US embassy in the theatre moved to an ordered or authorised departure in the last 7 days.",
     "cases": "Baghdad, Bahrain and Kuwait 11 Jun 2025, strikes on Iran 13 Jun; Lebanon 23 Feb 2026, strikes 28 Feb.",
     "note": "The history is weekly archive copies of the advisory pages, so it mostly sees a departure after the event; the live feed sees it the same day."},
    {"id": "leave", "name": "US raises its advisory and the UK changes its advice",
     "series": ["state_{t}", "fcdo_{t}"],
     "rule": lambda p, q, d: rose(p, d) and sum(_before(q, d, 0, WINDOW - 1)) > 0,
     "says": "The US raised a theatre country's travel advisory in the last 7 days, and the UK updated its advice in the same week.",
     "cases": "About a dozen governments told citizens to leave Ukraine in mid-February 2022.",
     "note": "The US side of the history is weekly archive copies, so a raise shows up up to a week late."},
    {"id": "airlines", "name": "Airliners thin out",
     "series": ["civil_{t}"], "rule": lambda p, d: slump(p, d, 0.6),
     "says": "Airliners in the air near the theatre fell to 60% or less of the usual count over the last 7 days.",
     "cases": "Lufthansa dropped Tehran 2 days before Iran's April 2024 attack; six airlines left Venezuela after 21 Nov 2025."},
    {"id": "tankers", "name": "Tankers parked forward",
     "series": ["adsb_{t}_tanker"], "rule": lambda p, d: surge(p, d, 3, 4),
     "says": "Aerial tankers over the theatre averaged at least 4 a day for 3 days, three times the usual count or more.",
     "cases": "22 KC-135 at Prince Sultan 19 Jun 2025, strikes 21-22 Jun; 14 at Ben Gurion 27 Feb 2026."},
    {"id": "airspace", "name": "Airspace closed or restricted",
     "series": ["czib_{t}", "notam_{t}"],
     "rule": lambda p, q, d: rose(p, d) or surge(q, d, 1.5, 10, recent=1, base=30, need=14),
     "says": "EASA issued or revised a conflict-zone bulletin for the theatre, or new restriction NOTAMs jumped by half, in the last 7 days.",
     "cases": "India closed its airspace to Pakistan a week before Operation Sindoor (30 Apr 2025)."},
    {"id": "sea", "name": "Firing or missile warnings at sea",
     "series": ["nga_{t}", "msa_{t}", "jcg_{t}"], "rule": lambda p, d: surge(p, d, 2, 3, recent=1),
     "says": "Navigation warnings for firing, missile or launch areas in the theatre's waters doubled against their usual count.",
     "cases": "DPRK satellite launch-window notice to Japan's Coast Guard, May 2023; China's live-fire zones before Strait Thunder 2025A."},
    {"id": "wave", "name": "Strike waves (wars under way)",
     "series": ["tzeva_{t}", "uaair_{t}"], "rule": lambda p, d: surge(p, d, 2, 5, recent=1),
     "says": "Rocket, missile or air-raid alert waves in the last 7 days doubled against their usual count.",
     "cases": "Tzeva Adom and alerts.in.ua count the attacks themselves: a reading of tempo in wars already under way."},
    {"id": "bases", "name": "Aircraft leave a named base, ships leave port", "series": [], "rule": None,
     "says": "Not watched yet: needs per-base aircraft traces and port presence.",
     "cases": "Al Udeid emptied 19 Jun 2025, strike 23 Jun; every US ship left Bahrain 26 Feb 2026, strikes 28 Feb."},
    {"id": "civil", "name": "Civil-defence instructions", "series": [], "rule": None,
     "says": "Not watched yet: needs home-front and civil-defence notices.",
     "cases": "India's nationwide civil-defence drill 5 May 2025, strikes 7 May."},
]


def _arity(rule):
    return rule.__code__.co_argcount - 1


def fires(tell, pts, day):
    """-> (fired, the series id that fired) for one theatre on one day. pts: [points per series in tell['series']]."""
    if tell["rule"] is None:
        return False, None
    n = _arity(tell["rule"])
    if n == 1:     # any of the series (one source per theatre, whichever exists)
        for sid, p in pts:
            if p and tell["rule"](p, day):
                return True, sid
        return False, None
    if any(not p for _, p in pts[:n]) and not pts[0][1]:
        return False, None
    return bool(tell["rule"](*[p or [] for _, p in pts[:n]], day)), pts[0][0]


def _resolve(tell, theatre, lookup):
    """[(series id, points)] for the series this tell reads in the theatre; points [] when there is none."""
    out = []
    for pat in tell["series"]:
        sid = pat.format(t=theatre)
        out.append((sid, lookup(sid)))
    return out


def watched(tell, theatre, lookup):
    return tell["rule"] is not None and any(p for _, p in _resolve(tell, theatre, lookup))


def last_fired(tell, theatre, lookup, day, window=WINDOW):
    """The newest day within the window on which the tell fired, and the series that fired, or (None, None)."""
    pts = _resolve(tell, theatre, lookup)
    d = dt.date.fromisoformat(day)
    for i in range(window):
        dd = (d - dt.timedelta(days=i)).isoformat()
        ok, sid = fires(tell, pts, dd)
        if ok:
            return dd, sid
    return None, None


def evaluate(series, today=None, record=None):
    """{theatre: [tell rows]} for the page: id, name, on (True/False/None for not watched), date, source series, rule, cases, record."""
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    record = record if record is not None else load_record()
    pts = {s["id"]: [(d[:10], v) for d, v in s.get("points") or []] for s in series}
    out = {}
    for t in C.THEATRES:
        if t == "global":
            continue
        rows = []
        for tell in TELLS:
            on, day, sid = None, None, None
            if watched(tell, t, lambda k: pts.get(k, [])):
                day, sid = last_fired(tell, t, lambda k: pts.get(k, []), today)
                on = day is not None
            rows.append({"id": tell["id"], "n": tell["name"], "on": on, "date": day, "src": sid, "says": tell["says"],
                         "cases": tell["cases"], "note": tell.get("note", ""), "rec": (record.get("tells") or {}).get(tell["id"])})
        out[t] = rows
    return out


def load_record(path=None):
    try:
        with open(path or RECORD) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- record on the stored history
def read_events():
    ev = []
    for fn in ("events.csv", "events_added.csv"):
        try:
            with open(os.path.join(DATA, fn), newline="") as f:
                ev += [(r["theatre"], r["date"]) for r in csv.DictReader(f)]
        except OSError:
            pass
    return sorted(set(ev))


def replay(tell, theatre, lookup, events):
    """Every day the tell's history covers, in order: -> dict(episodes, hits, events, caught, first, last).
    An episode is a run of firing days after 7 quiet ones; a hit is an episode with an event in this theatre within
    7 days of its first day. caught counts the events (inside the covered span) with an episode starting in the 7 days before."""
    pts = _resolve(tell, theatre, lookup)
    days = sorted({d for _, p in pts for d, _ in p})
    if tell["rule"] is None or len(days) < 120:
        return None
    first, last = days[59], days[-1]       # the first 60 days only build the baselines
    evd = [dt.date.fromisoformat(d) for t, d in events if t == theatre and first <= d <= last]
    starts, quiet, d = [], QUIET, dt.date.fromisoformat(first)
    end = dt.date.fromisoformat(last)
    while d <= end:
        ok, _ = fires(tell, pts, d.isoformat())
        if ok and quiet >= QUIET:
            starts.append(d)
        quiet = 0 if ok else quiet + 1
        d += dt.timedelta(days=1)
    hits = sum(any(0 < (e - s).days <= WINDOW for e in evd) for s in starts)
    caught = sum(any(0 < (e - s).days <= WINDOW for s in starts) for e in evd)
    return {"episodes": len(starts), "hits": hits, "events": len(evd), "caught": caught, "first": first, "last": last,
            "starts": [s.isoformat() for s in starts]}


def history_lookup():
    """Series id -> the longest stored daily history: the live build's cache or its own history, seeded with the archive."""
    import store

    def get(sid):
        pts = store.cache_load(sid)
        if not pts:
            live = store.daily(sid)
            if sid.startswith("state_dep_"):
                live = store.daily("state_dep_main_" + sid[len("state_dep_"):])
                arch = store.backfill(sid) or store.backfill("state_od_" + sid[len("state_dep_"):])
                first = live[0][0] if live else "9999"
                return [(d, v) for d, v in arch if d < first] + live
            if sid.startswith("state_") and sid[len("state_"):] in C.THEATRES:
                live = store.daily("state_main_" + sid[len("state_"):])
            pts = store.seed(sid, live)
        return [(d[:10], v) for d, v in pts]
    return get


def record(write=True):
    get = history_lookup()
    ev = read_events()
    per, tot = {}, {}
    for tell in TELLS:
        rows = {}
        for t in C.THEATRES:
            if t == "global":
                continue
            r = replay(tell, t, get, ev)
            if r:
                rows[t] = r
        per[tell["id"]] = rows
        if rows:
            agg = {k: sum(r[k] for r in rows.values()) for k in ("episodes", "hits", "events", "caught")}
            agg["first"] = min(r["first"] for r in rows.values())
            agg["last"] = max(r["last"] for r in rows.values())
            agg["theatres"] = len(rows)
            tot[tell["id"]] = agg
    out = {"made": dt.date.today().isoformat(), "window": WINDOW, "events": len(ev), "tells": tot, "per_theatre": per}
    if write:
        with open(RECORD, "w") as f:
            json.dump(out, f, indent=1)
        _report(out)
    return out


def _report(o):
    L = ["# Timing tells: their record on our history", "",
         f"Generated by `warwatch/tells.py record` on {o['made']}. Events: `warwatch/data/events.csv` and `events_added.csv` ({o['events']} in all). "
         f"A tell **fires** on a day its rule holds; an **episode** is a run of firing days after {QUIET} quiet ones. "
         f"A **hit** is an episode with an event in the same theatre within {o['window']} days of its first day; **caught** counts events with an episode starting in the {o['window']} days before. "
         "The rules are fixed by hand from the cases analysts cite (assessment part 1), not fitted, so this record is their first test, not a tuning set.", "",
         "| Tell | History | Theatres | Episodes | Followed by an event | Events in span | Events caught |", "|---|---|---|---|---|---|---|"]
    for tell in TELLS:
        a = o["tells"].get(tell["id"])
        if not a:
            L.append(f"| {tell['name']} | none yet | | | | | |")
            continue
        L.append(f"| {tell['name']} | {a['first']} to {a['last']} | {a['theatres']} | {a['episodes']} | {a['hits']} | {a['events']} | {a['caught']} |")
    L += ["", "Per theatre, episode start days are in `warwatch/data/tells_record.json`. The live page carries the pooled line above for each tell."]
    with open(os.path.join(os.path.dirname(HERE), "docs", "TELLS.md"), "w") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- forward record
FIELDS = ["date", "theatre", "tell", "on", "fired", "src", "prev_hash", "hash"]


def _digest(prev, row):
    return hashlib.sha256((prev + "|" + "|".join(str(row[k]) for k in FIELDS[:-2])).encode()).hexdigest()


def forward_append(tells, day=None, path=None):
    """Once per UTC day (the first build of the day), every watched tell's state, hash-chained like forward/log.csv."""
    path = path or FORWARD
    day = day or dt.datetime.now(dt.timezone.utc).date().isoformat()
    old = []
    try:
        with open(path, newline="") as f:
            old = list(csv.DictReader(f))
    except OSError:
        pass
    if old and old[-1]["date"] >= day:
        return 0
    prev = old[-1]["hash"] if old else "0" * 64
    rows = [{"date": day, "theatre": t, "tell": r["id"], "on": int(bool(r["on"])), "fired": r["date"] or "", "src": r["src"] or ""}
            for t, lst in tells.items() for r in lst if r["on"] is not None]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if not old:
            w.writeheader()
        for r in rows:
            r["prev_hash"] = prev
            r["hash"] = prev = _digest(prev, r)
            w.writerow(r)
    return len(rows)


if __name__ == "__main__":
    if (sys.argv[1:] or ["record"])[0] == "record":
        o = record()
        print(json.dumps(o["tells"], indent=1))
    else:
        sys.exit(__doc__)
