"""Probe: what do TradeAtlas and Export Genius expose publicly (docs, API paths)? Prints status codes and snippets only."""
import re, urllib.request
def get(u, t=20):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t)
        return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), str(e)[:100]
for u in ["https://doc.tradeatlas.com/", "https://doc.tradeatlas.com/en/", "https://doc.tradeatlas.com/en/api/", "https://doc.tradeatlas.com/api/",
          "https://www.tradeatlas.com/api", "https://www.tradeatlas.com/en/api", "https://api.tradeatlas.com/", "https://api.tradeatlas.com/docs",
          "https://api.tradeatlas.com/swagger", "https://api.tradeatlas.com/openapi.json", "https://www.exportgenius.in/api", "https://www.exportgenius.in/trade-data-api",
          "https://www.exportgenius.in/pricing", "https://api.exportgenius.in/", "https://thecompanyatlas.com/mcp/pricing"]:
    s, b = get(u)
    print(s, u, len(b), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))[:200] if s == 200 else b[:100])
s, b = get("https://doc.tradeatlas.com/")
for m in sorted(set(re.findall(r'(?:src|href)="([^"]+\.(?:js|html|md))"', b)))[:30]:
    print("asset", m)
