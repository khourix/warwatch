"""Baseline OOS predictions for the prediction study, cached."""
import os, sys, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "warwatch"))
import validate as V
import featurestudy as FS
SCR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(SCR, exist_ok=True)

def load(refresh=False):
    path = os.path.join(SCR, "base.pkl")
    if os.path.exists(path) and not refresh:
        return pickle.load(open(path, "rb"))
    t0 = time.time()
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare(subs=False)
    lam = 3
    raw, base = V.rolling(P, X, y, lab, lam)
    pub, gp = V.nested_published(P, raw, base, y, lab)
    # history-only model: same design without families
    nT = V.n_th(P)
    Xh = X[:, :1 + nT + 3]
    rawh, _ = V.rolling(P, Xh, y, lab, lam)
    pubh, _ = V.nested_published(P, rawh, base, y, lab)
    out = dict(P=P, meta=meta, fams=fams, X=X, y=y, lab=lab, eid=eid, ev=ev, through=through, raw=raw, base=base, pub=pub, gp=gp, rawh=rawh, pubh=pubh)
    pickle.dump(out, open(path, "wb"))
    print(f"baseline in {time.time()-t0:.0f}s")
    return out

if __name__ == "__main__":
    o = load(refresh=True)
    P, y, lab, pub, base = o["P"], o["y"], o["lab"], o["pub"], o["base"]
    yr = P["date"].dt.year.values
    ok = lab & ~np.isnan(pub) & (yr >= 2021)
    th = P["theatre"].values
    print("n", ok.sum(), "pos", y[ok].sum(), "events", len(set(o["eid"][ok & (y == 1)])))
    print("AUC pub", V.auc(y[ok], pub[ok]), "within", FS.within_auc(y[ok], pub[ok], th[ok]))
    print("AUC hist", V.auc(y[ok], o["pubh"][ok]), "within", FS.within_auc(y[ok], o["pubh"][ok], th[ok]))
    print("AUC base", V.auc(y[ok], base[ok]))
    clim = V.brier(y[ok], base[ok])
    print("BSS pub", 1 - V.brier(y[ok], pub[ok]) / clim, "BSS hist", 1 - V.brier(y[ok], o["pubh"][ok]) / clim)
