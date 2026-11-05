import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
V, FS = BB.V, BB.FS
o = BB.load()
P, y, lab, pub, base, eid, ev = o["P"], o["y"], o["lab"], o["pub"], o["base"], o["eid"], o["ev"]
pubh = o["pubh"]
yr = P["date"].dt.year.values
th = P["theatre"].values
ok = lab & ~np.isnan(pub) & (yr >= 2021)
dates = P["date"].values

# days until next event in same theatre (for positives)
lead = np.full(len(P), np.nan)
for t in V.TH:
    m = np.where(th == t)[0]
    ed = np.sort(ev.loc[ev["theatre"] == t, "date"].values)
    if not len(ed): continue
    d = dates[m]
    idx = np.searchsorted(ed, d, side="right")
    nxt = np.where(idx < len(ed), ed[np.minimum(idx, len(ed)-1)], np.datetime64("NaT"))
    lead[m] = (nxt - d) / np.timedelta64(1, "D")

def wauc_subset(score, posmask):
    """within-theatre AUC using positives in posmask and all negatives (ok & y==0)"""
    num = den = 0.0
    for t in np.unique(th[ok]):
        mt = ok & (th == t)
        pos = mt & posmask & (y == 1)
        neg = mt & (y == 0)
        if pos.sum() == 0 or neg.sum() == 0: continue
        yy = np.r_[np.ones(pos.sum()), np.zeros(neg.sum())]
        ss = np.r_[score[pos], score[neg]]
        num += pos.sum() * V.auc(yy, ss); den += pos.sum()
    return num / den if den else np.nan

print("== within-theatre AUC by lead (days until the event)")
for a, b in [(1, 3), (4, 7), (8, 14), (15, 21), (22, 30)]:
    pm = (lead >= a) & (lead <= b)
    print(f"lead {a:>2}-{b:<2}: full {wauc_subset(pub, pm):.3f}  history-only {wauc_subset(pubh, pm):.3f}  n_pos {(ok & pm & (y==1)).sum()}")

# hot/cold state: any event in theatre in the prior 365 days (excluding the last 30, already excluded)
hist = V.history_features(P, ev[~ev.get("dup", pd.Series(False, index=ev.index))] if "dup" in ev else ev)
h1 = hist[:, 0] * 3
hot = h1 > 0
print("== hot (event in prior year) vs cold")
for nm, msk in (("hot", hot), ("cold", ~hot)):
    m = ok & msk
    print(f"{nm}: days {m.sum()}, pos {y[m].sum()}, events {len(set(eid[m & (y==1)]))}, AUC pooled {V.auc(y[m], pub[m]):.3f}, within {FS.within_auc(y[m], pub[m], th[m]):.3f}, base-only AUC {V.auc(y[m], base[m]):.3f}, rate {y[m].mean():.3f}")

print("== by event type / surprise (positives restricted to that type)")
evt = ev.reset_index(drop=True)
etype = np.array([evt.loc[e, "type"] if e >= 0 else "" for e in eid])
sb = np.array([evt.loc[e, "surprise_or_buildup"] if e >= 0 and "surprise_or_buildup" in evt else "" for e in eid])
for tp in ["onset", "strike", "maritime", "exercise", "other"]:
    pm = etype == tp
    print(f"{tp:9s}: events {len(set(eid[ok & pm & (y==1)]))}, within AUC {wauc_subset(pub, pm):.3f}, pooled AUC {V.auc(np.r_[np.ones((ok&pm&(y==1)).sum()), np.zeros((ok&(y==0)).sum())], np.r_[pub[ok&pm&(y==1)], pub[ok&(y==0)]]):.3f}")
for tp in ["buildup", "surprise"]:
    pm = sb == tp
    print(f"{tp:9s}: events {len(set(eid[ok & pm & (y==1)]))}, within AUC {wauc_subset(pub, pm):.3f}")

print("== per theatre: within AUC full vs history-only, events")
for t in V.TH:
    m = ok & (th == t)
    if y[m].sum() == 0: continue
    print(f"{t:12s} ev {len(set(eid[m & (y==1)])):3d}  full {V.auc(y[m], pub[m]):.3f}  hist {V.auc(y[m], pubh[m]):.3f}")

# Murphy decomposition of Brier on published probability (10 bins by quantile)
def murphy(p, yy, bins=10):
    q = np.quantile(p, np.linspace(0, 1, bins + 1)); q[-1] += 1e-9
    k = np.clip(np.searchsorted(q, p, side="right") - 1, 0, bins - 1)
    obar = yy.mean(); rel = res = 0.0
    for b in range(bins):
        m = k == b
        if not m.any(): continue
        rel += m.sum() * (p[m].mean() - yy[m].mean()) ** 2
        res += m.sum() * (yy[m].mean() - obar) ** 2
    n = len(p)
    return rel / n, res / n, obar * (1 - obar)
for nm, s in (("published", pub), ("history-only", pubh), ("base rate", base)):
    r = murphy(s[ok], y[ok])
    print(f"Murphy {nm:12s}: reliability {r[0]:.5f} resolution {r[1]:.5f} uncertainty {r[2]:.5f}  brier {V.brier(y[ok], s[ok]):.5f}")

# log score skill
def logloss(p, yy):
    p = np.clip(p, 1e-4, 1 - 1e-4); return -np.mean(yy*np.log(p) + (1-yy)*np.log(1-p))
print("log score: pub", logloss(pub[ok], y[ok]), "base", logloss(base[ok], y[ok]), "hist", logloss(pubh[ok], y[ok]))

print("== event-rate by year (theatre-days positive share; events per year)")
evc = ev[~ev["dup"]] if "dup" in ev else ev
print(evc.groupby(evc["date"].dt.year).size().to_dict())
for Y in range(2019, 2027):
    m = lab & (yr == Y) & np.isin(th, V.TH)
    print(Y, f"{y[m].mean():.3f}")
