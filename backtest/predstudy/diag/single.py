import os, pickle, sys, numpy as np, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import base as BB; V = BB.V
o = BB.load()
P, y, lab, eid, fams = o['P'], o['y'], o['lab'], o['eid'], o['fams']
yr = P['date'].dt.year.values; th = P['theatre'].values
core = np.isin(th, V.TH)
def wauc(x, extra=None):
    ok = lab & ~np.isnan(x) & (yr >= 2021) & core
    num = den = 0.0
    for t in V.TH:
        m = ok & (th == t); n1 = y[m].sum()
        if n1 == 0 or n1 == m.sum(): continue
        num += n1 * V.auc(y[m], x[m]); den += n1
    return num / den if den else np.nan, len(set(eid[ok & (y == 1)]))
rows = []
for f in fams:
    a, n = wauc(P[f].values.astype(float))
    rows.append((f, a, n))
rows = [r for r in rows if r[1] == r[1] and r[2] >= 30]
rows.sort(key=lambda r: -r[1])
A = np.array([r[1] for r in rows])
print("families with >=30 events:", len(rows), "median within AUC %.3f, IQR %.3f-%.3f, max %.3f" % (np.median(A), *np.percentile(A, [25, 75]), A.max()))
print("share above 0.55: %.2f, above 0.57: %.2f" % ((A > 0.55).mean(), (A > 0.57).mean()))
for r in rows[:12]: print("%-28s %.3f  events %d" % r)
print('...'); 
for r in rows[-5:]: print("%-28s %.3f  events %d" % r)
# same under circular shift (null): per-family shift each theatre's series by a random offset >= 180 days
rng = np.random.default_rng(1)
null_max = []
for k in range(200):
    best = 0
    vals = []
    for f, _, _ in rows:
        x = P[f].values.astype(float).copy()
        for t in V.TH:
            m = np.where(th == t)[0]
            if len(m) < 400: continue
            s = rng.integers(180, len(m) - 180)
            x[m] = np.roll(x[m], s)
        vals.append(wauc(x)[0])
    null_max.append(np.nanmax(vals))
    if k == 0: null_med = np.nanmedian(vals)
print("null (shifted) family max within AUC: median %.3f, 95th %.3f; first-draw median %.3f" % (np.median(null_max), np.percentile(null_max, 95), null_med))
json.dump({"rows": rows, "null_max_median": float(np.median(null_max)), "null_max_95": float(np.percentile(null_max, 95))}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'single.json'), 'w'))
