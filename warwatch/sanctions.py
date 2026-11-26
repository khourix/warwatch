#!/usr/bin/env python3
"""Sanctioned ships and aircraft from the US Treasury's SDN list (OFAC, public domain), for matching against what WarWatch hears
on AIS (aiswatch.py) and sees in the adsb.lol archive (flights.py). Argos review, item 3.

    python3 warwatch/sanctions.py refresh     # download the SDN list, write warwatch/data/sanctions_ofac.csv (slow.yml, daily)

The list holds vessels with their IMO number (and often MMSI) and aircraft with their tail number and Mode S code. A sanctioned
civil cargo aircraft carries no military flag, so the military-aircraft counts miss it; a sanctioned tanker is the shadow fleet.
Matching history against today's list counts ships and aircraft designated later as if they were known then, so a backtest on the
adsb.lol archive must use the designation date (SDN remarks carry none; the OFAC recent-actions pages do).
"""
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as S  # noqa: E402

SDN_URLS = (("https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV",
             "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_COMMENTS.CSV"),
            ("https://www.treasury.gov/ofac/downloads/sdn.csv", "https://www.treasury.gov/ofac/downloads/sdn_comments.csv"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sanctions_ofac.csv")
HEAD = ["kind", "key", "name", "program"]   # kind: imo, mmsi, tail (registration without '-'), hex (Mode S, lower case)
IMO = re.compile(r"\bIMO\s*(\d{7})\b")
MMSI = re.compile(r"\bMMSI\s*(\d{9})\b")
TAIL = re.compile(r"Aircraft Tail Number\s+([A-Z0-9][A-Z0-9-]{2,9})", re.I)
MODE_S = re.compile(r"Mode S Transponder Code\s+([0-9A-F]{6})\b", re.I)


def norm_tail(r):
    return re.sub(r"[^A-Z0-9]", "", (r or "").upper())


def _blank(v):
    v = (v or "").strip()
    return "" if v == "-0-" else v


def parse_sdn(sdn_text, comments_text=""):
    """SDN.CSV (no header: ent_num, name, type, program, title, call sign, vessel type, tonnage, GRT, flag, owner, remarks) and
    SDN_COMMENTS.CSV (ent_num, the rest of long remarks) -> sorted rows [kind, key, name, program]."""
    more = {}
    for r in csv.reader(io.StringIO(comments_text or "")):
        if len(r) >= 2:
            more[r[0].strip()] = more.get(r[0].strip(), "") + " " + r[1]
    out = set()
    for r in csv.reader(io.StringIO(sdn_text or "")):
        if len(r) < 12:
            continue
        ent, name, typ, prog = r[0].strip(), _blank(r[1]), _blank(r[2]).lower(), _blank(r[3])
        remarks = _blank(r[11]) + more.get(ent, "")
        if typ == "vessel":
            for k in IMO.findall(remarks):
                out.add(("imo", k, name, prog))
            for k in MMSI.findall(remarks):
                out.add(("mmsi", k, name, prog))
        elif typ == "aircraft":
            tails = TAIL.findall(remarks) or ([name] if re.match(r"^[A-Z0-9]{1,2}-[A-Z0-9]{2,5}$", name) else [])
            for k in tails:
                out.add(("tail", norm_tail(k), name, prog))
            for k in MODE_S.findall(remarks):
                out.add(("hex", k.lower(), name, prog))
    return sorted(list(x) for x in out)


def refresh(path=OUT, get=None):
    """Downloads the list (the sanctions list service, else the Treasury mirror) and writes the rows. -> number of rows."""
    get = get or S.get
    err = None
    for sdn, com in SDN_URLS:
        try:
            rows = parse_sdn(get(sdn, raw=True, retries=2, timeout=180), get(com, raw=True, retries=2, timeout=180))
            break
        except Exception as e:
            err = e
    else:
        raise RuntimeError(f"SDN list failed: {str(err)[:200]}")
    if not any(r[0] == "imo" for r in rows):
        raise RuntimeError("SDN list parsed with no vessel IMO numbers: the format changed")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    return len(rows)


_W = {}


def watch(path=OUT):
    """{kind: {key: name}} from the saved list, or {} when it has not been downloaded yet."""
    if path not in _W:
        got = {}
        try:
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    got.setdefault(r["kind"], {})[r["key"]] = r["name"]
        except OSError:
            pass
        _W[path] = got
    return _W[path]


def aircraft_match(header, w=None):
    """An adsb.lol trace header ({'r': registration, 'icao': hex}) -> the sanctioned name, or ''."""
    w = watch() if w is None else w
    return (w.get("tail") or {}).get(norm_tail(header.get("r"))) or (w.get("hex") or {}).get(str(header.get("icao") or "").lower()) or ""


def ship_match(imo, mmsi, w=None):
    w = watch() if w is None else w
    return (w.get("imo") or {}).get(str(imo or "")) or (w.get("mmsi") or {}).get(str(mmsi or "")) or ""


if __name__ == "__main__":
    if sys.argv[1:] == ["refresh"]:
        print("sanctions: rows written", refresh())
    else:
        sys.exit(__doc__)
