# Temporary: GFW ships for two theatres from 2023-09 (timed), then one archive day through the flights pass.
set -e
export WARWATCH_HISTORY="$PWD/probe/out/history"
mkdir -p "$WARWATCH_HISTORY"
python3 - <<'PY'
import sys, time
sys.path.insert(0, "warwatch")
import gfw, store
k = gfw.token()
for th in ("iran", "yemen"):
    t = time.time()
    d = gfw.darkships(th, k); s = gfw.darkshare(th, k)
    print(th, "sar days", len(d), d[:2], d[-4:], "share", s[-4:], round(time.time() - t), "s", flush=True)
    for kind in ("loitering", "port-visits"):
        t = time.time(); e = gfw.events(kind, th, k)
        print(th, kind, len(e), e[:2], e[-4:], round(time.time() - t), "s", flush=True)
dark, loiter = gfw.map_items()
print("dark cells", len(dark), dark[:3]); print("loiter", len(loiter), loiter[:3])
t = time.time(); gfw._SAR.clear(); print("re-read", len(gfw.darkships("iran", k)), round(time.time() - t), "s")
PY
python3 -m pip install --quiet --break-system-packages orjson
export BACKFILL_DATA="$PWD/probe/out"
python3 backfill/backfill.py flights --start 2026-10-22 --end 2026-10-22 2>&1 | tail -3
for f in "$BACKFILL_DATA"/flights_*.csv "$BACKFILL_DATA"/bizjet_*.csv; do v=$(cut -d, -f2 "$f"); [ "$v" != "0" ] && echo "$(basename "$f" .csv) $v"; done | tr '\n' ' '
echo; echo "== events"; cat "$BACKFILL_DATA"/flights/events-*.csv
