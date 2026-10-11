#!/usr/bin/env python3
"""Timing study: can the data WarWatch now holds be transformed, added or used differently in training so that the 30-day model
passes its three release gates, unchanged, on past events? Plan fixed in advance: docs/TIMINGSTUDY_PLAN.md.

    python3 warwatch/timingstudy.py           # every candidate -> docs/TIMINGSTUDY.md, backtest/timingstudy.csv
    python3 warwatch/timingstudy.py --quick   # one ridge strength (lambda 3) and 300 shifts, for checking the code

Reuses validate.py and featurestudy.py for the panel, labels, fit, shrink and gates, so the baseline is the published model, scored
the same way. Nothing here writes model_weights.json, events.csv or MODEL.md. Needs numpy, pandas and scipy.
"""
import datetime as dt
import glob
import csv
import math
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import featurestudy as FS  # noqa: E402
import outsidestudy as O  # noqa: E402
import sourcestudy as SS  # noqa: E402
import sources as S  # noqa: E402
import validate as V  # noqa: E402

ROOT = V.ROOT
BACKFILL = os.path.join(ROOT, "backfill", "data")
OUT_MD = os.path.join(ROOT, "docs", "TIMINGSTUDY.md")
OUT_CSV = os.path.join(ROOT, "backtest", "timingstudy.csv")
TH = V.TH
CANDIDATES = ["D1", "D2", "D3", "T1", "T2", "T3", "L1", "L2", "K1", "K2", "K3", "K4"]
NAMES = {"base": "Baseline (published model)", "D1": "Archive feeds in the fit", "D2": "Newly held series", "D3": "Iraq and GCC rows in training",
         "T1": "Hot-state level (GDELT violence)", "T2": "Acceleration (GDELT, 7 days against 60)", "T3": "Fewer weights (own families + world tempo)",
         "L1": "Weights trained on a 10-day target", "L2": "Weights trained on a dense violence proxy", "K1": "Cleaning: one-day glitches removed",
         "K2": "Cleaning: standing drift removed", "K3": "Cleaning: late data dropped", "K4": "Cleaning: duplicate families merged", "C1": "Combination"}
N_TRIED = len(CANDIDATES) + 1           # the combination counts as a try whether or not it runs
ALPHA = 0.05 / N_TRIED
SHIFTS = 2000
FIGHT = ("18", "19")
ROOTS = {"threat": ("13",), "posture": ("15",), "preforce": ("13", "15"), "fight": FIGHT}
LAM_INDEX = V.LAM_H                     # ridge on the one stage-2 coefficient in L1 and L2 (the history terms' strength)


# ------------------------------------------------------------------ new families: {family: {theatre: pd.Series of evidence 0..5, indexed by the day it is known}}
def _evidence(sid, theatre, kind, pts, avail, direction="up"):
    s = {"id": sid, "theatre": theatre, "domain": "x", "direction": direction, "lag": False, "kind": kind, "all": pts, "avail": avail}
    _, r = V._zjob(s)
    z = pd.Series({pd.Timestamp(k): v for k, v in r["z"].items()}, dtype=float).sort_index()
    return (z if direction == "up" else -z).clip(0, 5)


def fam_D2():
    out = {}
    for fam in ("wiki", "wikiloc"):
        out[fam] = {}
        for t in TH:
            p = os.path.join(BACKFILL, f"{fam}_{t}.csv")
            if os.path.exists(p):
                pts = sorted((d.isoformat(), v) for d, v in FS.L.daily(p).items())
                out[fam][t] = _evidence(f"{fam}_{t}", t, "daily", pts, [(dt.date.fromisoformat(d) + dt.timedelta(1)).toordinal() for d, _ in pts])
    rows = {}
    for p in sorted(glob.glob(os.path.join(BACKFILL, "gdeltwide", "*.csv"))):
        with open(p) as fh:
            for r in csv.DictReader(fh):
                rows.setdefault(r["theatre"], {})[r["day"]] = {k: float(v) for k, v in r.items() if k not in ("day", "theatre")}
    for fam, (num, den, mn, sign, mean) in SS.GW.items():
        out[fam] = {}
        for t in TH:
            pts = []
            for d in sorted(rows.get(t, {})):
                x = rows[t][d]
                n = sum(x[c] for c in num)
                if den is None:
                    pts.append((d, n))
                elif x[den] >= mn:
                    pts.append((d, n / x[den] if mean else 1000.0 * n / x[den]))
            if pts:
                out[fam][t] = _evidence(f"{fam}_{t}", t, "daily", pts, [(dt.date.fromisoformat(d) + dt.timedelta(1)).toordinal() for d, _ in pts],
                                        "up" if sign > 0 else "down")
    srcs = {"cf_armedconf_3": O.cf_points("armedconf_3"), "cf_anyviolence_3": O.cf_points("anyviolence_3"), "views": O.views_points()}
    for fam, per in srcs.items():
        out[fam] = {}
        for t in TH:
            pts = per.get(t, [])
            if pts:          # one vintage a month, public on the day given: scored as the live build scores a monthly series
                out[fam][t] = _evidence(f"{fam}_{t}", t, "monthly", [(d.isoformat()[:7], v) for d, v in pts], [d.toordinal() for d, _ in pts])
    return out


