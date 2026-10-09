"""Outside forecasts as they were published, month by month: ConflictForecast.org (Mueller, Rauh and Seimon) and VIEWS
(Uppsala and PRIO). Both are free and open. Each monthly vintage is kept as published, so a backtest only ever sees the
forecast that existed on the day: no look-ahead.

The downloads (rows for the theatres' countries, every field) go to a scratch folder, RAW:
  cf/<MM-YYYY>/<file>.csv       ConflictForecast files of that vintage (armed conflict and any violence, 3 and 12 months)
  views/<run>.csv               VIEWS country-month state-based forecasts of that run
and backfill/forecasts_compact.py keeps only what each vintage forecast, in backfill/data/forecasts/ (each ConflictForecast
file repeats fitted values back to 2010, about 600 MB in all, so the raw files are not committed).
"""
import csv
import io
import os
import tempfile

import common as K

ISO = {"ukraine": ("UKR",), "europe_east": ("POL", "LTU", "LVA", "EST", "FIN", "ROU"), "iran": ("IRN",), "yemen": ("YEM",),
       "israel": ("ISR", "PSE", "LBN", "SYR"), "taiwan": ("TWN",), "scs": ("PHL", "VNM"), "korea": ("PRK", "KOR"),
       "southasia": ("IND", "PAK"), "libya": ("LBY",), "sudan": ("SDN", "SSD"), "drc": ("COD",), "venezuela": ("VEN", "GUY")}
ALL = {i for v in ISO.values() for i in v}
OUT = os.path.join(K.DATA, "forecasts")
RAW = os.path.join(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir(), "forecasts_raw")
CF = "https://api.backendless.com/C177D0DC-B3D5-818C-FF1E-1CC11BC69600/C5F2917E-C2F6-4F7D-9063-69555274134E/services/fileService/"
VIEWS = "https://api.viewsforecasting.org/"


def _keep_rows(text):
    """Header plus the rows that mention one of the theatre ISO codes in any column."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    return [rows[0]] + [r for r in rows[1:] if any(c.strip() in ALL for c in r)]


def _vintages():
    """MM-YYYY from January 2019 to this month; a month with no release just lists nothing."""
    y, m, out = 2019, 1, []
    while (y, m) <= (K.YDAY.year, K.YDAY.month):
        out.append(f"{m:02d}-{y}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def cmd_conflictforecast():
    try:
        K.log("conflictforecast directories:", str(K.get(CF + "get-all-directories"))[:400])
    except Exception as e:
        K.log("directory listing failed:", str(e)[:120])
    names = _vintages()
    for v in names:
        dest = os.path.join(RAW, "cf", v)
        if os.path.isdir(dest) and os.listdir(dest):
            continue
        try:
            files = K.get(CF + "get-file-listing?date=" + v)
        except Exception as e:
            K.log("skip vintage", v, str(e)[:80])
            continue
        if isinstance(files, dict):
            files = files.get("data") or files.get("files") or []
        for f in files:
            n = f.get("name", "")
            if not n.endswith(".csv") or "grid" in n.lower():
                continue
            try:
                txt = K.get(f["publicUrl"], raw=True).decode("utf-8", "replace")
            except Exception as e:
                K.log("skip file", v, n, str(e)[:80])
                continue
            rows = _keep_rows(txt)
            if len(rows) > 1:
                os.makedirs(dest, exist_ok=True)
                with open(os.path.join(dest, n), "w", newline="") as fh:
                    csv.writer(fh).writerows(rows)
                K.log(v, n, "header", rows[0][:8], "rows", len(rows) - 1)


def cmd_views():
    root = K.get(VIEWS)
    runs = root.get("runs", []) if isinstance(root, dict) else list(root)
    runs = [r for r in runs if r.startswith("fatalities")]      # the 2021 r_* runs cover Africa only
    K.log("views runs:", len(runs), runs[:3], "...", runs[-3:])
    for run in runs:
        dest = os.path.join(RAW, "views", run + ".csv")
        if os.path.exists(dest):
            continue
        out = []
        for iso in sorted(ALL):
            url = f"{VIEWS}{run}/cm/sb?iso={iso}&pagesize=1000"
            while url:
                try:
                    js = K.get(url)
                except Exception as e:
                    K.log("skip", run, iso, str(e)[:80])
                    break
                out += [r for r in js.get("data", []) if isinstance(r, dict)]
                url = js.get("next_page") or ""
        if out:
            cols = sorted({k for r in out for k in r})       # field names changed between model generations: keep them all
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols)
                w.writeheader()
                w.writerows(out)
            K.log(run, "rows", len(out), "fields", cols[:12])
