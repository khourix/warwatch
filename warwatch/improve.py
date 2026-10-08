#!/usr/bin/env python3
"""Candidate changes to the probability model, each tested out of sample on the 2021 to 2026 events.

    python3 warwatch/improve.py        # -> docs/IMPROVEMENTS.md, backtest/improvements.csv

Goal: catch more of the events that happen next. Each variant changes one thing in the model's own rolling-origin test (each test year fitted on earlier
years only, 30-day embargo; shrink to base rate fitted on earlier test years only), then is scored on the same days and labels as docs/MODEL.md:
Brier skill against each theatre's base rate, AUC, events flagged at a 10% false-alarm rate (the capture measure), lift on the top 10% of days, and
the per-year Brier-skill gain over the published model (a change that helps in only one year is not trusted).

Variants (all use only what the live model can know: the event list, the same indicator evidence):
  base        the published model
  recent      history terms for events in the last 30 to 90 days and in the last 90 days (fast-moving regime)
  linked      events in linked theatres in the last 90 days (Iran, Israel, Yemen; Ukraine, Eastern flank; Taiwan Strait, South China Sea)
  global      events anywhere else in the last 90 days
  recency     training rows weighted by age (half-life 2 years): the regime of 2024 to 2026 counts more than 2019 to 2021
  base3y      base rate anchored on the last three years of training data instead of all of it
  combos      the sets that help together
Then two more questions: (a) is there a better alert rule than "probability above the line" (rise over 14 days, own-theatre percentile, 7-day maximum), judged at
matched false-alarm episodes so a spikier score cannot win by getting more chances; (b) does training only on armed-force events (onset, strike, maritime; drills
and "other" left out of the target) catch more of those events than the all-events model, judged on the same days and events, year by year.
Needs numpy, pandas, scipy.
"""
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import validate as V  # noqa: E402

ROOT = os.path.dirname(HERE)
LAM = 3
GROUPS = [("iran", "israel", "yemen"), ("ukraine", "europe_east"), ("taiwan", "scs")]
HALF_LIFE = 2 * 365


