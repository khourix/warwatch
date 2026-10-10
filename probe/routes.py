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


PAGES = [   # pages that open from GitHub: list their links to find the warning and statistics pages behind them
    ("jcg www1 root", "https://www1.kaiho.mlit.go.jp/", r"TUHO|keiho|navarea|NAV|航行|警報|nav"),
    ("jcg main", "https://www.kaiho.mlit.go.jp/", r"TUHO|keiho|navarea|航行|警報|nav"),
    ("msa home", "https://www.msa.gov.cn/", r"航行|警告|通告|channel|article|\.do|\.jsp"),
    ("customs monthly", "http://english.customs.gov.cn/statics/report/monthly.html", r"Statics|statics|report|\.html"),
    ("customs preliminary", "http://english.customs.gov.cn/statics/report/preliminary.html", r"Statics|statics|report|\.html"),
    ("crisis group rss", "https://www.crisisgroup.org/rss.xml", None),
    ("crisis group rss short", "https://www.crisisgroup.org/rss", None),
]


def links(name, url, pat):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": P.UA, "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read(3_000_000)
    for enc in ("utf-8", "gb18030", "shift_jis"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if pat is None:   # an RSS feed: titles, links and dates
        items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?(?:<pubDate>(.*?)</pubDate>)?", text, re.S)
        return {"bytes": len(raw), "items": len(items), "first": items[:25], "crisiswatch": [i for i in items if re.search("crisiswatch", i[0] + i[1], re.I)][:25]}
    found = []
    for href, label in re.findall(r"""<a[^>]+href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", text, re.S | re.I):
        label = re.sub(r"<[^>]+>|\s+", " ", label).strip()[:60]
        if re.search(pat, href + " " + label):
            found.append([urllib.parse.urljoin(url, href), label])
    scripts = [m for m in re.findall(r"""["']([^"']*\.(?:do|jsp|json)[^"']*)["']""", text)][:60]
    return {"bytes": len(raw), "links": found[:150], "endpoints": scripts}


EXCERPTS = [   # round 3: text around the words that mark the data, plus scripts and links
    ("jcg navarea11", "https://www1.kaiho.mlit.go.jp/TUHO/keiho/navarea11.html", r"NAVAREA|ミサイル|ロケット|射撃|訓練|warning|\.html|\.txt|\.pdf"),
    ("jcg tuho2", "https://www1.kaiho.mlit.go.jp/TUHO/tuho2.html", r"航行警報|NAVAREA|\.html"),
    ("msa home text", "https://www.msa.gov.cn/", r"航行警告|航行通告|警告|jhtml"),
    ("customs preliminary text", "http://english.customs.gov.cn/statics/report/preliminary.html", r"2026|Statics|\.js|ajax|url"),
    ("customs monthly text", "http://english.customs.gov.cn/statics/report/monthly.html", r"2026|Statics|\.js|ajax|url"),
    ("crisiswatch rss item", "https://www.crisisgroup.org/rss.xml", r"Deteriorat|Conflict Risk|Resolution Opportunit|Improved Situation|CrisisWatch"),
]


