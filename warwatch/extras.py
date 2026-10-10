"""Map and panel data that is not a scored series: live aircraft positions,
active naval/air hazard warnings with coordinates, prediction-market odds and
US advisory levels by country. Every fetcher fails soft: a missing source
leaves its layer empty and the dashboard says so.
"""
import datetime as dt
import html
import json
import re
import time
import urllib.parse

import config as C
import sources as S

# Navigational-warning text that signals military activity or interference.
HAZARD = re.compile(r"MISSILE|ROCKET|LIVE FIR|FIRING|GUNNERY|NAVAL EXERCISE|MILITARY EXERCISE|EXERCISES?|"
                    r"GPS|GNSS|INTERFERENCE|JAMMING|MINES?\b|MINEFIELD|DRONE|UNMANNED|MILITARY|NAVAL OPERATION",
                    re.I)
COORD = re.compile(r"(\d{1,2})-(\d{2}(?:\.\d+)?)([NS])\s+(\d{1,3})-(\d{2}(?:\.\d+)?)([EW])")


def parse_coords(text):
    """All 'DD-MM.mN DDD-MM.mE' pairs in a warning text -> [(lat, lon)]."""
    out = []
    for la, lam, ns, lo, lom, ew in COORD.findall(text or ""):
        lat = int(la) + float(lam) / 60
        lon = int(lo) + float(lom) / 60
        out.append((-lat if ns == "S" else lat, -lon if ew == "W" else lon))
    return out


MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def parse_issue(text):
    """NGA 'issueDate' such as '071541Z SEP 2023' -> date, or None."""
    m = re.match(r"\s*(\d{2})\d{4}Z\s+([A-Z]{3})\s+(\d{4})", text or "")
    try:
        return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    except (AttributeError, KeyError, ValueError):
        return None


def parse_nga(warnings):
    """Active broadcast warnings -> hazard markers [{id, lat, lon, text}], one per warning (first position)."""
    out = []
    for w in warnings:
        text = w.get("text", "")
        if not HAZARD.search(text):
            continue
        pos = parse_coords(text)
        if not pos:
            continue
        out.append({"id": f"{w.get('navArea', '')}-{w.get('msgNumber', '')}/{w.get('msgYear', '')}",
                    "lat": round(pos[0][0], 2), "lon": round(pos[0][1], 2),
                    "text": " ".join(text.split())[:160], "issued": str(parse_issue(w.get("issueDate")) or ""),
                    "active": w.get("status") != "CANCELED"})
    return out


NGA_URL = "https://msi.nga.mil/api/publications/smaps?output=json&status=all"   # NGA's current warnings feed; the old broadcast-warn feed stopped on 2024-05-10


def smaps_to_warnings(rows):
    """NGA MSI 'smaps' rows -> the {text, issueDate, navArea, msgNumber, msgYear, status} shape parse_nga reads."""
    out = []
    for r in rows:
        issued = r.get("createdOn") or ""
        yr = re.search(r"(\d{4})\s*$", issued)
        out.append({"text": r.get("msgText") or "", "issueDate": issued, "navArea": r.get("usNavArea") or r.get("navArea") or "",
                    "msgNumber": r.get("msgSqncNumber", ""), "msgYear": yr.group(1) if yr else "", "status": r.get("status", "")})
    return out


_CACHE = {}


def nga_recent(theatre, days=30, today=None):
    """Hazard warnings issued in the last `days` whose position falls in the theatre box."""
    if "nga" not in _CACHE:
        _CACHE["nga"] = fetch_nga()
    cut = str((today or dt.date.today()) - dt.timedelta(days=days))
    box = C.THEATRE_BOX[theatre]
    return float(sum(1 for m in _CACHE["nga"] if m["issued"] >= cut and in_box(m["lat"], m["lon"], box)))


def hub_stats(theatre):
    """(aircraft with a position, aircraft with degraded navigation accuracy) over the theatre's hubs."""
    n = bad = 0
    for lat, lon, r in C.HUBS[theatre]:
        key = ("hub", lat, lon)
        if key not in _CACHE:
            _CACHE[key] = fetch_hub(lat, lon, r)
        a, b = parse_nav(_CACHE[key])
        n += a
        bad += b
    return n, bad


def fetch_nga():
    """Every hazard warning NGA serves, in force and cancelled. Raises when the feed fails, so a bad fetch is never read as 'no warnings'."""
    p = S.get(NGA_URL)
    return parse_nga(smaps_to_warnings(p["smaps"]))


