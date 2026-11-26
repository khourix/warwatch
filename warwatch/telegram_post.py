"""Posts WarWatch's key changes to a Telegram channel, after the page is deployed.

Added November 2026. Reads the deployed brief (data/v1/brief.json), picks the feed items marked "key" (contract.tier: a tripwire,
a build-up level change, a base that differed on two radar passes, raised advice) from the last two days that were not posted
before, and sends each as one plain message with a link to its page. At most DAILY_CAP a day, oldest first, so a busy day never
floods the channel. What was sent is kept in a small state file the workflow carries between runs (actions/cache).

The first run with no state file posts nothing: it marks everything already there as sent, so switching the poster on does not
replay the last month. Without TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID it does nothing and exits 0.

    python3 warwatch/telegram_post.py --brief https://khourix.github.io/warwatch/data/v1/brief.json --state tg_state.json
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

SITE = "https://khourix.github.io/warwatch/"
DAILY_CAP = 6          # messages a day, at most
RECENT_DAYS = 2        # only items from today and yesterday
KEEP = 600             # sent keys kept in the state file


def item_key(f):
    return f"{f['date'][:10]}|{f['kind']}|{f.get('theatre', '')}|{f['title']}"


def link(f):
    to = f.get("to") or {}
    v, i, tab = to.get("view"), to.get("id"), to.get("tab")
    if v == "theatre" and i:
        return f"{SITE}{i}/" + (f"{tab}/" if tab and tab != "now" else "")
    if v in ("base", "signal") and i:
        return f"{SITE}{v}/{i}/"
    return SITE


def message(f, names):
    name = names.get(f.get("theatre"), "")
    head = f"{name} · {f['title']}" if name else f["title"]
    lines = [head]
    if f.get("detail"):
        lines.append(f["detail"])
    lines.append(link(f))
    return "\n".join(lines)


def pick(brief, state, today):
    """The messages to send now, and the state after sending them. Pure, so it is tested without the network."""
    sent = list(state.get("sent") or [])
    seen = set(sent)
    feed = brief.get("feed") or []
    if not state:                                   # first run: mark what is there, send nothing
        return [], {"sent": [item_key(f) for f in feed][-KEEP:], "day": today, "count": 0}
    count = state.get("count", 0) if state.get("day") == today else 0
    since = (dt.date.fromisoformat(today) - dt.timedelta(days=RECENT_DAYS - 1)).isoformat()
    names = {t["id"]: t["name"].split(" (")[0] for t in brief.get("theatres") or []}
    fresh = [f for f in feed if f.get("tier") == "key" and f["date"][:10] >= since and item_key(f) not in seen]
    fresh.sort(key=lambda f: f["date"])
    out = []
    for f in fresh:
        if count >= DAILY_CAP:
            break
        out.append((item_key(f), message(f, names)))
        count += 1
    return out, {"sent": sent, "day": today, "count": count}


def send(token, chat, text):
    body = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("ok", False)


def load(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=30) as r:
            return json.load(r)
    with open(src, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument("--brief", default=SITE + "data/v1/brief.json")
    a.add_argument("--state", default="tg_state.json")
    args = a.parse_args(argv)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("telegram: no bot token or chat id set, nothing posted")
        return 0
    try:
        state = load(args.state) if os.path.exists(args.state) else {}
    except (OSError, ValueError):
        state = {}
    brief = load(args.brief)
    msgs, new = pick(brief, state, dt.datetime.now(dt.timezone.utc).date().isoformat())
    sent = new["sent"]
    posted = 0
    for k, text in msgs:
        try:
            if send(token, chat, text):
                sent.append(k)
                posted += 1
        except OSError as e:
            print(f"::warning title=telegram::send failed: {type(e).__name__}")
            break
    new["count"] = new["count"] - (len(msgs) - posted)
    new["sent"] = sent[-KEEP:]
    with open(args.state, "w", encoding="utf-8") as f:
        json.dump(new, f)
    print(f"telegram: posted {posted} of {len(msgs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
