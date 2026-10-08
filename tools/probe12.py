import os, json, urllib.request, urllib.parse
H = {"client_id": os.environ.get("FAA_CLIENT_ID", ""), "client_secret": os.environ.get("FAA_CLIENT_SECRET", ""), "User-Agent": "warwatch"}
print("creds present", bool(H["client_id"]), bool(H["client_secret"]))
def get(q):
    u = "https://external-api.faa.gov/notamapi/v1/notams?" + urllib.parse.urlencode(q)
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40)
        d = json.loads(r.read())
        print(q, "->", r.status, {k: d[k] for k in d if k != "items"}, "items", len(d.get("items", [])))
        for it in d.get("items", [])[:2]:
            print(json.dumps(it)[:600])
    except Exception as e:
        body = getattr(e, "read", lambda: b"")()[:300]
        print(q, "ERR", e, body)
get({"icaoLocation": "KJFK", "pageSize": 5})
get({"icaoLocation": "UKBV", "pageSize": 5})
get({"icaoLocation": "OIIX", "pageSize": 5})
get({"icaoLocation": "UKLV", "pageSize": 5})
get({"locationLatitude": 50.45, "locationLongitude": 30.5, "locationRadius": 100, "pageSize": 5})
get({"icaoLocation": "OIIX", "pageSize": 1000, "pageNum": 1})
