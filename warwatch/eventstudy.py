#!/usr/bin/env python3
"""Event-study backtest: how the model's published 30-day probability behaved around each past war, strike, drill or attack.

    python3 warwatch/eventstudy.py            # rolling-origin replay -> docs/BACKTEST_EVENTS.md, backtest/event_study.csv, backtest/alert_episodes.csv
    python3 warwatch/eventstudy.py --refresh  # rebuild the cached replay (backtest/cache/oos.pkl)

Reuses validate.py end to end, so the numbers are the model's own and strictly out of sample: each year from 2021 is scored by weights
fitted on earlier years only (30-day embargo), with the shrink toward the base rate fitted on earlier test years only. It adds what
MODEL.md does not show: event by event, how far ahead the probability moved and how often it cried wolf. Needs numpy, pandas, scipy.

Definitions (fixed here so they are not judged afterwards):
- A line is a published 30-day probability: Watch 5%, Elevated 10%, Critical 25% (validate.BANDS).
- Lead time for an event = days from the first day of the unbroken run of days at or above the line that is in force the day before the event,
  counting back at most 30 days. It is "none" if the probability was below the line the day before. Days inside the 30-day aftermath of an earlier
  event are not scored (the model is outside what it was validated on there).
- Fresh lead = the same, but only counting a run that began after the previous event's aftermath ended. A line that was already up before the
  window opens is capped at 30 days and marked "already up".
- Alert episode = a run of days at or above the line (gaps of up to 7 days are bridged). It is a hit if an event in that theatre follows within
  30 days of the episode's first day, a false alarm if none does, and aftermath if it starts inside an event's 30-day aftermath.
- "Signal added" compares with a history-only model (theatre base rate plus the conflict-history terms, no indicators): if that model reaches
  the line too, the indicators did not earn the alert.
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402
import validate as V  # noqa: E402

ROOT = os.path.dirname(HERE)
OOS = os.path.join(V.CACHE, "oos.pkl")
LAM = 3                       # ridge strength chosen in MODEL.md (out-of-sample Brier)
LINES = {"Watch": V.BANDS[0], "Elevated": V.BANDS[1], "Critical": V.BANDS[2]}
BRIDGE = 7
LOOKBACK = 30


def replay(refresh=False):
    """Out-of-sample published probability for every labelled theatre-day from 2021, from the full model and from a history-only model."""
    if os.path.exists(OOS) and not refresh:
        return pickle.load(open(OOS, "rb"))
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare()
    raw, base = V.rolling(P, X, y, lab, LAM)
    pub, gp = V.nested_published(P, raw, base, y, lab)
    nh = 1 + len(V.TH) + 3                      # intercept, theatre offsets, history terms: no indicator columns
    raw_h, base_h = V.rolling(P, X[:, :nh], y, lab, LAM)
    pub_h, _ = V.nested_published(P, raw_h, base_h, y, lab)
    # evidence strength for context: the mean of the three strongest family readings that day (0-5 scale)
    E = P[fams].fillna(0).values
    top3 = np.sort(E, axis=1)[:, -3:].mean(1)
    # raw output also on days that are labelled out (aftermath) so the series is continuous; flagged via lab
    d = P[["date", "theatre"]].copy()
    d["p"], d["p_hist"], d["base"], d["y"], d["lab"], d["eid"], d["top3"] = pub, pub_h, base, y, lab, eid, top3
    d["raw"] = raw
    out = {"d": d, "ev": ev, "through": through, "gp": gp, "fams": fams}
    os.makedirs(V.CACHE, exist_ok=True)
    pickle.dump(out, open(OOS, "wb"))
    return out


def runs(flag, bridge=BRIDGE):
    """Index ranges (start, end) of runs of True, bridging gaps of up to `bridge` False days."""
    idx = np.where(flag)[0]
    if not len(idx):
        return []
    out, s, last = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - last - 1 > bridge:
            out.append((s, last))
            s = i
        last = i
    out.append((s, last))
    return out


def per_event(o):
    d, ev = o["d"], o["ev"].reset_index(drop=True)
    rows = []
    for k, e in ev.iterrows():
        if e.date < pd.Timestamp("2021-01-01"):
            continue
        g = d[d.theatre == e.theatre].set_index("date").sort_index()
        # previous event in the theatre: its aftermath is not scored
        prev = ev[(ev.theatre == e.theatre) & (ev.date < e.date)].date.max()
        win = g.loc[e.date - pd.Timedelta(days=LOOKBACK):e.date - pd.Timedelta(days=1)]
        scored = win[win.lab & win.p.notna()]
        r = dict(date=e.date.date(), theatre=e.theatre, type=e.type, kind=e.surprise_or_buildup, market_moving=bool(e.market_moving),
                 description=e.description, days_scored=len(scored))
        if len(scored) < 10:
            r["status"] = "not scored (aftermath of an earlier event or no history)"
            rows.append(r)
            continue
        r["status"] = "scored"
        r["p_day1"] = float(scored.p.iloc[-1])
        r["p_day7"] = float(g.p.get(e.date - pd.Timedelta(days=7), np.nan))
        r["p_day30"] = float(g.p.get(e.date - pd.Timedelta(days=30), np.nan))
        r["p_max"] = float(scored.p.max())
        r["base"] = float(scored.base.iloc[-1])
        r["lift_day1"] = r["p_day1"] / r["base"]
        r["p_hist_day1"] = float(scored.p_hist.iloc[-1])
        # percentile of the day-before probability among this theatre's out-of-sample calm days (not within 60 days of an event)
        calm = g[g.lab & (g.y == 0) & g.p.notna()]
        r["pctile_day1"] = float((calm.p < r["p_day1"]).mean() * 100)
        for nm, line in LINES.items():
            col = g.p.reindex(pd.date_range(e.date - pd.Timedelta(days=LOOKBACK + 400), e.date - pd.Timedelta(days=1)))
            above = (col.values >= line)
            # unbroken run in force on the day before the event
            n = 0
            i = len(above) - 1
            while i >= 0 and above[i]:
                n += 1
                i -= 1
            fresh_lead = min(n, LOOKBACK) if n else 0
            up_before_window = n > LOOKBACK
            r[f"lead_{nm}"] = fresh_lead
            r[f"up_before_{nm}"] = up_before_window
            hist_above = (g.p_hist.reindex(win.index).values >= line)
            r[f"hist_only_{nm}"] = bool(hist_above[-1]) if len(hist_above) else False
            r[f"any_{nm}"] = bool((scored.p >= line).any())
        rows.append(r)
    return pd.DataFrame(rows)


def episodes(o, line_name="Watch"):
    d, ev = o["d"], o["ev"]
    line = LINES[line_name]
    out = []
    for t in V.TH:
        g = d[(d.theatre == t) & (d.date >= "2021-01-01")].sort_values("date").reset_index(drop=True)
        g = g[g.p.notna()].reset_index(drop=True)
        et = np.sort(ev.loc[ev.theatre == t, "date"].values)
        for s, e in runs((g.p.values >= line) & g.lab.values.astype(bool)):
            start, end = g.date[s], g.date[e]
            # hit: an event in the theatre falls after the episode starts and no later than 30 days after it ends
            nxt = et[et > np.datetime64(start)]
            days_to = (nxt[0] - np.datetime64(start)) / np.timedelta64(1, "D") if len(nxt) else np.inf
            late = (nxt[0] - np.datetime64(end)) / np.timedelta64(1, "D") if len(nxt) else np.inf
            seg = g.p.values[s:e + 1]
            out.append(dict(theatre=t, start=start.date(), end=end.date(), days=int((end - start).days + 1), peak=float(seg.max()),
                            outcome="hit" if late <= 30 else "false alarm", days_to_event=None if np.isinf(days_to) else int(days_to),
                            mean_hist_only=float(g.p_hist.values[s:e + 1].mean())))
    return pd.DataFrame(out)


def summarise(o, E, EP):
    d = o["d"]
    ok = d.lab & d.p.notna() & (d.date >= "2021-01-01")
    s = {}
    sc = E[E.status == "scored"]
    s["events_total"] = len(E)
    s["events_scored"] = len(sc)
    for nm, line in LINES.items():
        hit = sc[f"lead_{nm}"] > 0
        s[f"{nm}_hit"] = int(hit.sum())
        s[f"{nm}_median_lead"] = float(sc.loc[hit, f"lead_{nm}"].median()) if hit.any() else float("nan")
        s[f"{nm}_any"] = int(sc[f"any_{nm}"].sum())
        s[f"{nm}_hist_only"] = int(sc[f"hist_only_{nm}"].sum())
        calm = ok & (d.y == 0)
        s[f"{nm}_day_fpr"] = float((d.p[calm] >= line).mean())
    return s


def episode_stats(o, line_name):
    EP = episodes(o, line_name)
    if EP.empty:
        return EP, {}
    h = EP.outcome == "hit"
    long_ = EP.days > 60
    st = dict(n=len(EP), hits=int(h.sum()), false=int((~h).sum()), long=int(long_.sum()), long_hits=int((h & long_).sum()),
              median_days=float(EP.days.median()), false_days=int(EP.days[~h].sum()), hit_days=int(EP.days[h].sum()))
    return EP, st


# -- small pool-adjacent-violators isotonic fit, to avoid a scikit-learn dependency
def pav(x, y):
    order = np.argsort(x)
    xs, ys = x[order], y[order].astype(float)
    vals, wts, ends = [], [], []
    for i in range(len(xs)):
        vals.append(ys[i])
        wts.append(1.0)
        ends.append(xs[i])
        while len(vals) > 1 and vals[-2] >= vals[-1]:
            w = wts[-2] + wts[-1]
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / w
            e = ends[-1]
            vals[-2:], wts[-2:], ends[-2:] = [v], [w], [e]
    return np.array(ends), np.array(vals)


def iso_apply(model, x):
    ends, vals = model
    idx = np.clip(np.searchsorted(ends, x, side="left"), 0, len(vals) - 1)
    return vals[idx]


def platt(p, y, slope):
    """Fit logit(q) = c + b logit(p) (b fixed at 1 when slope is False) by maximum likelihood."""
    from scipy.optimize import minimize
    x = V.logit(p)

    def f(th):
        z = th[0] + (th[1] if slope else 1.0) * x
        return np.sum(np.logaddexp(0, z) - y * z)
    r = minimize(f, np.array([0.0, 1.0]), method="Nelder-Mead")
    return r.x[0], (r.x[1] if slope else 1.0)


def recalibrate(o):
    """Published probability vs what followed, by year and band, and three recalibrations each fitted on earlier test years only."""
    d = o["d"]
    yr = d.date.dt.year.values
    ok = (d.lab & d.p.notna()).values & (yr >= 2021)
    p, y = d.p.values, d.y.values
    q = {k: np.full(len(d), np.nan) for k in ("iso", "shift", "platt")}
    par = {}
    for Y in range(2023, 2027):          # needs two earlier test years to fit on
        tr = ok & (yr < Y)
        te = ok & (yr == Y)
        q["iso"][te] = iso_apply(pav(p[tr], y[tr]), p[te])
        c, _ = platt(p[tr], y[tr], False)
        q["shift"][te] = V.sigmoid(c + V.logit(p[te]))
        c2, b2 = platt(p[tr], y[tr], True)
        q["platt"][te] = V.sigmoid(c2 + b2 * V.logit(p[te]))
        par[Y] = (c, c2, b2)
    m = ok & ~np.isnan(q["iso"])
    base = d.base.values
    clim = V.brier(y[m], base[m])
    res = dict(n=int(m.sum()), par=par, brier_pub=V.brier(y[m], p[m]), brier_clim=clim, bss_pub=1 - V.brier(y[m], p[m]) / clim)
    for k in q:
        res["bss_" + k] = 1 - V.brier(y[m], q[k][m]) / clim
    edges = [0, 0.05, 0.10, 0.25, 1.01]
    rows = []
    for i in range(4):
        mm = m & (p >= edges[i]) & (p < edges[i + 1])
        rows.append((V.LEVELS[i], int(mm.sum()), float(p[mm].mean()), float(q["platt"][mm].mean()), float(y[mm].mean())))
    res["rows"] = rows
    res["years"] = [(Y, int((ok & (yr == Y)).sum()), float(p[ok & (yr == Y)].mean()), float(y[ok & (yr == Y)].mean()),
                     float(d.base.values[ok & (yr == Y)].mean())) for Y in range(2021, 2027)]
    return res


def indicator_value(o):
    """Do the indicators add anything beyond conflict history? Same days, same labels, full model against history-only."""
    d = o["d"]
    ok = (d.lab & d.p.notna() & d.p_hist.notna() & (d.date >= "2021-01-01")).values
    rows = []
    for nm, mask in (("All theatres", ok), ("Without Iran and Israel", ok & ~d.theatre.isin(["iran", "israel"]).values)):
        y = d.y.values[mask]
        b = d.base.values[mask]
        clim = V.brier(y, b)
        r = [nm, int(mask.sum()), int(y.sum())]
        for col in ("p", "p_hist"):
            p = d[col].values[mask]
            r += [V.auc(y, p), 1 - V.brier(y, p) / clim, float(y[p >= np.quantile(p, 0.9)].mean() / y.mean())]
        rows.append(r)
    return rows


def by_group(E):
    sc = E[E.status == "scored"].copy()
    out = []
    for key in ("theatre", "kind", "type", "market_moving"):
        for v, g in sc.groupby(key):
            out.append((key, str(v), len(g), int((g.lead_Watch > 0).sum()), int((g.lead_Elevated > 0).sum()), int((g.lead_Critical > 0).sum()),
                        float(g.lead_Watch[g.lead_Watch > 0].median()) if (g.lead_Watch > 0).any() else float("nan"), float(g.lift_day1.median())))
    return out


def fmt_p(x):
    return "n/a" if x != x else f"{x:.1%}"


def report(o, E, EP, stats, rec, ep_stats, iv):
    L = ["# Event-study backtest of the published probability", "",
         f"Generated by `warwatch/eventstudy.py`. Out-of-sample replay of the Phase 2 model (`docs/MODEL.md`) over {o['d'][o['d'].lab & o['d'].p.notna()].date.min().date()} to {o['d'][o['d'].lab & o['d'].p.notna()].date.max().date()}: "
         f"each year is scored by weights fitted on earlier years only. Events and their definition: `docs/EVENTS.md` ({len(o['ev'])} events; {stats['events_scored']} of the {stats['events_total']} from 2021 on could be scored, "
         "the rest fall inside the 30-day aftermath of an earlier event in the same theatre).", "",
         "The question: before each real event, how far ahead did the published 30-day probability rise to Watch (5%), Elevated (10%) or Critical (25%), and how often did it rise with no event following?", "",
         "## Headline", ""]
    n = stats["events_scored"]
    L += ["| Line | Events with the line up the day before | Events with the line reached at any point in the 30 days before | Median lead when up (days) | Share of calm days at or above the line | Also reached by history-only model |",
          "|---|---|---|---|---|---|"]
    for nm in LINES:
        L.append(f"| {nm} ({LINES[nm]:.0%}) | {stats[nm + '_hit']} of {n} | {stats[nm + '_any']} of {n} | {stats[nm + '_median_lead']:.0f} | {stats[nm + '_day_fpr']:.1%} | {stats[nm + '_hist_only']} of {n} |")
    L += ["", "'History-only' is a model with the same theatre base rates and conflict-history terms but no indicators. Where it reaches the line too, the alert comes from recent events in the theatre, not from the indicators. "
          "Lead is the unbroken run of days at or above the line ending the day before the event, capped at 30; zero means the line was not up the day before.", ""]
    L += ["## Do the indicators add anything beyond conflict history?", "",
          "Same out-of-sample days and labels, full model against the history-only model. Lift = event rate on the top 10% of days over the overall rate.", "",
          "| Days | Theatre-days | Positive | AUC full | Brier skill full | Lift full | AUC history-only | Brier skill history-only | Lift history-only |", "|---|---|---|---|---|---|---|---|---|"]
    for r in iv:
        L.append(f"| {r[0]} | {r[1]:,} | {r[2]:,} | {r[3]:.3f} | {r[4]:+.4f} | {r[5]:.2f}x | {r[6]:.3f} | {r[7]:+.4f} | {r[8]:.2f}x |")
    L += ["", "## Alert episodes and false alarms", "",
          "An episode is a run of days at or above the line (gaps up to 7 days bridged; the 30 days after an event are not scored, so they break a run). Hit = an event in the theatre follows the episode's start and comes no later than 30 days after its end. "
          "Long = lasted more than 60 days (a standing high-risk theatre, not a warning).", "",
          "| Line | Episodes | Hits | False alarms | Median length (days) | Long episodes (hits) | Days up in hits | Days up in false alarms | Precision (hits / episodes) |", "|---|---|---|---|---|---|---|---|---|"]
    for nm, st in ep_stats.items():
        pr = st["hits"] / st["n"] if st["n"] else float("nan")
        L.append(f"| {nm} | {st['n']} | {st['hits']} | {st['false']} | {st['median_days']:.0f} | {st['long']} ({st['long_hits']}) | {st['hit_days']} | {st['false_days']} | {fmt_p(pr)} |")
    L += ["", "Episode lists: `backtest/alert_episodes.csv` (Watch line).", ""]
    L += ["## Event by event", "",
          "Probability is the published 30-day probability the model would have shown, using only data public at the time. Lift = day-before probability over the theatre's base rate. "
          "Percentile = rank of the day-before probability among that theatre's calm days. Lead = days the line had been continuously up (30 = already up for at least 30 days).", "",
          "| Date | Theatre | Event | Type | Build-up? | 30 days before | 7 days before | Day before | Lift | Pctile | Lead Watch | Lead Elevated | Lead Critical | History-only at Watch |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in E.itertuples():
        if r.status != "scored":
            L.append(f"| {r.date} | {r.theatre} | {r.description} | {r.type} | {r.kind} | not scored (aftermath of an earlier event) | | | | | | | | |")
            continue
        ld = lambda v, up: ("none" if v == 0 else (f"{int(v)}+" if v >= LOOKBACK else str(int(v))))
        L.append(f"| {r.date} | {C.THEATRES[r.theatre]['name']} | {r.description} | {r.type} | {r.kind} | {fmt_p(r.p_day30)} | {fmt_p(r.p_day7)} | {fmt_p(r.p_day1)} | {r.lift_day1:.1f}x | {r.pctile_day1:.0f} | "
                 f"{ld(r.lead_Watch, 0)} | {ld(r.lead_Elevated, 0)} | {ld(r.lead_Critical, 0)} | {'yes' if r.hist_only_Watch else 'no'} |")
    L += ["", "## By group", "", "| Group | Value | Events | Watch up | Elevated up | Critical up | Median Watch lead | Median lift |", "|---|---|---|---|---|---|---|---|"]
    for k, v, n_, w, e_, c_, ml, lf in by_group(E):
        L.append(f"| {k} | {v} | {n_} | {w} | {e_} | {c_} | {'n/a' if ml != ml else f'{ml:.0f}'} | {lf:.1f}x |")
    L += ["", "## Calibration", "",
          "Is the published probability the right size? Mean published probability against the share of theatre-days that were followed by an event within 30 days, by year:", "",
          "| Year | Theatre-days | Mean published | Mean base rate used | Event rate that followed |", "|---|---|---|---|---|"]
    for Y, n_, mp, rate, bs in rec["years"]:
        L.append(f"| {Y} | {n_:,} | {fmt_p(mp)} | {fmt_p(bs)} | {fmt_p(rate)} |")
    L += ["", f"By band, 2023 to 2026 ({rec['n']:,} theatre-days, the years with two earlier test years to fit a recalibration on). 'Recalibrated' applies a two-parameter logistic correction fitted on earlier test years only:", "",
          "| Published band | Theatre-days | Mean published | Mean recalibrated | Event rate that followed |", "|---|---|---|---|---|"]
    for nm, n_, mp, mq, rate in rec["rows"]:
        L.append(f"| {nm} | {n_:,} | {fmt_p(mp)} | {fmt_p(mq)} | {fmt_p(rate)} |")
    L += ["", "Brier skill against each theatre's base rate over the same days (higher is better):", "",
          "| Version | Brier skill |", "|---|---|", f"| Published | {rec['bss_pub']:+.4f} |", f"| Level shift only (one parameter) | {rec['bss_shift']:+.4f} |",
          f"| Shift and slope (two parameters) | {rec['bss_platt']:+.4f} |", f"| Isotonic (monotone, many steps) | {rec['bss_iso']:+.4f} |", ""]
    return "\n".join(L)


def main():
    refresh = "--refresh" in sys.argv
    o = replay(refresh)
    E = per_event(o)
    ep_stats, EPW = {}, None
    for nm in LINES:
        EP, st = episode_stats(o, nm)
        ep_stats[nm] = st
        if nm == "Watch":
            EPW = EP
    stats = summarise(o, E, EPW)
    rec = recalibrate(o)
    os.makedirs(os.path.join(ROOT, "backtest"), exist_ok=True)
    E.to_csv(os.path.join(ROOT, "backtest", "event_study.csv"), index=False)
    EPW.to_csv(os.path.join(ROOT, "backtest", "alert_episodes.csv"), index=False)
    txt = report(o, E, EPW, stats, rec, ep_stats, indicator_value(o))
    with open(os.path.join(ROOT, "docs", "BACKTEST_EVENTS.md"), "w") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
