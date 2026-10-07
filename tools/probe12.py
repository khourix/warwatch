import json, os, urllib.request, urllib.parse, datetime as dt
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def get(u, h=None, t=40):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={**UA, **(h or {})}), timeout=t)
        return r.status, r.read()
    except Exception as e:
        return str(e)[:100], b""
def show(tag, u, h=None, n=300):
    s, b = get(u, h); print(tag, s, len(b), b[:n].decode("utf-8", "replace").replace("\n", " "), flush=True)
today = dt.date.today(); d5 = (today - dt.timedelta(days=4)).isoformat()
# power / energy (ENTSO-E substitutes)
show("EC price", "https://api.energy-charts.info/price?bzn=DE-LU&start=2026-10-01&end=2026-10-06")
show("EC cbpf", "https://api.energy-charts.info/cbpf?country=pl&start=2026-10-01&end=2026-10-06")
show("EC public_power", "https://api.energy-charts.info/public_power?country=de&start=2026-10-01&end=2026-10-06")
show("EC signal", "https://api.energy-charts.info/signal?country=pl")
show("AGSI UA", "https://agsi.gie.eu/api?country=UA&from=2026-09-01&to=2026-10-05")
show("AGSI EU", "https://agsi.gie.eu/api?continent=eu&from=2026-09-01&to=2026-10-05")
show("ALSI", "https://alsi.gie.eu/api?continent=eu&from=2026-09-20&to=2026-10-05")
show("Ember", "https://ember-energy.org/data-catalogue/")
# airspace
show("GPSJam", f"https://gpsjam.org/data/{d5}-h3_4.csv", n=200)
show("GPSJam mani", "https://gpsjam.org/data/manifest.csv", n=200)
show("SafeAirspace", "https://safeairspace.net/")
show("SafeAirspace api", "https://safeairspace.net/api/v1/warnings", n=200)
show("OpenSky UA", "https://opensky-network.org/api/states/all?lamin=44&lamax=53&lomin=22&lomax=41", n=150)
show("OpenSky flights", f"https://opensky-network.org/api/flights/arrival?airport=EPWA&begin={int(dt.datetime.now().timestamp())-86400}&end={int(dt.datetime.now().timestamp())}", n=200)
show("FAA tfr", "https://tfr.faa.gov/tfrapi/getTfrList", n=200)
show("EASA", "https://www.easa.europa.eu/en/domains/air-operations/czibs", n=100)
show("OurAirports", "https://davidmegginson.github.io/ourairports-data/airports.csv", n=100)
show("flightradar", "https://data-live.flightradar24.com/zones/fcgi/feed.js?bounds=53,44,22,41&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0", n=150)
# Cloudflare Radar with token
tok = os.environ.get("CLOUDFLARE_API_TOKEN", "")
print("CF token present:", bool(tok))
H = {"Authorization": "Bearer " + tok}
show("CF verify", "https://api.cloudflare.com/client/v4/user/tokens/verify", H)
show("CF http timeseries UA", "https://api.cloudflare.com/client/v4/radar/http/timeseries?location=UA&dateRange=28d&aggInterval=1d&format=json", H, 400)
show("CF traffic anomalies", "https://api.cloudflare.com/client/v4/radar/traffic_anomalies?location=UA&dateRange=28d&format=json", H, 400)
show("CF netflows", "https://api.cloudflare.com/client/v4/radar/netflows/timeseries?location=UA&dateRange=28d&format=json", H, 400)
show("CF attacks l7", "https://api.cloudflare.com/client/v4/radar/attacks/layer7/timeseries?location=UA&dateRange=28d&format=json", H, 400)
show("CF bgp hijacks", "https://api.cloudflare.com/client/v4/radar/bgp/hijacks/events?dateRange=28d&format=json&per_page=2", H, 300)
show("CF bgp leaks", "https://api.cloudflare.com/client/v4/radar/bgp/leaks/events?dateRange=28d&format=json&per_page=2", H, 300)
