"""One-off check of the alerts.in.ua token: active alerts and a month of history for Kyiv city. Prints counts only, never the token."""
import json
import os
import urllib.error
import urllib.request

TOKEN = os.environ.get("ALERTS_IN_UA_TOKEN", "")


def call(path):
    req = urllib.request.Request("https://api.alerts.in.ua" + path, headers={"Authorization": "Bearer " + TOKEN, "User-Agent": "warwatch/0.3"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read(200).decode("utf-8", "replace").replace(TOKEN, "***")


if not TOKEN:
    print("ALERTS_IN_UA_TOKEN missing")
    raise SystemExit(0)
st, d = call("/v1/alerts/active.json")
print("active:", st, len(d.get("alerts", [])) if isinstance(d, dict) else d)
if isinstance(d, dict) and d.get("alerts"):
    a = d["alerts"][0]
    print("fields:", sorted(a))
st, d = call("/v1/regions/31/alerts/month_ago.json")
if isinstance(d, dict):
    al = d.get("alerts", [])
    print("Kyiv city, last month:", st, len(al), "alerts", (al[-1].get("started_at"), al[0].get("started_at")) if al else "")
    print("types:", sorted({x.get("alert_type") for x in al}))
else:
    print("history:", st, d)