def nga_archive(items):
    """Folds the warnings into history/cache/nga_msgs.csv (id, issued, lat, lon), which keeps what NGA later drops. -> all archived rows."""
    import store
    rows = {r[0]: r for r in store.cache_rows("nga_msgs")}
    for m in items:
        if m["issued"]:
            rows[m["id"]] = [m["id"], m["issued"], f"{m['lat']}", f"{m['lon']}"]
    out = sorted(rows.values(), key=lambda r: (r[1], r[0]))
    store.cache_rows_save("nga_msgs", out)
    return out


def nga_series(theatre, today=None):
    """Hazard warnings issued in the 30 days up to each day, inside the theatre box -> [(date, count)].
    NGA's new feed starts keeping cancelled warnings on C.NGA_COVERED_FROM, so counts start 30 days after it."""
    if "nga" not in _CACHE:
        _CACHE["nga"] = fetch_nga()
    rows = nga_archive(_CACHE["nga"])
    box = C.THEATRE_BOX[theatre]
    mine = [dt.date.fromisoformat(r[1]) for r in rows if in_box(float(r[2]), float(r[3]), box)]
    today = today or dt.date.today()
    d = dt.date.fromisoformat(C.NGA_COVERED_FROM) + dt.timedelta(days=30)
    out = []
    while d <= today:
        out.append((d.isoformat(), float(sum(1 for m in mine if 0 <= (d - m).days <= 30))))
        d += dt.timedelta(days=1)
    return out


# ---- Japan Coast Guard navigational warnings (NAVAREA XI, which Japan coordinates, and Japan's own warnings) ----
# The TUHO index refuses GitHub and home connections alike, but the warning list and text CGIs behind navarea11.html answer.
JCG_CGI = "https://www1.kaiho.mlit.go.jp/TUHO/keiho/cgi/"
JCG_TYPES = ("NAVAREA11", "JAPANNW")
JCG_COVERED_FROM = "2026-10-10"   # first fetch: the lists show warnings in force, so ones issued and cancelled before this are missing
JCG_MSG = re.compile(r"(?:NO\.|番号:)\s*(\d{2})-(\d{3,4})\s*発表日時:\s*(\d{4})年(\d{1,2})月(\d{1,2})日")   # after NFKC folding
JCG_HAZARD = re.compile(r"射撃|ミサイル|ロケット|訓練|爆撃|演習|機雷")   # Japanese-language warnings: firing, missile, rocket, exercise, bombing, mines
DMS = re.compile(r"(\d{1,3})-(\d{2})-(\d{2}(?:\.\d+)?)([NSEW])")


def parse_jcg_texts(kind, text):
    """disp_warnings.cgi page (warnings one after another, each 'NO.26-0454 発表日時：2026年10月10日 03時 <English text>', or for Japan's own
    warnings '番号：26-3998 発表日時：... <Japanese text with full-width digits>') -> hazard markers
    [{id, lat, lon, text, issued}] like parse_nga's."""
    import unicodedata
    plain = unicodedata.normalize("NFKC", re.sub(r"<[^>]+>", " ", text)).replace("\u2212", "-").replace("\u2010", "-")
    plain = re.sub(r"\s+", " ", plain)
    plain = DMS.sub(lambda m: f"{m.group(1)}-{int(m.group(2)) + float(m.group(3)) / 60:05.2f}{m.group(4)}", plain)   # 34-20-00N -> 34-20.00N
    heads = list(JCG_MSG.finditer(plain))
    out = []
    for i, m in enumerate(heads):
        body = plain[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(plain)]
        body = re.sub(r"^\s*\d{1,2}時\s*", "", body)
        pos = parse_coords(body)
        if not (HAZARD.search(body) or JCG_HAZARD.search(body)) or not pos:
            continue
        out.append({"id": f"{kind}-{m.group(2)}/{m.group(1)}", "lat": round(pos[0][0], 2), "lon": round(pos[0][1], 2), "text": body.strip()[:160],
                    "issued": f"{int(m.group(3)):04d}-{int(m.group(4)):02d}-{int(m.group(5)):02d}"})
    return out


