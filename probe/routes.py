"""Other routes to the sites that block both GitHub and the home connection, plus live tests of Tzeva Adom and Jetstream.

Public data only. The Comtrade key is sent as a header and never written out.
"""
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warwatch"))
import assessment_probe as P  # noqa: E402

CDX = "https://web.archive.org/cdx/search/cdx?"


def cdx(url, limit=-300, **kw):
    q = {"url": url, "output": "json", "limit": str(limit), "fl": "original,timestamp,statuscode", "collapse": "urlkey"}
    q.update(kw)
    return CDX + urllib.parse.urlencode(q)


ROUTES = [
    # Crisis Group CrisisWatch
    ("crisiswatch: rss.xml", "https://www.crisisgroup.org/rss.xml", {}),
    ("crisiswatch: rss", "https://www.crisisgroup.org/rss", {}),
    ("crisiswatch: print", "https://www.crisisgroup.org/crisiswatch/print", {}),
    ("crisiswatch: wayback latest raw", "https://web.archive.org/web/2026id_/https://www.crisisgroup.org/crisiswatch", {"keep": "page"}),
    ("crisiswatch: wayback snapshots", cdx("crisisgroup.org/crisiswatch", limit=-40, collapse="digest"), {"keep": "cdx"}),
    ("crisiswatch: wayback url list", cdx("crisisgroup.org/crisiswatch*", limit=-300), {"keep": "cdx"}),
    ("crisiswatch: reliefweb rss", "https://reliefweb.int/updates/rss.xml?search=CrisisWatch", {"keep": "page"}),
    ("crisiswatch: archive.ph newest", "https://archive.ph/newest/https://www.crisisgroup.org/crisiswatch", {}),
    # Japan Coast Guard
    ("jcg: wayback url list", cdx("www1.kaiho.mlit.go.jp/TUHO/*", limit=-400), {"keep": "cdx"}),
    ("jcg: wayback TUHO raw", "https://web.archive.org/web/2026id_/https://www1.kaiho.mlit.go.jp/TUHO/", {"keep": "page"}),
    ("jcg: www1 root", "https://www1.kaiho.mlit.go.jp/", {}),
    ("jcg: main site", "https://www.kaiho.mlit.go.jp/", {}),
    ("jcg: english TUHO", "https://www1.kaiho.mlit.go.jp/TUHO/en/", {}),
    # China MSA
    ("msa: wayback url list", cdx("msa.gov.cn/page/*", limit=-400), {"keep": "cdx"}),
    ("msa: wayback weather.jsp raw", "https://web.archive.org/web/2026id_/https://www.msa.gov.cn/page/outter/weather.jsp", {"keep": "page"}),
    ("msa: home", "https://www.msa.gov.cn/", {"keep": "page"}),
    ("msa: mobile", "https://m.msa.gov.cn/", {}),
    # China Customs
    ("customs: english home", "http://english.customs.gov.cn/", {"keep": "page"}),
    ("customs: english statistics", "http://english.customs.gov.cn/statics/report/preliminary.html", {}),
    ("customs: wayback english url list", cdx("english.customs.gov.cn/statics/*", limit=-300), {"keep": "cdx"}),
    ("customs: stats indexEn", "http://stats.customs.gov.cn/indexEn", {}),
    ("customs: query platform ip", "http://43.248.49.97/indexEn", {}),
    ("customs: wayback stats url list", cdx("stats.customs.gov.cn/*", limit=-200), {"keep": "cdx"}),
    ("customs: www statistics page", "http://www.customs.gov.cn/customs/302249/zfxxgk/2799825/302274/index.html", {}),
    # Israel alerts: deeper history
    ("tzeva: alerts-history by id", "https://api.tzevaadom.co.il/alerts-history/id/7000", {}),
    ("oref mirror: dleshem israel-alerts-data", "https://api.github.com/repos/dleshem/israel-alerts-data/contents/", {"keep": "page"}),
]
KEEP = {"page": 4000, "cdx": 60000}


def tzeva_stats():
    import osint
    import sources as S
    g = S.get(osint.TZEVA_API, headers={"Accept": "application/json", "Referer": "https://www.tzevaadom.co.il/"})
    times = [a["time"] for x in g for a in x.get("alerts") or []]
    thr = collections.Counter(a.get("threat") for x in g for a in x.get("alerts") or [])
    waves = osint.parse_tzeva(g)
    fmt = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()
    return {"groups": len(g), "ids": [g[-1].get("id"), g[0].get("id")], "oldest": fmt(min(times)), "newest": fmt(max(times)),
            "threats": {str(k): v for k, v in thr.items()}, "hostile_waves": len(waves), "drills": sum(a.get("isDrill", False) for x in g for a in x.get("alerts") or [])}


def jetstream_test():
    import osint
    out = {}
    now = dt.datetime.now(dt.timezone.utc)
    for back_h in (0.25, 6, 20, 30):
        st = int((now - dt.timedelta(hours=back_h)).timestamp() * 1e6)
        t0 = time.time()
        try:
            posts = osint.jetstream_window(st, 60)
            n, hits = osint.bsky_tally(posts)
            out[f"{back_h}h ago"] = {"posts": len(posts), "english": n, "hits": hits, "secs": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            out[f"{back_h}h ago"] = {"error": str(e)[:200], "secs": round(time.time() - t0, 1)}
    return out


def nga_coverage():
    import sources as S
    rows = S.get("https://msi.nga.mil/api/publications/smaps?output=json&status=all")["smaps"]
    areas = collections.Counter(r.get("usNavArea") or r.get("navArea") for r in rows)
    words = {w: sum(1 for r in rows if re.search(w, r.get("msgText") or "")) for w in ("CHINA", "TAIWAN", "JAPAN", "DPRK|NORTH KOREA", "EAST CHINA SEA", "YELLOW SEA", "SOUTH CHINA SEA", "ROCKET|MISSILE")}
    return {"rows": len(rows), "areas": dict(areas), "mentions": words}


def comtrade_china():
    key = os.environ.get("COMTRADE_API_KEY", "")
    if not key:
        return {"error": "no COMTRADE_API_KEY"}
    import urllib.request
    out = {}
    for per in ("202606", "202607", "202608"):
        url = f"https://comtradeapi.un.org/data/v1/get/C/M/HS?reporterCode=156&period={per}&partnerCode=643&cmdCode=TOTAL&flowCode=X"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": key}), timeout=40) as r:
                d = json.loads(r.read())
            out[per] = [round(x.get("primaryValue") or 0) for x in d.get("data") or []]
        except Exception as e:  # noqa: BLE001
            out[per] = str(e).replace(key, "***")[:160]
    return out


def main(path):
    res = []
    for name, url, opts in ROUTES:
        r = P.fetch(url, opts)
        res.append(dict(r, name=name, url=url))
        print(f"{r.get('status', 'ERR')}\t{r.get('bytes', 0)}\t{name}\t{r.get('error', '')}", flush=True)
    for name, fn in (("tzeva stats", tzeva_stats), ("jetstream windows", jetstream_test), ("nga coverage", nga_coverage), ("comtrade china", comtrade_china)):
        try:
            v = fn()
        except Exception as e:  # noqa: BLE001
            v = {"error": str(e)[:300]}
        res.append({"name": name, "result": v})
        print(name, json.dumps(v)[:600], flush=True)
    with open(path, "w") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    P.DETAIL.update(KEEP)
    main(sys.argv[1] if len(sys.argv) > 1 else "probe/routes.json")
