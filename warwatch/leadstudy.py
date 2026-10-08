"""Lead study: did any back-filled indicator rise before the labelled events?

For every archive series in backfill/data (aircraft by class, fires, advisories, hazard warnings, vessel presence, SAR) it asks one
question per event: in the 30 days before the event, did the series' 7-day mean climb well above its own recent normal?
That is compared with how often it did so in 30-day windows with no event near them. No model is fitted and nothing is tuned to
the events: it is a count of hits against a count of false alarms, with an exact binomial test.

  python3 warwatch/leadstudy.py            writes docs/LEADSTUDY.md
"""
import csv
import datetime as dt
import math
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKFILL = os.path.join(ROOT, "backfill", "data")
EVENTS = os.path.join(ROOT, "warwatch", "data", "events.csv")
OUT = os.path.join(ROOT, "docs", "LEADSTUDY.md")

THEATRES = ["europe_east", "southasia", "ukraine", "venezuela", "taiwan", "israel", "sudan", "korea", "libya", "yemen", "iran", "drc", "scs"]
KINDS = ["adsb_fighter", "adsb_isr", "adsb_lift", "adsb_mil", "adsb_tanker", "state", "firms", "firms_frp", "nga", "ais_presence", "sar"]
LEAD = 30             # look-back window, days
GAP = 30              # an event this close after another in the same theatre is a continuation, not a new onset
BASE_FROM, BASE_TO = 180, 31   # the normal a day is compared with: the 150 days that end 31 days before it
SMOOTH = 7
CUTS = (1.5, 2.0, 3.0)
MIN_BASE = 90         # observed days needed in that baseline


def daily(path):
    pts = {}
    with open(path) as f:
        for r in csv.reader(f):
            try:
                pts[dt.date.fromisoformat(r[0])] = float(r[1])
            except (ValueError, IndexError):
                continue
    return pts


def zseries(pts):
    """Point-in-time z of the 7-day mean against the baseline that ends 31 days earlier. -> {date: z}"""
    if not pts:
        return {}
    a, b = min(pts), max(pts)
    n = (b - a).days + 1
    x = [pts.get(a + dt.timedelta(i)) for i in range(n)]
    m = []
    for i in range(n):
        w = [v for v in x[max(0, i - SMOOTH + 1):i + 1] if v is not None]
        m.append(sum(w) / len(w) if len(w) >= SMOOTH // 2 + 1 else None)
    out = {}
    for i in range(BASE_FROM, n):
        base = [v for v in x[i - BASE_FROM:i - BASE_TO + 1] if v is not None]
        if m[i] is None or len(base) < MIN_BASE:
            continue
        mu = sum(base) / len(base)
        sd = math.sqrt(sum((v - mu) ** 2 for v in base) / len(base))
        sd = max(sd, 0.25 * abs(mu), 0.5)          # a flat series must not make a one-count wobble look huge
        out[a + dt.timedelta(i)] = (m[i] - mu) / sd
    return out


def binom_tail(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log(1 - p))
                        for i in range(k, n + 1)))


def load_events():
    ev = defaultdict(list)
    with open(EVENTS, newline="") as f:
        for r in csv.DictReader(f):
            ev[r["theatre"]].append((dt.date.fromisoformat(r["date"]), r["description"], r["surprise_or_buildup"]))
    return {t: sorted(v) for t, v in ev.items()}


def onsets(evs):
    out, last = [], None
    for e in evs:
        if last is None or (e[0] - last).days > GAP:
            out.append(e)
        last = e[0]
    return out


def series_for(kind, th):
    sid = f"{kind}_{th}" if not kind.startswith("adsb_") else f"adsb_{th}_{kind[5:]}"
    p = os.path.join(BACKFILL, sid + ".csv")
    return sid, p if os.path.exists(p) else None


def window_max(z, end):
    """Highest z in the LEAD days before `end`, or None when fewer than half of them are scored."""
    v = [z[end - dt.timedelta(k)] for k in range(1, LEAD + 1) if (end - dt.timedelta(k)) in z]
    return max(v) if len(v) >= LEAD // 2 else None


