#!/usr/bin/env python3
"""Feature and methodology study: can the data WarWatch holds be turned into features, or the method changed, so the 30-day
probability rises more reliably before past events than the published model does? Plan fixed in advance: docs/FEATURESTUDY_PLAN.md.

    python3 warwatch/featurestudy.py           # every candidate on both event lists -> docs/FEATURESTUDY.md, backtest/featurestudy*.csv
    python3 warwatch/featurestudy.py --quick   # one ridge strength per candidate (lambda 3), for checking the code

Reuses validate.py for the panel, labels, fit, shrink and gates, so the baseline is the published model, scored the same way. Nothing
here writes model_weights.json, events.csv or MODEL.md. Needs numpy, pandas, scipy and scikit-learn.
"""
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import leadstudy as L  # noqa: E402
import sources as S  # noqa: E402
import validate as V  # noqa: E402

ROOT = os.path.dirname(HERE)
BACKFILL = os.path.join(ROOT, "backfill", "data")
ADDED = os.path.join(V.DATA, "events_added.csv")
OUT_MD = os.path.join(ROOT, "docs", "FEATURESTUDY.md")
OUT_CSV = os.path.join(ROOT, "backtest", "featurestudy.csv")
OUT_EV = os.path.join(ROOT, "backtest", "featurestudy_events.csv")
OUT_PROFILE = os.path.join(ROOT, "backtest", "featurestudy_profile.csv")
TH = V.TH
NT = len(TH)
CANDIDATES = ["H1", "H2", "F1", "F2", "F3", "F4", "F5", "F6", "M1"]
NAMES = {"base": "Baseline (published model)", "R0": "Reference: history only, no indicators", "H1": "Decayed conflict history", "H2": "Global tempo", "F1": "Slow build-up (GDELT)",
         "F2": "Cross-theatre attention", "F3": "Smoothed evidence", "F4": "Implied volatility", "F5": "Advisory steps",
         "F6": "Air co-occurrence", "M1": "Monotone boosted trees", "C1": "Combination"}
BOOT_N = 2000
GDELT_ROOTS = {"threat": ("13",), "posture": ("15",), "preforce": ("13", "15")}


# ------------------------------------------------------------------ events
def read_events(extended):
    ev = pd.read_csv(os.path.join(V.DATA, "events.csv"), parse_dates=["date"])
    ev["added"] = False
    if extended:
        ad = pd.read_csv(ADDED, parse_dates=["date"])
        ad["added"] = True
        ev = pd.concat([ev, ad[[c for c in ad.columns if c in ev.columns]]], ignore_index=True)
    return ev.sort_values(["date", "theatre"]).reset_index(drop=True)


# ------------------------------------------------------------------ helpers for new families
def calendar(days):
    return pd.date_range(V.START, days[-1] if len(days) else V.START, freq="D")


def roll_mad(x, win, minp):
    """Rolling median and MAD (past values only; the caller shifts)."""
    med = x.rolling(win, min_periods=minp).median()
    mad = x.rolling(win, min_periods=minp).apply(lambda a: np.median(np.abs(a[~np.isnan(a)] - np.median(a[~np.isnan(a)]))), raw=True)
    return med, mad


def mod_z(x, med, mad):
    z = 0.6745 * (x - med) / mad.where(mad > 0)
    return z.clip(-5, 5)


def daily_series(pts):
    """[(label, value)] or {date: value} -> daily pd.Series on a full calendar (missing days NaN)."""
    if isinstance(pts, dict):
        s = pd.Series({pd.Timestamp(k): v for k, v in pts.items()})
    else:
        s = pd.Series({pd.Timestamp(l[:10]): float(v) for l, v in pts})
    s = s.sort_index()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))


def read_backfill(sid):
    p = os.path.join(BACKFILL, sid + ".csv")
    if not os.path.exists(p):
        return None
    return daily_series(L.daily(p))


def slow_z(x):
    """F1: 30-day mean against the median and MAD of 30-day means over the two years ending 31 days earlier."""
    m30 = x.rolling(30, min_periods=20).mean()
    med, mad = roll_mad(m30.shift(31), 730, 365)
    return mod_z(m30, med, mad)


