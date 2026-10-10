import json, os, sys, urllib.parse, urllib.request
sys.path.insert(0, "backfill")
import estat
K = os.environ["ESTAT_APP_ID"]
sid = "0004049306"
meta = estat.get(K, "getMetaInfo", statsDataId=sid)["GET_META_INFO"]["METADATA_INF"]["CLASS_INF"]["CLASS_OBJ"]
cat02 = estat.classes({o["@id"]: o for o in estat.listify(meta)}["cat02"])
print({k: v for k, v in cat02.items()})
d = estat.get(K, "getStatsData", statsDataId=sid, cdArea="50137", cdCat01="870323915,870324920,870421915", limit=60)
b = d["GET_STATS_DATA"]
print(json.dumps(b["RESULT_INF"]), json.dumps(b["STATISTICAL_DATA"]["DATA_INF"]["VALUE"][:50], ensure_ascii=False))