def _jcg_post(cgi, data):
    import urllib.request
    req = urllib.request.Request(JCG_CGI + cgi, data=urllib.parse.urlencode(data).encode(),
                                 headers={"User-Agent": C.USER_AGENT, "Content-Type": "application/x-www-form-urlencoded",
                                          "Referer": "https://www1.kaiho.mlit.go.jp/TUHO/keiho/navarea11.html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def fetch_jcg(today=None):
    """Every warning in force in both lists (this year's and last year's numbers), with its text. Raises when a list fails."""
    yr = (today or dt.date.today()).year
    out = []
    for kind in JCG_TYPES:
        tanas = []
        for y in (yr - 1, yr):
            tanas += re.findall(r"<tana>(\d+)</tana>", _jcg_post("warnings.cgi", {"YEAR": str(y), "TYPE": kind, "LANG": "JP"}))
        for i in range(0, len(tanas), 25):
            out += parse_jcg_texts(kind, _jcg_post("disp_warnings.cgi", {"TYPE": kind, "TANA": ":".join(tanas[i:i + 25]) + ":", "LANG": "JP"}))
            time.sleep(1)
    return out


def jcg_series(theatre, today=None):
    """Hazard warnings (firing, missiles, exercises) Japan's Coast Guard issued in the 30 days up to each day inside the theatre box,
    kept in history/cache/jcg_msgs.csv. -> [(date, count)]"""
    import store
    if "jcg" not in _CACHE:
        _CACHE["jcg"] = fetch_jcg(today)
        rows = {r[0]: r for r in store.cache_rows("jcg_msgs")}
        for m in _CACHE["jcg"]:
            rows[m["id"]] = [m["id"], m["issued"], f"{m['lat']}", f"{m['lon']}"]
        _CACHE["jcg_rows"] = sorted(rows.values(), key=lambda r: (r[1], r[0]))
        store.cache_rows_save("jcg_msgs", _CACHE["jcg_rows"])
    box = C.THEATRE_BOX[theatre]
    mine = [dt.date.fromisoformat(r[1]) for r in _CACHE["jcg_rows"] if in_box(float(r[2]), float(r[3]), box)]
    today = today or dt.date.today()
    d, out = dt.date.fromisoformat(JCG_COVERED_FROM) + dt.timedelta(days=30), []
    if d > today:
        raise RuntimeError(f"archive building: first 30-day count on {d.isoformat()} ({len(mine)} warnings kept so far)")
    while d <= today:
        out.append((d.isoformat(), float(sum(1 for m in mine if 0 <= (d - m).days <= 30))))
        d += dt.timedelta(days=1)
    return out


# ---- China MSA navigational warnings (航行警告), read from the MSA mobile site's list API ----
# msa.gov.cn/page/outter/weather.jsp refuses GitHub and home connections alike; the mobile site's article API answers from GitHub and lists
# every warning all bureaus issue since late 2015, newest first, with a title naming the activity and usually the sea or the bureau
# ('军事训练—琼航警196/26', '渤海北部军事演习'). The PLA's largest drills around Taiwan were announced by Xinhua rather than in this list.
MSA_API = "https://www.msa.gov.cn/msacncms_wap/cmsarticle/selectPageByChannelId.jhtml"
MSA_CHANNEL = "9c219298b27f460e995a99401b3ff6af"
MSA_MIL = re.compile(r"军事|实弹|射击|演习|打靶|导弹|火箭|武器")   # military, live fire, firing, exercise, target practice, missile, rocket, weapons
MSA_OFF = re.compile(r"取消|结束|解除|终止")   # cancelled, ended, lifted: not a new closure
MSA_BUREAU = re.compile(r"([\u4e00-\u9fff]{1,2})航警")   # 琼航警196/26, 【琼航警102】, 云航警2022（0074）, 鲁航警0409
MSA_SEA = [("korea", "渤海|黄海|莱州|辽东"), ("taiwan", "东海|台湾|平潭|闽|浪岗|舟山"), ("scs", "南海|北部湾|珠江口|琼州|海南|西沙|南沙|湛江|汕尾")]   # sea named in the title
MSA_THEATRE = {"taiwan": "闽浙沪", "scs": "琼粤桂深海", "korea": "鲁辽冀津云连苏"}   # else the issuing bureau (海 = Guangxi Beihai, 云 = Lianyungang)


def msa_theatre(title):
    """Theatre of a warning title: the sea it names, else its issuing bureau, else ''."""
    for th, pat in MSA_SEA:
        if re.search(pat, title):
            return th
    m = MSA_BUREAU.findall(title)
    b = m[-1][-1] if m else ""   # the last match: '演习航警——津航警159/22' is Tianjin's
    return next((th for th, bs in MSA_THEATRE.items() if b and b in bs), "")


def parse_msa(items):
    """MSA list items -> [[id, date, bureau, title]] for the Chinese-language military warnings (the English copies would count twice)."""
    out = []
    for x in items or []:
        t = (x.get("articleTitle") or "").strip()
        if not MSA_MIL.search(t) or MSA_OFF.search(t) or not re.search(r"[\u4e00-\u9fff]", t):
            continue
        m = MSA_BUREAU.findall(t)
        out.append([str(x.get("articleId")), str(x.get("articlePublishTime") or "")[:10], m[-1][-1] if m else "", t[:60]])
    return out


def fetch_msa_page(page, count=100):
    """-> (items, total pages). Items carry articleId, articleTitle, articlePublishTime ('2026-10-10 17:40')."""
    import urllib.request
    req = urllib.request.Request(MSA_API, data=urllib.parse.urlencode({"channelId": MSA_CHANNEL, "pageNum": page, "count": count}).encode(),
                                 headers={"User-Agent": C.USER_AGENT, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                                          "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.msa.gov.cn/msacncms_wap/pages/info_warn.jhtml?channelId=" + MSA_CHANNEL})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("list") or [], int(d.get("pages") or 0)


def msa_update(max_pages=10):
    """Reads the list newest first until it reaches warnings already kept, folding military ones into history/cache/msa_warn.csv.
    The first row of that file, ['_from', date], is the oldest day the scans have read completely. -> (rows, covered-from date)"""
    import store
    rows = store.cache_rows("msa_warn")
    start = rows[0][1] if rows and rows[0][0] == "_from" else ""
    kept = {r[0]: r for r in rows if r[0] != "_from"}
    seen_ids = set(kept)
    oldest = ""
    for page in range(1, max_pages + 1):
        items, pages = fetch_msa_page(page)
        if not items:
            break
        oldest = str(items[-1].get("articlePublishTime") or "")[:10]
        for r in parse_msa(items):
            kept[r[0]] = r
        if start and (any(str(x.get("articleId")) in seen_ids for x in items) or oldest < start):
            break
        if page >= pages:
            break
        time.sleep(1)
    start = start or oldest
    out = sorted(kept.values(), key=lambda r: (r[1], r[0]))
    store.cache_rows_save("msa_warn", [["_from", start]] + out)
    return out, start


def msa_counts(rows, theatre, first, today, days=30):
    """Military warnings from the theatre's bureaus issued in the `days` up to each day from `first`. -> [(date, count)]"""
    mine = [dt.date.fromisoformat(r[1]) for r in rows if r[1] and msa_theatre(r[3]) == theatre]
    out, d = [], first
    while d <= today:
        out.append((d.isoformat(), float(sum(1 for m in mine if 0 <= (d - m).days < days))))
        d += dt.timedelta(days=1)
    return out


def msa_series(theatre, today=None):
    import store
    if "msa" not in _CACHE:
        _CACHE["msa"] = msa_update()
    rows, start = _CACHE["msa"]
    today = today or dt.date.today()
    live = msa_counts(rows, theatre, dt.date.fromisoformat(start) + dt.timedelta(days=30), today) if start else []
    return store.seed(f"msa_{theatre}", live)


# ---- China Customs (GACC) monthly bulletin: exports by destination country ----
# stats.customs.gov.cn refuses GitHub and home connections alike (412); the English site's Monthly Bulletin answers and links one
# table per month, 'Imports and Exports by Country (Region) of Origin/Destination', in US$1,000.
GACC_MONTHLY = "http://english.customs.gov.cn/statics/report/monthly.html"
GACC_COUNTRY = {"russia": "Russia", "iran": "Iran", "dprk": "Democratic People's Republic of Korea", "belarus": "Belarus"}


def gacc_month_links(page):
    """Monthly Bulletin page -> [(YYYY-MM-01, url)] for the by-country table of each month listed."""
    year = re.search(r'<option value="(\d{4})"', page)
    row = re.search(r"Imports and Exports by Country.*?</tr>", page, re.S)
    if not year or not row:
        raise RuntimeError("GACC monthly bulletin: by-country row not found")
    months = {m[:3].lower(): i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
    return [(f"{year.group(1)}-{months[m.lower()]:02d}-01", u) for u, m in re.findall(r"href=['\"]?(http[^ '\">]+)['\"]?\s*>\s*(\w{3})", row.group(0))
            if m.lower() in months]


def parse_gacc_country(page):
    """By-country table -> {country: exports that month in US$ million}. Columns: total, exports, imports, each for the month then the year to date."""
    out = {}
    plain = html.unescape(re.sub(r"<[^>]+>", "|", page)).replace("\xa0", " ")
    for key, name in GACC_COUNTRY.items():
        m = re.search(r"\|\s*" + re.escape(name) + r"\s*\|([\s|0-9,.\-]+)", plain)
        if not m:
            continue
        nums = [float(x.replace(",", "")) for x in re.findall(r"-?[\d,]+(?:\.\d+)?", m.group(1))]
        if len(nums) >= 6:
            out[key] = nums[2] / 1000.0
    return out


def gacc_series(country):
    """China's monthly exports to a country (US$ million), kept in history/cache/gacc_exports.csv (month, country, value) as each month appears."""
    import store
    if "gacc" not in _CACHE:
        kept = {(r[0], r[1]): r for r in store.cache_rows("gacc_exports")}
        have = {r[0] for r in kept.values()}
        for month, url in gacc_month_links(S.get(GACC_MONTHLY, raw=True, retries=2, wait=5)):
            if month in have:
                continue
            for k, v in parse_gacc_country(S.get(url, raw=True, retries=2, wait=5)).items():
                kept[(month, k)] = [month, k, f"{v:.3f}"]
            time.sleep(1)
        _CACHE["gacc"] = sorted(kept.values())
        store.cache_rows_save("gacc_exports", _CACHE["gacc"])
    return store.seed(f"gacc_{country}", [(r[0], float(r[2])) for r in _CACHE["gacc"] if r[1] == country])


def in_box(lat, lon, box):
    la0, la1, lo0, lo1 = box
    return la0 <= lat <= la1 and lo0 <= lon <= lo1


# ---- ADS-B: military and airlift positions for the map ----------------------------
def mil_positions(payload):
    """Military aircraft with a position -> osint.aircraft() records (owner, type, altitude, squawk, theatre)."""
    import osint
    return [osint.aircraft(a) for a in payload.get("ac", []) if a.get("lat") is not None and a.get("lon") is not None]


# ---- ADS-B: civil traffic and navigation degradation near a hub -------------------
def parse_nav(payload):
    """-> (aircraft with a position, aircraft reporting degraded navigation accuracy).
    NACp below 8 means position error above ~93 m: the signature of GNSS interference."""
    n = bad = 0
    for a in payload.get("ac", []):
        if a.get("lat") is None or a.get("lon") is None:
            continue
        n += 1
        nac = a.get("nac_p")
        if isinstance(nac, int) and nac < 8:
            bad += 1
    return n, bad


def fetch_hub(lat, lon, radius=250):
    return S.get(f"https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}", retries=2, wait=5)


# ---- EASA conflict-zone information bulletins (airline airspace risk notices) -------------
def parse_czib(payload):
    """EASA CZIB export -> [{name, lat, lon, updated}] for active zones with a position."""
    rows = payload if isinstance(payload, list) else next(iter(payload.values()), [])
    out = []
    for r in rows:
        if str(r.get("status", "")).lower() != "active":
            continue
        try:
            lat, lon = (float(x) for x in str(r.get("coordinates", "")).split(","))
        except ValueError:
            continue
        m = re.search(r"\d{4}-\d{2}-\d{2}", str(r.get("updated", "")))
        out.append({"name": r.get("name", ""), "lat": round(lat, 2), "lon": round(lon, 2), "updated": m.group(0) if m else ""})
    return out


def fetch_czib():
    return parse_czib(S.get("https://www.easa.europa.eu/en/domains/air-operations/czibs/export-json?page&_format=json"))


def czib_recent(days=30, today=None, box=None):
    """Active zones (inside `box`, if given) whose bulletin was revised in the last `days`: airlines are being told something changed."""
    if "czib" not in _CACHE:
        _CACHE["czib"] = fetch_czib()
    cut = str((today or dt.date.today()) - dt.timedelta(days=days))
    return float(sum(1 for z in _CACHE["czib"] if z["updated"] >= cut and (box is None or in_box(z["lat"], z["lon"], box))))


# ---- Prediction markets (display only, never scored) and the Pentagon pizza index -----------
KEYS = {   # theatre -> words that tie a market to it
    "ukraine": r"Ukrain|Russia|Putin|Zelensk|Crimea|Donbas",
    "europe_east": r"NATO|Baltic|Poland|Lithuania|Latvia|Estonia|Kaliningrad|Finland|Suwalki",
    "iran": r"\bIran|Hormuz|Tehran|Khamenei",
    "yemen": r"Houthi|Yemen|Red Sea|Bab el|Sanaa",
    "israel": r"Israel|Hezbollah|Lebanon|Gaza|Netanyahu|Hamas",
    "taiwan": r"Taiwan|Taipei|Taiwan Strait|Kinmen",
    "scs": r"South China Sea|Philippines|Scarborough|Spratly|Second Thomas",
    "korea": r"North Korea|Kim Jong|Pyongyang|South Korea|Korean",
    "southasia": r"India|Pakistan|Kashmir|Modi|Islamabad",
    "libya": r"Libya|Tripoli|Haftar",
    "sudan": r"Sudan|\bRSF\b|Khartoum",
    "drc": r"Congo|\bM23\b|Goma|Kinshasa",
    "venezuela": r"Venezuela|Maduro|Caracas|Cuba|Guyana|Colombia|Panama",
}


def theatre_of_text(text):
    for t, pat in KEYS.items():
        if re.search(pat, text or "", re.I):
            return t
    return ""


WAR = re.compile(r"\bwar\b|military|strike|invade|invasion|attack|missile|nuclear|ceasefire|cease-fire|troops|nato|bomb|conflict|houthi|hezbollah|hamas|"
                 r"drone|airstrike|blockade|hormuz|regime|offensive|escalat|annex|capture|peace deal|peace agreement|sanction|iran|russia|ukrain|taiwan|gaza|israel|"
                 r"north korea|pakistan|kashmir|venezuela|maduro|sudan|congo|libya|article 5|martial law|draft|mobiliz|coup|assassinat|kharg|invade|enter .* city|control of", re.I)
EXCLUDE = re.compile(r"\b(nba|nfl|nhl|mlb|ufc|fifa|world cup|super bowl|oscar|grammy|bitcoin|ethereum|\bbtc\b|album|movie|box office|tweet|elon|temperature|weather|mvp|ballon|"
                     r"stanley cup|premier league|champions league|f1|formula 1)\b", re.I)


def is_war(q):
    return bool(WAR.search(q or "")) and not EXCLUDE.search(q or "")


def parse_poly(payload, min_volume=50000):
    out = []
    for e in payload.get("events", []):
        for m in e.get("markets", []):
            if m.get("closed") or not m.get("active", True):
                continue
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
                p = float(prices[0])
                vol = float(m.get("volume") or 0)
            except (ValueError, IndexError, TypeError):
                continue
            if vol < min_volume or not (0.005 < p < 0.995):
                continue
            q = m.get("question") or e.get("title", "")
            if not is_war(q + " " + e.get("title", "")):
                continue
            try:
                tok = json.loads(m.get("clobTokenIds") or "[]")[0]
            except (ValueError, IndexError, TypeError):
                tok = ""
            out.append({"q": q, "p": p, "vol": vol, "end": (m.get("endDate") or e.get("endDate") or "")[:10], "tok": tok,
                        "src": "Polymarket", "theatre": theatre_of_text(q),
                        "url": "https://polymarket.com/event/" + (e.get("slug") or "")})
    return out


def fetch_poly(queries=("Iran war", "Iran strike", "Hormuz", "Ukraine ceasefire", "Russia NATO", "Israel Hezbollah", "Houthi", "Taiwan invasion", "nuclear", "military action", "North Korea", "India Pakistan", "Venezuela", "South China Sea", "Sudan war")):
    seen, out = set(), []
    for q in queries:
        try:
            p = S.get("https://gamma-api.polymarket.com/public-search?"
                      + urllib.parse.urlencode({"q": q, "limit_per_type": 6}), retries=2, wait=3)
        except Exception:
            continue
        for m in parse_poly(p):
            if m["q"] not in seen:
                seen.add(m["q"])
                out.append(m)
        time.sleep(0.5)
    return out


def parse_kalshi(payload, min_volume=5000):
    out = []
    for e in payload.get("events", []):
        title = e.get("title", "")
        th = theatre_of_text(title)
        if not th or not is_war(title):
            continue
        best = None
        for m in e.get("markets", []):
            try:
                p = float(m.get("last_price_dollars") or 0)
                vol = float(m.get("volume_fp") or 0)
            except (TypeError, ValueError):
                continue
            if vol >= min_volume and 0.005 < p < 0.995 and (best is None or vol > best[1]):
                best = (m, vol, p)
        if best:
            m, vol, p = best
            sub = m.get("yes_sub_title") or ""
            out.append({"q": title + (f": {sub}" if sub and sub.lower() not in title.lower() else ""), "p": p, "vol": vol,
                        "kser": e.get("series_ticker") or "", "ktk": m.get("ticker") or "",
                        "end": (m.get("close_time") or "")[:10], "src": "Kalshi", "theatre": th,
                        "url": "https://kalshi.com/markets/" + (e.get("event_ticker") or "").lower()})
    return out


def fetch_kalshi(pages=4):
    out, cursor = [], ""
    for _ in range(pages):
        q = {"limit": 200, "status": "open", "with_nested_markets": "true"}
        if cursor:
            q["cursor"] = cursor
        try:
            p = S.get("https://api.elections.kalshi.com/trade-api/v2/events?" + urllib.parse.urlencode(q), retries=2, wait=3)
        except Exception:
            break
        out.extend(parse_kalshi(p))
        cursor = p.get("cursor") or ""
        if not cursor:
            break
    return out


def downsample(pts, n=90):
    """Keep at most n points, always the first and last."""
    if len(pts) <= n:
        return pts
    step = (len(pts) - 1) / (n - 1)
    return [pts[round(i * step)] for i in range(n)]


def parse_poly_history(payload):
    """CLOB prices-history -> [[YYYY-MM-DD HH:MM, probability]]."""
    out = []
    for h in payload.get("history", []):
        try:
            out.append([dt.datetime.fromtimestamp(int(h["t"]), dt.timezone.utc).strftime("%Y-%m-%d"), round(float(h["p"]), 4)])
        except (KeyError, ValueError, TypeError):
            continue
    return downsample(out)


def parse_kalshi_history(payload):
    out = []
    for c in payload.get("candlesticks", []):
        try:
            p = float((c.get("price") or {}).get("close_dollars") or (c.get("yes_bid") or {}).get("close_dollars"))
            out.append([dt.datetime.fromtimestamp(int(c["end_period_ts"]), dt.timezone.utc).strftime("%Y-%m-%d"), round(p, 4)])
        except (KeyError, ValueError, TypeError):
            continue
    return downsample(out)


def fetch_history(m):
    try:
        if m["src"] == "Polymarket" and m.get("tok"):
            return parse_poly_history(S.get("https://clob.polymarket.com/prices-history?" + urllib.parse.urlencode(
                {"market": m["tok"], "interval": "max", "fidelity": 360}), retries=2, wait=3))
        if m["src"] == "Kalshi" and m.get("kser") and m.get("ktk"):
            now = int(time.time())
            return parse_kalshi_history(S.get(f"https://api.elections.kalshi.com/trade-api/v2/series/{m['kser']}/markets/{m['ktk']}/candlesticks?"
                                              + urllib.parse.urlencode({"start_ts": now - 120 * 86400, "end_ts": now, "period_interval": 1440}), retries=2, wait=3))
    except Exception:
        return []
    return []


def fetch_markets():
    top = sorted(fetch_poly() + fetch_kalshi(), key=lambda m: -m["vol"])[:40]
    for m in top:
        h = fetch_history(m)
        if h:
            today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
            if h[-1][0] < today:
                h.append([today, round(m["p"], 4)])   # end the line at today's price
            else:
                h[-1] = [today, round(m["p"], 4)]
            m["h"] = h
        m.pop("tok", None), m.pop("kser", None), m.pop("ktk", None)
        time.sleep(0.2)
    return top


def parse_pizza(payload):
    """PizzINT (a third-party scrape of Google 'popular times' for pizza places near the Pentagon).
    -> (index 0-100, active spikes, places with a reading now)."""
    spikes = payload.get("active_spikes")
    idx = payload.get("overall_index")
    live = sum(1 for d in payload.get("data", []) if d.get("current_popularity") is not None)
    return (float(idx) if idx is not None else None, int(spikes or 0), live)


def fetch_pizza():
    return parse_pizza(S.get("https://www.pizzint.watch/api/dashboard-data", retries=2, wait=3))


def pizza_now():
    if "pizza" not in _CACHE:
        _CACHE["pizza"] = fetch_pizza()
    return _CACHE["pizza"]


# ---- US advisory level by country (map shading) --------------------------------------
ALIAS = {"Türkiye": "Turkey", "Burma (Myanmar)": "Myanmar", "Congo, Democratic Republic of the": "Dem. Rep. Congo",
         "Israel, The West Bank and Gaza": "Israel", "South Sudan": "S. Sudan", "Bosnia and Herzegovina": "Bosnia and Herz."}


def country_levels(items):
    out = {}
    for it in items:
        t = it.get("Title", "")
        if " - Level " not in t:
            continue
        name, rest = t.split(" - Level ", 1)
        try:
            out[ALIAS.get(name.strip(), name.strip())] = int(rest[0])
        except ValueError:
            pass
    return out


def collect():
    """All map and panel layers; any failure leaves that layer empty."""
    import os
    import osint
    ex = {"mil": [], "sqk": [], "ships": [], "inc": [], "fires": [], "nga": [], "markets": [], "levels": {}, "czib": [], "pizza": None, "errors": []}
    def nga():
        if "nga" not in _CACHE:
            _CACHE["nga"] = fetch_nga()
        return [m for m in _CACHE["nga"] if m.get("active", True)]
    def czib():
        if "czib" not in _CACHE:
            _CACHE["czib"] = fetch_czib()
        return _CACHE["czib"]
    def ships():
        out = []
        try:
            out.extend(osint.fetch_usni())
        except Exception as e:
            ex["errors"].append(f"usni: {str(e)[:80]}")
        try:
            out.extend(osint.fetch_digitraffic()[0])
        except Exception as e:
            ex["errors"].append(f"digitraffic: {str(e)[:80]}")
        key = os.environ.get("AISSTREAM_API_KEY")
        if key:
            try:
                boxes = [C.BOXES[t] for t in ("iran", "yemen", "israel", "ukraine", "europe_east")] + [(30, 46, -6, 36), (12, 32, 32, 45)] + [C.BOXES[t] for t in ("taiwan", "scs", "korea", "venezuela")]   # Gulf and Red Sea coverage is thin on aisstream
                for m in osint.fetch_aisstream(key, boxes).values():
                    if m["lat"] is None or int(m["type"] or 0) not in (35, 55):
                        continue
                    out.append({"n": m["n"] or m["mmsi"], "k": "navy", "loc": f'{m["lat"]:.2f}, {m["lon"]:.2f}', "g": "Military ship (AIS)", "lat": m["lat"], "lon": m["lon"],
                                "flag": osint.MID.get(m["mmsi"][:3], ""), "dest": m["dest"], "spd": m["spd"], "d": "live", "th": osint.theatre_at(m["lat"], m["lon"]),
                                "note": "AIS position from aisstream.io."})
            except Exception as e:
                ex["errors"].append(f"aisstream: {str(e)[:80]}")
        return out
    def fires():
        key = os.environ.get("FIRMS_MAP_KEY")
        if not key:
            return []
        return osint.fetch_fires(key, C.FIRMS_BOX)
    for key, fn in (("mil", lambda: mil_positions(S.fetch_adsb())),
                    ("sqk", osint.fetch_squawks),
                    ("ships", ships),
                    ("inc", osint.fetch_incidents),
                    ("fires", fires),
                    ("nga", nga),
                    ("czib", czib),
                    ("markets", fetch_markets),
                    ("pizza", pizza_now),
                    ("levels", lambda: country_levels(S.fetch_state()))):
        try:
            ex[key] = fn()
        except Exception as e:
            ex["errors"].append(f"{key}: {str(e)[:80]}")
    # squawks seen anywhere: also surface any military aircraft in the main list that squawk an emergency
    seen = {m["hex"] for m in ex["sqk"]}
    for m in ex["mil"]:
        if m.get("sq") in osint.SQUAWK and m["hex"] not in seen:
            mean, why = osint.SQUAWK[m["sq"]]
            ex["sqk"].append(dict(m, mean=mean, why=why))
    return ex
