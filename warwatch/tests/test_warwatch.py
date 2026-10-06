#!/usr/bin/env python3
"""Run: python3 tools/warwatch/tests/test_warwatch.py"""
import datetime as dt
import os
import statistics
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["WARWATCH_HISTORY"] = tempfile.mkdtemp()
import catalog  # noqa: E402
import config as C  # noqa: E402
import demo  # noqa: E402
import run  # noqa: E402
import scoring  # noqa: E402
import sources as S  # noqa: E402
import stats  # noqa: E402
import store  # noqa: E402

# shaped like the responses read from a GitHub runner on 2026-10-06
COMEXT = {"id": ["freq", "reporter", "partner", "product", "flow", "indicators", "time"],
          "size": [1, 3, 1, 1, 1, 1, 2],
          "dimension": {
              "freq": {"category": {"index": {"M": 0}}},
              "reporter": {"category": {"index": {"DE": 0, "FR": 1, "EU27_2020": 2}}},
              "partner": {"category": {"index": {"UA": 0}}},
              "product": {"category": {"index": {"8704": 0}}},
              "flow": {"category": {"index": {"2": 0}}},
              "indicators": {"category": {"index": {"VALUE_IN_EUROS": 0}}},
              "time": {"category": {"index": {"2026-05": 0, "2026-06": 1}}}},
          "value": {"0": 10, "1": 20, "2": 5, "4": 1000, "5": 2000}}


class TestStats(unittest.TestCase):
    def test_robust_z(self):
        base = [100, 102, 98, 101, 99, 100, 103, 97]
        self.assertGreater(stats.robust_z(160, base), 5)
        self.assertLess(abs(stats.robust_z(101, base)), 1)
        self.assertIsNone(stats.robust_z(5, [1, 2, 3]))

    def test_flat_history_change_is_maximal_not_divide_by_zero(self):
        self.assertEqual(stats.robust_z(3, [3] * 8), 0.0)
        self.assertEqual(stats.robust_z(4, [3] * 8), 6.0)
        self.assertEqual(stats.robust_z(2, [3] * 8), -6.0)

    def test_seasonal_bulge_is_not_an_anomaly(self):
        pts = demo.monthly(1, 0.0, end=(2026, 9))      # newest month is the September bulge
        self.assertLess(abs(stats.score_series(pts, "monthly")["z"]), 3)

    def test_spike_is_detected(self):
        self.assertGreater(stats.score_series(demo.monthly(1, 1.5), "monthly")["z"], 4)
        self.assertGreater(stats.score_series(demo.daily(1, 1.0), "daily")["z"], 4)

    def test_short_series_unscored(self):
        self.assertIsNone(stats.score_series([("a", 1)] * 10, "monthly"))
        self.assertIsNone(stats.score_series([("a", 1)] * 30, "daily"))

    def test_false_alarm_rate_on_pure_noise_is_low(self):
        for kind in ("monthly", "daily"):
            zs = [stats.score_series(demo.monthly(s, 0) if kind == "monthly" else demo.daily(s, 0), kind)["z"]
                  for s in range(300)]
            self.assertLess(sum(z >= 2.5 for z in zs) / 300, 0.05, kind)
            self.assertLess(statistics.pstdev(zs), 1.5, kind)


