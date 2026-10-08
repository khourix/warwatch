import json, re, urllib.request, urllib.parse, collections
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) warwatch-probe", "Accept": "application/json,text/html,*/*"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=12) as f:
        return f.status, f.headers.get("content-type"), f.read()
# 1. every host and api path named in the live site's own JS
s, c, b = get("https://msi.nga.mil/NavWarnings")
html = b.decode("utf-8", "replace")
hosts = set(); paths = set()
for src in re.findall(r'<script[^>]+src="([^"]+)"', html):
    u = urllib.parse.urljoin("https://msi.nga.mil/NavWarnings", src)
    try:
        js = get(u)[2].decode("utf-8", "replace")
        hosts |= set(re.findall(r'https?://[A-Za-z0-9\.\-]*nga[A-Za-z0-9\.\-]*[^"\'\s\)]{0,40}', js))
        paths |= set(re.findall(r'["\'`]((?:/?api)?/publications/[A-Za-z0-9_/\-\.\?=&{}\$]*)["\'`]', js))
    except Exception as e: print("ERR js", repr(e)[:80])
print("HOSTS", sorted(hosts)[:40]); print("PATHS", sorted(paths)[:60], flush=True)
def show(u):
    print("=====", u, flush=True)
    try:
        s, c, b = get(u); t = b.decode("utf-8", "replace")
        print(s, c, len(t), t[:300].replace("\n", " "))
        try:
            d = json.loads(t)
            L = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
            dates = sorted(str(w.get("date") or w.get("issueDate") or w.get("dateOfOccurrence") or w.get("occurrenceDate") or "") for w in L if isinstance(w, dict))
            print("n", len(L), "keys", (list(d.keys()) if isinstance(d, dict) else list(L[0].keys()) if L and isinstance(L[0], dict) else ""), "dates", dates[:1], dates[-1:])
        except Exception as e: print("not json")
    except Exception as e: print("ERR", repr(e)[:160])
for host in ("https://msi.nga.mil", "https://msi.pub.kubic.nga.mil", "https://msi.gs.mil"):
    for p in ("/api/publications/broadcast-warn/latest-warning", "/api/publications/broadcast-warn?output=json&status=active&navArea=P",
              "/api/publications/asam?output=json&sort=date&maxOccurrenceDate=2030-01-01", "/api/publications/asam?output=json&minOccurrenceDate=2026-09-01",
              "/api/publications/ntm/pubs?output=json"):
        show(host + p)
