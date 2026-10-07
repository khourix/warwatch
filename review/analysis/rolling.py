"""Rolling-origin (train on years < Y, test on Y) penalised logit with theatre intercepts and conflict-history baseline.
Compares feature sets by Brier skill vs per-theatre climatology, AUC, AUPR and event recall at fixed false-alarm rate."""
import sys, pickle, numpy as np, pandas as pd, panel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
paths = sys.argv[2:]
H = panel.load(paths); P, meta = panel.panel(H)
ev = pd.read_csv(sys.argv[1]); y, excl, lead, eid, evlist = panel.labels(P, ev)
use = ~excl
dates = pd.to_datetime(P['date']); th = P['theatre'].values; yr = dates.dt.year.values
fams = [c for c in P.columns if c in meta]
# conflict history: prior events in theatre (365d, 3y) known at t; UCDP 90d fatalities at 35d lag
evd = {}
for _, e in ev.iterrows(): evd.setdefault(e['theatre'], []).append(pd.Timestamp(e['date']))
hist1 = np.zeros(len(P)); hist3 = np.zeros(len(P)); since = np.zeros(len(P))
for i, (t, d) in enumerate(zip(th, dates)):
    ds = [x for x in evd.get(t, []) if x < d]
    hist1[i] = sum((d - x).days <= 365 for x in ds); hist3[i] = sum((d - x).days <= 1095 for x in ds)
    since[i] = np.log1p(min((d - max(ds)).days, 3650)) if ds else np.log1p(3650)
S = pickle.load(open('newseries.pkl', 'rb'))
ucdp = np.zeros(len(P))
for t in panel.TH:
    s = S.get(f'ucdp_{t}')
    if not s: continue
    ser = pd.Series({pd.Timestamp(k): v for k, v in s['points']}).asfreq('D').fillna(0)
    lvl = np.log1p(ser.rolling(90, min_periods=1).sum()).shift(35)
    m = th == t
    ucdp[m] = lvl.reindex(dates[m]).fillna(0).values
TH1 = np.array([[t == x for x in panel.TH] for t in th], float)
Z = P[fams].clip(0, 5).fillna(0).values; M = P[fams].notna().values.astype(float)
lead_f = [k for k, f in enumerate(fams) if not meta[f][1]]
sets = {
    'A theatre climatology': TH1,
    'B + conflict history': np.hstack([TH1, np.c_[hist1, hist3, since, ucdp]]),
    'C + all indicators': np.hstack([TH1, np.c_[hist1, hist3, since, ucdp], Z, M]),
    'D + leading indicators only': np.hstack([TH1, np.c_[hist1, hist3, since, ucdp], Z[:, lead_f], M[:, lead_f]]),
    'E indicators, no history': np.hstack([TH1, Z, M]),
}
def recall(s, ok, fpr):
    neg = s[ok & (y == 0)]; cut = np.quantile(neg, 1 - fpr)
    evs = sorted(set(eid[ok & (y == 1)])); hits = sum(((eid == e) & ok & (s >= cut)).any() for e in evs)
    return f'{hits}/{len(evs)}'
out = {}
for name, X in sets.items():
    mu = X.mean(0); sd = X.std(0) + 1e-9; Xs = (X - mu) / sd
    p = np.full(len(P), np.nan)
    for Y in range(2021, 2027):
        tr = use & (yr < Y); te = use & (yr == Y)
        m = LogisticRegression(C=0.05, max_iter=3000).fit(Xs[tr], y[tr]); p[te] = m.predict_proba(Xs[te])[:, 1]
    out[name] = p
ok = use & ~np.isnan(out['A theatre climatology'])
clim = brier_score_loss(y[ok], out['A theatre climatology'][ok])
pooled = brier_score_loss(y[ok], np.full(ok.sum(), y[use & (yr < 2021)].mean()))
print(f'test years 2021-2026, n={ok.sum()} theatre-days, positives={y[ok].sum()}, events={len(set(eid[ok & (y==1)]))}; pooled-climatology Brier {pooled:.4f}')
rows = []
for name, p in out.items():
    b = brier_score_loss(y[ok], p[ok])
    rows.append(dict(model=name, brier=round(b, 4), BSS_vs_theatre_clim=round(1 - b / clim, 3), auc=round(roc_auc_score(y[ok], p[ok]), 3),
                     aupr=round(average_precision_score(y[ok], p[ok]), 3), rec10=recall(p, ok, .10), rec5=recall(p, ok, .05)))
print(pd.DataFrame(rows).to_string(index=False))
np.save('out/rolling_probs.npy', np.vstack(list(out.values()))); pickle.dump((P[['date', 'theatre']], y, use, eid), open('out/rolling_meta.pkl', 'wb'))