class TestParsers(unittest.TestCase):
    def test_usaspending_fiscal_to_calendar(self):
        p = {"results": [{"time_period": {"fiscal_year": "2026", "month": m}, "aggregated_amount": a}
                         for m, a in (("1", 5), ("4", 7), ("12", 9))]}
        self.assertEqual(S.parse_usaspending(p), [("2025-10", 5.0), ("2026-01", 7.0), ("2026-09", 9.0)])

    def test_comext_sums_members_and_skips_aggregates(self):
        self.assertEqual(S.parse_comext(COMEXT), [("2026-05", 15.0), ("2026-06", 20.0)])

    def test_jsonstat_decode_coords(self):
        cells = {(c["reporter"], c["time"]): v for c, v in S.decode_jsonstat(COMEXT)}
        self.assertEqual(cells[("FR", "2026-05")], 5)
        self.assertEqual(cells[("EU27_2020", "2026-06")], 2000)
        self.assertEqual(cells[("DE", "2026-06")], 20)

    def test_ted_query_and_count(self):
        q = S.ted_query("18830000", "2026-02")
        self.assertIn("publication-date>=20260201", q)
        self.assertIn("publication-date<=20260228", q)
        self.assertEqual(S.parse_ted_count({"totalNoticeCount": 687, "notices": [1]}), 687)

    def test_portwatch(self):
        p = {"features": [{"attributes": {"date": "2026-09-27", "n_total": 37}},
                          {"attributes": {"date": "2026-09-26", "n_total": 30}}]}
        self.assertEqual(S.parse_portwatch(p), [("2026-09-26", 30.0), ("2026-09-27", 37.0)])

    def test_census_filters_named_partners(self):
        rows = [["CTY_CODE", "CTY_NAME", "ALL_VAL_MO", "time"], ["1", "UKRAINE", "5", "2026-06"],
                ["2", "FRANCE", "9", "2026-06"], ["3", "UKRAINE", "7", "2026-07"]]
        self.assertEqual(S.parse_census(rows, ["UKRAINE"]), [("2026-06", 5.0), ("2026-07", 7.0)])

    def test_sam_counts_by_month(self):
        p = {"opportunitiesData": [{"postedDate": "2026-09-01"}, {"postedDate": "2026-09-20"}, {"postedDate": "2026-08-02"}]}
        self.assertEqual(S.parse_sam(p), {"2026-09": 2, "2026-08": 1})
        self.assertEqual(S.parse_sam({}), {})

    def test_fcdo_daily_counts_history_by_day(self):
        p = {"details": {"change_history": [{"public_timestamp": "2026-10-02T08:30:25Z"},
                                            {"public_timestamp": "2026-10-02T09:00:00Z"}]}}
        d = dict(S.fcdo_daily(p, days=5, today=dt.date(2026, 10, 5)))
        self.assertEqual(d["2026-10-02"], 2.0)
        self.assertEqual(d["2026-10-03"], 0.0)

    def test_state_levels(self):
        items = [{"Title": "Israel - Level 3: Reconsider Travel", "Category": ["IS"]},
                 {"Title": "Iran - Level 4: Do Not Travel", "Category": ["IR"]},
                 {"Title": "France - Level 2: x", "Category": ["FR"]}]
        self.assertEqual(S.state_levels(items, ["IS", "IR"]), 7.0)

    def test_adsb_box_and_airlift(self):
        p = {"ac": [{"lat": 50, "lon": 30, "t": "C17"}, {"lat": 50, "lon": 31, "t": "H60"},
                    {"lat": 10, "lon": 0, "t": "C17"}, {"t": "C17"}]}
        self.assertEqual(S.adsb_counts(p, C.BOXES["ukraine"]), (2.0, 1.0))

    def test_gdelt_without_timeline_is_an_error_not_silence(self):
        with self.assertRaises(ValueError):
            S.parse_gdelt({})

    def test_incomplete_months_are_dropped_before_scoring(self):
        s = [x for x in catalog.SERIES if x["id"] == "us_boots_awards"][0]
        self.assertEqual(s["drop"], catalog.DOD)
        self.assertEqual([x for x in catalog.SERIES if x["id"] == "eu_kit_tenders"][0]["drop"], 1)
        self.assertEqual([x for x in catalog.SERIES if x["id"] == "wiki_conscription"][0]["drop"], 0)

    def test_gdelt_wiki_fred(self):
        self.assertEqual(S.parse_gdelt({"timeline": [{"data": [{"date": "20260930T000000Z", "value": 12}]}]}),
                         [("2026-09-30", 12.0)])
        self.assertEqual(S.parse_wiki({"items": [{"timestamp": "2026090100", "views": 40}]}), [("2026-09-01", 40.0)])
        self.assertEqual(S.parse_fred({"observations": [{"date": "2026-01-01", "value": "."},
                                                        {"date": "2026-01-02", "value": "5.5"}]}),
                         [("2026-01-02", 5.5)])


class TestStore(unittest.TestCase):
    def test_append_and_daily_mean(self):
        store.append("t1", 2, "2026-10-01T00:00")
        store.append("t1", 4, "2026-10-01T12:00")
        store.append("t1", 9, "2026-10-02T00:00")
        self.assertEqual(store.daily("t1"), [("2026-10-01", 3.0), ("2026-10-02", 9.0)])


class TestScoring(unittest.TestCase):
    def test_catalogue_is_wellformed(self):
        ids = [s["id"] for s in catalog.SERIES]
        self.assertEqual(len(ids), len(set(ids)))
        for s in catalog.SERIES:
            self.assertIn(s["domain"], C.DOMAINS)
            self.assertIn(s["theatre"], C.THEATRES)
            self.assertIn(s["kind"], ("monthly", "daily"))

    def test_calm_is_below_warning(self):
        for t, v in run.evaluate(demo.scenario("calm"))["theatres"].items():
            self.assertIn(v["level"], ("Normal", "Watch"), t)

    def test_buildup_alerts_with_both_basis(self):
        v = run.evaluate(demo.scenario("buildup"))["theatres"]["ukraine"]
        self.assertEqual(v["level"], "Alert")
        self.assertEqual(v["basis"], "leading and lagging")

    def test_lone_series_cannot_fire_a_domain(self):
        s = {"id": "a", "domain": "kit", "theatre": "global", "lag": True, "direction": "up",
             "score": {"z": 9.0}}
        d = scoring.theatre_view([s], "ukraine")["kit"]
        self.assertLess(d["z"], C.THRESH_SIGNAL * 3)       # 9 * 0.7 = 6.3 is the cap for one series
        self.assertAlmostEqual(d["z"], 6.3)

    def test_down_direction_flags_falls(self):
        self.assertEqual(scoring.directed(-4.0, "down"), 4.0)
        self.assertEqual(scoring.directed(-4.0, "up"), -4.0)
        self.assertEqual(scoring.directed(-4.0, "both"), 4.0)

    def test_lagging_only_is_labelled(self):
        d = {"a": {"z": 3.0, "fast": False}, "b": {"z": 3.0, "fast": False}, "c": {"z": 0.1, "fast": True}}
        self.assertEqual(scoring.level(d)["basis"], "lagging only")

    def test_fails_closed(self):
        self.assertEqual(scoring.level({"a": {"z": 9.0, "fast": True}, "b": {"z": None, "fast": False}})["level"],
                         "insufficient data")
        res = run.evaluate([{"id": "x", "domain": "kit", "theatre": "global", "lag": True, "direction": "up",
                             "kind": "daily", "points": [], "score": None, "status": "error", "error": "boom"}])
        self.assertEqual(res["theatres"]["ukraine"]["level"], "insufficient data")

    def test_missing_key_is_reported_not_hidden(self):
        os.environ.pop("CENSUS_API_KEY", None)
        got = run.collect({"us_pickups_to_ukraine"})
        self.assertEqual(got[0]["status"], "awaiting_key")


if __name__ == "__main__":
    unittest.main()
