"""Event desk: a free LLM reads public headlines and proposes qualifying events (docs/EVENTDESK_PLAN.md; accuracy proposal P1).

Nothing here writes warwatch/data/events.csv. The desk proposes; a person approves each row before it is added by hand.

    python3 warwatch/eventdesk.py blindtest --provider groq --budget 55   # the pre-registered test, resumable, one day's quota at a time
    python3 warwatch/eventdesk.py report                                 # recall, extras and the review sample -> docs/EVENTDESK_TEST.md
    python3 warwatch/eventdesk.py propose                                # live: candidates since events_through.txt (needs a passed test)
    python3 warwatch/eventdesk.py prompt iran 2024-04-08                 # print one prompt with its headlines, call nothing

Headlines come from Google News search (the same public RSS the build uses), one query per area per 7 days, read only for the title,
outlet and date. The LLM may cite only those headlines; a candidate without a valid citation is dropped.
"""
import argparse
import csv
import datetime as dt
import gzip
import html
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import llm  # noqa: E402
import model  # noqa: E402

DESK = os.path.join(model.ROOT, "backtest", "eventdesk")
NEWS = os.path.join(DESK, "news")
VERDICT = os.path.join(DESK, "verdict.json")
TEST_DOC = os.path.join(model.ROOT, "docs", "EVENTDESK_TEST.md")
CAND_CSV = os.path.join(model.DATA, "event_candidates.csv")
CAND_DOC = os.path.join(model.ROOT, "docs", "EVENT_CANDIDATES.md")
EVENTS = os.path.join(model.DATA, "events.csv")
THROUGH = os.path.join(model.DATA, "events_through.txt")

# Fixed in docs/EVENTDESK_PLAN.md before the test ran.
TEST_START, TEST_END = dt.date(2024, 7, 1), dt.date(2025, 12, 31)
WINDOW = 14             # days per LLM call
MATCH_DAYS = 3          # a candidate finds a listed event within this many days, in the same area
EPISODE_DAYS = 30       # the codebook's continuation rule: 30 days after an event are the same episode
REVIEW_N, REVIEW_SEED = 40, 20261109
RECALL_PASS, PRECISION_PASS = 0.90, 0.50
MAX_HEADLINES = 160
TYPES = ("onset", "strike", "maritime", "exercise", "other")

PLACES = {   # Google News search terms per area (the theatre or sub-theatre and its usual names in headlines)
    "ukraine": ["Ukraine", "Russia", "Belarus", "Moldova"],
    "europe_east": ["Poland", "Lithuania", "Latvia", "Estonia", "Finland", "Romania", "Baltic"],
    "iran": ["Iran", "IRGC"],
    "iraq": ["Iraq", "Baghdad", "Erbil"],
    "gulf": ["Saudi", "UAE", "Emirates", "Qatar", "Bahrain", "Kuwait", "Oman"],
    "lebanon": ["Lebanon", "Hezbollah", "Beirut"],
    "syria": ["Syria", "Damascus", "Aleppo", "Idlib"],
    "yemen": ["Yemen", "Houthi", "Houthis", "\"Red Sea\"", "\"Gulf of Aden\""],
    "israel": ["Israel", "Gaza", "Hamas", "\"West Bank\""],
    "taiwan": ["Taiwan"],
    "scs": ["\"South China Sea\"", "Philippines", "Vietnam", "Scarborough", "\"Second Thomas\""],
    "korea": ["\"North Korea\"", "\"South Korea\"", "Pyongyang"],
    "southasia": ["India", "Pakistan", "Kashmir"],
    "libya": ["Libya", "Tripoli", "Benghazi"],
    "sudan": ["Sudan", "RSF", "Khartoum", "Darfur"],
    "drc": ["Congo", "M23", "Goma"],
    "venezuela": ["Venezuela", "Guyana", "Caribbean"],
}
# Google News drops the date limits when a query has more than about 15 terms, so each query is one place name and one of two short
# action lists (checked live, 2026-11-09).
ACTIONS = (["strike", "airstrike", "attack", "missile", "drone", "offensive", "invasion", "clashes", "shelling"],
           ["drills", "exercise", "blockade", "seized", "sabotage", "cable", "coup", "troops", "warships"])

