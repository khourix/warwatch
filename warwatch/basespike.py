#!/usr/bin/env python3
"""Base watch feasibility test (docs/BASESPIKE_PLAN.md, fixed before this ran): can free 10 m imagery see the base
changes that came before past strikes? Writes docs/BASESPIKE.md and chips in docs/basespike/.

    python3 warwatch/basespike.py           # needs numpy, scipy, rasterio, Pillow; reads Planetary Computer (no key)
"""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import basewatch as B  # noqa: E402
import imagery as I  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "BASESPIKE.md")
IMG = os.path.join(ROOT, "docs", "basespike")
CASES = [   # site, part, start, end, case date, expected direction, radar?, counts for the rule, what
    ("al_udeid", "apron", "2024-12-01", "2025-07-15", "2025-06-19", -1, True, True, "aircraft dispersed before Iran's strike of 23 Jun 2025"),
    ("nsa_bahrain", "harbour", "2025-07-01", "2026-03-15", "2026-02-26", -1, True, True, "US ships left port before the strikes of 28 Feb 2026"),
    ("diego_garcia", "apron", "2024-12-01", "2025-05-31", "2025-03-25", 1, False, True, "B-2 bombers deployed (reported from late March 2025)"),
    ("olenya", "apron", "2024-12-01", "2025-07-15", "2025-06-01", -1, True, False, "bombers present, then struck on 1 Jun 2025"),
]
PAIRS = [(m, t) for m in ("bright_m2", "blobs") for t in B.THRESHOLDS]


def log(*a):
    print(*a, flush=True)


def caught(zrows, case_day, sign):
    """Scenes within 7 days of the case date with z beyond Z_AT in the expected direction."""
    d0 = dt.date.fromisoformat(case_day)
    return [(d, z) for d, _, _, z in zrows if z is not None and abs((dt.date.fromisoformat(d) - d0).days) <= 7 and sign * z >= B.Z_AT]


def others(zrows, case_day):
    d0 = dt.date.fromisoformat(case_day)
    return [z for d, _, _, z in zrows if z is not None and abs((dt.date.fromisoformat(d) - d0).days) > 7]


def run():
    sites = {s["id"]: s for s in B.load_bases()}
    radar, optical = {}, {}
    for site, part, start, end, day, sign, use_radar, counts, what in CASES:
        rec = sites[site]
        if use_radar:
            rows = B.radar_rows(rec, start, end, budget=400, log=log)
            radar[site] = [r for r in rows if r["part"] == part]
            log(site, "radar scenes:", len(radar[site]))
        try:
            optical[site] = B.optical_rows(rec, start, end, budget=400, log=log)
        except Exception as e:
            log(site, "optical failed:", repr(e)[:200])
            optical[site] = []
        log(site, "clear optical scenes:", len(optical[site]))
    # score every radar pair
    res = {}
    for m, t in PAIRS:
        key = f"{m}@{t:g}"
        hit, fa_n, fa_k, detail = 0, 0, 0, {}
        for site, part, start, end, day, sign, use_radar, counts, what in CASES:
            if not use_radar:
                continue
            zr = B.scene_z(radar[site], key, part)
            c = caught(zr, day, sign)
            o = others(zr, day)
            detail[site] = (c, zr)
            if counts:
                hit += bool(c)
            fa_n += len(o)
            fa_k += sum(1 for z in o if abs(z) >= B.Z_AT)
        res[(m, t)] = {"hit": hit, "fa": fa_k / fa_n if fa_n else float("nan"), "n_other": fa_n, "detail": detail}
    best = sorted(PAIRS, key=lambda p: (-res[p]["hit"], res[p]["fa"] if res[p]["fa"] == res[p]["fa"] else 9))[0]
    # optical (Diego Garcia, and reported for every site)
    opt = {}
    for site, part, start, end, day, sign, use_radar, counts, what in CASES:
        rows = [dict(r, part="apron", orbit="S2") for r in optical[site]]
        zr = B.scene_z(rows, "objects", "apron")
        opt[site] = (caught(zr, day, sign), others(zr, day), zr)
    dg = opt["diego_garcia"]
    opt_fa = sum(1 for z in dg[1] if abs(z) >= B.Z_AT) / len(dg[1]) if dg[1] else float("nan")
    leading = [c for c in CASES if c[7]]
    got = res[best]["hit"] + bool(dg[0])
    go = got >= 2 and res[best]["fa"] <= 0.10
    chips(sites, optical)
    write(res, best, opt, opt_fa, got, go, radar, optical)
    log("GO" if go else "NO-GO", "best", best, "hits", got, "fa", res[best]["fa"])
    return go, best


