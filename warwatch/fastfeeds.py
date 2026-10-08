#!/usr/bin/env python3
"""Backtest the back-filled fast feeds (aircraft, fires, ships, radar, hazard warnings, PLA counts) against the labelled events.

    python3 warwatch/fastfeeds.py            # -> docs/BACKTEST_FASTFEEDS.md, backtest/fastfeeds.csv
    python3 warwatch/fastfeeds.py --refresh  # rebuild the point-in-time scores (backtest/cache/zfast.pkl)

These feeds only expose "now", so the model of docs/MODEL.md could not use them. The back-fills (backfill/data, Phase 3) give them history; this
scores each exactly as the live build would (stats.score_series, one day of delay) and asks, per family: does it rise before events more than on
calm days? It does not change any weight. A family earns a place in the model only if it clears the same bar as the model itself.

Per family, over theatre-days with a score, labels as in docs/EVENTS.md (positive = an event follows in 1 to 30 days; the 30 days after an event
are left out):
- AUC within theatre, averaged over theatres with at least 20 positive days and weighted by positive days; the interval resamples theatre-years.
- Event hit rate: share of events where the trailing 30-day maximum of the evidence (max(0, z), clipped at 5) read at the day before had reached 2; false-alarm rate: share of calm days where that trailing maximum was at least 2 (same window).
- NSR = false-alarm rate / hit rate (below 1 = fires more before events than on calm days).
Direction is declared up (more is worse) except radar ship counts (fewer ships), as in catalog.py; AUC if reversed is shown so a wrong direction is visible.
"""
import bisect
import datetime as dt
import glob
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402
import stats  # noqa: E402
import validate as V  # noqa: E402

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "backfill", "data")
CACHE = os.path.join(V.CACHE, "zfast.pkl")
PREFIX = ("adsb", "firms_frp", "firms", "nga_new", "nga", "ais_presence", "sar", "pla")
DOWN = ("sar",)
ZMIN = 2.0
MIN_POS = 20


def load():
    """{series id: (family, theatre, [(iso date, value)])} for every back-filled daily series that maps to a theatre."""
    out = {}
    for path in sorted(glob.glob(os.path.join(DATA, "*.csv"))):
        name = os.path.basename(path)[:-4]
        pre = next((p for p in PREFIX if name.startswith(p + "_") or name == p), None)
        if pre is None:
            continue
        rest = name[len(pre):].lstrip("_")
        if pre == "pla":
            fam, th = name, "taiwan"
        else:
            th, cls = None, ""
            for t in sorted(V.TH, key=len, reverse=True):
                if rest == t:
                    th = t
                elif rest.startswith(t + "_"):
                    th, cls = t, rest[len(t) + 1:]
                elif rest.endswith("_" + t):
                    th, cls = t, rest[:-len(t) - 1]
                if th:
                    break
            if th is None:
                continue
            fam = pre + ("_" + cls if cls else "")
        pts = []
        with open(path) as f:
            for line in f:
                a = line.strip().split(",")
                if len(a) >= 2 and re.match(r"\d{4}-\d\d-\d\d$", a[0]):
                    try:
                        pts.append((a[0], float(a[1])))
                    except ValueError:
                        pass
        if len(pts) > 200:
            out[name] = (fam, th, sorted(pts))
    return out


def _job(item):
    sid, (fam, th, pts) = item
    avail = [(dt.date.fromisoformat(d) + dt.timedelta(days=1)).toordinal() for d, _ in pts]
    z = {}
    d = max(dt.date.fromisoformat(pts[0][0]) + dt.timedelta(days=60), V.ZSTART)
    end = dt.date.fromisoformat(pts[-1][0]) + dt.timedelta(days=1)
    while d <= end:
        cut = bisect.bisect_right(avail, d.toordinal())
        w = pts[max(0, cut - V.KEEP):cut]
        if w:
            r = stats.score_series(w, "daily")
            if r is not None:
                z[d] = r["z"]
        d += dt.timedelta(days=1)
    return sid, (fam, th, z)


