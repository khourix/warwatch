"""Polymarket review: (1) calibration of resolved geopolitical markets at fixed horizons before resolution;
(2) a per-theatre daily market index (30-day hazard of open strike/attack markets) and whether it rose before past events."""
import sys, json, gzip, re, math, numpy as np, pandas as pd, panel
from sklearn.metrics import roc_auc_score
path = sys.argv[1]
M = [json.loads(l) for l in gzip.open(path, 'rt')]
TH_RX = {'iran': r'\biran|tehran|hormuz|khamenei|fordow|natanz|isfahan|kharg', 'israel': r'\bisrael|gaza|hamas|hezbollah|lebanon|idf\b|netanyahu|west bank',
         'yemen': r'yemen|houthi|red sea|aden', 'ukraine': r'ukrain|kyiv|russia (x|and) ukraine|zelensk|crimea|odesa|kharkiv|donetsk|zaporizh',
         'europe_east': r'nato|poland|baltic|lithuania|latvia|estonia|finland|moldova|belarus', 'taiwan': r'taiwan|\bchina (invade|blockade)|pla\b',
         'korea': r'korea|kim jong|pyongyang', 'venezuela': r'venezuela|maduro|caracas', 'southasia': r'india|pakistan|kashmir',
         'scs': r'philippines|south china sea|scarborough', 'libya': r'libya', 'sudan': r'sudan|rsf\b', 'drc': r'congo|\bm23\b|\bdrc\b'}
ACT = re.compile(r'\b(strikes?|struck|attacks?|invades?|invasion|military (action|clash|operation)|missiles?|airstrikes?|bomb\w*|clash|offensive|'
                 r'drones?|blockade|ground operation|enter|incursion|declares? war|war\b|target|hits?)', re.I)
NEG = re.compile(r'ceasefire|peace|deal|agreement|talks|meeting|recogni|release|sanction|leader|head of state|prime minister|election|visit', re.I)
rows = []
for m in M:
    q = m.get('question') or ''
    try: outs = json.loads(m.get('outcomes') or '[]'); px = [float(x) for x in json.loads(m.get('outcomePrices') or '[]')]
    except Exception: continue
    if outs[:2] != ['Yes', 'No'] or not m.get('history'): continue
    th = [t for t, rx in TH_RX.items() if re.search(rx, q, re.I)]
    act = bool(ACT.search(q)) and not NEG.search(q)
    res = None
    if m.get('closed') and px and max(px) > 0.98: res = int(px[0] > 0.5)
    end = pd.Timestamp(m.get('closedTime') or m.get('endDate')).tz_localize(None) if (m.get('closedTime') or m.get('endDate')) else None
    endd = pd.Timestamp(m.get('endDate')).tz_localize(None) if m.get('endDate') else end
    h = pd.Series({pd.Timestamp(t, unit='s').normalize(): p for t, p in m['history']}).sort_index()
    h = h[~h.index.duplicated(keep='last')]
    rows.append(dict(id=m['id'], q=q, th=th[0] if th else None, act=act, res=res, end=end, endd=endd, vol=float(m.get('volumeNum') or 0), h=h))
D = pd.DataFrame(rows)
print('markets with history', len(D), 'resolved', D.res.notna().sum(), 'action markets', D.act.sum(), 'mapped to a theatre', D.th.notna().sum())
# (1) calibration at horizons
cal = []
for r in D[D.res.notna()].itertuples():
    for hz in (30, 7, 1):
        d = (r.end.normalize() - pd.Timedelta(days=hz))
        s = r.h[r.h.index <= d]
        if len(s) and (r.end - s.index[-1]).days <= hz + 3 and s.index[0] <= d:
            cal.append(dict(id=r.id, act=r.act, hz=hz, p=float(s.iloc[-1]), y=r.res, vol=r.vol))
C = pd.DataFrame(cal)
print('\nresolved markets in calibration:', C.id.nunique(), 'of which military-action', C[C.act].id.nunique())
for hz in (30, 7, 1):
    c = C[C.hz == hz]
    if len(c) < 5: continue
    b = ((c.p - c.y) ** 2).mean(); bc = ((c.y.mean() - c.y) ** 2).mean()
    print(f'h={hz:2d}d n={len(c):4d} yes-rate={c.y.mean():.3f} mean p={c.p.mean():.3f} Brier={b:.4f} BSS vs base={1-b/bc:.3f}')
c = C[C.hz == 7].copy(); c['bin'] = pd.cut(c.p, [-.001, .05, .15, .3, .5, .7, .85, .95, 1.001])
print(c.groupby('bin', observed=True).agg(n=('y', 'size'), mean_p=('p', 'mean'), yes=('y', 'mean')).round(3))
ca = C[(C.hz == 7) & C.act]
if len(ca): print('military-action markets at 7d: n', len(ca), 'mean p', round(ca.p.mean(), 3), 'yes rate', round(ca.y.mean(), 3))
C.to_csv('out/poly_calibration.csv', index=False)
# (2) theatre market index: max over open action markets of the 30-day hazard
days = pd.date_range('2020-06-01', '2026-09-30')
IDX = {}
for t in panel.TH:
    sub = D[(D.th == t) & D.act]
    if sub.empty: continue
    mat = []
    for r in sub.itertuples():
        s = r.h.reindex(days).ffill(limit=3)
        if r.endd is None: continue
        T = np.maximum((r.endd.normalize() - days).days.values, 1)
        live = (days >= r.h.index[0]) & (days <= min(r.endd, r.end or r.endd))
        p = s.values.clip(0.001, 0.999)
        p30 = np.where(T <= 30, p, 1 - (1 - p) ** (30 / T))
        mat.append(np.where(live, p30, np.nan))
    IDX[t] = pd.Series(np.nanmax(np.vstack(mat), axis=0), index=days)
print('\ntheatres with a market index:', {t: int(s.notna().sum()) for t, s in IDX.items()})
ev = pd.read_csv('events_full.csv'); ev['date'] = pd.to_datetime(ev['date'])
out = []
for e in ev.itertuples():
    s = IDX.get(e.theatre)
    if s is None or e.date < pd.Timestamp('2020-07-01'): continue
    v = {k: s.get(e.date + pd.Timedelta(days=k)) for k in (-30, -14, -7, -3, -1, 1)}
    if all(pd.isna(x) for x in v.values()): continue
    out.append(dict(theatre=e.theatre, date=e.date.date(), desc=e.description[:50], **{f'p{k}': (round(x, 3) if pd.notna(x) else None) for k, x in v.items()}))
E = pd.DataFrame(out); pd.set_option('display.width', 220); print(E.to_string(index=False)); E.to_csv('out/poly_events.csv', index=False)
# AUC of market index vs 30-day-ahead label, on days the index exists
P = pd.DataFrame([(t, d, v) for t, s in IDX.items() for d, v in s.items() if pd.notna(v)], columns=['theatre', 'date', 'p'])
y, excl, lead, eid, evl = panel.labels(P, ev)
ok = ~excl
if y[ok].sum() and (1 - y[ok]).sum(): print('market index AUC', round(roc_auc_score(y[ok], P.p.values[ok]), 3), 'days', ok.sum(), 'pos', y[ok].sum(), 'events', len(set(eid[ok & (y == 1)])))
pd.to_pickle(IDX, 'out/poly_index.pkl')
