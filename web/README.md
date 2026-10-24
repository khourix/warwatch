# web: the new WarWatch app

React, Vite and MapLibre. It reads only the data contract (`site/data/v1/`, written by `warwatch/contract.py`), never `data.json`.
Until the switch-over it ships as a preview at `/warwatch/next/`; the workflow builds it after the Python run and copies `dist/` to `site/next/`.

## Run it locally

```sh
python3 ../warwatch/run.py --demo buildup --out /tmp/ww/index.html   # writes /tmp/ww/data/v1
npm ci
WW_SITE=/tmp/ww npm run dev                                          # serves the app with /data from /tmp/ww
npm run build                                                        # type-check, then dist/
```

Versions in `package.json` are exact; update them on purpose, with the lock file.
