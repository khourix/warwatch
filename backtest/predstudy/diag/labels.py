import os, sys, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
V = BB.V
o = BB.load()
P, y, lab, pub, ev = o["P"], o["y"], o["lab"], o["pub"], o["ev"]
evc = ev[~ev["dup"]] if "dup" in ev else ev
U = {}
for t in V.TH:
    p = f"warwatch/history/cache/ucdp_deaths_{t}.csv"
    if os.path.exists(p):
        d = pd.read_csv(p, header=None, names=["month", "deaths"])
        U[t] = d.set_index("month")["deaths"]
U = pd.DataFrame(U).fillna(0)
U.index = pd.PeriodIndex(U.index, freq="M")
print("UCDP months", U.index.min(), U.index.max(), "theatres", list(U.columns))
yr_deaths = U.groupby(U.index.year).sum().sum(axis=1)
yr_events = evc.groupby(evc["date"].dt.year).size()
print(pd.DataFrame({"events": yr_events, "ucdp_deaths": yr_deaths}).loc[2018:2026])
# escalation labels: month deaths >= 25 and >= 2x trailing 6-month mean (and >= trailing max?) -> count
esc = []
for t in U.columns:
    s = U[t]
    tr = s.shift(1).rolling(6, min_periods=3).mean()
    m = (s >= 25) & (s >= 2 * tr.clip(lower=10))
    for per in s.index[m.fillna(False).values]:
        esc.append((t, per))
E = pd.DataFrame(esc, columns=["theatre", "month"])
print("escalation months (>=25 deaths and >=2x prior 6-month mean):", len(E), "of which 2021+:", (E["month"].dt.year >= 2021).sum())
print(E.groupby("theatre").size().to_dict())
# overlap with events.csv: is there a coded event in that theatre-month?
evm = set(zip(evc["theatre"], evc["date"].dt.to_period("M")))
print("escalation months that hold a coded event:", sum((t, m) in evm for t, m in esc), "/", len(esc))
# within-theatre AUC of the model's mean probability in the month before, for escalation months (monthly panel)
P2 = P.assign(pub=pub, m=P["date"].dt.to_period("M"))
ok = lab & ~np.isnan(pub)
mon = P2[ok].groupby(["theatre", "m"])["pub"].mean()       # mean published p during month m
rows = []
for (t, m), v in mon.items():
    if t not in U.columns: continue
    nxt = m + 1
    if nxt not in U.index: continue
    rows.append((t, m, v, int((t, nxt) in set(esc))))
R = pd.DataFrame(rows, columns=["theatre", "m", "p", "esc_next"])
R = R[R["m"].dt.year >= 2021]
num = den = 0
for t, g in R.groupby("theatre"):
    if 0 < g["esc_next"].sum() < len(g):
        num += g["esc_next"].sum() * V.auc(g["esc_next"].values, g["p"].values); den += g["esc_next"].sum()
print("months 2021+:", len(R), "escalation next month:", R["esc_next"].sum(), "pooled AUC", round(V.auc(R["esc_next"].values, R["p"].values), 3), "within-theatre AUC", round(num / den, 3))
