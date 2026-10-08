import json, re, urllib.request, urllib.parse, collections
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "application/json,*/*"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as f:
        return f.status, f.headers.get("content-type"), f.read()
B = "https://msi.nga.mil/api/publications/broadcast-warn/"
for q in ("current-warnings", "current-warnings?output=json", "current-warnings?navArea=4&output=json", "current-warnings?navArea=P&output=json",
          "latest-warning", "latest-warning?output=json", "subregions", "subregions?output=json&navArea=4"):
    print("=====", q, flush=True)
    try:
        s, c, b = get(B + q); t = b.decode("utf-8", "replace")
        print(s, c, len(t), t[:500].replace("\n", " "))
        try:
            d = json.loads(t)
            L = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
            ys = collections.Counter(str(w.get("issueDate", ""))[-4:] for w in L if isinstance(w, dict))
            print("n", len(L), dict(ys), "keys", list(d.keys())[:8] if isinstance(d, dict) else "")
        except Exception as e: print("not json", repr(e)[:60])
    except Exception as e: print("ERR", repr(e)[:200])
