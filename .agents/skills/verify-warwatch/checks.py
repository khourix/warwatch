#!/usr/bin/env python3
"""verify-warwatch checks. Run through verify.sh: quick | full | live-read.

Prints one verdict line per check (PASS, FAIL or SKIP) and exits 0 only when no check failed.
Evidence goes to <repo>/.verify-evidence/<YYYYmmdd-HHMMSS>/. Standard library only.
"""
import datetime as dt
import glob
import hashlib
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=os.path.dirname(os.path.abspath(__file__)),
                      capture_output=True, text=True, check=True).stdout.strip()
WW = os.path.join(ROOT, "warwatch")
LIVE = "https://khourix.github.io/warwatch/"
LEVELS = ("Normal", "Watch", "Elevated", "Critical", "insufficient data")
MAX_AGE_MIN = 90

# The never list (SKILL.md). Every command this script runs goes through sh(), which refuses these.
NEVER = [
    (re.compile(r"\bgit\b.*\bpush\b"), "git push: the public repo is written only by its own workflows"),
    (re.compile(r"\bgh\b.*\bworkflow\b.*\b(run|enable|disable)\b"), "gh workflow run: never trigger workflows"),
    (re.compile(r"\bgh\b.*\b(pr\s+merge|api\b.*-X\s*(POST|PUT|PATCH|DELETE))"), "gh write calls"),
    (re.compile(r"\brun\.py\b(?!.*--demo)"), "run.py without --demo fetches live data and appends forward/log.csv"),
    (re.compile(r"\b(validate\.py\s+fit|forward_score\.py)\b"), "refit and forward scoring rewrite committed files"),
]


class Refused(Exception):
    pass


def guard(cmd):
    line = " ".join(cmd)
    for rx, why in NEVER:
        if rx.search(line):
            raise Refused(f"refused ({why}): {line}")


def sh(cmd, log=None, timeout=900, env=None, cwd=ROOT):
    guard(cmd)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       env=dict(os.environ, **(env or {})))
    if log:
        with open(log, "w") as f:
            f.write(f"$ {' '.join(cmd)}\nexit {p.returncode}\n--- stdout\n{p.stdout}\n--- stderr\n{p.stderr}")
    return p


