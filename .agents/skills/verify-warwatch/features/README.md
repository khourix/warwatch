# WarWatch verification map

The maintained source for verifying what a WarWatch reader sees. Read this index, then use the feature file as the recipe.

## Baseline preconditions

- A checkout of this repo; `python3` 3.9 or newer; Chrome or Chromium for rendered checks.
- Render only the demo: `python3 warwatch/run.py --demo buildup --out "$T/site/index.html"` with `WARWATCH_HISTORY="$T/history"` and `T=$(mktemp -d)`.
- Never run `run.py` without `--demo`, and never push or trigger workflows (SKILL.md, Never).

## Driving conventions

- `verify.sh full` drives every feature below; the feature files say which check proves what and how to drive it by hand.
- Routes are hash paths on `index.html` (for example `#iran/signals`). Headless Chrome: `--dump-dom` for the DOM, `--screenshot` for proof.
- Assert on the output files (`index.json`, `audit.json`, `feed.xml`) and the rendered DOM, not on log lines.

## Proof and skip reporting

- Paste the verdict lines from `.verify-evidence/<run>/summary.txt`.
- A screenshot proves the page renders; the DOM and JSON files prove what it says.
- Report a check you could not run (no Chrome, no network for live-read) as not verified, never as passed.

## Features

- [Theatre levels](./theatre-levels.md): every theatre, region and the global area shows a level on the map and pages.
- [Feed](./feed.md): `feed.xml`, the RSS feed of this week's tells and readings.
- [History append](./history-append.md): CSV history for sources that only expose "now".
- [Audit](./audit.md): `audit.json`, the per-theatre audit trail and `model_ran`.
- [Forward log](./forward-log.md): `forward/log.csv`, the hash-chained public record of daily probabilities.
