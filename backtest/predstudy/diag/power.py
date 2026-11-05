"""Power of the shuffled-timing gate: how many years of forward record (or events) does it take to show a real within-theatre timing
signal of a given size? Semi-synthetic: the noise is the published model's own out-of-sample day-to-day movement within each theatre
(so its autocorrelation and regime shifts are real); events are drawn at the 2022-2025 rate per theatre; the signal is a step of size b
on the 30 days before each synthetic event, with b set so the within-theatre AUC equals the target."""
import os, sys, json
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base as BB
V = BB.V
o = BB.load()
P, y, lab, pub, ev = o["P"], o["y"], o["lab"], o["pub"], o["ev"]
yr = P["date"].dt.year.values
th = P["theatre"].values
okp = ~np.isnan(pub) & (yr >= 2021)
noise = {}
for t in V.TH:
    m = okp & (th == t)
    z = V.logit(pub[m])
    z = (z - z.mean()) / (z.std() + 1e-9)
    noise[t] = z
# event rates per theatre, 2022-2025 (the recent regime), events per day
evc = ev[~ev["dup"]] if "dup" in ev else ev
rec = evc[(evc["date"].dt.year >= 2022) & (evc["date"].dt.year <= 2025)]
rate = {t: max((rec["theatre"] == t).sum(), 0.5) / (4 * 365.0) for t in V.TH}
print("events per year, all theatres:", round(sum(rate.values()) * 365, 1))
ac = np.mean([np.corrcoef(noise[t][:-1], noise[t][1:])[0, 1] for t in V.TH])
ac30 = np.mean([np.corrcoef(noise[t][:-30], noise[t][30:])[0, 1] for t in V.TH])
print(f"noise autocorrelation lag1 {ac:.3f} lag30 {ac30:.3f}")

def auc_fast(yv, s):
    n1 = yv.sum(); n0 = len(yv) - n1
    if n1 == 0 or n0 == 0: return np.nan
    r = np.argsort(np.argsort(s, kind="mergesort"), kind="mergesort") + 1.0
    return (r[yv == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def sim(args):
    a_target, years, seed, nshift = args
    rng = np.random.default_rng(seed)
    b = np.sqrt(2) * __import__("scipy.stats", fromlist=["norm"]).norm.ppf(a_target)   # step size for Gaussian noise
    days = int(round(years * 365))
    series = []
    for t in V.TH:
        z = noise[t]
        start = rng.integers(0, len(z))
        idx = (start + np.arange(days)) % len(z)
        x = z[idx].copy()
        # events: Bernoulli per day at the theatre's rate, with 30 days off after each (as the labels do)
        ylab = np.zeros(days, int); excl = np.zeros(days, bool); d = 0; evs = []
        while d < days:
            if rng.random() < rate[t]:
                evs.append(d); d += 31
            else:
                d += 1
        for e in evs:
            ylab[max(0, e - 30):e] = 1
            x[max(0, e - 30):e] += b
            excl[e:min(days, e + 31)] = True
        keep = ~excl & (np.arange(days) < days - 30)      # last 30 days unknown, as in the forward record
        series.append((x, ylab, keep, len(evs)))
    def wauc(shifted=False):
        num = den = 0.0
        for x, yl, keep, _ in series:
            xx = np.roll(x, rng.integers(min(60, len(x) // 4), max(len(x) - 60, len(x) // 4 + 1))) if shifted else x
            yy, ss = yl[keep], xx[keep]
            n1 = yy.sum()
            if n1 == 0 or n1 == len(yy): continue
            num += n1 * auc_fast(yy, ss); den += n1
        return num / den if den else np.nan
    a = wauc()
    null = np.array([wauc(True) for _ in range(nshift)])
    nev = sum(s[3] for s in series)
    p = float(np.mean(null >= a)) if not np.isnan(a) else 1.0
    return a, p, nev

if __name__ == "__main__":
    out = {}
    targets = [0.55, 0.60, 0.65, 0.70]
    horizons = [0.25, 0.5, 1, 2, 4, 6, 10]
    NS = int(os.environ.get("NSIM", 120))
    with Pool(4) as pool:
        for a in targets:
            for T in horizons:
                res = pool.map(sim, [(a, T, 1000 * int(a * 100) + 10 * int(T * 4) + i, 200) for i in range(NS)])
                arr = np.array(res, dtype=float)
                pw = float(np.mean(arr[:, 1] < 0.05))
                pw_bonf = float(np.mean(arr[:, 1] < 0.0038))
                out[f"{a}_{T}"] = dict(a=a, years=T, power=pw, power_013=pw_bonf, events_med=float(np.median(arr[:, 2])), auc_obs_med=float(np.nanmedian(arr[:, 0])))
                print(f"AUC {a:.2f}  {T:>5} yrs  events~{np.median(arr[:,2]):.0f}  power(p<0.05) {pw:.2f}  power(p<0.0038) {pw_bonf:.2f}  obs AUC median {np.nanmedian(arr[:,0]):.3f}", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "power.json"), "w"), indent=1)