def zfast(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        return pickle.load(open(CACHE, "rb"))
    from multiprocessing import Pool
    items = list(load().items())
    with Pool(min(8, os.cpu_count() or 1)) as p:
        res = dict(p.map(_job, items, chunksize=3))
    os.makedirs(V.CACHE, exist_ok=True)
    pickle.dump(res, open(CACHE, "wb"))
    return res


def evaluate(Z, P, y, lab, eid):
    dates = P["date"].values
    th = P["theatre"].values
    yr = P["date"].dt.year.values
    fams = {}
    for sid, (fam, t, z) in Z.items():
        fams.setdefault(fam, []).append((sid, t, z))
    rows = []
    for fam, lst in sorted(fams.items()):
        sign = -1 if fam.startswith(DOWN) else 1
        per = {}
        pooled = {"y": [], "e": [], "cl": [], "er": []}
        hit_ev, n_ev, fa_n, fa_k, leads = set(), set(), 0, 0, []
        for sid, t, z in lst:
            allm = np.where(th == t)[0]
            zs = pd.Series(z)
            zs.index = pd.to_datetime(zs.index)
            vfull = zs.reindex(pd.DatetimeIndex(dates[allm])).values
            e_full = pd.Series(np.clip(vfull * sign, 0, 5))
            # trailing 30-day maximum: the same quantity for an event (read the day before it) and for a calm day
            rmax = e_full.rolling(30, min_periods=15).max().values
            keep = lab[allm] & ~np.isnan(vfull)
            if keep.sum() < 100:
                continue
            m, v, rm = allm[keep], vfull[keep], rmax[keep]
            yy = y[m]
            e_up, e_dn = np.clip(v * sign, 0, 5), np.clip(-v * sign, 0, 5)
            per[t] = (yy, e_up, e_dn, yr[m])
            for k in np.unique(eid[m][yy == 1]):
                n_ev.add((t, int(k)))
                sel = (eid[m] == k) & (yy == 1)
                last = np.where(sel)[0][-1]          # the day before the event
                if rm[last] >= ZMIN:
                    hit_ev.add((t, int(k)))
                    first = np.where(sel & (e_up >= ZMIN))[0]
                    if len(first):
                        leads.append(int((dates[m][last] - dates[m][first[0]]) / np.timedelta64(1, "D")) + 1)
            calm = yy == 0
            ok_ = calm & ~np.isnan(rm)
            fa_n += int(ok_.sum())
            fa_k += int((rm[ok_] >= ZMIN).sum())
        if not per:
            continue
        a_up, a_dn, w_, boots = [], [], [], []
        allp = {"y": [], "e": [], "cl": []}
        for t, (yy, eu, ed, yrs) in per.items():
            if yy.sum() < MIN_POS or (yy == 0).sum() < 100:
                continue
            a_up.append(V.auc(yy, eu))
            a_dn.append(V.auc(yy, ed))
            w_.append(yy.sum())
            allp["y"] += list(yy)
            allp["e"] += list(eu - 0.0)
            allp["cl"] += [f"{t}{Y}" for Y in yrs]
        if not w_:
            rows.append(dict(family=fam, theatres=len(per), events=len(n_ev), pos_days=int(sum(p[0].sum() for p in per.values())), auc=np.nan))
            continue
        # within-theatre AUC pooled by ranking inside each theatre: bootstrap over theatre-years of the rank-normalised evidence
        tot = float(np.average(a_up, weights=w_))
        # a within-theatre percentile-rank score so that pooling across theatres does not mix levels
        yy_all, sc_all, cl_all = [], [], []
        for t, (yy, eu, ed, yrs) in per.items():
            if yy.sum() < MIN_POS or (yy == 0).sum() < 100:
                continue
            r = pd.Series(eu).rank(pct=True).values
            yy_all += list(yy)
            sc_all += list(r)
            cl_all += [f"{t}{Y}" for Y in yrs]
        lo, hi = V.cluster_boot_auc(np.array(yy_all), np.array(sc_all), np.array(cl_all), B_=300)
        hr = len(hit_ev) / len(n_ev) if n_ev else np.nan
        fr = fa_k / fa_n if fa_n else np.nan
        rows.append(dict(family=fam, theatres=len(per), scored_theatres=len(w_), events=len(n_ev), pos_days=int(sum(w_)), auc=tot, auc_lo=float(lo), auc_hi=float(hi),
                         auc_reversed=float(np.average(a_dn, weights=w_)), hit=hr, false_alarm=fr, nsr=fr / hr if hr else np.inf,
                         median_lead=float(np.median(leads)) if leads else np.nan, events_hit=len(hit_ev),
                         first=min(min(z) for _, _, z in lst).isoformat(), pass_bar=bool(lo > 0.5 and hr > 0 and fr / hr < 1)))
    return pd.DataFrame(rows)


def report(R):
    L = ["# Back-filled fast feeds against the labelled events", "",
         "Generated by `warwatch/fastfeeds.py`. Each back-filled feed (Phase 3: `backfill/data`) is scored point by point exactly as the live build scores it "
         "(`stats.score_series`, one day of publication delay), then compared with the 78 labelled events (`docs/EVENTS.md`; positive = an event follows in 1 to 30 days, "
         "the 30 days after an event left out). **This does not change any weight.** It tells you which of the feeds the probability model has not been using would earn one.", "",
         "How to read it: AUC is within theatre (0.5 = coin flip), averaged over theatres with at least 20 positive days and weighted by those days; the interval resamples theatre-years. "
         f"Hit = share of events where the feed had reached z >= {ZMIN:g} at some point in the 30 days up to the day before; false alarm = share of calm days where it had in the trailing 30 days (same window, so the two rates compare); NSR = false alarm / hit (below 1 is better than noise). "
         "'AUC if reversed' tests the opposite direction: a large value there means the declared direction is wrong or the feed is two-sided. "
         "A feed clears the bar when the lower end of its AUC interval is above 0.5 and its NSR is below 1; the bar is the model's own gate, applied to one feed at a time, "
         f"so with {len(R)} families some will clear it by chance (about 1 in 40 at the 2.5% tail).", ""]
    L += ["| Feed family | Theatres tested | Events | Positive days | AUC | 95% interval | AUC if reversed | Hit | False alarm | NSR | Median lead (days) | Clears bar |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in R.sort_values("auc", ascending=False).itertuples():
        if r.auc != r.auc:
            L.append(f"| {r.family} | {r.theatres} | {r.events} | {r.pos_days} | n/a (under {MIN_POS} positive days per theatre) | | | | | | | |")
            continue
        L.append(f"| {r.family} | {r.scored_theatres} | {r.events} | {r.pos_days} | {r.auc:.3f} | {r.auc_lo:.3f} to {r.auc_hi:.3f} | {r.auc_reversed:.3f} | {r.hit:.1%} | {r.false_alarm:.1%} | {r.nsr:.2f} | "
                 f"{'n/a' if r.median_lead != r.median_lead else f'{r.median_lead:.0f}'} | {'yes' if r.pass_bar else 'no'} |")
    return "\n".join(L) + "\n"


def main():
    Z = zfast("--refresh" in sys.argv)
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare()
    R = evaluate(Z, P, y, lab, eid)
    R.to_csv(os.path.join(ROOT, "backtest", "fastfeeds.csv"), index=False)
    txt = report(R)
    with open(os.path.join(ROOT, "docs", "BACKTEST_FASTFEEDS.md"), "w") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
