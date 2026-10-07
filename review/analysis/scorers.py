"""Point-in-time daily scorers: v7 (production), long (365-day baseline skipping the latest 30 days), ewma (EWMA z of daily robust z, lambda 0.1)."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import stats

def daily_frame(points, start='2017-06-01', end='2026-10-06'):
    s = pd.Series({pd.Timestamp(k[:10]): float(v) for k, v in points})
    s = s[~s.index.duplicated()].sort_index()
    idx = pd.date_range(start, end, freq='D')
    s = s.reindex(idx)
    return s.ffill(limit=2)            # same LOCF rule as production

def v7(points, lag=1, grid=None):
    """Production score_series on every day (slow-ish but exact)."""
    pts = sorted(points)
    out = {}
    labels = [p[0][:10] for p in pts]
    import bisect
    grid = grid or pd.date_range('2018-06-01', '2026-09-30', freq='D')
    for d in grid:
        cut = bisect.bisect_right(labels, (d - pd.Timedelta(days=lag)).strftime('%Y-%m-%d'))
        p = pts[max(0, cut - 250):cut]
        if p:
            r = stats.score_series(p, 'daily')
            if r is not None:
                out[d.date()] = r['z']
    return out

def _rmed_mad(arr, lo, hi):
    w = arr[lo:hi]; w = w[~np.isnan(w)]
    if len(w) < 120: return None, None
    m = np.median(w); mad = np.median(np.abs(w - m))
    if mad == 0:
        mad = np.mean(np.abs(w - m)) * 0.7979   # mean abs dev -> MAD-equivalent for normal data
    return m, mad

def long_and_cusum(points, direction='up', lag=1, base=365, guard=30, lam=0.1):
    s = daily_frame(points)
    m7 = s.rolling(7, min_periods=4).mean().values
    raw = s.values
    idx = s.index
    zl, cs = {}, {}
    S = 0.0
    for i in range(len(idx)):
        lo, hi = i - base, i - guard
        if lo < 0:
            continue
        m, mad = _rmed_mad(m7, lo, hi)
        md, madd = _rmed_mad(raw, lo, hi)
        d = (idx[i] + pd.Timedelta(days=lag)).date()
        if m is not None and mad and not np.isnan(m7[i]):
            z = 0.6745 * (m7[i] - m) / mad
            zl[d] = float(max(-5, min(5, z)))
        if md is not None and madd and not np.isnan(raw[i]):
            u = 0.6745 * (raw[i] - md) / madd
            u = {'up': u, 'down': -u}.get(direction, abs(u))
            S = lam * max(-5.0, min(u, 5.0)) + (1 - lam) * S
            cs[d] = float(max(-5, min(5, S / (lam / (2 - lam)) ** 0.5)))
        elif md is None:
            S = 0.0
    return zl, cs
