"""A free LLM forecaster, forward only (prediction study, recommendation 4). Standard library only.

    python3 warwatch/llmcast.py            # one forecast per theatre for today -> forward/log_llm.csv (needs GEMINI_API_KEY)
    python3 warwatch/llmcast.py --dry-run  # print the prompts, call nothing

Once a day, Google's Gemini API (free tier) is asked the page's own question for each theatre: will a qualifying event (docs/EVENTS.md)
happen within 30 days? It may search the web (Google Search grounding) for current news. It is never shown the model's probability, so
its forecast stays independent of the model and the two can be pooled later. Each answer goes to its own hash-chained record, in the same
format as the other shadow records, and is scored by forward_score.py under the same forward gates. It never touches the page.

An LLM forecast cannot be backtested honestly (the model knows, or can find, what happened), so only this forward record counts.
GitHub Models, the first choice, was retired on 30 July 2026; Gemini's free tier was the fallback.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
import model  # noqa: E402

FORWARD_LLM = os.path.join(model.ROOT, "forward", "log_llm.csv")
NOTES = os.path.join(model.ROOT, "forward", "llm_notes")      # the model's short reasoning and sources, one file a month, for review
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
# Tried in order; the first that answers is used for every theatre that day, and its exact version is written to the record.
MODELS = [m for m in os.environ.get("GEMINI_MODEL", "").split(",") if m] or ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest"]
P_MIN, P_MAX = 0.005, 0.95
PAUSE = 7.0           # seconds between calls: the free tier allows about 10 a minute
NOTE_CHARS = 600

CODEBOOK = """A qualifying event is one of:
- onset: a war onset, or a major new ground offensive by a state;
- strike: a wave of state strikes on another state's territory, or a missile or drone exchange between states;
- maritime: an attack on commercial or naval shipping, or a blockade;
- exercise: a named, large-scale military exercise or drill around a contested border or strait, run by the state that disputes it;
- other: a coup with fighting, or organised armed force used across or within a border in a way that changes the theatre's risk.
Not events: diplomacy, sanctions, leadership changes without fighting, territory changes without new fighting, and the continuation of
an operation already under way. A new event must be a distinct new escalation, not more of what is already happening."""


def _question(t, today):
    th = C.THEATRES[t]
    end = today + dt.timedelta(days=29)
    if t in C.SUBTHEATRES:
        where = (f"{th['name']} (a country that may be drawn into a neighbouring war): will {th['name']} be struck, or used to strike, "
                 f"in a qualifying event")
    else:
        where = f"the {th['name']} theatre ({', '.join(th['countries'])}): will a qualifying event happen there"
    return where + f" between {today.isoformat()} and {end.isoformat()} inclusive?"


def prompt(t, today, base, recent):
    """The question for one theatre. base: the theatre's historical share of 30-day windows with an event (2018 on); recent: [(date, text)]."""
    ctx = C.CONTEXT.get(t, ("", ""))[0]
    past = "\n".join(f"- {d.isoformat()}: {s}" for d, s in recent) or "- none on record since 2018"
    return f"""You are a careful geopolitical forecaster. Today is {today.isoformat()}.

Question. For {_question(t, today)}

{CODEBOOK}

Reference points:
- Since 2018, {base:.0%} of 30-day windows in this theatre contained a qualifying event (the base rate).
- {('Current situation: ' + ctx + '.') if ctx else 'No war is marked as under way in this theatre.'}
- The most recent qualifying events on record here:
{past}

Search for news from the last two weeks about this theatre before answering. Weigh concrete signs (troop movements, evacuations,
official warnings, recent strikes) against the base rate; most 30-day windows contain no event. Write at most 120 words of reasoning,
then end with one line exactly in the form
PROBABILITY: <a number between 0 and 1>"""


def parse(text):
    """The last 'PROBABILITY: x' in the answer, as a probability (a percentage is read as one), clipped to [P_MIN, P_MAX]. None if absent."""
    hits = re.findall(r"PROBABILITY\s*[:=]\s*\**\s*([0-9]*\.?[0-9]+)\s*(%?)", text or "", flags=re.I)
    if not hits:
        return None
    v, pct = hits[-1]
    p = float(v) / (100 if pct or float(v) > 1 else 1)
    return None if not 0 <= p <= 1 else min(P_MAX, max(P_MIN, p))


