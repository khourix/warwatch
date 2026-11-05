"""How often would the forward gates (BSS vs base > 0 and theatre-month bootstrap AUC lower end > 0.5, read at 90 days) pass
for (a) the published model, (b) the same probabilities with their timing destroyed (circular shift within theatre), (c) history-only?
Replayed on the 2021-2026 out-of-sample record, windows of W matured days."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
V = BB.V
o = BB.load()
P, y, lab, pub, base, pubh = o["P"], o["y"], o["lab"], o["pub"], o["base"], o["pubh"]
yr = P["date"].dt.year.values
th = P["theatre"].values
ok = lab & ~np.isnan(pub) & (yr >= 2021)
dates = P["date"].values.astype("datetime64[D]")
month = P["date"].dt.strftime("%Y-%m").values
rng = np.random.default_rng(7)

def shifted(p):
    q = p.copy()
    for t in V.TH:
        r = np.where((th == t) & ~np.isnan(p))[0]
        q[r] = np.roll(p[r], rng.integers(60, len(r) - 60))
    return q

def gate(sel, p, B=300):
    yy, pp, bb = y[sel], p[sel], base[sel]
    if yy.sum() == 0 or yy.sum() == len(yy): return None
    bss = 1 - np.sum((pp - yy) ** 2) / np.sum((bb - yy) ** 2)
    keys = np.array([f"{a}|{b}" for a, b in zip(th[sel], month[sel])])
    uk, inv = np.unique(keys, return_inverse=True)
    idx = [np.where(inv == k)[0] for k in range(len(uk))]
    boots = []
    for _ in range(B):
        pick = rng.integers(0, len(uk), len(uk))
        ii = np.concatenate([idx[k] for k in pick])
        a = V.auc(yy[ii], pp[ii])
        if a == a: boots.append(a)
    lo = np.percentile(boots, 2.5)
    return bss > 0, lo > 0.5, V.auc(yy, pp)

starts = np.arange(np.datetime64("2021-01-01"), np.datetime64("2026-06-01"), np.timedelta64(45, "D"))
for W in (90, 180, 365):
    res = {"published": [], "timing destroyed": [], "history only": []}
    for s in starts:
        sel = ok & (dates >= s) & (dates < s + np.timedelta64(W, "D"))
        if sel.sum() < 0.8 * W * 13: continue
        for nm, p in (("published", pub), ("timing destroyed", shifted(pub)), ("history only", pubh)):
            g = gate(sel, p)
            if g: res[nm].append(g)
    for nm, r in res.items():
        r = np.array(r, dtype=float)
        print(f"W={W:3d} {nm:17s} windows {len(r):3d}  pass both {np.mean(r[:,0]*r[:,1]):.2f}  BSS>0 {r[:,0].mean():.2f}  AUC-lo>0.5 {r[:,1].mean():.2f}  median AUC {np.median(r[:,2]):.3f}")
