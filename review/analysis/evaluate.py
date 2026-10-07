import sys, math, json, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import engine as E
import panel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

W = E.load_weights()['weights']
DOMS = ['logistics', 'financial', 'behavioral', 'geospatial', 'information']

def v7(P, meta, onesided=False, orness=None, mean_only=False, lagk=E.LAG_K):
    fams = [c for c in P.columns if c in meta]
    X = P[fams].values
    out = np.full(len(P), np.nan)
    dom_of = [meta[f][0] for f in fams]; lag_of = [meta[f][1] for f in fams]
    old = E.ORNESS
    if orness is not None: E.ORNESS = orness
    owa_cache = {}
    def owa(n):
        if n not in owa_cache: owa_cache[n] = E.owa_weights(n, E.ORNESS)
        return owa_cache[n]
    for i in range(len(P)):
        t = P['theatre'].iat[i]; wt = W[t]
        vals, ws = [], []
        for d in DOMS:
            zs = [X[i, j] * (lagk if lag_of[j] else 1) for j in range(len(fams)) if dom_of[j] == d and not np.isnan(X[i, j])]
            if onesided: zs = [max(0.0, z) for z in zs]
            if not zs: continue
            zs = sorted(zs, reverse=True)[:E.TOPK]
            w = owa(len(zs)); sc = sum(a * b for a, b in zip(w, zs))
            if len(zs) == 1: sc *= E.LONE
            vals.append(sc); ws.append(wt[d])
        if len(vals) < 2: continue
        if mean_only:
            out[i] = sum(a * b for a, b in zip(vals, ws)) / sum(ws)
        else:
            out[i] = (E.mpi(vals, ws)[2] - 100) / 10
    E.ORNESS = old
    return out

def design(P, meta, clip=(0, 5)):
    fams = [c for c in P.columns if c in meta]
    X = P[fams].clip(*clip).fillna(0).values
    M = P[fams].notna().values.astype(float)
    return np.hstack([X, M]), fams

def loto_logit(P, meta, y, use, C=0.1, fams_keep=None):
    Xall, fams = design(P, meta)
    if fams_keep is not None:
        idx = [k for k, f in enumerate(fams) if f in fams_keep]
        idx = idx + [len(fams) + k for k in idx]
        Xall = Xall[:, idx]
    p = np.full(len(P), np.nan)
    th = P['theatre'].values
    for t in panel.TH:
        tr = use & (th != t); te = use & (th == t)
        if y[tr].sum() == 0 or te.sum() == 0: continue
        m = LogisticRegression(C=C, max_iter=2000)
        m.fit(Xall[tr], y[tr])
        p[te] = m.predict_proba(Xall[te])[:, 1]
    return p

def klr_nb(P, meta, y, use, thr_grid=(1.0, 1.5, 2.0, 2.5, 3.0), alpha=1.0):
    """KLR signals per family with LOTO CV: per family choose the threshold minimising NSR on training theatres,
    log-LR of signal / no-signal (Laplace smoothed); naive-Bayes sum."""
    fams = [c for c in P.columns if c in meta]
    X = P[fams].values; th = P['theatre'].values
    score = np.full(len(P), np.nan)
    for t in panel.TH:
        tr = use & (th != t); te = use & (th == t)
        if te.sum() == 0: continue
        s = np.zeros(te.sum())
        for j in range(len(fams)):
            x = X[tr, j]; ok = ~np.isnan(x)
            if ok.sum() < 200 or y[tr][ok].sum() < 20: continue
            yy = y[tr][ok]; xx = x[ok]
            best = None
            for c in thr_grid:
                sig = xx >= c
                A = (sig & (yy == 1)).sum(); B = (sig & (yy == 0)).sum(); Cn = (~sig & (yy == 1)).sum(); D = (~sig & (yy == 0)).sum()
                hit = (A + alpha) / (A + Cn + 2 * alpha); fa = (B + alpha) / (B + D + 2 * alpha)
                nsr = fa / hit
                if best is None or nsr < best[0]: best = (nsr, c, hit, fa)
            nsr, c, hit, fa = best
            if nsr >= 1: continue          # family carries no signal on training data
            xt = X[te, j]
            l1, l0 = math.log(hit / fa), math.log((1 - hit) / (1 - fa))
            s += np.where(np.isnan(xt), 0, np.where(xt >= c, l1, l0))
        score[te] = s
    return score

def metrics(name, s, y, use, eid, lead, P):
    ok = use & ~np.isnan(s)
    out = {'method': name, 'n_days': int(ok.sum()), 'pos_days': int(y[ok].sum())}
    out['auc'] = round(roc_auc_score(y[ok], s[ok]), 3)
    out['aupr'] = round(average_precision_score(y[ok], s[ok]), 3)
    out['base'] = round(y[ok].mean(), 3)
    neg = s[ok & (y == 0)]
    for fpr in (0.10, 0.05):
        cut = np.quantile(neg, 1 - fpr)
        hits, leads = 0, []
        evs = sorted(set(eid[ok & (y == 1)]))
        for e in evs:
            m = ok & (eid == e)
            above = m & (s >= cut)
            if above.any():
                hits += 1; leads.append(np.nanmax(lead[above]))
        out[f'events_hit@{int(fpr*100)}%FPR'] = f"{hits}/{len(evs)}"
        out[f'median_lead@{int(fpr*100)}%'] = float(np.median(leads)) if leads else None
    return out
