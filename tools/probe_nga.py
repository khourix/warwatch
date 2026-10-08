import json, re, urllib.request, urllib.parse
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "application/json,text/html,*/*"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=15) as f:
        return f.status, f.headers.get("content-type"), f.read()
site = "https://msi.nga.mil/"
html = get(site + "NavWarnings")[2].decode("utf-8", "replace")
api = set(); asam = set()
for src in re.findall(r'<script[^>]+src="([^"]+)"', html):
    js = get(urllib.parse.urljoin(site, src))[2].decode("utf-8", "replace")
    api |= set(re.findall(r'["\'`](/?api/[A-Za-z0-9_/\-\.]{2,60})', js))
    for m in re.finditer(r'.{0,80}asam.{0,100}', js, re.I): asam.add(m.group(0))
print("API", sorted(api)); print("ASAM", sorted(asam)[:12], flush=True)
for p in ("api/publications/asam?output=json", "api/publications/asam", "api/publications/asam/list?output=json", "api/publications/anti-shipping-activity-messages?output=json",
          "api/publications/odnr?output=json", "api/publications/broadcast-warn?output=json&status=active&navArea=4&msgYear=2026",
          "api/publications/broadcast-warn/current-warnings", "api/publications/ntm/pubs?output=json&limit=1", "api/publications/smaps?output=json"):
    print("=====", p, flush=True)
    try:
        s, c, b = get(site + p); t = b.decode("utf-8", "replace"); print(s, c, len(t), t[:400].replace("\n", " "))
    except Exception as e: print("ERR", repr(e)[:120])
