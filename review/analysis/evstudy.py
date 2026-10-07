"""Event study: mean direction-adjusted z of each series family in the days around past events (point-in-time scores)."""
import pickle, csv, sys, re, statistics, datetime as dt, collections
H = pickle.load(open('zhist.pkl', 'rb'))
EV = list(csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else 'events_prov.csv')))
TH = 'ukraine|europe_east|iran|yemen|israel|taiwan|scs|korea|southasia|libya|sudan|drc|venezuela'
def fam(i): return re.sub(f'_({TH})$', '', i)
def dz(s, z): return {'up': z, 'down': -z}.get(s['direction'], abs(z))
evd = collections.defaultdict(list)
for e in EV: evd[e['theatre']].append(dt.date.fromisoformat(e['date']))
WIN = [(-60, -31), (-30, -8), (-7, -1), (0, 6), (7, 30)]
rows = collections.defaultdict(lambda: collections.defaultdict(list))
calm = collections.defaultdict(list)
for sid, s in H.items():
    t = s['theatre']
    if t == 'global':
        ts = list(evd)          # global series: every event counts
    else:
        ts = [t]
    evs = [e for tt in ts for e in evd.get(tt, [])]
    if not evs: continue
    f = fam(sid)
    for d, z in s['z'].items():
        v = dz(s, z)
        near = [ (d - e).days for e in evs ]
        if all(abs(x) > 90 for x in near):
            calm[f].append(v)
    for e in evs:
        for lo, hi in WIN:
            vals = [dz(s, s['z'][e + dt.timedelta(days=k)]) for k in range(lo, hi + 1) if e + dt.timedelta(days=k) in s['z']]
            if vals: rows[f][(lo, hi)].append(statistics.fmean(vals))
print(f"{'family':28} {'dom':6} lag  n_ev  calm_mean  " + "  ".join(f"[{lo},{hi}]" for lo, hi in WIN))
out = []
for f, w in rows.items():
    sid = next(i for i in H if fam(i) == f); s = H[sid]
    cm = statistics.fmean(calm[f]) if calm[f] else float('nan')
    vals = [statistics.fmean(w[x]) if w[x] else float('nan') for x in WIN]
    ns = len(w[WIN[1]])
    out.append((vals[1] + vals[2] - 2 * cm, f, s, ns, cm, vals))
for _, f, s, ns, cm, vals in sorted(out, reverse=True, key=lambda x: x[0]):
    print(f"{f:28} {s['domain'][:6]:6} {'LAG' if s['lag'] else '   '} {ns:4}  {cm:+.2f}     " + "  ".join(f"{v:+7.2f}" for v in vals))
