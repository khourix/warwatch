"""Feature lab: do better transformations of the same data add real lead on the labelled events?

Pre-registered on 2026-10-09, before any result was seen. Nothing here touches the live score or the fitted model.

Each feature is a daily number per theatre built from the archive series in backfill/data. It is tested the way leadstudy.py tests a
single series: a **hit** is an event onset with the feature at or above its cut at some point in the 30 days before; a **false alarm**
is the same in a 30-day window with no event within 30 days either side. Onsets are events with no earlier event in that theatre in
the previous 30 days, and only buildup events count (surprise events carry no warning by definition; they are shown as a secondary line).

Eras. A feature is only comparable between event windows and calm windows if the same feeds exist in both, so each test uses one fixed
set of domains and only days on which every one of them is scored:
  era A  2018-12 to 2024-05-10   sea (vessel presence), fire (FIRMS), warnings (NGA), advisories (State)
  era B  2024-09-16 to 2026-06-30  air (aircraft by class), sea, fire, advisories
and only theatres that have every series in the set (A and B: Iran, Israel, Ukraine, Yemen, Korea).

Features (z = a series' 7-day mean against its own baseline, as in leadstudy.py; a domain's z is the highest z of its series):
  F1 breadth       number of domains with z >= 1.5.                                   primary cut: >= 2
  F2 co-occurrence min(z tanker, max(z ISR, z fighter)) on the same day, era B only.   primary cut: >= 1.0
  F3 acceleration  7-day mean minus 30-day mean, as a z against its own baseline; highest across the theatre's series.  primary cut: >= 2.0
  F4 absence       the largest fall (negative z) in vessel presence, military lift or military total.  primary cut: >= 2.0 (z <= -2)
  F5 regime        the plain "any series z >= 2" signal, tested only inside theatres with an event in the previous 365 days
                   and compared with the same signal outside them.                    primary cut: >= 2
  F6 pooled surge  mean over domains of z clipped to 0..5, one score for every theatre.   primary cut: >= 1.5
  Baseline         "any": the highest z over every series in the set.                  cut: >= 2

A feature passes only if, in at least one era and with the primary cut fixed above: at least 10 onsets are scored, the hit rate is at
least 3 times the false-alarm rate, the exact binomial p is below 0.01, hits come from at least 3 theatres, and it beats the baseline's
lift in that era. It must also not run backwards (lift above 1) in the other era where it can be tested. 12 tests are run, so about
0.1 would pass by chance at p < 0.01. Failures are reported, not tuned.

  python3 warwatch/featurelab.py        writes docs/FEATURELAB.md
"""
import datetime as dt
import os
from collections import defaultdict

import leadstudy as L

OUT = os.path.join(L.ROOT, "docs", "FEATURELAB.md")
THEATRES = ["iran", "israel", "ukraine", "yemen", "korea"]
ERAS = {"A": (dt.date(2018, 12, 1), dt.date(2024, 5, 10), ["sea", "fire", "warn", "adv"]),
        "B": (dt.date(2024, 9, 16), dt.date(2026, 6, 30), ["air", "sea", "fire", "adv"])}
DOMAIN_KINDS = {"air": ["adsb_fighter", "adsb_isr", "adsb_lift", "adsb_mil", "adsb_tanker"], "sea": ["ais_presence"],
                "fire": ["firms", "firms_frp"], "warn": ["nga"], "adv": ["state"]}
PRIMARY = {"F1": 2.0, "F2": 1.0, "F3": 2.0, "F4": 2.0, "F5": 2.0, "F6": 1.5, "any": 2.0}


def accel_z(pts):
    """z of (7-day mean - 30-day mean) against that gap's own baseline (days 180 to 31 before). -> {date: z}"""
    if not pts:
        return {}
    a, b = min(pts), max(pts)
    n = (b - a).days + 1
    x = [pts.get(a + dt.timedelta(i)) for i in range(n)]

    def roll(i, k):
        w = [v for v in x[max(0, i - k + 1):i + 1] if v is not None]
        return sum(w) / len(w) if len(w) >= k // 2 + 1 else None
    g = [None if (roll(i, 7) is None or roll(i, 30) is None) else roll(i, 7) - roll(i, 30) for i in range(n)]
    out = {}
    for i in range(L.BASE_FROM, n):
        base = [v for v in g[i - L.BASE_FROM:i - L.BASE_TO + 1] if v is not None]
        if g[i] is None or len(base) < L.MIN_BASE:
            continue
        mu = sum(base) / len(base)
        sd = max((sum((v - mu) ** 2 for v in base) / len(base)) ** 0.5, 0.15 * abs(mu), 0.5)
        out[a + dt.timedelta(i)] = (g[i] - mu) / sd
    return out


