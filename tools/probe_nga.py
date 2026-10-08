import json, collections, urllib.request
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "application/json,*/*"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60) as f:
        return json.loads(f.read())
B = "https://msi.nga.mil/api/publications/smaps?output=json"
for q in ("", "&status=cancelled", "&status=inforce", "&status=all", "&status=active,cancelled"):
    try:
        L = get(B + q)["smaps"]
    except Exception as e:
        print(repr(q), "ERR", repr(e)[:100]); continue
    yrs = collections.Counter((x.get("createdOn") or "")[-4:] for x in L)
    mons = collections.Counter(((x.get("createdOn") or "")[-8:]) for x in L if (x.get("createdOn") or "").endswith(("2026", "2025")))
    st = collections.Counter(x.get("status") for x in L)
    print(repr(q), len(L), "years", dict(sorted(yrs.items())), "status", dict(st))
    print("   months", dict(sorted(mons.items())[:40]))
    print("   keys", sorted(L[0].keys()) if L else "")
    if L:
        c = [x for x in L if x.get("cancelledOn")]
        print("   cancelledOn sample", [x.get("cancelledOn") for x in c[:3]], "lat/lon null share", sum(1 for x in L if x.get("latitude") is None) / len(L))
