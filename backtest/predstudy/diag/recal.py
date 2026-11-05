"""Exploratory (not pre-registered): does rolling recalibration of the published probability improve Brier / log score out of sample?"""
import os, pickle, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import base as BB; V = BB.V
o = BB.load()
P, y, lab, pub, base = o['P'], o['y'].astype(float), o['lab'], o['pub'], o['base']
th = P['theatre'].values; d = P['date'].values.astype('datetime64[D]')
core = np.isin(th, V.TH)
ok = lab & ~np.isnan(pub) & core
L = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
S = lambda z: 1 / (1 + np.exp(-z))
months = pd.period_range('2022-01', str(pd.Timestamp(d[ok].max()).to_period('M')), freq='M')
platt = np.full(len(y), np.nan); offs = np.full(len(y), np.nan); both = np.full(len(y), np.nan)
from scipy.optimize import minimize
def fit_platt(z, yy):
    f = lambda w: -np.mean(yy * (w[0] + w[1] * z) - np.log1p(np.exp(w[0] + w[1] * z))) + 0.5 * 1e-3 * ((w[1] - 1) ** 2 + w[0] ** 2)
    return minimize(f, [0.0, 1.0]).x
for M in months:
    m0 = np.datetime64(M.start_time.date()); m1 = np.datetime64((M + 1).start_time.date())
    cut = m0 - np.timedelta64(31, 'D')
    tr = ok & (d <= cut) & (d > cut - np.timedelta64(730, 'D'))
    te = ok & (d >= m0) & (d < m1)
    if tr.sum() < 500 or te.sum() == 0: continue
    w = fit_platt(L(pub[tr]), y[tr])
    platt[te] = S(w[0] + w[1] * L(pub[te]))
    tr1 = ok & (d <= cut) & (d > cut - np.timedelta64(365, 'D'))
    for t in V.TH:
        a = tr1 & (th == t); b = te & (th == t)
        if not b.any(): continue
        n = a.sum(); mp = pub[a].mean() if n else pub[b].mean()
        alpha = 365.0
        rate = (y[a].sum() + alpha * mp) / (n + alpha)
        c = L(np.array([rate]))[0] - L(np.array([mp]))[0]
        offs[te & (th == t)] = S(L(pub[b]) + c)
        both[te & (th == t)] = S(w[0] + w[1] * L(pub[b]) + c)
ev = ok & ~np.isnan(platt) & ~np.isnan(offs)
def wauc(p):
    num = den = 0.0
    for t in V.TH:
        m = ev & (th == t); n1 = y[m].sum()
        if n1 == 0 or n1 == m.sum(): continue
        num += n1 * V.auc(y[m], p[m]); den += n1
    return num / den
def murphy(p):
    bins = np.clip((p * 20).astype(int), 0, 19); rel = res = 0.0; yb = y[ev].mean()
    for k in range(20):
        m = bins == k
        if m.any(): rel += m.sum() * (p[m].mean() - y[ev][m].mean()) ** 2; res += m.sum() * (y[ev][m].mean() - yb) ** 2
    return rel / len(p), res / len(p)
clim = V.brier(y[ev], base[ev])
print("rows", ev.sum(), "2022-01 on; positives", int(y[ev].sum()))
for name, p in (("base rate", base), ("published", pub), ("rolling Platt", platt), ("theatre offset", offs), ("Platt+offset", both)):
    b = V.brier(y[ev], p[ev]); ls = -np.mean(y[ev] * np.log(np.clip(p[ev], 1e-6, 1)) + (1 - y[ev]) * np.log(np.clip(1 - p[ev], 1e-6, 1)))
    rel, res = murphy(p[ev])
    print(f"{name:15s} brier {b:.5f}  BSS {1 - b / clim:+.4f}  log {ls:.4f}  pooled AUC {V.auc(y[ev], p[ev]):.3f}  within {wauc(p):.3f}  reliability {rel:.5f} resolution {res:.5f}")
