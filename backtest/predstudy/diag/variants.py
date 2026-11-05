"""Exploratory, two tries, fixed before running: (a) the published model without its three conflict-history terms;
(b) an 'improper' model: theatre offsets plus one non-negative coefficient on the unweighted mean of the 15 families present on
95% of days since 2019. Same rolling origin, embargo, ridge strength (3) and nested shrink as the published model.
Reports the model gate (pooled AUC against 2,000 circular shifts) and within-theatre / within theatre-year AUC with their own nulls.
Run from the repo root."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
V = BB.V
o = BB.load()
P, X, y, lab, eid, fams, pub0, base0 = o["P"], o["X"], o["y"], o["lab"], o["eid"], o["fams"], o["pub"], o["base"]
yr = P["date"].dt.year.values; th = P["theatre"].values; core = np.isin(th, V.TH)
nT = V.n_th(P)
E = P[fams].values.astype(float)
since = core & (yr >= 2019)
full = [i for i, f in enumerate(fams) if np.mean(~np.isnan(E[since, i])) >= 0.95]
comp = np.nan_to_num(np.nanmean(E[:, full], axis=1) / 5.0)
Xa = X.copy(); Xa[:, 1 + nT:1 + nT + 3] = 0.0
Xb = np.hstack([X[:, :1 + nT], np.zeros((len(P), 3)), comp[:, None]])
def strat(p, ok, by_year):
    num = den = 0.0
    for t in V.TH:
        for Y in (sorted(set(yr[ok])) if by_year else [None]):
            m = ok & (th == t) & ((yr == Y) if by_year else True)
            n1 = y[m].sum()
            if n1 == 0 or n1 == m.sum(): continue
            num += n1 * V.auc(y[m], p[m]); den += n1
    return num / den
rng = np.random.default_rng(5)
out = {}
for name, Xv in (("published", None), ("no history terms", Xa), ("improper: offsets + unweighted mean of 15 full-coverage families", Xb)):
    if Xv is None:
        pub, base = pub0, base0
    else:
        raw, base = V.rolling(P, Xv, y, lab, 3)
        pub, _ = V.nested_published(P, raw, base, y, lab)
    ok = lab & ~np.isnan(pub) & (yr >= 2021) & core
    clim = V.brier(y[ok], base[ok]); bss = 1 - V.brier(y[ok], pub[ok]) / clim
    a = V.auc(y[ok], pub[ok])
    lo, hi = V.cluster_boot_auc(y[ok], pub[ok], (P["theatre"] + P["date"].dt.year.astype(str)).values[ok])
    sa, _ = V.shifted_control(P, y, pub, ok, n=2000)
    w, wy = strat(pub, ok, False), strat(pub, ok, True)
    nw, nwy = [], []
    for _ in range(300):
        z = pub.copy()
        for t in V.TH:
            m = np.where((th == t) & ~np.isnan(pub))[0]     # shift within the rows that have a probability, as validate.shifted_control does
            z[m] = np.roll(z[m], rng.integers(180, len(m) - 180))
        nw.append(strat(z, ok, False)); nwy.append(strat(z, ok, True))
    nw, nwy = np.array(nw), np.array(nwy)
    r = {"bss": bss, "auc": a, "auc_lo": float(lo), "gate_shuffle_p": float((sa >= a).mean()), "within": w, "within_p": float((nw >= w).mean()),
         "within_theatre_year": wy, "within_theatre_year_p": float((nwy >= wy).mean())}
    out[name] = r
    print(f"{name:66s} BSS {bss:+.4f} AUC {a:.3f} (lo {lo:.3f}) gate p {r['gate_shuffle_p']:.3f} | within {w:.3f} (p {r['within_p']:.3f}) "
          f"| within theatre-year {wy:.3f} (p {r['within_theatre_year_p']:.3f})", flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "variants.json"), "w"), indent=1)
