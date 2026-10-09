"""New free sources against past events, each to the plan fixed before its data was read.

Same method as warwatch/wikistudy.py and warwatch/indicatorstudy.py: every series is scored day by day as the live build
would have scored it (a day's data public the next day), and the highest z in the 30 days before each event is compared
with the same measure in calm 30-day windows of the same theatre, on the original and the added events separately.

    python3 warwatch/sourcestudy.py pla        Taiwan's daily PLA counts            -> docs/PLASTUDY.md
    python3 warwatch/sourcestudy.py gdeltwide  wider GDELT event types and dyads    -> docs/GDELTWIDE.md  (docs/GDELTWIDE_PLAN.md)
    python3 warwatch/sourcestudy.py senkaku    Japan Coast Guard Senkaku counts     -> docs/SENKAKU.md    (docs/SENKAKU_PLAN.md)
"""
import csv
import datetime as dt
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indicatorstudy as S  # noqa: E402
import stats  # noqa: E402
import validate as V  # noqa: E402

DATA = os.path.join(V.ROOT, "backfill", "data")
DOCS = os.path.join(V.ROOT, "docs")


def zdaily(pts, sign=1, kind="daily", lag=1):
    """{day public: z in the warning direction} for sorted (iso day, value) points."""
    z = {}
    for i in range(len(pts)):
        d = dt.date.fromisoformat(pts[i][0])
        if d < S.FROM - dt.timedelta(S.LEAD + 31):
            continue
        r = stats.score_series(pts[max(0, i + 1 - V.KEEP):i + 1], kind)
        if r is not None:
            z[d + dt.timedelta(lag)] = sign * r["z"]
    return z


def test(zs, alpha_added=0.05):
    """zs: {theatre: {day: z}} -> stats on original and added events, and the plan's pass rule."""
    on, allev = S.events()
    ev, calm = [], []
    for th, z in zs.items():
        if len(z) < 200:
            continue
        near = set()
        for d in allev.get(th, []):
            near.update(d + dt.timedelta(k) for k in range(-S.LEAD, S.GAP + 1))
        for r in on[on.theatre == th].itertuples():
            w = S.window_max(z, r.date)
            if w is not None:
                ev.append((w, r.added, th, r.date, r.description))
        d = max(S.FROM, min(z) + dt.timedelta(S.LEAD))
        while d <= max(z):
            if d not in near:
                w = S.window_max(z, d)
                if w is not None:
                    calm.append(w)
            d += dt.timedelta(S.CALM_STEP)
    fa = float(np.mean([c >= S.CUT for c in calm])) if calm else float("nan")
    out = {"calm": len(calm), "fa": fa, "events": ev, "theatres": sorted(zs)}
    for nm, sel in (("orig", lambda a: not a), ("added", lambda a: a)):
        w = [x[0] for x in ev if sel(x[1])]
        k = int(sum(x >= S.CUT for x in w))
        out[nm] = {"n": len(w), "hits": k, "hit": k / len(w) if w else float("nan"),
                   "p": S.binom_tail(k, len(w), fa) if w else float("nan"), "auc": S.auc(w, calm)}
    o, a = out["orig"], out["added"]
    out["pass"] = bool(a["n"] and o["n"] and a["p"] < alpha_added and o["p"] < 0.10 and o["auc"] > 0.55 and a["auc"] > 0.55)
    return out