CODEBOOK = """A qualifying event is one of:
- onset: a war onset, or a major new ground offensive by a state;
- strike: a wave of state strikes on another state's territory, or a missile or drone exchange between states;
- maritime: an attack on commercial or naval shipping, or a blockade;
- exercise: a named, large-scale military exercise or drill around a contested border or strait, run by the state that disputes it;
- other: a coup with fighting, or organised armed force used across or within a border in a way that changes the area's risk.
Not events: diplomacy, sanctions, leadership changes without fighting, territory changes without new fighting, and the continuation of
an operation already under way. A new event must be a distinct new escalation, not more of what is already happening."""


# ---------------------------------------------------------------- headlines
def query(place, acts, start, end):
    """Google News search for one place name, one action list and dates [start, end]. `before:` is exclusive: the day after end."""
    return f"{place} ({' OR '.join(acts)}) after:{start.isoformat()} before:{(end + dt.timedelta(days=1)).isoformat()}"


def _rss(q, timeout=40):
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_rss(xml, start, end):
    """-> [{d, src, t, u}] for items dated inside [start, end], titles without the ' - Outlet' tail."""
    out = []
    for it in re.findall(r"<item>.*?</item>", xml, re.S):
        title = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", (re.search(r"<title>(.*?)</title>", it, re.S) or [None, ""])[1])).strip()
        src = html.unescape((re.search(r"<source[^>]*>(.*?)</source>", it, re.S) or [None, ""])[1]).strip()
        pub = (re.search(r"<pubDate>(.*?)</pubDate>", it) or [None, ""])[1]
        try:
            d = dt.datetime.strptime(pub[5:16], "%d %b %Y").date()
        except ValueError:
            continue
        if not title or not start <= d <= end:
            continue
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3].strip()
        link = html.unescape((re.search(r"<link>(.*?)</link>", it, re.S) or [None, ""])[1]).strip()
        out.append({"d": d.isoformat(), "src": src or "News", "t": title, "u": link})
    return out


def cap(heads, n=MAX_HEADLINES):
    """At most n headlines, taken in turn from each day so a busy day cannot crowd out the rest; oldest first."""
    days = {}
    for h in heads:
        days.setdefault(h["d"], []).append(h)
    out, i = [], 0
    while len(out) < n and any(i < len(v) for v in days.values()):
        out += [v[i] for v in days.values() if i < len(v)][: n - len(out)]
        i += 1
    return sorted(out, key=lambda h: h["d"])


def fetch_news(unit, start, end, rss=_rss, sleep=time.sleep, pause=1.5):
    """Headlines for one area and window: for each 7 days, each place name and each action list, de-duplicated by title."""
    got, seen = [], set()
    a = start
    while a <= end:
        b = min(end, a + dt.timedelta(days=6))
        for place in PLACES[unit]:
            for acts in ACTIONS:
                try:
                    items = parse_rss(rss(query(place, acts, a, b)), a, b)
                except Exception as e:  # noqa: BLE001  a failed query leaves a gap; the answer records how many headlines it saw
                    print(f"news {unit} {place} {a}: {str(e)[:100]}", flush=True)
                    items = []
                for h in items:
                    k = re.sub(r"\W+", " ", h["t"].lower()).strip()[:90]
                    if k not in seen:
                        seen.add(k)
                        got.append(h)
                sleep(pause)
        a = b + dt.timedelta(days=1)
    return cap(got)


def cached_news(unit, start, end, root=NEWS, **kw):
    """Headlines for a test window, fetched once and kept, so every provider reads exactly the same list."""
    path = os.path.join(root, unit, f"{start.isoformat()}.json.gz")
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            return json.load(f)
    heads = fetch_news(unit, start, end, **kw)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt") as f:
        json.dump(heads, f, separators=(",", ":"))
    return heads


# ---------------------------------------------------------------- the question and the answer
def area(unit):
    th = C.THEATRES[unit]
    if unit in C.SUBTHEATRES:
        return f"{th['name']} (events on its territory or waters, including strikes there by or on foreign forces)"
    return f"the {th['name']} theatre ({', '.join(th['countries'])})"


