"""Compact models: (1) penalty sweep; (2) two-stage KLR evidence score -> calibrated logistic with theatre intercepts (rolling origin)."""
import sys, math, numpy as np, pandas as pd, panel
exec(open('rolling.py').read().split("sets = {")[0])
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
X0 = np.hstack([TH1, np.c_[hist1, hist3, since, ucdp]])
def recall(s, ok, fpr):
    neg = s[ok & (y == 0)]; cut = np.quantile(neg, 1 - fpr)
    evs = sorted(set(eid[ok & (y == 1)])); return f"{sum(((eid == e) & ok & (s >= cut)).any() for e in evs)}/{len(evs)}"
def klr_score(tr, rows, fam_idx):
    s = np.zeros(rows.sum())
    for j in fam_idx:
        x = P[fams[j]].values; okj = tr & ~np.isnan(x)
        if okj.sum() < 200 or y[okj].sum() < 20: continue
        best = None
        for c in (1.0, 1.5, 2.0, 2.5, 3.0):
            sig = x[okj] >= c; yy = y[okj]
            hit = ((sig & (yy == 1)).sum() + 1) / ((yy == 1).sum() + 2); fa = ((sig & (yy == 0)).sum() + 1) / ((yy == 0).sum() + 2)
            if best is None or fa / hit < best[0]: best = (fa / hit, c, hit, fa)
        nsr, c, hit, fa = best
        if nsr >= 0.8: continue
        xt = x[rows]; s += np.where(np.isnan(xt), 0, np.where(xt >= c, math.log(hit / fa), math.log((1 - hit) / (1 - fa))))
    return s
res = {}
for C in (0.002, 0.01, 0.05):
    X = np.hstack([X0, Z, M]); Xs = (X - X.mean(0)) / (X.std(0) + 1e-9); p = np.full(len(P), np.nan)
    for Y in range(2021, 2027):
        tr = use & (yr < Y); te = use & (yr == Y)
        p[te] = LogisticRegression(C=C, max_iter=3000).fit(Xs[tr], y[tr]).predict_proba(Xs[te])[:, 1]
    res[f'logit all features C={C}'] = p
for label, idx in (('all', range(len(fams))), ('leading', lead_f)):
    p = np.full(len(P), np.nan)
    for Y in range(2021, 2027):
        tr = use & (yr < Y); te = use & (yr == Y); allr = use & (yr <= Y)
        k = klr_score(tr, allr, idx)                      # thresholds learned on train years only
        kv = np.full(len(P), np.nan); kv[allr] = k
        F = np.c_[X0, kv]; F = (F - F[tr].mean(0)) / (F[tr].std(0) + 1e-9)
        p[te] = LogisticRegression(C=1.0, max_iter=3000).fit(F[tr], y[tr]).predict_proba(F[te])[:, 1]
    res[f'two-stage KLR ({label}) + history, calibrated'] = p
ok = use & (yr >= 2021)
clim_p = np.full(len(P), np.nan)
for Y in range(2021, 2027):
    tr = use & (yr < Y); te = use & (yr == Y)
    clim_p[te] = LogisticRegression(C=1, max_iter=2000).fit(TH1[tr], y[tr]).predict_proba(TH1[te])[:, 1]
clim = brier_score_loss(y[ok], clim_p[ok]); rows = []
for n, p in res.items():
    b = brier_score_loss(y[ok], p[ok])
    rows.append(dict(model=n, brier=round(b, 4), BSS=round(1 - b / clim, 3), auc=round(roc_auc_score(y[ok], p[ok]), 3), aupr=round(average_precision_score(y[ok], p[ok]), 3), rec10=recall(p, ok, .1), rec5=recall(p, ok, .05)))
    np.save(f"out/p_{n.split()[0]}_{n.split('(')[-1][:3] if '(' in n else C}.npy", p)
print(pd.DataFrame(rows).to_string(index=False))
import pickle; pickle.dump(res, open('out/rolling2.pkl', 'wb'))
