# Audit

`audit.json` is published next to the page. It holds, per theatre, the domain groups and z-scores behind the level, per series the score inputs, and `model_ran`: whether the probability model ran on that build. A build can stay green while the model fails (run.py catches the error to keep the page up); `model_ran: false` makes that visible.

## Sub-features

- `audit-built` the render writes `audit.json` and it parses.
- `audit-model-ran` the file has `model_ran` (false on demo, true on a healthy live build).
- `audit-live-fresh` the live file is under 90 minutes old.

## How to get to it (user POV)

- https://khourix.github.io/warwatch/audit.json

## Driving it with verify.sh

Preconditions:

- `full`: demo render in `$T/site`. `live-read`: network access to khourix.github.io.

- **Built.** `outputs-parse` parses it; `demo-audit.json` is saved in the evidence.
- **Demo flag.** `audit-model-ran` requires `"model_ran": false` on the demo render.
- **Live.** Run `verify.sh live-read`. `live-fresh` prints the `generated` time and age; `live-model-ran` requires `"model_ran": true`. The response is saved as `live-audit.json`.
- **By hand.** Run `curl -s https://khourix.github.io/warwatch/audit.json | python3 -c "import json,sys; a=json.load(sys.stdin); print(a['generated'], a.get('model_ran'))"`.

## Gotchas

- `generated` is minute precision UTC (`2026-10-15 09:25 UTC`).
- Until the PR that added `model_ran` is deployed, `live-model-ran` fails with "the live build predates it".
- Unit tests `ModelRan.*` cover `run.run_model` returning true, false on an exception, and false with no weights.