def load():
    """{theatre: {kind: (z, accel)}} for every kind that exists."""
    data = {}
    for th in THEATRES:
        data[th] = {}
        for kinds in DOMAIN_KINDS.values():
            for k in kinds:
                _, p = L.series_for(k, th)
                if p:
                    pts = L.daily(p)
                    data[th][k] = (L.zseries(pts), accel_z(pts))
    return data


def days(era):
    a, b, _ = ERAS[era]
    return [a + dt.timedelta(i) for i in range((b - a).days + 1)]


def features(data, th, era):
    """{feature: {date: value}} for the days on which every domain of the era is scored."""
    doms = ERAS[era][2]
    Z = data[th]
    out = defaultdict(dict)
    for d in days(era):
        dz, da, allz, allfall = {}, {}, [], []
        ok = True
        for dom in doms:
            zs = [Z[k][0][d] for k in DOMAIN_KINDS[dom] if k in Z and d in Z[k][0]]
            ac = [Z[k][1][d] for k in DOMAIN_KINDS[dom] if k in Z and d in Z[k][1]]
            if not zs:
                ok = False
                break
            dz[dom], da[dom] = max(zs), max(ac) if ac else None
            allz += zs
            if dom in ("sea", "air"):
                allfall += [-Z[k][0][d] for k in DOMAIN_KINDS[dom] if k in ("ais_presence", "adsb_lift", "adsb_mil") and k in Z and d in Z[k][0]]
        if not ok:
            continue
        out["any"][d] = max(allz)
        out["F1"][d] = float(sum(v >= 1.5 for v in dz.values()))
        out["F6"][d] = sum(min(5.0, max(0.0, v)) for v in dz.values()) / len(dz)
        acs = [v for v in da.values() if v is not None]
        if acs:
            out["F3"][d] = max(acs)
        if allfall:
            out["F4"][d] = max(allfall)
        if era.startswith("B") and all(k in Z and d in Z[k][0] for k in ("adsb_tanker", "adsb_isr", "adsb_fighter")):
            out["F2"][d] = min(Z["adsb_tanker"][0][d], max(Z["adsb_isr"][0][d], Z["adsb_fighter"][0][d]))
    return out


def wmax(f, end):
    v = [f[end - dt.timedelta(k)] for k in range(1, L.LEAD + 1) if (end - dt.timedelta(k)) in f]
    return max(v) if len(v) >= L.LEAD // 2 else None


def evaluate(feats, cut, events, era, typ="buildup", regime=None):
    """feats {th: {date: v}}. regime None, True or False: restrict to windows with / without an event in the previous 365 days."""
    a, b, _ = ERAS[era]
    hits, n, fa_n, fa_all, by_th = 0, 0, 0, 0, set()

    def in_regime(th, d):
        if regime is None:
            return True
        prev = any(0 < (d - e[0]).days <= 365 for e in events.get(th, []))
        return prev == regime
    for th, f in feats.items():
        evs = events.get(th, [])
        near = set()
        for e in evs:
            for k in range(-L.LEAD, L.GAP + 1):
                near.add(e[0] + dt.timedelta(k))
        for e, desc, t in L.onsets(evs):
            if t != typ and typ != "all":
                continue
            if not (a <= e <= b) or not in_regime(th, e):
                continue
            w = wmax(f, e)
            if w is None:
                continue
            n += 1
            if w >= cut:
                hits += 1
                by_th.add(th)
        for d in f:
            if d in near or not in_regime(th, d):
                continue
            w = wmax(f, d)
            if w is None:
                continue
            fa_all += 1
            fa_n += w >= cut
    fa = fa_n / fa_all if fa_all else 0.0
    h = hits / n if n else 0.0
    return {"n": n, "hits": hits, "hit": h, "fa": fa, "nctl": fa_all, "lift": (h / fa if fa else float("inf") if h else 0.0),
            "p": L.binom_tail(hits, n, fa) if n and fa_all else 1.0, "theatres": len(by_th)}


def run():
    data, events = load(), L.load_events()
    res = {}
    for era in ERAS:
        F = {th: features(data, th, era) for th in THEATRES}
        for name in ("any", "F1", "F2", "F3", "F4", "F6"):
            feats = {th: F[th][name] for th in THEATRES if F[th].get(name)}
            if feats:
                res[(name, era, "buildup")] = evaluate(feats, PRIMARY[name], events, era)
                res[(name, era, "surprise")] = evaluate(feats, PRIMARY[name], events, era, typ="surprise")
        feats = {th: F[th]["any"] for th in THEATRES if F[th].get("any")}
        res[("F5 inside regime", era, "buildup")] = evaluate(feats, PRIMARY["F5"], events, era, regime=True)
        res[("F5 outside regime", era, "buildup")] = evaluate(feats, PRIMARY["F5"], events, era, regime=False)
    res["F2 exploratory"] = explore_f2(data, events)
    return res


