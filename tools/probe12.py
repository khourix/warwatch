import os, json, base64, gzip, urllib.request, urllib.parse, collections
i = os.environ["FAA_CLIENT_ID"].strip(); s = os.environ["FAA_CLIENT_SECRET"].strip()
B = base64.b64encode(f"{i}:{s}".encode()).decode()
host = "https://api-staging.cgifederal-aim.com"
r = urllib.request.urlopen(urllib.request.Request(host + "/v1/auth/token", data=b"grant_type=client_credentials", headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": "Basic " + B}), timeout=60)
tok = json.loads(r.read())["access_token"]
r = urllib.request.urlopen(urllib.request.Request(host + "/nmsapi/v1/notams?classification=INTERNATIONAL", headers={"Authorization": "Bearer " + tok, "nmsResponseFormat": "GEOJSON"}), timeout=180)
raw = gzip.decompress(r.read())
print("bytes", len(raw), raw[:150])
d = json.loads(raw)
print(type(d).__name__, list(d)[:10] if isinstance(d, dict) else len(d))
def find(o):
    if isinstance(o, list) and o and isinstance(o[0], dict) and "properties" in o[0]: return o
    if isinstance(o, dict):
        for v in o.values():
            x = find(v)
            if x: return x
items = find(d) or []
print("items", len(items))
c = collections.Counter(f["properties"]["coreNOTAMData"]["notam"].get("affectedFir") for f in items)
print({k: c.get(k) for k in ["UKBV","UKLV","UKOV","UKDV","OIIX","LLLL","OSTT","ORBB","OLBB","RCAA","RKRR","ZKKP","HLLL","HSSS","FZZA","SVZM","OYSC","OPKR","VIDF","EPWW","UMMV"]})
print("top", c.most_common(8))
