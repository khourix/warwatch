"""Per-family KLR leading-ness: best threshold on all theatres, hit rate on pre-event windows, false-alarm rate, NSR, event coverage, median lead."""
import sys, numpy as np, pandas as pd, panel
paths = sys.argv[2:]
H = panel.load(paths); P, meta = panel.panel(H)
ev = pd.read_csv(sys.argv[1]); y, excl, lead, eid, evlist = panel.labels(P, ev)
use = ~excl
rows = []
for f in [c for c in P.columns if c in meta]:
    x = P[f].values; ok = use & ~np.isnan(x)
    if y[ok].sum() < 50: continue
    best = None
    for c in (1.0, 1.5, 2.0, 2.5, 3.0):
        sig = x >= c
        hit = (sig & ok & (y == 1)).sum() / (ok & (y == 1)).sum()
        fa = (sig & ok & (y == 0)).sum() / (ok & (y == 0)).sum()
        if hit == 0: continue
        nsr = fa / hit
        if best is None or nsr < best[1]: best = (c, nsr, hit, fa)
    if not best: continue
    c, nsr, hit, fa = best
    evs = sorted(set(eid[ok & (y == 1)])); got = 0; leads = []
    for e in evs:
        m = ok & (eid == e) & (x >= c)
        if m.any(): got += 1; leads.append(np.nanmax(lead[m]))
    rows.append(dict(family=f, domain=meta[f][0], confirming=meta[f][1], thr=c, hit=round(hit, 3), false_alarm=round(fa, 3),
                     nsr=round(nsr, 2), events=f"{got}/{len(evs)}", ev_frac=got / max(1, len(evs)), med_lead=np.median(leads) if leads else None,
                     cond_p=round((sig := (x >= c) & ok & (y == 1)).sum() / max(1, ((x >= c) & ok).sum()), 3)))
T = pd.DataFrame(rows).sort_values('nsr')
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)
print('base rate', round(y[use].mean(), 3))
print(T.to_string(index=False))
T.to_csv('out/famtable.csv', index=False)
