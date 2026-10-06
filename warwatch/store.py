"""Tiny CSV history for sources that only expose "now" (ADS-B, advisory
levels). Public data only; the folder is committed by the workflow.
"""
import csv
import datetime as dt
import os

ROOT = os.environ.get("WARWATCH_HISTORY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "history"))


def path(series_id):
    return os.path.join(ROOT, f"{series_id}.csv")


def load(series_id):
    p = path(series_id)
    if not os.path.exists(p):
        return []
    with open(p, newline="") as f:
        return [(r[0], float(r[1])) for r in csv.reader(f) if len(r) == 2]


def append(series_id, value, when=None):
    """Append one observation stamped with its UTC fetch time."""
    when = when or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    os.makedirs(ROOT, exist_ok=True)
    with open(path(series_id), "a", newline="") as f:
        csv.writer(f).writerow([when, f"{value:.4f}"])


def daily(series_id):
    """Collapse the history to one mean value per UTC day."""
    by = {}
    for t, v in load(series_id):
        by.setdefault(t[:10], []).append(v)
    return sorted((d, sum(v) / len(v)) for d, v in by.items())


def cache_path(series_id):
    return os.path.join(ROOT, "cache", f"{series_id}.csv")


def cache_save(series_id, pts):
    """Last good full fetch of a series; overwritten each time. Public data only."""
    os.makedirs(os.path.dirname(cache_path(series_id)), exist_ok=True)
    with open(os.path.join(os.path.dirname(cache_path(series_id)), f"{series_id}.ts"), "w") as f:
        f.write(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M"))
    with open(cache_path(series_id), "w", newline="") as f:
        csv.writer(f).writerows((t, repr(float(v))) for t, v in pts)


def cache_load(series_id):
    try:
        with open(cache_path(series_id), newline="") as f:
            return [(r[0], float(r[1])) for r in csv.reader(f) if len(r) == 2]
    except OSError:
        return []


def cache_rows(name):
    """A multi-column cache table (rows of strings)."""
    try:
        with open(os.path.join(ROOT, "cache", f"{name}.csv"), newline="") as f:
            return [r for r in csv.reader(f) if r]
    except OSError:
        return []


def cache_rows_save(name, rows):
    os.makedirs(os.path.join(ROOT, "cache"), exist_ok=True)
    with open(os.path.join(ROOT, "cache", f"{name}.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rows)


def cache_age_hours(series_id):
    """Hours since the series was last fetched in full, or None if never (a checkout's file times are meaningless, so a stamp file is kept)."""
    try:
        with open(os.path.join(os.path.dirname(cache_path(series_id)), f"{series_id}.ts")) as f:
            t = dt.datetime.strptime(f.read().strip(), "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc)
    except (OSError, ValueError):
        return None
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600
