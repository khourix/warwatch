"""Probe: does Comtrade (key) and e-Stat (appId) return monthly pickup/SUV trade for the war-zone countries? Prints counts only."""
import json, os, sys, urllib.parse, urllib.request

CK = os.environ.get("COMTRADE_API_KEY", "")
EK = os.environ.get("ESTAT_APP_ID", "")
print("COMTRADE_API_KEY set:", bool(CK), "len", len(CK), "| ESTAT_APP_ID set:", bool(EK), "len", len(EK))


def get(url, headers=None, t=25):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "warwatch-probe"})
    try:
        with urllib.request.urlopen(req, timeout=t) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", 0), str(e)[:300]


def comtrade(reporter, partner, flow, cmd, period):
    q = {"reporterCode": reporter, "period": period, "cmdCode": cmd, "flowCode": flow, "partnerCode": partner, "maxRecords": 500}
    u = "https://comtradeapi.un.org/data/v1/get/C/M/HS?" + urllib.parse.urlencode({k: v for k, v in q.items() if v is not None})
    s, b = get(u, {"Ocp-Apim-Subscription-Key": CK, "User-Agent": "warwatch-probe"})
    try:
        d = json.loads(b)
        rows = d.get("data", [])
        return s, len(rows), rows[:2], d.get("error") or d.get("message")
    except Exception:
        return s, 0, [], b[:200]


NAMES = {729: "Sudan", 434: "Libya", 887: "Yemen", 180: "DRC", 368: "Iraq", 148: "Chad", 400: "Jordan", 784: "UAE", 792: "Turkey", 760: "Syria", 706: "Somalia"}
if CK:
    per = ",".join(f"2023{m:02d}" for m in range(1, 13))
    print("\n== Mirror: Japan (392) exports of 8704 pickups to each country, 2023 monthly ==")
    for p in (729, 434, 887, 180, 368, 148, 400, 784, 792, 760, 706):
        s, n, rows, err = comtrade(392, p, "X", "8704", per)
        print(NAMES[p], s, n, err or "", [(r.get("period"), r.get("qty"), r.get("primaryValue")) for r in rows[:2]])
    print("\n== Own reports: country imports of 8704, 2023 monthly ==")
    for r_ in (729, 434, 887, 180, 368, 148, 400):
        s, n, rows, err = comtrade(r_, None, "M", "8704", per)
        print(NAMES[r_], s, n, err or "")
    print("\n== Depth: Japan -> Sudan 8704 for 2019 ==")
    s, n, rows, err = comtrade(392, 729, "X", "8704", ",".join(f"2019{m:02d}" for m in range(1, 13)))
    print(s, n, err or "")
    print("\n== HS6 split available? Japan -> Yemen 870421,870422,870431,870323,870324 2023 ==")
    s, n, rows, err = comtrade(392, 887, "X", "870421,870422,870431,870323,870324", per)
    print(s, n, err or "", sorted({r.get("cmdCode") for r in rows}))
if EK:
    print("\n== e-Stat: Japanese trade statistics datasets ==")
    for w in ("貿易統計 品別国別", "普通貿易統計"):
        u = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList?" + urllib.parse.urlencode({"appId": EK, "statsCode": "00350300", "searchWord": w, "limit": 5})
        s, b = get(u)
        try:
            d = json.loads(b)["GET_STATS_LIST"]
            lst = d["DATALIST_INF"].get("TABLE_INF", [])
            lst = lst if isinstance(lst, list) else [lst]
            print(w, s, d["RESULT"]["STATUS"], d["RESULT"].get("ERROR_MSG"), d["DATALIST_INF"].get("NUMBER"))
            for t in lst[:5]:
                print("  ", t.get("@id"), t.get("STAT_NAME", {}).get("$"), "|", (t.get("TITLE") or {}).get("$") if isinstance(t.get("TITLE"), dict) else t.get("TITLE"), t.get("SURVEY_DATE"))
        except Exception as e:
            print(w, s, b[:300])
