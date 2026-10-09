"""Metaculus community forecasts on the theatres' military questions, daily, as they stood each day. Token needed
(METACULUS_TOKEN, a repository secret). The question rule is fixed in docs/METACULUS_PLAN.md before any forecast is read.

Step 1 lists every binary question (titles and dates only) and keeps those whose title names a theatre and a military
action and does not ask about a ceasefire or settlement (RULE below). Step 2 reads each kept question's community-prediction
history and keeps the last value of each UTC day. Output, backfill/data/metaculus/:
  questions.csv   id, theatres, title, published, open, close, resolution
  cp.csv          id, day, p
"""
import csv
import datetime as dt
import io
import os
import re
import time
import zipfile

import common as K

API = "https://www.metaculus.com/api"
OUT = os.path.join(K.DATA, "metaculus")
PLACE = {
    "ukraine": r"ukrain|kyiv|kiev|crimea|donbas|donetsk|luhansk|zaporizh|kharkiv|odesa|odessa",
    "europe_east": r"\bnato\b|baltic|estonia|latvia|lithuania|poland|polish|finland|kaliningrad|suwa[lł]ki|romania",
    "iran": r"\biran|irgc|hormuz",
    "yemen": r"yemen|houthi|red sea|bab[- ]el",
    "israel": r"israel|hezbollah|hamas|gaza|lebanon|west bank",
    "taiwan": r"taiwan|taipei|kinmen|matsu",
    "scs": r"south china sea|philippin|spratly|scarborough|second thomas|vietnam",
    "korea": r"north korea|dprk|pyongyang|kim jong|south korea|korean peninsula",
    "southasia": r"\bindia|pakistan|kashmir",
    "libya": r"libya|tripoli|haftar",
    "sudan": r"sudan|\brsf\b|khartoum|darfur",
    "drc": r"congo|\bdrc\b|\bm23\b|goma|kivu|rwanda",
    "venezuela": r"venezuel|maduro|guyana|essequibo",
}
ACTION = (r"attack|invade|invasion|\bwar\b|strike|airstrike|military|troops|clash|conflict|missile|bomb|blockade|armed|offensive|"
          r"killed|deaths|fatalit|nuclear test|drone|shoot down|shot down|naval|incursion|occupy|annex|combat|hostilit|mobiliz|mobilis")
EXCLUDE = r"ceasefire|cease-fire|peace|truce|end of|\bend\b|agreement|\bdeal\b|negotiat|withdraw|normaliz|normalis|talks"


def rule(title):
    t = title.lower()
    if not re.search(ACTION, t) or re.search(EXCLUDE, t):
        return []
    return [th for th, pat in PLACE.items() if re.search(pat, t)]


def _get(url, tok):
    time.sleep(0.6)
    return K.get(url, headers={"Authorization": f"Token {tok}"}, retries=6, wait=10)


def _history(q):
    """[(epoch seconds, p)] from whichever aggregation the post carries."""
    ag = (q or {}).get("aggregations") or {}
    for k in ("recency_weighted", "unweighted", "metaculus_prediction"):
        h = (ag.get(k) or {}).get("history") or []
        out = []
        for it in h:
            c = it.get("centers") or it.get("means") or []
            if c and it.get("start_time") is not None:
                st = it["start_time"]
                st = st if isinstance(st, (int, float)) else dt.datetime.fromisoformat(str(st).replace("Z", "+00:00")).timestamp()
                out.append((float(st), float(c[0])))
        if out:
            return sorted(out)
    return []


def _download(pid, tok, log=False):
    """[(epoch seconds, p)] from the post's data download (the post itself carries no history for API reads)."""
    time.sleep(0.6)
    b = K.get(f"{API}/posts/{pid}/download-data/?aggregation_methods=recency_weighted", raw=True,
              headers={"Authorization": f"Token {tok}"}, retries=6, wait=10)
    files = {}
    if b[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(b))
        files = {n: z.read(n).decode("utf-8", "replace") for n in z.namelist()}
    else:
        files = {"body": b.decode("utf-8", "replace")}
    if log:
        K.log("download", pid, {n: (len(t), t.splitlines()[0][:300] if t else "") for n, t in files.items()})
    for n, t in files.items():
        if "aggregat" not in n.lower() and n != "body":
            continue
        rows = list(csv.DictReader(io.StringIO(t)))
        if not rows:
            continue
        cols = {c.lower(): c for c in rows[0]}
        tcol = next((cols[c] for c in cols if "start" in c and "time" in c), None)
        pcol = next((cols[c] for c in cols if "probability yes" in c or c in ("centers", "center", "median", "probability_yes")), None)
        mcol = next((cols[c] for c in cols if "method" in c), None)
        if not (tcol and pcol):
            continue
        out = []
        for r in rows:
            if mcol and r[mcol] and "recency" not in r[mcol].lower():
                continue
            try:
                v = float(str(r[pcol]).strip("[]").split(",")[0])
                ts = r[tcol]
                ts = float(ts) if re.fullmatch(r"[\d.]+", ts) else dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                continue
            out.append((ts, v))
        if out:
            return sorted(out)
    return []


def cmd_metaculus(tok):
    os.makedirs(OUT, exist_ok=True)
    keep, seen, off = [], 0, 0
    qpath = os.path.join(OUT, "questions.csv")
    listed = os.path.exists(qpath)
    if listed:                                      # the list is fixed once made; rerun only the histories
        keep = list(csv.DictReader(open(qpath)))
        K.log("metaculus: reusing", len(keep), "listed questions")
    while not listed:
        js = _get(f"{API}/posts/?forecast_type=binary&statuses=open&statuses=closed&statuses=resolved&order_by=-published_at&limit=100&offset={off}", tok)
        res = js.get("results", [])
        if off == 0:
            K.log("metaculus listing: count", js.get("count"), "first keys", sorted(res[0])[:20] if res else None)
        for p in res:
            q = p.get("question") or {}
            title = q.get("title") or p.get("title") or ""
            th = rule(title)
            if th and q.get("type", "binary") == "binary":
                keep.append({"id": p["id"], "theatres": ";".join(th), "title": title, "published": p.get("published_at") or "",
                             "open": q.get("open_time") or "", "close": q.get("actual_close_time") or q.get("scheduled_close_time") or "",
                             "resolution": q.get("resolution") or ""})
        seen += len(res)
        if not js.get("next") or not res:
            K.log("metaculus: listed", seen, "binary questions;", len(keep), "match the rule")
            listed = True
            break
        off += len(res)
    with open(qpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "theatres", "title", "published", "open", "close", "resolution"])
        w.writeheader()
        w.writerows(keep)
    rows, first = [], 0
    for q in keep:
        try:
            p = _get(f"{API}/posts/{q['id']}/", tok)
        except Exception as e:
            K.log("skip", q["id"], str(e)[:100])
            continue
        hist = _history(p.get("question"))
        if not hist:
            try:
                hist = _download(q["id"], tok, log=first < 3)
            except Exception as e:
                K.log("download failed", q["id"], str(e)[:120])
        first += 1
        day = {}
        for t, v in hist:
            day[dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()] = v
        rows += [(q["id"], d, round(v, 4)) for d, v in sorted(day.items())]
    with open(os.path.join(OUT, "cp.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "day", "p"])
        w.writerows(rows)
    K.log("metaculus: wrote", len(rows), "question-days")
