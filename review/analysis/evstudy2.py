"""Event study + chance-level reference. Scores: v7 as built (scores from out/scores_long.npy row 0 and v7 row0), best rolling model.
For each event, percentile rank (within theatre, all days) of the score from -60 to +20 days; average across events.
Chance recall: circularly shift each theatre's score by a random offset (keeps autocorrelation), 200 draws."""
import numpy as np, pandas as pd, pickle, panel
P0, y, use, eid = pickle.load(open('out/rolling_meta.pkl', 'rb'))
ev = pd.read_csv('events_full.csv')
S = {'v7 as built': np.load('out/scores_v7.npy')[0], 'v7 one-sided, long baseline': np.load('out/scores_long.npy')[1],
     'proposed: regularised logit (rolling origin)': np.load('out/p_best.npy')}
dates = pd.to_datetime(P0['date']).values; th = P0['theatre'].values
rk = {}
for n, s in S.items():
    r = np.full(len(s), np.nan)
    for t in panel.TH:
        m = (th == t) & ~np.isnan(s)
        r[m] = pd.Series(s[m]).rank(pct=True).values
    rk[n] = r
idx = {(t, d): i for i, (t, d) in enumerate(zip(th, pd.to_datetime(dates)))}
curves = {n: {k: [] for k in range(-60, 21)} for n in S}
for _, e in ev.iterrows():
    d0 = pd.Timestamp(e['date'])
    if d0 < pd.Timestamp('2021-03-01') or d0 > pd.Timestamp('2026-09-10'): continue
    for n in S:
        for k in range(-60, 21):
            i = idx.get((e['theatre'], d0 + pd.Timedelta(days=k)))
            if i is not None and not np.isnan(rk[n][i]): curves[n][k].append(rk[n][i])
C = pd.DataFrame({n: {k: np.mean(v) for k, v in c.items()} for n, c in curves.items()})
print(C.loc[[-60, -45, -30, -21, -14, -7, -3, -1, 0, 3, 7, 14]].round(3).to_string())
C.to_csv('out/event_study_curves.csv')
# chance recall at 10% FPR, evaluated on 2021+ for all three
ok = use & (pd.to_datetime(dates) >= pd.Timestamp('2021-01-01'))
rng = np.random.default_rng(0)
def recall(s, okk):
    okk = okk & ~np.isnan(s); cut = np.quantile(s[okk & (y == 0)], .9); evs = sorted(set(eid[okk & (y == 1)]))
    return sum(((eid == e) & okk & (s >= cut)).any() for e in evs), len(evs)
for n, s in S.items():
    real = recall(s, ok); null = []
    for _ in range(200):
        z = s.copy()
        for t in panel.TH:
            m = np.where(th == t)[0]; z[m] = np.roll(s[m], rng.integers(60, len(m) - 60))
        null.append(recall(z, ok)[0])
    print(n, 'recall@10%FPR', real, 'chance mean', np.mean(null), 'p95', np.percentile(null, 95), 'p-value', np.mean(np.array(null) >= real[0]))
mm = pd.read_csv('event_market_moves.csv')
mcol = [c for c in mm.columns if 'moving' in c.lower()][0]
mk = set((r.theatre, pd.Timestamp(r.date)) for r in mm.itertuples() if getattr(r, mcol))
evl = [tuple(x) for x in pickle.load(open('out/rolling_meta.pkl', 'rb'))[0][['theatre']].values]  # unused
_, _, _, _, evlist = panel.labels(*panel.panel(panel.load(['znew_v7.pkl']))[:1], ev)
mids = {i for i, (t, d) in enumerate(evlist) if (t, d) in mk}
for n, s in S.items():
    okk = ok & ~np.isnan(s); cut = np.quantile(s[okk & (y == 0)], .9); evs = sorted(set(eid[okk & (y == 1)]) & mids)
    print(n, 'market-moving events hit', sum(((eid == e) & okk & (s >= cut)).any() for e in evs), '/', len(evs))
for n, s in S.items():
    okk = ok & ~np.isnan(s); cut = np.quantile(s[okk], .9); top = okk & (s >= cut)
    print(n, 'P(event in 30d | top 10% of days)', round(y[top].mean(), 3), 'base', round(y[okk].mean(), 3), 'lift', round(y[top].mean() / y[okk].mean(), 2))