# ------------------------------------------------------------------ candidate families: {family: {theatre: pd.Series of evidence 0..5, indexed by the day it is known}}
def fam_F1():
    out = {}
    for key, roots in GDELT_ROOTS.items():
        for share in (False, True):
            f = f"slow_gdelt{'share' if share else ''}_{key}"
            out[f] = {}
            for t in TH:
                x = daily_series(S.gdelt_series(t, roots, share))
                out[f][t] = slow_z(x).clip(lower=0).shift(1)        # a GDELT day is public the next day
    return out


def fam_F2():
    cnt = {t: daily_series(S.gdelt_series(t, GDELT_ROOTS["preforce"])) for t in TH}
    idx = pd.date_range(min(s.index.min() for s in cnt.values()), max(s.index.max() for s in cnt.values()), freq="D")
    s7 = pd.DataFrame({t: cnt[t].reindex(idx).rolling(7, min_periods=4).sum() for t in TH})
    share = s7.div(s7.sum(1), axis=0)
    out = {"xshare_preforce": {}}
    for t in TH:
        med, mad = roll_mad(share[t].shift(31), 365, 120)
        out["xshare_preforce"][t] = mod_z(share[t], med, mad).clip(lower=0).shift(1)
    return out


def fam_F4():
    """Implied volatility, scored exactly as the live build scores a daily series (stats.score_series, point in time)."""
    out = {}
    for sid in ("vol_ovx", "vol_gvz", "vol_vix_term"):
        pts = sorted(L.daily(os.path.join(BACKFILL, sid + ".csv")).items())
        s = {"id": sid, "theatre": "global", "domain": "financial", "direction": "up", "lag": False, "kind": "daily",
             "all": [(d.isoformat(), v) for d, v in pts], "avail": [(d + dt.timedelta(days=1)).toordinal() for d, _ in pts]}
        _, r = V._zjob(s)
        e = pd.Series({pd.Timestamp(k): v for k, v in r["z"].items()}).sort_index().clip(0, 5)
        out[sid] = {t: e for t in TH}
    return out


def fam_F5():
    out = {"state_raise": {}, "state_od_new": {}}
    for t in TH:
        lv = read_backfill(f"state_{t}")
        od = read_backfill(f"state_od_{t}")
        if lv is not None:
            lv = lv.ffill()
            rise = (lv - lv.rolling(31, min_periods=1).min()).clip(lower=0)
            out["state_raise"][t] = (2.5 * rise).clip(upper=5).shift(7)          # weekly captures: known about a week later
        if od is not None:
            od = od.ffill()
            new = (od - od.rolling(31, min_periods=1).min()).clip(lower=0)
            out["state_od_new"][t] = (5.0 * new).clip(upper=5).shift(7)
    return out


def fam_F6():
    """featurelab F2: min(z tanker, max(z ISR, z fighter)), from 2024-09-16 (era B), every theatre with aircraft data."""
    out = {"air_cooccur": {}}
    start = pd.Timestamp("2024-09-16")
    for t in TH:
        z = {}
        for k in ("adsb_tanker", "adsb_isr", "adsb_fighter"):
            _, p = L.series_for(k, t)
            if p:
                zz = L.zseries(L.daily(p))
                z[k] = pd.Series({pd.Timestamp(d): v for d, v in zz.items()}).sort_index()
        if len(z) < 3:
            continue
        df = pd.DataFrame(z)
        f = np.minimum(df["adsb_tanker"], np.maximum(df["adsb_isr"], df["adsb_fighter"]))
        f = f[f.index >= start].clip(0, 5)
        out["air_cooccur"][t] = f.shift(1, freq="D")
    return out


FAMS = {"F1": fam_F1, "F2": fam_F2, "F4": fam_F4, "F5": fam_F5, "F6": fam_F6}


def attach(P, fams):
    """Add new family columns to the panel (NaN where a family has no value for that theatre-day)."""
    P = P.copy()
    key = pd.MultiIndex.from_arrays([P["theatre"].values, P["date"].values])
    for f, per in fams.items():
        col = np.full(len(P), np.nan)
        for t, s in per.items():
            m = (P["theatre"].values == t)
            col[m] = s.reindex(P["date"].values[m]).values
        P[f] = col
    return P