def gdelt(t, roots, share):
    return FS.daily_series(S.gdelt_series(t, roots, share))


def expanding_mad(x, minp):
    med = x.expanding(minp).median()
    mad = x.expanding(minp).apply(lambda a: np.median(np.abs(a[~np.isnan(a)] - np.median(a[~np.isnan(a)]))), raw=True)
    return med, mad


def fam_T1():
    out = {}
    for share in (False, True):
        f = f"level_gdelt{'share' if share else ''}_fight"
        out[f] = {}
        for t in TH:
            x = np.log1p(gdelt(t, FIGHT, share).rolling(30, min_periods=20).mean())
            med, mad = expanding_mad(x.shift(1), 365)
            out[f][t] = FS.mod_z(x, med, mad).clip(lower=0).shift(1)
    return out


def fam_T2():
    out = {}
    for key, roots in ROOTS.items():
        for share in (False, True):
            f = f"accel_gdelt{'share' if share else ''}_{key}"
            out[f] = {}
            for t in TH:
                x = gdelt(t, roots, share)
                m7 = x.rolling(7, min_periods=4).mean()
                med, mad = FS.roll_mad(x.shift(7), 60, 40)
                out[f][t] = FS.mod_z(m7, med, mad).clip(lower=0).shift(1)
    return out


def proxy_L2(P):
    """1 when the theatre's 7-day count of GDELT assault and fight events, at any point in the next 30 days, is above the 90th
    percentile of that count over the year before the day; NaN where either is unknown."""
    out = np.full(len(P), np.nan)
    th, dates = P["theatre"].values, P["date"].values
    for t in TH:
        c7 = gdelt(t, FIGHT, False).rolling(7, min_periods=4).sum()
        thr = c7.shift(1).rolling(365, min_periods=180).quantile(0.9)
        m = np.where(th == t)[0]
        d = pd.DatetimeIndex(dates[m])
        c, q = c7.reindex(d).values, thr.reindex(d).values         # the threshold is fixed on the day of the forecast
        cf = c7.reindex(pd.date_range(d.min(), d.max() + pd.Timedelta(days=30))).values
        y = np.full(len(m), np.nan)
        for i in range(len(m)):
            nxt = cf[i + 1:i + 31]
            if np.isnan(q[i]) or len(nxt) < 30 or np.isnan(nxt).all():
                continue
            y[i] = float(np.nanmax(nxt) > q[i])
        out[m] = y
    return out


FAMS = {"D2": fam_D2, "T1": fam_T1, "T2": fam_T2}


def merge_duplicates(P, fams, cut=0.8):
    """K4: families whose evidence correlates above cut over all theatre-days, averaged in pairs, strongest pair first."""
    R = P[fams].corr(min_periods=200)
    pairs = sorted(((R.iloc[i, j], fams[i], fams[j]) for i in range(len(fams)) for j in range(i + 1, len(fams)) if R.iloc[i, j] > cut), reverse=True)
    used, P = set(), P.copy()
    out = list(fams)
    for _, a, b in pairs:
        if a in used or b in used:
            continue
        used |= {a, b}
        P[f"{a}+{b}"] = P[[a, b]].mean(axis=1, skipna=True)
        out = [f for f in out if f not in (a, b)] + [f"{a}+{b}"]
    print(f"K4 merged {len(used) // 2} pairs: " + ", ".join(f"{a}+{b} ({r:.2f})" for r, a, b in pairs if f"{a}+{b}" in out), flush=True)
    return P, out


# ------------------------------------------------------------------ labels with another horizon (L1)
def labels_h(P, ev, through, horizon):
    saved = V.HORIZON
    V.HORIZON = horizon
    try:
        y, _, unk, _ = V.labels(P, ev, through)
    finally:
        V.HORIZON = saved
    return y, unk


# ------------------------------------------------------------------ the runner
def site_copies(ev):
    s = ev[ev["site_theatre"] != ""].assign(theatre=lambda d: d["site_theatre"], added=False)
    return pd.concat([ev, s], ignore_index=True)


