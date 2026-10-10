import os, json, urllib.request
t = os.environ.get("UCDP_TOKEN", "")
print("token present", bool(t), len(t))
def g(path):
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://ucdpapi.pcr.uu.se/api/" + path, headers={"x-ucdp-access-token": t, "User-Agent": "warwatch"}), timeout=60)
        return r.status, json.loads(r.read())
    except Exception as e:
        return getattr(e, "code", "ERR"), (getattr(e, "read", lambda: str(e).encode())() or b"")[:200]
for v in ("26.1", "26.0.9", "26.0.8", "25.1"):
    st, d = g(f"gedevents/{v}?pagesize=1")
    if st == 200:
        print(v, st, {k: d[k] for k in d if k != "Result"}, json.dumps(d["Result"][0])[:700] if d.get("Result") else "")
    else:
        print(v, st, d)
for v in ("26.0.9", "26.1"):
    st, d = g(f"gedevents/{v}?pagesize=1000&StartDate=2026-08-01&EndDate=2026-12-31")
    if st == 200:
        dates = sorted(e["date_start"][:10] for e in d["Result"])
        print(v, "window", d.get("TotalCount"), dates[:1], dates[-1:])
    else: print(v, "window", st, d)