def smooth_evidence(P, fams, halflife=5):
    """F3: each family's evidence replaced by its exponentially weighted mean over past days (missing days count as no evidence)."""
    P = P.copy()
    for t in TH:
        m = P["theatre"].values == t
        E = P.loc[m, fams].fillna(0)
        P.loc[m, fams] = E.ewm(halflife=halflife, adjust=False).mean().values
    return P


# ------------------------------------------------------------------ history terms
def hist_decay(P, ev, halflives=(30, 180, 730), pool=False, own=True):
    """log(1 + sum exp(-ln2 * age / h)) over earlier events (own theatre, or every theatre when pool), one column per half-life."""
    cols = []
    th, dates = P["theatre"].values, P["date"].values
    for h in halflives:
        c = np.zeros(len(P))
        for t in TH:
            m = np.where(th == t)[0]
            ed = np.sort((ev["date"] if pool else ev.loc[ev["theatre"] == t, "date"]).values)
            if not len(ed):
                continue
            age = (dates[m][:, None] - ed[None, :]) / np.timedelta64(1, "D")
            w = np.where(age > 0, np.exp(-math.log(2) * np.maximum(age, 0) / h), 0.0)
            c[m] = np.log1p(w.sum(1))
        cols.append(c)
    return np.c_[tuple(cols)]


def history(P, ev, cand):
    base = V.history_features(P, ev)
    if cand == "H1":
        return np.c_[hist_decay(P, ev), base[:, 2]]                    # decayed counts plus log days since the latest event
    if cand == "H2":
        return np.c_[base, hist_decay(P, ev, halflives=(365,), pool=True)]
    return base


# ------------------------------------------------------------------ fit
def fit_lin(X, y, lam_w, nH):
    """validate.fit with a variable number of free history columns (family weights >= 0, ridge lam_w)."""
    k = X.shape[1]
    pen = np.zeros(k)
    pen[1:1 + NT] = V.LAM_T
    pen[1 + NT:1 + NT + nH] = V.LAM_H
    pen[1 + NT + nH:] = lam_w

    def f(th):
        z = X @ th
        return np.sum(np.logaddexp(0, z) - y * z) + 0.5 * np.sum(pen * th * th), X.T @ (V.sigmoid(z) - y) + pen * th

    th0 = np.zeros(k)
    th0[0] = math.log(max(y.mean(), 1e-4) / (1 - y.mean()))
    bounds = [(None, None)] * (1 + NT + nH) + [(0, None)] * (k - 1 - NT - nH)
    return minimize(f, th0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": 400}).x


def rolling(P, X, y, lab, nH, lam_w, model="lin"):
    yr = P["date"].dt.year.values
    dates = P["date"].values
    raw = np.full(len(P), np.nan)
    base = np.full(len(P), np.nan)
    th = P["theatre"].values
    for Y in V.TEST_YEARS:
        cut = np.datetime64(f"{Y}-01-01") - np.timedelta64(V.EMBARGO, "D")
        tr = lab & (dates < cut)
        te = lab & (yr == Y)
        if model == "lin":
            theta = fit_lin(X[tr], y[tr], lam_w, nH)
            raw[te] = V.sigmoid(X[te] @ theta)
        else:
            from sklearn.ensemble import HistGradientBoostingClassifier
            mono = [0] * (NT + nH) + [1] * (X.shape[1] - 1 - NT - nH)
            m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05, min_samples_leaf=300, l2_regularization=1.0,
                                               monotonic_cst=mono, early_stopping=False, random_state=0)
            m.fit(X[tr][:, 1:], y[tr])
            raw[te] = m.predict_proba(X[te][:, 1:])[:, 1]
        b, _ = V.base_rates(P, y, tr)
        base[te] = np.array([b[t] for t in th[te]])
    return raw, base


# ------------------------------------------------------------------ evaluation
def runs(flag, bridge=7):
    idx = np.where(flag)[0]
    if not len(idx):
        return []
    out, s, last = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - last - 1 > bridge:
            out.append((s, last))
            s = i
        last = i
    out.append((s, last))
    return out


