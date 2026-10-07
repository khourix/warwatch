"""Shared helpers for the history back-fills. Public data only, standard library only.

Every back-fill writes plain `date,value` CSVs under backfill/data/ (one file per series, UTC day, ascending),
the same shape as backtest/history. Series ids match the live catalogue where the live series has one, so
validate.py can line a back-filled history up with the live feed that continues it. The live engine reads none of this.
"""
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "warwatch"))   # config.py, extras.py, sources.py: reused, never edited
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "warwatch-backfill/0.1 (public-data research; github.com/khourix/warwatch)"}
START = dt.date(2018, 1, 1)                          # same floor as the GDELT history
YDAY = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)


def get(url, data=None, headers=None, raw=False, timeout=120, retries=4, wait=5):
    """GET (or POST json) with retries. Returns parsed JSON, or bytes when raw."""
    hdr = dict(UA)
    hdr.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdr["Content-Type"] = "application/json"
    err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=hdr), timeout=timeout) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            err = f"{e} {e.read()[:120]!r}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            err = e
        time.sleep(wait * (i + 1))
    raise RuntimeError(f"{str(err)[:240]} @ {url.split('?')[0][:80]}")


def days(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def path(series):
    return os.path.join(DATA, f"{series}.csv")


def load(series):
    try:
        with open(path(series), newline="") as f:
            return {r[0]: float(r[1]) for r in csv.reader(f) if len(r) == 2}
    except OSError:
        return {}


def save(series, rows):
    """Merge {iso_date: value} into the series file (new values win) and rewrite it sorted."""
    cur = load(series)
    cur.update({str(k): float(v) for k, v in dict(rows).items()})
    os.makedirs(DATA, exist_ok=True)
    with open(path(series), "w", newline="") as f:
        w = csv.writer(f)
        for d in sorted(cur):
            w.writerow([d, f"{cur[d]:.6g}"])
    return len(cur)


def log(*a):
    print(*a, flush=True)
