# Temporary: one full archive day through the flights pass, timed.
set -e
python3 -m pip install --quiet --break-system-packages orjson
export BACKFILL_DATA="$PWD/probe/out"
mkdir -p "$BACKFILL_DATA"
/usr/bin/time -v python3 backfill/backfill.py flights --start 2026-10-22 --end 2026-10-22 2>&1 | grep -v "^\s*\(Page\|Socket\|Signals\|Swaps\|File system\|Average\|Voluntary\|Involuntary\|Minor\|Major\|Exit\)"
for f in "$BACKFILL_DATA"/flights_*.csv "$BACKFILL_DATA"/bizjet_*.csv; do v=$(cut -d, -f2 "$f"); [ "$v" != "0" ] && echo "$(basename "$f" .csv) $v"; done
echo "== events"; cat "$BACKFILL_DATA"/flights/events-*.csv | head -80
echo "== airports (top by departures)"; sort -t, -k3 -nr "$BACKFILL_DATA"/flights/airports-*.csv | head -40
