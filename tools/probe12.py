import os, json, base64, urllib.request, urllib.parse
i = os.environ["FAA_CLIENT_ID"].strip(); s = os.environ["FAA_CLIENT_SECRET"].strip()
B = base64.b64encode(f"{i}:{s}".encode()).decode()
def call(url, h, data=None):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=40)
        return r.status, r.read()
    except Exception as e:
        return getattr(e, "code", "ERR"), (getattr(e, "read", lambda: str(e).encode())() or b"")[:300]
tok = None
for host in ("https://api-staging.cgifederal-aim.com/nmsapi/v1/auth/token", "https://api-staging.cgifederal-aim.com/v1/auth/token"):
    st, b = call(host, {"Content-Type": "application/x-www-form-urlencoded", "Authorization": "Basic " + B}, b"grant_type=client_credentials")
    print("token", host, st, b[:120] if st != 200 else "ok keys=" + str(list(json.loads(b))))
    if st == 200:
        tok = json.loads(b)["access_token"]; base = host.rsplit("/auth/token", 1)[0]; break
if tok:
    H = {"Authorization": "Bearer " + tok, "nmsResponseFormat": "GEOJSON"}
    for q in ({"location": "JFK"}, {"classification": "INTERNATIONAL", "location": "UKBV"},
              {"latitude": 50.45, "longitude": 30.5, "radius": 100},
              {"feature": "AIRSPACE", "latitude": 48.0, "longitude": 11.0, "radius": 100}):
        st, b = call(base + "/notams?" + urllib.parse.urlencode(q), H)
        n = "?"
        try:
            d = json.loads(b if st == 200 else b"{}"); n = len(d["data"].get("geojson", []))
        except Exception: pass
        print(q, st, "items", n, b[:200] if st != 200 else "")
    st, b = call(base + "/notams/checklist?" + urllib.parse.urlencode({"classification": "INTERNATIONAL"}), H)
    print("checklist", st, len(b) if st == 200 else b)
