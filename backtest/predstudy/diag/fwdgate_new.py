"""Replays the revised forward gates (warwatch/forward_score.gates: Brier skill, AUC lower end, and the shuffled-timing control at
0.05/3) on 365-day windows of the 2021-2026 out-of-sample record, for the published, timing-scrambled and history-only forecasts.
Compare with fwdgate.py (the old gates). Run from the repo root."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "warwatch"))
import forward_score as F
V = BB.V
o = BB.load()
P, y, lab, pub, base, pubh = o["P"], o["y"], o["lab"], o["pub"], o["base"], o["pubh"]
yr = P["date"].dt.year.values; th = P["theatre"].values
ok = lab & ~np.isnan(pub) & (yr >= 2021) & np.isin(th, V.TH)
dates = P["date"].values.astype("datetime64[D]")
ds = P["date"].dt.strftime("%Y-%m-%d").values
rng = np.random.default_rng(7)
def shifted(p):
    q = p.copy()
    for t in V.TH:
        r = np.where((th == t) & ~np.isnan(p))[0]
        q[r] = np.roll(p[r], rng.integers(60, len(r) - 60))
    return q
starts = np.arange(np.datetime64("2021-01-01"), np.datetime64("2025-07-01"), np.timedelta64(45, "D"))
res = {"published": [], "timing scrambled": [], "history only": []}
for s in starts:
    sel = np.where(ok & (dates >= s) & (dates < s + np.timedelta64(365, "D")))[0]
    if len(sel) < 0.8 * 365 * 13: continue
    for nm, p in (("published", pub), ("timing scrambled", shifted(pub)), ("history only", pubh)):
        sc = [(float(p[i]), float(base[i]), bool(y[i]), {"theatre": th[i], "date": ds[i]}) for i in sel]
        g = F.gates(sc, B=200, read_days=300)
        if g["ready"]:
            res[nm].append((g["bss"] > 0 and g["auc_lo"] > 0.5, g["pass"], g["shuffle_p"]))
for nm, r in res.items():
    r = np.array(r, dtype=float)
    print(f"{nm:17s} windows {len(r)}  old gates pass {r[:,0].mean():.2f}  new gates pass {r[:,1].mean():.2f}  median shuffle p {np.median(r[:,2]):.2f}", flush=True)
