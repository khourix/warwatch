# Forward log

`forward/log.csv` is the public, hash-chained record of the probability the model gave each theatre each day, written before the outcome is known. `log_armed.csv` and `log_wave.csv` are the hidden shadow models' records. `forward_score.py` scores them; the Track record page (`#record`) shows the result.

## Sub-features

- `forward-chain` every row's `prev_hash` and `hash` verify, from the first row.
- `forward-untouched` a verification run never appends to or rewrites these files.
- `forward-page` the Track record page renders.

## How to get to it (user POV)

- `#record` on the page; `forward/log.csv` in the public repo.

## Driving it with verify.sh

Preconditions:

- A checkout with `forward/` (any branch).

- **Chain.** `forward-chain` runs `model.forward_verify` on the three files and prints their row counts.
- **Untouched.** `no-writes` requires `forward/` byte-for-byte unchanged after the run.
- **Page.** `links-rendered` renders `#record` in headless Chrome.
- **By hand.** Run `python3 -c "import sys; sys.path.insert(0,'warwatch'); import model; print(model.forward_verify()[:2])"`. It prints `(True, None)`.

## Gotchas

- Never edit these files, not even whitespace: one changed byte breaks the chain for every later row.
- Appends happen only in a non-demo `run.py` (once per day per theatre); the unit tests cover append logic against temp files.
