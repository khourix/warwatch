#!/usr/bin/env python3
"""One-off runner probe, round 6. Prints a report; changes nothing."""
import json, re, urllib.request, urllib.error
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"}
def get(u, n=4000):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read(n)
def hdr(t): print(f"\n===== {t} =====", flush=True)

hdr("worldmonitor Hormuz tracker structure")
j = json.loads(get("https://www.worldmonitor.app/api/supply-chain/hormuz-tracker", 400000))
print({k: (str(v)[:80] if not isinstance(v, (list, dict)) else f"{type(v).__name__}[{len(v)}]") for k, v in j.items()})
for c in j.get("charts", []):
    s = c.get("series", [])
    vals = [x["value"] for x in s]
    print(c.get("label"), "points", len(s), "nonzero", sum(1 for v in vals if v), "max", max(vals) if vals else None, "first/last", s[0] if s else None, s[-1] if s else None)
for k in j:
    if k not in ("charts", "summary"): print(k, str(j[k])[:200])

hdr("PizzINT front end: other indices (bars?)")
html = get("https://www.pizzint.watch/", 800000).decode("utf-8", "replace")
for m in re.finditer(r'(?i)(gay|freddie|bar index|dc bars|nightlife)', html):
    print("...", html[max(0, m.start() - 80): m.end() + 120].replace("\n", " "))
    break
js = sorted(set(re.findall(r'/_next/static/[A-Za-z0-9_/\-\.]+\.js', html)))
print("js files", len(js))
seen = set()
for u in js:
    try:
        t = get("https://www.pizzint.watch" + u, 3_000_000).decode("utf-8", "replace")
    except Exception as e:
        continue
    for r in sorted(set(re.findall(r'["\'](/api/[A-Za-z0-9_/\-\.?=&]+)["\']', t))):
        if r not in seen: seen.add(r); print("route", r)
    for m in re.finditer(r'(?i)(gay[ -]?bar|freddie)', t):
        print("bar ref in", u[-40:], t[max(0, m.start() - 60): m.end() + 100].replace("\n", " ")); break

hdr("ShipFinder links and plans")
h = get("https://www.shipfinder.com/", 400000).decode("utf-8", "replace")
print(sorted(set(re.findall(r'href="(/[^"#]*(?:api|pricing|plan|price|doc|dev)[^"]*)"', h, re.I)))[:15])
for u in ("https://www.shipfinder.com/api", "https://www.shipfinder.com/pricing"):
    try: b = get(u, 60000).decode("utf-8", "replace"); print(u, len(b), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))[:500])
    except Exception as e: print(u, str(e)[:60])

hdr("oilpriceapi demo codes (freight)")
d = json.loads(get("https://api.oilpriceapi.com/v1/demo/prices", 100000))
print([p["code"] for p in d["data"]["prices"]])

hdr("Drewry WCI headline and SCFI")
t = get("https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry", 600000).decode("utf-8", "replace")
print([re.sub(r"<[^>]+>", "", x)[:200] for x in re.findall(r"(?:Drewry[^<]{0,40})?Composite[^<]{0,200}", t)[:3]])
print(re.findall(r"WCI\)[^<]{0,150}", t)[:2])
