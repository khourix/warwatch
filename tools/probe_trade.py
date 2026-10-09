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
import time
if CK:
    def cm(reporter, partner, flow, cmd, period):
        time.sleep(4)
        r = comtrade(reporter, partner, flow, cmd, period)
        if r[0] == 429:
            time.sleep(20)
            r = comtrade(reporter, partner, flow, cmd, period)
        return r
    y23 = ",".join(f"2023{m:02d}" for m in range(1, 13))
    y19 = ",".join(f"2019{m:02d}" for m in range(1, 13))
    print("== Thailand (764) exports, Hilux source: 870421/870422/870431/870432 to targets, 2023 ==")
    for p in (729, 887, 434, 180, 368, 400, 784):
        s_, n, rows, err = cm(764, p, "X", "870421,870422,870431,870432", y23)
        print(NAMES[p], s_, n, err or "", sorted({(r.get("cmdCode")) for r in rows}), sum(r.get("qty") or 0 for r in rows))
    print("== South Africa (710) exports of 8704 to Sudan/Yemen/DRC 2023 ==")
    for p in (729, 887, 180):
        s_, n, rows, err = cm(710, p, "X", "8704", y23)
        print(NAMES[p], s_, n, err or "")
    print("== Japan HS6 vehicle codes to Sudan 2023 (all partners listing for 870323,870324,870333,870421,870422) ==")
    s_, n, rows, err = cm(392, 729, "X", "870323,870324,870333,870421,870422,870431", y23)
    print(s_, n, err or "", sorted({r.get("cmdCode") for r in rows}), sum(r.get("qty") or 0 for r in rows))
    print("== History depth: Japan -> Sudan 8704 and 8703 in 2019, 2015 ==")
    for yr in (2019, 2015):
        s_, n, rows, err = cm(392, 729, "X", "8704,8703", ",".join(f"{yr}{m:02d}" for m in range(1, 13)))
        print(yr, s_, n, err or "", sum(r.get("qty") or 0 for r in rows))
    print("== Latest month available: Japan -> Sudan 8703/8704 2026 ==")
    s_, n, rows, err = cm(392, 729, "X", "8704,8703", ",".join(f"2026{m:02d}" for m in range(1, 10)))
    print(s_, n, err or "", sorted({r.get("period") for r in rows}))
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
