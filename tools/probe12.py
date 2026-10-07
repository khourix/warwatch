import urllib.request
UA = {"User-Agent": "Mozilla/5.0"}
for d in ["2026-08-26","2026-08-20","2026-07-01","2026-01-01","2025-10-05","2024-01-01","2022-03-01"]:
    for suf in ("h3_4", "h3_5"):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"https://gpsjam.org/data/{d}-{suf}.csv", headers=UA), timeout=60)
            print(d, suf, r.status, len(r.read()))
        except Exception as e:
            print(d, suf, "ERR", str(e)[:80])
