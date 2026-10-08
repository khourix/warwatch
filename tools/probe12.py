import os, json, base64, urllib.request, urllib.parse
i = os.environ["FAA_CLIENT_ID"].strip(); s = os.environ["FAA_CLIENT_SECRET"].strip()
B = base64.b64encode(f"{i}:{s}".encode()).decode()
host = "https://api-nms.aim.faa.gov"
try:
    r = urllib.request.urlopen(urllib.request.Request(host + "/v1/auth/token", data=b"grant_type=client_credentials", headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": "Basic " + B}), timeout=60)
    tok = json.loads(r.read())["access_token"]; print("PROD TOKEN OK")
    r = urllib.request.urlopen(urllib.request.Request(host + "/nmsapi/v1/notams?" + urllib.parse.urlencode({"location": "OIIX"}), headers={"Authorization": "Bearer " + tok, "nmsResponseFormat": "GEOJSON"}), timeout=60)
    print("notams", r.status, len(json.loads(r.read())["data"]["geojson"]))
except Exception as e:
    print("PROD FAIL", e, getattr(e, "read", lambda: b"")()[:200])
