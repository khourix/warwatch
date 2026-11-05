"""Single-family null for the pre-specified AI-GPR families: within-theatre AUC of each alone vs the same series with its timing
shifted (circular shift within theatre, offsets of at least 180 days), 300 draws; also within theatre-year. Run from the repo root."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "warwatch"))
import predstudy as PS
import timingstudy as TS
import validate as V
TS.FAMS.update(PS.CANDS)
st = TS.Study(quick=True)
S_ = st.setup(["G1", "G2"])
P, y, lab, eid = S_["P"], S_["y"], S_["lab"], S_["eid"]
yr = P["date"].dt.year.values; th = P["theatre"].values; core = S_["core"]
def wauc(x, by_year=False):
    """Within-theatre AUC (by_year: within theatre x calendar year, which removes slow multi-year co-movement)."""
    ok = lab & ~np.isnan(x) & (yr >= 2021) & core
    num = den = 0.0
    for t in V.TH:
        for Y in (sorted(set(yr[ok])) if by_year else [None]):
            m = ok & (th == t) & ((yr == Y) if by_year else True)
            n1 = y[m].sum()
            if n1 == 0 or n1 == m.sum(): continue
            num += n1 * V.auc(y[m], x[m]); den += n1
    return num / den if den else np.nan
rng = np.random.default_rng(7)
out = {}
for f in ("aigpr_pair", "aigpr_country", "aigpr_milconf"):
    x0 = P[f].values.astype(float)
    obs, obs_y = wauc(x0), wauc(x0, True)
    null, null_y = [], []
    for k in range(300):
        x = x0.copy()
        for t in V.TH:
            m = np.where(th == t)[0]
            if len(m) < 400: continue
            x[m] = np.roll(x[m], rng.integers(180, len(m) - 180))
        null.append(wauc(x)); null_y.append(wauc(x, True))
    null, null_y = np.array(null), np.array(null_y)
    out[f] = {"obs": obs, "null_mean": float(np.nanmean(null)), "null_sd": float(np.nanstd(null)), "p": float(np.nanmean(null >= obs)),
              "obs_theatre_year": obs_y, "null_mean_theatre_year": float(np.nanmean(null_y)), "null_sd_theatre_year": float(np.nanstd(null_y)),
              "p_theatre_year": float(np.nanmean(null_y >= obs_y))}
    print(f, json.dumps(out[f]), flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "single_gpr.json"), "w"), indent=1)
