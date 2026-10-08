import os, json, base64, urllib.request, urllib.parse
i = os.environ["FAA_CLIENT_ID"].strip(); s = os.environ["FAA_CLIENT_SECRET"].strip()
B = base64.b64encode(f"{i}:{s}".encode()).decode()
def call(url, h, data=None):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=120)
        return r.status, r.read(), r.geturl()
    except Exception as e:
        return getattr(e, "code", "ERR"), (getattr(e, "read", lambda: str(e).encode())() or b"")[:300], ""
for host in ("https://api-nms.aim.faa.gov", "https://api-staging.cgifederal-aim.com"):
    st, b, _ = call(host + "/v1/auth/token", {"Content-Type": "application/x-www-form-urlencoded", "Authorization": "Basic " + B}, b"grant_type=client_credentials")
    print(host, "token", st, b[:100] if st != 200 else "ok")
    if st != 200: continue
    tok = json.loads(b)["access_token"]
    H = {"Authorization": "Bearer " + tok, "nmsResponseFormat": "GEOJSON"}
    for ac in ("false", None):
        q = {"classification": "INTERNATIONAL"}
        if ac: q["allowRedirect"] = ac
        st, b, final = call(host + "/nmsapi/v1/notams?" + urllib.parse.urlencode(q), H)
        print(" bulk", q, st, len(b), final[:90], b[:200] if len(b) < 2000 or st != 200 else "")
        if st == 200 and len(b) > 2000:
            try:
                d = json.loads(b); print("  parsed keys", list(d), list(d.get("data", {})) if isinstance(d, dict) else "", "n", len(d.get("data", {}).get("geojson", [])))
            except Exception as e: print("  not json", e, b[:100])
