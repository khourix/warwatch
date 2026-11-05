"""Exploratory: does an unfitted equal-weight composite of the input families time events better than the fitted model?
Two timing metrics, 2021 on: within-theatre AUC, and within theatre-year AUC (strata = theatre x calendar year, which removes
slow co-movement such as a series and the event rate both rising over several years). Null: each theatre's series circularly
shifted by >= 180 days, 500 draws. Run from the repo root."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
V = BB.V
o = BB.load()
P, y, lab, eid, fams, pub, pubh = o["P"], o["y"], o["lab"], o["eid"], o["fams"], o["pub"], o["pubh"]
yr = P["date"].dt.year.values; th = P["theatre"].values; core = np.isin(th, V.TH)
OK = lab & (yr >= 2021) & core & ~np.isnan(pub)
E = P[fams].values.astype(float)
# families present on at least 95% of core rows from 2019: a fixed set, so coverage growth can't drive the composite
since = core & (yr >= 2019)
full = [i for i, f in enumerate(fams) if np.mean(~np.isnan(E[since, i])) >= 0.95]
Ef = E[:, full]
def strat_auc(x, by_year):
    ok = OK & ~np.isnan(x)
    num = den = 0.0
    for t in V.TH:
        for Y in (sorted(set(yr[ok])) if by_year else [None]):
            m = ok & (th == t) & ((yr == Y) if by_year else True)
            n1 = y[m].sum()
            if n1 == 0 or n1 == m.sum(): continue
            num += n1 * V.auc(y[m], x[m]); den += n1
    return num / den
cands = {"published model": pub, "history terms only": pubh,
         "equal-weight mean, all families": np.nanmean(E, axis=1),
         "equal-weight mean, fixed full-coverage set": np.nanmean(Ef, axis=1),
         "share elevated (>0), fixed full-coverage set": np.mean(Ef > 0, axis=1),
         "share elevated (>0), among families available": np.nansum(E > 0, axis=1) / np.sum(~np.isnan(E), axis=1)}
print("fixed full-coverage families:", len(full), "of", len(fams))
rng = np.random.default_rng(11)
out = {}
for k, x in cands.items():
    obs = (strat_auc(x, False), strat_auc(x, True))
    null = []
    for _ in range(300):
        z = x.copy()
        for t in V.TH:
            m = np.where(th == t)[0]
            if len(m) < 400: continue
            z[m] = np.roll(z[m], rng.integers(180, len(m) - 180))
        null.append((strat_auc(z, False), strat_auc(z, True)))
    null = np.array(null)
    out[k] = {"within_theatre": obs[0], "within_theatre_year": obs[1], "null_mean": null.mean(0).tolist(), "null_sd": null.std(0).tolist(),
              "p": [float((null[:, 0] >= obs[0]).mean()), float((null[:, 1] >= obs[1]).mean())]}
    print(f"{k:48s} within theatre {obs[0]:.3f} (null {null[:,0].mean():.3f} +- {null[:,0].std():.3f}, p {out[k]['p'][0]:.3f})   "
          f"within theatre-year {obs[1]:.3f} (null {null[:,1].mean():.3f} +- {null[:,1].std():.3f}, p {out[k]['p'][1]:.3f})", flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "equalweight.json"), "w"), indent=1)