class Run:
    def __init__(self, level):
        self.level = level
        self.ev = os.path.join(ROOT, ".verify-evidence", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
        os.makedirs(self.ev, exist_ok=True)
        self.tmp = tempfile.mkdtemp(prefix="verify-warwatch-")
        self.results = []

    def check(self, name, fn):
        t0 = time.time()
        try:
            out = fn()
            verdict, detail = out if isinstance(out, tuple) else ("PASS", out or "")
        except AssertionError as e:
            verdict, detail = "FAIL", str(e)
        except Exception as e:  # noqa: BLE001 - a crash in a check is a failed check
            verdict, detail = "FAIL", f"{type(e).__name__}: {e}"
        line = f"{verdict:4}  {name:18} {detail}  ({time.time() - t0:.0f}s)"
        print(line, flush=True)
        self.results.append((verdict, name, line))

    def finish(self):
        failed = [n for v, n, _ in self.results if v == "FAIL"]
        verdict = "FAIL" if failed else "PASS"
        summary = f"verify-warwatch {self.level}: {verdict}" + (f" (failed: {', '.join(failed)})" if failed else "")
        with open(os.path.join(self.ev, "summary.txt"), "w") as f:
            f.write("\n".join(l for _, _, l in self.results) + "\n" + summary + "\n")
        shutil.rmtree(self.tmp, ignore_errors=True)   # scratch only; the evidence folder stays
        print(summary)
        print("evidence:", os.path.relpath(self.ev, ROOT))
        return 1 if failed else 0


# ---------- quick ----------

def c_never_guard(r):
    for cmd in (["git", "push", "origin", "HEAD"], ["gh", "workflow", "run", "warwatch.yml"],
                ["python3", "warwatch/run.py", "--out", "site/index.html"], ["python3", "warwatch/validate.py", "fit"]):
        try:
            guard(cmd)
        except Refused:
            continue
        raise AssertionError(f"guard let through: {' '.join(cmd)}")
    guard(["python3", "warwatch/run.py", "--demo", "buildup", "--out", "x/index.html"])
    return "4 never-list commands refused, demo render allowed"


def c_unit_tests(r):
    # unittest discovery, not `python3 test_warwatch.py`: that entry calls unittest.main() before the classes
    # defined below it (TestEngine), so the script form skips them.
    p = sh([sys.executable, "-m", "unittest", "test_warwatch"], log=os.path.join(r.ev, "unit-tests.log"),
           env={"WARWATCH_HISTORY": os.path.join(r.tmp, "history-tests")}, cwd=os.path.join(WW, "tests"))
    ran = re.findall(r"Ran (\d+) tests?", p.stderr)
    assert p.returncode == 0, f"exit {p.returncode}; see unit-tests.log: " + (p.stderr.strip().splitlines() or ["?"])[-1]
    return f"{ran[-1] if ran else '?'} tests OK"


# ---------- full ----------

def snapshot():
    """Everything a render must not touch: hashes of the forward records and history CSVs, and the git status lines."""
    files = glob.glob(os.path.join(ROOT, "forward", "**"), recursive=True) + glob.glob(os.path.join(WW, "history", "**"), recursive=True)
    snap = {}
    for p in sorted(f for f in files if os.path.isfile(f)):
        with open(p, "rb") as f:
            snap[os.path.relpath(p, ROOT)] = hashlib.sha256(f.read()).hexdigest()
    st = sh(["git", "status", "--porcelain", "--untracked-files=all"]).stdout
    snap["git status"] = "\n".join(l for l in st.splitlines() if ".verify-evidence/" not in l)
    return snap


def c_render(r):
    r.site = os.path.join(r.tmp, "site")
    p = sh([sys.executable, "warwatch/run.py", "--demo", "buildup", "--out", os.path.join(r.site, "index.html")],
           log=os.path.join(r.ev, "render.log"), env={"WARWATCH_HISTORY": os.path.join(r.tmp, "history-render")})
    assert p.returncode == 0, f"run.py --demo buildup exit {p.returncode}; see render.log"
    missing = [f for f in ("index.html", "feed.xml", "audit.json", "index.json", "series.json") if not os.path.isfile(os.path.join(r.site, f))]
    assert not missing, "missing " + ", ".join(missing)
    for f in ("audit.json", "index.json", "feed.xml"):
        shutil.copyfile(os.path.join(r.site, f), os.path.join(r.ev, "demo-" + f))
    return "index.html, feed.xml, audit.json, index.json, series.json written"


def page_data(site):
    with open(os.path.join(site, "index.html"), encoding="utf-8") as f:
        page = f.read()
    assert "__DATA__" not in page and "__GENERATED__" not in page, "template placeholder left in index.html"
    return page


def c_parse(r):
    page_data(r.site)
    for f in ("audit.json", "index.json", "series.json"):
        with open(os.path.join(r.site, f)) as fh:
            json.load(fh)
    items = ET.parse(os.path.join(r.site, "feed.xml")).getroot().findall(".//item")
    return f"audit.json, index.json, series.json parse; feed.xml parses ({len(items)} items)"


def c_levels(r):
    with open(os.path.join(r.site, "index.json")) as f:
        s = json.load(f)
    areas = dict(s["theatres"], **{"global": s["global"]})
    bad = {a: v.get("level") for a, v in areas.items() if v.get("level") not in LEVELS}
    assert not bad, f"areas without a valid level: {bad}"
    count = {}
    for v in areas.values():
        count[v["level"]] = count.get(v["level"], 0) + 1
    return f"{len(areas)} areas, all with a level {count}"


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in ("href", "src"):
            if k in a and tag in ("a", "link", "script", "img"):
                self.refs.append((tag, k, a[k]))


def local_ok(site, ref):
    path = ref.split("#")[0].split("?")[0]
    return not path or os.path.isfile(os.path.join(site, path))


def c_links_static(r):
    p = Links()
    p.feed(page_data(r.site))
    bad = [x for x in p.refs if not x[2] or x[2].strip() in ("#", "undefined", "null")]
    bad += [x for x in p.refs if x[2] and not re.match(r"^(https?:|mailto:|data:|#|\$\{)", x[2]) and not local_ok(r.site, x[2])]
    assert not bad, f"bad links in index.html: {bad[:5]}"
    return f"{len(p.refs)} links in the template, local files present"


def chrome():
    for c in [os.environ.get("CHROME"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              *sorted(glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*")), reverse=True),
              shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")]:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def headless(r, *args, timeout=120):
    prof = tempfile.mkdtemp(dir=r.tmp)
    cmd = [chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
           f"--user-data-dir={prof}", "--allow-file-access-from-files", "--virtual-time-budget=15000", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def walk_urls(x, path=""):
    """Every value under a key named url or u in the page data (series sources, official reports, markets)."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("url", "u") and not isinstance(v, (dict, list)):
                yield path + "." + k, v
            else:
                yield from walk_urls(v, path + "." + str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk_urls(v, f"{path}[{i}]")


def c_links_data(r):
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', page_data(r.site), re.S)
    assert m, "no inline data block in index.html"
    data = json.loads(m.group(1))
    with open(os.path.join(r.site, "series.json")) as f:
        urls = list(walk_urls(data)) + list(walk_urls(json.load(f), "series.json"))
    bad = [(k, v) for k, v in urls if v not in (None, "") and not re.match(r"^https?://[^\s/]+\.[^\s]+$", str(v))]
    assert not bad, f"{len(bad)} malformed source links: {bad[:5]}"
    have = [v for _, v in urls if v]
    assert have, "no source links in the page data"
    return f"{len(have)} source links in the page data, all http(s) URLs"


ROUTES = ("", "#iran", "#iran/signals", "#ukraine/about", "#signals", "#record", "#settings/method")


def c_links_rendered(r):
    if not chrome():
        return "FAIL", "no Chrome or Chromium found; set CHROME=/path/to/chrome"
    url = "file://" + os.path.join(r.site, "index.html")
    hrefs, navs, bad = 0, set(), []
    for route in ROUTES:
        p = headless(r, "--dump-dom", url + route)
        assert p.returncode == 0 and "<html" in p.stdout, f"dump-dom {route or 'overview'} failed"
        if not route:
            with open(os.path.join(r.ev, "dom-overview.html"), "w") as f:
                f.write(p.stdout)
        lp = Links()
        lp.feed(p.stdout)
        for tag, k, ref in lp.refs:
            if tag != "a":
                continue
            hrefs += 1
            if not ref or "undefined" in ref or "null" == ref or "${" in ref:
                bad.append(f"{route or 'overview'}: href={ref!r}")
            elif not re.match(r"^(https?:|mailto:|data:|#)", ref) and not local_ok(r.site, ref):
                bad.append(f"{route or 'overview'}: {ref} not in the site folder")
        for nav in re.findall(r'data-nav="([^"]*)"', p.stdout.split('<script id="data"')[0]):
            if "${" in nav:
                continue   # inside a page script template, not rendered
            navs.add(nav)
            if not nav.strip() or "undefined" in nav or "null" in nav:
                bad.append(f"{route or 'overview'}: data-nav={nav!r}")
    assert navs, "rendered page has no navigation targets: the page script did not run"
    assert not bad, f"{len(bad)} empty or broken links: {bad[:5]}"
    return f"{len(ROUTES)} routes rendered: {hrefs} hrefs and {len(navs)} distinct nav targets, none empty, local files present"


def c_screenshot(r):
    if not chrome():
        return "FAIL", "no Chrome or Chromium found; set CHROME=/path/to/chrome"
    url = "file://" + os.path.join(r.site, "index.html")
    shots = []
    for route, name in (("", "overview"), ("#iran", "iran")):
        out = os.path.join(r.ev, f"screenshot-{name}.png")
        headless(r, f"--screenshot={out}", "--window-size=1440,1800", url + route)
        assert os.path.isfile(out) and os.path.getsize(out) > 20_000, f"screenshot {name} missing or blank"
        shots.append(f"{os.path.basename(out)} {os.path.getsize(out) // 1024} KB")
    return ", ".join(shots)


def c_model_ran_key(r):
    with open(os.path.join(r.site, "audit.json")) as f:
        a = json.load(f)
    assert "model_ran" in a, "audit.json has no model_ran"
    assert a["model_ran"] is False, f"demo render must report model_ran false (demo skips the model), got {a['model_ran']!r}"
    return "audit.json model_ran=false on the demo render (demo skips the model by design)"


MODEL_PROBE = """
import json, os, sys
sys.path.insert(0, "warwatch")
import demo, model, run
res = run.evaluate(demo.scenario("buildup"))
res = model.apply(res, forward_path=os.devnull)
m = res.get("model") or {}
print(json.dumps({"ran": bool(m), "version": m.get("version"), "active": m.get("active"),
                  "theatres": {t: round(v["p"], 4) for t, v in (m.get("theatres") or {}).items()}, "expected": model.TH}))
"""


def c_model_runs(r):
    p = sh([sys.executable, "-c", MODEL_PROBE], log=os.path.join(r.ev, "model-probe.log"),
           env={"WARWATCH_HISTORY": os.path.join(r.tmp, "history-model")})
    assert p.returncode == 0, f"model probe exit {p.returncode}; see model-probe.log"
    o = json.loads(p.stdout.strip().splitlines()[-1])
    assert o["ran"], "model.apply did not set res['model']"
    missing = [t for t in o["expected"] if t not in o["theatres"]]
    assert not missing, f"no probability for {missing}"
    bad = {t: p for t, p in o["theatres"].items() if not 0 <= p <= 1}
    assert not bad, f"probabilities out of range: {bad}"
    return f"model {o['version']} (active={o['active']}) gives a probability for all {len(o['theatres'])} theatres"


def c_forward_chain(r):
    p = sh([sys.executable, "-c", "import sys; sys.path.insert(0,'warwatch'); import model, activity\n"
            "for f in (model.FORWARD, model.FORWARD_ARMED, model.FORWARD_WAVE):\n"
            "    ok, bad, rows = model.forward_verify(f); print(f.split('/')[-1], ok, bad, len(rows))\n"
            "ok, bad, rows = activity.forward_verify(); print(activity.FORWARD.split('/')[-1], ok, bad, len(rows))"])
    assert p.returncode == 0, p.stderr.strip()[-200:]
    rows = [l.split() for l in p.stdout.strip().splitlines()]
    broken = [f"{n} row {b}" for n, ok, b, _ in rows if ok != "True"]
    assert not broken, "hash chain broken: " + ", ".join(broken)
    return "hash chains intact: " + ", ".join(f"{n} {c} rows" for n, _, _, c in rows)


def c_no_writes(r):
    now = snapshot()
    changed = sorted(k for k in set(now) | set(r.before) if now.get(k) != r.before.get(k))
    assert not changed, f"changed during the run: {', '.join(changed[:5])}" + (f" (git status now: {now['git status']!r:.200})" if "git status" in changed else "")
    return "forward/, warwatch/history/ and git status unchanged"


# ---------- live-read ----------

def live_audit(r):
    if not hasattr(r, "live"):
        req = urllib.request.Request(LIVE + "audit.json", headers={"User-Agent": "verify-warwatch (read-only)", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
        with open(os.path.join(r.ev, "live-audit.json"), "wb") as f:
            f.write(body)
        r.live = json.loads(body)
    return r.live


def c_live_fresh(r):
    a = live_audit(r)
    gen = dt.datetime.strptime(a["generated"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=dt.timezone.utc)
    age = (dt.datetime.now(dt.timezone.utc) - gen).total_seconds() / 60
    assert age <= MAX_AGE_MIN, f"stale: generated {a['generated']}, {age:.0f} min old (limit {MAX_AGE_MIN})"
    assert a.get("theatres") and a.get("series"), "live audit.json has no theatres or series"
    return f"generated {a['generated']}, {age:.0f} min old, {len(a['theatres'])} theatres, {len(a['series'])} scored series"


def c_live_model_ran(r):
    a = live_audit(r)
    assert "model_ran" in a, "no model_ran field: the live build predates it"
    assert a["model_ran"] is True, f"model_ran={a['model_ran']!r}: the model failed on the last live build"
    return "model_ran=true on the last live build"


QUICK = [("never-guard", c_never_guard), ("unit-tests", c_unit_tests)]
FULL = QUICK + [("render-demo", c_render), ("outputs-parse", c_parse), ("every-area-level", c_levels),
                ("links-template", c_links_static), ("links-data", c_links_data), ("links-rendered", c_links_rendered), ("screenshot", c_screenshot),
                ("audit-model-ran", c_model_ran_key), ("model-runs", c_model_runs), ("forward-chain", c_forward_chain),
                ("no-writes", c_no_writes)]
LIVE_READ = [("live-fresh", c_live_fresh), ("live-model-ran", c_live_model_ran)]


def main(argv):
    level = argv[0] if argv else ""
    checks = {"quick": QUICK, "full": FULL, "live-read": LIVE_READ}.get(level)
    if checks is None:
        print("usage: verify.sh quick | full | live-read")
        return 2
    r = Run(level)
    r.before = snapshot()
    print(f"verify-warwatch {level} at {sh(['git', 'rev-parse', '--short', 'HEAD']).stdout.strip()}")
    for name, fn in checks:
        if name in ("outputs-parse", "every-area-level", "links-template", "links-data", "links-rendered",
                                               "screenshot", "audit-model-ran") and not getattr(r, "site", None):
            r.check(name, lambda: ("SKIP", "render-demo failed"))
            continue
        r.check(name, lambda fn=fn: fn(r))
    return r.finish()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