def episodes(P, ev, v, ok, cut):
    """Alert episodes at a line: hit if an event in the theatre follows within 30 days of the episode's end (improve.py's rule)."""
    th, dates = P["theatre"].values, P["date"].values
    nh = nf = 0
    for t in TH:
        m = np.where((th == t) & ok)[0]
        if not len(m):
            continue
        ed = np.sort(ev.loc[ev["theatre"] == t, "date"].values)
        dd = dates[m]
        for s_, e_ in runs(v[m] >= cut):
            nxt = ed[ed > dd[s_]]
            late = (nxt[0] - dd[e_]) / np.timedelta64(1, "D") if len(nxt) else np.inf
            nh += late <= 30
            nf += late > 30
    return int(nh), int(nf)


def within_auc(y, p, th):
    num = den = 0.0
    for t in np.unique(th):
        m = th == t
        n1 = y[m].sum()
        if n1 == 0 or n1 == m.sum():
            continue
        num += n1 * V.auc(y[m], p[m])
        den += n1
    return num / den


def evaluate(P, ev, y, lab, eid, raw, base, gates=True):
    yr = P["date"].dt.year.values
    pub, gp = V.nested_published(P, raw, base, y, lab)
    ok = lab & ~np.isnan(pub) & (yr >= V.TEST_YEARS[0])
    yy, pu, th = y[ok], pub[ok], P["theatre"].values[ok]
    clim = V.brier(yy, base[ok])
    cut = np.quantile(pu[yy == 0], 0.9)
    flagged = sorted({int(e) for e in set(eid[ok & (y == 1)]) if ((eid == e) & ok & (pub >= cut)).any()})
    allev = sorted({int(e) for e in set(eid[ok & (y == 1)])})
    added = set(ev.index[ev["added"]])
    hit_ep, false_ep = episodes(P, ev, pub, ok, cut)
    per_year = {Y: V.brier(y[ok & (yr == Y)], base[ok & (yr == Y)]) - V.brier(y[ok & (yr == Y)], pub[ok & (yr == Y)]) for Y in V.TEST_YEARS}
    r = dict(bss=1 - V.brier(yy, pu) / clim, auc=V.auc(yy, pu), wauc=within_auc(yy, pu, th), flagged=len(flagged), events=len(allev),
             flagged_added=len([e for e in flagged if e in added]), events_added=len([e for e in allev if e in added]),
             hit_ep=hit_ep, false_ep=false_ep, false_per_hit=false_ep / max(hit_ep, 1), per_year=per_year, gp=gp, pub=pub, ok=ok,
             flagged_ids=flagged, cut=cut)
    if gates:
        clusters = (P["theatre"] + P["date"].dt.year.astype(str)).values[ok]
        lo, hi = V.cluster_boot_auc(yy, pu, clusters)
        sa, _ = V.shifted_control(P, y, pub, ok)
        r.update(auc_lo=float(lo), auc_hi=float(hi), shuffle_p=float((sa >= r["auc"]).mean()))
        r["gates"] = bool(r["bss"] > 0 and lo > 0.5 and r["shuffle_p"] < 0.05)
    return r


def paired_boot(P, y, ok, p_base, p_cand, n=BOOT_N, seed=7):
    """One-sided p that the candidate's Brier is not lower than the baseline's, resampling theatre-years."""
    cl = (P["theatre"] + P["date"].dt.year.astype(str)).values[ok]
    u, inv = np.unique(cl, return_inverse=True)
    d = (p_base[ok] - y[ok]) ** 2 - (p_cand[ok] - y[ok]) ** 2          # positive = candidate better
    s = np.bincount(inv, weights=d, minlength=len(u))
    c = np.bincount(inv, minlength=len(u)).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(u), size=(n, len(u)))
    stat = s[pick].sum(1) / c[pick].sum(1)
    return float((stat <= 0).mean()), float(d.mean())