def excerpts(url, pat, n=40, width=220):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": P.UA, "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw, final = r.read(3_000_000), r.geturl()
    text = raw.decode("utf-8", "replace")
    if text.count("\ufffd") > 50:
        text = raw.decode("gb18030", "replace") if "msa" in url or "customs" in url else raw.decode("shift_jis", "replace")
    out, last = [], -10_000
    for m in re.finditer(pat, text, re.I):
        if m.start() - last < width:
            continue
        last = m.start()
        out.append(re.sub(r"\s+", " ", text[max(0, m.start() - width // 2): m.start() + width]))
        if len(out) >= n:
            break
    scripts = re.findall(r"""<script[^>]+src=["']([^"']+)""", text, re.I)[:30]
    return {"bytes": len(raw), "final_url": final, "hits": out, "scripts": scripts}


def tzeva_ids():
    import sources as S
    out = {}
    for i in (1, 100, 1000, 3000, 5000, 6000, 6500, 7500):
        try:
            g = S.get(f"https://api.tzevaadom.co.il/alerts-history/id/{i}", retries=1)
            out[i] = dt.datetime.fromtimestamp(min(a["time"] for a in g["alerts"]), dt.timezone.utc).isoformat()[:16] if g.get("alerts") else "no alerts"
        except Exception as e:  # noqa: BLE001
            out[i] = str(e)[:80]
        time.sleep(1)
    return out


def oref_csv_ends():
    import urllib.request
    url = "https://raw.githubusercontent.com/dleshem/israel-alerts-data/main/israel-alerts.csv"
    out = {}
    for name, rng in (("head", "bytes=0-1500"), ("tail", "bytes=-1500")):
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": rng, "User-Agent": P.UA}), timeout=40) as r:
            out[name] = r.read().decode("utf-8", "replace")
    readme = urllib.request.urlopen("https://raw.githubusercontent.com/dleshem/israel-alerts-data/main/README.md", timeout=40).read().decode()
    lic = urllib.request.urlopen("https://raw.githubusercontent.com/dleshem/israel-alerts-data/main/LICENSE", timeout=40).read(300).decode()
    out.update(readme=readme, license=lic)
    return out


def fetch_text(url, enc="utf-8"):
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": P.UA, "Accept-Language": "en-US,en;q=0.8"}), timeout=60) as r:
        return r.read(5_000_000).decode(enc, "replace")


def crisiswatch_lists():
    import html as H
    text = H.unescape(fetch_text("https://www.crisisgroup.org/rss.xml"))
    m = re.search(r"<item>\s*<title>([^<]*Trends and [^<]*Alerts[^<]*)</title>.*?</item>", text, re.S)
    body = m.group(0)
    out = {"title": m.group(1), "bytes": len(body)}
    for head in ("Conflict Risk Alerts", "Resolution Opportunities", "Deteriorated Situations", "Improved Situations"):
        k = body.find(head + "</h4>")
        if k < 0:
            out[head] = "not found"
            continue
        seg = body[k: k + 6000]
        seg = seg[: seg.find("</h4>", len(head) + 6) if seg.find("</h4>", len(head) + 6) > 0 else 6000]
        out[head] = [re.sub(r"\s+", " ", x).strip() for x in re.findall(r"<a[^>]*>(.*?)</a>", seg, re.S)][:40]
        out[head + " raw"] = re.sub(r"\s+", " ", seg)[:700]
    return out


def jcg_scripts():
    out = {}
    for f in ("warnings.js", "AjaxLib.js"):
        t = fetch_text("https://www1.kaiho.mlit.go.jp/TUHO/keiho/js/" + f, "shift_jis")
        out[f] = {"bytes": len(t), "cgi": sorted(set(re.findall(r"[\w/.-]*\.cgi[^\"' ]*", t)))[:30], "text": t[:5000]}
    return out


def customs_country_table():
    page = fetch_text("http://english.customs.gov.cn/statics/report/monthly.html")
    row = re.search(r"Imports and Exports by Country.*?</tr>", page, re.S).group(0)
    links = re.findall(r"href=(http[^ >]+)>\s*(\w+)\.", row)
    url, mon = links[-1]
    t = fetch_text(url)
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", t))
    rus = plain.find("Russia")
    return {"months": [m for _, m in links], "latest": url, "bytes": len(t), "head": plain[:1500], "russia": plain[max(0, rus - 300): rus + 600],
            "links_in_page": re.findall(r"href=[\"']?([^\"' >]+\.(?:xls|xlsx|pdf|csv))", t)[:10]}


def round4():
    out = []
    for name, fn in (("crisiswatch lists", crisiswatch_lists), ("jcg scripts", jcg_scripts), ("customs by country", customs_country_table)):
        try:
            v = fn()
        except Exception as e:  # noqa: BLE001
            v = {"error": f"{type(e).__name__}: {e}"[:300]}
        out.append({"name": name, "result": v})
        print(name, json.dumps(v, ensure_ascii=False)[:500], flush=True)
    return out


def post(url, data, enc="utf-8"):
    import urllib.request
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"User-Agent": P.UA, "Content-Type": "application/x-www-form-urlencoded",
                                                                                          "Referer": "https://www1.kaiho.mlit.go.jp/TUHO/keiho/navarea11.html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(3_000_000).decode(enc, "replace")


def jcg_cgi():
    out = {}
    cgi = "https://www1.kaiho.mlit.go.jp/TUHO/keiho/cgi/"
    for lang in ("EN", "JP"):
        try:
            x = post(cgi + "warnings.cgi", {"YEAR": "2026", "TYPE": "NAVAREA11", "LANG": lang})
            out["list " + lang] = {"bytes": len(x), "head": x[:2500]}
        except Exception as e:  # noqa: BLE001
            out["list " + lang] = str(e)[:200]
    tanas = re.findall(r"<tana>(.*?)</tana>", out.get("list EN", {}).get("head", "") if isinstance(out.get("list EN"), dict) else "")
    if tanas:
        try:
            t = post(cgi + "disp_warnings.cgi", {"TYPE": "NAVAREA11", "TANA": ":".join(tanas[:5]) + ":", "LANG": "EN"})
            out["text"] = {"bytes": len(t), "plain": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:3000]}
        except Exception as e:  # noqa: BLE001
            out["text"] = str(e)[:200]
    for page in ("navtex.html", "japan_nw.html", "local_nw.html", "backnumber.html"):
        try:
            t = fetch_text("https://www1.kaiho.mlit.go.jp/TUHO/keiho/" + page, "shift_jis")
            out[page] = re.findall(r"var (?:type|vtype|cgidir) = \"([^\"]*)\"", t) + [len(t)]
        except Exception as e:  # noqa: BLE001
            out[page] = str(e)[:120]
    return out


def msa_more():
    out = {}
    for name, url in (("wap", "https://www.msa.gov.cn/msacncms_wap/index.jhtml"),
                      ("cdx outter", cdx("www.msa.gov.cn/page/outter*", limit=200)),
                      ("cdx wap", cdx("www.msa.gov.cn/msacncms_wap*", limit=200)),
                      ("cdx hxjg", cdx("msa.gov.cn", limit=200, matchType="domain", filter="original:.*(hxjg|hxtg|navigat|warning|jinggao).*"))):
        try:
            t = fetch_text(url)
            hits = [re.sub(r"\s+", " ", t[max(0, m.start() - 150): m.start() + 200]) for m in re.finditer("航行警告|航行通告|航警", t)][:15]
            out[name] = {"bytes": len(t), "hits": hits, "head": t[:3000] if "cdx" in name else ""}
        except Exception as e:  # noqa: BLE001
            out[name] = str(e)[:200]
    return out


def customs_more():
    out = {}
    js = fetch_text("http://english.customs.gov.cn/Scripts/statistic.js")
    out["statistic.js"] = js[:4000]
    return out


def round6():
    out = {}
    cgi = "https://www1.kaiho.mlit.go.jp/TUHO/keiho/cgi/"
    x = post(cgi + "warnings.cgi", {"YEAR": "2026", "TYPE": "JAPANNW", "LANG": "JP"})
    out["japannw list"] = {"bytes": len(x), "titles": re.findall(r"<title>(.*?)</title>", x)[:60]}
    x = post(cgi + "warnings.cgi", {"YEAR": "2026", "TYPE": "NAVAREA11", "LANG": "JP"})
    out["navarea11 titles"] = list(zip(re.findall(r"<categoly>(.*?)</categoly>", x), re.findall(r"<title>(.*?)</title>", x)))[:120]
    tanas = re.findall(r"<tana>(.*?)</tana>", x)
    for lang in ("JP", "EN"):
        try:
            t = post(cgi + "disp_warnings.cgi", {"TYPE": "NAVAREA11", "TANA": ":".join(tanas[:3]) + ":", "LANG": lang})
            out["text " + lang] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:2500]
        except Exception as e:  # noqa: BLE001
            out["text " + lang] = str(e)[:200]
    for yr in ("2025",):
        x = post(cgi + "warnings.cgi", {"YEAR": yr, "TYPE": "NAVAREA11", "LANG": "JP"})
        out["navarea11 " + yr] = len(re.findall("<Member>", x))
    try:
        t = fetch_text("https://www.msa.gov.cn/msacncms_wap/pages/info_warn.jhtml?channelId=9c219298b27f460e995a99401b3ff6af")
        out["msa warn page"] = {"bytes": len(t), "ajax": re.findall(r"""(?:url|\$\.(?:post|get|ajax))\s*[:(]\s*["']([^"']+)""", t)[:20],
                                "text": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", t, flags=re.S)))[:2500],
                                "scripts": re.findall(r"<script[^>]*>(.*?)</script>", t, re.S)[-3:]}
    except Exception as e:  # noqa: BLE001
        out["msa warn page"] = str(e)[:200]
    return out


def round7():
    out = {}
    page = fetch_text("https://www.msa.gov.cn/msacncms_wap/pages/info_warn.jhtml?channelId=9c219298b27f460e995a99401b3ff6af")
    srcs = re.findall(r"""<script[^>]+src=["']([^"']+)""", page)
    out["msa scripts"] = srcs
    for src in srcs:
        u = urllib.parse.urljoin("https://www.msa.gov.cn/msacncms_wap/pages/", src)
        try:
            js = fetch_text(u)
        except Exception as e:  # noqa: BLE001
            continue
        if "selectPageByChannelId" in js or "baseUrl" in js or "article" in js:
            k = js.find("selectPageByChannelId")
            out["msa js " + src] = {"around": js[max(0, k - 1500): k + 500] if k >= 0 else "", "base": re.findall(r"(?:baseUrl|BASE|ctx|basePath)\s*[:=]\s*['\"]([^'\"]+)", js)[:5]}
    page = fetch_text("http://english.customs.gov.cn/statics/report/monthly.html")
    out["customs years in page"] = len(re.findall(r"Imports and Exports by Country", page))
    out["customs select"] = re.findall(r"<select.*?</select>", page, re.S)[:2]
    out["customs year blocks"] = re.findall(r"""id=["'](\w*20\d\d\w*)["']""", page)[:20]
    row = re.search(r"Imports and Exports by Country.*?</tr>", page, re.S).group(0)
    url = re.findall(r"href=(http[^ >]+)>", row)[-1]
    t = fetch_text(url)
    tab = t[t.find("<table"):]
    out["customs table head"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", tab))[:2500]
    for c in ("Iran", "Korea, DPR", "Democratic People", "Belarus", "Israel"):
        k = tab.find(c)
        out["row " + c] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", tab[k: k + 900])) if k >= 0 else "absent"
    return out


def main(path):
    res = []
    if os.environ.get("ROUTES_ROUND") == "7":
        try:
            v = round7()
        except Exception as e:  # noqa: BLE001
            v = {"error": f"{type(e).__name__}: {e}"[:300]}
        print(json.dumps(v, ensure_ascii=False)[:800])
        with open(path, "w") as f:
            json.dump(v, f, indent=1, ensure_ascii=False)
        return
    if os.environ.get("ROUTES_ROUND") == "6":
        try:
            v = round6()
        except Exception as e:  # noqa: BLE001
            v = {"error": f"{type(e).__name__}: {e}"[:300]}
        print(json.dumps(v, ensure_ascii=False)[:800])
        with open(path, "w") as f:
            json.dump(v, f, indent=1, ensure_ascii=False)
        return
    if os.environ.get("ROUTES_ROUND") == "5":
        for name, fn in (("jcg cgi", jcg_cgi), ("msa more", msa_more), ("customs more", customs_more)):
            try:
                v = fn()
            except Exception as e:  # noqa: BLE001
                v = {"error": f"{type(e).__name__}: {e}"[:300]}
            res.append({"name": name, "result": v})
            print(name, json.dumps(v, ensure_ascii=False)[:500], flush=True)
        with open(path, "w") as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
        return
    if os.environ.get("ROUTES_ROUND") == "4":
        with open(path, "w") as f:
            json.dump(round4(), f, indent=1, ensure_ascii=False)
        return
    if os.environ.get("ROUTES_ROUND") == "3":
        for name, url, pat in EXCERPTS:
            try:
                v = excerpts(url, pat)
            except Exception as e:  # noqa: BLE001
                v = {"error": str(e)[:300]}
            res.append({"name": name, "url": url, "result": v})
            print(name, json.dumps(v, ensure_ascii=False)[:300], flush=True)
        for name, fn in (("tzeva ids", tzeva_ids), ("oref csv", oref_csv_ends)):
            try:
                v = fn()
            except Exception as e:  # noqa: BLE001
                v = {"error": str(e)[:300]}
            res.append({"name": name, "result": v})
            print(name, json.dumps(v, ensure_ascii=False)[:300], flush=True)
        with open(path, "w") as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
        return
    if os.environ.get("ROUTES_ROUND") == "2":
        for name, url, pat in PAGES:
            try:
                v = links(name, url, pat)
            except Exception as e:  # noqa: BLE001
                v = {"error": str(e)[:300]}
            res.append({"name": name, "url": url, "result": v})
            print(name, json.dumps(v, ensure_ascii=False)[:400], flush=True)
        with open(path, "w") as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
        return
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