def prompt(unit, start, end, heads, listed=()):
    """The question for one area and window. `listed`: [(date, type, description)] already on the list (live use only; never in the test)."""
    lines = "\n".join(f"[{i}] {h['d']} | {h['src']} | {h['t'][:160]}" for i, h in enumerate(heads, 1)) or "(no headlines)"
    known = ""
    if listed:
        known = "\nAlready on the list (do not propose these again):\n" + "\n".join(f"- {d}: {t}: {s}" for d, t, s in listed) + "\n"
    return f"""You keep a list of military events for an early-warning research project. Work only from the numbered headlines below.

Area: {area(unit)}.
Window: {start.isoformat()} to {end.isoformat()}.

{CODEBOOK}
{known}
Headlines (id | date | outlet | headline):
{lines}

List every qualifying event in this area that started inside the window. Give the first day it qualified. Cite the ids of the
headlines that report it; an event without a cited headline is not accepted. If several headlines report the same event, it is one
event. Answer with JSON only, in this form:
{{"events": [{{"date": "YYYY-MM-DD", "type": "onset|strike|maritime|exercise|other", "description": "at most 20 words", "evidence": [1, 2]}}]}}
If there is none, answer {{"events": []}}."""


def parse_answer(text):
    """-> list of raw event dicts, or None when the answer is not the JSON asked for."""
    s = (text or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < i:
        return None
    try:
        obj = json.loads(s[i: j + 1])
    except ValueError:
        return None
    ev = obj.get("events") if isinstance(obj, dict) else None
    return ev if isinstance(ev, list) else None


def source_of(h):
    return f"{h['src']}, '{h['t']}' ({h['d']}) {h['u']}".strip()


def validate(raw, heads, start, end):
    """Keep candidates that cite real headlines, have a known type, a date inside the window and no later than their last cited headline.
    -> (kept, rejected) where kept rows carry date, type, description, evidence (headline dicts) and source."""
    kept, rejected = [], []
    for e in raw or []:
        why = None
        try:
            d = dt.date.fromisoformat(str(e.get("date", ""))[:10])
        except ValueError:
            d, why = None, "date"
        ids = [i for i in (e.get("evidence") or []) if isinstance(i, int) and 1 <= i <= len(heads)]
        typ = str(e.get("type", "")).strip().lower()
        if why is None and not ids:
            why = "no valid citation"
        elif why is None and typ not in TYPES:
            why = "type"
        elif why is None and not start <= d <= end:
            why = "outside window"
        elif why is None:
            ev = [heads[i - 1] for i in ids]
            if d > max(dt.date.fromisoformat(h["d"]) for h in ev):
                why = "dated after its headlines"
        if why:
            rejected.append({"raw": e, "why": why})
            continue
        ev = sorted((heads[i - 1] for i in ids), key=lambda h: h["d"])
        kept.append({"date": d.isoformat(), "type": typ, "description": str(e.get("description", ""))[:200], "evidence": ev,
                     "source": source_of(ev[0])})
    return kept, rejected


# ---------------------------------------------------------------- listed events and matching
def listed_events(path=EVENTS):
    """-> [(date, set of areas it labels, type, description)]: the theatre plus any sub-theatre sites."""
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.append((dt.date.fromisoformat(r["date"]), {r["theatre"], *C.sites(r.get("site_theatre"))}, r["type"], r["description"]))
    return out


def windows(start=TEST_START, end=TEST_END):
    a = start
    while a <= end:
        yield a, min(end, a + dt.timedelta(days=WINDOW - 1))
        a += dt.timedelta(days=WINDOW)


def score(cands, events, start=TEST_START, end=TEST_END):
    """cands: [{unit, date, ...}]. -> dict with recall over listed events in [start, end], the missed ones, and the extras: candidates
    that match no listed event and do not fall in a listed event's 30-day episode, merged into one per area and 30 days."""
    cd = [(c["unit"], dt.date.fromisoformat(c["date"]), c) for c in cands]
    inside = [e for e in events if start <= e[0] <= end]
    found, missed = [], []
    for d, units, typ, desc in inside:
        hit = any(u in units and abs((cdate - d).days) <= MATCH_DAYS for u, cdate, _ in cd)
        (found if hit else missed).append({"date": d.isoformat(), "areas": sorted(units), "type": typ, "description": desc})
    extras, continuation, last = [], 0, {}
    for u, cdate, c in sorted(cd, key=lambda x: (x[0], x[1])):
        near = [d for d, units, _, _ in events if u in units and -MATCH_DAYS <= (cdate - d).days <= EPISODE_DAYS]
        if any(abs((cdate - d).days) <= MATCH_DAYS for d in near):
            continue
        if near:
            continuation += 1
            continue
        if u in last and (cdate - last[u]).days <= EPISODE_DAYS:
            continue
        last[u] = cdate
        extras.append(c)
    n = len(inside)
    return {"events": n, "found": len(found), "recall": round(len(found) / n, 3) if n else None, "missed": missed,
            "extras": extras, "continuation": continuation}


# ---------------------------------------------------------------- the blind test
def answers_path(provider):
    return os.path.join(DESK, f"answers_{provider}.jsonl")


def load_answers(provider):
    path = answers_path(provider)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip()]


