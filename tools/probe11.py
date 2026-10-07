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
s, b = get("https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=3")
t = b.decode("utf-8", "replace")
i = t.index("<item>"); print("RSS ITEM", t[i:i+2500].replace("\n", " "))
print("RSS items", t.count("<item>"))
s, b = get("https://api.ooni.io/api/v1/aggregation?probe_cc=UA&since=2026-09-20&until=2026-10-06&axis_x=measurement_start_day&test_name=web_connectivity")
print("OONI UA", b[:300])
s, b = get("https://public-api.prozorro.gov.ua/api/2.5/tenders?limit=1&descending=1&opt_fields=value,procuringEntity,items,dateModified")
print("PROZ", b[:700])
s, b = get("https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search?publishedFrom=2026-10-01&publishedTo=2026-10-06&limit=1")
j = json.loads(b); print("CF keys", list(j.keys()), j.get("releases", [{}])[0].get("tender", {}).keys() if j.get("releases") else "")
