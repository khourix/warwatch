# History append

Some sources only expose "now" (ADS-B counts, advisory levels). Each real build appends one row per such series to `warwatch/history/<id>.csv` and the workflow commits it, so the page can show their history.

## Sub-features

- `history-append` `store.append` writes a timestamped row; `store.daily` collapses rows to daily means.
- `history-untouched` a verification run never writes to the committed `warwatch/history/`.

## How to get to it (user POV)

- A theatre's History tab (`#israel/history`) and the series detail charts.
- The `history: <time>` commits on `main`, made by the warwatch workflow.

## Driving it with verify.sh

Preconditions:

- `WARWATCH_HISTORY` points at a temp folder (the script sets it for every subprocess).

- **Append logic.** `unit-tests` runs `TestStore.test_append_and_daily_mean` against a temp history folder.
- **Untouched.** `no-writes` hashes every file under `warwatch/history/` and `forward/` plus `git status` before and after the run and requires them equal.
- **By hand, sandboxed.** Run `WARWATCH_HISTORY=$(mktemp -d) python3 -c "import sys; sys.path.insert(0,'warwatch'); import store; store.append('x', 1.5); print(store.load('x'))"`. It prints one `(time, 1.5)` row and touches nothing in the repo.

## Gotchas

- The real append happens only in a non-demo `run.py`, which this skill never runs. The real append is proven by the `history:` commits on `main`, not by this skill.
- `.gitattributes` merges concurrent appends with `union`; do not reformat these CSVs.
