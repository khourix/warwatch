"""Back-fill of the Google News headline counts (news_<theatre>) for theatres whose live series only keeps the last 150 days.

One RSS query per day with the same search text the live series uses (config.GNEWS), so a back-filled day and a live day measure the same
thing. Days already held are skipped; a day that fails is left empty (never zero). The live series reads these as the history before its own cache
starts (store.seed), and validate.py can test them against the event list from 2018.
"""
import datetime as dt
import time

import common as K
import config as C
import sources as S


def cmd_news(theatres, start, end, pause=1.5):
    for th in theatres:
        sid = f"news_{th}"
        have = K.load(sid)
        todo = [d for d in K.days(start, end) if d.isoformat() not in have]
        K.log("news", th, "days to read", len(todo))
        fails = got = 0
        for d in todo:
            try:
                have[d.isoformat()] = S.gnews_day(C.GNEWS[th], d)
                got += 1
                fails = 0
            except Exception as e:
                fails += 1
                K.log("fail", th, d, str(e)[:100])
                if fails >= 8:      # rate-limited: stop and keep what was read; a re-run resumes
                    K.log("::warning::news", th, "stopped after repeated failures at", d)
                    break
                time.sleep(30)
                continue
            if got % 25 == 0:
                K.save(sid, have)
            time.sleep(pause)
        K.save(sid, have)
        K.log("news", th, "read", got, "rows now", len(have))
