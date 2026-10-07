import sys, pickle, csv, datetime as dt, bisect
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import catalog, stats
H = pickle.load(open('zhist.pkl', 'rb'))
cat = {s['id']: s for s in catalog.SERIES}
for sid in ['china_equity','container_equity','copper_miners','def_ita','def_lmt','def_noc','def_rtx','gold','india_equity','israel_equity','korea_equity','latam_equity','poland_equity','taiwan_equity','tanker_equity']:
    s = cat[sid]
    pts = [(r[0], float(r[1])) for r in csv.reader(open(f'/home/claude/warwatch/backtest/history/{sid}.csv'))]
    avail = [(dt.date.fromisoformat(l[:10]) + dt.timedelta(days=1)).toordinal() for l, _ in pts]
    zs = {}
    d = dt.date(2018, 6, 1)
    while d <= dt.date(2026, 9, 30):
        cut = bisect.bisect_right(avail, d.toordinal())
        p = pts[max(0, cut - 250):cut]
        if p:
            r = stats.score_series(p, 'daily')
            if r is not None: zs[d] = r['z']
        d += dt.timedelta(days=1)
    H[sid] = {k: s[k] for k in ('theatre', 'domain', 'direction', 'lag', 'kind')} | {'z': zs}
    print(sid, len(zs), flush=True)
pickle.dump(H, open('zhist.pkl', 'wb'))