def blindtest(provider, budget, ask=llm.ask, news=cached_news, sleep=time.sleep, pause=None, units=None):
    """Answers up to `budget` (area, window) questions not yet answered, in time order, appending each to answers_<provider>.jsonl.
    The prompt never lists known events. -> number answered this run."""
    pause = llm.PROVIDERS[provider]["pause"] if pause is None else pause
    done = {(a["unit"], a["start"]) for a in load_answers(provider)}
    os.makedirs(DESK, exist_ok=True)
    n = 0
    for start, end in windows():
        for unit in units or model.TH:
            if (unit, start.isoformat()) in done:
                continue
            if n >= budget:
                return n
            heads = news(unit, start, end)
            try:
                text, version = ask(prompt(unit, start, end, heads), provider)
            except llm.DailyLimit as e:
                print(f"stopping for today: {e}", flush=True)
                return n
            raw = parse_answer(text)
            kept, rejected = validate(raw, heads, start, end)
            row = {"unit": unit, "start": start.isoformat(), "end": end.isoformat(), "model": version, "headlines": len(heads),
                   "parse_error": raw is None, "kept": [{**k, "unit": unit} for k in kept], "rejected": rejected, "answer": text[-3000:]}
            with open(answers_path(provider), "a") as f:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
            n += 1
            print(f"{provider} {unit:11} {start} heads={len(heads):3} kept={len(kept)} rejected={len(rejected)}"
                  f"{' PARSE-ERROR' if raw is None else ''}", flush=True)
            sleep(pause)
    return n


def complete(provider):
    need = {(u, s.isoformat()) for s, _ in windows() for u in model.TH}
    return need <= {(a["unit"], a["start"]) for a in load_answers(provider)}


def review_path(provider):
    return os.path.join(DESK, f"review_{provider}.csv")


def report(providers=("groq", "gemini"), events_path=EVENTS):
    """Scores every provider whose blind test is complete, writes the review sample (once) and docs/EVENTDESK_TEST.md, and the gate file
    when a verdict is possible. -> {provider: result}."""
    events = listed_events(events_path)
    res = {}
    for p in providers:
        ans = load_answers(p)
        if not ans:
            continue
        cands = [k for a in ans for k in a["kept"]]
        s = score(cands, events)
        s.update(provider=p, models=sorted({a["model"] for a in ans}), answered=len(ans), complete=complete(p),
                 parse_errors=sum(a["parse_error"] for a in ans), candidates=len(cands))
        rp = review_path(p)
        if s["complete"] and not os.path.exists(rp):
            sample = random.Random(REVIEW_SEED).sample(s["extras"], min(REVIEW_N, len(s["extras"])))
            with open(rp, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["n", "area", "date", "type", "description", "source", "verdict", "note"])
                for i, c in enumerate(sorted(sample, key=lambda c: (c["date"], c["unit"])), 1):
                    w.writerow([i, c["unit"], c["date"], c["type"], c["description"], c["source"], "", ""])
        s["review"] = _review(rp)
        res[p] = s
    if res:
        _write_doc(res)
        _write_verdict(res)
    return res


