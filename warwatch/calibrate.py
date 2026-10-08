#!/usr/bin/env python3
"""Which indicators rose before the events, and what weight should each carry? Out-of-sample test of weighting schemes.

    python3 warwatch/calibrate.py            # -> docs/CALIBRATION.md, backtest/family_evidence.csv, backtest/weight_schemes.csv

Part 1, per indicator family (all scored families in the model's panel plus the back-filled fast feeds of fastfeeds.py):
within-theatre AUC of the family's evidence against "an event follows in 1 to 30 days", an interval that resamples theatre-years, the same AUC in
2019 to 2022 and in 2023 to 2026 (a family that works in one half only is not trusted), and hit and false-alarm rates on a trailing 30-day window.

Part 2, weighting schemes compared in the model's own rolling-origin test (each test year 2021 to 2026 scored by weights fitted on earlier years
only, 30-day embargo, shrink to base rate fitted on earlier test years only). Every choice that looks at labels (which families to keep, how strongly to
shrink) is made inside the training years, so the comparison is clean except for the ridge strength, which is fixed at the model's published value:
  current   the model as published (ridge, all scored families)
  screened  keep only families whose training-period within-theatre AUC interval is above 0.5, then the same ridge
  equal     screened families at one common weight (a single number fitted on the training years)
  +fast     current, plus the back-filled fast feeds as extra families
  +fast screened   screened, over the larger set
Needs numpy, pandas, scipy.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fastfeeds as FF  # noqa: E402
import validate as V  # noqa: E402

ROOT = os.path.dirname(HERE)
LAM = 3
MIN_POS = 20
HALF = 2023


def with_fast(P, fams):
    """Add the back-filled fast feeds as evidence columns (max(0, signed z) clipped at 5, NaN where no score)."""
    Z = FF.zfast()
    P = P.copy()
    new = []
    th = P["theatre"].values
    dates = pd.DatetimeIndex(P["date"].values)
    cols = {}
    for sid, (fam, t, z) in Z.items():
        name = "fast_" + fam
        sign = -1 if fam.startswith(FF.DOWN) else 1
        s = pd.Series(z)
        s.index = pd.to_datetime(s.index)
        m = np.where(th == t)[0]
        v = np.clip(s.reindex(dates[m]).values * sign, 0, 5)
        col = cols.setdefault(name, np.full(len(P), np.nan))
        col[m] = v
    for name, col in cols.items():
        P[name] = col
    new = [c for c in cols if np.isfinite(cols[c]).sum() > 200]
    return P, fams + new


def theatre_auc(x, y, ok, th, yr, mask=None, boot=True):
    """Positive-day-weighted mean over theatres of the within-theatre AUC; also the rank-normalised score for bootstrapping."""
    a, w, yy, sc, cl = [], [], [], [], []
    for t in V.TH:
        m = ok & (th == t) & (mask if mask is not None else True)
        if m.sum() < 150 or y[m].sum() < MIN_POS:
            continue
        a.append(V.auc(y[m], x[m]))
        w.append(y[m].sum())
        yy += list(y[m])
        sc += list(pd.Series(x[m]).rank(pct=True).values)
        cl += [f"{t}{Y}" for Y in yr[m]]
    if not a:
        return float("nan"), float("nan"), float("nan"), 0
    if not boot:
        return float(np.average(a, weights=w)), float("nan"), float("nan"), int(sum(w))
    lo, hi = V.cluster_boot_auc(np.array(yy), np.array(sc), np.array(cl), B_=200)
    return float(np.average(a, weights=w)), float(lo), float(hi), int(sum(w))


def family_table(P, fams, meta, y, lab, eid):
    th, yr = P["theatre"].values, P["date"].dt.year.values
    rows = []
    for f in fams:
        x = P[f].values
        ok = lab & ~np.isnan(x)
        a, lo, hi, npos = theatre_auc(x, y, ok, th, yr)
        if npos == 0:
            continue
        a1 = theatre_auc(x, y, ok, th, yr, yr < HALF)[0]
        a2 = theatre_auc(x, y, ok, th, yr, yr >= HALF)[0]
        # trailing 30-day max of evidence by theatre, read the day before each event vs on calm days
        hit_n = hit_k = fa_n = fa_k = 0
        for t in V.TH:
            m = np.where((th == t))[0]
            xs = pd.Series(x[m])
            if xs.notna().sum() < 150:
                continue
            rm = xs.rolling(30, min_periods=15).max().values
            okm = ok[m]
            ym, em = y[m], eid[m]
            calm = okm & (ym == 0) & ~np.isnan(rm)
            fa_n += int(calm.sum())
            fa_k += int((rm[calm] >= 2.0).sum())
            for k in np.unique(em[okm & (ym == 1)]):
                sel = np.where(okm & (ym == 1) & (em == k))[0]
                if np.isnan(rm[sel[-1]]):
                    continue
                hit_n += 1
                hit_k += int(rm[sel[-1]] >= 2.0)
        dom = meta.get(f, ("fast", False))
        rows.append(dict(family=f, domain=dom[0], confirming=bool(dom[1]), auc=a, lo=lo, hi=hi, auc_2019_22=a1, auc_2023_26=a2, pos_days=npos,
                         events=hit_n, hit=hit_k / hit_n if hit_n else np.nan, false_alarm=fa_k / fa_n if fa_n else np.nan,
                         nsr=(fa_k / fa_n) / (hit_k / hit_n) if hit_n and hit_k else np.inf))
    R = pd.DataFrame(rows)
    R["stable"] = (R.lo > 0.5) & (R.auc_2019_22 > 0.5) & (R.auc_2023_26 > 0.5)
    return R.sort_values("auc", ascending=False)


# ------------------------------------------------------------------ weighting schemes
def design_cols(P, fams, hist, use):
    X = V.design(P, fams, hist)
    nb = 1 + len(V.TH) + 3
    keep = list(range(nb)) + [nb + i for i in use]
    return X[:, keep]


def scheme_oos(P, fams, hist, y, lab, scheme, screen_lo=0.5):
    """Raw out-of-sample probabilities and base rates for one scheme. scheme in {'all','screened','equal'}."""
    yr = P["date"].dt.year.values
    dates = P["date"].values
    th = P["theatre"].values
    raw = np.full(len(P), np.nan)
    base = np.full(len(P), np.nan)
    Xfull = V.design(P, fams, hist)
    nb = 1 + len(V.TH) + 3
    chosen = {}
    for Y in V.TEST_YEARS:
        cut = np.datetime64(f"{Y}-01-01") - np.timedelta64(V.EMBARGO, "D")
        tr = lab & (dates < cut)
        te = lab & (yr == Y)
        use = list(range(len(fams)))
        if scheme in ("screened", "equal"):
            use = []
            for i, f in enumerate(fams):
                x = P[f].values
                ok = tr & ~np.isnan(x)
                a, lo, hi, npos = theatre_auc(x, y, ok, th, yr)
                if npos and lo > screen_lo:
                    use.append(i)
        chosen[Y] = [fams[i] for i in use]
        cols = list(range(nb)) + [nb + i for i in use]
        X = Xfull[:, cols]
        if scheme == "equal" and use:
            # one common weight on the mean evidence of the kept families: collapse them into a single column
            ev = Xfull[:, [nb + i for i in use]]
            n = np.maximum((ev > 0).sum(1), 1)
            X = np.c_[Xfull[:, :nb], ev.sum(1) / np.sqrt(len(use))]
        lam = LAM
        if scheme == "support":
            # families seen on few positive days are shrunk harder: penalty grows as the support falls below the median
            sup = np.array([max(int(((y[tr] == 1) & ~np.isnan(P[f].values[tr])).sum()), 1) for f in fams], float)
            lam = LAM * np.clip(np.median(sup) / sup, 1.0, 20.0)
        elif scheme == "domain":
            doms = {}
            for i, f in enumerate(fams):
                doms.setdefault(DOMAIN[f], []).append(nb + i)
            cols_d = [np.sort(Xfull[:, c], axis=1)[:, -3:].mean(1) for c in doms.values()]
            X = np.c_[Xfull[:, :nb], np.column_stack(cols_d)]
        elif scheme == "aucw":
            w_ = np.zeros(len(fams))
            for i, f in enumerate(fams):
                x = P[f].values
                ok = tr & ~np.isnan(x)
                a, lo, hi, npos = theatre_auc(x, y, ok, th, yr, None, boot=False)
                if npos:
                    w_[i] = max(a - 0.5, 0.0) * min(1.0, npos / 500)
            ev = Xfull[:, [nb + i for i in range(len(fams))]]
            X = np.c_[Xfull[:, :nb], ev @ (w_ / max(w_.sum(), 1e-9))]
            chosen[Y] = [fams[i] for i in range(len(fams)) if w_[i] > 0]
        if scheme == "support":
            pen_fit = lam
        else:
            pen_fit = lam
        theta = V.fit(X[tr], y[tr], pen_fit)
        raw[te] = V.sigmoid(X[te] @ theta)
        b, _ = V.base_rates(P, y, tr)
        base[te] = np.array([b[t] for t in th[te]])
    return raw, base, chosen


def score(P, y, lab, eid, raw, base):
    yr = P["date"].dt.year.values
    pub, gp = V.nested_published(P, raw, base, y, lab)
    ok = lab & ~np.isnan(pub) & (yr >= V.TEST_YEARS[0])
    clim = V.brier(y[ok], base[ok])
    pu, yy = pub[ok], y[ok]
    top = pu >= np.quantile(pu, 0.9)
    hit, n = V.recall_at(P, eid, y, pub, ok, 0.10)
    th = P["theatre"].values[ok]
    noir = ~np.isin(th, ["iran", "israel"])
    return dict(bss=1 - V.brier(yy, pu) / clim, auc=V.auc(yy, pu), lift=float(yy[top].mean() / yy.mean()), flagged=f"{hit}/{n}",
                auc_ex_iran_israel=V.auc(yy[noir], pu[noir]),
                bss_ex_iran_israel=1 - V.brier(yy[noir], pu[noir]) / V.brier(yy[noir], base[ok][noir]))

def verdict(r, w):
    if r.pos_days <= 100:
        return "too few events to judge"
    if r.stable:
        return "supported" if w > 0 else "evidence, no weight"
    if w >= 1.0 and r.lo <= 0.5:
        return "weight ahead of evidence"
    if w > 0 and r.lo <= 0.5:
        return "weak"
    if w == 0 and r.lo > 0.5:
        return "evidence, one half only"
    return "no case"


def report(F, S, W):
    f = lambda v, n=3: "n/a" if v != v else f"{v:.{n}f}"
    L = ["# Calibration: which indicators rose before the events, and how much weight each should carry", "",
         "Generated by `warwatch/calibrate.py`. Labels: `warwatch/data/events.csv` (78 events, 2018 to 2026; the model is tested 2021 to 2026). Companion to [BACKTEST_EVENTS.md](BACKTEST_EVENTS.md) and [MODEL.md](MODEL.md).", "",
         "## 1. Weighting schemes, out of sample", "",
         "Each scheme is scored the way the model is: every test year 2021 to 2026 uses only earlier years (30-day embargo), and any choice that looks at labels is made inside those earlier years. "
         "Higher Brier skill (against each theatre's base rate), AUC and lift are better; 'ex Iran and Israel' drops the two theatres that carry most of the signal.", "",
         "| Scheme | Brier skill | AUC | Lift, top 10% of days | Events flagged at 10% false alarms | AUC ex Iran and Israel | Brier skill ex Iran and Israel | Families kept in 2026 |", "|---|---|---|---|---|---|---|---|"]
    for r in S.itertuples():
        L.append(f"| {r.scheme} | {r.bss:+.4f} | {r.auc:.3f} | {r.lift:.2f}x | {r.flagged} | {r.auc_ex_iran_israel:.3f} | {r.bss_ex_iran_israel:+.4f} | {r.families_kept_2026} |")
    L += ["", "- **current**: the published model (non-negative ridge over every scored family).",
          "- **screened**: only families whose training-period AUC interval is above 0.5, then the same ridge. **equal**: those families at one common weight.",
          "- **support-weighted ridge**: families seen on few positive days are shrunk harder. **one coefficient per domain**: the mean of each domain's three strongest readings. **AUC-weighted single index**: one coefficient on a sum weighted by training AUC.",
          "- **+fast**: current, plus the back-filled aircraft, fire, vessel, radar, hazard-warning and PLA feeds as extra families.", "",
          "## 2. Evidence per indicator family", "",
          "AUC is within theatre (0.5 = no better than chance), averaged over theatres with at least 20 positive days and weighted by those days; the interval resamples theatre-years. "
          "Halves split 2019 to 2022 and 2023 to 2026; n/a = fewer than 20 positive days there. Hit / false alarm: share of events (day before) and of calm days where the trailing 30-day maximum evidence had reached 2. "
          "'Stable' = interval above 0.5 and AUC above 0.5 in both halves. Weight = the model's fitted log-odds per full-scale reading (0 = not in the model). "
          f"With {len(F)} families, a few will clear any bar by chance (about 1 in 40 each at the 2.5% tail).", "",
          "| Family | Domain | Confirming | AUC | Interval | 2019-22 | 2023-26 | Positive days | Hit | False alarm | Weight | Verdict |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in F.itertuples():
        w = W.get(r.family, 0.0)
        L.append(f"| {r.family} | {r.domain} | {'yes' if r.confirming else 'no'} | {f(r.auc)} | {f(r.lo)} to {f(r.hi)} | {f(r.auc_2019_22)} | {f(r.auc_2023_26)} | {r.pos_days:,} | {f(r.hit, 2)} | {f(r.false_alarm, 2)} | {w:.2f} | {verdict(r, w)} |")
    return "\n".join(L) + "\n"



def main():
    global DOMAIN
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare()
    DOMAIN = {f: meta[f][0] for f in fams}
    hist = V.history_features(P, ev)
    P2, fams2 = with_fast(P, fams)
    only = [a for a in sys.argv[1:]]
    if not only:
        F = family_table(P2, fams2, meta, y, lab, eid)
        F.to_csv(os.path.join(ROOT, "backtest", "family_evidence.csv"), index=False)
    else:
        F = None
    out = []
    kept = {}
    schemes = [("current", P, fams, "all"), ("screened", P, fams, "screened"), ("equal", P, fams, "equal"), ("support-weighted ridge", P, fams, "support"),
               ("one coefficient per domain", P, fams, "domain"), ("AUC-weighted single index", P, fams, "aucw"), ("+fast", P2, fams2, "all")]
    for name, PP, ff, sch in schemes:
        if only and name not in only:
            continue
        raw, base, chosen = scheme_oos(PP, ff, hist, y, lab, sch)
        s = score(PP, y, lab, eid, raw, base)
        s["scheme"] = name
        s["families_kept_2026"] = len(chosen[2026])
        kept[name] = chosen
        out.append(s)
        print(name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}, flush=True)
    S = pd.DataFrame(out)
    if not only:
        S.to_csv(os.path.join(ROOT, "backtest", "weight_schemes.csv"), index=False)
        pd.to_pickle(dict(F=F, S=S, kept=kept), os.path.join(V.CACHE, "calibrate.pkl"))
        import json
        W = json.load(open(os.path.join(V.DATA, "model_weights.json")))["theta"]["w"]
        with open(os.path.join(ROOT, "docs", "CALIBRATION.md"), "w") as fh:
            fh.write(report(F, S, W))


if __name__ == "__main__":
    main()