def chips(sites, optical):
    """True-colour chips at the clear dates nearest before and after each case date."""
    for site, part, start, end, day, sign, use_radar, counts, what in CASES:
        rows = optical.get(site) or []
        before = [r for r in rows if r["date"] < day]
        after = [r for r in rows if r["date"] >= day]
        bbox = B.site_bbox(sites[site])
        for k, r in (("before", before[-1] if before else None), ("after", after[0] if after else None)):
            if r:
                try:
                    I.chip_s2(r["_item"], bbox, os.path.join(IMG, f"{site}_{k}_{r['date']}.jpg"))
                except Exception as e:
                    log(site, "chip failed:", repr(e)[:120])


def write(res, best, opt, opt_fa, got, go, radar, optical):
    f = lambda x: "n/a" if x != x else f"{x:.0%}"     # noqa: E731
    L = ["# Base watch feasibility test: result", "",
         f"Written by `warwatch/basespike.py` on {dt.date.today()} to the plan fixed before it ran ([BASESPIKE_PLAN.md](BASESPIKE_PLAN.md)).", "",
         f"**Verdict: {'GO' if go else 'NO-GO'}.** {got} of 3 leading cases caught; the chosen radar pair is "
         f"`{best[0]}` at VV ≥ {best[1]:g} dB, with a false-alarm rate of {f(res[best]['fa'])} on the other scenes "
         f"(the rule needs at least 2 cases and 10% or less).", "",
         "## Radar pairs (Sentinel-1, Al Udeid, Bahrain and Olenya)", "",
         "| Metric | VV threshold | Leading cases caught (of 2 radar) | False-alarm rate | Other scenes |", "|---|---:|---:|---:|---:|"]
    for m, t in PAIRS:
        r = res[(m, t)]
        L.append(f"| {m} | {t:g} dB | {r['hit']} | {f(r['fa'])} | {r['n_other']} |")
    L += ["", "## Each case with the chosen radar pair", ""]
    for site, part, start, end, day, sign, use_radar, counts, what in CASES:
        L.append(f"### {site}: {what} ({day})")
        L.append("")
        if use_radar:
            c, zr = res[best]["detail"][site]
            L.append(f"Radar scenes: {len(zr)}. Caught: {'yes, ' + ', '.join(f'{d} (z {z:+.1f})' for d, z in c) if c else 'no'}.")
            L.append("")
            near = [x for x in zr if abs((dt.date.fromisoformat(x[0]) - dt.date.fromisoformat(day)).days) <= 30]
            if near:
                L += ["| Date | Orbit | Value | z |", "|---|---|---:|---:|"]
                L += [f"| {d} | {o} | {v:.0f} | {'' if z is None else f'{z:+.1f}'} |" for d, o, v, z in near]
                L.append("")
        else:
            L += ["No Sentinel-1 coverage at this site: optical only.", ""]
        oc, oo, ozr = opt[site]
        L.append(f"Optical (Sentinel-2, clear scenes): {len(optical.get(site) or [])} scenes. Caught: "
                 f"{'yes, ' + ', '.join(f'{d} (z {z:+.1f})' for d, z in oc) if oc else 'no'}.")
        near = [x for x in ozr if abs((dt.date.fromisoformat(x[0]) - dt.date.fromisoformat(day)).days) <= 30]
        if near:
            L += ["", "| Date | Object pixels | z |", "|---|---:|---:|"] + [f"| {d} | {v:.0f} | {'' if z is None else f'{z:+.1f}'} |" for d, _, v, z in near]
        imgs = sorted(n for n in os.listdir(IMG) if n.startswith(site + "_")) if os.path.isdir(IMG) else []
        if imgs:
            L += ["", " ".join(f"![{n[:-4]}](basespike/{n})" for n in imgs), "", "Contains modified Copernicus Sentinel data 2024–2026."]
        L.append("")
    L += ["## Optical false-alarm rate (Diego Garcia)", "", f"{f(opt_fa)} of the other clear scenes reached |z| ≥ {B.Z_AT:g}.", ""]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