def _review(path):
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    done = [r for r in rows if r["verdict"].strip().lower() in ("yes", "no")]
    yes = sum(r["verdict"].strip().lower() == "yes" for r in done)
    return {"rows": len(rows), "reviewed": len(done), "yes": yes, "share": round(yes / len(done), 3) if done else None,
            "finished": len(done) == len(rows)}


def passes(s):
    """None while undecided; else True or False under the pre-registered rule."""
    if not s.get("complete") or s.get("recall") is None:
        return None
    if s["recall"] < RECALL_PASS:
        return False
    r = s.get("review")
    if not r or not r["finished"]:
        return None
    return r["rows"] == 0 or r["share"] >= PRECISION_PASS


def decide(res):
    """The plan's order: Groq (the window is new to it) decides first; Gemini counts only after Groq has failed.
    -> (provider or None, verdicts) once decided, or None while waiting."""
    verdicts = {p: passes(res[p]) for p in ("groq", "gemini") if p in res}
    g = verdicts.get("groq")
    if g is None:
        return None
    if g:
        return "groq", verdicts
    if "gemini" in res and verdicts["gemini"] is None:
        return None
    return ("gemini" if verdicts.get("gemini") else None), verdicts


def _write_verdict(res):
    got = decide(res)
    if got is None:
        return
    chosen, verdicts = got
    os.makedirs(DESK, exist_ok=True)
    with open(VERDICT, "w") as f:
        json.dump({"pass": chosen is not None, "provider": chosen, "model": res[chosen]["models"][-1] if chosen else None,
                   "verdicts": verdicts, "written": dt.date.today().isoformat()}, f, indent=1)


