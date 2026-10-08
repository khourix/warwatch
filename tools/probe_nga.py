import json, re, urllib.request, urllib.parse, collections
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "*/*"}
def get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=dict(H, **(headers or {}))), timeout=60) as f:
        return f.status, f.headers.get("content-type"), f.read()
s, c, b = get("https://msi.nga.mil/NavWarnings")
html = b.decode("utf-8", "replace")
print(re.findall(r'<script[^>]+src="([^"]+)"', html))
for src in re.findall(r'<script[^>]+src="([^"]+)"', html):
    u = urllib.parse.urljoin("https://msi.nga.mil/NavWarnings", src)
    try:
        s, c, b = get(u); js = b.decode("utf-8", "replace")
        print("JS", u, len(js))
        for m in sorted(set(re.findall(r'["\'`](/?api/[A-Za-z0-9_/\-\.\?=&{}\$]*)["\'`]', js)))[:60]: print("  api:", m)
        for m in sorted(set(re.findall(r'(?:broadcast|warn|navwarn)[A-Za-z0-9_\-/\.\?=&]{0,60}', js, re.I)))[:40]: print("  kw:", m)
    except Exception as e: print("ERR", u, repr(e)[:100])
for u in ("https://www.maritime.dot.gov/msci-advisories",):
    s, c, b = get(u); h = b.decode("utf-8", "replace")
    print(u, re.findall(r'href="(/msci/[^"]+)"', h)[:12], re.findall(r'<time[^>]*datetime="([^"]+)"', h)[:6])
    print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))[2000:3200])
