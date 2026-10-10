"""One-off: list e-Stat Japan customs tables and peek at HS 8703/8704 detail by country."""
import json, os, urllib.parse, urllib.request
K = os.environ["ESTAT_APP_ID"]
B = "https://api.e-stat.go.jp/rest/3.0/app/json/"
def get(ep, **p):
    p["appId"] = K
    with urllib.request.urlopen(B + ep + "?" + urllib.parse.urlencode(p), timeout=60) as r:
        return json.load(r)
for sw in ("品別国別", "輸出 品別国別表"):
    d = get("getStatsList", statsCode="00350300", searchWord=sw, limit=30)
    ts = d["GET_STATS_LIST"]["DATALIST_INF"].get("TABLE_INF", [])
    ts = ts if isinstance(ts, list) else [ts]
    print("==", sw, d["GET_STATS_LIST"]["DATALIST_INF"].get("NUMBER"))
    for t in ts:
        print(t["@id"], t.get("SURVEY_DATE"), t.get("CYCLE"), (t.get("TITLE") or {}).get("$", t.get("TITLE")) if not isinstance(t.get("TITLE"), str) else t["TITLE"], "|", t.get("STATISTICS_NAME"))
