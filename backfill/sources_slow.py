"""Back-fills that crawl public archives slowly: US State Department advisories (Wayback Machine) and the Taiwan PLA aircraft counts."""
import csv
import datetime as dt
import io
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
import time
import urllib.parse

import common as K
import config as C

# ---------------------------------------------------------------- State Department advisories via Wayback
BASE = "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/"
SLUG = {   # FIPS code used by config.STATE_ISO -> advisory page slug
    "UP": "ukraine", "BO": "belarus", "MD": "moldova", "PL": "poland", "LH": "lithuania", "LG": "latvia", "EN": "estonia", "FI": "finland",
    "IR": "iran", "IZ": "iraq", "YM": "yemen", "SA": "saudi-arabia", "MU": "oman", "DJ": "djibouti",
    "IS": "israel-west-bank-and-gaza", "LE": "lebanon", "JO": "jordan", "EG": "egypt", "TW": "taiwan", "RP": "philippines", "VM": "vietnam",
    "KS": "south-korea", "KN": "north-korea", "IN": "india", "PK": "pakistan", "LY": "libya", "SU": "sudan", "OD": "south-sudan",
    "CG": "democratic-republic-of-the-congo", "VE": "venezuela", "CO": "colombia", "CU": "cuba"}
# From 2025 most pages moved to destination.<ISO3>.html (the old addresses now answer 403), so the archive's
# copies of the old pages stop there. Both addresses are read.
NEW_BASE = "https://travel.state.gov/content/tsg_aem/us/en/home/international-travel/travel-advisories/destination."
ISO3 = {"UP": "ukr", "BO": "blr", "MD": "mda", "PL": "pol", "LH": "ltu", "LG": "lva", "EN": "est", "FI": "fin",
        "IR": "irn", "IZ": "irq", "YM": "yem", "SA": "sau", "MU": "omn", "DJ": "dji", "IS": "isr", "LE": "lbn",
        "JO": "jor", "EG": "egy", "TW": "twn", "RP": "phl", "VM": "vnm", "KS": "kor", "KN": "prk", "IN": "ind",
        "PK": "pak", "LY": "lby", "SU": "sdn", "OD": "ssd", "CG": "cod", "VE": "ven", "CO": "col", "CU": "cub"}
LEVEL = re.compile(r"Level\s*([1-4])\s*[:\-–]", re.I)
ORDERED = re.compile(r"ordered\s+(?:the\s+)?departure", re.I)     # "ordered the departure of" is how Kyiv's January 2022 notice read
DEPART = re.compile(r"(?:ordered|authori[sz]ed)\s+(?:the\s+)?departure", re.I)   # either kind: the timing tell (warwatch/tells.py) counts both
HEAD = re.compile(r"(?is)<(title|h1)\b[^>]*>(.*?)</\1>")
CARRY_DAYS = 90       # a page not captured for this long is unknown, not unchanged (most old addresses stop in 2025)


def parse_advisory(html, strict=False):
    """Advisory page -> (level 1-4, 1 if the text mentions an ordered departure of US government staff) or None.
    The level is read from the page title or heading when they carry it, else from the first level in the page;
    strict (the redesigned pages, whose navigation may list every level): only from the title or heading."""
    html = html or ""
    m = next((m for h in HEAD.finditer(html) for m in [LEVEL.search(unescape(h.group(2)))] if m), None)
    if m is None and not strict:
        m = LEVEL.search(html)
    if not m:
        return None
    return int(m.group(1)), 1 if ORDERED.search(html) else 0


def weekly(snaps):
    """[(timestamp, digest)] -> the first snapshot of each ISO week whose content differs from the one before."""
    out, last_week, last_digest = [], None, None
    for ts, digest in snaps:
        d = dt.datetime.strptime(ts[:8], "%Y%m%d").date()
        wk = d.isocalendar()[:2]
        if wk == last_week:
            continue
        last_week = wk
        if digest == last_digest:
            continue
        last_digest = digest
        out.append(ts)
    return out


