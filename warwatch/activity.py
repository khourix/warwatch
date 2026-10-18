"""Activity v1: which fast signal families are on in a theatre this week, weighted by how often each came before an event.

Frozen from the short-fuse study (docs/ACTIVITY.md). The weights were set on the original event list only; on the added
events, which they never saw, the index was on before 16 of 71 (23%) against 15% of calm weeks (p 0.071). That is a hint,
not a proof, so the page shows Activity beside the level as experimental, never instead of it, and its daily values go to a
hash-chained forward record (forward/log_activity.csv) before anything happens, where it can be judged on days it has not seen.

A family is on for a theatre when it fired on any of the 7 days before today:
  adsb_fighter, adsb_tanker, wiki, gdelt_accel  the 7-day mean is 2 SD or more above its normal (leadstudy.zseries)
  tells                                         a departure, advisory, sea-warning, strike-wave or tanker tell fired
  base                                          a watched base was far from usual (out or in) on two radar passes
Index = 100 x (sum of the weights of the families on) / (sum of all weights). Active from the cut, 1.04: any family on.
A family with no data in the window, or whose newest data is stale, reads as missing and counts as off.
"""
import csv
import datetime as dt
import hashlib
import os

import leadstudy as L

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BF = os.path.join(ROOT, "backfill", "data")
FORWARD = os.path.join(ROOT, "forward", "log_activity.csv")
VERSION = "activity-1"

WEIGHTS = {"adsb_fighter": 2.51, "wiki": 0.816, "gdelt_accel": 0.628, "tells": 0.375, "adsb_tanker": 0.351, "base": 0.049}
CUT = 100.0 * WEIGHTS["base"] / sum(WEIGHTS.values())   # 1.036, the base family alone: Active when any family is on
Z_ON = 2.0
WINDOW = 7
STALE = 3          # a family whose newest data day is more than this many days before yesterday reads as missing
KEEP = L.BASE_FROM + WINDOW + 30   # days of history zseries needs for the window (it looks back BASE_FROM days)
THEATRES = list(L.THEATRES)
ALIAS = {"iran": ["iran", "iraq", "gulf"], "israel": ["israel", "lebanon", "syria"]}
TELL_IDS = ("departure", "leave", "sea", "wave", "tankers")
NAMES = {"adsb_fighter": "Fighter aircraft", "wiki": "Wikipedia attention", "gdelt_accel": "Severe-event share in the news record",
         "tells": "Timing tells", "adsb_tanker": "Tanker aircraft", "base": "Bases by satellite radar"}


def boxes(t):
    return ALIAS.get(t, [t])


def _merge_max(series):
    out = {}
    for s in series:
        for d, z in s.items():
            if d not in out or z > out[d]:
                out[d] = z
    return out


def _recent(pts, today):
    lo = today - dt.timedelta(KEEP)
    return {d: v for d, v in pts.items() if d >= lo}


def _z_family(fmt, t, today):
    return _merge_max(L.zseries(_recent(L.daily(fmt.format(b=b)), today)) for b in boxes(t) if os.path.exists(fmt.format(b=b)))


def _gdelt_rows(today):
    """{box: {day: severe events per 1000}} from the wider GDELT counts, days with at least 50 located events (as in the study)."""
    rows = {}
    for y in sorted({today.year - 1, today.year}):
        p = os.path.join(BF, "gdeltwide", f"{y}.csv")
        if not os.path.exists(p):
            continue
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if float(r["loc_all"]) >= 50:
                    rows.setdefault(r["theatre"], {})[dt.date.fromisoformat(r["day"])] = 1000.0 * float(r["loc_q4"]) / float(r["loc_all"])
    return rows


def _window(z, today):
    """(on, newest data day) over the 7 days before `today`: on when any of them is at or above Z_ON."""
    v = [(today - dt.timedelta(k), z.get(today - dt.timedelta(k))) for k in range(1, WINDOW + 1)]
    v = [(d, x) for d, x in v if x is not None]
    if not v:
        return None, None
    return any(x >= Z_ON for _, x in v), max(d for d, _ in v)