class Study:
    def __init__(self, quick=False):
        self.quick = quick
        t0 = time.time()
        self.through = V.events_through()
        self.ev = FS.read_events(True)
        self.H = V.zhistory()
        self.new = {}
        self.t0 = t0

    def fams_of(self, c):
        if c not in self.new:
            self.new[c] = FAMS[c]()
            print(f"{c}: {', '.join(self.new[c])} built ({time.time() - self.t0:.0f}s)", flush=True)
        return self.new[c]

    def H_for(self, cands):
        if "D1" not in cands:
            return self.H
        if not hasattr(self, "H1"):
            V.USE_BACKFILL = True
            try:
                self.H1 = V.zhistory()
            finally:
                V.USE_BACKFILL = False
        return self.H1

    def setup(self, cands):
        subs = "D3" in cands
        H = self.H_for(cands)
        P, meta = V.panel(H, end=self.through, subs=subs)
        ev = site_copies(self.ev) if subs else self.ev
        core = P["theatre"].isin(TH).values
        fams = [c for c in P.columns if c in meta and P.loc[core, c].notna().sum() > 200]
        for c in cands:
            if c in FAMS:
                add = {k: v for k, v in self.fams_of(c).items() if v}
                P = FS.attach(P, add)
                fams += [f for f in add if P.loc[core, f].notna().sum() > 200]
        if "K3" in cands:
            fams = [f for f in fams if not meta.get(f, ("", False))[1]]
        if "K4" in cands:
            P, fams = merge_duplicates(P, fams)
        if "K1" in cands or "K2" in cands:
            P = P.copy()
            for t in set(P["theatre"]):
                m = P["theatre"].values == t
                E = P.loc[m, fams]
                if "K1" in cands:
                    E = E.where(E.isna(), np.minimum(E, E.shift(1).fillna(0)))
                if "K2" in cands:
                    E = (E - E.shift(1).rolling(365, min_periods=180).median().fillna(0)).clip(lower=0)
                P.loc[m, fams] = E.values
        if "T3" in cands:
            glob_ = {V.family(sid) for sid, s in H.items() if s["theatre"] == "global"}
            g = [f for f in fams if f in glob_]
            P["world_tempo"] = P[g].mean(axis=1, skipna=True)
            fams = [f for f in fams if f not in glob_] + ["world_tempo"]
        y, excl, unk, eid = V.labels(P, ev, self.through)
        lab = ~excl & ~unk
        hist = V.history_features(P, ev)
        X = V.design(P, fams, hist)
        nT = V.n_th(P)
        extra = {}
        if "L1" in cands:
            y10, unk10 = labels_h(P, ev, self.through, 10)
            extra["stage1"] = (y10, ~excl & ~unk10, list(range(len(fams))))
        if "L2" in cands:
            yp = proxy_L2(P)
            keep = [i for i, f in enumerate(fams) if not f.startswith(("gdelt", "level_gdelt", "accel_gdelt", "gw_"))]
            extra["stage1"] = (np.nan_to_num(yp), ~np.isnan(yp), keep)
        return dict(P=P, ev=ev, fams=fams, X=X, y=y, lab=lab, eid=eid, nT=nT, core=core, **extra)

    def rolling(self, S_, lam):
        P, X, y, lab, nT, core = S_["P"], S_["X"], S_["y"], S_["lab"], S_["nT"], S_["core"]
        yr = P["date"].dt.year.values
        dates = P["date"].values
        th = P["theatre"].values
        raw = np.full(len(P), np.nan)
        base = np.full(len(P), np.nan)
        nH = 3
        for Y in V.TEST_YEARS:
            cut = np.datetime64(f"{Y}-01-01") - np.timedelta64(V.EMBARGO, "D")
            tr = lab & (dates < cut)
            te = lab & (yr == Y) & core            # only the 13 theatres are scored
            if "stage1" in S_:
                y1, lab1, keep = S_["stage1"]
                # stage 1: family weights on the stage-1 target, training days whose stage-1 label is known before the cut
                tr1 = lab1 & (dates < cut - np.timedelta64(30, "D")) & core
                cols = list(range(1 + nT + nH)) + [1 + nT + nH + i for i in keep]
                th1 = V.fit(X[tr1][:, cols], y1[tr1], lam, nT=nT)
                w = th1[1 + nT + nH:]
                idx = X[:, [1 + nT + nH + i for i in keep]] @ w
                X2 = np.c_[X[:, :1 + nT + nH], idx]
                th2 = V.fit(X2[tr & core], y[tr & core], LAM_INDEX, nT=nT)
                raw[te] = V.sigmoid(X2[te] @ th2)
            else:
                trm = tr if nT > len(TH) else tr & core     # D3: the sub-theatres' rows train the shared weights too
                theta = V.fit(X[trm], y[trm], lam, nT=nT)
                raw[te] = V.sigmoid(X[te] @ theta)
            b, _ = V.base_rates(P, y, tr)
            base[te] = np.array([b[t] for t in th[te]])
        return raw, base

    def run(self, cands):
        t0 = time.time()
        S_ = self.setup(cands)
        P, y, lab, eid, ev = S_["P"], S_["y"], S_["lab"], S_["eid"], S_["ev"]
        yr = P["date"].dt.year.values
        best = None
        for lam in ([3] if self.quick else list(V.LAMBDAS)):
            raw, base = self.rolling(S_, lam)
            pub, _ = V.nested_published(P, raw, base, y, lab)
            ok = lab & ~np.isnan(pub) & (yr >= V.TEST_YEARS[0])
            b = V.brier(y[ok], pub[ok])
            if best is None or b < best[0]:
                best = (b, lam, raw, base)
        _, lam, raw, base = best
        r = FS.evaluate(P, ev, y, lab, eid, raw, base, gates=False)
        ok, pub = r["ok"], r["pub"]
        clusters = (P["theatre"] + P["date"].dt.year.astype(str)).values[ok]
        lo, hi = V.cluster_boot_auc(y[ok], pub[ok], clusters)
        sa, _ = V.shifted_control(P, y, pub, ok, n=300 if self.quick else SHIFTS)
        r.update(auc_lo=float(lo), auc_hi=float(hi), shuffle_p=float((sa >= r["auc"]).mean()), shuf95=float(np.percentile(sa, 95)),
                 lam=lam, nfam=len(S_["fams"]), P=P, y=y, lab=lab, eid=eid, ev=ev)
        r["gates"] = bool(r["bss"] > 0 and lo > 0.5 and r["shuffle_p"] < 0.05)
        r["validated"] = bool(r["bss"] > 0 and lo > 0.5 and r["shuffle_p"] < ALPHA)
        r["lists"] = by_list(P, ev, y, pub, ok, eid)
        r["years"] = {Y: V.auc(y[ok & (yr == Y)], pub[ok & (yr == Y)]) for Y in V.TEST_YEARS}
        print(f"{'+'.join(cands) or 'base':8s} bss {r['bss']:+.4f} auc {r['auc']:.3f} ({lo:.3f}) within {r['wauc']:.3f} shuffle p {r['shuffle_p']:.4f} "
              f"(95th {r['shuf95']:.3f}) flagged {r['flagged']}/{r['events']} lam {lam} fams {r['nfam']} ({time.time() - t0:.0f}s)", flush=True)
        return r