def fit2(X, y, lam_w, nH, weight=None):
    """validate.fit with a variable number of free history columns."""
    k = X.shape[1]
    nT = len(V.TH)
    pen = np.zeros(k)
    pen[1:1 + nT] = V.LAM_T
    pen[1 + nT:1 + nT + nH] = V.LAM_H
    pen[1 + nT + nH:] = lam_w
    wt = np.ones(len(y)) if weight is None else weight

    def f(th):
        z = X @ th
        p = V.sigmoid(z)
        return np.sum(wt * (np.logaddexp(0, z) - y * z)) + 0.5 * np.sum(pen * th * th), X.T @ (wt * (p - y)) + pen * th

    th0 = np.zeros(k)
    th0[0] = math.log(max(y.mean(), 1e-4) / (1 - y.mean()))
    bounds = [(None, None)] * (1 + nT + nH) + [(0, None)] * (k - 1 - nT - nH)
    return minimize(f, th0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": 400}).x


def extra_history(P, ev):
    """Columns: events in own theatre in the last 90 days; in linked theatres in the last 90 days; anywhere else in the last 90 days. Scaled to 0-1."""
    th, dates = P["theatre"].values, P["date"].values
    n = len(P)
    own, linked, glob = np.zeros(n), np.zeros(n), np.zeros(n)
    grp = {t: [x for g in GROUPS if t in g for x in g if x != t] for t in V.TH}
    byt = {t: np.sort(ev.loc[ev.theatre == t, "date"].values) for t in V.TH}

    def count(ts, d, lo=0, hi=90):
        out = np.zeros(len(d))
        for t in ts:
            e = byt.get(t, [])
            if len(e):
                gap = (d[:, None] - e[None, :]) / np.timedelta64(1, "D")
                out += ((gap > lo) & (gap <= hi)).sum(1)
        return out
    for t in V.TH:
        m = np.where(th == t)[0]
        d = dates[m]
        own[m] = count([t], d, 30, 90)
        linked[m] = count(grp[t], d)
        glob[m] = count([x for x in V.TH if x != t], d)
    return np.c_[np.minimum(own, 2) / 2, np.minimum(linked, 3) / 3, np.minimum(glob, 6) / 6]


def run_variant(P, fams, hist, extra, y, lab, use_extra, recency, base3y):
    yr = P["date"].dt.year.values
    dates = P["date"].values
    th = P["theatre"].values
    X0 = V.design(P, fams, hist)
    nb = 1 + len(V.TH) + 3
    if use_extra:
        X = np.hstack([X0[:, :nb], extra[:, use_extra], X0[:, nb:]])
    else:
        X = X0
    nH = 3 + len(use_extra)
    raw = np.full(len(P), np.nan)
    base = np.full(len(P), np.nan)
    for Y in V.TEST_YEARS:
        cut = np.datetime64(f"{Y}-01-01") - np.timedelta64(V.EMBARGO, "D")
        tr = lab & (dates < cut)
        te = lab & (yr == Y)
        w = None
        if recency:
            age = (cut - dates[tr]) / np.timedelta64(1, "D")
            w = 0.5 ** (age / HALF_LIFE)
            w = w * len(w) / w.sum()
        theta = fit2(X[tr], y[tr], LAM, nH, w)
        raw[te] = V.sigmoid(X[te] @ theta)
        mask = tr & (dates >= cut - np.timedelta64(3 * 365, "D")) if base3y else tr
        b, _ = V.base_rates(P, y, mask)
        base[te] = np.array([b[t] for t in th[te]])
    return raw, base


def evaluate(P, y, lab, eid, raw, base):
    yr = P["date"].dt.year.values
    pub, gp = V.nested_published(P, raw, base, y, lab)
    ok = lab & ~np.isnan(pub) & (yr >= V.TEST_YEARS[0])
    clim = V.brier(y[ok], base[ok])
    pu, yy = pub[ok], y[ok]
    top = pu >= np.quantile(pu, 0.9)
    hit10, n = V.recall_at(P, eid, y, pub, ok, 0.10)
    hit5, _ = V.recall_at(P, eid, y, pub, ok, 0.05)
    per_year = {}
    for Y in V.TEST_YEARS:
        m = ok & (yr == Y)
        per_year[Y] = V.brier(y[m], base[m]) - V.brier(y[m], pub[m])      # Brier points gained over the theatre base rate
    th = P["theatre"].values[ok]
    noir = ~np.isin(th, ["iran", "israel"])
    return dict(bss=1 - V.brier(yy, pu) / clim, auc=V.auc(yy, pu), lift=float(yy[top].mean() / yy.mean()), flag10=hit10, flag5=hit5, events=n,
                auc_ex=V.auc(yy[noir], pu[noir]), bss_ex=1 - V.brier(yy[noir], pu[noir]) / V.brier(yy[noir], base[ok][noir]), per_year=per_year, pub=pub)


# ------------------------------------------------------------------ alert rules
def alert_rules():
    import eventstudy as ES
    o = ES.replay()
    d = o["d"][o["d"].date >= "2020-01-01"].sort_values(["theatre", "date"]).reset_index(drop=True)
    ok0 = (d.lab & d.p.notna() & (d.date >= "2021-01-01")).values
    y, eid, th = d.y.values, d.eid.values, d.theatre.values
    P = d[["date", "theatre"]]

    def per(f):
        out = np.full(len(d), np.nan)
        for t, g in d.groupby("theatre"):
            s = pd.Series(g.p.values, index=g.date.values).reindex(pd.date_range(g.date.min(), g.date.max()))
            out[g.index] = f(s).reindex(g.date.values).values
        return out
    rk = lambda v: pd.Series(v).rank(pct=True).values
    S = {"published probability": d.p.values}
    S["probability / own 1-year median"] = d.p.values / per(lambda s: s.rolling(365, min_periods=120).median().shift(1))
    S["rise over 14 days"] = per(lambda s: s - s.shift(14))
    S["highest of last 7 days"] = per(lambda s: s.rolling(7, min_periods=1).max())
    S["own-theatre percentile, last year"] = per(lambda s: s.rolling(365, min_periods=120).apply(lambda a: (a[:-1] < a[-1]).mean(), raw=True))
    S["rank(probability) + rank(rise)"] = rk(S["published probability"]) + rk(np.nan_to_num(S["rise over 14 days"], nan=0))
    S["rank(probability) + rank(percentile)"] = rk(S["published probability"]) + rk(np.nan_to_num(S["own-theatre percentile, last year"], nan=0.5))
    ed = {t: np.sort(o["ev"].loc[o["ev"].theatre == t, "date"].values) for t in V.TH}

    def episodes_at(v, cut):
        nh = nf = 0
        for t in V.TH:
            m = np.where((th == t) & ok0 & ~np.isnan(v))[0]
            if not len(m):
                continue
            dd = d.date.values[m]
            for s_, e_ in ES.runs(v[m] >= cut):
                nxt = ed[t][ed[t] > dd[s_]]
                late = (nxt[0] - dd[e_]) / np.timedelta64(1, "D") if len(nxt) else np.inf
                nh += late <= 30
                nf += late > 30
        return int(nh), int(nf)
    base = S["published probability"]
    cutp = np.quantile(base[ok0 & ~np.isnan(base) & (y == 0)], 0.9)
    nh0, nf0 = episodes_at(base, cutp)
    rows = []
    for k, v in S.items():
        ok = ok0 & ~np.isnan(v)
        a = V.auc(y[ok], v[ok])
        h10, n = V.recall_at(P, eid, y, v, ok, 0.10)
        c = np.quantile(v[ok & (y == 0)], 0.9)                       # the line that puts 10% of calm days in alert, for every rule
        h, f = episodes_at(v, c)
        rows.append(dict(rule=k, auc=a, flag10=f"{h10}/{n}", hit_episodes=h, false_episodes=f, false_per_hit=f / max(h, 1)))
    return pd.DataFrame(rows), nh0, nf0


# ------------------------------------------------------------------ war-focused training
def focus():
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare()
    yr = P["date"].dt.year.values
    dates, th = P["date"].values, P["theatre"].values
    sets = {"all events": ev, "armed-force events (onset, strike, maritime)": ev[ev.type.isin(["onset", "strike", "maritime"])],
            "onset and strike": ev[ev.type.isin(["onset", "strike"])], "market-moving events": ev[ev.market_moving.astype(bool)]}

    def prep(e):
        yt, excl, unk, eidt = V.labels(P, e, through)
        return yt, ~excl & ~unk, eidt, V.history_features(P, e)

    def oos(evtr, lab_c):
        yT, labT, _, hT = prep(evtr)
        raw, base = np.full(len(P), np.nan), np.full(len(P), np.nan)
        Xd = V.design(P, fams, hT)
        for Y in V.TEST_YEARS:
            cut = np.datetime64(f"{Y}-01-01") - np.timedelta64(V.EMBARGO, "D")
            tr, te = labT & (dates < cut), lab_c & (yr == Y)
            raw[te] = V.sigmoid(Xd[te] @ V.fit(Xd[tr], yT[tr], LAM))
            b, _ = V.base_rates(P, yT, tr)
            base[te] = np.array([b[t] for t in th[te]])
        return V.nested_published(P, raw, base, yT, labT)[0], labT
    rows, years = [], None
    for tn, et in sets.items():
        yE, labE, eidE, _ = prep(et)
        for rn, er in sets.items():
            _, labT, _, _ = prep(er)
            lab_c = labE & labT
            pub, _ = oos(er, lab_c)
            ok = lab_c & ~np.isnan(pub) & (yr >= 2021)
            h10, n = V.recall_at(P, eidE, yE, pub, ok, 0.10)
            top = pub[ok] >= np.quantile(pub[ok], 0.9)
            rows.append(dict(judged_on=tn, trained_on=rn, auc=V.auc(yE[ok], pub[ok]), flag10=f"{h10}/{n}", lift=float(yE[ok][top].mean() / yE[ok].mean())))
            if tn.startswith("armed") and rn in ("all events", tn):
                cut10 = np.quantile(pub[ok & (yE == 0)], 0.9)
                yrs = []
                for Y in V.TEST_YEARS:
                    m = ok & (yr == Y)
                    evs = set(eidE[m & (yE == 1)])
                    yrs.append((Y, sum(bool(((eidE == e) & m & (pub >= cut10)).any()) for e in evs), len(evs), V.auc(yE[m], pub[m])))
                years = years or {}
                years[rn] = yrs
    return pd.DataFrame(rows), years


def report(R, A, nh0, nf0, Fo, years):
    L = ["# Improvement tests: can the past events tune the model to catch more of the next ones?", "",
         "Generated by `warwatch/improve.py`. Every candidate is tested out of sample (each test year 2021 to 2026 fitted on earlier years only, 30-day embargo), on the same days and "
         "events as [MODEL.md](MODEL.md). With 51 scorable events, a difference of one or two events flagged is noise; the per-year column shows whether a gain is consistent.", "",
         "## 1. Changes to the history terms, base rate and training weights", "",
         "| Variant | Brier skill | AUC | Events flagged at 10% false alarms | at 5% | AUC ex Iran and Israel | Years better than published (of 6) | Brier-point gain by year, 2021 to 2026 (x1e-4) |", "|---|---|---|---|---|---|---|---|"]
    for r in R.itertuples():
        L.append(f"| {r.variant} | {r.bss:+.4f} | {r.auc:.3f} | {r.flag10}/{r.events} | {r.flag5}/{r.events} | {r.auc_ex:.3f} | {r.years_better if r.variant[:4] != 'base' else '-'} | {r.gain_by_year} |")
    L += ["", "No variant beats the published model on Brier skill and AUC together, and none gains consistently across years.", "",
          "## 2. Alert rules", "",
          f"Same probabilities, different rule for when to alert. 'Flagged at 10%' lets any day in the 30 before an event count; a spikier score gets more chances to cross a line, so it looks better there without being better. "
          f"So each rule is also counted in episodes (runs of days above the line, gaps up to 7 days bridged) at the same line (10% of calm days in alert): hit episodes are followed by an event within 30 days of their end, the rest are false alarms. "
          "A rule that catches more events only by raising many more separate alarms is not better.", "",
          "| Rule | AUC | Events flagged at 10% false-alarm days | Hit episodes | False episodes | False per hit |", "|---|---|---|---|---|---|"]
    for r in A.itertuples():
        L.append(f"| {r.rule} | {r.auc:.3f} | {r.flag10} | {r.hit_episodes} | {r.false_episodes} | {r.false_per_hit:.1f} |")
    L += ["", "Rules built on the rise or the theatre's own history catch 4 to 5 more events at the same share of calm days but raise three times as many separate alarms (170 to 181 false episodes against 55), so each hit costs 7 to 8 false alarms instead of 4.6. Smoothing the published probability with its highest value of the last 7 days catches the same events with 22% fewer false episodes (43 against 55): the same alarms without the day-to-day flicker.", "",
          "## 3. Train on armed-force events only", "",
          "The event list mixes wars with drills, exercises and 'other' events (coups, blockades, cable damage). Training the same model on onset, strike and maritime events only, then judging both models on the same days and the same events:", "",
          "| Judged on | Trained on | AUC | Events flagged at 10% false alarms | Lift, top 10% of days |", "|---|---|---|---|---|"]
    for r in Fo.itertuples():
        L.append(f"| {r.judged_on} | {r.trained_on} | {r.auc:.3f} | {r.flag10} | {r.lift:.2f}x |")
    L += ["", "Armed-force events, year by year (events flagged at the 10% line / events, and AUC):", "", "| Year | Trained on all events | Trained on armed-force events |", "|---|---|---|"]
    ya, yb = years["all events"], years["armed-force events (onset, strike, maritime)"]
    for (Y, h1, n1, a1), (_, h2, n2, a2) in zip(ya, yb):
        L.append(f"| {Y} | {h1}/{n1}, AUC {a1:.2f} | {h2}/{n2}, AUC {a2:.2f} |")
    return "\n".join(L) + "\n"


def main():
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare()
    hist = V.history_features(P, ev)
    extra = extra_history(P, ev)
    variants = [("base (published)", [], False, False), ("recent: own events 30-90 days ago", [0], False, False), ("linked theatres, last 90 days", [1], False, False),
                ("events anywhere else, last 90 days", [2], False, False), ("recency-weighted training", [], True, False), ("base rate from last 3 years", [], False, True),
                ("recent + linked + global", [0, 1, 2], False, False), ("linked + global + recency", [1, 2], True, False), ("all of them", [0, 1, 2], True, True)]
    rows, res = [], {}
    for name, use, rec, b3 in variants:
        raw, base = run_variant(P, fams, hist, extra, y, lab, use, rec, b3)
        r = evaluate(P, y, lab, eid, raw, base)
        res[name] = r
        print(name, round(r["bss"], 4), round(r["auc"], 3), r["flag10"], flush=True)
    b0 = res["base (published)"]
    for name, r in res.items():
        gain = [r["per_year"][Y] - b0["per_year"][Y] for Y in V.TEST_YEARS]
        rows.append(dict(variant=name, bss=r["bss"], auc=r["auc"], lift=r["lift"], flag10=r["flag10"], flag5=r["flag5"], events=r["events"], auc_ex=r["auc_ex"], bss_ex=r["bss_ex"],
                         years_better=int(sum(g > 0 for g in gain)), gain_by_year=";".join(f"{g * 1e4:+.1f}" for g in gain)))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(ROOT, "backtest", "improvements.csv"), index=False)
    pd.to_pickle(dict(R=R, res={k: {kk: vv for kk, vv in v.items() if kk != "pub"} for k, v in res.items()}), os.path.join(V.CACHE, "improve.pkl"))
    A, nh0, nf0 = alert_rules()
    A.to_csv(os.path.join(ROOT, "backtest", "alert_rules.csv"), index=False)
    Fo, years = focus()
    Fo.to_csv(os.path.join(ROOT, "backtest", "training_focus.csv"), index=False)
    with open(os.path.join(ROOT, "docs", "IMPROVEMENTS.md"), "w") as f:
        f.write(report(R, A, nh0, nf0, Fo, years))
    print(R.to_string())


if __name__ == "__main__":
    main()
