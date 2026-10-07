import csv, numpy as np, pandas as pd
H = '/home/claude/warwatch/backtest/history/'
def px(n):
    s = pd.Series({pd.Timestamp(r[0][:10]): float(r[1]) for r in csv.reader(open(H + n + '.csv'))}).sort_index()
    return s[~s.index.duplicated()]
LOCAL = {'ukraine': ['poland_equity', 'eu_gas'], 'europe_east': ['poland_equity', 'fx_pln'], 'iran': ['tanker_equity'], 'yemen': ['container_equity', 'tanker_equity'],
         'israel': ['israel_equity', 'fx_ils'], 'taiwan': ['taiwan_equity', 'fx_twd'], 'scs': ['china_equity'], 'korea': ['korea_equity', 'fx_krw'],
         'southasia': ['india_equity', 'fx_inr'], 'libya': [], 'sudan': [], 'drc': ['copper_miners'], 'venezuela': ['latam_equity']}
GLOBAL = ['brent', 'gold']
cache = {}
def move(name, d):
    if name not in cache:
        s = px(name); r = np.log(s).diff().dropna(); cache[name] = r
    r = cache[name]
    d = pd.Timestamp(d)
    prior = r[(r.index < d) & (r.index >= d - pd.Timedelta(days=365))]
    win = r[(r.index >= d) & (r.index <= d + pd.Timedelta(days=4))]
    if len(prior) < 100 or len(win) == 0: return None
    sd = prior.std()
    cum = win.cumsum()
    return float(cum.abs().max() / (sd * np.sqrt(np.arange(1, len(cum) + 1)[cum.abs().values.argmax()])))
ev = pd.read_csv('events_full.csv')
rows = []
for _, e in ev.iterrows():
    m = {n: move(n, e['date']) for n in GLOBAL + LOCAL[e['theatre']] if n != 'eu_gas'}
    m = {k: v for k, v in m.items() if v is not None}
    best = max(m.items(), key=lambda kv: kv[1]) if m else (None, None)
    rows.append((e['theatre'], e['date'], e['description'][:40], best[0], None if best[1] is None else round(best[1], 1)))
mm = pd.DataFrame(rows, columns=['theatre', 'date', 'event', 'largest_mover', 'move_sd'])
mm['market_moving'] = mm['move_sd'] >= 2.5
print(mm.to_string())
print('market-moving (>=2.5 sd within 3 trading days):', mm['market_moving'].sum(), 'of', mm['move_sd'].notna().sum())
mm.to_csv('event_market_moves.csv', index=False)
