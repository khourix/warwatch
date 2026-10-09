"""Parse the Japan Coast Guard Senkaku PDFs' text (backfill/data/senkaku/raw) into daily series, checked against each month's totals.

Writes backfill/data/senkaku_contig.csv and senkaku_terr.csv (date,value). Each month's parsed days and vessel counts must
equal the totals printed at the foot of that month's PDF; a month that does not match is left out and listed.
"""
import calendar
import datetime as dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "senkaku", "raw")
FW = str.maketrans("０１２３４５６７８９／", "0123456789/")


def ym(name):
    m = re.match(r"data_(h|R)(\d*)_(\d+)", name)
    era, y, mo = m.group(1), m.group(2), int(m.group(3))
    return (1988 + int(y), mo) if era == "h" else (2018 + int(y or 1), mo)


def parse(text, year, month):
    lines = text.translate(FW).splitlines()
    rows = []
    for ln in lines:
        if "隻" in ln or "現在" in ln or "状況" in ln or "年" in ln or "月" in ln:
            continue
        toks = [(m.start(), int(m.group())) for m in re.finditer(r"(?<![A-Za-z0-9])\d+", ln)]
        if toks:
            rows.append(toks)
    starts = [t[0][0] for t in rows if t[0][1] == 1]
    if not starts:
        return None
    p0 = starts[0]
    cand = [p for t in rows for p, v in t if 16 <= v <= 31 and p > p0 + 25]
    p1 = max(set(cand), key=cand.count)
    contig, terr = {}, {}
    for t in rows:
        for base in (p0, p1):
            day = [v for p, v in t if abs(p - base) <= 1]
            if not day:
                continue
            d = day[0]
            for p, v in t:
                off = p - base
                if 2 <= off <= 26 and (base == p1 or p < p1 - 2):
                    (contig if off < 13 else terr)[d] = v
    n = calendar.monthrange(year, month)[1]
    asof = re.search(r"\((\d+)/(\d+)現在\)", text.translate(FW).replace(" ", ""))
    last = int(asof.group(2)) if asof and int(asof.group(1)) == month else n
    return {dt.date(year, month, d): (contig.get(d, 0), terr.get(d, 0)) for d in range(1, last + 1)}


def totals(text):
    t = text.translate(FW).replace(" ", "")
    a = re.search(r"接続水域入域；(\d+)日、のべ(\d+)隻", t)
    b = re.search(r"領海侵入\(接続水域入域の内数\)；(\d+)日、のべ(\d+)隻", t)
    return tuple(int(x) for x in a.groups() + b.groups()) if a and b else None


def main():
    out, bad = {}, []
    for f in sorted(os.listdir(RAW)):
        y, m = ym(f)
        txt = open(os.path.join(RAW, f)).read()
        res, tot = parse(txt, y, m), totals(txt)
        if res is None or tot is None:
            bad.append((f, "unreadable", tot))
            continue
        got = (sum(c > 0 for c, _ in res.values()), sum(c for c, _ in res.values()),
               sum(t > 0 for _, t in res.values()), sum(t for _, t in res.values()))
        if got != tot:
            bad.append((f, got, tot))
            continue
        out.update(res)
    for name, i in (("senkaku_contig", 0), ("senkaku_terr", 1)):
        with open(os.path.join(HERE, "data", name + ".csv"), "w") as fh:
            fh.write("".join(f"{d},{out[d][i]}\n" for d in sorted(out)))
    print(f"{len(out)} days, {min(out)} to {max(out)}; {len(bad)} months left out")
    for b in bad:
        print("  ", b)
    return bad


if __name__ == "__main__":
    sys.exit(1 if len(main()) > 12 else 0)