def study():
    events = load_events()
    allev = {t: [e[0] for e in v] for t, v in events.items()}
    res, per_event, profile = {}, defaultdict(list), {}
    for kind in KINDS:
        hits = {c: 0 for c in CUTS}
        n_on = 0
        ctl = {c: [0, 0] for c in CUTS}       # [windows above the cut, windows]
        lag_sum, lag_n, ctl_sum, ctl_n = defaultdict(float), defaultdict(int), 0.0, 0
        used = []
        for th in THEATRES:
            sid, path = series_for(kind, th)
            if not path:
                continue
            z = zseries(daily(path))
            if len(z) < 200:
                continue
            used.append(th)
            ons = onsets(events.get(th, []))
            near = set()
            for e in allev.get(th, []):
                for k in range(-LEAD, GAP + 1):
                    near.add(e + dt.timedelta(k))
            for e, desc, typ in ons:
                w = window_max(z, e)
                if w is None:
                    continue
                n_on += 1
                for c in CUTS:
                    hits[c] += w >= c
                if w >= 2.0:
                    per_event[(th, e.isoformat(), desc, typ)].append((kind, round(w, 1)))
                for k in range(-LEAD, 1):
                    if e + dt.timedelta(k) in z:
                        lag_sum[k] += z[e + dt.timedelta(k)]
                        lag_n[k] += 1
            for d in sorted(z):
                if d in near or (d - dt.timedelta(1)) not in z:
                    continue
                w = window_max(z, d)
                if w is None:
                    continue
                for c in CUTS:
                    ctl[c][0] += w >= c
                    ctl[c][1] += 1
                ctl_sum += z[d]
                ctl_n += 1
        if not n_on:
            continue
        res[kind] = {"theatres": used, "n": n_on, "hits": hits,
                     "fa": {c: ctl[c][0] / max(1, ctl[c][1]) for c in CUTS}, "nctl": ctl[2.0][1],
                     "p": {c: binom_tail(hits[c], n_on, ctl[c][0] / max(1, ctl[c][1])) for c in CUTS}}
        profile[kind] = {k: lag_sum[k] / lag_n[k] for k in (-30, -21, -14, -7, -3, -1, 0) if lag_n[k]}
        profile[kind]["control"] = ctl_sum / ctl_n if ctl_n else 0.0
    return res, per_event, profile, events


def write(res, per_event, profile, events):
    tested = len(res) * len(CUTS)
    L = ["# Lead study: which indicators rose before the events",
         "",
         "Written by `warwatch/leadstudy.py`. No model is fitted and nothing is tuned to the events. For each archive series the 7-day mean is compared "
         f"with its own normal (the {BASE_FROM - BASE_TO + 1} days ending {BASE_TO} days earlier) as a z-score. An event is a **hit** for a series if the z reached the cut "
         f"at any point in the {LEAD} days before it. A **false alarm** is the same thing in a {LEAD}-day window with no event within {GAP} days either side, in the same theatre. "
         "If a family really leads events, its hit rate should clearly beat its false-alarm rate.",
         "",
         f"Events: {sum(len(v) for v in events.values())} labelled, counted only when no earlier event in the same theatre fell in the previous {GAP} days (a continuing war is not a new onset). "
         "Only series with history before the event can be scored, so aircraft cover 2024 onward and advisories, fires, NGA and vessel presence reach further back. "
         "The p-value is an exact binomial test of the hit count against the false-alarm rate; windows overlap, so it is a little generous.",
         "",
         "## Hit rate against false-alarm rate (z of 2 or more)",
         "",
         "| Family | Theatres | Events scored | Hits | Hit rate | False-alarm rate | Lift | p |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, r in sorted(res.items(), key=lambda kv: kv[1]["p"][2.0]):
        h, fa = r["hits"][2.0] / r["n"], r["fa"][2.0]
        L.append(f"| {k} | {len(r['theatres'])} | {r['n']} | {r['hits'][2.0]} | {h:.0%} | {fa:.0%} | {h / fa if fa else float('inf'):.1f}x | {r['p'][2.0]:.3f} |")
    L += ["", f"{tested} family-and-cut combinations are tested here, so about {tested * 0.05:.1f} would show p < 0.05 by chance alone. Treat a single p just under 0.05 as a lead to follow, not a finding.",
          "", "### Other cut-offs", "", "| Family | Cut | Hit rate | False-alarm rate | p |", "|---|---:|---:|---:|---:|"]
    for k, r in sorted(res.items()):
        for c in (1.5, 3.0):
            L.append(f"| {k} | {c} | {r['hits'][c] / r['n']:.0%} | {r['fa'][c]:.0%} | {r['p'][c]:.3f} |")
    L += ["", "## Average z by days before the event", "",
          "Mean z of the series on the given day before the event, over the same events as above. A real lead shows the mean climbing toward 0; the last column is the mean on ordinary days.",
          "", "| Family | -30 | -21 | -14 | -7 | -3 | -1 | event day | ordinary day |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k, p in sorted(profile.items()):
        L.append(f"| {k} | " + " | ".join(f"{p[d]:+.2f}" if d in p else "" for d in (-30, -21, -14, -7, -3, -1, 0)) + f" | {p['control']:+.2f} |")
    L += ["", "## Events with a family above z = 2 beforehand", "", "| Date | Theatre | Event | Type | Families that rose |", "|---|---|---|---|---|"]
    for (th, d, desc, typ), v in sorted(per_event.items(), key=lambda kv: kv[0][1]):
        L.append(f"| {d} | {th} | {desc[:60]} | {typ} | " + ", ".join(f"{k} ({z})" for k, z in v) + " |")
    L.append("")
    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print("wrote", OUT)


if __name__ == "__main__":
    write(*study())