def by_list(P, ev, y, pub, ok, eid):
    """AUC on the 78 original and on the 83 added events: positive days of that list's events against every calm day."""
    out = {}
    for name, want in (("original", False), ("added", True)):
        ids = set(ev.index[ev["added"] == want])
        pos = ok & (y == 1) & np.isin(eid, list(ids))
        m = pos | (ok & (y == 0))
        out[name] = V.auc(pos[m].astype(int), pub[m]) if pos.any() else float("nan")
    return out


# ------------------------------------------------------------------ report
def aligned(r, rb, k):
    """r[k] on the baseline's rows (a candidate with sub-theatre rows has a longer panel)."""
    key = lambda x: pd.MultiIndex.from_arrays([x["P"]["theatre"].values, x["P"]["date"].values])
    return pd.Series(r[k], index=key(r)).reindex(key(rb)).values


def row(c, r, rb):
    if c == "base":
        p, d = float("nan"), 0.0
    else:
        okc, pc = aligned(r, rb, "ok"), aligned(r, rb, "pub")
        p, d = FS.paired_boot(rb["P"], rb["y"], rb["ok"] & (okc == True), rb["pub"], pc)  # noqa: E712
    return dict(candidate=c, name=NAMES.get(c, c), families=r["nfam"], lam=r["lam"], bss=r["bss"], auc=r["auc"], auc_lo=r["auc_lo"], auc_hi=r["auc_hi"],
                within_auc=r["wauc"], shuffle_p=r["shuffle_p"], shuffle_95=r["shuf95"], flagged=r["flagged"], events=r["events"],
                false_per_hit=r["false_per_hit"], auc_original=r["lists"]["original"], auc_added=r["lists"]["added"],
                brier_gain_vs_base=d, brier_p_vs_base=p, gates_at_005=r["gates"], validated=r["validated"],
                auc_by_year=";".join(f"{a:.2f}" for a in r["years"].values()))