def parse_departure(html):
    """1 if the page mentions an ordered or an authorised departure of US government staff or families, else 0."""
    return 1 if DEPART.search(html or "") else 0


def fill_forward(points, start, end, max_carry=None):
    """[(date, value)] changes -> {iso_date: value} for every day from the first observation to `end`,
    or, with max_carry, to at most that many days after each observation."""
    pts = sorted(points)
    out, i, cur, seen = {}, 0, None, None
    for d in K.days(max(start, dt.date.fromisoformat(pts[0][0])) if pts else end, end):
        while i < len(pts) and pts[i][0] <= d.isoformat():
            cur, seen = pts[i][1], dt.date.fromisoformat(pts[i][0])
            i += 1
        if cur is not None and (max_carry is None or (d - seen).days <= max_carry):
            out[d.isoformat()] = cur
    return out


def cdx(url):
    q = urllib.parse.urlencode({"url": url, "output": "txt", "fl": "timestamp,digest", "filter": "statuscode:200", "collapse": "timestamp:8"})
    txt = K.get("https://web.archive.org/cdx/search/cdx?" + q, raw=True, timeout=240, retries=4, wait=15).decode()
    return [tuple(ln.split()) for ln in txt.splitlines() if len(ln.split()) == 2]


def cmd_state(theatres, start, end):
    codes = sorted({c for t in theatres for c in C.STATE_ISO.get(t, [])})
    for code in codes:
        slug = SLUG[code]
        urls = {f"{BASE}{slug}-travel-advisory.html": False, f"{NEW_BASE}{ISO3[code]}.html": True}   # address -> strict parse
        if all(K.load(f"state_{k}_{slug}").get(end.isoformat()) for k in ("level", "od_country", "dep_country")):
            continue
        try:
            snaps = sorted((ts, dg, url) for url in urls for ts, dg in cdx(url) if ts[:8] >= start.isoformat().replace("-", ""))
        except RuntimeError as e:
            K.log("cdx failed", slug, str(e)[:100])       # leave this country for the rerun, keep going with the others
            continue
        where = {ts: url for ts, _, url in snaps}
        pick = weekly([(ts, dg) for ts, dg, _ in snaps])
        K.log(slug, len(snaps), "daily captures,", len(pick), "to read")
        lv, od, dep, miss = [], [], [], 0

        def read(ts):
            try:
                html = K.get(f"https://web.archive.org/web/{ts}id_/{where[ts]}", raw=True, timeout=120, retries=3, wait=10).decode("utf-8", "replace")
            except RuntimeError as e:
                K.log("miss", slug, ts, str(e)[:80])
                return ts, None
            got = parse_advisory(html, strict=urls[where[ts]])
            return ts, got and got + (parse_departure(html),)

        with ThreadPoolExecutor(4) as pool:
            for ts, got in pool.map(read, pick):
                if got is None:
                    miss += 1
                    continue
                day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                lv.append((day, got[0]))
                od.append((day, got[1]))
                dep.append((day, got[2]))
        K.log(slug, "read", len(lv), "missed", miss)
        if lv:
            replace_from(f"state_level_{slug}", fill_forward(lv, start, end, CARRY_DAYS), start)
            replace_from(f"state_od_country_{slug}", fill_forward(od, start, end, CARRY_DAYS), start)
            replace_from(f"state_dep_country_{slug}", fill_forward(dep, start, end, CARRY_DAYS), start)
    derive_state(theatres)


def replace_from(series, rows, start):
    """Keep the file's days before `start` and replace the rest with `rows`: a re-read drops what an older
    parser or a longer carry left in the range, where K.save would keep it."""
    cur = {d: v for d, v in K.load(series).items() if d < start.isoformat()}
    cur.update(rows)
    K.write_csv(K.path(series), cur)


