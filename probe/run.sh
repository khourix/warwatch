# Temporary: one archive day through the flights pass (the diversion rule), then two minutes of the AIS collector.
set -e
export WARWATCH_HISTORY="$PWD/probe/out/history"
mkdir -p "$WARWATCH_HISTORY"
python3 -m pip install --quiet --break-system-packages orjson
export BACKFILL_DATA="$PWD/probe/out"
python3 backfill/backfill.py flights --start 2026-10-22 --end 2026-10-22 2>&1 | tail -3
for f in "$BACKFILL_DATA"/flights_*.csv "$BACKFILL_DATA"/bizjet_*.csv; do v=$(cut -d, -f2 "$f"); [ "$v" != "0" ] && echo "$(basename "$f" .csv) $v"; done | tr '\n' ' '
echo; echo "== events"; cat "$BACKFILL_DATA"/flights/events-*.csv
echo "== ais"
python3 warwatch/aiswatch.py --state probe/out/ais.json --seconds 120
python3 - <<'PY'
import json, sys
sys.path.insert(0, "warwatch")
import aiswatch
st = json.load(open("probe/out/ais.json"))
ms = aiswatch.map_ships(st)
print("map ships", len(ms), [(m["n"], m["flag"], len(m["tr"])) for m in ms[:8]])
print("counts", {k: v for k, v in aiswatch.counts(st["today"], st["cross"]).items() if v})
PY
