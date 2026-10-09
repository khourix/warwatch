"""Toyota indicator test: do Japan and Thailand pickup and large-SUV exports to a country surge before conflict events there?

Pre-registered 2026-10-09, before any result was seen. Does not touch the live score or the fitted model.

Data: backfill/data/trade_<origin>_<pickup|suv>_<country>.csv (UN Comtrade mirror data; see backfill/trade.py), summed over both
origins and both products into monthly units per country.
Feature: S3 = units in the latest 3 months; z = (S3 - mean of S3 over the 24 months that end 12 months earlier) / max(sd, 0.25 x mean).
A surge month is z >= 2.
Hit: an event onset (no earlier event in that theatre in the previous 30 days; buildup events only) with a surge month in the 12 months
before it. False alarm: a 12-month window ending in a month with no event within 12 months either side in that theatre.
Countries: Sudan, Libya, Yemen, DRC (the theatres with their own import line). Pass rule: 10 or more onsets scored, hit rate at least 3x the
false-alarm rate, exact binomial p < 0.01, hits in at least 3 countries. Also reported, not pass-eligible: the same test with the
8-month publication lag applied (what could have been seen in time), and the re-export hubs (UAE, Jordan, Turkey) against the same events.

  python3 warwatch/tradelab.py      writes docs/TRADELAB.md
"""
import csv
import datetime as dt
import glob
import os
from collections import defaultdict

import leadstudy as L

DATA = os.path.join(L.ROOT, "backfill", "data")
OUT = os.path.join(L.ROOT, "docs", "TRADELAB.md")
COUNTRIES = ["sudan", "libya", "yemen", "drc"]
HUBS = ["uae", "jordan", "turkey"]
LAG = 8


def monthly(country):
    tot = defaultdict(float)
    for f in glob.glob(os.path.join(DATA, f"trade_*_*_{country}.csv")):
        for r in csv.reader(open(f)):
            if r:
                tot[r[0][:7]] += float(r[1])
    return dict(tot)


def months(a, b):
    y, m = a
    while (y, m) <= b:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def key(y, m):
    return f"{y}-{m:02d}"


def zseries(units):
    """{(y,m): z} for months with a full baseline."""
    if not units:
        return {}
    ks = sorted(units)
    a = tuple(int(x) for x in ks[0].split("-"))
    b = tuple(int(x) for x in ks[-1].split("-"))
    allm = list(months(a, b))
    idx = {ym: i for i, ym in enumerate(allm)}
    x = [units.get(key(*ym), 0.0) for ym in allm]
    s3 = [sum(x[max(0, i - 2):i + 1]) if i >= 2 else None for i in range(len(x))]
    out = {}
    for i, ym in enumerate(allm):
        if s3[i] is None:
            continue
        base = [s3[j] for j in range(i - 35, i - 11) if j >= 2 and s3[j] is not None]
        if len(base) < 24:
            continue
        mu = sum(base) / len(base)
        sd = max((sum((v - mu) ** 2 for v in base) / len(base)) ** 0.5, 0.25 * mu, 1.0)
        out[ym] = (s3[i] - mu) / sd
    return out


def month_of(d):
    return d.year, d.month


def shift(ym, k):
    n = ym[0] * 12 + ym[1] - 1 + k
    return n // 12, n % 12 + 1


def wmax(z, end, lag=0):
    """highest z among the 12 months before `end` (a month), counting only months published by then (lag)."""
    v = [z[shift(end, -k)] for k in range(1 + lag, 13) if shift(end, -k) in z]
    return max(v) if len(v) >= (12 - lag) // 2 else None