def derive_state(theatres):
    """Per-theatre sums over its countries: `state_<th>` (level sum, the live series' definition), `state_od_<th>`
    (countries under an ordered departure) and `state_dep_<th>` (an ordered or an authorised one). Country files are `state_level_<slug>` and `state_od_country_<slug>`,
    named apart from the theatre files (the Iran and Ukraine slugs are also theatre names). A theatre with a country
    that has no history gets empty files: a sum over some of its countries is not the live series' quantity, and the
    live series is better left to build its own history than seeded with a lower one (Israel and Venezuela were)."""
    for th in theatres:
        codes = C.STATE_ISO.get(th, [])
        lv = [K.load(f"state_level_{SLUG[c]}") for c in codes]
        od = [K.load(f"state_od_country_{SLUG[c]}") for c in codes]
        dep = [K.load(f"state_dep_country_{SLUG[c]}") for c in codes]
        if not codes or not all(lv) or not all(od):
            K.log("state", th, "no history: nothing yet for", [SLUG[c] for c, x, y in zip(codes, lv, od) if not (x and y)])
            for k in ("state", "state_od", "state_dep"):
                K.write_csv(K.path(f"{k}_{th}"), {})
            continue
        days_ = sorted(set.intersection(*[set(x) for x in lv]))      # only days when every country has been observed
        K.write_csv(K.path(f"state_{th}"), {d: float(sum(x[d] for x in lv)) for d in days_})
        K.write_csv(K.path(f"state_od_{th}"), {d: float(sum(x.get(d, 0) for x in od)) for d in days_})
        if all(dep):     # countries read before the departure file existed have none until their next re-read
            K.write_csv(K.path(f"state_dep_{th}"), {d: float(sum(x.get(d, 0) for x in dep)) for d in days_})


# ---------------------------------------------------------------- Taiwan PLA activity (MND daily bulletins)
MND = "https://www.mnd.gov.tw/"
BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"}   # the site's firewall refuses bare clients
LINK = re.compile(r'href="[^"]*?news/plaact/(\d+)[^"]*"[^>]*>(.*?)</a>', re.S)
TOTAL = [re.compile(p) for p in (r"共機\s*(\d+)\s*架次", r"共軍機\s*(\d+)\s*架次", r"共機\s*(\d+)\s*架", r"共機[^0-9]{0,6}(\d+)\s*架", r"(\d+)\s*(?:sorties|PLA aircraft|military aircraft)\b")]
MEDIAN = [re.compile(p) for p in (r"(\d+)\s*架次\s*(?:逾越|跨越)\s*(?:海峽)?中線", r"(?:逾越|跨越)\s*(?:海峽)?中線[^0-9]{0,12}(\d+)\s*架次", r"(\d+)\s*(?:of which|sorties)?[^.]{0,40}crossed the median line")]
VESSELS = [re.compile(p) for p in (r"共艦\s*(\d+)\s*艘", r"(\d+)\s*PLAN vessels")]
OFFICIAL = [re.compile(p) for p in (r"公務船\s*(\d+)\s*艘", r"(\d+)\s*official ships")]
DATE = re.compile(r"(\d{2,4})[/\-.年](\d{1,2})[/\-.月](\d{1,2})")


def parse_date(text):
    m = DATE.search(text or "")
    if not m:
        return None
    y = int(m.group(1))
    y += 1911 if y <= 200 else 0
    try:
        return dt.date(y, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def first_int(pats, text):
    for p in pats:
        m = p.search(text)
        if m:
            return int(m.group(1))
    return None


def parse_bulletin(text):
    """Bulletin body -> dict(total, median, vessels, official), each None when the text does not say."""
    flat = " ".join((text or "").split())
    total = first_int(TOTAL, flat)
    if total is None and re.search(r"未偵獲共機|未發現共機|無共機", flat):
        total = 0          # the bulletin says no aircraft were detected
    return {"total": total, "median": first_int(MEDIAN, flat),
            "vessels": first_int(VESSELS, flat), "official": first_int(OFFICIAL, flat)}


def strip_tags(html):
    """Page -> plain text. The site writes much of its Chinese as numeric entities (&#x5171;), so decode them before matching."""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html))))


