#!/usr/bin/env python3
"""Validation, fitting and reporting for the 30-day probability model (warwatch/model.py serves what this writes).

    python3 warwatch/validate.py panel    # point-in-time evidence for every family and theatre-day -> backtest/cache/panel.pkl
    python3 warwatch/validate.py report   # rolling-origin test, gates, shuffled-timing control -> docs/MODEL.md
    python3 warwatch/validate.py fit      # report, then fit on all history and write warwatch/data/model_weights.json
    python3 warwatch/validate.py fit-armed  # the same on armed-force events only -> model_weights_armed.json, docs/MODEL_ARMED.md (hidden shadow model)

Unlike the live build this needs numpy, pandas and scipy. It reads only committed data: backtest/history (prices, transits, advisories,
procurement, trade, conflict counts, GDELT and GPSJam histories) and warwatch/data/events.csv (the labels, see docs/EVENTS.md).

The model: log-odds of an event in the theatre within 30 days = theatre intercept (partially pooled) + conflict history
+ sum over families of weight x evidence, with evidence = max(0, z)/5 and every family weight constrained to be zero or positive.
Ridge penalties stand in for a rare-events correction; a fitted shrink toward each theatre's base rate (gamma) and a floor (phi)
correct the over- and under-confidence the rolling-origin test shows. See docs/MODEL.md for the numbers and the gates.
"""
import datetime as dt
import json
import math
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backtest as B  # noqa: E402
import catalog  # noqa: E402
import config as C  # noqa: E402
import sources as S  # noqa: E402
import stats  # noqa: E402

ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(ROOT, "backtest", "cache")
MODEL_PATH = os.path.join(DATA, "model_weights.json")
TH = [t for t in C.THEATRES if t != "global"]
HORIZON, POST = 30, 30        # label window; days after an event left out so an ongoing war is not a success
START, ZSTART = "2019-01-01", dt.date(2018, 6, 1)
TEST_YEARS = range(2021, 2027)
EMBARGO = 30                  # training rows whose label window reaches into the test year are dropped
BANDS = (0.05, 0.10, 0.25)    # Watch, Elevated, Critical, as 30-day probabilities
LEVELS = ("Normal", "Watch", "Elevated", "Critical")
LAMBDAS = (0.3, 1, 3, 10, 30, 100)   # ridge strength on family weights (evidence is scaled to 0-1)
LAM_T, LAM_H = 10.0, 1.0      # theatre intercepts pooled toward the global one; conflict-history terms
BASE_PRIOR = 1000             # pseudo-days of the pooled base rate mixed into each theatre's base rate
# The archive families (adsb, state, firms, nga, ais presence, package) were tried in the fit on
# 2026-10-08: the gates went from PASS (shuffle p 0.027, AUC 0.628) to FAIL (p 0.097, AUC 0.601), because
# nearly all of them have noise-to-signal near or above 1. So the fit leaves them out until a re-run
# says otherwise; WARWATCH_BACKFILL_FIT=1 turns them on to re-test as history accumulates.
USE_BACKFILL = os.environ.get("WARWATCH_BACKFILL_FIT") == "1"
BACKFILL_LAG = {"adsb_": 1, "package_": 1, "firms_": 1, "nga_": 1, "state_": 7, "ais_presence_": 6}   # days after the date a value was public
KEEP = 450                    # points of history a point-in-time score may see (a year baseline needs ~400 days)
BOOT = 40
EVENT_TYPES = None            # set by `fit-armed`: train and label on these event types only (the hidden armed-force model)
REPORT = "MODEL.md"


# ------------------------------------------------------------------ data
def read_events():
    ev = pd.read_csv(os.path.join(DATA, "events.csv"), parse_dates=["date"])
    if EVENT_TYPES:
        ev = ev[ev["type"].isin(EVENT_TYPES)].reset_index(drop=True)
    return ev


def events_through():
    with open(os.path.join(DATA, "events_through.txt")) as f:
        return pd.Timestamp(f.read().strip())


