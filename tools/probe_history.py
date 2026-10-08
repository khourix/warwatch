import os, sys, json, urllib.request, urllib.parse, collections, datetime as dt
sys.path.insert(0, "warwatch")
def get(url, headers=None, n=600, raw=False, method="GET"):
    r = urllib.request.Request(url, headers=dict({"User-Agent": "Mozilla/5.0 warwatch-probe"}, **(headers or {})), method=method)
    with urllib.request.urlopen(r, timeout=60) as f:
        b = f.read() if not raw else b""
        return f.status, dict(f.headers), b
def t(name):
    def deco(fn):
        print("=====", name, flush=True)
        try: fn()
        except Exception as e: print("ERR", repr(e)[:300], flush=True)
    return deco

@t("ukmto all")
def _():
    import osint, config as C
    rows = osint.ukmto_all()
    ds = sorted(str(r.get("utcDateOfIncident"))[:10] for r in rows)
    print(len(rows), ds[0], ds[-1])
    c = collections.Counter(x["th"] for x in osint.parse_ukmto(rows, days=100000))
    print(dict(c))

for d in ("2022-06-01", "2024-01-15", "2025-06-01", "2026-09-30"):
    @t("gpsjam " + d)
    def _():
        for host in ("https://gpsjam.org/data/%s-h3_4.csv" % d,):
            s, h, b = get(host)
            print(s, len(b), b[:200])
@t("gpsjam manifest")
def _():
    s, h, b = get("https://gpsjam.org/data/manifest.csv"); print(s, len(b), b[:300], b[-200:])

@t("adsb.lol globe_history releases")
def _():
    for repo in ("adsblol/globe_history_2025", "adsblol/globe_history_2026"):
        try:
            s, h, b = get("https://api.github.com/repos/%s/releases?per_page=3" % repo)
            for r in json.loads(b)[:3]:
                print(repo, r["tag_name"], [(a["name"], a["size"]) for a in r["assets"]][:4])
        except Exception as e: print(repo, "ERR", repr(e)[:150])

@t("wayback state advisories")
def _():
    u = "https://web.archive.org/cdx/search/cdx?url=cadataapi.state.gov/api/TravelAdvisories&output=json&limit=20&from=2023"
    s, h, b = get(u); print(s, b[:600])
    u = "https://web.archive.org/cdx/search/cdx?url=travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html&output=json&limit=5&from=2023&fl=timestamp,statuscode,length&collapse=timestamp:6"
    s, h, b = get(u); print(s, b[:900])

@t("pizzint endpoints")
def _():
    for u in ("https://www.pizzint.watch/api/dashboard-data", "https://www.pizzint.watch/api/history", "https://www.pizzint.watch/api/gdelt/latest",
              "https://www.pizzint.watch/api/dashboard-data?history=1", "https://www.pizzint.watch/"):
        try:
            s, h, b = get(u); print(u, s, len(b), b[:300].decode("utf-8", "replace").replace("\n", " "))
        except Exception as e: print(u, "ERR", repr(e)[:120])

@t("firms deep window")
def _():
    import osint, config as C
    key = os.environ.get("FIRMS_MAP_KEY", "")
    for start in ("2025-06-01", "2024-06-01", "2023-06-01"):
        try:
            tx = osint.S.get(osint.firms_url(key, C.FIRMS_BOX["iran"], 5, start), raw=True, retries=1, wait=2)
            tx = tx.decode("utf-8", "replace") if isinstance(tx, bytes) else tx
            print(start, len(osint.parse_firms(tx)), tx[:80].replace("\n", " | "))
        except Exception as e: print(start, "ERR", repr(e)[:150])

@t("czib list shape")
def _():
    import extras
    z = extras.fetch_czib(); print(len(z), z[:2])

@t("nga history")
def _():
    s, h, b = get("https://msi.nga.mil/api/publications/broadcast-warn?output=json&status=inactive&navArea=P")
    d = json.loads(b); x = d.get("broadcast-warn", []); print(s, len(x), x[:1])
