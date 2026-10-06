"""Robust anomaly maths, standard library only.

A series is a list of (label, value). The score of the newest point is a
robust z against a baseline: the median and MAD of comparable earlier points.
Comparable means the same calendar month in prior years when the series is
monthly and has at least 3 such years (strips fiscal-year seasonality), else
the trailing window.
"""
import math
import statistics

MAD_SCALE = 1.4826


def robust_z(value, baseline, min_n=6):
    """z of `value` against `baseline`; None when the baseline is too thin."""
    if len(baseline) < min_n:
        return None
    med = statistics.median(baseline)
    mad = statistics.median(abs(x - med) for x in baseline)
    scale = MAD_SCALE * mad
    if scale == 0:   # flat history: fall back to mean absolute deviation
        scale = statistics.fmean(abs(x - med) for x in baseline) or 0
    if scale == 0:   # a perfectly flat past: any change is maximal
        return 0.0 if value == med else (6.0 if value > med else -6.0)
    return max(-12.0, min(12.0, (value - med) / scale))


def deseasonalize(points, period=12):
    """log1p values minus a per-calendar-month factor (median over the years)."""
    logs = [math.log1p(max(v, 0.0)) for _, v in points]
    n = len(logs)
    # centred annual mean removes the level so the factor is pure seasonality
    dev = []
    for i in range(n):
        lo, hi = max(0, i - period // 2), min(n, i + period // 2 + 1)
        dev.append(logs[i] - statistics.fmean(logs[lo:hi]))
    # leave-one-out: a point never helps set its own seasonal factor, so the
    # baseline residuals are as noisy as the newest one (no in-sample shrinkage);
    # the newest point is excluded from every factor.
    out = []
    for i in range(n):
        same = [dev[j] for j in range(i % period, n - 1, period) if j != i]
        out.append(logs[i] - (statistics.median(same) if same else 0.0))
    return out



def score_series(points, kind):
    """-> dict(z, method, value, label) for the newest point, or None.

    monthly: log, remove calendar-month seasonality, robust z of the newest
    month against the previous 36 (needs 36+ months). daily: the latest
    7-day mean against weekly means over the prior 26 weeks (needs 84+ days; up to 26 weeks).
    """
    if kind == "monthly":
        if len(points) < 40:
            return None
        res = deseasonalize(points)
        z = robust_z(res[-1], res[-37:-1])
        return None if z is None else {"z": z, "method": "seasonal-adjusted", "value": points[-1][1],
                                       "label": points[-1][0]}
    if len(points) < 84:
        return None
    recent = statistics.fmean(v for _, v in points[-7:])
    base_pts = [v for _, v in points[-189:-7]]
    weekly = [statistics.fmean(base_pts[i:i + 7]) for i in range(0, len(base_pts) - 6, 7)]
    z = robust_z(recent, weekly)
    return None if z is None else {"z": z, "method": "vs prior 26 weeks", "value": recent, "label": points[-1][0]}


def ewma(values, alpha=0.3):
    out, s = [], None
    for v in values:
        s = v if s is None else alpha * v + (1 - alpha) * s
        out.append(s)
    return out
