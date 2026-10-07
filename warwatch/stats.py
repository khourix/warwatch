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



def legacy_score_series(points, kind):
    """Pre-v7 scoring (26-week baseline, clamp 12). Kept only so the backtest can show before/after.
    -> dict(z, method, value, label) for the newest point, or None.

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
    if z is None:
        return None
    med = statistics.median(weekly)
    scale = MAD_SCALE * statistics.median(abs(x - med) for x in weekly) or statistics.fmean(abs(x - med) for x in weekly)
    return {"z": z, "method": "vs prior 26 weeks", "value": recent, "label": points[-1][0],
            "base_med": med, "base_sd": scale, "base_n": len(weekly)}


WINSOR = 5.0
BASE_DAYS = 90
YEAR_DAYS = 365   # preferred baseline: the year before the newest 30 days
GUARD_DAYS = 30   # the newest month is left out of the baseline, so a slow build-up is not absorbed into its own yardstick
YEAR_MIN = 120    # rolling means needed in the year baseline; shorter histories use the plain 90-day baseline
FILL_MAX = 2   # carry the last value forward over at most this many missing days


def modified_z(value, baseline, min_n=6):
    """Modified z = 0.6745 * (x - median) / MAD, winsorized at +-5. -> (z, raw) or None.
    A zero MAD (flat history) falls back to the mean absolute deviation (x 1.2533 so it equals
    one sd for normal data); a perfectly flat past gives 0 for no change and +-WINSOR otherwise."""
    if len(baseline) < min_n:
        return None
    med = statistics.median(baseline)
    mad = statistics.median(abs(x - med) for x in baseline)
    if mad > 0:
        raw = 0.6745 * (value - med) / mad
    else:
        mean_ad = statistics.fmean(abs(x - med) for x in baseline)
        if mean_ad == 0:
            raw = 0.0 if value == med else (WINSOR * 2 if value > med else -WINSOR * 2)
        else:
            raw = (value - med) / (1.2533 * mean_ad)
    return max(-WINSOR, min(WINSOR, raw)), raw


def calendar_fill(points, days, end=None):
    """Daily values on a calendar of `days` days ending at the newest point. A gap of up to FILL_MAX
    days carries the last value forward (LOCF); longer gaps stay None. -> (values, observed, filled)."""
    import datetime as dt
    by = {l: v for l, v in points}
    last = dt.date.fromisoformat(points[-1][0][:10])
    vals, obs, filled, run, prev = [], 0, 0, 0, None
    for k in range(days - 1, -1, -1):
        d = (last - dt.timedelta(days=k)).isoformat()
        if d in by:
            prev, run = by[d], 0
            vals.append(prev)
            obs += 1
        else:
            run += 1
            if prev is not None and run <= FILL_MAX:
                vals.append(prev)
                filled += 1
            else:
                vals.append(None)
    return vals, obs, filled


def score_series(points, kind, base_days=None):
    """-> dict(z, z_raw, method, value, label, miss, filled, ...) for the newest point, or None.

    z is the modified z (winsorized at +-5; z_raw keeps the unclamped value for the audit log).
    monthly: log, remove calendar-month seasonality, against the previous 36 months (needs 40).
    daily: the latest 7-day mean against the 7-day means of the year before the newest 30 days (gaps <=2 days
    carried forward, longer gaps left missing; needs YEAR_MIN such means and 4 of the last 7 days). Series with
    less history than that, and any call with an explicit base_days, use the plain trailing window of base_days
    days (needs half of those baseline means)."""
    if kind == "monthly":
        if len(points) < 40:
            return None
        res = deseasonalize(points)
        r = modified_z(res[-1], res[-37:-1])
        return None if r is None else {"z": r[0], "z_raw": r[1], "method": "seasonal-adjusted, modified z", "value": points[-1][1],
                                       "label": points[-1][0], "miss": 0.0, "filled": 0}
    if base_days is None:
        r = len(points) >= YEAR_MIN and _score_daily(points, YEAR_DAYS + 7 + GUARD_DAYS, GUARD_DAYS, YEAR_MIN, "vs prior year (latest 30 days left out), modified z")
        if r:
            return r
        base_days = BASE_DAYS
    if len(points) < base_days // 2 + 7:
        return None
    return _score_daily(points, base_days + 7, 0, base_days // 2, "vs prior 90 days, modified z" if base_days == BASE_DAYS else f"vs prior {base_days} days, modified z")


def _score_daily(points, n_win, guard, min_roll, method):
    """Latest 7-day mean against the 7-day means that ended between 6 and n_win-1-guard days before the window's end."""
    vals, obs, filled = calendar_fill(points, n_win)
    last7 = [v for v in vals[-7:] if v is not None]
    if len(last7) < 4:
        return None
    recent = statistics.fmean(last7)
    roll = []
    for i in range(6, n_win - guard):
        w = [v for v in vals[i - 6:i + 1] if v is not None]
        if len(w) >= 5:
            roll.append(statistics.fmean(w))
    if len(roll) < min_roll:
        return None
    r = modified_z(recent, roll)
    if r is None:
        return None
    med = statistics.median(roll)
    mad = statistics.median(abs(x - med) for x in roll)
    sd = mad / 0.6745 if mad else statistics.fmean(abs(x - med) for x in roll) * 1.2533
    return {"z": r[0], "z_raw": r[1], "method": method, "value": recent, "label": points[-1][0],
            "base_med": med, "base_sd": sd, "base_n": len(roll), "miss": round(1 - (obs + filled) / n_win, 3), "filled": filled}


def ewma(values, alpha=0.3):
    out, s = [], None
    for v in values:
        s = v if s is None else alpha * v + (1 - alpha) * s
        out.append(s)
    return out


def history_z(points, kind, n):
    """[(label, z)] for the last n points, each scored as if it were the newest (what the dashboard
    would have shown that day). Points that cannot be scored yet are skipped."""
    out = []
    for i in range(max(0, len(points) - n), len(points)):
        r = score_series(points[:i + 1], kind)
        if r is not None:
            out.append((points[i][0], round(r["z"], 2)))
    return out
