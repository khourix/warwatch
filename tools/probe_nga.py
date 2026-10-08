import json, re, urllib.request, urllib.parse, collections
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "application/json,*/*"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as f:
        return f.status, f.read()
B = "https://msi.nga.mil/api/publications/smaps"
s, b = get(B + "?output=json")
d = json.loads(b); L = d["smaps"]
print("n", len(L), "keys", list(L[0].keys()))
print("SAMPLE", json.dumps(L[0], indent=1)[:2500])
for k in ("category", "usNavArea", "navArea", "dncRegion", "oceans", "status", "msgType", "msgStatus"):
    if k in L[0]: print(k, collections.Counter(str(x.get(k)) for x in L).most_common(14))
dts = sorted(str(x.get("ingestDate") or "") for x in L); print("ingest", dts[0], dts[-1])
cr = sorted(x.get("createdOn") or "" for x in L); print("created sample", cr[:2], cr[-2:])
yrs = collections.Counter((x.get("createdOn") or "")[-4:] for x in L); print("created years", dict(yrs))
cats = [x for x in L if x.get("category") and "FIR" in x["category"].upper() or "MISSILE" in x["category"].upper() or "GUNNERY" in x["category"].upper()]
print("hazard-ish", len(cats))
for x in L[:3]: print("TEXT", json.dumps({k: x[k] for k in x if k in ("category", "title", "text", "msgText", "message", "navArea", "usNavArea", "createdOn", "cancelledOn")})[:700])
for q in ("?output=json&status=active", "?output=json&navArea=A", "?output=json&category=GUNNERY", "?output=json&year=2025", "?output=json&usNavArea=HYDROPAC", "?output=json&status=cancelled"):
    try:
        s, b = get(B + q); n = len(json.loads(b)["smaps"]); print(q, s, n)
    except Exception as e: print(q, "ERR", repr(e)[:100])
