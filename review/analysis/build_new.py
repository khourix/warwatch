"""z histories (v7 / long / ewma) for the back-filled leading feeds."""
import sys, gzip, io, csv, pickle, collections, datetime as dt
import pandas as pd, numpy as np
sys.path.insert(0, '/home/claude/warwatch/warwatch')
import config as C, scorers
D = '/home/claude/warwatch/review/data/'
series = {}   # id -> dict(theatre, domain, direction, lag, kind, points, lagdays)
def add(sid, th, dom, pts, lagdays=1, direction='up', kind='daily', lag=False):
    pts = sorted((k, v) for k, v in pts.items() if v is not None and not (isinstance(v, float) and np.isnan(v)))
    if len(pts) > 60:
        series[sid] = dict(theatre=th, domain=dom, direction=direction, lag=lag, kind=kind, points=pts, lagdays=lagdays)
# GDELT
g = collections.defaultdict(float)
for d, cc, root, n, men in csv.reader(io.TextIOWrapper(gzip.open(D + 'gdelt_country_day.csv.gz'))):
    g[(d, cc, root)] += float(n)
days = sorted({k[0] for k in g})
for th, ccs in C.GDELT_CC.items():
    def tot(roots): return {d: sum(g.get((d, c, r), 0) for c in ccs for r in roots) for d in days}
    allv = tot(['all'])
    defs = {'posture': ['15'], 'threat': ['13'], 'fight': ['18', '19'], 'preforce': ['13', '15'], 'coerce': ['17']}
    for name, roots in defs.items():
        cnt = tot(roots)
        add(f'gdelt_{name}_{th}', th, 'information', {d: cnt[d] for d in days if allv[d] > 0})
        add(f'gdeltshare_{name}_{th}', th, 'information', {d: 1000 * cnt[d] / allv[d] for d in days if allv[d] >= 50})
# GPSJam
gj = collections.defaultdict(dict)
for d, th, good, bad in csv.reader(io.TextIOWrapper(gzip.open(D + 'gpsjam_theatre_day.csv.gz'))):
    good, bad = int(good), int(bad)
    if good + bad >= 20: gj[th][d] = 100.0 * bad / (good + bad)
for th, pts in gj.items(): add(f'gpsjam_{th}', th, 'geospatial', pts)
# OONI anomaly rate
OC = {'ukraine': ['UA', 'RU', 'BY'], 'europe_east': ['PL', 'LT', 'LV', 'EE', 'FI'], 'iran': ['IR', 'IQ'], 'yemen': ['YE'], 'israel': ['IL', 'LB', 'PS', 'SY'],
      'taiwan': ['TW'], 'scs': ['PH', 'VN'], 'korea': ['KR'], 'southasia': ['IN', 'PK'], 'libya': ['LY'], 'sudan': ['SD', 'SS'], 'drc': ['CD'], 'venezuela': ['VE', 'CU']}
oo = collections.defaultdict(lambda: [0, 0])
for r in csv.reader(io.TextIOWrapper(gzip.open(D + 'ooni.csv.gz'))):
    oo[(r[0][:10], r[1])][0] += int(r[2] or 0); oo[(r[0][:10], r[1])][1] += int(r[3] or 0)
odays = sorted({k[0] for k in oo})
for th, ccs in OC.items():
    pts = {}
    for d in odays:
        m = sum(oo[(d, c)][0] for c in ccs if (d, c) in oo); a = sum(oo[(d, c)][1] for c in ccs if (d, c) in oo)
        if m >= 30: pts[d] = 100.0 * a / m
    add(f'ooni_{th}', th, 'information', pts)
# GPR daily (global) and country monthly
gd = pd.read_excel(io.BytesIO(gzip.open(D + 'data_gpr_daily_recent.xls.gz').read()))
gd['d'] = pd.to_datetime(gd['DAY'].astype(str), format='%Y%m%d').dt.strftime('%Y-%m-%d')
for col, nm in (('GPRD', 'gpr'), ('GPRD_THREAT', 'gpr_threat'), ('GPRD_ACT', 'gpr_act')):
    add(nm, 'global', 'information', dict(zip(gd['d'], gd[col].astype(float))))
gm = pd.read_excel(io.BytesIO(gzip.open(D + 'data_gpr_export.xls.gz').read()))
GC = {'ukraine': ['UKR', 'RUS'], 'europe_east': ['POL', 'FIN'], 'iran': ['SAU'], 'israel': ['ISR', 'EGY'], 'taiwan': ['TWN', 'CHN'], 'scs': ['PHL', 'VNM'],
      'korea': ['KOR'], 'southasia': ['IND'], 'venezuela': ['VEN', 'COL']}
for th, cs in GC.items():
    pts = {}
    for _, r in gm.iterrows():
        v = [r.get('GPRC_' + c) for c in cs]
        v = [x for x in v if pd.notna(x)]
        if v: pts[pd.Timestamp(r['month']).strftime('%Y-%m')] = float(np.mean(v))
    add(f'gprc_{th}', th, 'information', pts, kind='monthly', lagdays=10)
# UCDP fatalities per theatre-day (conflict history; candidate data ~1 month late)
UC = {'ukraine': ['Ukraine', 'Russia (Soviet Union)'], 'europe_east': ['Poland'], 'iran': ['Iran', 'Iraq'], 'yemen': ['Yemen (North Yemen)'],
      'israel': ['Israel', 'Lebanon', 'Syria'], 'scs': ['Philippines'], 'southasia': ['India', 'Pakistan'], 'libya': ['Libya'], 'sudan': ['Sudan', 'South Sudan'],
      'drc': ['DR Congo (Zaire)'], 'venezuela': ['Venezuela', 'Colombia']}
uc = collections.defaultdict(float)
for d, c, t, ev, best in csv.reader(io.TextIOWrapper(gzip.open(D + 'ucdp_country_day.csv.gz'))):
    uc[(d, c)] += float(best)
alld = [d.strftime('%Y-%m-%d') for d in pd.date_range('2017-01-01', '2026-08-31')]
for th, cs in UC.items():
    add(f'ucdp_{th}', th, 'geospatial', {d: sum(uc.get((d, c), 0) for c in cs) for d in alld}, lagdays=35, lag=True)
print(len(series), 'series')
pickle.dump(series, open('newseries.pkl', 'wb'))