def per_event(P, ev, y, lab, r):
    """Day-before probability of each scorable event and its percentile among the theatre's out-of-sample calm days."""
    pub, ok = r["pub"], r["ok"]
    th, dates = P["theatre"].values, P["date"].values
    rows = []
    for k, e in ev.iterrows():
        if e.date < pd.Timestamp(f"{V.TEST_YEARS[0]}-01-01"):
            continue
        m = np.where((th == e.theatre) & ok & (dates < np.datetime64(e.date)) & (dates >= np.datetime64(e.date - pd.Timedelta(days=30))))[0]
        if len(m) < 10:
            continue
        calm = pub[(th == e.theatre) & ok & (y == 0)]
        p1 = pub[m[-1]]
        rows.append(dict(event=k, date=e.date.date(), theatre=e.theatre, type=e.type, kind=e.surprise_or_buildup, added=bool(e.added),
                         description=e.description, p_day1=p1, pctile_day1=float((calm < p1).mean() * 100), p_max30=float(pub[m].max()),
                         flagged=bool(k in r["flagged_ids"])))
    return pd.DataFrame(rows)


def profile(P, ev, r, days=60):
    """Mean published probability over the theatre's base by day relative to scorable events, -days..-1."""
    pub, ok = r["pub"], r["ok"]
    g = pd.DataFrame({"date": P["date"].values, "theatre": P["theatre"].values, "p": np.where(ok, pub, np.nan)})
    base = g.groupby("theatre")["p"].median()
    piv = g.pivot(index="date", columns="theatre", values="p")
    out = {}
    for _, e in ev.iterrows():
        if e.date < pd.Timestamp(f"{V.TEST_YEARS[0]}-01-01") or e.theatre not in piv:
            continue
        s = piv[e.theatre].reindex(pd.date_range(e.date - pd.Timedelta(days=days), e.date - pd.Timedelta(days=1))).values / base[e.theatre]
        if np.isfinite(s[-10:]).sum() >= 5:
            out[(e.date, e.theatre)] = s
    M = np.array(list(out.values()))
    return pd.Series(np.nanmean(M, 0), index=range(-days, 0))


# ------------------------------------------------------------------ driver
class Study:
    def __init__(self, quick=False):
        self.quick = quick
        t0 = time.time()
        self.H = V.zhistory()
        self.through = V.events_through()
        self.P0, self.meta = V.panel(self.H, end=self.through)
        self.fams0 = [c for c in self.P0.columns if c in self.meta and self.P0[c].notna().sum() > 200]
        self.newfams = {}
        for c, f in FAMS.items():
            self.newfams[c] = f()
            print(f"{c}: {', '.join(self.newfams[c])} built ({time.time() - t0:.0f}s)", flush=True)

    def setup(self, cands, ev):
        P = self.P0
        fams = list(self.fams0)
        for c in cands:
            if c in FAMS:
                add = {k: v for k, v in self.newfams[c].items() if v}
                P = attach(P, add)
                fams += [f for f in add if P[f].notna().sum() > 200]
        if "F3" in cands:
            P = smooth_evidence(P, fams)
        y, excl, unk, eid = V.labels(P, ev, self.through)
        lab = ~excl & ~unk
        hist = V.history_features(P, ev)
        if "H1" in cands:
            hist = history(P, ev, "H1")
        if "H2" in cands:
            hist = np.c_[hist, hist_decay(P, ev, halflives=(365,), pool=True)]
        X = V.design(P, fams, hist)
        if "R0" in cands:
            X, fams = X[:, :1 + NT + hist.shape[1]], []
        return P, fams, X, y, lab, eid, hist.shape[1]

    def run(self, cands, ev):
        P, fams, X, y, lab, eid, nH = self.setup(cands, ev)
        yr = P["date"].dt.year.values
        model = "hgb" if "M1" in cands else "lin"
        lams = [3] if (self.quick or model == "hgb") else list(V.LAMBDAS)
        best = None
        for lam in lams:
            raw, base = rolling(P, X, y, lab, nH, lam, model)
            pub, _ = V.nested_published(P, raw, base, y, lab)
            ok = lab & ~np.isnan(pub) & (yr >= V.TEST_YEARS[0])
            b = V.brier(y[ok], pub[ok])
            if best is None or b < best[0]:
                best = (b, lam, raw, base)
        _, lam, raw, base = best
        r = evaluate(P, ev, y, lab, eid, raw, base)
        r.update(lam=lam if model == "lin" else None, nfam=len(fams), P=P, y=y, lab=lab, eid=eid)
        return r