def build_series():
    """Every series the model may use, as dicts with all points and the day each became public."""
    out = [s for s in B.load_series() if s["scored"]]
    for s in catalog.SERIES:
        if s["id"].startswith(("gdelt_", "gdeltshare_")) and s["scored"]:
            pts = s["fetch"]()
            out.append({"id": s["id"], "theatre": s["theatre"], "domain": s["domain"], "direction": s["direction"], "lag": s["lag"],
                        "kind": "daily", "all": pts, "avail": [(dt.date.fromisoformat(l) + dt.timedelta(days=1)).toordinal() for l, _ in pts]})
    import csv
    import gzip
    per = {}
    with gzip.open(os.path.join(ROOT, "backtest", "history", "gpsjam_theatre_day.csv.gz"), "rt", newline="") as f:
        for d, th, good, bad in csv.reader(f):
            good, bad = int(good), int(bad)
            if good + bad >= 20:
                per.setdefault(th, []).append((d, 100.0 * bad / (good + bad)))
    cat = {s["id"]: s for s in catalog.SERIES}
    for th, pts in per.items():
        pts.sort()
        c = cat.get(f"gpsjam_{th}")
        if c and c["scored"]:
            out.append({"id": c["id"], "theatre": th, "domain": c["domain"], "direction": c["direction"], "lag": c["lag"], "kind": "daily", "all": pts,
                        "avail": [(dt.date.fromisoformat(l) + dt.timedelta(days=1)).toordinal() for l, _ in pts]})
    if USE_BACKFILL:
        out.extend(backfill_series())
    return out


def backfill_series():
    """Series the live catalogue scores whose long history is in backfill/data (aircraft, advisories, fires, warnings, vessel presence,
    and the strike-package index built from the aircraft classes). Same ids and definitions as live, so the family weights carry over."""
    import store
    out = []
    for c in catalog.SERIES:
        sid = c["id"]
        lag = next((v for k, v in BACKFILL_LAG.items() if sid.startswith(k)), None)
        if lag is None or not c["scored"] or c["kind"] != "daily":
            continue
        pts = catalog._package(sid[len("package_"):])() if sid.startswith("package_") else store.backfill(sid)
        if len(pts) < 200:
            continue
        out.append({"id": sid, "theatre": c["theatre"], "domain": c["domain"], "direction": c["direction"], "lag": c["lag"], "kind": "daily", "all": pts,
                    "avail": [(dt.date.fromisoformat(l[:10]) + dt.timedelta(days=lag)).toordinal() for l, _ in pts]})
    return out


def _zjob(s):
    import bisect
    z = {}
    end = dt.date.today()
    d = ZSTART
    while d <= end:
        cut = bisect.bisect_right(s["avail"], d.toordinal())
        pts = s["all"][max(0, cut - KEEP):cut]
        if pts:
            r = stats.score_series(pts, s["kind"])
            if r is not None:
                z[d] = r["z"]
        d += dt.timedelta(days=1)
    return s["id"], {k: s[k] for k in ("theatre", "domain", "direction", "lag", "kind")} | {"z": z}


def zhistory(refresh=False):
    """{series id: meta + {date: z}}: each series scored point by point exactly as the live build scores it."""
    path = os.path.join(CACHE, "zhist.pkl" if USE_BACKFILL else "zhist_nobackfill.pkl")
    if os.path.exists(path) and not refresh:
        return pickle.load(open(path, "rb"))
    series = build_series()
    t0 = time.time()
    from multiprocessing import Pool
    with Pool(min(8, os.cpu_count() or 1)) as p:
        res = dict(p.map(_zjob, series, chunksize=4))
    print(f"scored {len(res)} series in {time.time() - t0:.0f}s", flush=True)
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(res, open(path, "wb"))
    return res


def family(sid):
    import re
    m = re.match(f"^adsb_(?:{'|'.join(TH)})_(\\w+)$", sid)   # one family per aircraft class, pooled across theatres
    return f"adsb_{m.group(1)}" if m else re.sub(f"_({'|'.join(TH)})$", "", sid)