def explore_f2(data, events):
    """Not part of the pre-registered tests: F2 on every theatre that has aircraft data (the air-only part of era B), to see whether the
    result in the five-theatre test is a fluke of that choice. Cannot pass or fail the rule."""
    ERAS["B2"] = (dt.date(2024, 9, 16), dt.date(2026, 10, 6), ["air"])
    keep = list(THEATRES)
    THEATRES[:] = L.THEATRES
    try:
        data = load()
        feats = {th: f for th in THEATRES if (f := features(data, th, "B2").get("F2"))}
        out = {c: evaluate(feats, c, events, "B2") for c in (0.5, 1.0, 1.5)}
    finally:
        THEATRES[:] = keep
        ERAS.pop("B2")
    return out


def verdicts(res):
    out = {}
    for name in ("F1", "F2", "F3", "F4", "F6", "F5 inside regime"):
        passed, notes = False, []
        for era in ERAS:
            r = res.get((name, era, "buildup"))
            if not r:
                continue
            base = res.get(("F5 outside regime" if name.startswith("F5") else "any", era, "buildup"))
            ok = (r["n"] >= 10 and r["lift"] >= 3 and r["p"] < 0.01 and r["theatres"] >= 3 and base is not None and r["lift"] > base["lift"])
            if name.startswith("F5") and base:
                ok = ok and (r["n"] >= 10)
            passed = passed or ok
            notes.append(f"era {era}: {'meets all five conditions' if ok else 'fails'}")
        out[name] = (passed, "; ".join(notes))
    return out


def write(res):
    V = verdicts(res)
    L_ = ["# Feature lab", "",
          "Written by `warwatch/featurelab.py`. The features, cuts and pass rule were fixed on 2026-10-09 before any result was seen (see the module docstring). "
          "Nothing was tuned afterward, and nothing here changes the live score or the fitted model.", "",
          "Hit rate: share of buildup onsets where the feature reached its cut in the 30 days before. False-alarm rate: same in windows with no event within 30 days either side. "
          "p is an exact binomial test of the hit count against the false-alarm rate (windows overlap, so it is generous).", "",
          "## Results at the pre-set cuts", "",
          "| Feature | Era | Cut | Onsets scored | Hits | Hit rate | False-alarm rate | Lift | p | Theatres hit | Surprise events (hit/scored) |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for key, r in res.items():
        if key == "F2 exploratory":
            continue
        name, era, typ = key
        if typ != "buildup":
            continue
        cut = PRIMARY["F5" if name.startswith("F5") else name]
        s = res.get((name, era, "surprise"))
        sup = f"{s['hits']}/{s['n']}" if s else ""
        lift = f"{r['lift']:.1f}x" if r["lift"] != float("inf") else "inf"
        L_.append(f"| {name} | {era} | {cut} | {r['n']} | {r['hits']} | {r['hit']:.0%} | {r['fa']:.0%} | {lift} | {r['p']:.3f} | {r['theatres']} | {sup} |")
    ex = res["F2 exploratory"]
    L_ += ["", "## F2 on every theatre with aircraft data (exploratory, cannot pass or fail)", "",
           "Same feature, 13 theatres, 2024-09-16 to 2026-10-06, buildup onsets. Shown at three cuts, so read only the pre-set cut of 1.0 as the main line.", "",
           "| Cut | Onsets | Hits | Hit rate | False-alarm rate | Lift | p | Theatres hit |", "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for c, r in ex.items():
        L_.append(f"| {c} | {r['n']} | {r['hits']} | {r['hit']:.0%} | {r['fa']:.1%} | {r['lift']:.1f}x | {r['p']:.3f} | {r['theatres']} |")
    L_ += ["", "## Verdicts", "", "| Feature | Passes | Detail |", "|---|---|---|"]
    for k, (ok, note) in V.items():
        L_.append(f"| {k} | {'**yes**' if ok else 'no'} | {note} |")
    L_ += ["", "A pass needs, in one era: 10 or more onsets scored, hit rate at least 3 times the false-alarm rate, p below 0.01, hits in at least 3 theatres, "
           "and a lift above the baseline's (for F5, above the same signal outside the regime). About 0.1 of the 12 tests would pass by chance.", ""]
    with open(OUT, "w") as f:
        f.write("\n".join(L_))
    print("\n".join(L_))


if __name__ == "__main__":
    write(run())