def summary_row(name, r, rb=None, P=None):
    row = dict(candidate=name, name=NAMES.get(name, name), bss=r["bss"], auc=r["auc"], within_auc=r["wauc"], flagged=r["flagged"], events=r["events"],
               flagged_added=r["flagged_added"], events_added=r["events_added"], hit_episodes=r["hit_ep"], false_episodes=r["false_ep"],
               false_per_hit=r["false_per_hit"], auc_lo=r.get("auc_lo"), shuffle_p=r.get("shuffle_p"), gates=r.get("gates"), lam=r.get("lam"))
    if rb is not None:
        ok = rb["ok"] & r["ok"]
        p, d = paired_boot(P, rb["y"], ok, rb["pub"], r["pub"])
        row.update(boot_p=p, brier_gain=d, years_better=int(sum(r["per_year"][Y] > rb["per_year"][Y] for Y in V.TEST_YEARS)))
        row["per_year_gain_1e4"] = ";".join(f"{1e4 * (r['per_year'][Y] - rb['per_year'][Y]):+.1f}" for Y in V.TEST_YEARS)
    return row


def holm(ps):
    order = np.argsort(ps)
    m = len(ps)
    adj = np.empty(m)
    run_max = 0.0
    for k, i in enumerate(order):
        run_max = max(run_max, min(1.0, (m - k) * ps[i]))
        adj[i] = run_max
    return adj


def verdicts(df, cur):
    """Apply the plan's pass rule. df: extended-list rows (with baseline first), cur: current-list rows keyed by candidate."""
    b = df[df.candidate == "base"].iloc[0]
    rows = df[df.candidate.isin(CANDIDATES)].copy()
    rows["holm_p"] = holm(rows["boot_p"].values)
    out = []
    for _, r in rows.iterrows():
        fails = []
        if not r.boot_p < 0.05:
            fails.append(f"Brier not better (p = {r.boot_p:.2f})")
        if r.auc < b.auc or r.within_auc < b.within_auc:
            fails.append("AUC lower")
        if r.flagged < b.flagged or r.false_per_hit > b.false_per_hit:
            fails.append("fewer events flagged or more false alarms per hit")
        if r.years_better < 4:
            fails.append(f"better in {r.years_better} of 6 years")
        if not r.gates:
            fails.append("fails a model gate")
        c = cur.get(r.candidate)
        if c is not None and c["bss"] < cur["base"]["bss"]:
            fails.append("worse on the current 78 events")
        ok_unc = not fails
        verdict = "passes" if ok_unc and r.holm_p < 0.05 else ("promising, not proven" if ok_unc else "fails")
        out.append(dict(candidate=r.candidate, holm_p=r.holm_p, verdict=verdict, detail="; ".join(fails) if fails else "meets rules 1 to 6"))
    return pd.DataFrame(out)


