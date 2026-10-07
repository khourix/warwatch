"""Alternative scorings (long baseline, EWMA) for every daily backtest series; monthly series keep the v7 score."""
import sys, pickle, csv, datetime as dt
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import backtest as B, catalog, scorers
H = pickle.load(open('zhist.pkl', 'rb'))
cat = {s['id']: s for s in catalog.SERIES}
L, Ew = {}, {}
for sid, h in H.items():
    s = cat[sid]
    if s['kind'] != 'daily':
        L[sid] = h; Ew[sid] = h; continue
    fn = B._fetcher(s)
    lag = B.LAG.get(fn, 1) if fn else 1
    pts = [(r[0], float(r[1])) for r in csv.reader(open(f'/home/claude/warwatch/backtest/history/{sid}.csv'))]
    zl, ze = scorers.long_and_cusum(pts, 'up', lag=lag)     # raw z; direction applied later in panel
    L[sid] = dict(h, z=zl); Ew[sid] = dict(h, z=ze)
    print(sid, len(zl), flush=True)
pickle.dump(L, open('zhist_long.pkl', 'wb')); pickle.dump(Ew, open('zhist_ewma.pkl', 'wb'))
