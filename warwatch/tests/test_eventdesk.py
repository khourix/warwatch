"""Event desk and free LLM calls (docs/EVENTDESK_PLAN.md). No network: Google News and the LLM are replaced by fakes."""
import csv
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eventdesk as E  # noqa: E402
import llm  # noqa: E402
import model  # noqa: E402

D = dt.date


def _rss(items):
    body = "".join(f"<item><title>{t} - {s}</title><link>https://news.example/{i}</link><pubDate>{p}</pubDate>"
                   f"<source url=\"https://x\">{s}</source></item>" for i, (t, s, p) in enumerate(items))
    return f"<rss><channel>{body}</channel></rss>"


def _heads(n, day="2025-03-03"):
    return [{"d": day, "src": "Wire", "t": f"headline {i}", "u": f"https://news.example/{i}"} for i in range(1, n + 1)]


class _Desk:
    """Points the desk's files at a temporary folder for one test."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: getattr(E, k) for k in ("DESK", "NEWS", "VERDICT", "TEST_DOC")}
        E.DESK = self.tmp.name
        E.NEWS = os.path.join(self.tmp.name, "news")
        E.VERDICT = os.path.join(self.tmp.name, "verdict.json")
        E.TEST_DOC = os.path.join(self.tmp.name, "EVENTDESK_TEST.md")
        return self.tmp.name

    def __exit__(self, *a):
        for k, v in self.saved.items():
            setattr(E, k, v)
        self.tmp.cleanup()


def _events_csv(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    w = csv.writer(f)
    w.writerow(["date", "theatre", "site_theatre", "type", "surprise_or_buildup", "description", "market_moving", "largest_mover", "move_sd",
                "source"])
    for d, th, site, typ in rows:
        w.writerow([d, th, site, typ, "buildup", f"{typ} in {th}", "False", "", "", "src"])
    f.close()
    return f.name


class EventDeskSearch(unittest.TestCase):
    def test_every_area_has_search_terms_and_queries_stay_short(self):
        self.assertEqual(set(E.PLACES), set(model.TH))
        for unit, places in E.PLACES.items():
            for p in places:
                for acts in E.ACTIONS:
                    q = E.query(p, acts, D(2025, 1, 1), D(2025, 1, 7))
                    self.assertLessEqual(q.count(" OR ") + 1, 14, q)       # Google drops the date limits on longer queries
                    self.assertTrue(q.endswith("after:2025-01-01 before:2025-01-08"))

    def test_parse_rss_keeps_window_and_strips_outlet(self):
        xml = _rss([("Rebels launch attack in Aleppo", "Reuters", "Wed, 27 Nov 2024 10:00:00 GMT"),
                    ("Old story", "BBC", "Mon, 04 Nov 2024 10:00:00 GMT")])
        got = E.parse_rss(xml, D(2024, 11, 25), D(2024, 12, 1))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["t"], "Rebels launch attack in Aleppo")
        self.assertEqual(got[0]["src"], "Reuters")
        self.assertEqual(got[0]["d"], "2024-11-27")

    def test_fetch_news_dedupes_and_survives_a_failed_query(self):
        calls = []

        def rss(q):
            calls.append(q)
            if len(calls) == 2:
                raise OSError("refused")
            return _rss([("Same story", "AP", "Mon, 03 Mar 2025 08:00:00 GMT")])
        got = E.fetch_news("taiwan", D(2025, 3, 3), D(2025, 3, 9), rss=rss, sleep=lambda s: None)
        self.assertEqual(len(calls), len(E.PLACES["taiwan"]) * len(E.ACTIONS))
        self.assertEqual(len(got), 1)

    def test_cap_shares_the_limit_across_days(self):
        heads = _heads(200, "2025-03-03") + _heads(5, "2025-03-09")
        got = E.cap(heads, 20)
        self.assertEqual(len(got), 20)
        self.assertEqual(sum(h["d"] == "2025-03-09" for h in got), 5)          # the quiet day is not crowded out
        self.assertEqual([h["d"] for h in got], sorted(h["d"] for h in got))

    def test_cached_news_is_fetched_once(self):
        with tempfile.TemporaryDirectory() as root:
            n = []

            def rss(q):
                n.append(q)
                return _rss([("Drills near Taiwan", "AP", "Tue, 04 Mar 2025 08:00:00 GMT")])
            a = E.cached_news("taiwan", D(2025, 3, 3), D(2025, 3, 16), root=root, rss=rss, sleep=lambda s: None)
            calls = len(n)
            b = E.cached_news("taiwan", D(2025, 3, 3), D(2025, 3, 16), root=root, rss=rss, sleep=lambda s: None)
            self.assertEqual(a, b)
            self.assertEqual(len(n), calls)                       # the second read comes from the file
            self.assertTrue(os.path.exists(os.path.join(root, "taiwan", "2025-03-03.json.gz")))


class EventDeskAnswers(unittest.TestCase):
    def test_blind_prompt_never_lists_known_events(self):
        txt = E.prompt("iran", D(2025, 6, 9), D(2025, 6, 22), _heads(2))
        self.assertNotIn("Already on the list", txt)
        self.assertIn("[2] 2025-03-03 | Wire | headline 2", txt)
        live = E.prompt("iran", D(2025, 6, 9), D(2025, 6, 22), _heads(2), [("2025-06-13", "onset", "Twelve-Day War")])
        self.assertIn("Already on the list", live)
        self.assertIn("Twelve-Day War", live)

    def test_parse_answer(self):
        self.assertEqual(E.parse_answer('```json\n{"events": []}\n```'), [])
        self.assertEqual(len(E.parse_answer('Sure. {"events": [{"date": "2025-03-04"}]} done')), 1)
        self.assertIsNone(E.parse_answer("I cannot help."))
        self.assertIsNone(E.parse_answer('{"events": "none"}'))

    def test_validate_needs_citation_type_window_and_date_order(self):
        heads = _heads(3, "2025-03-05")
        raw = [{"date": "2025-03-04", "type": "strike", "description": "ok", "evidence": [2, 9]},
               {"date": "2025-03-04", "type": "strike", "evidence": [99]},
               {"date": "2025-03-04", "type": "riot", "evidence": [1]},
               {"date": "2025-02-01", "type": "strike", "evidence": [1]},
               {"date": "2025-03-06", "type": "strike", "evidence": [1]},
               {"date": "soon", "type": "strike", "evidence": [1]}]
        kept, rejected = E.validate(raw, heads, D(2025, 3, 3), D(2025, 3, 16))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["source"], "Wire, 'headline 2' (2025-03-05) https://news.example/2")
        self.assertEqual([r["why"] for r in rejected],
                         ["no valid citation", "type", "outside window", "dated after its headlines", "date"])

    def test_score_recall_extras_and_episodes(self):
        path = _events_csv([("2025-03-10", "yemen", "gulf", "strike"), ("2025-05-01", "iran", "", "strike"),
                            ("2025-08-01", "taiwan", "", "exercise")])
        try:
            ev = E.listed_events(path)
        finally:
            os.unlink(path)
        cands = [{"unit": "gulf", "date": "2025-03-12"},          # finds the Yemen event through its gulf site
                 {"unit": "gulf", "date": "2025-03-30"},          # inside that event's 30-day episode
                 {"unit": "iran", "date": "2025-06-20"},          # extra
                 {"unit": "iran", "date": "2025-07-05"},          # same extra episode, merged
                 {"unit": "korea", "date": "2025-09-01"}]         # extra
        s = E.score(cands, ev, D(2025, 1, 1), D(2025, 12, 31))
        self.assertEqual((s["events"], s["found"]), (3, 1))
        self.assertAlmostEqual(s["recall"], 0.333)
        self.assertEqual(s["continuation"], 1)
        self.assertEqual([(c["unit"], c["date"]) for c in s["extras"]], [("iran", "2025-06-20"), ("korea", "2025-09-01")])


class EventDeskRuns(unittest.TestCase):
    def test_blindtest_resumes_and_stops_at_the_daily_limit(self):
        with _Desk():
            asked = []

            def ask(text, provider):
                asked.append(text)
                if len(asked) == 4:
                    raise llm.DailyLimit("spent")
                return '{"events": [{"date": "2024-07-01", "type": "strike", "description": "x", "evidence": [1]}]}', "test-model-1"
            news = lambda unit, a, b: _heads(2, a.isoformat())  # noqa: E731
            n = E.blindtest("groq", 2, ask=ask, news=news, sleep=lambda s: None, pause=0, units=["iran", "yemen"])
            self.assertEqual(n, 2)
            self.assertNotIn("Already on the list", asked[0])
            n = E.blindtest("groq", 10, ask=ask, news=news, sleep=lambda s: None, pause=0, units=["iran", "yemen"])
            self.assertEqual(n, 1)                                # one more, then the daily limit
            rows = E.load_answers("groq")
            self.assertEqual([(r["unit"], r["start"]) for r in rows], [("iran", "2024-07-01"), ("yemen", "2024-07-01"),
                                                                       ("iran", "2024-07-15")])
            self.assertEqual(rows[0]["kept"][0]["unit"], "iran")
            self.assertFalse(E.complete("groq"))

    def test_verdict_rules(self):
        base = {"complete": True, "recall": 0.95}
        self.assertIsNone(E.passes({"complete": False, "recall": 0.95}))
        self.assertFalse(E.passes({"complete": True, "recall": 0.80}))
        self.assertIsNone(E.passes({**base, "review": {"finished": False}}))
        self.assertTrue(E.passes({**base, "review": {"finished": True, "rows": 40, "share": 0.5}}))
        self.assertFalse(E.passes({**base, "review": {"finished": True, "rows": 40, "share": 0.45}}))

    def test_decide_follows_the_plan_order(self):
        ok = {"complete": True, "recall": 0.95, "review": {"finished": True, "rows": 40, "share": 0.6}}
        bad = {"complete": True, "recall": 0.5}
        waiting = {"complete": False, "recall": None}
        self.assertIsNone(E.decide({}))
        self.assertIsNone(E.decide({"gemini": ok}))                       # Gemini alone never decides
        self.assertEqual(E.decide({"groq": ok, "gemini": waiting})[0], "groq")
        self.assertIsNone(E.decide({"groq": bad, "gemini": waiting}))
        self.assertEqual(E.decide({"groq": bad, "gemini": ok})[0], "gemini")
        self.assertIsNone(E.decide({"groq": bad, "gemini": bad})[0])
        self.assertIsNone(E.decide({"groq": bad})[0])                     # no Gemini run: a plain fail

    def test_report_with_no_answers_writes_nothing(self):
        with _Desk() as d:
            self.assertEqual(E.report(), {})
            self.assertFalse(os.path.exists(E.VERDICT))
            self.assertFalse(os.path.exists(os.path.join(d, "EVENTDESK_TEST.md")))

    def test_report_writes_review_sample_doc_and_verdict(self):
        with _Desk() as d:
            orig = E.complete
            E.complete = lambda p: True
            path = _events_csv([("2024-08-10", "iran", "", "strike")])
            try:
                rows = [{"unit": "iran", "start": "2024-08-05", "end": "2024-08-18", "model": "m1", "headlines": 3, "parse_error": False,
                         "kept": [{"unit": "iran", "date": "2024-08-11", "type": "strike", "description": "a", "source": "s"}],
                         "rejected": [], "answer": ""},
                        {"unit": "korea", "start": "2024-08-05", "end": "2024-08-18", "model": "m1", "headlines": 3,
                         "parse_error": False, "kept": [{"unit": "korea", "date": "2024-08-12", "type": "exercise", "description": "b",
                                                         "source": "s"}], "rejected": [], "answer": ""}]
                with open(E.answers_path("groq"), "w") as f:
                    f.write("\n".join(json.dumps(r) for r in rows) + "\n")
                res = E.report(providers=("groq",), events_path=path)
                self.assertEqual(res["groq"]["recall"], 1.0)
                self.assertFalse(os.path.exists(E.VERDICT))           # review not done yet
                rp = E.review_path("groq")
                with open(rp, newline="") as f:
                    rv = list(csv.DictReader(f))
                self.assertEqual([(r["area"], r["date"]) for r in rv], [("korea", "2024-08-12")])
                rv[0]["verdict"] = "yes"
                with open(rp, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(rv[0]))
                    w.writeheader()
                    w.writerows(rv)
                E.report(providers=("groq",), events_path=path)
                with open(E.VERDICT) as f:
                    v = json.load(f)
                self.assertEqual((v["pass"], v["provider"], v["model"]), (True, "groq", "m1"))
                with open(os.path.join(d, "EVENTDESK_TEST.md")) as f:
                    self.assertIn("PASS", f.read())
            finally:
                E.complete = orig
                os.unlink(path)

    def test_propose_refuses_without_a_passed_test_and_drops_listed_events(self):
        with tempfile.TemporaryDirectory() as d:
            out_csv, out_doc, gate = os.path.join(d, "c.csv"), os.path.join(d, "c.md"), os.path.join(d, "v.json")
            path = _events_csv([("2026-10-20", "iran", "", "strike")])
            try:
                self.assertEqual(E.propose(D(2026, 10, 13), D(2026, 10, 26), gate=gate, events_path=path, out_csv=out_csv,
                                           out_doc=out_doc), 0)
                self.assertFalse(os.path.exists(out_csv))
                with open(gate, "w") as f:
                    json.dump({"pass": True, "provider": "groq", "model": "m1"}, f)
                seen = []

                def ask(text, provider, mdl):
                    seen.append(text)
                    if "Area: the Iran theatre" in text:
                        return ('{"events": [{"date": "2026-10-21", "type": "strike", "description": "listed", "evidence": [1]},'
                                ' {"date": "2026-10-14", "type": "strike", "description": "new", "evidence": [1]}]}', "m1")
                    return '{"events": []}', "m1"
                news = lambda unit, a, b: _heads(1, "2026-10-22")  # noqa: E731
                n = E.propose(D(2026, 10, 13), D(2026, 10, 26), ask=ask, news=news, sleep=lambda s: None, gate=gate, events_path=path,
                              out_csv=out_csv, out_doc=out_doc, today=D(2026, 10, 27))
                self.assertEqual(n, 1)
                self.assertEqual(len(seen), len(model.TH))
                self.assertTrue(any("Already on the list" in t for t in seen))
                with open(out_csv, newline="") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual((rows[0]["date"], rows[0]["area"], rows[0]["description"]), ("2026-10-14", "iran", "new"))
                with open(out_doc) as f:
                    self.assertIn("Not on the event list", f.read())
            finally:
                os.unlink(path)


class FreeLlm(unittest.TestCase):
    def test_gemini_and_groq_answers(self):
        def post(url, body, headers):
            if "googleapis" in url:
                self.assertEqual(headers, {"x-goog-api-key": "k"})
                return {"modelVersion": "gemini-x-001", "candidates": [{"content": {"parts": [{"text": "a", "thought": True},
                                                                                                 {"text": "b"}]}}]}
            self.assertEqual(headers, {"Authorization": "Bearer k"})
            self.assertEqual(body["reasoning_effort"], "low")
            return {"model": "openai/gpt-oss-120b", "choices": [{"message": {"content": "c"}}]}
        self.assertEqual(llm.ask("q", "gemini", key="k", post=post), ("b", "gemini-x-001"))
        self.assertEqual(llm.ask("q", "groq", key="k", post=post), ("c", "openai/gpt-oss-120b"))

    def test_429_retries_then_daily_limit_and_missing_key(self):
        n = []

        def post(url, body, headers):
            n.append(1)
            raise urllib.error.HTTPError(url, 429, "slow down", {}, io.BytesIO())
        with self.assertRaises(llm.DailyLimit):
            llm.ask("q", "groq", key="k", post=post, sleep=lambda s: None)
        self.assertEqual(len(n), 3)
        with self.assertRaises(RuntimeError):
            llm.ask("q", "groq", key="")
