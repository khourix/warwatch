import os, json, urllib.request
i = os.environ.get("FAA_CLIENT_ID", ""); s = os.environ.get("FAA_CLIENT_SECRET", "")
print("len", len(i), len(s), "id shape", i[:2] + "..." + i[-2:], "ws", i != i.strip(), s != s.strip(), "hex", all(c in "0123456789abcdef" for c in i.lower()))
def t(url, h):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40)
        print(url[:80], list(h)[:2], r.status, r.read()[:200])
    except Exception as e:
        print(url[:80], list(h)[:2], "ERR", e, getattr(e, "read", lambda: b"")()[:200], dict(getattr(e, "headers", {}) or {}).get("WWW-Authenticate"))
base = "https://external-api.faa.gov/notamapi/v1/notams?icaoLocation=KJFK&pageSize=1"
t(base, {"client_id": i.strip(), "client_secret": s.strip()})
t(base, {"Client_Id": i.strip(), "Client_Secret": s.strip(), "Accept": "application/json"})
t(base + "&responseFormat=aixmJson", {"client_id": i.strip(), "client_secret": s.strip()})
t(base.replace("external-api.faa.gov", "api.faa.gov"), {"client_id": i.strip(), "client_secret": s.strip()})
t(base + "&client_id=" + i.strip() + "&client_secret=" + s.strip(), {})
