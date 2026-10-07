import sys, os, json, collections
sys.path.insert(0, '/home/claude/warwatch/warwatch')
os.environ['WARWATCH_NO_RETRY'] = '1'
for k in ['FRED_API_KEY','CENSUS_API_KEY','SAM_API_KEY','GFW_TOKEN','CLOUDFLARE_API_TOKEN','FIRMS_MAP_KEY','GIE_API_KEY','TWELVEDATA_API_KEY','AISSTREAM_API_KEY','OPENWATERS_AIS_TOKEN']: os.environ.setdefault(k,'x')
import catalog, run, engine, config as C
def boom(): raise RuntimeError('offline')
for s in catalog.SERIES: s['fetch'] = boom
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    series = run.collect()
res = run.evaluate(series)
st = collections.Counter(s['status'] for s in series)
print('status', st)
print('calib', res['calib'])
for t, v in res['theatres'].items():
    print(f"{t:12} {v['level']:18} score={v['score']} zc={v['zc']} th={v.get('th')} firing={v['firing']} conf={v['conf_label']} worst={v['worst']}")
print('global', res['global'])
for r in res['regions']: print(r['id'], r['level'], r['score'])
json.dump({'theatres': res['theatres'], 'regions': res['regions'], 'global': res['global'], 'calib': res['calib'],
           'series': [{k: s.get(k) for k in ('id','theatre','domain','lag','kind','direction','status','stale')} | {'z': (s['score'] or {}).get('z'), 'n': len(s['points']), 'first': s['points'][0][0] if s['points'] else None, 'last': s['points'][-1][0] if s['points'] else None} for s in res['series']]},
          open('live_state.json','w'), default=str)
