#!/usr/bin/env python3
"""Prediction study, one-off data pulls (run by .github/workflows/predstudy-fetch.yml on GitHub's runners, which reach these hosts).

    python3 backtest/predstudy/fetch.py gpr          # Caldara-Iacoviello GPR and AI-GPR files -> backtest/predstudy/data/gpr/*.csv.gz
    python3 backtest/predstudy/fetch.py crisiswatch  # CrisisWatch issues from Wayback snapshots of the Crisis Group RSS feed and page
    python3 backtest/predstudy/fetch.py polymarket   # daily prices of resolved and open Polymarket markets on military action in the theatres

Public data only. Nothing here touches the live build, the model or the event list.
"""
import csv
import gzip
import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "backtest", "predstudy", "data")
UA = {"User-Agent": "warwatch-research/1.0 (public-data study; https://github.com/khourix/warwatch)"}


def get(url, tries=4, timeout=90, raw=False):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b if raw else b.decode("utf-8", "replace")
        except Exception as e:     # noqa: BLE001 - retried, then reported
            last = e
            time.sleep(3 * (i + 1))
    print(f"FAILED {url}: {last}", flush=True)
    return None


def save_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", path, len(rows), "rows", flush=True)


# ------------------------------------------------------------------ GPR and AI-GPR
GPR_PAGES = ["https://www.matteoiacoviello.com/gpr.htm", "https://www.matteoiacoviello.com/ai_gpr.html"]
DATA_EXT = (".xls", ".xlsx", ".csv", ".zip", ".dta")