def write(path, title, intro, res, note=""):
    f = lambda x, s: "n/a" if x != x else format(x, s)      # noqa: E731
    L = [f"# {title}", "", intro, "",
         f"Hit = z reached {S.CUT:g} in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.", "",
         "| Family | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for fam, r in res.items():
        o, a = r["orig"], r["added"]
        L.append(f"| {fam} | {r['calm']} | {f(r['fa'], '.0%')} | {o['n']} | {f(o['hit'], '.0%')} | {f(o['p'], '.3f')} | {f(o['auc'], '.2f')} | "
                 f"{a['n']} | {f(a['hit'], '.0%')} | {f(a['p'], '.3f')} | {f(a['auc'], '.2f')} | {'yes' if r['pass'] else 'no'} |")
    if note:
        L += ["", note]
    L += ["", "## Events where the series reached z 2 or more in the 30 days before", "",
          "| Family | Theatre | Date | Event | Max z | List |", "|---|---|---|---|---:|---|"]
    for fam, r in res.items():
        for w, added, th, d, desc in sorted(r["events"], key=lambda x: x[3]):
            if w >= S.CUT:
                L.append(f"| {fam} | {th} | {d} | {desc} | {w:.1f} | {'added' if added else 'original'} |")
    L.append("")
    open(path, "w").write("\n".join(L))


def _csv_points(p):
    with open(p) as fh:
        return [(r.split(",")[0], float(r.split(",")[1])) for r in fh.read().split() if r[:1].isdigit()]


def pla():
    res = {}
    for nm in ("pla_aircraft", "pla_vessels"):
        p = os.path.join(DATA, nm + ".csv")
        if os.path.exists(p):
            res[nm] = test({"taiwan": zdaily(_csv_points(p))})
    write(os.path.join(DOCS, "PLASTUDY.md"), "Taiwan's daily PLA counts against past events",
          "Written by `warwatch/sourcestudy.py pla`. Daily counts of PLA aircraft and naval vessels around Taiwan from Taiwan's "
          "Ministry of National Defense (back-filled from August 2022), scored as the live build scores a daily count and tested "
          "on the Taiwan events with the indicator study's method.", res,
          "Too few Taiwan events fall inside the archive to judge either series. The archive starts in August 2022 and the yearly "
          "baseline needs most of a year, so only the events from mid-2023 can be scored. Read the table as a description, not a test.")
    return res


GW = {   # family: (numerator column(s), denominator column, minimum denominator, sign, mean instead of per 1,000)
    "gw_milthreat": (("loc_mil138",), "loc_all", 50, 1, False),
    "gw_mobilise": (("loc_mob",), "loc_all", 50, 1, False),
    "gw_coerce": (("loc_coerce",), "loc_all", 50, 1, False),
    "gw_material": (("loc_q4",), "loc_all", 50, 1, False),
    "gw_goldstein": (("loc_gold",), "loc_all", 50, -1, True),
    "gw_dyadhostile": (("dy_q34",), "dy_all", 10, 1, False),
    "gw_dyadforce": (("dy_force",), None, 0, 1, False),
    "gw_dyadgoldstein": (("dy_gold",), "dy_all", 10, -1, True),
}


def gdeltwide():
    rows = {}
    for p in sorted(glob.glob(os.path.join(DATA, "gdeltwide", "*.csv"))):
        with open(p) as fh:
            for r in csv.DictReader(fh):
                rows.setdefault(r["theatre"], {})[r["day"]] = {k: float(v) for k, v in r.items() if k not in ("day", "theatre")}
    res = {}
    for fam, (num, den, mn, sign, mean) in GW.items():
        zs = {}
        for th, days in rows.items():
            pts = []
            for d in sorted(days):
                x = days[d]
                n = sum(x[c] for c in num)
                if den is None:
                    pts.append((d, n))
                elif x[den] >= mn:
                    pts.append((d, n / x[den] if mean else 1000.0 * n / x[den]))
            zs[th] = zdaily(pts, sign)
        res[fam] = test(zs, alpha_added=0.05 / len(GW))
    days = sorted({d for v in rows.values() for d in v})
    write(os.path.join(DOCS, "GDELTWIDE.md"), "Wider GDELT event types against past events",
          f"Written by `warwatch/sourcestudy.py gdeltwide` to the plan fixed before the data was read ([GDELTWIDE_PLAN.md](GDELTWIDE_PLAN.md)). "
          f"{len(days)} days of GDELT files, {days[0] if days else '-'} to {days[-1] if days else '-'}. Pass rule: added events p < 0.00625, "
          "original events p < 0.10, AUC above 0.55 on both.", res)
    return res


def senkaku():
    res = {}
    for nm in ("senkaku_contig", "senkaku_terr"):
        z = zdaily(_csv_points(os.path.join(DATA, nm + ".csv")))
        res[nm] = test({"taiwan": z, "scs": z}, alpha_added=0.05 / 2)
    write(os.path.join(DOCS, "SENKAKU.md"), "Senkaku vessel counts against past events",
          "Written by `warwatch/sourcestudy.py senkaku` to the plan fixed before the data was read ([SENKAKU_PLAN.md](SENKAKU_PLAN.md)). "
          "Daily China Coast Guard vessels around the Senkaku Islands (Japan Coast Guard), parsed by `backfill/senkaku_parse.py` and checked "
          "against each month's printed totals, tested against the Taiwan and South China Sea events. Pass rule: added events p < 0.025, "
          "original events p < 0.10, AUC above 0.55 on both.", res)
    return res


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "pla"
    r = {"pla": pla, "gdeltwide": gdeltwide, "senkaku": senkaku}[what]()
    for fam, x in r.items():
        print(fam, {k: x[k] for k in ("calm", "fa", "orig", "added", "pass")})
