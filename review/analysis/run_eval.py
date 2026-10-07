import sys, json, numpy as np, pandas as pd
import panel, evaluate as V
paths = sys.argv[2:] or ['zhist.pkl']
H = panel.load(paths); P, meta = panel.panel(H)
ev = pd.read_csv(sys.argv[1])
y, excl, lead, eid, evlist = panel.labels(P, ev)
use = ~excl
res = []
s0 = V.v7(P, meta); res.append(V.metrics('v7 as built', s0, y, use, eid, lead, P))
s1 = V.v7(P, meta, onesided=True); res.append(V.metrics('v7 one-sided (z floored at 0)', s1, y, use, eid, lead, P))
s2 = V.v7(P, meta, onesided=True, orness=0.7); res.append(V.metrics('v7 one-sided, OWA orness 0.7', s2, y, use, eid, lead, P))
s3 = V.klr_nb(P, meta, y, use); res.append(V.metrics('KLR signals, naive Bayes (LOTO)', s3, y, use, eid, lead, P))
s4 = V.loto_logit(P, meta, y, use); res.append(V.metrics('Penalised logit (LOTO)', s4, y, use, eid, lead, P))
for r in res: print(r)
ok = use & ~np.isnan(s4)
from sklearn.metrics import brier_score_loss
b = brier_score_loss(y[ok], s4[ok]); clim = brier_score_loss(y[ok], np.full(ok.sum(), y[ok].mean()))
print('logit Brier', round(b, 4), 'climatology', round(clim, 4), 'BSS', round(1 - b / clim, 3))
np.save('scores.npy', np.vstack([s0, s1, s2, s3, s4]))
