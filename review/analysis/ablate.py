import sys, numpy as np, pandas as pd, panel, pickle
exec(open('rolling.py').read().split("sets = {")[0])
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
X0 = np.hstack([TH1, np.c_[hist1, hist3, since, ucdp]])
def fit(cols):
    X = np.hstack([X0, Z[:, cols], M[:, cols]]) if len(cols) else X0
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9); p = np.full(len(P), np.nan)
    for Y in range(2021, 2027):
        tr = use & (yr < Y); te = use & (yr == Y)
        p[te] = LogisticRegression(C=0.002, max_iter=3000).fit(Xs[tr], y[tr]).predict_proba(Xs[te])[:, 1]
    return p
ok = use & (yr >= 2021)
def rec(p, fpr=.1):
    cut = np.quantile(p[ok & (y == 0)], 1 - fpr); evs = sorted(set(eid[ok & (y == 1)]))
    return [e for e in evs if ((eid == e) & ok & (p >= cut)).any()]
base = fit(list(range(len(fams))))
doms = sorted(set(meta[f][0] for f in fams))
newsrc = ('gdelt', 'gpsjam', 'ooni', 'gpr', 'ucdp')
groups = {f'drop {d}': [k for k, f in enumerate(fams) if meta[f][0] != d] for d in doms}
groups['drop new back-filled feeds (GDELT, GPSJam, OONI, GPR, UCDP)'] = [k for k, f in enumerate(fams) if not f.startswith(newsrc)]
groups['only GDELT'] = [k for k, f in enumerate(fams) if f.startswith('gdelt')]
groups['only financial'] = [k for k, f in enumerate(fams) if meta[f][0] == 'financial']
rows = [dict(model='all', auc=round(roc_auc_score(y[ok], base[ok]), 3), aupr=round(average_precision_score(y[ok], base[ok]), 3), rec10=len(rec(base)))]
for n, cols in groups.items():
    p = fit(cols); rows.append(dict(model=n, auc=round(roc_auc_score(y[ok], p[ok]), 3), aupr=round(average_precision_score(y[ok], p[ok]), 3), rec10=len(rec(p))))
print(pd.DataFrame(rows).to_string(index=False))
hit = set(rec(base)); evs = sorted(set(eid[ok & (y == 1)]))
evl = ev.copy(); evl['key'] = list(zip(evl.theatre, pd.to_datetime(evl.date)))
tab = []
for e in evs:
    t, d = evlist[e]; r = evl[(evl.theatre == t) & (pd.to_datetime(evl.date) == d)].iloc[0]
    tab.append(dict(theatre=t, date=d.date(), kind=r.surprise_or_buildup, type=r.type, hit=e in hit, desc=r.description[:50]))
T = pd.DataFrame(tab); print(T.groupby('kind').hit.agg(['sum', 'count'])); print(T.groupby('theatre').hit.agg(['sum', 'count']))
T.to_csv('out/event_hits.csv', index=False); np.save('out/p_best.npy', base)
