import os, sys, traceback
sys.path.insert(0, "warwatch")
import sources as S
tok = os.environ.get("CLOUDFLARE_API_TOKEN", "")
for name, fn in [("http", lambda: S.fetch_radar("http/timeseries", "UA", tok)), ("flows", lambda: S.fetch_radar("netflows/timeseries", "UA", tok)),
                 ("l7", lambda: S.fetch_radar("attacks/layer7/timeseries", "UA", tok)), ("gas_ua", lambda: S.fetch_agsi("UA")), ("gas_eu", lambda: S.fetch_agsi("eu"))]:
    try:
        r = fn(); print("OK", name, len(r), r[:2], r[-2:])
    except Exception as e:
        print("ERR", name, repr(e)[:300])
