import json, sys, urllib.request, urllib.parse, csv, io
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(u, t=40):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t)
        return r.status, r.read()
    except Exception as e:
        return str(e)[:100], b""
s, b = get("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services?f=json")
names = [x["name"] for x in json.loads(b)["services"]]
print("PW services with port/trade/daily:", [n for n in names if any(k in n.lower() for k in ("port", "daily", "chokepoint", "trade"))])
for sym in ["ita.us","lmt.us","gld.us","ewt.us","stng.us","zim.us","eis.us","epol.us","fxi.us","ewy.us","inda.us","copx.us","ilf.us","^vix","cl.f","bz.f","usdils","usdpln","usdtwd","bdry.us","^spx","usdrub","usduah"]:
    s, b = get(f"https://stooq.com/q/d/l/?s={sym}&i=d")
    rows = list(csv.reader(io.StringIO(b.decode("utf-8", "replace"))))
    print("STOOQ", sym, s, len(rows), rows[-1] if rows else b[:80])
for host in ("query2.finance.yahoo.com", "query1.finance.yahoo.com"):
    s, b = get(f"https://{host}/v8/finance/chart/ITA?range=1mo&interval=1d")
    print("YAHOO", host, s, len(b))
s, b = get("https://fc.yahoo.com"); print("YAHOO fc", s, len(b))
for u in ["https://api.exchangerate.host/timeseries?start_date=2026-09-01&end_date=2026-09-05&base=USD&symbols=ILS",
          "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=ITA&apikey=demo",
          "https://api.coingecko.com/api/v3/ping"]:
    s, b = get(u); print("MISC", u[:60], s, b[:100])