def _post(url, body, key, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ask(text, key, mdl, search=True, post=_post):
    """-> (answer text, model version, grounded, first source URLs) for one prompt. Raises urllib.error.HTTPError on a refusal of the call."""
    body = {"contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}}
    if search:
        body["tools"] = [{"google_search": {}}]
    r = post(API.format(m=mdl), body, key)
    c = (r.get("candidates") or [{}])[0]
    out = "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []) if not p.get("thought"))
    grounded = bool((c.get("groundingMetadata") or {}).get("groundingChunks"))
    return out, r.get("modelVersion") or mdl, grounded, [g.get("web", {}).get("uri", "") for g in (c.get("groundingMetadata") or {}).get("groundingChunks", [])][:5]


def recent_events(t, today, n=3, path=None):
    import csv
    out = []
    try:
        with open(path or os.path.join(model.DATA, "events.csv"), newline="") as f:
            for r in csv.DictReader(f):
                d = dt.date.fromisoformat(r["date"])
                if d < today and (r["theatre"] == t or t in C.sites(r.get("site_theatre"))):
                    out.append((d, f"{r['type']}: {r['description']}"))
    except OSError:
        pass
    return sorted(out)[-n:]


def forecast(today=None, key=None, post=_post, pause=PAUSE, log_path=None, notes=NOTES, sleep=time.sleep):
    """Asks once per theatre and appends today's rows. -> rows appended (0 when nothing answered, None when today is already logged)."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    log_path = log_path or FORWARD_LLM
    ok, _, old = model.forward_verify(log_path)
    if not ok:
        raise SystemExit(f"{log_path}: hash chain broken; not appending")
    if old and old[-1]["date"] >= today.isoformat():
        return None
    m = model.load()
    per, info, chosen = {}, [], None
    for t in model.TH:
        text = prompt(t, today, m["base"].get(t, m["pooled_base"]), recent_events(t, today))
        for mdl in ([chosen] if chosen else MODELS):
            got = None
            for attempt in range(3):
                try:
                    got = ask(text, key, mdl, post=post)
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429 and attempt < 2:
                        sleep(30 * (attempt + 1))        # per-minute limit: wait and retry; a daily limit fails the third try
                        continue
                    print(f"{t}: {mdl} answered {e.code}", flush=True)
                    break
                except (urllib.error.URLError, TimeoutError, ValueError) as e:
                    print(f"{t}: {mdl} failed: {str(e)[:120]}", flush=True)
                    break
            if got:
                chosen = mdl
                break
        sleep(pause)
        if not got:
            continue
        out, version, grounded, sources = got
        p = parse(out)
        print(f"{t:12} p={p} {version}{' +search' if grounded else ''}", flush=True)
        if p is None:
            continue
        per[t] = {"p": p, "version": version + ("+search" if grounded else "")}
        info.append({"date": today.isoformat(), "theatre": t, "p": p, "model": per[t]["version"], "why": out.strip()[-NOTE_CHARS:], "sources": sources})
    return _append(per, m, today, log_path, info, notes)


def _append(per, m, today, path, info, notes):
    if not per:
        return 0
    rows = []
    for t, v in per.items():
        p, base = v["p"], m["base"].get(t, m["pooled_base"])
        rows.append({"date": today.isoformat(), "theatre": t, "p": f"{p:.5f}", "lo": f"{p:.5f}", "hi": f"{p:.5f}", "raw": f"{p:.5f}",
                     "base": f"{base:.5f}", "level": model.level_of(p, m["bands"]), "composite_level": "", "p_market": "", "active": 0,
                     "model": "llm-" + v["version"]})
    tops = [t for t in model.TH if t not in C.SUBTHEATRES]
    if all(t in per for t in tops):       # the any-theatre row only when every theatre answered, else it would read low
        g = model.global_view(m, per)
        rows.append({"date": today.isoformat(), "theatre": "_any", "p": f"{g['p_any']:.5f}", "lo": "", "hi": "", "raw": "", "base": f"{g['clim']:.5f}",
                     "level": g["level"], "composite_level": "", "p_market": "", "active": 0, "model": rows[0]["model"]})
    import csv
    ok, _, old = model.forward_verify(path)
    prev = old[-1]["hash"] if old else "0" * 64
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, model.FIELDS)
        if not old:
            w.writeheader()
        for r in rows:
            r["prev_hash"] = prev
            r["hash"] = prev = model._digest(prev, r)
            w.writerow(r)
    if notes:
        os.makedirs(notes, exist_ok=True)
        with open(os.path.join(notes, today.strftime("%Y-%m") + ".jsonl"), "a") as f:
            for x in info:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    today = dt.datetime.now(dt.timezone.utc).date()
    if a.dry_run:
        m = model.load()
        for t in model.TH:
            print(f"--- {t}\n" + prompt(t, today, m["base"].get(t, m["pooled_base"]), recent_events(t, today)))
        return 0
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY is not set: no LLM forecast today (add it as a repository secret)")
        return 0
    n = forecast(key=key)
    if n is None:
        print("LLM shadow record: today is already logged")
        return 0
    print("LLM shadow record: appended", n, "rows")
    return 0 if n else 1            # no theatre answered: fail, so the run shows red


if __name__ == "__main__":
    sys.exit(main())
