"""Reduce downloaded ConflictForecast and VIEWS files to the forecast each vintage issued (backfill/data/forecasts/*.csv).

Every ConflictForecast vintage file repeats the model's fitted values back to 2010; only its last month is the forecast that
was published that month, so only that row is kept. The file layout changed twice (February 2024: probabilities as fractions
under `all` instead of percentages under `best_model`; September 2024: files renamed `ons_*_03`), so both are mapped to one
table: vintage, isocode, period (YYYYMM of the forecast row), text (news-text model), all (full model), as probabilities.
VIEWS keeps run, month_id, isoab, main_dich, main_mean for the theatres' countries, from the fatalities runs (Dec 2021 on).
"""
import csv
import glob
import os
import sys

from sources_forecasts import ALL

FAM = {"armedconf_3": ("armedconf_3", "ons_armedconf_03"), "anyviolence_3": ("anyviolence_3", "ons_anyviolence_03"),
       "armedconf_12": ("armedconf_12", "ons_armedconf_12"), "anyviolence_12": ("anyviolence_12", "ons_anyviolence_12")}


def cf_rows(path, vintage):
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return []
    last = {}
    for r in rows:
        if "year" in r:
            per, text, full = int(r["year"]) * 100 + int(r["month"]), float(r["text_model"]) / 100, float(r["best_model"]) / 100
        else:
            tcol = next((k for k in r if k.endswith("_text") or k == "text"), None)
            acol = next((k for k in r if k.endswith("_all") or k == "all"), None)
            per, text, full = int(r["period"]), float(r[tcol] or "nan"), float(r[acol] or "nan")
        if r["isocode"] not in last or per > last[r["isocode"]][0]:
            last[r["isocode"]] = (per, text, full)
    return [[vintage, iso, p, round(t, 5), round(a, 5)] for iso, (p, t, a) in sorted(last.items())]


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    for fam, names in FAM.items():
        out = []
        for vdir in glob.glob(os.path.join(src, "cf", "*")):
            v = os.path.basename(vdir)
            for n in names:
                p = os.path.join(vdir, f"conflictforecast_{n}.csv")
                if os.path.exists(p):
                    out += cf_rows(p, v)
        out.sort(key=lambda r: (r[0][3:], r[0][:2], r[1]))
        with open(os.path.join(dst, f"cf_{fam}.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["vintage", "isocode", "period", "text", "all"])
            w.writerows(out)
        print(fam, len(out), "rows")
    out, seen = [], set()
    for f in sorted(glob.glob(os.path.join(src, "views", "fatalities*.csv"))):     # the 2021 runs (r_*) cover Africa only
        run = os.path.basename(f)[:-4]
        for r in csv.DictReader(open(f)):      # the API ignores the iso filter and repeats rows across pages: filter and dedupe
            k = (run, r.get("month_id"), r.get("isoab"))
            if r.get("isoab") in ALL and r.get("main_dich") and k not in seen:
                seen.add(k)
                out.append([run, r["month_id"], r["isoab"], r["main_dich"], r.get("main_mean", "")])
    with open(os.path.join(dst, "views.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "month_id", "isoab", "main_dich", "main_mean"])
        w.writerows(out)
    print("views", len(out), "rows")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
