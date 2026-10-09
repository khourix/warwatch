"""Which tracked indicators rose before past events: every scored series, every event since 2019, no model.

Each series is scored day by day exactly as the live build scores it (validate.zhistory with the back-filled archives), turned to
the warning direction, and pooled into its family. For each event the highest z in the 30 days before it is compared with the same
measure in calm 30-day windows of the same theatre (no event within 30 days either side). Two numbers per family:

  - hit rate (z reached 2 in the 30 days before) against the false-alarm rate in calm windows, with an exact binomial p;
  - AUC of the window maximum, events against calm windows (0.5 = no difference), cut-off free.

The 78 events the model was built on and the 83 added later are scored separately, so a lead found on one half can be checked on
the other. Run with WARWATCH_BACKFILL_FIT=1 so aircraft, fires, advisories, warnings and vessel presence are included.
Writes docs/INDICATORSTUDY.md and backtest/indicatorstudy.csv. Changes nothing the live page reads.
"""
import datetime as dt
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import validate as V  # noqa: E402

ROOT = V.ROOT
DATA = os.path.join(ROOT, "warwatch", "data")
OUT_MD = os.path.join(ROOT, "docs", "INDICATORSTUDY.md")
OUT_CSV = os.path.join(ROOT, "backtest", "indicatorstudy.csv")
LEAD, GAP, CUT = 30, 30, 2.0
FROM = dt.date(2019, 1, 1)
CALM_STEP = 30          # calm windows end every 30 days, so they do not overlap


def events():
    a = pd.read_csv(os.path.join(DATA, "events.csv")).assign(added=False)
    b = pd.read_csv(os.path.join(DATA, "events_added.csv")).assign(added=True)
    e = pd.concat([a, b], ignore_index=True)
    e["date"] = pd.to_datetime(e.date).dt.date
    e = e.sort_values(["theatre", "date"])
    allev = e.groupby("theatre").date.apply(list).to_dict()
    keep, last = [], {}
    for r in e.itertuples():
        if r.theatre not in last or (r.date - last[r.theatre]).days > GAP:
            keep.append(r.Index)
        last[r.theatre] = r.date
    on = e.loc[keep]
    return on[on.date >= FROM].reset_index(drop=True), allev


def window_max(z, end):
    v = [z[d] for d in (end - dt.timedelta(k) for k in range(1, LEAD + 1)) if d in z]
    return max(v) if len(v) >= LEAD // 2 else None


def binom_tail(k, n, p):
    if n == 0 or p <= 0:
        return 1.0 if k == 0 else 0.0
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    a = np.concatenate([pos, neg])
    r = pd.Series(a).rank().values
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def study():
    H = V.zhistory()
    on, allev = events()
    label = {s["id"]: s["label"] for s in catalog.SERIES}
    per_fam = defaultdict(lambda: {"ev": [], "calm": [], "theatres": set(), "first": None, "label": "", "prof": defaultdict(list)})
    rows_ev = []
    for sid, s in H.items():
        sgn = {"up": 1, "down": -1}.get(s["direction"], 0)
        z = {d: (v * sgn if sgn else abs(v)) for d, v in s["z"].items() if d >= FROM - dt.timedelta(LEAD)}
        if len(z) < 200:
            continue
        f = V.family(sid)
        F = per_fam[f]
        F["label"] = F["label"] or label.get(sid, sid)
        first = min(z)
        F["first"] = first if F["first"] is None else min(F["first"], first)
        for th in (V.TH if s["theatre"] == "global" else [s["theatre"]]):
            near = set()
            for d in allev.get(th, []):
                near.update(d + dt.timedelta(k) for k in range(-LEAD, GAP + 1))
            got = False
            for r in on[on.theatre == th].itertuples():
                w = window_max(z, r.date)
                if w is None:
                    continue
                got = True
                F["ev"].append((w, r.added, r.surprise_or_buildup))
                rows_ev.append(dict(family=f, series=sid, theatre=th, date=r.date, added=r.added, kind=r.surprise_or_buildup,
                                    description=r.description, max_z_30d=round(w, 2)))
                for k in (30, 21, 14, 7, 3, 1):
                    d = r.date - dt.timedelta(k)
                    if d in z:
                        F["prof"][k].append(z[d])
            d = max(FROM, min(z) + dt.timedelta(LEAD))
            last = max(z)
            while d <= last:
                if d not in near:
                    w = window_max(z, d)
                    if w is not None:
                        F["calm"].append(w)
                        got = True
                d += dt.timedelta(CALM_STEP)
            if got:
                F["theatres"].add(th)
    out = []
    for f, F in per_fam.items():
        if not F["ev"] or len(F["calm"]) < 10:
            continue
        calm = F["calm"]
        fa = float(np.mean([c >= CUT for c in calm]))
        res = dict(family=f, label=F["label"], first=F["first"], theatres=len(F["theatres"]), calm_windows=len(calm), false_alarm=fa)
        for nm, sel in (("all", lambda a: True), ("orig", lambda a: not a), ("added", lambda a: a)):
            w = [x[0] for x in F["ev"] if sel(x[1])]
            k = int(sum(x >= CUT for x in w))
            res[f"n_{nm}"], res[f"hits_{nm}"] = len(w), k
            res[f"hit_{nm}"] = k / len(w) if w else float("nan")
            res[f"p_{nm}"] = binom_tail(k, len(w), fa) if w else float("nan")
            res[f"auc_{nm}"] = auc(w, calm)
        for k in (30, 21, 14, 7, 3, 1):
            res[f"z_d{k}"] = float(np.mean(F["prof"][k])) if F["prof"][k] else float("nan")
        res["z_calm"] = float(np.mean(calm))
        out.append(res)
    R = pd.DataFrame(out).sort_values("p_all").reset_index(drop=True)
    m = len(R)
    R["q_all"] = np.minimum.accumulate((R.p_all * m / (np.arange(m) + 1))[::-1])[::-1].clip(upper=1)   # Benjamini-Hochberg
    return R, pd.DataFrame(rows_ev), on