def evaluate(zs, events, cut=2.0, lag=0):
    hits, n, fa_n, fa_all, th_hit = 0, 0, 0, 0, set()
    for th, z in zs.items():
        evs = events.get(th, [])
        evm = [month_of(e[0]) for e in evs]
        near = set()
        for em in evm:
            for k in range(-12, 13):
                near.add(shift(em, k))
        for e, desc, t in L.onsets(evs):
            if t != "buildup":
                continue
            w = wmax(z, month_of(e), lag)
            if w is None:
                continue
            n += 1
            if w >= cut:
                hits += 1
                th_hit.add(th)
        for ym in z:
            if ym in near:
                continue
            w = wmax(z, ym, lag)
            if w is None:
                continue
            fa_all += 1
            fa_n += w >= cut
    fa = fa_n / fa_all if fa_all else 0.0
    h = hits / n if n else 0.0
    return {"n": n, "hits": hits, "hit": h, "fa": fa, "nctl": fa_all, "lift": (h / fa if fa else (float("inf") if h else 0.0)),
            "p": L.binom_tail(hits, n, fa) if n and fa_all else 1.0, "countries": len(th_hit)}


def run():
    ev = L.load_events()
    zs = {c: zseries(monthly(c)) for c in COUNTRIES}
    res = {"main": evaluate(zs, ev), "lag": evaluate(zs, ev, lag=LAG)}
    # hubs against the events of the theatres they supply
    hz = zseries({k: sum(monthly(h).get(k, 0.0) for h in HUBS) for k in set().union(*[monthly(h) for h in HUBS])})
    supplied = {th: hz for th in COUNTRIES}
    res["hubs"] = evaluate(supplied, ev)
    res["hubs_lag"] = evaluate(supplied, ev, lag=LAG)
    detail = []
    for th, z in zs.items():
        for e, desc, t in L.onsets(ev.get(th, [])):
            w = wmax(z, month_of(e))
            detail.append((th, e.isoformat(), t, desc, None if w is None else round(w, 1)))
    return res, sorted(detail, key=lambda r: r[1]), zs


def write(res, detail, zs):
    L_ = ["# Toyota indicator test", "",
          "Written by `warwatch/tradelab.py`. Rule and cut fixed on 2026-10-09 before any result was seen (see the module docstring). Nothing here changes the live score.", "",
          "Feature: monthly Japan and Thailand exports of pickups and large SUVs (Land Cruiser and Hilux sources) to the country, from UN Comtrade. "
          "A surge is the latest 3 months at least 2 standard deviations above the same measure over the 24 months that ended a year earlier. "
          "Hit: a surge in the 12 months before a buildup onset.", "",
          "| Test | Onsets scored | Hits | Hit rate | False-alarm rate | Lift | p | Countries hit |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    names = {"main": "Pre-registered: Sudan, Libya, Yemen, DRC", "lag": f"Same, with the {LAG}-month publication lag (what could be seen in time)",
             "hubs": "Exploratory: UAE + Jordan + Turkey, against the same four theatres' events",
             "hubs_lag": f"Exploratory: hubs with the {LAG}-month lag"}
    for k, r in res.items():
        lift = f"{r['lift']:.1f}x" if r["lift"] != float("inf") else "inf"
        L_.append(f"| {names[k]} | {r['n']} | {r['hits']} | {r['hit']:.0%} | {r['fa']:.0%} | {lift} | {r['p']:.3f} | {r['countries']} |")
    m = res["main"]
    ok = m["n"] >= 10 and m["lift"] >= 3 and m["p"] < 0.01 and m["countries"] >= 3
    L_ += ["", f"**Pre-registered verdict: {'passes' if ok else 'does not pass'}** (needs 10 or more onsets, hit rate 3x false alarms, p < 0.01, hits in 3 or more countries).", "",
           "## Each onset", "", "| Date | Country | Type | Event | Highest surge z in the 12 months before |", "|---|---|---|---|---:|"]
    for th, d, t, desc, w in detail:
        L_.append(f"| {d} | {th} | {t} | {desc[:55]} | {'' if w is None else w} |")
    L_.append("")
    open(OUT, "w").write("\n".join(L_))
    print("\n".join(L_))


if __name__ == "__main__":
    write(*run())
