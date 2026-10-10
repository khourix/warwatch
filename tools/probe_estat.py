"""One-off: inspect the 2026 customs commodity-by-country export table and peek at HS 8703/8704 rows."""
import json, os, urllib.parse, urllib.request
K = os.environ["ESTAT_APP_ID"]
B = "https://api.e-stat.go.jp/rest/3.0/app/json/"
ID = "0004049306"
def get(ep, **p):
    p["appId"] = K
    with urllib.request.urlopen(B + ep + "?" + urllib.parse.urlencode(p), timeout=120) as r:
        return json.load(r)
m = get("getMetaInfo", statsDataId=ID)["GET_META_INFO"]["METADATA_INF"]
objs = m["CLASS_INF"]["CLASS_OBJ"]
for o in objs:
    c = o["CLASS"]; c = c if isinstance(c, list) else [c]
    print("OBJ", o["@id"], o["@name"], len(c), [(x["@code"], x["@name"]) for x in c[:6]])
    if o["@id"] in ("cat01", "cat02", "cat03"):
        hs = [x for x in c if x["@code"].startswith(("8703", "8704"))]
        print("  8703/8704 codes:", len(hs), [(x["@code"], x["@name"][:50]) for x in hs[:60]])
    if "国" in o["@name"] or o["@id"].startswith("area"):
        sel = [x for x in c if any(k in x["@name"] for k in ("スーダン", "リビア", "イエメン", "サウジ", "クウェート", "カタール", "オマーン", "バーレーン", "アラブ首長"))]
        print("  countries:", [(x["@code"], x["@name"]) for x in sel])
