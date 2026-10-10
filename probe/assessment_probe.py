"""One-off reachability probe for the October 2026 data-source assessment.

Fetches each candidate source once from a GitHub runner and records status, size,
content type and a short snippet. Public data only; no keys are printed.
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
GFW = os.environ.get("GFW_TOKEN", "")

PROBES = [
    # air
    ("adsb.lol 2023 history repo", "https://api.github.com/repos/adsblol/globe_history_2023/releases?per_page=3", {}),
    ("adsb.lol 2024 history repo", "https://api.github.com/repos/adsblol/globe_history_2024/releases?per_page=2", {}),
    ("adsb.lol 2025 history repo", "https://api.github.com/repos/adsblol/globe_history_2025/releases?per_page=2", {}),
    ("adsb.lol 2026 history repo", "https://api.github.com/repos/adsblol/globe_history_2026/releases?per_page=2", {}),
    ("adsb.fi military", "https://opendata.adsb.fi/api/v2/mil", {}),
    ("airplanes.live military", "https://api.airplanes.live/v2/mil", {}),
    ("ADS-B Exchange monthly samples 2022-02-01", "https://samples.adsbexchange.com/readsb-hist/2022/02/01/", {}),
    ("OpenSky anonymous states (Iran box)", "https://opensky-network.org/api/states/all?lamin=24&lomin=44&lamax=40&lomax=64", {}),
    ("Zenodo OpenSky flight lists", "https://zenodo.org/api/records?q=%22opensky%22%20flightlist&size=5", {}),
    ("Safe Airspace Iran page", "https://safeairspace.net/iran/", {}),
    ("CelesTrak military GP", "https://celestrak.org/NORAD/elements/gp.php?GROUP=military&FORMAT=json", {}),
    ("Launch Library 2 upcoming", "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=3", {}),
    ("USGS explosions", "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventtype=explosion&starttime=2026-09-01", {}),
    ("Open-Meteo Tehran cloud", "https://api.open-meteo.com/v1/forecast?latitude=35.7&longitude=51.4&daily=cloud_cover_mean", {}),
    ("Japan MOD Joint Staff press", "https://www.mod.go.jp/js/press/index.html", {}),
    ("Japan Coast Guard nav warnings", "https://www1.kaiho.mlit.go.jp/TUHO/", {}),
    ("China MSA nav warnings", "https://www.msa.gov.cn/page/outter/weather.jsp", {}),
    ("China MSA home", "https://www.msa.gov.cn/", {}),
    ("alerts.in.ua site", "https://alerts.in.ua/", {}),
    ("Tzeva Adom history", "https://api.tzevaadom.co.il/alerts-history", {}),
    ("Israel Home Front Command", "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json", {}),
    # sea
    ("Danish AIS downloads", "http://aisdata.ais.dk/", {}),
    ("Danish AIS web", "https://web.ais.dk/aisdata/", {}),
    ("OpenSanctions maritime index", "https://data.opensanctions.org/datasets/latest/maritime/index.json", {}),
    ("GUR war-sanctions ships", "https://war-sanctions.gur.gov.ua/en/transport/ships", {}),
    ("MARAD advisories", "https://www.maritime.dot.gov/msci-advisories", {}),
    ("UKMTO / JMIC products", "https://www.ukmto.org/partner-products/jmic-products", {}),
    ("straits.live", "https://straits.live/", {}),
    ("Freightos FBX page", "https://terminal.freightos.com/freightos-baltic-index-global-container-pricing-index/", {}),
    ("Drewry WCI", "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry", {}),
    ("GFW gaps events (token)", "https://gateway.api.globalfishingwatch.org/v3/events?datasets[0]=public-global-gaps-events:latest&start-date=2026-09-01&end-date=2026-09-03&limit=2&offset=0", {"auth": "gfw"}),
    ("GFW encounters events (token)", "https://gateway.api.globalfishingwatch.org/v3/events?datasets[0]=public-global-encounters-events:latest&start-date=2026-09-01&end-date=2026-09-03&limit=2&offset=0", {"auth": "gfw"}),
    ("GFW port visits (token)", "https://gateway.api.globalfishingwatch.org/v3/events?datasets[0]=public-global-port-visits-c2-events:latest&start-date=2026-09-01&end-date=2026-09-02&limit=2&offset=0", {"auth": "gfw"}),
    # political / info / finance
    ("Auswaertiges Amt travel warnings", "https://www.auswaertiges-amt.de/opendata/travelwarning", {}),
    ("Canada travel advisories", "https://data.international.gc.ca/travel-voyage/index-alpha-eng.json", {}),
    ("Smartraveller export", "https://www.smartraveller.gov.au/destinations-export", {}),
    ("Japan MOFA open data", "https://www.ezairyu.mofa.go.jp/opendata/area/newarrivalA.xml", {}),
    ("OSAC", "https://www.osac.gov/Content/Browse/Report?subContentTypes=Alerts", {}),
    ("Telegram preview (rybar)", "https://t.me/s/rybar", {}),
    ("Telegram preview (DeepStateUA)", "https://t.me/s/DeepStateUA", {}),
    ("GDELT DOC timeline", "https://api.gdeltproject.org/api/v2/doc/doc?query=mobilization%20sourcecountry:RS&mode=timelinevolraw&format=json&timespan=30d", {}),
    ("GDELT GKG last update", "http://data.gdeltproject.org/gdeltv2/lastupdate.txt", {}),
    ("bonbast", "https://www.bonbast.com/", {}),
    ("alanchand USD", "https://alanchand.com/en/currencies-price/usd", {}),
    ("Nobitex USDT-IRT stats", "https://api.nobitex.ir/market/stats?srcCurrency=usdt&dstCurrency=rls", {}),
    ("MOEX ISS IMOEX history", "https://iss.moex.com/iss/history/engines/stock/markets/index/securities/IMOEX.json?from=2026-09-01", {}),
    ("GPR daily", "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls", {}),
    ("CrisisWatch", "https://www.crisisgroup.org/crisiswatch", {}),
    ("Prozorro tenders", "https://public.api.openprocurement.org/api/2.5/tenders?descending=1&limit=3", {}),
    ("UK Find a Tender OCDS", "https://www.find-a-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=1", {}),
    ("Manifold war search", "https://api.manifold.markets/v0/search-markets?term=war&limit=3", {}),
    ("Bluesky public search", "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=mobilization&limit=3", {}),
    ("ReliefWeb (no appname)", "https://api.reliefweb.int/v2/reports?limit=1", {}),
    ("Google Trends daily RSS", "https://trends.google.com/trending/rss?geo=IL", {}),
    ("Poland border waits", "https://granica.gov.pl/index_wait.php?p=b&v=en", {}),
    ("OFAC SDN advanced XML head", "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV", {}),
    ("Polymarket gamma", "https://gamma-api.polymarket.com/markets?limit=1", {}),
]


def fetch(url, opts):
    hdr = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.8"}
    if opts.get("auth") == "gfw":
        if not GFW:
            return {"error": "no GFW_TOKEN"}
        hdr["Authorization"] = "Bearer " + GFW
    req = urllib.request.Request(url, headers=hdr)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context()) as r:
            body = r.read(400_000)
            return {"status": r.status, "type": r.headers.get("Content-Type", ""), "bytes": len(body),
                    "secs": round(time.time() - t0, 1), "snippet": body[:300].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        body = e.read(2000)
        return {"status": e.code, "type": e.headers.get("Content-Type", ""), "bytes": len(body),
                "secs": round(time.time() - t0, 1), "snippet": body[:300].decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001 - a probe records every failure
        return {"error": f"{type(e).__name__}: {e}"[:300], "secs": round(time.time() - t0, 1)}


def main(out):
    res = []
    for name, url, opts in PROBES:
        r = fetch(url, opts)
        r.update(name=name, url=url)
        res.append(r)
        print(f"{r.get('status', 'ERR')}\t{r.get('bytes', 0)}\t{name}\t{r.get('error', '')}", flush=True)
    with open(out, "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "probe/results.json")
