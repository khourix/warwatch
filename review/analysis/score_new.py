import sys, pickle, bisect, datetime as dt
from multiprocessing import Pool
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import stats, scorers, backtest as B
S = pickle.load(open('newseries.pkl', 'rb'))
def job(item):
    sid, s = item
    pts = s['points']
    meta = {k: s[k] for k in ('theatre', 'domain', 'direction', 'lag', 'kind')}
    if s['kind'] == 'monthly':
        avail = [(B._eom(l) + dt.timedelta(days=s['lagdays'])).toordinal() for l, _ in pts]
        z = {}
        d = dt.date(2018, 6, 1)
        while d <= dt.date(2026, 9, 30):
            cut = bisect.bisect_right(avail, d.toordinal())
            r = stats.score_series(pts[max(0, cut - 250):cut], 'monthly') if cut else None
            if r: z[d] = r['z']
            d += dt.timedelta(days=1)
        return sid, dict(meta, z=z), dict(meta, z=z), dict(meta, z=z)
    z7 = scorers.v7(pts, lag=s['lagdays'])
    zl, ze = scorers.long_and_cusum(pts, 'up', lag=s['lagdays'])
    return sid, dict(meta, z=z7), dict(meta, z=zl), dict(meta, z=ze)
if __name__ == '__main__':
    with Pool(8) as p:
        res = p.map(job, list(S.items()), chunksize=2)
    for k, name in ((1, 'znew_v7.pkl'), (2, 'znew_long.pkl'), (3, 'znew_ewma.pkl')):
        pickle.dump({r[0]: r[k] for r in res}, open(name, 'wb'))
    print('done', len(res))
