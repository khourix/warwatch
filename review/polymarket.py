"""Methodology review: every geopolitical Polymarket market (resolved and open) with its daily price history.

The first back-fill matched keywords on descriptions and caught sports ("Counter-Strike"); this one walks Polymarket's
own geopolitics/war tags, then keeps questions that name a military action with whole-word matching.
Output: review/data/polymarket_war.jsonl (one market per line, history = [[unix, p_yes], ...] at daily fidelity).
"""
import json, os, re, sys, time, urllib.parse, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
G = "https://gamma-api.polymarket.com"
TAG_RX = re.compile(r"geopolit|war\b|military|middle.?east|ukrain|russia|israel|iran|china|taiwan|korea|venezuela|india|pakistan|yemen|houthi|gaza|"
                    r"lebanon|hezbollah|syria|strike|nato|world|global|conflict|nuclear|missile|defen", re.I)
Q_RX = re.compile(r"\b(strikes?|struck|attacks?|invades?|invasion|war|military|missiles?|ceasefire|troops|blockade|airstrikes?|bomb\w*|"
                  r"clash|offensive|martial law|drones?|nuclear test|declares? war|ground operation|enter|capture|airspace|shoot ?down|"
                  r"hits?|target|retaliat\w*|seize|incursion|annex)\b", re.I)
NOT_RX = re.compile(r"counter-strike|\bcs2?\b|\bnba\b|\bnfl\b|\bufc\b|\bmlb\b|\bnhl\b|esports|dota|\blol\b|map \d|o/u|spread|tennis|"
                    r"strike ?out|election|nominee|bitcoin|\bbtc\b|eth\b|box office|album|movie|song|video", re.I)


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "warwatch-review/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def main():
    os.makedirs(OUT, exist_ok=True)
    tags = []
    off = 0
    while True:
        page = get(f"{G}/tags?limit=500&offset={off}")
        if not page:
            break
        tags += page
        off += 500
        if len(page) < 500 or off > 20000:
            break
    keep = [t for t in tags if TAG_RX.search((t.get("label") or "") + " " + (t.get("slug") or ""))]
    print("tags", len(tags), "kept", len(keep), [t.get("slug") for t in keep][:80], flush=True)
    seen, n = set(), 0
    with open(os.path.join(OUT, "polymarket_war.jsonl"), "w") as f:
        for t in keep:
            for closed in ("true", "false"):
                off = 0
                while off <= 5000:
                    q = urllib.parse.urlencode({"tag_id": t["id"], "closed": closed, "limit": 100, "offset": off})
                    try:
                        evs = get(f"{G}/events?{q}")
                    except Exception as e:
                        print("events fail", t.get("slug"), off, str(e)[:80], flush=True)
                        break
                    if not evs:
                        break
                    for ev in evs:
                        for m in ev.get("markets") or []:
                            qn = m.get("question") or ""
                            if m.get("id") in seen or not Q_RX.search(qn) or NOT_RX.search(qn + " " + (ev.get("title") or "")):
                                continue
                            if float(m.get("volumeNum") or m.get("volume") or 0) < 5000:
                                continue
                            seen.add(m.get("id"))
                            try:
                                tok = json.loads(m.get("clobTokenIds") or "[]")[0]
                                h = get("https://clob.polymarket.com/prices-history?" + urllib.parse.urlencode({"market": tok, "interval": "max", "fidelity": 1440}))
                                hist = [[int(x["t"]), float(x["p"])] for x in h.get("history", [])]
                            except Exception as e:
                                hist = []
                            rec = {k: m.get(k) for k in ("id", "question", "slug", "startDate", "endDate", "closedTime", "outcomes", "outcomePrices",
                                                          "volumeNum", "umaResolutionStatus", "closed")}
                            rec.update(event=ev.get("title"), event_slug=ev.get("slug"), tag=t.get("slug"), history=hist,
                                       description=(m.get("description") or "")[:500])
                            f.write(json.dumps(rec) + "\n")
                            n += 1
                            time.sleep(0.1)
                    off += 100
                    if len(evs) < 100:
                        break
    print("markets", n)


if __name__ == "__main__":
    main()
