# web: the new WarWatch app

React, Vite and MapLibre. It reads only the data contract (`site/data/v1/`, written by `warwatch/contract.py`), never `data.json`.
It is the page at `/warwatch/`. The workflow builds it after the Python run, and `warwatch/pages.py` writes `dist/` into `site/`:

- one copy of `index.html` per address, each with its own title and link preview: the root, `/warwatch/<theatre>/` (with the theatre's
  card, `og/<theatre>.jpg`), `/warwatch/base/<id>/`, `/warwatch/signals/`, `/warwatch/ground/`, `/warwatch/record/` and `/warwatch/map/`;
- `404.html`, the same page, which GitHub Pages serves for any other address (a theatre's tab, a signal);
- the old page at `/warwatch/classic/` until 7 Dec 2026, and `/warwatch/next/`, which sends the preview's links on.

Every page carries `<base href="/warwatch/">`, so data, images and routes resolve from the root at any depth. Links from before the
switch-over (`#iran/signals`, `#/theatre/iran`) move to their address when the app opens. On Signals, a theatre filter is its
address (`/warwatch/signals/iran/`) and the open signal is `?s=<id>`, so a reload or a shared link keeps them.

Fields the app reads only when they are there (added November 2026; older data still draws):

- `theatres/<id>.json` and the brief's theatre rows: `lines`, where Watch, Elevated and Critical sit on the 0 to 100 reading. Without
  it the gauge draws Watch at 50, Critical at 90 and no Elevated line.
- `signals/buildup.json`: the Signals page's build-up wall. Without it the page says the wall is not in this data run.
- `map/live.json`, each chokepoint: `gfw`, true when the strait lies inside a Global Fishing Watch waters box. Only then does Ground
  show its dark-ship and loitering counts; without the flag, or when it is false, it says they are not covered there.

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
