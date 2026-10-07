import json, sys, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept": "application/json,text/xml,*/*"}
def get(u, n=600, t=40):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t)
        b = r.read()
        return r.status, b
    except Exception as e:
        return str(e)[:100], b""
def show(name, u, n=500):
    s, b = get(u)
    print("###", name, s, len(b)); print(b[:n].decode("utf-8", "replace").replace("\n", " ")); sys.stdout.flush()

# Yahoo
ok, bad = [], []
for sym in ["ITA","BZ=F","CL=F","NG=F","ZW=F","BDRY","JETS","^VIX","^OVX","USDILS=X","USDPLN=X","USDTWD=X","USDKRW=X","USDINR=X","USDRUB=X","USDUAH=X","USDTRY=X","USDIRR=X","USDEGP=X","USDPKR=X","^N225","^TWII","^KS11","^BSESN","^TA125.TA","^STOXX50E","WEAT","FRO","DHT","EURN","TUR","EZA","ERUS","UKRN.L","^GSPC","GC=F","HG=F","TLT"]:
    s, b = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=1y&interval=1d")
    try:
        r = json.loads(b)["chart"]["result"][0]; n = len([c for c in r["indicators"]["quote"][0]["close"] if c is not None]); ok.append((sym, n))
    except Exception:
        bad.append((sym, s))
print("YAHOO ok", ok); print("YAHOO bad", bad)
# PortWatch services
show("pw services", "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services?f=json", 3000)
# DoD contracts rss
show("defense.gov rss", "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=5", 800)
show("defense.gov contracts page", "https://www.defense.gov/News/Contracts/", 300)
# OONI
show("ooni aggregation", "https://api.ooni.io/api/v1/aggregation?probe_cc=IR&since=2026-09-01&until=2026-10-06&axis_x=measurement_start_day&test_name=web_connectivity", 700)
# ProZorro
show("prozorro", "https://public-api.prozorro.gov.ua/api/2.5/tenders?limit=2&descending=1", 600)
# UK contracts finder
show("contracts finder", "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search?publishedFrom=2026-10-01&publishedTo=2026-10-06&limit=2", 600)
# Find a tender
show("find a tender", "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=1&updatedFrom=2026-10-01T00:00:00", 400)
# AGSI without key
show("agsi", "https://agsi.gie.eu/api?country=UA&from=2026-09-25&to=2026-10-05", 300)
# cloudflare radar no token
show("cf radar", "https://api.cloudflare.com/client/v4/radar/annotations/outages?limit=2&format=json", 300)
# gpsjam
show("gpsjam", "https://gpsjam.org/", 200)
# Danish AIS
show("dma ais", "https://web.ais.dk/aisdata/", 300)
# EIA
show("opensky states", "https://opensky-network.org/api/states/all?lamin=44&lomin=22&lamax=52&lomax=40", 300)
# NASA GIBS? Eurocontrol
show("eurocontrol", "https://www.eurocontrol.int/network-operations-portal", 120)
# FAA notam
show("faa notam", "https://external-api.faa.gov/notamapi/v1/notams?icaoLocation=UKBB", 200)
# Reliefweb
show("reliefweb", "https://api.reliefweb.int/v1/reports?appname=warwatch&limit=1", 300)
# UN comtrade preview
show("comtrade", "https://comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode=842&period=202507&cmdCode=93", 300)
# GDELT 2 geo
show("gdelt doc", "https://api.gdeltproject.org/api/v2/doc/doc?query=ukraine&mode=timelinevol&format=json&timespan=7d", 200)
show("gdelt v1 file", "http://data.gdeltproject.org/events/index.html", 150)