def gpr():
    import pandas as pd
    manifest = []
    seen = set()
    for page in GPR_PAGES:
        h = get(page)
        if not h:
            manifest.append({"page": page, "error": "unreachable"})
            continue
        hrefs = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', h, re.I)
        for href in hrefs:
            url = urllib.parse.urljoin(page, href.strip())
            if not url.lower().split("?")[0].endswith(DATA_EXT) or url in seen:
                continue
            seen.add(url)
            b = get(url, raw=True, timeout=180)
            entry = {"page": page, "url": url, "bytes": len(b) if b else 0, "tables": []}
            if not b:
                manifest.append(entry)
                continue
            base = re.sub(r"[^\w.-]", "_", os.path.basename(urllib.parse.urlparse(url).path))
            frames = {}
            try:
                low = url.lower().split("?")[0]
                if low.endswith((".xls", ".xlsx")):
                    frames = pd.read_excel(io.BytesIO(b), sheet_name=None)
                elif low.endswith(".csv"):
                    frames = {"csv": pd.read_csv(io.BytesIO(b), low_memory=False)}
                elif low.endswith(".dta"):
                    frames = {"dta": pd.read_stata(io.BytesIO(b))}
                elif low.endswith(".zip"):
                    import zipfile
                    z = zipfile.ZipFile(io.BytesIO(b))
                    for n in z.namelist():
                        if n.lower().endswith(".csv"):
                            frames[n] = pd.read_csv(z.open(n), low_memory=False)
                        elif n.lower().endswith((".xls", ".xlsx")):
                            for sh, df in pd.read_excel(io.BytesIO(z.read(n)), sheet_name=None).items():
                                frames[f"{n}__{sh}"] = df
            except Exception as e:  # noqa: BLE001
                entry["error"] = repr(e)[:300]
            for sh, df in frames.items():
                tag = re.sub(r"[^\w.-]", "_", str(sh))
                name = f"{base}__{tag}.csv.gz"
                path = os.path.join(OUT, "gpr", name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if len(df) * max(1, len(df.columns)) > 6_000_000:      # keep the repo small: very large tables are described, not stored
                    entry["tables"].append({"sheet": str(sh), "rows": len(df), "cols": list(map(str, df.columns))[:80], "stored": False})
                    continue
                with gzip.open(path, "wt", newline="") as f:
                    df.to_csv(f, index=False)
                entry["tables"].append({"sheet": str(sh), "file": name, "rows": len(df), "cols": list(map(str, df.columns))[:80], "stored": True})
                print("wrote", path, df.shape, flush=True)
            manifest.append(entry)
            time.sleep(1)
    os.makedirs(os.path.join(OUT, "gpr"), exist_ok=True)
    with open(os.path.join(OUT, "gpr", "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


# ------------------------------------------------------------------ CrisisWatch from the Wayback Machine
MONTHS = {m: i + 1 for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"))}
CW_LISTS = {"alert": "Conflict Risk Alert", "resolution": "Resolution Opportunit", "deteriorated": "Deteriorated Situation", "improved": "Improved Situation"}


def cdx(url, frm="201712", to="202611", collapse="timestamp:8"):
    q = (f"https://web.archive.org/cdx/search/cdx?url={urllib.parse.quote(url, safe='')}&from={frm}&to={to}&output=json"
         f"&filter=statuscode:200&collapse={collapse}")
    t = get(q, timeout=180)
    try:
        rows = json.loads(t) if t else []
    except ValueError:
        rows = []
    return [dict(zip(rows[0], r)) for r in rows[1:]] if rows else []


def cw_rss_rows(rss):
    """The live parser's rule (warwatch/osint.py parse_crisiswatch), kept loose about markup: -> [(alert month, list, entry slug or name)]."""
    out = []
    for item in re.findall(r"<item>.*?</item>", rss, re.S):
        m = re.search(r"<title>\s*(?:<!\[CDATA\[)?\s*(\w+) (?:\d{4} )?Trends,? and (\w+) (?:\d{4} )?Alerts,? (\d{4})", item)
        if not m or m.group(2).lower() not in MONTHS:
            continue
        mon, yr = MONTHS[m.group(2).lower()], int(m.group(3))
        body = html.unescape(html.unescape(item))
        out += cw_lists(body, f"{yr:04d}-{mon:02d}-01")
    return out


def cw_lists(body, month):
    out = []
    for key, head in CW_LISTS.items():
        for k in [m.start() for m in re.finditer(re.escape(head), body)]:
            seg = body[k:k + 6000]
            end = re.search(r"</p>|</ul>|<h[1-6]", seg[len(head) + 20:])
            seg = seg[:len(head) + 20 + end.start()] if end else seg[:3000]
            slugs = re.findall(r'data-entry-target="([\w-]+)"', seg)
            if not slugs:
                slugs = [re.sub(r"\s+", "-", a.strip().lower()) for a in re.findall(r"<a[^>]*>([^<]{2,60})</a>", seg)]
            out += [(month, key, s) for s in slugs]
    return out


def crisiswatch():
    rows, raw = set(), []
    for u in ("crisisgroup.org/rss.xml", "www.crisisgroup.org/rss.xml", "crisisgroup.org/rss", "crisisgroup.org/crisiswatch/rss.xml"):
        snaps = cdx(u, collapse="timestamp:8")
        print(u, len(snaps), "snapshots", flush=True)
        last_month = None
        for s in snaps:
            ts = s["timestamp"]
            if last_month == ts[:6] + str(int(ts[6:8]) // 6):      # at most about five per month: the feed keeps ten posts
                continue
            last_month = ts[:6] + str(int(ts[6:8]) // 6)
            t = get(f"https://web.archive.org/web/{ts}id_/{s['original']}", timeout=120)
            time.sleep(1.0)
            if not t:
                continue
            got = cw_rss_rows(t)
            rows |= set(got)
            raw.append({"ts": ts, "src": "rss", "n": len(got)})
    # The CrisisWatch page itself: the newest issue's lists, as archived each month
    for u in ("crisisgroup.org/crisiswatch", "www.crisisgroup.org/crisiswatch"):
        snaps = cdx(u, collapse="timestamp:6")
        print(u, len(snaps), "monthly snapshots", flush=True)
        for s in snaps:
            ts = s["timestamp"]
            t = get(f"https://web.archive.org/web/{ts}id_/{s['original']}", timeout=120)
            time.sleep(1.0)
            if not t:
                continue
            body = html.unescape(t)
            m = re.search(r"(\w+) (\d{4}) Alerts", body) or re.search(r"Alerts?\s+for\s+(\w+)\s+(\d{4})", body)
            month = f"{int(m.group(2)):04d}-{MONTHS[m.group(1).lower()]:02d}-01" if m and m.group(1).lower() in MONTHS else f"snap-{ts[:8]}"
            got = cw_lists(body, month)
            rows |= {(a, b, c) for a, b, c in got}
            k = body.find("Conflict Risk Alert")
            raw.append({"ts": ts, "src": "page", "month": month, "n": len(got), "head": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body[k:k + 4000]))[:1500] if k >= 0 else ""})
    save_csv(os.path.join(OUT, "crisiswatch", "crisiswatch_wayback.csv.gz"), ["month", "list", "entry"], sorted(rows))
    with gzip.open(os.path.join(OUT, "crisiswatch", "snapshots.json.gz"), "wt") as f:
        json.dump(raw, f)


# ------------------------------------------------------------------ Polymarket
PLACE = (r"ukrain|russia|kyiv|crimea|nato|poland|baltic|lithuania|latvia|estonia|finland|moldova|iran|tehran|israel|gaza|hamas|hezbollah|lebanon|"
         r"syria|yemen|houthi|red sea|hormuz|saudi|qatar|uae|emirates|iraq|taiwan|china|chinese|pla\b|south china sea|philippin|scarborough|"
         r"north korea|south korea|korea|kim jong|india|pakistan|kashmir|libya|sudan|congo|drc|rwanda|m23|venezuela|maduro|caribbean|guyana")
ACTION = (r"invade|invasion|strike|strikes|attack|bomb|missile|drone|war\b|military|troops|blockade|airstrike|offensive|clash|ground operation|"
          r"enter|seize|capture|declare war|nuclear test|launch|ceasefire|shoot down|sink|fire on")


def polymarket():
    place, action = re.compile(PLACE, re.I), re.compile(ACTION, re.I)
    markets = {}

    def keep(m, title=""):
        q = (m.get("question") or "") + " " + title
        if place.search(q) and action.search(q) and m.get("id"):
            markets[str(m["id"])] = m

    def pages(url_fmt, step, cap):
        off, n = 0, 0
        while off < cap:
            t = get(url_fmt.format(off=off), timeout=120)
            try:
                page = json.loads(t) if t else []
            except ValueError:
                page = []
            if isinstance(page, dict):
                page = page.get("data") or page.get("events") or page.get("markets") or []
            if not page:
                break
            yield page
            n += len(page)
            off += step
            time.sleep(0.15)
        print("scanned", url_fmt[:90], n, flush=True)

    # 1. events by tag (each event carries its markets); 2. every market, closed and open
    for tag in ("geopolitics", "world", "middle-east", "ukraine", "russia", "israel", "iran", "china", "taiwan", "war", "military", "politics"):
        for closed in ("true", "false"):
            for page in pages("https://gamma-api.polymarket.com/events?tag_slug=" + tag + "&closed=" + closed + "&limit=100&offset={off}", 100, 30000):
                for e in page:
                    for m in e.get("markets") or []:
                        keep(m, e.get("title") or "")
        print("after tag", tag, len(markets), flush=True)
    for closed in ("true", "false"):
        for page in pages("https://gamma-api.polymarket.com/markets?limit=500&closed=" + closed + "&offset={off}", 500, 400000):
            for m in page:
                keep(m)
        print("after markets closed=" + closed, len(markets), flush=True)
    print("matching markets", len(markets), flush=True)
    meta, rows = [], []
    for mid, m in markets.items():
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
            outs = json.loads(m.get("outcomes") or "[]")
            final = json.loads(m.get("outcomePrices") or "[]")
        except ValueError:
            continue
        if not toks:
            continue
        yes = toks[outs.index("Yes")] if "Yes" in outs else toks[0]
        meta.append([mid, m.get("slug", ""), m.get("question", "").replace("\n", " "), m.get("createdAt", ""), m.get("startDate", ""), m.get("endDate", ""),
                     m.get("closedTime", ""), m.get("closed"), ";".join(outs), ";".join(map(str, final)), m.get("volume", "")])
        hist = []
        for q in (f"https://clob.polymarket.com/prices-history?market={yes}&interval=max&fidelity=1440",
                  f"https://clob.polymarket.com/prices-history?market={yes}&startTs=1577836800&endTs={int(time.time())}&fidelity=1440"):
            t = get(q, tries=2, timeout=60)
            try:
                hist = (json.loads(t) or {}).get("history", []) if t else []
            except ValueError:
                hist = []
            if hist:
                break
        rows += [[mid, time.strftime("%Y-%m-%d", time.gmtime(int(h["t"]))), h["p"]] for h in hist]
        time.sleep(0.2)
    save_csv(os.path.join(OUT, "polymarket", "markets.csv.gz"), ["id", "slug", "question", "created", "start", "end", "closed_time", "closed", "outcomes", "final_prices", "volume"], meta)
    save_csv(os.path.join(OUT, "polymarket", "prices_daily.csv.gz"), ["id", "date", "p_yes"], rows)


if __name__ == "__main__":
    for job in sys.argv[1:] or ["gpr", "crisiswatch", "polymarket"]:
        {"gpr": gpr, "crisiswatch": crisiswatch, "polymarket": polymarket}[job]()