def panel(H, end=None):
    """Theatre-day evidence table: one column per family, evidence = max(0, warning-direction z) clipped at 5, NaN where the feed has no score."""
    end = end or pd.Timestamp(dt.date.today())
    days = pd.date_range(START, end, freq="D")
    cols = {t: {} for t in TH}
    meta = {}
    for sid, s in H.items():
        f = family(sid)
        sgn = {"up": 1, "down": -1}.get(s["direction"], 0)
        z = pd.Series({pd.Timestamp(k): v for k, v in s["z"].items()}).reindex(days)
        e = (z * sgn if sgn else z.abs()).clip(0, 5)
        meta[f] = (s["domain"], bool(s["lag"]))
        for t in (TH if s["theatre"] == "global" else [s["theatre"]]):
            cols[t][f] = e.values
    frames = []
    for t in TH:
        df = pd.DataFrame(cols[t], index=days)
        df["theatre"] = t
        frames.append(df)
    P = pd.concat(frames)
    P.index.name = "date"
    return P.reset_index(), meta


def labels(P, ev, through):
    """y: an event in this theatre follows within 1..30 days. excl: 0..30 days after one. unk: label window not fully inside the events file."""
    n = len(P)
    y = np.zeros(n, int)
    excl = np.zeros(n, bool)
    th, dates = P["theatre"].values, P["date"].values
    eid = np.full(n, -1)
    evl = list(ev.itertuples(index=False))
    byt = {}
    for k, e in enumerate(evl):
        byt.setdefault(e.theatre, []).append((np.datetime64(e.date), k))
    for t in TH:
        m = np.where(th == t)[0]
        d = dates[m]
        for ed, k in byt.get(t, []):
            ahead = (ed - d) / np.timedelta64(1, "D")
            hit = (ahead >= 1) & (ahead <= HORIZON)
            y[m[hit]] = 1
            eid[m[hit & (eid[m] < 0)]] = k
            excl[m[(ahead <= 0) & (ahead >= -POST)]] = True
    unk = P["date"].values > np.datetime64(through - pd.Timedelta(days=HORIZON))
    return y, excl, unk, eid


def history_features(P, ev):
    """Conflict history known on each day: events in the last year and three years, and days since the latest."""
    n = len(P)
    h1, h3, since = np.zeros(n), np.zeros(n), np.full(n, 3650.0)
    th, dates = P["theatre"].values, P["date"].values
    for t in TH:
        m = np.where(th == t)[0]
        ed = np.sort(ev.loc[ev["theatre"] == t, "date"].values)
        if not len(ed):
            continue
        d = dates[m]
        before = ed[None, :] < d[:, None]
        gap = (d[:, None] - ed[None, :]) / np.timedelta64(1, "D")
        h1[m] = (before & (gap <= 365)).sum(1)
        h3[m] = (before & (gap <= 1095)).sum(1)
        g = np.where(before, gap, np.inf).min(1)
        since[m] = np.where(np.isinf(g), 3650.0, np.minimum(g, 3650.0))
    return np.c_[np.minimum(h1, 3) / 3, np.minimum(h3, 5) / 5, np.log1p(since) / np.log1p(3650)]


def design(P, fams, hist):
    """Columns: global intercept, 13 theatre offsets, 3 history terms, families (evidence / 5, 0 where missing)."""
    T = np.array([[t == x for x in TH] for t in P["theatre"].values], float)
    E = P[fams].fillna(0).values / 5.0
    return np.hstack([np.ones((len(P), 1)), T, hist, E])


