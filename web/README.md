# web: the new WarWatch app

React, Vite and MapLibre. It reads only the data contract (`site/data/v1/`, written by `warwatch/contract.py`), never `data.json`.
It is the page at `/warwatch/`. The workflow builds it after the Python run, and `warwatch/pages.py` writes `dist/` into `site/`:

- one copy of `index.html` per address, each with its own title and link preview: the root, `/warwatch/<theatre>/` (with the theatre's
  card, `og/<theatre>.jpg`), `/warwatch/base/<id>/`, `/warwatch/signals/`, `/warwatch/record/` and `/warwatch/map/`;
- `404.html`, the same page, which GitHub Pages serves for any other address (a theatre's tab, a signal);
- the old page at `/warwatch/classic/` until 7 Dec 2026, and `/warwatch/next/`, which sends the preview's links on.

Every page carries `<base href="/warwatch/">`, so data, images and routes resolve from the root at any depth. Links from before the
switch-over (`#iran/signals`, `#/theatre/iran`) move to their address when the app opens.

## Run it locally

```sh
python3 ../warwatch/run.py --demo buildup --out /tmp/ww/index.html   # writes /tmp/ww/data/v1
npm ci
WW_SITE=/tmp/ww npm run dev                                          # serves the app with /data from /tmp/ww
npm run build                                                        # type-check, then dist/
```

Versions in `package.json` are exact; update them on purpose, with the lock file.