def _write_doc(res):
    L = ["# Event desk: blind test", "",
         f"Written by `warwatch/eventdesk.py report` to the plan fixed before the run ([EVENTDESK_PLAN.md](EVENTDESK_PLAN.md)). Window "
         f"{TEST_START} to {TEST_END}, {WINDOW}-day questions per area, headlines from Google News search only, no listed event shown to "
         f"the model. Pass: recall {RECALL_PASS:.0%} or more, and {PRECISION_PASS:.0%} or more of a sample of {REVIEW_N} extras judged real "
         "qualifying events on review.", "",
         "| Provider | Model | Questions answered | Complete | Parse errors | Listed events | Found | Recall | Extras | In a listed episode | Review | Verdict |",
         "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for p, s in res.items():
        r = s["review"]
        rv = "not started" if not r else f"{r['reviewed']}/{r['rows']} reviewed, {r['yes']} real"
        v = passes(s)
        L.append(f"| {p} | {', '.join(s['models'])} | {s['answered']} | {'yes' if s['complete'] else 'no'} | {s['parse_errors']} | "
                 f"{s['events']} | {s['found']} | {s['recall'] if s['recall'] is not None else 'n/a'} | {len(s['extras'])} | "
                 f"{s['continuation']} | {rv} | {'pending' if v is None else ('PASS' if v else 'FAIL')} |")
    for p, s in res.items():
        if s["missed"]:
            L += ["", f"## Listed events {p} did not find ({len(s['missed'])})", "", "| Date | Areas | Type | Event |", "|---|---|---|---|"]
            L += [f"| {m['date']} | {', '.join(m['areas'])} | {m['type']} | {m['description']} |" for m in s["missed"]]
    L += ["", "Gemini's training covers the test window, so its result can be flattered; gpt-oss-120b (Groq) has a June 2024 cutoff."]
    os.makedirs(os.path.dirname(TEST_DOC), exist_ok=True)
    with open(TEST_DOC, "w") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- live use
def through_date(path=THROUGH):
    with open(path) as f:
        return dt.date.fromisoformat(f.read().strip())


def propose(start=None, end=None, ask=llm.ask, news=fetch_news, sleep=time.sleep, gate=VERDICT, events_path=EVENTS, out_csv=CAND_CSV,
            out_doc=CAND_DOC, today=None):
    """Candidates since the list's complete-through date (or [start, end]) for every area, minus events already listed.
    Refuses to run until the blind test has passed. -> rows written."""
    try:
        with open(gate) as f:
            v = json.load(f)
    except OSError:
        v = {}
    if not v.get("pass"):
        print("event desk: the blind test has not passed (backtest/eventdesk/verdict.json); proposing nothing", flush=True)
        return 0
    provider = v["provider"]
    today = today or dt.datetime.now(dt.timezone.utc).date()
    start = start or through_date() + dt.timedelta(days=1)
    end = end or today - dt.timedelta(days=1)
    events = listed_events(events_path)
    rows, stopped = [], None
    for a, b in windows(start, end):
        if stopped:
            break
        for unit in model.TH:
            heads = news(unit, a, b)
            listed = [(d.isoformat(), t, s) for d, us, t, s in events if unit in us and a - dt.timedelta(days=EPISODE_DAYS) <= d <= b]
            try:
                text, version = ask(prompt(unit, a, b, heads, listed), provider, v.get("model"))
            except llm.DailyLimit as e:
                print(f"stopping: {e}", flush=True)
                stopped = b
                break
            kept, _ = validate(parse_answer(text), heads, a, b)
            for k in kept:
                d = dt.date.fromisoformat(k["date"])
                near = [x for x, us, _, _ in events if unit in us and -MATCH_DAYS <= (d - x).days <= EPISODE_DAYS]
                if any(abs((d - x).days) <= MATCH_DAYS for x in near):
                    continue
                note = "may continue the listed event of " + max(near).isoformat() if near else ""
                rows.append({"date": k["date"], "area": unit, "type": k["type"], "description": k["description"], "source": k["source"],
                             "note": note, "model": version})
            sleep(llm.PROVIDERS[provider]["pause"])
    rows.sort(key=lambda r: (r["date"], r["area"]))
    for i, r in enumerate(rows, 1):
        r["n"] = i
    cols = ["n", "date", "area", "type", "description", "source", "note", "model"]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    L = ["# Event candidates", "",
         f"Proposed by the event desk on {today} for {start} to {end} ({provider}). **Not on the event list.** Each row needs a person's yes "
         "before it is added to `warwatch/data/events.csv` under `docs/EVENTS.md`.", "",
         *([f"**Incomplete:** the provider's daily limit stopped the run in the window ending {stopped}; later days were not read.", ""]
           if stopped else []),
         "| # | Date | Area | Type | Event | Source | Note |", "|---:|---|---|---|---|---|---|"]
    L += [f"| {r['n']} | {r['date']} | {r['area']} | {r['type']} | {r['description']} | {r['source']} | {r['note']} |" for r in rows]
    if not rows:
        L.append("| | | | | No candidates. | | |")
    with open(out_doc, "w") as f:
        f.write("\n".join(L) + "\n")
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("blindtest")
    b.add_argument("--provider", choices=sorted(llm.PROVIDERS), required=True)
    b.add_argument("--budget", type=int, default=50)
    sub.add_parser("report")
    p = sub.add_parser("propose")
    p.add_argument("--start", type=dt.date.fromisoformat)
    p.add_argument("--end", type=dt.date.fromisoformat)
    q = sub.add_parser("prompt")
    q.add_argument("unit", choices=model.TH)
    q.add_argument("start", type=dt.date.fromisoformat)
    a = ap.parse_args(argv)
    if a.cmd == "blindtest":
        if not llm.key_for(a.provider):
            print(f"{llm.PROVIDERS[a.provider]['key']} not set; nothing to do", flush=True)
            return
        if complete(a.provider):
            print(f"{a.provider}: blind test complete", flush=True)
            return
        print(f"answered {blindtest(a.provider, a.budget)}", flush=True)
    elif a.cmd == "report":
        for p_, s in report().items():
            print(p_, {k: s[k] for k in ("answered", "complete", "events", "found", "recall", "continuation")}, "extras", len(s["extras"]),
                  "review", s["review"], "verdict", passes(s))
    elif a.cmd == "propose":
        print(f"candidates: {propose(a.start, a.end)}", flush=True)
    else:
        end = a.start + dt.timedelta(days=WINDOW - 1)
        print(prompt(a.unit, a.start, end, fetch_news(a.unit, a.start, end)))


if __name__ == "__main__":
    main()
