---
name: verify-warwatch
description: "Prove a WarWatch change works: unit tests, an offline demo render of the public dashboard (index.html, feed.xml, audit.json), links, headless-Chrome screenshots, the probability model, the forward record chain, and (read-only) the freshness of the live page. Use before every commit (quick), before every PR (full), and when asked whether the live site is healthy (live-read)."
---

# verify-warwatch

WarWatch is a static dashboard. `warwatch/run.py` fetches public series, scores them, applies the probability model
and writes `site/` (index.html, feed.xml, audit.json, index.json, series.json). GitHub Actions rebuilds it about every
30 minutes and deploys it to GitHub Pages (https://khourix.github.io/warwatch/). The user surface is that page and its
RSS feed. There is no server: "launch" means render into a temp folder.

## Run it

```
.agents/skills/verify-warwatch/verify.sh quick       # never-list guard + all unit tests (about 3 min, no network)
.agents/skills/verify-warwatch/verify.sh full        # quick + demo render, parse, levels, links, screenshots, model, forward chain, no-writes (about 4 min, no network)
.agents/skills/verify-warwatch/verify.sh live-read   # GET the live audit.json: age under 90 min, model_ran true
```

One verdict line per check (`PASS`, `FAIL`, `SKIP`), then a summary line. Exit 0 means no check failed.
Before you open a PR, run `full` and paste its output in the PR body.

Needs: `python3` (3.9+, standard library only) and, for `links-rendered` and `screenshot`, Chrome or Chromium.
The script looks in `$CHROME`, `/Applications/Google Chrome.app`, the Playwright cache, then `google-chrome`/`chromium` on PATH.

## Launch

`full` runs `python3 warwatch/run.py --demo buildup --out <tmp>/site/index.html` with `WARWATCH_HISTORY=<tmp>/...`.
Demo mode uses the synthetic scenario in `warwatch/demo.py`: no network, no keys, and it skips the model and every
forward-record append. Ready means `render-demo` passed: all five output files exist. A real (non-demo) run is never
part of this skill (see Never).

## Doctor

`verify.sh quick`. If `never-guard` fails, stop: the guard is broken and no other check is safe to run.
If `unit-tests` fails, read `.verify-evidence/<run>/unit-tests.log`.

## Drive

Each check is a function in `checks.py`; names match the verdict lines.

| Check | Level | What it proves |
|---|---|---|
| `never-guard` | quick | the guard in `sh()` refuses every Never command, and allows the demo render |
| `unit-tests` | quick | `python3 -m unittest test_warwatch` in `warwatch/tests` passes (all classes; see Gotchas) |
| `render-demo` | full | the site builds: index.html, feed.xml, audit.json, index.json, series.json |
| `outputs-parse` | full | the JSON files parse, feed.xml is valid XML with items, no template placeholder is left |
| `every-area-level` | full | every theatre and the global area has a level (Normal, Watch, Elevated, Critical or insufficient data) |
| `links-template` | full | no empty `href`/`src` in index.html; local ones (feed.xml, icons, fonts) exist in the site folder |
| `links-data` | full | every source link in the page data and series.json (`url`, `u`) is an http(s) URL |
| `links-rendered` | full | headless Chrome renders 7 routes; no empty or `undefined` href or `data-nav` target |
| `screenshot` | full | PNGs of the overview and `#iran` routes, saved as evidence |
| `audit-model-ran` | full | audit.json carries `model_ran`; it is `false` on the demo render because demo skips the model |
| `model-runs` | full | `model.apply` on the demo scenario (forward path `/dev/null`) gives a probability for every theatre |
| `forward-chain` | full | `forward/log.csv`, `log_armed.csv`, `log_wave.csv` hash chains verify (read-only) |
| `no-writes` | full | `forward/`, `warwatch/history/` and `git status` are byte-for-byte unchanged after the run |
| `live-fresh` | live-read | live audit.json was generated under 90 minutes ago and has theatres and series |
| `live-model-ran` | live-read | live audit.json says `model_ran: true` |

To look at a route yourself after a `full` run, render again and open it:
`python3 warwatch/run.py --demo buildup --out /tmp/ww/index.html && open "/tmp/ww/index.html#iran/signals"`.
Routes are hash paths: `overview`, `region/<id>`, `<theatre>`, `<theatre>/signals|history|about|drivers`, `signals`,
`activity`, `record`, `settings/health`, `settings/method`.

## Evidence

`.verify-evidence/<YYYYmmdd-HHMMSS>/` at the repo root (git-ignored): `summary.txt` (the verdict lines),
`unit-tests.log`, `render.log`, `demo-audit.json`, `demo-index.json`, `demo-feed.xml`, `dom-overview.html`,
`screenshot-overview.png`, `screenshot-iran.png`, `model-probe.log`, `live-audit.json`. Paste `summary.txt` in the PR.
Proof standard: a check passes on what it observed in files, the rendered DOM or the live response, never on a
command's exit code alone.

## Cleanup

The script deletes its own temp folder (`verify-warwatch-*` under the system temp dir) at the end. It starts no
server and no background process. The evidence folder stays. Delete old evidence folders by hand when you no longer need them.

## Never

The script refuses these in code (`NEVER` in `checks.py`, tested by `never-guard`); do not run them by hand either:

- `git push` of any kind. The public repo is written only by its own workflows (and by you through a PR branch, outside this skill).
- `gh workflow run|enable|disable`, `gh pr merge`, `gh api -X POST|PUT|PATCH|DELETE`. Never trigger workflows.
- `python3 warwatch/run.py` without `--demo`: it fetches live sources and appends `forward/log.csv` and the shadow records.
- `python3 warwatch/validate.py fit`, `python3 warwatch/forward_score.py`: they rewrite committed docs and records.
- Never edit or rewrite `forward/log.csv` (or `log_armed.csv`, `log_wave.csv`, `tells.csv`): they are hash-chained public records.

## Gotchas

- `python3 warwatch/tests/test_warwatch.py` (the README form) calls `unittest.main()` before the last class
  (`TestEngine`, 9 tests) is defined, so the script form runs 127 tests and skips those 9. The skill uses unittest discovery (136 tests).
- `quick` takes about 3 minutes, over the 2-minute target: the unit tests render the demo several times.
- The demo render does not run the model, so `model_ran` is `false` there by design. `model-runs` covers the model
  offline; `live-model-ran` covers the real build.
- `live-model-ran` fails until the PR that added `model_ran` is merged and the next live build has deployed.
- Without Chrome, `links-rendered` and `screenshot` fail (not skip): screenshots are required proof here.
- Feature map: [features/README.md](features/README.md).