def cmd_pla(start, end, max_pages=400):
    """Walk the MND list pages newest first, read each bulletin, keep one total per day (the first bulletin of the day wins).
    The ypcat/plavis community archive (public CSV, 2025 onward) is merged for days the crawl could not parse."""
    have = {s: K.load(s) for s in ("pla_aircraft", "pla_median", "pla_vessels", "pla_official_ships")}
    seen, found, empty, unparsed, shown = set(), 0, 0, 0, {}
    parsed = {s: {} for s in have}
    for page in range(1, max_pages + 1):
        try:
            html = K.get(f"{MND}news/plaactlist/{page}", headers=BROWSER, raw=True, timeout=90, retries=4, wait=10).decode("utf-8", "replace")
        except RuntimeError as e:
            K.log("list page", page, "failed", str(e)[:100])
            break
        links = [(i, strip_tags(t)) for i, t in LINK.findall(html)]
        new = [(i, t) for i, t in links if i not in seen]
        seen.update(i for i, _ in new)
        if not new:
            empty += 1
            if empty >= 3:
                break
            continue
        empty = 0
        oldest = None
        for i, title in new:
            tday = parse_date(title)
            if tday and not (start <= tday <= end):
                oldest = min(oldest, tday) if oldest else tday
                continue       # the list title already dates it: no need to open it
            try:
                body = K.get(f"{MND}news/plaact/{i}", headers=BROWSER, raw=True, timeout=90, retries=3, wait=10).decode("utf-8", "replace")
            except RuntimeError as e:
                K.log("miss", i, str(e)[:80])
                continue
            text = strip_tags(body)
            day = parse_date(title) or parse_date(text[:400])
            if not day:
                K.log("no date", i, title[:60])
                continue
            oldest = min(oldest, day) if oldest else day
            if not (start <= day <= end):
                continue
            row = parse_bulletin(text)
            if all(v is None for v in row.values()):
                unparsed += 1
                n = shown.get(day.year, 0)
                if n < 2:          # two samples per year are enough to see the wording the patterns miss
                    shown[day.year] = n + 1
                    # the page starts with the site menu; print what follows it, and any attachments the page links
                    tail = text.split("資訊服務", 1)[-1]
                    files = re.findall(r'(?:href|src)="([^"]+\.(?:pdf|odt|ods|jpg|jpeg|png|docx?))"', body, re.I)
                    K.log("unparsed", day, i, "len", len(text), "files", files[:3], "|", tail[:420])
                continue
            found += 1
            for key, sid in (("total", "pla_aircraft"), ("median", "pla_median"), ("vessels", "pla_vessels"), ("official", "pla_official_ships")):
                if row[key] is not None:
                    parsed[sid].setdefault(day.isoformat(), float(row[key]))
            if found <= 5 or found % 100 == 0:
                K.log("sample", day, row)
            time.sleep(0.2)
        K.log("page", page, "entries", len(new), "oldest", oldest, "days parsed", len(parsed["pla_aircraft"]))
        for sid, rows in parsed.items():      # saved page by page: a long crawl that is cut off keeps what it read
            K.save(sid, rows)
        if oldest and oldest < start:
            break
    for sid, rows in parsed.items():
        K.save(sid, rows)
    # community archive: fills any day the crawl missed
    try:
        txt = K.get("https://raw.githubusercontent.com/ypcat/plavis/main/data/pla_activity.csv", raw=True).decode()
        com = {s: {} for s in have}
        for r in csv.DictReader(io.StringIO(txt)):
            for col, sid in (("total_aircraft", "pla_aircraft"), ("median_crossings", "pla_median"), ("plan_vessels", "pla_vessels"), ("official_ships", "pla_official_ships")):
                if r.get(col) not in (None, ""):
                    com[sid][r["date"]] = float(r[col])
        for sid, rows in com.items():
            cur = K.load(sid)
            K.save(sid, {d: v for d, v in rows.items() if d not in cur})
        K.log("plavis rows", {s: len(v) for s, v in com.items()})
    except RuntimeError as e:
        K.log("plavis unavailable", str(e)[:100])
    K.log({s: len(K.load(s)) for s in have})