# ------------------------------------------------------------------ model
def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fit(X, y, lam_w, theta0=None, weight=None):
    """Penalised logistic regression. Theatre offsets (ridge LAM_T) and history terms (ridge LAM_H) are free; family weights are >= 0 with ridge lam_w."""
    k = X.shape[1]
    nT, nH = len(TH), 3
    pen = np.zeros(k)
    pen[1:1 + nT] = LAM_T
    pen[1 + nT:1 + nT + nH] = LAM_H
    pen[1 + nT + nH:] = lam_w
    wt = np.ones(len(y)) if weight is None else weight

    def f(th):
        z = X @ th
        p = sigmoid(z)
        ll = np.sum(wt * (np.logaddexp(0, z) - y * z)) + 0.5 * np.sum(pen * th * th)
        g = X.T @ (wt * (p - y)) + pen * th
        return ll, g

    if theta0 is None:
        theta0 = np.zeros(k)
        theta0[0] = math.log(max(y.mean(), 1e-4) / (1 - y.mean()))
    bounds = [(None, None)] * (1 + nT + nH) + [(0, None)] * (k - 1 - nT - nH)
    r = minimize(f, theta0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": 400})
    return r.x


def base_rates(P, y, mask):
    """Each theatre's base rate from the rows in mask, mixed with the pooled rate (BASE_PRIOR pseudo-days)."""
    g = y[mask].mean()
    th = P["theatre"].values
    out = {}
    for t in TH:
        m = mask & (th == t)
        out[t] = (y[m].sum() + BASE_PRIOR * g) / (m.sum() + BASE_PRIOR)
    return out, g


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def shrink(p_raw, b, gamma, phi):
    """Pull toward the theatre's base rate (in log-odds) and floor at a share of it."""
    p = sigmoid(logit(b) + gamma * (logit(p_raw) - logit(b)))
    return np.maximum(p, phi * b)


def auc(y, s):
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return (r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def level_of(p):
    return LEVELS[sum(p >= b for b in BANDS)]


# ------------------------------------------------------------------ rolling origin
def rolling(P, X, y, lab, lam_w):
    """Out-of-sample raw probabilities and base rates for each test year, training on earlier years only (30-day embargo)."""
    yr = P["date"].dt.year.values
    dates = P["date"].values
    raw = np.full(len(P), np.nan)
    base = np.full(len(P), np.nan)
    th = P["theatre"].values
    for Y in TEST_YEARS:
        cut = np.datetime64(f"{Y}-01-01") - np.timedelta64(EMBARGO, "D")
        tr = lab & (dates < cut)
        te = lab & (yr == Y)
        theta = fit(X[tr], y[tr], lam_w)
        raw[te] = sigmoid(X[te] @ theta)
        b, _ = base_rates(P, y, tr)
        base[te] = np.array([b[t] for t in th[te]])
    return raw, base


def fit_shrink(raw, base, y, ok):
    """Grid search for (gamma, phi) minimising Brier on the rows in ok."""
    best = None
    for g in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        for ph in (0.0, 0.25, 0.5, 0.75):
            b = brier(y[ok], shrink(raw[ok], base[ok], g, ph))
            if best is None or b < best[0]:
                best = (b, g, ph)
    return best[1], best[2]


def nested_published(P, raw, base, y, lab):
    """Published probability for each OOS row, with (gamma, phi) fitted only on earlier test years (defaults for the first two)."""
    yr = P["date"].dt.year.values
    pub = np.full(len(P), np.nan)
    gp = {}
    for Y in TEST_YEARS:
        te = lab & (yr == Y) & ~np.isnan(raw)
        prev = lab & (yr < Y) & (yr >= TEST_YEARS[0]) & ~np.isnan(raw)
        g, ph = fit_shrink(raw, base, y, prev) if Y >= TEST_YEARS[0] + 2 else (0.6, 0.5)
        gp[Y] = (g, ph)
        pub[te] = shrink(raw[te], base[te], g, ph)
    return pub, gp


def cluster_boot_auc(y, p, clusters, B_=500, seed=1):
    rng = np.random.default_rng(seed)
    uc = np.unique(clusters)
    idx = {c: np.where(clusters == c)[0] for c in uc}
    out = []
    for _ in range(B_):
        pick = rng.choice(uc, len(uc))
        ii = np.concatenate([idx[c] for c in pick])
        a = auc(y[ii], p[ii])
        if not np.isnan(a):
            out.append(a)
    return np.percentile(out, [2.5, 97.5])


def shifted_control(P, y, p, ok, n=300, seed=2):
    """Circularly shift each theatre's probabilities (keeps their autocorrelation, breaks their timing): AUC and Brier skill under no relation."""
    rng = np.random.default_rng(seed)
    th = P["theatre"].values
    rows = {t: np.where((th == t) & ~np.isnan(p))[0] for t in TH}
    aucs, bss = [], []
    clim = np.nanmean(y[ok])
    for _ in range(n):
        q = p.copy()
        for t, r in rows.items():
            if len(r) > 200:
                q[r] = np.roll(p[r], rng.integers(60, len(r) - 60))
        aucs.append(auc(y[ok], q[ok]))
        bss.append(1 - brier(y[ok], q[ok]) / brier(y[ok], np.full(ok.sum(), clim)))
    return np.array(aucs), np.array(bss)


def recall_at(P, eid, y, p, ok, fpr=0.10):
    neg = p[ok & (y == 0)]
    cut = np.quantile(neg, 1 - fpr)
    evs = sorted(set(eid[ok & (y == 1)]))
    hit = sum(bool(((eid == e) & ok & (p >= cut)).any()) for e in evs)
    return hit, len(evs)


# ------------------------------------------------------------------ report
def nsr_table(P, fams, meta, y, lab, eid):
    rows = []
    for f in fams:
        x = P[f].values
        ok = lab & ~np.isnan(x)
        if y[ok].sum() < 50:
            continue
        best = None
        for c in (1.0, 1.5, 2.0, 2.5, 3.0):
            sig = x >= c
            hit = (sig & ok & (y == 1)).sum() / (ok & (y == 1)).sum()
            fa = (sig & ok & (y == 0)).sum() / (ok & (y == 0)).sum()
            if hit == 0:
                continue
            if best is None or fa / hit < best[1]:
                best = (c, fa / hit, hit, fa)
        if best:
            evs = sorted(set(eid[ok & (y == 1)]))
            got = sum(bool(((eid == e) & ok & (x >= best[0])).any()) for e in evs)
            rows.append({"family": f, "domain": meta[f][0], "confirming": meta[f][1], "threshold": best[0], "hit": best[2], "false_alarm": best[3],
                         "nsr": best[1], "events": f"{got}/{len(evs)}"})
    return pd.DataFrame(rows).sort_values("nsr")


def prepare(refresh=False):
    H = zhistory(refresh)
    ev = read_events()
    through = events_through()
    P, meta = panel(H, end=through)
    y, excl, unk, eid = labels(P, ev, through)
    fams = [c for c in P.columns if c in meta and P[c].notna().sum() > 200]
    X = design(P, fams, history_features(P, ev))
    lab = ~excl & ~unk
    return P, meta, fams, X, y, lab, eid, ev, through


def run(write):
    P, meta, fams, X, y, lab, eid, ev, through = prepare()
    yr = P["date"].dt.year.values
    ok0 = lab & (yr >= TEST_YEARS[0])
    sel = {}
    for lam in LAMBDAS:
        raw, base = rolling(P, X, y, lab, lam)
        ok = ok0 & ~np.isnan(raw)
        pub, gp = nested_published(P, raw, base, y, lab)
        sel[lam] = (brier(y[ok], pub[ok]), raw, base, pub, gp)
        print(f"lambda {lam}: OOS Brier {sel[lam][0]:.5f}", flush=True)
    lam = min(sel, key=lambda k: sel[k][0])
    _, raw, base, pub, gp = sel[lam]
    ok = ok0 & ~np.isnan(pub)
    clim = brier(y[ok], base[ok])
    bss = 1 - brier(y[ok], pub[ok]) / clim
    bss_raw = 1 - brier(y[ok], raw[ok]) / clim
    a = auc(y[ok], pub[ok])
    clusters = (P["theatre"] + P["date"].dt.year.astype(str)).values[ok]
    lo, hi = cluster_boot_auc(y[ok], pub[ok], clusters)
    sa, sb = shifted_control(P, y, pub, ok)
    p_auc = float((sa >= a).mean())
    p_bss = float((sb >= bss).mean())
    gates = {"bss": round(bss, 4), "auc": round(a, 3), "auc_lo": round(float(lo), 3), "auc_hi": round(float(hi), 3),
             "shuffle_p_auc": round(p_auc, 3), "shuffle_p_bss": round(p_bss, 3), "bss_positive": bool(bss > 0), "auc_lo_above_half": bool(lo > 0.5),
             "beats_shuffled": bool(p_auc < 0.05), "pass": bool(bss > 0 and lo > 0.5 and p_auc < 0.05)}
    print(json.dumps(gates), flush=True)
    # bands, per theatre, calibration, events
    pu = pub[ok]
    yy = y[ok]
    bands = []
    cuts = (0,) + BANDS + (1.01,)
    for i, nm in enumerate(LEVELS):
        m = (pu >= cuts[i]) & (pu < cuts[i + 1])
        bands.append((nm, f"{cuts[i]:.0%} to {min(cuts[i + 1], 1):.0%}" if i < 3 else "25% or more", m.mean(), yy[m].mean() if m.any() else float("nan"), pu[m].mean() if m.any() else float("nan"), int(m.sum())))
    th = P["theatre"].values[ok]
    per = []
    for t in TH:
        m = th == t
        if yy[m].sum() == 0:
            per.append((t, int(yy[m].sum()), float("nan"), float("nan")))
            continue
        per.append((t, int(yy[m].sum()), 1 - brier(yy[m], pu[m]) / brier(yy[m], base[ok][m]), auc(yy[m], pu[m])))
    rec10 = recall_at(P, eid, y, pub, ok)
    top = pu >= np.quantile(pu, 0.9)
    lift = yy[top].mean() / yy.mean()
    nsr = nsr_table(P, fams, meta, y, lab, eid)
    out = dict(lam=lam, gp=gp, gates=gates, bands=bands, per=per, rec10=rec10, lift=lift, top_rate=yy[top].mean(), base=yy.mean(), n=int(ok.sum()),
               pos=int(yy.sum()), events=len(set(eid[ok & (y == 1)])), bss_raw=bss_raw, sel={k: v[0] for k, v in sel.items()}, nsr=nsr,
               shuf_auc=(float(np.percentile(sa, 50)), float(np.percentile(sa, 95))), through=through)
    # reliability of published probabilities
    edges = [0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3, 1.01]
    rel = []
    for i in range(len(edges) - 1):
        m = (pu >= edges[i]) & (pu < edges[i + 1])
        if m.sum() >= 30:
            rel.append((edges[i], edges[i + 1], int(m.sum()), float(pu[m].mean()), float(yy[m].mean())))
    out["rel"] = rel
    out["pub"] = pub
    out["P"], out["fams"], out["meta"], out["X"], out["y"], out["lab"], out["ev"] = P, fams, meta, X, y, lab, ev
    if write:
        final(out)
    write_report(out)
    return out


def final(o):
    """Fit on everything, bootstrap theatre-years for intervals, write the model file."""
    P, fams, X, y, lab, ev = o["P"], o["fams"], o["X"], o["y"], o["lab"], o["ev"]
    theta = fit(X[lab], y[lab], o["lam"])
    b, g = base_rates(P, y, lab)
    gam, phi = fit_shrink_all(o)
    yrs = P["date"].dt.year.values
    cl = (P["theatre"] + pd.Series(yrs).astype(str)).values
    rng = np.random.default_rng(3)
    uc = np.unique(cl[lab])
    boots = []
    t0 = time.time()
    for i in range(BOOT):
        pick = rng.choice(uc, len(uc))
        cnt = pd.Series(pick).value_counts()
        w = pd.Series(cl).map(cnt).fillna(0).values.astype(float)
        boots.append(fit(X[lab], y[lab], o["lam"], theta0=theta, weight=w[lab]))
    print(f"bootstrap {BOOT} refits in {time.time() - t0:.0f}s", flush=True)
    nT, nH = len(TH), 3
    nz = [i for i in range(len(fams)) if theta[1 + nT + nH + i] > 1e-6 or any(bt[1 + nT + nH + i] > 1e-6 for bt in boots)]
    def pack(th):
        return {"a0": round(float(th[0]), 5), "delta": {t: round(float(th[1 + k]), 5) for k, t in enumerate(TH)},
                "hist": [round(float(x), 5) for x in th[1 + nT:1 + nT + nH]],
                "w": {fams[i]: round(float(th[1 + nT + nH + i]), 5) for i in nz}}
    mm = ev.groupby("theatre")["market_moving"].agg(["sum", "count"])
    anyday = np.zeros(len(P), bool)
    for t in TH:
        m = (P["theatre"].values == t)
        anyday[m] = y[m] == 1
    byday = pd.Series(anyday & lab).groupby(P["date"].values).max()
    labday = pd.Series(lab).groupby(P["date"].values).max()
    p_any = float(byday[labday].mean())
    pub_max = float(np.nanmax(o["pub"][o["lab"] & ~np.isnan(o["pub"])]))
    model = {"version": "1.0.0", "p_cap": round(min(0.95, math.ceil(max(pub_max, 0.3) / 0.05) * 0.05), 2), "fitted": dt.date.today().isoformat(), "data_through": str(P["date"].max().date()), "events_through": str(o["through"].date()),
             "n_events": int(len(ev)), "lambda_w": o["lam"], "gamma": gam, "phi": phi, "bands": list(BANDS), "levels": list(LEVELS),
             "base": {t: round(float(b[t]), 5) for t in TH}, "pooled_base": round(float(g), 5), "p_any_clim": round(p_any, 4),
             "mm_share": {t: round(float(mm.loc[t, "sum"] / mm.loc[t, "count"]), 3) if t in mm.index else 0.0 for t in TH},
             "theta": pack(theta), "boot": [pack(bt) for bt in boots], "gates": o["gates"], "active": bool(o["gates"]["pass"]),
             "validation": {"test_years": [TEST_YEARS[0], TEST_YEARS[-1]], "oos_days": o["n"], "oos_positive_days": o["pos"], "oos_events": o["events"],
                            "bss_raw": round(o["bss_raw"], 4), "top_decile_rate": round(float(o["top_rate"]), 4), "base_rate": round(float(o["base"]), 4)}}
    os.makedirs(DATA, exist_ok=True)
    with open(MODEL_PATH, "w") as f:
        json.dump(model, f, indent=1)
    o["model"] = model
    print("wrote", MODEL_PATH, "active" if model["active"] else "inactive (gates not passed)")


def fit_shrink_all(o):
    P, y, lab = o["P"], o["y"], o["lab"]
    raw, base = rolling(P, o["X"], y, lab, o["lam"])
    ok = lab & ~np.isnan(raw) & (P["date"].dt.year.values >= TEST_YEARS[0])
    return fit_shrink(raw, base, y, ok)


def write_report(o):
    g = o["gates"]
    L = ["# Probability model: validation report", "",
         f"Generated by `warwatch/validate.py`. Labels: `warwatch/data/events.csv` ({len(o['ev'])} events, complete through {o['through'].date()}); definition in `docs/EVENTS.md`. "
         f"A theatre-day is positive when an event in that theatre follows within 1 to 30 days; the 30 days after each event are left out.", "",
         "## Gates", "",
         "Nothing the model says reaches the live page until all three pass on out-of-sample data (rolling origin: each test year is scored by a model fitted on earlier years only, with a 30-day embargo).", "",
         "| Gate | Result | Pass |", "|---|---|---|",
         f"| Brier skill against each theatre's own base rate is positive | {g['bss']:+.4f} (before the shrink: {o['bss_raw']:+.4f}) | {'yes' if g['bss_positive'] else 'NO'} |",
         f"| Lower end of the AUC interval is above 0.5 | AUC {g['auc']:.3f}, 95% interval {g['auc_lo']:.3f} to {g['auc_hi']:.3f} (resampling theatre-years) | {'yes' if g['auc_lo_above_half'] else 'NO'} |",
         f"| Beats a shuffled-timing control | p = {g['shuffle_p_auc']:.3f} on AUC, {g['shuffle_p_bss']:.3f} on Brier skill (300 circular shifts per theatre; shifted AUC median {o['shuf_auc'][0]:.3f}, 95th percentile {o['shuf_auc'][1]:.3f}) | {'yes' if g['beats_shuffled'] else 'NO'} |",
         "", f"**Overall: {'PASS. The model drives the levels on the live page.' if g['pass'] else 'FAIL. The model runs in shadow (probabilities are logged to the forward record but the page keeps the composite levels).'}**", "",
         f"Test years {TEST_YEARS[0]} to {TEST_YEARS[-1]}: {o['n']:,} theatre-days, {o['pos']:,} positive, {o['events']} events. Ridge strength chosen from {list(LAMBDAS)} by out-of-sample Brier "
         f"(lambda = {o['lam']}); this one choice used the same test years, so treat the gates as a little optimistic. The forward record is the clean test. "
         f"Shrink toward the base rate (gamma, phi) is refitted each year on earlier test years only: " + ", ".join(f"{y}: {a:.1f}/{b:.2f}" for y, (a, b) in o["gp"].items()) + ".", "",
         "| Ridge strength | OOS Brier |", "|---|---|"] + [f"| {k} | {v:.5f} |" for k, v in o["sel"].items()]
    L += ["", "## What it buys", "",
          f"On its top 10% of days an event follows within 30 days {o['top_rate']:.1%} of the time, against a base rate of {o['base']:.1%} ({o['lift']:.2f} times). "
          f"At a 10% false-alarm rate it flags {o['rec10'][0]} of {o['rec10'][1]} events.", "",
          "### Probability bands", "", "| Level | 30-day probability | Share of theatre-days | Event rate that followed | Mean published probability |", "|---|---|---|---|---|"]
    for nm, rng_, share, real, mean, n in o["bands"]:
        L.append(f"| {nm} | {rng_} | {share:.1%} | {real:.1%} | {mean:.1%} |" if n else f"| {nm} | {rng_} | 0% | n/a | n/a |")
    L += ["", "### Reliability of the published probability", "", "| Predicted from | to | Days | Mean predicted | Event rate that followed |", "|---|---|---|---|---|"]
    for a, b, n, p, r in o["rel"]:
        L.append(f"| {a:.0%} | {min(b, 1):.0%} | {n:,} | {p:.1%} | {r:.1%} |")
    L += ["", "### By theatre", "", "| Theatre | Positive days | Brier skill | AUC |", "|---|---|---|---|"]
    for t, n, b_, a_ in o["per"]:
        L.append(f"| {C.THEATRES[t]['name']} | {n} | {'n/a' if b_ != b_ else f'{b_:+.3f}'} | {'n/a' if a_ != a_ else f'{a_:.3f}'} |")
    L += ["", "## Indicator families ranked by noise-to-signal", "",
          "Best threshold per family over all labelled days. NSR is the false-alarm rate divided by the hit rate: below 1 the family fires more often before events than on calm days; 1 or more it is noise. "
          "Families flagged confirming are published late and cannot warn. The model weights below come from the regression, not from this table; this is the plain-language check on them.", "",
          "| Family | Domain | Confirming | Threshold | Hit rate | False-alarm rate | NSR | Events with a signal |", "|---|---|---|---|---|---|---|---|"]
    for r in o["nsr"].itertuples():
        L.append(f"| {r.family} | {r.domain} | {'yes' if r.confirming else 'no'} | {r.threshold} | {r.hit:.1%} | {r.false_alarm:.1%} | {r.nsr:.2f} | {r.events} |")
    if "model" in o:
        m = o["model"]
        L += ["", "## Fitted model", "", f"Fitted {m['fitted']} on data through {m['data_through']}. Family weights (log-odds per full-scale reading, evidence = max(0, z)/5; the live model multiplies the same way):", "",
              "| Family | Weight |", "|---|---|"] + [f"| {k} | {v:.3f} |" for k, v in sorted(m["theta"]["w"].items(), key=lambda kv: -kv[1]) if v > 0.001]
        h = m["theta"]["hist"]
        L += ["", f"Conflict-history terms (log-odds per full-scale term): events in the last year {h[0]:+.2f}, in the last three years {h[1]:+.2f}, log days since the latest event {h[2]:+.2f}. "
              "They are correlated, so read them together: risk is higher where events are recent and frequent, and a theatre is lower in the weeks right after the 30 days left out of the labels.",
              f"Published probabilities are capped at {m['p_cap']:.0%}, the highest the model produced out of sample, rounded up: it is not shown claiming more than it was tested on."]
        L += ["", "Theatre base rates (30-day probability on a quiet day with no history): " + ", ".join(f"{C.THEATRES[t]['name']} {v:.1%}" for t, v in m["base"].items()) + ".",
              f"Shrink toward the base rate gamma = {m['gamma']}, floor phi = {m['phi']}. Chance of an event somewhere within 30 days, climatological: {m['p_any_clim']:.0%}."]
    with open(os.path.join(ROOT, "docs", REPORT), "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote docs/" + REPORT)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "panel":
        zhistory(refresh=True)
    elif cmd in ("report", "fit"):
        run(write=cmd == "fit")
    elif cmd == "fit-armed":     # hidden shadow model: armed-force events only (onset, strike, maritime); never drives the page
        EVENT_TYPES = ("onset", "strike", "maritime")
        MODEL_PATH = os.path.join(DATA, "model_weights_armed.json")
        REPORT = "MODEL_ARMED.md"
        run(write=True)
    else:
        sys.exit(__doc__)
