import json, re, urllib.request, urllib.parse, collections
def get(url, headers=None, n=400):
    r = urllib.request.Request(url, headers=dict({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "*/*"}, **(headers or {})))
    with urllib.request.urlopen(r, timeout=60) as f:
        return f.status, f.headers.get("content-type"), f.read()
def t(name):
    def deco(fn):
        print("=====", name, flush=True)
        try: fn()
        except Exception as e: print("ERR", repr(e)[:250], flush=True)
    return deco
B = "https://msi.nga.mil/api/publications/broadcast-warn?"
for q in ("output=json&status=active", "output=json&status=A", "output=json", "output=json&status=active&navArea=4", "output=json&status=active&navArea=A",
          "output=json&status=active&navArea=P", "output=json&status=active&navArea=12", "output=json&status=active&navArea=C", "output=json&status=active&navArea=I",
          "output=json&status=active&navArea=1&msgYear=2026", "output=json&msgYear=2026", "output=json&msgYear=2025&navArea=4"):
    @t("nga " + q)
    def _():
        s, c, b = get(B + q)
        d = json.loads(b); x = d.get("broadcast-warn", [])
        ys = collections.Counter(str(w.get("issueDate", ""))[-4:] for w in x)
        print(s, len(x), dict(ys), [ (w.get("navArea"), w.get("msgYear"), w.get("msgNumber"), w.get("issueDate")) for w in x[:2]])
for u in ("https://msi.nga.mil/NavWarnings", "https://msi.nga.mil/api/publications/download?type=view&key=16920959/SFH00000/DailyMemII.txt",
          "https://msi.nga.mil/api/publications/broadcast-warn/latest", "https://msi.nga.mil/api/swagger.json", "https://msi.nga.mil/api/publications/ntm?output=json"):
    @t(u)
    def _():
        s, c, b = get(u); print(s, c, len(b), b[:300].decode("utf-8", "replace").replace("\n", " "))
for u in ("https://www.maritime.dot.gov/msci-advisories", "https://www.maritime.dot.gov/msci/2025-001", "https://www.maritime.dot.gov/msci/rss.xml", "https://www.maritime.dot.gov/rss-feed",
          "https://www.sealagom.com/", "https://www.sealagom.com/robots.txt", "https://www.navcen.uscg.gov/maritime-safety-information",
          "https://api.worldmonitor.app/api/maritime/v1/list-navigational-warnings", "https://www.worldmonitor.app/"):
    @t(u)
    def _():
        s, c, b = get(u); print(s, c, len(b), b[:300].decode("utf-8", "replace").replace("\n", " "))
