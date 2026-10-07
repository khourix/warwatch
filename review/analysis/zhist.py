"""Point-in-time z history for every backtest series (as the v7 dashboard would have scored it each day)."""
import sys, os, pickle, datetime as dt, bisect
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import backtest as B, stats
series = B.load_series()
START, END = dt.date(2018, 6, 1), dt.date(2026, 9, 30)
out = {}
for s in series:
    zs = {}
    d = START
    while d <= END:
        o = d.toordinal()
        cut = bisect.bisect_right(s['avail'], o)
        pts = s['all'][max(0, cut - 250):cut]
        if pts:
            r = stats.score_series(pts, s['kind'])
            if r is not None:
                zs[d] = r['z']
        d += dt.timedelta(days=1)
    out[s['id']] = {k: s[k] for k in ('theatre', 'domain', 'direction', 'lag', 'kind')} | {'z': zs}
    print(s['id'], len(zs), flush=True)
pickle.dump(out, open('zhist.pkl', 'wb'))
