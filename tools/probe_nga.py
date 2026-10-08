import os, sys, json, re, collections, datetime as dt, tempfile
sys.path.insert(0, "warwatch")
os.environ["WARWATCH_HISTORY"] = tempfile.mkdtemp()
import extras, store, config as C, sources as S
raw = S.get(extras.NGA_URL)["smaps"]
print("rows", len(raw))
# coverage: per usNavArea family, sequence numbers issued since Aug 1 should be consecutive if cancelled ones are all kept
by = collections.defaultdict(list)
for r in raw:
    m = re.search(r"(\d{2})(\d{4})Z\s+([A-Z]{3})\s+(\d{4})", r.get("createdOn") or "")
    if not m: continue
    d = dt.date(int(m.group(4)), extras.MONTHS[m.group(3)], int(m.group(1)))
    by[(r.get("msgType"), d.year)].append((d, r.get("msgSqncNumber")))
for (t, y), v in sorted(by.items()):
    if y != 2026: continue
    nums = sorted(n for d, n in v if d >= dt.date(2026, 7, 1))
    jul = sorted(n for d, n in v if dt.date(2026, 7, 1) <= d < dt.date(2026, 8, 1))
    aug = sorted(n for d, n in v if d >= dt.date(2026, 8, 1))
    print(t, y, "since Jul1:", len(nums), "range", nums[:1], nums[-1:], "| July:", len(jul), jul[:1], jul[-1:], "| since Aug1:", len(aug), "expected", (aug[-1] - aug[0] + 1) if aug else 0)
# first date per family where numbering is gap-free
for t in sorted({k[0] for k in by}):
    v = sorted((d, n) for (tt, y), L in by.items() if tt == t and y == 2026 for d, n in L)
    nums = sorted(n for d, n in v)
    seen = set(nums); mx = max(nums)
    first_gap = next((n for n in range(min(nums), mx) if n not in seen), None)
    print(t, "n", len(nums), "min", min(nums), "max", mx, "missing", len([n for n in range(min(nums), mx + 1) if n not in seen]), "last missing num", max([n for n in range(min(nums), mx + 1) if n not in seen], default=None))
extras._CACHE["nga"] = extras.parse_nga(extras.smaps_to_warnings(raw))
print("hazard warnings with positions", len(extras._CACHE["nga"]), "active", sum(1 for m in extras._CACHE["nga"] if m["active"]))
for th in C.BOXES:
    pts = extras.nga_series(th)
    print(th, len(pts), pts[0], pts[-1], "max", max(v for _, v in pts), "nonzero days", sum(1 for _, v in pts if v))