def write(R, E, on):
    n_ev = len(on)
    n_add = int(on.added.sum())
    rep = R[(R.p_orig < 0.05) & (R.p_added < 0.05)]
    sig = R[R.q_all < 0.10]
    L = ["# Which indicators rose before events", "",
         "Written by `warwatch/indicatorstudy.py`. No model and no tuning: each tracked series is scored day by day as the live build "
         "scores it, turned to the warning direction, and pooled into its family. For each event the highest z in the 30 days before it is "
         f"compared with the same measure in calm 30-day windows of the same theatre. Events from 2019 on, after merging any within 30 days "
         f"of an earlier one in the same theatre: {n_ev} ({n_ev - n_add} from `events.csv`, {n_add} from `events_added.csv`). A family is "
         "only scored on events that fall after its history starts.", "",
         f"**Hit** = z reached {CUT:g} in the 30 days before. **False-alarm rate** = share of calm windows where it did. **AUC** compares the "
         "30-day maximum before events with calm windows (0.5 = no difference). **q** is the p-value corrected for testing "
         f"{len(R)} families at once (Benjamini-Hochberg). **Holds on both halves** means p < 0.05 on the original events and again on the added ones.", "",
         "## Headline", "",
         f"- Families tested: {len(R)}. Significant after correction (q < 0.10): {len(sig)}. Lead on both the original and the added events: {len(rep)}.",
         ""]
    if len(rep):
        L += ["- Holding on both halves: " + ", ".join(f"{r.family} ({r.hit_orig:.0%} and {r.hit_added:.0%} hit against {r.false_alarm:.0%} false alarms)" for r in rep.itertuples()), ""]
    L += ["## All families, ranked by p on all events", "",
          "| Family | First day | Events scored | Hit rate | False-alarm rate | AUC | p | q | Original events: hit, p | Added events: hit, p |",
          "|---|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for r in R.itertuples():
        o = f"{r.hit_orig:.0%}, {r.p_orig:.3f} (n {r.n_orig})" if r.n_orig else "n/a"
        a = f"{r.hit_added:.0%}, {r.p_added:.3f} (n {r.n_added})" if r.n_added else "n/a"
        L.append(f"| {r.family} | {r.first} | {r.n_all} | {r.hit_all:.0%} | {r.false_alarm:.0%} | {r.auc_all:.2f} | {r.p_all:.3f} | {r.q_all:.2f} | {o} | {a} |")
    L += ["", "## How the top families moved before events", "",
          "Mean warning-direction z on days before events, against the mean of calm windows' maximum.", "",
          "| Family | Day -30 | -21 | -14 | -7 | -3 | -1 | Calm window max |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in R.head(15).itertuples():
        L.append(f"| {r.family} | {r.z_d30:.2f} | {r.z_d21:.2f} | {r.z_d14:.2f} | {r.z_d7:.2f} | {r.z_d3:.2f} | {r.z_d1:.2f} | {r.z_calm:.2f} |")
    L += ["", "## Coverage: how many events each kind of indicator can be tested on", "",
          "| First day of history | Families | Median events scored |", "|---|---:|---:|"]
    R["yr"] = pd.to_datetime(R["first"]).dt.year
    for y, g in R.groupby("yr"):
        L.append(f"| {y} | {len(g)} | {int(g.n_all.median())} |")
    L.append("")
    open(OUT_MD, "w").write("\n".join(L))
    R.drop(columns="yr").to_csv(OUT_CSV, index=False)
    E.to_csv(OUT_CSV.replace(".csv", "_events.csv"), index=False)


if __name__ == "__main__":
    R, E, on = study()
    write(R, E, on)
    print(R[["family", "first", "n_all", "hit_all", "false_alarm", "auc_all", "p_all", "q_all", "p_orig", "p_added"]].head(25).to_string())
