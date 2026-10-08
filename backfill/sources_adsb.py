"""Back-fill of military aircraft counts per theatre from the adsb.lol daily archives (GitHub releases of adsblol/globe_history_YYYY).

Each day is a ~2 GB tar split in two release assets: readsb "trace_full" files, one per aircraft, each a gzipped JSON with the
registration database flags (`dbFlags`, bit 1 = military), the ICAO type code (`t`) and every recorded position. The stream is read once,
never stored: military traces are kept, the rest are skipped after one byte-level check.

Value written per theatre and class: how many different military aircraft of that class were seen inside the theatre's box on that UTC day.
The live series counts aircraft present at one instant, so its level is lower; the two are NOT interchangeable. validate.py scores each on its own baseline.
`adsb_global_mil` (military aircraft seen anywhere that day) is written as a denominator, because the feeder network grew over the period.
"""
import datetime as dt
import gzip
import json
import re
import tarfile
import urllib.request

import common as K
import config as C
import sources as S

CLASSES = {"lift": S.AIRLIFT, "tanker": S.TANKER, "isr": S.ISR, "fighter": S.FIGHTER}
FLAGS = re.compile(rb'"dbFlags":\s*(\d+)')
TAGS = re.compile(r"^v(\d{4})\.(\d{2})\.(\d{2})-planes-readsb-(prod|staging)-0$")


def releases(years, token=None):
    """-> {date: [(url, ...)]} one entry per day: the prod release's assets, else staging's."""
    best = {}
    for y in years:
        page = 1
        while True:
            hdr = {"Accept": "application/vnd.github+json"}
            if token:
                hdr["Authorization"] = "Bearer " + token
            try:
                rows = K.get(f"https://api.github.com/repos/adsblol/globe_history_{y}/releases?per_page=100&page={page}", headers=hdr)
            except RuntimeError:
                break
            if not rows:
                break
            for r in rows:
                m = TAGS.match(r["tag_name"])
                if not m:
                    continue
                d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                urls = [a["browser_download_url"] for a in sorted(r["assets"], key=lambda a: a["name"]) if ".tar." in a["name"]]
                if urls and (d not in best or (m.group(4) == "prod" and best[d][0] != "prod")):
                    best[d] = (m.group(4), urls)
            page += 1
    return {d: v[1] for d, v in best.items()}


class Chain:
    """Several HTTP bodies read back to back as one stream."""
    def __init__(self, urls):
        self.urls = list(urls)
        self.cur = None

    def read(self, n=-1):
        out = b""
        while n < 0 or len(out) < n:
            if self.cur is None:
                if not self.urls:
                    break
                req = urllib.request.Request(self.urls.pop(0), headers=K.UA)
                self.cur = urllib.request.urlopen(req, timeout=300)
            b = self.cur.read(-1 if n < 0 else n - len(out))
            if not b:
                self.cur.close()
                self.cur = None
                continue
            out += b
        return out


def classify(t):
    return [c for c, s in CLASSES.items() if t in s]


def count_trace(header, points, boxes, seen):
    """Add one military aircraft's hex to seen[(theatre, class)] for every theatre box it entered."""
    hexid = header.get("icao")
    classes = ["mil"] + classify(header.get("t"))
    seen[("global", "mil")].add(hexid)
    hit = set()
    for p in points:
        la, lo = p[1], p[2]
        if la is None or lo is None:
            continue
        for th, (la0, la1, lo0, lo1) in boxes.items():
            if th not in hit and la0 <= la <= la1 and lo0 <= lo <= lo1:
                hit.add(th)
        if len(hit) == len(boxes):
            break
    for th in hit:
        for c in classes:
            seen[(th, c)].add(hexid)


def run_day(urls, boxes):
    seen = {("global", "mil"): set()}
    for th in boxes:
        for c in ["mil"] + list(CLASSES):
            seen[(th, c)] = set()
    n_files = n_mil = 0
    tf = tarfile.open(fileobj=Chain(urls), mode="r|")
    for m in tf:
        if not m.isfile() or "trace_full" not in m.name:
            continue
        n_files += 1
        b = tf.extractfile(m).read()
        if b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        f = FLAGS.search(b[:600])
        if not f or not int(f.group(1)) & 1:
            continue
        n_mil += 1
        d = json.loads(b)
        count_trace(d, d.get("trace", []), boxes, seen)
    return {k: float(len(v)) for k, v in seen.items()}, n_files, n_mil


def cmd_adsb(start, end, step=1, token=None):
    boxes = dict(C.BOXES)
    avail = releases(range(start.year, end.year + 1), token)
    todo = [d for d in K.days(start, end) if (d - start).days % step == 0 and d in avail]
    K.log("adsb: days with an archive", len(todo), "of", (end - start).days + 1)
    have = K.load("adsb_global_mil")
    for d in todo:
        if d.isoformat() in have:
            continue
        try:
            res, nf, nm = run_day(avail[d], boxes)
        except Exception as e:     # a truncated or missing asset: leave the day empty and move on
            K.log("fail", d, str(e)[:120])
            continue
        for (th, c), v in res.items():
            K.save("adsb_global_mil" if th == "global" else f"adsb_{th}_{c}", {d.isoformat(): v})
        K.log("ok", d, "traces", nf, "military", nm, {k: int(v) for k, v in res.items() if k[1] in ("mil",) and v})
