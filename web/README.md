# web: the new WarWatch app

React, Vite and MapLibre. It reads only the data contract (`site/data/v1/`, written by `warwatch/contract.py`), never `data.json`.
It is the page at `/warwatch/`. The workflow builds it after the Python run, and `warwatch/pages.py` writes `dist/` into `site/`:

- one copy of `index.html` per address, each with its own title and link preview: the root, `/warwatch/<theatre>/` (with the theatre's
  card, `og/<theatre>.jpg`), `/warwatch/base/<id>/`, `/warwatch/signals/`, `/warwatch/ground/`, `/warwatch/record/`, `/warwatch/glossary/`, `/warwatch/map/` and `/warwatch/wall/`;
- `404.html`, the same page, which GitHub Pages serves for any other address (a theatre's tab, a signal);
- the old page at `/warwatch/classic/` until 7 Dec 2026, and `/warwatch/next/`, which sends the preview's links on.

Every page carries `<base href="/warwatch/">`, so data, images and routes resolve from the root at any depth. Links from before the
switch-over (`#iran/signals`, `#/theatre/iran`) move to their address when the app opens. On Signals, a theatre filter is its
address (`/warwatch/signals/iran/`) and the open signal is `?s=<id>`, so a reload or a shared link keeps them. On Watch (the home, a
theatre, a base, the map) the picked day is `?d=2026-11-10` and the map layers, when they differ from the usual set, `?l=bases.fires`.
These change in place and add no steps to Back. Copy link always names the layers.

The app fetches `brief.json` again every 10 minutes, also in a background tab, and `map/live.json` every 30, so a page left open
picks up new runs and shows the late line when they stop.

- **Replay.** A day picked on the timeline (`?d=`) replays the board, the dispatch, the tripwires and the feed for that day, from what
  the data keeps per day: each theatre's level and the tripwires lit at the day's first run (the forward records), the group
  readings from `signals/buildup.json`, and the dated feed. A day a record did not keep says "not kept", and heat before
  `replay.heatFrom` says heat was not kept that far back, never zero. The 0 to 100 readings, context tags, the map's marks and the
  dossier's tabs are not kept per day, so they stay today's, and the replay line names them. Escape or "Back to now" returns to
  live. Since-you-last-looked and notifications ignore a replay (`src/replay.tsx`).
- **Follow.** A pin on each board row and on a theatre's page puts the theatre at the top of the board. The list stays in this browser
  only (`ww-follow`); settings' Clear removes it. "Notify me" asks the browser's permission only from that switch. It works in desktop
  browsers while a WarWatch tab is open: each newer run is compared with the data the tab saw before, and a followed theatre that
  rises to Watch or above, or where a tripwire turns on (by id, `tellsLit`), gets one notification. There is no push and no service
  worker, so a closed page cannot notify and phones cannot at all; there the switch is off and says why (`src/follow.ts`).
- **Wall.** `/warwatch/wall/` is Watch for a spare screen: large type, no controls, the theatres closest to Watch, the week's
  tripwires and a globe that moves for 3 seconds every 30 between them and draws nothing in between (a cut once a minute under
  reduced motion). Esc leaves, F switches full
  screen, and the screen is kept awake where the browser allows. It is in the command menu and settings, not the rail.

The words the explainers show (a dotted term) and the glossary page both come from `src/glossary.ts`, and nowhere else.

Fields the app reads only when they are there (added November 2026; older data still draws):

- The brief's theatre rows: `levels`, `wires` (the tripwire ids lit at each day's first run) and `tellsLit` (the ids lit now), and
  the brief's `replay` (`heatFrom`, tripwire names). Without them the replay says not kept and notifications send no tripwire.
- `theatres/<id>.json` and the brief's theatre rows: `lines`, where Watch, Elevated and Critical sit on the 0 to 100 reading. Without
  it the gauge draws Watch at 50, Critical at 90 and no Elevated line.
- `signals/buildup.json`: the Signals page's build-up wall. Without it the page says the wall is not in this data run.
- `map/live.json`, each chokepoint: `gfw`, true when the strait lies inside a Global Fishing Watch waters box. Only then does Ground
  show its dark-ship and loitering counts; without the flag, or when it is false, it says they are not covered there.
- `brief.json`: `health` (signal statuses, the sources that reported a problem, how often a run is due and when the data counts as
  late, 90 minutes). Without it the top bar shows the data's age alone, and the late line still appears after 90 minutes.
- the brief's theatre rows: `levels`, `[date, level]` for each of the last 30 days whose first run had the model switched off (the
  level the page showed). The replay reads it; a day without it says "not kept".
- `record.json`: `past`, the newest labelled events with the tripwires and group readings of the week before each. Without it the
  Record page says the list is not in this data run.

## Run it locally

```sh
python3 ../warwatch/run.py --demo buildup --out /tmp/ww/index.html   # writes /tmp/ww/data/v1
npm ci
WW_SITE=/tmp/ww npm run dev                                          # serves the app with /data from /tmp/ww
npm run build                                                        # type-check, then dist/
```

Versions in `package.json` are exact; update them on purpose, with the lock file.

`npm run dev` and `npm run build` first download two fonts, Switzer and Sentient, from Fontshare (`scripts/fetch-fonts.mjs`). Their
licence allows the site to serve them but not the repository to hold them, so they are git-ignored. If the download fails the app
still builds and uses system fonts. See `src/fonts/README.md`.