def fmt(x, f="{:.3f}"):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f.format(x)


def write_report(df, combo):
    b = df[df.candidate == "base"].iloc[0]
    val = df[(df.candidate != "base") & df.validated]
    prom = df[(df.candidate != "base") & df.gates_at_005 & ~df.validated]
    L = ["# Timing study: can the 30-day chance be validated on past events?", "",
         f"Written by `warwatch/timingstudy.py` to the plan fixed before any candidate was run ([TIMINGSTUDY_PLAN.md](TIMINGSTUDY_PLAN.md)). "
         f"161 events, the 13 theatres, test years {V.TEST_YEARS[0]} to {V.TEST_YEARS[-1]}, each fitted on earlier years only. The three gates are unchanged; "
         f"with {N_TRIED} tries a candidate counts as validated only when its shuffled-timing p is below 0.05 / {N_TRIED} = {ALPHA:.4f} ({SHIFTS:,} shifts).", "",
         "## Result", ""]
    if len(val):
        L.append("**Validated:** " + ", ".join(f"{r.candidate} ({r['name']})" for _, r in val.iterrows()) + ".")
    else:
        L.append("**No candidate is validated.**" + (" Promising at the uncorrected 0.05 line, not proven: " + ", ".join(f"{r.candidate} ({r['name']}, p {r.shuffle_p:.3f})" for _, r in prom.iterrows()) + "."
                                                  if len(prom) else " None passes even at the uncorrected 0.05 line."))
    L += ["", "| Id | Change | Families | Brier skill | AUC (95% interval) | Within-theatre AUC | Shuffle p (95th pct of shifted AUC) | Events flagged at 10% | False alarms per hit | AUC, original / added events | Brier vs baseline (p) | Validated |",
          "|---|---|---:|---:|---|---:|---|---:|---:|---|---|---|"]
    for _, r in df.iterrows():
        vs = "–" if r.candidate == "base" else f"{r.brier_gain_vs_base * 1e4:+.1f}e-4 ({r.brier_p_vs_base:.2f})"
        verdict = "yes" if r.validated else ("at 0.05 only" if r.gates_at_005 else "no")
        L.append(f"| {r.candidate} | {r['name']} | {r.families} | {r.bss:+.4f} | {r.auc:.3f} ({r.auc_lo:.3f} to {r.auc_hi:.3f}) | {r.within_auc:.3f} | "
                 f"{r.shuffle_p:.4f} ({r.shuffle_95:.3f}) | {r.flagged}/{r.events} | {r.false_per_hit:.1f} | {fmt(r.auc_original, '{:.2f}')} / {fmt(r.auc_added, '{:.2f}')} | {vs} | {verdict if r.candidate != 'base' else ('passes' if r.gates_at_005 else 'fails')} |")
    L += ["", "AUC by test year, 2021 to 2026:", "", "| Id | " + " | ".join(str(y) for y in V.TEST_YEARS) + " |", "|---|" + "---:|" * len(V.TEST_YEARS)]
    for _, r in df.iterrows():
        L.append(f"| {r.candidate} | " + " | ".join(r.auc_by_year.split(";")) + " |")
    L += ["", f"Combination (C1): {'run with ' + ', '.join(combo) if combo else 'not run, since no candidate passed the gates at the uncorrected 0.05 line'}.", "",
          f"Baseline for reference: within-theatre AUC {b.within_auc:.3f}. The plan's check puts the pass line at a within-theatre AUC of about 0.58 to 0.63."]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote", OUT_MD)


def main():
    quick = "--quick" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    st = Study(quick)
    res = {"base": st.run([])}
    for c in (only or CANDIDATES):
        res[c] = st.run([c])
    combo = [c for c in CANDIDATES if c in res and res[c]["gates"]]
    if combo and not only:
        if any(c in ("L1", "L2") for c in combo) and len(combo) > 1:
            combo = [c for c in combo if c not in ("L1", "L2")] + [max((c for c in combo if c in ("L1", "L2")), key=lambda k: res[k]["auc"])]
        res["C1"] = st.run(combo)
    rb = res["base"]
    df = pd.DataFrame([row(c, r, rb) for c, r in res.items()])
    if not only:
        df.to_csv(OUT_CSV, index=False)
        write_report(df, combo if "C1" in res else [])
    else:
        print(df.drop(columns=["name"]).to_string())


if __name__ == "__main__":
    main()