def main():
    quick = "--quick" in sys.argv
    st = Study(quick)
    ev_cur = read_events(False)
    ev_ext = read_events(True)
    print(f"events: current {len(ev_cur)}, extended {len(ev_ext)}", flush=True)
    res = {"current": {}, "extended": {}}
    for lst, ev in (("current", ev_cur), ("extended", ev_ext)):
        for c in ["base", "R0"] + CANDIDATES:
            t0 = time.time()
            res[lst][c] = st.run([] if c == "base" else [c], ev)
            r = res[lst][c]
            print(f"{lst:8s} {c:4s} bss {r['bss']:+.4f} auc {r['auc']:.3f} wauc {r['wauc']:.3f} flagged {r['flagged']}/{r['events']} "
                  f"false/hit {r['false_per_hit']:.1f} gates {r.get('gates')} lam {r.get('lam')} ({time.time() - t0:.0f}s)", flush=True)
    tables = {}
    for lst in res:
        rb = res[lst]["base"]
        tables[lst] = pd.DataFrame([summary_row("base", rb)] + [summary_row(c, res[lst][c], rb, rb["P"]) for c in ["R0"] + CANDIDATES])
    cur = {c: {"bss": res["current"][c]["bss"]} for c in res["current"]}
    V_ = verdicts(tables["extended"], cur)
    combo = list(V_.loc[V_.verdict != "fails", "candidate"])
    if combo:
        for lst, ev in (("current", ev_cur), ("extended", ev_ext)):
            r = st.run(combo, ev)
            res[lst]["C1"] = r
            rb = res[lst]["base"]
            tables[lst] = pd.concat([tables[lst], pd.DataFrame([summary_row("C1", r, rb, rb["P"])])], ignore_index=True)
    out = pd.concat([t.assign(events_list=lst) for lst, t in tables.items()], ignore_index=True)
    out.to_csv(OUT_CSV, index=False)
    # event-by-event and the pre-event profile, baseline against every candidate, extended list
    rb = res["extended"]["base"]
    E = per_event(rb["P"], ev_ext, rb["y"], rb["lab"], rb).rename(columns={"p_day1": "p_day1_base", "pctile_day1": "pctile_base", "flagged": "flagged_base"})
    E = E.drop(columns=["p_max30"])
    prof = {"base": profile(rb["P"], ev_ext, rb)}
    for c in [c for c in res["extended"] if c not in ("base", "R0")]:
        r = res["extended"][c]
        e = per_event(r["P"], ev_ext, r["y"], r["lab"], r)[["event", "pctile_day1", "flagged"]].rename(columns={"pctile_day1": f"pctile_{c}", "flagged": f"flagged_{c}"})
        E = E.merge(e, on="event", how="left")
        prof[c] = profile(r["P"], ev_ext, r)
    E.to_csv(OUT_EV, index=False)
    pd.DataFrame(prof).to_csv(OUT_PROFILE, index_label="day")
    write_report(tables, V_, combo, E, prof, ev_cur, ev_ext, res)


def fmt(x, f="{:+.4f}"):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f.format(x)


def write_report(tables, Vd, combo, E, prof, ev_cur, ev_ext, res):
    L_ = ["# Feature and methodology study", "",
          "Written by `warwatch/featurestudy.py` to the plan fixed in advance in [FEATURESTUDY_PLAN.md](FEATURESTUDY_PLAN.md). Everything is out of sample: "
          "each test year 2021 to 2026 is scored by a model fitted on earlier years only (30-day embargo), with the shrink toward the base rate fitted on earlier test years only. "
          "Nothing here changes the live page, `model_weights.json` or `events.csv`.", "",
          f"Event lists: current {len(ev_cur)} events (`events.csv`); extended {len(ev_ext)} (`events.csv` plus the {int(ev_ext.added.sum())} in `events_added.csv`).", ""]
    for lst in ("extended", "current"):
        t = tables[lst]
        L_ += [f"## Results on the {lst} list", "",
               "| Candidate | Brier skill | AUC | Within-theatre AUC | Events flagged | of which added events | False episodes per hit | Brier gain vs baseline (x1e-4) | Bootstrap p | Years better | Gates |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
        for _, r in t.iterrows():
            L_.append(f"| {r['name']} | {r.bss:+.4f} | {r.auc:.3f} | {r.within_auc:.3f} | {r.flagged}/{r.events} | {r.flagged_added}/{r.events_added} | {r.false_per_hit:.1f} | "
                      f"{fmt(r.get('brier_gain', np.nan) * 1e4 if r.candidate != 'base' else np.nan, '{:+.2f}')} | {fmt(r.get('boot_p', np.nan), '{:.3f}')} | "
                      f"{'' if r.candidate == 'base' else int(r.years_better)} | {'pass' if r.gates else 'FAIL'} |")
        L_.append("")
    L_ += ["## Verdicts (pass rule from the plan, on the extended list)", "", "| Candidate | Holm-corrected p | Verdict | Detail |", "|---|---:|---|---|"]
    for _, r in Vd.iterrows():
        L_.append(f"| {NAMES[r.candidate]} | {r.holm_p:.3f} | {r.verdict} | {r.detail} |")
    L_ += ["", f"Combination run (C1): {', '.join(NAMES[c] for c in combo) if combo else 'not run, no candidate met rules 1 to 6'}.", ""]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(L_) + "\n")
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