def _fresh(on, newest, today):
    return on if newest and (today - newest).days <= STALE + 1 else None


def _tells(t, tells):
    """From the run's tells (tells.evaluate, the rules the study replayed): on when one of TELL_IDS fired in the last 7 days."""
    xs = [x for b in boxes(t) for x in (tells or {}).get(b, []) if x.get("id") in TELL_IDS and x.get("on") is not None]
    return any(bool(x["on"]) for x in xs) if xs else None


def _base(t, series, today):
    """On when a bases_out or bases_in count for one of the theatre's boxes was 1 or more on any of the 7 days before."""
    seen = False
    for b in boxes(t):
        for kind in ("out", "in"):
            s = next((x for x in series if x["id"] == f"bases_{kind}_{b}"), None)
            for d, v in (s or {}).get("points") or []:
                if 1 <= (today - dt.date.fromisoformat(d[:10])).days <= WINDOW:
                    seen = True
                    if v is not None and float(v) >= 1:
                        return True
    return False if seen else None


def compute(series=None, tells=None, today=None):
    """{theatre: {"index", "on", "families": {name: True/False/None}, "missing": [names]}} for the 13 study theatres."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    total = sum(WEIGHTS.values())
    gd = _gdelt_rows(today)
    out = {}
    for t in THEATRES:
        fam = {}
        for name, fmt in (("adsb_fighter", "adsb_{b}_fighter.csv"), ("adsb_tanker", "adsb_{b}_tanker.csv"), ("wiki", "wiki_{b}.csv")):
            fam[name] = _fresh(*_window(_z_family(os.path.join(BF, fmt), t, today), today), today)
        fam["gdelt_accel"] = _fresh(*_window(_merge_max(L.zseries(_recent(gd[b], today)) for b in boxes(t) if b in gd), today), today)
        fam["tells"] = _tells(t, tells)
        fam["base"] = _base(t, series or [], today)
        idx = 100.0 * sum(WEIGHTS[k] for k, v in fam.items() if v) / total
        out[t] = {"index": round(idx, 1), "on": idx >= CUT - 1e-9, "families": {k: fam[k] for k in WEIGHTS},
                  "missing": [k for k in WEIGHTS if fam[k] is None]}
    return out


# ------------------------------------------------------------------ forward record
FIELDS = ["date", "theatre", "index", "on", "families_on", "missing", "model", "prev_hash", "hash"]


def _digest(prev, row):
    body = "|".join(str(row[k]) for k in FIELDS[:-2])
    return hashlib.sha256((prev + "|" + body).encode()).hexdigest()


def forward_append(act, day=None, path=None):
    """Append today's values once per UTC day, hash-chained like forward/log.csv, before any outcome can be known."""
    path = path or FORWARD
    day = day or dt.datetime.now(dt.timezone.utc).date().isoformat()
    old = []
    try:
        with open(path, newline="") as f:
            old = list(csv.DictReader(f))
    except OSError:
        pass
    if not act or (old and old[-1]["date"] >= day):
        return 0
    prev = old[-1]["hash"] if old else "0" * 64
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if not old:
            w.writeheader()
        for t in sorted(act):
            v = act[t]
            r = {"date": day, "theatre": t, "index": f"{v['index']:.1f}", "on": int(v["on"]),
                 "families_on": ";".join(k for k in WEIGHTS if v["families"].get(k)), "missing": ";".join(v["missing"]), "model": VERSION}
            r["prev_hash"] = prev
            r["hash"] = prev = _digest(prev, r)
            w.writerow(r)
    return len(act)


def forward_verify(path=None):
    """(intact, first bad row number or None, rows)."""
    prev, rows = "0" * 64, []
    if not os.path.exists(path or FORWARD):
        return True, None, rows
    with open(path or FORWARD, newline="") as f:
        for i, r in enumerate(csv.DictReader(f), 1):
            if r["prev_hash"] != prev or _digest(prev, r) != r["hash"]:
                return False, i, rows
            prev = r["hash"]
            rows.append(r)
    return True, None, rows
