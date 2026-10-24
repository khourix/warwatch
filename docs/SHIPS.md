# Ships

WarWatch reads ships from two free sources. Free live AIS covers European waters well. Global Fishing Watch covers the Gulf and the Red Sea, where free AIS has almost no receivers.

Paid AIS (MarineTraffic, Spire, Kpler) is ruled out. Scraping MarineTraffic is ruled out too.

A proposal to widen coverage with a free source, Open Waters AIS, is in `docs/AIS_PLAN.md`, with the measurements and the one open licence question. It is not built yet.

Code: `warwatch/aiswatch.py` (live AIS), `warwatch/gfw.py` (Global Fishing Watch). Workflows: `.github/workflows/ais.yml`, `.github/workflows/slow.yml`.

## Live AIS (aisstream.io)

`ais.yml` runs every 30 minutes. It listens to the aisstream.io websocket for nine minutes (`AISSTREAM_API_KEY`, free).

It folds what it hears into a small state file. The file lives on the orphan branch `ais`, as one commit that each run replaces, so `main` does not grow. The state holds:

- every ship's last position, name, type, flag (from the MMSI country code) and destination, for 48 hours;
- the last 48 hours of track, one point every 10 minutes, for military (AIS type 35) and law-enforcement (type 55) ships;
- the ships seen today in each counted region, by class;
- today's crossings of the watched straits.

When the UTC day turns, the finished day goes to `main` as daily series in the history cache:

| Series | What it counts |
|---|---|
| `aisday_<class>_<region>` | distinct ships heard that day in the region. Classes: navy, law, tanker, cargo, passenger, other. Regions: `baltic` (Eastern flank), `blacksea` (Ukraine), `eastmed` (Israel) |
| `strait_<gate>_<dir>` | distinct ships that crossed the gate line that day, north or south. Gates: Bosporus, Dardanelles, Øresund, Great Belt |

A crossing needs two positions of the same ship, at most 3 hours apart and within 30 km of the gate's middle, on opposite sides of the line.

The dashboard build reads the state file for the map instead of listening itself. The map shows military and law-enforcement ships heard in the last 6 hours, each with its dotted trail. If the state file is missing, the build falls back to a 75-second listen.

The `aisday_*` and `strait_*` series are not in the catalog yet. They need a few months of history before they mean anything.

### Coverage

aisstream relays volunteer receivers. In a four-minute test in October 2026 it heard many ships in the Baltic, the Black Sea and the Mediterranean, one ship at Hormuz, and none in the Red Sea. A full day of the collector on 24 October 2026 kept 4,372 ships, one of them in the Gulf and none in the Red Sea. So live AIS is for the Eastern flank, Ukraine and Israel. The Gulf and the Red Sea rely on Global Fishing Watch.

Open Waters AIS, a free network that re-serves AISHub, has one volunteer station near Dubai. On 24 October 2026 it returned 1,034 ships in the Gulf box, 129 of them under way, and none in the Red Sea. `docs/AIS_PLAN.md` has the boxes and the counts.

## Global Fishing Watch

The slow job (`slow.yml`, daily) calls the GFW API v3 for each theatre's waters box (`gfw.BOX`) with `GFW_TOKEN` (free, non-commercial use). The Gulf and Hormuz sit in Iran's box. The Red Sea and Bab el-Mandeb sit in Yemen's.

| Series | What it is |
|---|---|
| `darkships_<t>` | Sentinel-1 radar detections of vessels with no matching AIS signal, per pass day |
| `darkshare_<t>` | those detections as a percent of all radar detections that day (only days with 5 or more) |
| `loiter_<t>` | loitering events that started that day: carrier vessels slowing or drifting at sea for hours |
| `portcalls_<t>` | port visits that started that day |

Radar passes come every few days, so a day without a pass has no value, not zero. GFW posts about four days late and revises recent days, so each run re-reads the last 45 days. The first run reads the whole history from 2023-09-01, in half-year slices.

The share is the series to watch. A pass that saw only part of the box gives a low dark count but a normal share. In October 2026 the Iran box ran at 35 to 44% dark.

For the map, the same calls keep:

- the newest pass's dark-ship cells (0.1 degree, about 10 km), the 150 busiest per theatre (cache table `gfw_dark`);
- the last ten days' loitering events, 40 per theatre, with vessel name, flag, type and hours (cache table `gfw_loiter`).

## How it shows

- **Map.** Dark-ship cells are a faint grey field under everything, larger where more ships went dark. Loitering ships are small amber boats. Military ships from live AIS have a dotted trail. Each opens a card with the source and how late it is.
- **Signals.** The GFW series are listed under Sea, labelled "not tested".
- **Tells.** "Ships go dark" fires when at least 30% of the ships on the latest pass sent no AIS, half as many again as usual (the 90 days before).

## Not tested

None of these series is in the score. Each enters only after a test on the event list (`docs/EVENTS.md`), written down before it is run, shows it moves before events. That needs the backfilled history. GFW history goes back to 2023-09; AIS history starts in October 2026.
