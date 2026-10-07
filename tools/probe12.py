import json, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0"}
PW = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
def get(u):
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode()
    except Exception as e:
        return "ERR " + str(e)[:150]
j = get(PW + "Daily_Ports_Data/FeatureServer/0?f=json")
try:
    d = json.loads(j); print("FIELDS", [(f["name"], f["type"]) for f in d["fields"]])
except Exception:
    print("FIELDS raw", j[:300])
j = get(PW + "PortWatch_ports_database/FeatureServer/0?f=json")
try:
    d = json.loads(j); print("PORTDB FIELDS", [f["name"] for f in d["fields"]])
except Exception:
    print("PORTDB raw", j[:300])
q = urllib.parse.urlencode({"where": "1=1", "outFields": "*", "returnGeometry": "false", "resultRecordCount": 2, "f": "json"})
print("PORTDB SAMPLE", get(PW + "PortWatch_ports_database/FeatureServer/0/query?" + q)[:900])
for name in ["Odesa", "Bandar Abbas", "Haifa", "Ashdod", "Kaohsiung", "Busan", "Hodeidah", "Gdansk", "Karachi", "Mundra", "Tripoli", "Puerto Cabello", "Basra", "Aden", "Jeddah"]:
    q = urllib.parse.urlencode({"where": f"portname LIKE '%{name}%'", "outFields": "portid,portname,country", "returnGeometry": "false", "resultRecordCount": 3, "f": "json"})
    print("PORT", name, get(PW + "PortWatch_ports_database/FeatureServer/0/query?" + q)[:400])
q = urllib.parse.urlencode({"where": "portname LIKE '%Kaohsiung%'", "outFields": "*", "returnGeometry": "false", "resultRecordCount": 2, "orderByFields": "date DESC", "f": "json"})
print("DAILY SAMPLE", get(PW + "Daily_Ports_Data/FeatureServer/0/query?" + q)[:900])
