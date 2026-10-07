"""Build the theatre-day feature panel from point-in-time z histories (+ optional extra z histories)."""
import pickle, re, sys, datetime as dt, numpy as np, pandas as pd, glob
TH = ['ukraine','europe_east','iran','yemen','israel','taiwan','scs','korea','southasia','libya','sudan','drc','venezuela']
PAT = '|'.join(TH)
def fam(i): return re.sub(f'_({PAT})$', '', i)
def load(paths=('zhist.pkl',)):
    H = {}
    for p in paths:
        H.update(pickle.load(open(p, 'rb')))
    return H
def panel(H, start='2019-01-01', end='2026-09-30'):
    days = pd.date_range(start, end, freq='D')
    rows = []
    meta = {}
    cols = {}
    for sid, s in H.items():
        f = fam(sid)
        meta[f] = (s['domain'], s['lag'])
        sgn = {'up': 1, 'down': -1}.get(s['direction'], 0)
        z = pd.Series({pd.Timestamp(k): v for k, v in s['z'].items()}).reindex(days)
        dz = z * sgn if sgn else z.abs()
        targets = TH if s['theatre'] == 'global' else [s['theatre']]
        for t in targets:
            cols.setdefault(t, {})[f] = dz.values
    frames = []
    for t in TH:
        df = pd.DataFrame(cols.get(t, {}), index=days)
        df['theatre'] = t
        frames.append(df)
    P = pd.concat(frames)
    P.index.name = 'date'
    return P.reset_index(), meta
def labels(P, events, horizon=30, post=30):
    ev = {}
    for _, e in events.iterrows():
        ev.setdefault(e['theatre'], []).append(pd.Timestamp(e['date']))
    y = np.zeros(len(P), int); excl = np.zeros(len(P), bool); lead = np.full(len(P), np.nan); eid = np.full(len(P), -1)
    evlist = [(t, d) for t, ds in ev.items() for d in ds]
    for i, (t, d) in enumerate(zip(P['theatre'].values, P['date'].values)):
        d = pd.Timestamp(d)
        for e in ev.get(t, []):
            k = (e - d).days
            if 1 <= k <= horizon:
                y[i] = 1; lead[i] = k if np.isnan(lead[i]) else min(lead[i], k)
                eid[i] = evlist.index((t, e)) if eid[i] < 0 else eid[i]
            if 0 <= -k <= post:
                excl[i] = True
    return y, excl, lead, eid, evlist
