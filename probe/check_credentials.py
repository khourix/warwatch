"""One-off check that the new account secrets are present and accepted.

Prints only secret presence, HTTP status and a short scrubbed message; never a
token, key or response body that could carry one.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "warwatch-credential-check/1.0 (+https://github.com/khourix/warwatch)"
NAMES = [
    "CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET", "OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET",
    "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION", "ALERTS_IN_UA_TOKEN",
    "GCP_SA_KEY_JSON", "GCP_PROJECT", "MEDIACLOUD_API_KEY", "EARTHDATA_TOKEN",
    "TOMTOM_API_KEY", "SPACETRACK_USER", "SPACETRACK_PASS", "BARENTSWATCH_CLIENT_ID",
    "BARENTSWATCH_CLIENT_SECRET", "FREIGHTOS_EMAIL", "FREIGHTOS_PASSWORD", "ENTSOE_TOKEN",
]
ENV = {n: os.environ.get(n, "").strip() for n in NAMES}
SECRETS = [v for v in ENV.values() if len(v) >= 4]


def scrub(text):
    for s in SECRETS:
        text = text.replace(s, "***")
    return text


def call(url, data=None, headers=None, method=None):
    hdr = {"User-Agent": UA}
    hdr.update(headers or {})
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read(200_000)
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000)
    except Exception as e:  # noqa: BLE001 - every failure is a result here
        return None, f"{type(e).__name__}: {e}".encode()


def oauth(url, cid, secret, extra=None):
    data = {"grant_type": "client_credentials", "client_id": cid, "client_secret": secret}
    data.update(extra or {})
    st, raw = call(url, data, {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        tok = json.loads(raw).get("access_token")
    except Exception:  # noqa: BLE001
        tok = None
    return st, tok, ("" if tok else raw[:160].decode("utf-8", "replace"))


def need(*names):
    missing = [n for n in names if not ENV[n]]
    return ("missing " + ", ".join(missing)) if missing else None


def check_cdse():
    if m := need("CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET"):
        return m
    st, tok, msg = oauth("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
                         ENV["CDSE_CLIENT_ID"], ENV["CDSE_CLIENT_SECRET"])
    if not tok:
        return f"token {st} {msg}"
    q = json.dumps({"collections": ["sentinel-2-l2a"], "bbox": [51.30, 25.10, 51.33, 25.13],
                    "datetime": "2026-09-01T00:00:00Z/2026-10-10T00:00:00Z", "limit": 3}).encode()
    st2, raw = call("https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search", q,
                    {"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    n = len(json.loads(raw).get("features", [])) if st2 == 200 else raw[:120].decode("utf-8", "replace")
    return f"token OK; Sentinel Hub catalog {st2}, Al Udeid scenes: {n}"


def check_opensky():
    if m := need("OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET"):
        return m
    st, tok, msg = oauth("https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
                         ENV["OPENSKY_CLIENT_ID"], ENV["OPENSKY_CLIENT_SECRET"])
    if not tok:
        return f"token {st} {msg}"
    end = int(time.time()) - 86400 * 2
    st2, raw = call(f"https://opensky-network.org/api/flights/arrival?airport=OTHH&begin={end - 3600 * 12}&end={end}",
                    headers={"Authorization": "Bearer " + tok})
    n = len(json.loads(raw)) if st2 == 200 else raw[:120].decode("utf-8", "replace")
    return f"token OK; Doha arrivals (12 h, 2 days ago) {st2}: {n}"


def check_alerts():
    if m := need("ALERTS_IN_UA_TOKEN"):
        return m
    st, raw = call("https://api.alerts.in.ua/v1/alerts/active.json",
                   headers={"Authorization": "Bearer " + ENV["ALERTS_IN_UA_TOKEN"]})
    n = len(json.loads(raw).get("alerts", [])) if st == 200 else raw[:120].decode("utf-8", "replace")
    return f"{st}, active alerts: {n}"


def check_mediacloud():
    if m := need("MEDIACLOUD_API_KEY"):
        return m
    st, raw = call("https://search.mediacloud.org/api/sources/collections/?limit=1",
                   headers={"Authorization": "Token " + ENV["MEDIACLOUD_API_KEY"]})
    return f"{st} {'' if st == 200 else raw[:120].decode('utf-8', 'replace')}"


def check_earthdata():
    if m := need("EARTHDATA_TOKEN"):
        return m
    st, raw = call("https://ladsweb.modaps.eosdis.nasa.gov/api/v2/content/details/allData/5200/VNP46A2/2026/270?fields=name",
                   headers={"Authorization": "Bearer " + ENV["EARTHDATA_TOKEN"]})
    return f"LAADS listing {st} {'' if st == 200 else raw[:120].decode('utf-8', 'replace')}"


def check_tomtom():
    if m := need("TOMTOM_API_KEY"):
        return m
    st, raw = call("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point=50.60,36.59&key="
                   + urllib.parse.quote(ENV["TOMTOM_API_KEY"]))
    if st == 200:
        f = json.loads(raw).get("flowSegmentData", {})
        return f"200, Belgorod segment speed {f.get('currentSpeed')} of {f.get('freeFlowSpeed')} km/h"
    return f"{st} {raw[:120].decode('utf-8', 'replace')}"


def check_spacetrack():
    if m := need("SPACETRACK_USER", "SPACETRACK_PASS"):
        return m
    st, raw = call("https://www.space-track.org/ajaxauth/login",
                   {"identity": ENV["SPACETRACK_USER"], "password": ENV["SPACETRACK_PASS"]})
    ok = st == 200 and b"Failed" not in raw
    return f"login {st} {'OK' if ok else raw[:120].decode('utf-8', 'replace')}"


def check_barentswatch():
    if m := need("BARENTSWATCH_CLIENT_ID", "BARENTSWATCH_CLIENT_SECRET"):
        return m
    out = []
    for scope in ("api", "ais"):
        st, tok, msg = oauth("https://id.barentswatch.no/connect/token", ENV["BARENTSWATCH_CLIENT_ID"],
                             ENV["BARENTSWATCH_CLIENT_SECRET"], {"scope": scope})
        out.append(f"scope {scope}: {'OK' if tok else f'{st} {msg}'}")
    return "; ".join(out)


def check_entsoe():
    if m := need("ENTSOE_TOKEN"):
        return m
    st, raw = call("https://web-api.tp.entsoe.eu/api?documentType=A65&processType=A16"
                   "&outBiddingZone_Domain=10YPL-AREA-----S&periodStart=202610080000&periodEnd=202610090000"
                   "&securityToken=" + urllib.parse.quote(ENV["ENTSOE_TOKEN"]))
    return f"{st} {'' if st == 200 else raw[:120].decode('utf-8', 'replace')}"


def check_gcp():
    if m := need("GCP_SA_KEY_JSON"):
        return m
    try:
        k = json.loads(ENV["GCP_SA_KEY_JSON"])
    except ValueError:
        try:
            k = json.loads(base64.b64decode(ENV["GCP_SA_KEY_JSON"]))
        except Exception:  # noqa: BLE001
            return "present but not valid JSON"
    return f"present, service account {k.get('client_email', '?')}, project {k.get('project_id', '?')} (live test after setup)"


def check_present(*names):
    return lambda: need(*names) or "present (tested on first use)"


CHECKS = [
    ("Copernicus Data Space", check_cdse),
    ("OpenSky", check_opensky),
    ("Telegram API id and hash", check_present("TELEGRAM_API_ID", "TELEGRAM_API_HASH")),
    ("Telegram session", check_present("TELEGRAM_SESSION")),
    ("alerts.in.ua", check_alerts),
    ("Google Cloud key", check_gcp),
    ("Media Cloud", check_mediacloud),
    ("NASA Earthdata", check_earthdata),
    ("TomTom", check_tomtom),
    ("Space-Track", check_spacetrack),
    ("BarentsWatch", check_barentswatch),
    ("Freightos", check_present("FREIGHTOS_EMAIL", "FREIGHTOS_PASSWORD")),
    ("ENTSO-E", check_entsoe),
]


def main(out):
    res = []
    for name, fn in CHECKS:
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001
            r = f"error {type(e).__name__}: {e}"
        r = scrub(str(r)).replace("\n", " ")
        res.append({"name": name, "result": r})
        print(f"{name}: {r}", flush=True)
    with open(out, "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "probe/credentials.json")
