"""Wikipedia page views against past events, to the plan fixed in docs/WIKISTUDY_PLAN.md before the data was read.

Each back-filled series (backfill/data/wiki_<theatre>.csv, wikiloc_<theatre>.csv) is scored day by day as the live build
scores a daily count, then tested like every other indicator in warwatch/indicatorstudy.py. Writes docs/WIKISTUDY.md.
"""
import datetime as dt
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indicatorstudy as S  # noqa: E402
import stats  # noqa: E402
import validate as V  # noqa: E402

DATA = os.path.join(V.ROOT, "backfill", "data")
OUT = os.path.join(V.ROOT, "docs", "WIKISTUDY.md")
FAMILIES = ("wiki", "wikiloc")


def zseries(path):
    with open(path) as f:
        pts = [(r.split(",")[0], float(r.split(",")[1])) for r in f.read().split()]
    z = {}
    for i in range(len(pts)):
        d = dt.date.fromisoformat(pts[i][0])
        if d < S.FROM - dt.timedelta(S.LEAD):
            continue
        r = stats.score_series(pts[max(0, i + 1 - V.KEEP):i + 1], "daily")
        if r is not None:
            z[d + dt.timedelta(1)] = r["z"]       # a day's views are public the next day
    return z


def study():
    on, allev = S.events()
    res = {}
    for fam in FAMILIES:
        ev, calm = [], []
        for th in V.TH:
            p = os.path.join(DATA, f"{fam}_{th}.csv")
            if not os.path.exists(p):
                continue
            z = zseries(p)
            if len(z) < 200:
                continue
            near = set()
            for d in allev.get(th, []):
                near.update(d + dt.timedelta(k) for k in range(-S.LEAD, S.GAP + 1))
            for r in on[on.theatre == th].itertuples():
                w = S.window_max(z, r.date)
                if w is not None:
                    ev.append((w, r.added, th, r.date, r.description))
            d = max(S.FROM, min(z) + dt.timedelta(S.LEAD))
            while d <= max(z):
                if d not in near:
                    w = S.window_max(z, d)
                    if w is not None:
                        calm.append(w)
                d += dt.timedelta(S.CALM_STEP)
        fa = float(np.mean([c >= S.CUT for c in calm])) if calm else float("nan")
        out = {"calm": len(calm), "fa": fa, "events": ev}
        for nm, sel in (("orig", lambda a: not a), ("added", lambda a: a)):
            w = [x[0] for x in ev if sel(x[1])]
            k = int(sum(x >= S.CUT for x in w))
            out[nm] = {"n": len(w), "hits": k, "hit": k / len(w) if w else float("nan"),
                       "p": S.binom_tail(k, len(w), fa) if w else float("nan"), "auc": S.auc(w, calm)}
        o, a = out["orig"], out["added"]
        out["pass"] = bool(a["p"] < 0.05 and o["p"] < 0.10 and o["auc"] > 0.55 and a["auc"] > 0.55)
        res[fam] = out
    return res


def write(res):
    L = ["# Wikipedia page views against past events", "",
         "Written by `warwatch/wikistudy.py` to the plan fixed before the data was read ([WIKISTUDY_PLAN.md](WIKISTUDY_PLAN.md)). "
         f"Hit = z reached {S.CUT:g} in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.", "",
         "| Family | Original events | Hit rate | False-alarm rate | p | AUC | Added events | Hit rate | p | AUC | Passes |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for fam, r in res.items():
        o, a = r["orig"], r["added"]
        L.append(f"| {fam} | {o['n']} | {o['hit']:.0%} | {r['fa']:.0%} | {o['p']:.3f} | {o['auc']:.2f} | "
                 f"{a['n']} | {a['hit']:.0%} | {a['p']:.3f} | {a['auc']:.2f} | {'yes' if r['pass'] else 'no'} |")
    L += ["", "## Events where views reached z 2 or more in the 30 days before", "", "| Family | Theatre | Date | Event | Max z | List |", "|---|---|---|---|---:|---|"]
    for fam, r in res.items():
        for w, added, th, d, desc in sorted(r["events"], key=lambda x: x[3]):
            if w >= S.CUT:
                L.append(f"| {fam} | {th} | {d} | {desc} | {w:.1f} | {'added' if added else 'original'} |")
    L.append("")
    open(OUT, "w").write("\n".join(L))


if __name__ == "__main__":
    r = study()
    write(r)
    for fam, x in r.items():
        print(fam, {k: x[k] for k in ("calm", "fa", "orig", "added", "pass")})
