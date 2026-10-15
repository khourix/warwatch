# Theatre levels

A reader opens the page and sees each theatre, region and the global area with a level (Normal, Watch, Elevated, Critical, or insufficient data), set from the probability model when it is active and from the composite score otherwise.

## Sub-features

- `levels-all` every area in `index.json` has a valid level.
- `levels-map` the overview map and the Theatres panel show the areas.
- `levels-theatre` a theatre page (`#iran`) renders with its level and signals.
- `levels-model` the probability model gives a probability for every theatre.

## How to get to it (user POV)

- Open https://khourix.github.io/warwatch/ (overview map, Theatres panel).
- Choose a region in the left rail, or a theatre (`#iran`, `#ukraine`), or `#signals` for the table.

## Driving it with verify.sh

Preconditions:

- Demo render in `$T/site` (README baseline).

- **All levels.** Run `verify.sh full`. `every-area-level` reads `index.json` and prints `18 areas, all with a level {...}`.
- **Map and pages.** `screenshot` saves `screenshot-overview.png` (map with region badges, Theatres panel, DEMO tag) and `screenshot-iran.png`.
- **By hand.** Run `"$CHROME" --headless=new --screenshot=/tmp/iran.png --window-size=1440,1800 "file://$T/site/index.html#iran"`. The PNG shows the Iran page with its level pill.
- **Model.** `model-runs` applies `model.apply` to the demo scenario with `forward_path=/dev/null` and prints a probability for all 17 theatres.

## Gotchas

- The demo render skips the model, so demo levels are composite levels. The model is checked separately by `model-runs`.
- The buildup scenario is synthetic: levels there say nothing about the world.
- `checks.py` passes `--virtual-time-budget=15000` to headless Chrome so the page script finishes before the DOM dump or screenshot; keep it when you drive by hand.
