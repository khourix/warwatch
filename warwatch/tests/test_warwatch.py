#!/usr/bin/env python3
"""Run: python3 tools/warwatch/tests/test_warwatch.py"""
import datetime as dt
import json
import os
import statistics
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["WARWATCH_HISTORY"] = tempfile.mkdtemp()
import catalog  # noqa: E402
import config as C  # noqa: E402
import dashboard  # noqa: E402
import demo  # noqa: E402
import extras  # noqa: E402
import geo  # noqa: E402
import model  # noqa: E402
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

    def test_year_baseline_leaves_out_the_latest_30_days(self):
        import datetime as dt
        d0 = dt.date(2025, 1, 1)
        def series(vals):
            return [((d0 + dt.timedelta(days=i)).isoformat(), v) for i, v in enumerate(vals)]
        noise = [10 + (i * 7 % 5) for i in range(500)]
        ramp = noise[:440] + [10 + (i * 7 % 5) + 1.5 * (i - 440) / 10 for i in range(440, 500)]   # a slow build-up over the last 60 days
        yr = stats.score_series(series(ramp), "daily")
        short = stats.score_series(series(ramp), "daily", base_days=90)
        self.assertIn("prior year", yr["method"])
        self.assertGreater(yr["z"], short["z"])    # the 90-day yardstick has absorbed the ramp; the year one has not
        thin = stats.score_series(series(noise[:150]), "daily")
        self.assertIn("90 days", thin["method"])   # not enough history for a year baseline: plain 90-day window

    def test_backtest_replays_market_series(self):
        import backtest
        self.assertIn("fetch_market", backtest.LONG)
        self.assertIn("fetch_market", backtest.LAG)

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

    def test_nms_counts_fresh_restrictions(self):
        def f(i, issued, text, code="QXXXX", typ="N"):
            return {"properties": {"coreNOTAMData": {"notam": {"id": i, "issued": issued, "text": text, "selectionCode": code, "type": typ}}}}
        items = [f("1", "2026-10-05T00:00:00Z", "AIRSPACE CLOSED DUE MILITARY ACTIVITY"), f("1", "2026-10-05T00:00:00Z", "AIRSPACE CLOSED"),
                 f("2", "2026-10-06T00:00:00Z", "RWY LGT U/S"), f("3", "2026-10-06T00:00:00Z", "x", code="QRTCA"),
                 f("4", "2026-08-01T00:00:00Z", "PROHIBITED AREA"), f("5", "2026-10-06T00:00:00Z", "PROHIBITED", typ="C")]
        self.assertEqual(S.parse_nms(items, dt.date(2026, 10, 8)), 2.0)

    def test_nms_select_matches_region_or_icao_prefix(self):
        def f(i, fir, loc):
            return {"properties": {"coreNOTAMData": {"notam": {"id": i, "affectedFir": fir, "location": loc}}}}
        items = [f("1", "UKXX", "UKBV"), f("2", "UKLV", "UKLL"), f("3", "KZLC", "UKOV"), f("4", "KZLC", "HLN"), f("5", "KZLC", "HLLL"), f("6", "EPWW", "EPWA")]
        got = lambda firs, prefix=None: sorted(x["properties"]["coreNOTAMData"]["notam"]["id"] for x in S.nms_select(items, firs, prefix))
        self.assertEqual(got(["UKLV"]), ["2"])
        self.assertEqual(got(["UKLV", "UKXX"], "UK"), ["1", "2", "3"])
        self.assertEqual(got(["HLLL"], "HL"), ["5"])    # Helena, Montana (HLN) is a US airport, not Libya

    def test_sar_detector_counts_ships_not_land_or_big_blobs(self):
        try:
            import numpy as np
            import sar
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("numpy and scipy not installed")
        rng = np.random.default_rng(1)
        db = rng.normal(-20, 1.5, (400, 400))
        for y, x in ((50, 60), (200, 300), (350, 100)):
            db[y:y + 3, x:x + 2] += 14          # three ships
        db[120:150, 120:150] += 14              # a 900-pixel patch is not a ship
        land = np.zeros((400, 400), bool)
        land[:, :30] = True
        db[:, :30] = -5
        db[100:102, 32:34] += 14                # bright spot inside the coastal strip
        self.assertEqual(sar.detect(db, land)[0], 3)

    def test_sar_daily_value_needs_enough_sea_in_view(self):
        import sar
        import tempfile
        rows = [["a", "hormuz", "2026-10-01", "400", "5"], ["b", "hormuz", "2026-10-03", "3000", "6"], ["c", "hormuz", "2026-10-03", "1000", "2"]]
        with tempfile.TemporaryDirectory() as d:
            old = store.ROOT
            store.ROOT = d
            try:
                sar.rebuild(rows)
                self.assertEqual(store.cache_load("sar_hormuz"), [("2026-10-03", 20.0)])   # 8 ships in 4000 km2
            finally:
                store.ROOT = old

    def test_sam_counts_by_day(self):
        p = {"opportunitiesData": [{"postedDate": "2026-09-01"}, {"postedDate": "2026-09-20"}, {"postedDate": "2026-08-02"}]}
        self.assertEqual(S.parse_sam(p), {"2026-09-01": 1, "2026-09-20": 1, "2026-08-02": 1})
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

    def test_incomplete_months_are_dropped_before_scoring(self):
        s = [x for x in catalog.SERIES if x["id"] == "us_boots_awards"][0]
        self.assertEqual(s["drop"], catalog.DOD)
        self.assertEqual([x for x in catalog.SERIES if x["id"] == "eu_kit_tenders"][0]["drop"], 1)
        self.assertEqual([x for x in catalog.SERIES if x["id"] == "news_ukraine"][0]["drop"], 0)

    def test_fred_and_gnews(self):
        self.assertEqual(S.parse_gnews_count("<rss><item>a</item><item>b</item></rss>"), 2.0)
        self.assertEqual(S.parse_fred({"observations": [{"date": "2026-01-01", "value": "."},
                                                        {"date": "2026-01-02", "value": "5.5"}]}),
                         [("2026-01-02", 5.5)])

    def test_cboe_vix_csv(self):
        txt = "DATE,OPEN,HIGH,LOW,CLOSE\n10/06/2026,15.1,16.0,14.9,15.5\n10/07/2026,15.21,16.01,14.97,15.08\n\n"
        self.assertEqual(S.parse_cboe_vix(txt), [("2026-10-06", 15.5), ("2026-10-07", 15.08)])


class TestExtras(unittest.TestCase):
    def test_nga_coordinates_and_issue_date(self):
        self.assertEqual(extras.parse_issue("071541Z SEP 2023"), dt.date(2023, 9, 7))
        self.assertIsNone(extras.parse_issue("garbage"))
        lat, lon = extras.parse_coords("MINES NEAR 45-07.10N 030-09.70E AND 12-30S 045-00W")[0]
        self.assertAlmostEqual(lat, 45.1183, 3)
        self.assertAlmostEqual(lon, 30.1617, 3)
        self.assertEqual(extras.parse_coords("12-30S 045-00W"), [(-12.5, -45.0)])

    def test_nga_keeps_only_hazards_with_a_position(self):
        w = [{"navArea": "A", "msgNumber": 1, "msgYear": 2026, "issueDate": "011200Z OCT 2026",
              "text": "BLACK SEA. MISSILE FIRING 44-00N 033-00E."},
             {"text": "BLACK SEA. MISSILE FIRING, NO POSITION."},
             {"text": "LIGHT UNLIT 44-00N 033-00E."}]
        got = extras.parse_nga(w)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["issued"], "2026-10-01")

    def test_navigation_degradation(self):
        p = {"ac": [{"lat": 1, "lon": 1, "nac_p": 9}, {"lat": 1, "lon": 1, "nac_p": 3}, {"lat": 1, "lon": 1},
                    {"nac_p": 0}]}
        self.assertEqual(extras.parse_nav(p), (3, 1))

    def test_polymarket_skips_closed_and_thin_markets(self):
        p = {"events": [{"title": "e", "markets": [
            {"question": "US strike on Iran", "outcomePrices": '["0.145","0.855"]', "volume": "72000000", "closed": False},
            {"question": "closed", "outcomePrices": '["1","0"]', "volume": "9000000", "closed": True},
            {"question": "thin", "outcomePrices": '["0.5","0.5"]', "volume": "100", "closed": False}]}]}
        self.assertEqual([m["q"] for m in extras.parse_poly(p)], ["US strike on Iran"])

    def test_czib_active_zones_only(self):
        p = {"x": [{"status": "Active", "name": "Airspace of Syria", "coordinates": "33.5, 36.3",
                    "updated": "<time>2026-10-01T16:25:34+03:00</time>"},
                   {"status": "Withdrawn", "name": "old", "coordinates": "1, 1", "updated": ""}]}
        z = extras.parse_czib(p)
        self.assertEqual([(a["name"], a["updated"]) for a in z], [("Airspace of Syria", "2026-10-01")])

    def test_advisory_levels_by_country(self):
        got = extras.country_levels([{"Title": "Iran - Level 4: Do Not Travel"},
                                     {"Title": "Israel, The West Bank and Gaza - Level 3: Reconsider"}, {"Title": "x"}])
        self.assertEqual(got, {"Iran": 4, "Israel": 3})


class TestGeoAndPage(unittest.TestCase):
    def test_projection_is_monotonic_and_clips(self):
        pr = geo.Proj((0, 10, 40, 50), 100, 100)
        self.assertLess(pr.xy(2, 45)[0], pr.xy(8, 45)[0])
        self.assertLess(pr.xy(5, 48)[1], pr.xy(5, 42)[1])
        self.assertFalse(pr.inside(30, 45))

    def test_page_renders_without_map_or_live_layers(self):
        res = run.evaluate(demo.scenario("buildup"))
        page = dashboard.render(res, "now", demo=True)
        self.assertIn('id="data"', page)
        self.assertNotIn("__DATA__", page)
        blob = page.split('type="application/json">')[1].split("</script>")[0]
        d = json.loads(blob.replace("\\u003c", "<"))
        self.assertEqual(set(d["theatres"]), set(C.THEATRES))
        self.assertEqual(len(d["series"]), len(catalog.SERIES))
        self.assertIsNone(d["map"])

    def test_series_detail_has_history_and_sd_bands(self):
        res = run.evaluate(demo.scenario("buildup"))
        d = dashboard.build_data(res, "now", True, None, None)
        daily = next(s for s in d["series"] if s["kind"] == "daily" and s["st"] == "ok")
        self.assertIn("base", daily)
        self.assertTrue(daily["zh"])
        self.assertIsNotNone(daily["z"])

    def test_region_map_has_countries(self):
        topo = geo.load()
        if topo is None:
            self.skipTest("basemap not downloaded")
        rm = geo.region_map(topo)
        names = {c["name"] for c in rm["countries"]}
        self.assertTrue({"Ukraine", "Iran", "Yemen", "Israel"} <= names)

    def test_history_z_scores_each_day(self):
        pts = demo.daily(3, 1.0)
        h = stats.history_z(pts, "daily", 10)
        self.assertEqual(len(h), 10)
        self.assertEqual(h[-1][0], pts[-1][0])


class TestSources(unittest.TestCase):
    def test_gdelt_events_filtered_by_country_and_root(self):
        row = [""] * 58
        row[28], row[51] = "15", "IR"
        other = list(row); other[51] = "US"
        got = S.parse_gdelt_events([row, other, row], ["IR"])
        self.assertEqual(got, {("IR", "all"): 2, ("IR", "15"): 2})   # every event counts toward 'all' (the share's denominator), watched roots also count alone

    def test_gdelt_series_merges_history_and_cache_and_builds_shares(self):
        import store
        import tempfile
        old = store.ROOT
        store.ROOT = tempfile.mkdtemp()
        try:
            hist = S.gdelt_history()
            self.assertTrue(hist, "committed GDELT history missing")
            last = max(d for v in hist.values() for d in v)
            day = (dt.date.fromisoformat(last) + dt.timedelta(days=1)).isoformat()
            store.cache_rows_save("gdelt_events", [[day, "IR", "13", "10"], [day, "IR", "all", "100"]])
            pts = dict(S.gdelt_series("iran", ("13",)))
            self.assertEqual(pts[day], 10.0)
            self.assertIn(last, pts)
            self.assertAlmostEqual(dict(S.gdelt_series("iran", ("13",), share=True))[day], 100.0)   # 10 of 100 events = 100 per 1,000
        finally:
            store.ROOT = old

    def test_ioda_parse_daily_means(self):
        p = {"data": [[{"from": 1759708800, "step": 3600, "values": [10, 20]}]]}
        got = S.parse_ioda(p)
        self.assertEqual(list(got.values())[0], 15.0)

    def test_adsb_classes(self):
        p = {"ac": [{"t": "K35R", "lat": 30, "lon": 50}, {"t": "F16", "lat": 30, "lon": 50}, {"t": "C17", "lat": 30, "lon": 50},
                    {"t": "E3TF", "lat": 30, "lon": 50}, {"t": "F16", "lat": 80, "lon": 0}]}
        c = S.adsb_classes(p, (24, 40, 44, 64))
        self.assertEqual((c["mil"], c["tanker"], c["fighter"], c["lift"], c["isr"]), (4, 1, 1, 2, 1))

    def test_pizza_parse(self):
        self.assertEqual(extras.parse_pizza({"overall_index": 31, "active_spikes": 1, "data": [{"current_popularity": 5}, {}]}),
                         (31.0, 1, 1))


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

    def test_calm_is_mostly_normal(self):
        lv = [v["level"] for v in run.evaluate(demo.scenario("calm"))["theatres"].values()]
        self.assertGreaterEqual(lv.count("Normal"), 10)      # thresholds are 90/95/99th calm percentiles: a stray Watch is by design

    def test_buildup_is_critical_with_both_basis(self):
        v = run.evaluate(demo.scenario("buildup"))["theatres"]["ukraine"]
        self.assertEqual(v["level"], "Critical")
        self.assertEqual(v["basis"], "leading and lagging")

    def test_down_direction_flags_falls(self):
        self.assertEqual(scoring.directed(-4.0, "down"), 4.0)
        self.assertEqual(scoring.directed(-4.0, "up"), -4.0)
        self.assertEqual(scoring.directed(-4.0, "both"), 4.0)

    def test_fails_closed(self):
        res = run.evaluate([{"id": "x", "domain": "logistics", "theatre": "ukraine", "lag": True, "direction": "up",
                             "kind": "daily", "points": [], "score": None, "status": "error", "error": "boom"}])
        self.assertEqual(res["theatres"]["ukraine"]["level"], "insufficient data")

    def test_missing_key_is_reported_not_hidden(self):
        os.environ.pop("CENSUS_API_KEY", None)
        got = run.collect({"us_pickups_to_ukraine"})
        self.assertEqual(got[0]["status"], "awaiting_key")



class TestOsint(unittest.TestCase):
    def test_aircraft_owner_and_class(self):
        import osint
        a = osint.aircraft({"hex": "ae1234", "flight": "REACH402 ", "t": "C17", "lat": 36.0, "lon": 36.0, "alt_baro": 31000, "gs": 440, "track": 120, "squawk": "1200"})
        self.assertEqual(a["ct"], "United States")
        self.assertIn("Air Mobility", a["o"])
        self.assertEqual(a["cls"], "lift")
        self.assertIn("C-17", a["d"])
        self.assertEqual(a["th"], osint.theatre_at(36.0, 36.0))
        self.assertFalse(a["em"])

    def test_squawk_parse(self):
        import osint
        out = osint.parse_squawks({"ac": [{"hex": "43c123", "flight": "RRR1", "t": "E3TF", "lat": 50, "lon": 10, "alt_baro": 20000},
                                          {"hex": "x", "lat": 1, "lon": 1, "alt_baro": "ground"}]}, "7700")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["mean"], "General emergency")
        self.assertEqual(out[0]["ct"], "United Kingdom")

    def test_heading_toward(self):
        import osint
        self.assertIn("AB, Germany", osint.heading_toward(52.0, 7.6, 180))
        self.assertEqual(osint.heading_toward(52.0, 7.6, None), "")

    def test_usni_regions_and_ships(self):
        import osint
        xml = ("<item><content:encoded><![CDATA[<p>The fleet as of Oct. 5, 2026.</p><p>In the Arabian Sea, USS George Washington (CVN-73) is operating in support "
               "of U.S. operations. USS Spruance (DDG-111) is also here.</p><p>In the Eastern Mediterranean, USS Carney (DDG-64) is conducting patrols.</p>]]></content:encoded></item>")
        out = osint.parse_usni(xml, "http://u", "Mon, 05 Oct")
        names = [s["n"] for s in out]
        self.assertIn("USS George Washington (CVN-73)", names)
        self.assertEqual([s for s in out if "George" in s["n"]][0]["k"], "carrier")
        self.assertEqual([s for s in out if "Carney" in s["n"]][0]["loc"], "Eastern Mediterranean")

    def test_incident_news(self):
        import osint, datetime as dt
        xml = ("<rss><item><title>Crude oil tanker struck by unknown projectile off Oman, UKMTO says - Reuters</title><link>http://x</link>"
               "<pubDate>Fri, 02 Oct 2026 23:31:28 GMT</pubDate><source url=\"http://r\">Reuters</source></item>"
               "<item><title>Stocks rally</title><link>http://y</link><pubDate>Fri, 02 Oct 2026 23:31:28 GMT</pubDate></item></rss>")
        out = osint.parse_incident_news(xml, today=dt.date(2026, 10, 5))
        self.assertEqual(len(out), 0)   # no place keyword in the Oman headline
        xml2 = xml.replace("off Oman", "in the Gulf of Oman")
        out = osint.parse_incident_news(xml2, today=dt.date(2026, 10, 5))
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["uk"])
        self.assertEqual(out[0]["loc"], "Gulf of Oman")

    def test_ukmto_official(self):
        import osint, datetime as dt
        rows = [{"incidentNumber": 78, "utcDateOfIncident": "2026-10-01T11:22:00Z", "incidentTypeName": "Suspicious Activity", "locationLatitude": 12.6,
                 "locationLongitude": 48.2, "place": "Gulf of Aden", "vesselName": "..", "vesselType": "Tanker ", "otherDetails": "UKMTO WARNING 078-26\r\nUKMTO has received a report of an incident 85NM south of Balhaf.",
                 "crewHeld": 0, "vesselUnderPirateControl": False},
                {"incidentNumber": 1, "utcDateOfIncident": "2024-01-01T00:00:00Z", "locationLatitude": 1, "locationLongitude": 1}]
        out = osint.parse_ukmto(rows, today=dt.date(2026, 10, 5))
        self.assertEqual(len(out), 1)
        self.assertIn("Suspicious Activity", out[0]["t"])
        self.assertTrue(out[0]["tx"].startswith("UKMTO has received"))

    def test_market_history(self):
        h = extras.parse_poly_history({"history": [{"t": 1762387203 + i * 21600, "p": 0.1 + i / 1000} for i in range(300)]})
        self.assertEqual(len(h), 90)
        self.assertEqual(h[0][1], 0.1)
        k = extras.parse_kalshi_history({"candlesticks": [{"end_period_ts": 1759032000, "price": {"close_dollars": "0.0800"}}]})
        self.assertEqual(k[0][1], 0.08)

    def test_firms_parse(self):
        import osint
        t = "latitude,longitude,bright_ti4,acq_date,confidence,frp\n48.1,37.2,340,2026-10-05,n,12.5\n48.2,37.3,330,2026-10-05,l,3\n"
        out = osint.parse_firms(t)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["frp"], 12.5)
        self.assertEqual(out[0]["ts"], "")   # no acq_time column: no pass time
        t = "latitude,longitude,acq_date,acq_time,confidence,frp\n48.1,37.2,2026-10-05,912,n,12.5\n"
        self.assertEqual(osint.parse_firms(t)[0]["ts"], "2026-10-05T09:12Z")

    def test_firms_routine_sources_burn_on_several_days(self):
        import osint
        flare = [{"lat": 30.0 + 0.001 * i, "lon": 48.0, "date": f"2026-10-0{i + 1}", "frp": 9} for i in range(3)]
        new = [{"lat": 31.5, "lon": 47.0, "date": "2026-10-07", "frp": 40}, {"lat": 31.5, "lon": 47.0, "date": "2026-10-07", "frp": 30}]
        out = osint.mark_routine(flare + new)
        self.assertEqual([p["routine"] for p in out], [True, True, True, False, False])

    def test_digitraffic_military(self):
        import osint
        loc = {"features": [{"mmsi": 230111000, "geometry": {"coordinates": [25.0, 59.9]}, "properties": {"sog": 10}},
                            {"mmsi": 230222000, "geometry": {"coordinates": [25.1, 59.9]}, "properties": {"sog": 0}}]}
        ves = [{"mmsi": 230111000, "name": "PATROL", "shipType": 35, "destination": ""}, {"mmsi": 230222000, "name": "CARGO", "shipType": 70}]
        ships, total = osint.parse_digitraffic(loc, ves, (50, 70, 10, 40))
        self.assertEqual(total, 2)
        self.assertEqual([s["n"] for s in ships], ["PATROL"])

    def test_ais_messages(self):
        import osint
        m = [{"MetaData": {"MMSI": 1, "ShipName": "X ", "latitude": 1.0, "longitude": 2.0}, "Message": {"PositionReport": {"Sog": 7}}},
             {"MetaData": {"MMSI": 1}, "Message": {"ShipStaticData": {"Type": 35, "Destination": "ABC ", "Name": "NAVYSHIP"}}}]
        s = osint.parse_ais_messages(m)["1"]
        self.assertEqual((s["type"], s["spd"], s["dest"], s["n"]), (35, 7, "ABC", "NAVYSHIP"))

    def test_ws_frame_roundtrip(self):
        import osint
        f = osint.ws_read(bytes([0x81, 0x03]) + b"abc")
        self.assertEqual(f[:2], (1, b"abc"))
        self.assertEqual(f[2], b"")

    def test_war_filter(self):
        self.assertTrue(extras.is_war("Will the US strike Iran by December?"))
        self.assertFalse(extras.is_war("Will the Lakers win the NBA title?"))
        self.assertFalse(extras.is_war("Bitcoin above 100k attack on resistance?"))

class TestGfw(unittest.TestCase):
    def test_parse_presence_sums_hours_per_day(self):
        pl = {"entries": [{"public-global-presence:v4.0": [
            {"date": "2026-09-30", "flag": "IRN", "hours": 1, "lat": 26.7, "lon": 55.7},
            {"date": "2026-09-30", "flag": "PAN", "hours": 13, "lat": 25, "lon": 56.6},
            {"date": "2026-09-29", "flag": "MHL", "hours": 1.5, "lat": 23.1, "lon": 59.7}]}]}
        self.assertEqual(S.parse_gfw_presence(pl), [("2026-09-29", 1.5), ("2026-09-30", 14.0)])


class TestRegions(unittest.TestCase):
    def test_every_theatre_in_one_region(self):
        kids = [k for _, _, ks in C.REGIONS for k in ks]
        self.assertEqual(sorted(kids), sorted(t for t in C.THEATRES if t != "global"))

    def test_region_level_is_highest_child(self):
        import dashboard
        import engine
        th = {t: {"level": "Normal", "score": 10.0, "zc": 0.0, "theatre": t} for t in C.THEATRES}
        th["yemen"].update(level="Elevated", score=80.0)
        reg, gti = engine.rollup(th, C.REGIONS)
        r = {x["id"]: x for x in dashboard.regions_json(reg)}
        self.assertEqual(r["mideast"]["level"], "Elevated")
        self.assertEqual(gti["level"], "Elevated")
        self.assertEqual(r["korea_r"]["level"], "Normal")

    def test_theatre_configs_complete(self):
        for t in C.BOXES:
            self.assertIn(t, C.THEATRES)
            self.assertIn(t, C.GNEWS)
            self.assertIn(t, C.GDELT_CC)
            self.assertIn(t, C.CITIES)

    def test_gdelt_backfills_new_country(self):
        import store
        import tempfile
        old = store.ROOT
        store.ROOT = tempfile.mkdtemp()
        try:
            day = dt.date(2030, 1, 10)   # after the committed history, which is not re-fetched
            store.cache_rows_save("gdelt_events", [[day.isoformat(), "UP", "15", "3"]])
            calls = []
            orig = S.gdelt_day
            S.gdelt_day = lambda d, ccs: calls.append(d) or {}
            S._GDELT_DONE.clear()
            S.gdelt_update(days=3, max_days=3, today=day + dt.timedelta(days=2))
            self.assertIn(day, calls)   # day was cached for UP only, so it is re-read for the other countries
        finally:
            S.gdelt_day = orig
            store.ROOT = old


def _toy_model(active=True):
    theta = {"a0": -2.0, "delta": {}, "hist": [0.5, 0.0, 0.0], "w": {"brent": 2.0, "gdelt_threat": 1.0}}
    return {"version": "t", "fitted": "2026-01-01", "gamma": 1.0, "phi": 0.5, "bands": [0.05, 0.10, 0.25], "base": {t: 0.05 for t in model.TH},
            "pooled_base": 0.05, "p_any_clim": 0.4, "mm_share": {t: 0.3 for t in model.TH}, "theta": theta, "boot": [theta], "gates": {"pass": active},
            "active": active, "p_cap": 0.6}


class TestModel(unittest.TestCase):
    def test_shrink_pulls_toward_base_and_floors(self):
        self.assertAlmostEqual(model.shrink(0.5, 0.05, 1.0, 0.0), 0.5)
        self.assertAlmostEqual(model.shrink(0.5, 0.05, 0.0, 0.0), 0.05)    # gamma 0: the base rate
        self.assertAlmostEqual(model.shrink(0.001, 0.05, 1.0, 0.5), 0.025)  # floor at half the base rate

    def test_history_counts_only_earlier_events(self):
        ev = [("iran", dt.date(2026, 1, 1)), ("iran", dt.date(2026, 10, 1)), ("ukraine", dt.date(2026, 5, 1))]
        h = model.history(ev, "iran", dt.date(2026, 10, 1))   # the event on the day itself is not yet history
        self.assertEqual(h[:2], [1 / 3, 1 / 5])
        self.assertGreater(model.history(ev, "iran", dt.date(2026, 10, 2))[0], h[0])

    def test_evidence_is_one_sided_and_takes_the_strongest(self):
        def row(i, th, z, d="up"):
            return {"id": i, "theatre": th, "direction": d, "score": {"z": z}}
        ev = model.evidence([row("gdelt_threat_iran", "iran", 3.0), row("gdelt_threat_ukraine", "ukraine", 5.0), row("brent", "global", -4.0),
                             row("gold", "global", -4.0, "down")], "iran")
        self.assertEqual(ev, {"gdelt_threat": 3.0, "brent": 0.0, "gold": 4.0})

    def test_probability_rises_with_evidence_and_is_capped(self):
        m = _toy_model()
        quiet = model.predict(m, [], "iran", [], dt.date(2026, 10, 1))
        hot = model.predict(m, [{"id": "brent", "theatre": "global", "direction": "up", "score": {"z": 5.0}}], "iran", [], dt.date(2026, 10, 1))
        self.assertLess(quiet["p"], hot["p"])
        self.assertLessEqual(hot["p"], m["p_cap"])
        self.assertEqual(hot["contrib"][0][0], "brent")
        self.assertLessEqual(hot["lo"], hot["p"])
        self.assertGreaterEqual(hot["hi"], hot["p"])

    def test_active_model_sets_levels_inactive_only_shadows(self):
        for active in (True, False):
            res = run.evaluate(demo.scenario("calm"))
            before = {t: v["level"] for t, v in res["theatres"].items()}
            res = model.apply(res, events=[], today=dt.date(2026, 10, 1), m=_toy_model(active))
            self.assertEqual(res["model"]["active"], active)
            for t in model.TH:
                self.assertIn("p", res["theatres"][t])
                if not active:
                    self.assertEqual(res["theatres"][t]["level"], before[t])
                else:
                    self.assertEqual(res["theatres"][t]["level"], res["model"]["theatres"][t]["level"])
                    self.assertEqual(res["theatres"][t]["level_composite"], before[t])
            self.assertIn("p_any", res["global"])

    def test_backfill_extends_the_history_file_by_missing_days(self):
        import backfill
        import gzip
        import shutil
        p = os.path.join(tempfile.mkdtemp(), "g.csv.gz")
        shutil.copy(S.GDELT_HISTORY, p)
        last = max(d for v in S.gdelt_history().values() for d in v)
        orig = S.gdelt_day
        S.gdelt_day = lambda d, ccs: {("IR", "all"): 10, ("IR", "13"): 2}
        try:
            n = backfill.gdelt(2, today=dt.date.fromisoformat(last) + dt.timedelta(days=5), path=p)
        finally:
            S.gdelt_day = orig
        self.assertEqual(n, 2)
        with gzip.open(p, "rt") as f:
            self.assertEqual(f.read().splitlines()[-1].split(",")[0], (dt.date.fromisoformat(last) + dt.timedelta(days=2)).isoformat())

    def test_global_probability_is_chance_of_any(self):
        m = _toy_model()
        per = {t: {"p": 0.1} for t in model.TH}
        g = model.global_view(m, per)
        self.assertAlmostEqual(g["p_any"], 1 - 0.9 ** len(model.TH))
        self.assertAlmostEqual(g["p_market_moving"], 1 - 0.97 ** len(model.TH))

    def test_market_probability_filters_converts_and_blends(self):
        end = (dt.date.today() + dt.timedelta(days=90)).isoformat()
        mk = [{"theatre": "iran", "p": 0.2, "vol": 100000, "end": end}, {"theatre": "iran", "p": 0.9, "vol": 1000, "end": end},
              {"theatre": "ukraine", "p": 0.5, "vol": 100000, "end": end}]
        p = model.market_probability(mk, "iran")           # the thin market and the other theatre are ignored
        self.assertIsNotNone(p)
        self.assertLess(p, 0.2)                              # 90-day 20% is about 7% over 30 days, then recalibrated
        self.assertIsNone(model.market_probability(mk, "taiwan"))
        self.assertAlmostEqual(model.blend(0.1, None), 0.1)
        self.assertGreater(model.blend(0.1, 0.5), 0.1)

    def test_forward_record_is_hash_chained_once_a_day(self):
        res = model.apply(run.evaluate(demo.scenario("calm")), events=[], today=dt.date(2026, 10, 1), m=_toy_model())
        path = os.path.join(tempfile.mkdtemp(), "log.csv")
        n = model.forward_append(res, "2026-10-01", path)
        self.assertEqual(n, len(model.TH) + 1)
        self.assertEqual(model.forward_append(res, "2026-10-01", path), 0)    # one batch per day
        self.assertGreater(model.forward_append(res, "2026-10-02", path), 0)
        ok, bad, rows = model.forward_verify(path)
        self.assertTrue(ok)
        self.assertEqual(len(rows), 2 * (len(model.TH) + 1))
        import csv
        with open(path, newline="") as f:
            lines = list(csv.DictReader(f))
        lines[3]["p"] = "0.99999"
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, model.FIELDS)
            w.writeheader()
            w.writerows(lines)
        ok, bad, _ = model.forward_verify(path)
        self.assertFalse(ok)
        self.assertEqual(bad, 4)

    def test_committed_model_and_events_are_consistent(self):
        m = model.load()
        self.assertIsNotNone(m)
        self.assertTrue(all(w >= 0 for w in m["theta"]["w"].values()))
        self.assertTrue(all(all(w >= 0 for w in b["w"].values()) for b in m["boot"]))
        self.assertEqual(m["active"], m["gates"]["pass"])
        self.assertEqual(sorted(m["base"]), sorted(model.TH))
        ev = model.load_events()
        self.assertGreaterEqual(len(ev), 78)
        self.assertTrue(all(t in model.TH for t, _ in ev))
        import csv
        with open(os.path.join(model.DATA, "events.csv"), newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(all(r["type"] in ("onset", "strike", "maritime", "exercise", "other") and r["source"] for r in rows))
        self.assertEqual([r["date"] for r in rows], sorted(r["date"] for r in rows))

    def test_chance_change_against_the_forward_record(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("date,theatre,p\n2026-09-28,iran,0.05\n2026-10-01,iran,0.06\n2026-10-08,iran,0.09\n2026-10-08,korea,0.03\n")
        got = dashboard.p_change({"iran": 0.093, "korea": 0.03, "global": None}, path=f.name)
        os.unlink(f.name)
        self.assertEqual(got["iran"], [0.033, 7])   # the newest day at least 7 days back
        self.assertNotIn("korea", got)              # one day of record: nothing to compare with

    def test_page_data_carries_probabilities(self):
        res = model.apply(run.evaluate(demo.scenario("calm")), events=[], today=dt.date(2026, 10, 1), m=_toy_model())
        d = dashboard.build_data(res, "now", True, None, None)
        self.assertTrue(d["model"]["active"])
        self.assertIsNotNone(d["theatres"]["iran"]["p"])
        self.assertIn("p_any", res["global"])


try:
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import scipy  # noqa: F401
    import validate
except ImportError:
    validate = None


@unittest.skipIf(validate is None, "validate.py needs numpy, pandas and scipy")
class TestValidate(unittest.TestCase):
    def test_labels_follow_the_codebook_windows(self):
        import numpy as np
        import pandas as pd
        days = pd.date_range("2024-01-01", "2024-04-30", freq="D")
        P = pd.DataFrame({"date": list(days) * len(validate.TH), "theatre": np.repeat(validate.TH, len(days))})
        ev = pd.DataFrame({"date": [pd.Timestamp("2024-03-01")], "theatre": ["iran"]})
        y, excl, unk, _ = validate.labels(P, ev, pd.Timestamp("2024-04-30"))
        m = (P["theatre"] == "iran").values
        d = P["date"]
        self.assertEqual(y[m & (d == "2024-01-31").values].sum(), 1)    # 30 days ahead
        self.assertEqual(y[m & (d == "2024-01-30").values].sum(), 0)    # 31 days ahead
        self.assertEqual(y[m & (d == "2024-03-01").values].sum(), 0)    # the day itself is not a warning
        self.assertTrue(excl[m & (d == "2024-03-15").values].all())     # the aftermath is left out
        self.assertFalse(excl[m & (d == "2024-04-01").values].any())
        self.assertEqual(y[~m].sum(), 0)
        self.assertTrue(unk[(d > "2024-03-31").values].all())          # labels need 30 days of events file beyond them

    def test_auc_and_shrink(self):
        import numpy as np
        self.assertAlmostEqual(validate.auc(np.array([0, 0, 1, 1]), np.array([.1, .2, .3, .4])), 1.0)
        self.assertAlmostEqual(validate.auc(np.array([0, 1, 0, 1]), np.array([.1, .1, .1, .1])), 0.5)
        self.assertAlmostEqual(float(validate.shrink(np.array([0.5]), np.array([0.05]), 0.0, 0.0)[0]), 0.05)


if __name__ == "__main__":
    unittest.main()


class TestEngine(unittest.TestCase):
    def test_modified_z_matches_formula_and_winsorizes(self):
        import stats
        base = [10, 11, 9, 10, 12, 8, 10, 11, 9, 10]
        z, raw = stats.modified_z(13, base)
        self.assertAlmostEqual(raw, 0.6745 * 3 / 1.0)
        z, raw = stats.modified_z(1000, base)
        self.assertEqual(z, 5.0)
        self.assertGreater(raw, 5.0)

    def test_locf_fills_short_gaps_only(self):
        import stats
        pts = [("2026-01-01", 1.0), ("2026-01-04", 4.0), ("2026-01-09", 9.0)]
        vals, obs, filled = stats.calendar_fill(pts, 9)
        self.assertEqual(vals[1], 1.0)       # Jan 2: carried
        self.assertEqual(vals[2], 1.0)       # Jan 3: carried
        self.assertEqual(obs, 3)
        self.assertEqual(vals[5], 4.0)       # Jan 6: second day after Jan 4... carried
        self.assertIsNone(vals[7])           # Jan 8: third missing day, left missing

    def test_owa_weights_hit_orness(self):
        import engine
        for n in (2, 4, 6):
            w = engine.owa_weights(n)
            self.assertAlmostEqual(sum(w), 1.0)
            self.assertAlmostEqual(sum(x * (n - 1 - i) / (n - 1) for i, x in enumerate(w)), engine.ORNESS, places=4)

    def test_calm_readings_never_cancel_an_alarm(self):
        import engine
        def row(i, z, domain="logistics"):
            return {"id": i, "theatre": "ukraine", "domain": domain, "direction": "up", "lag": False, "kind": "daily", "points": [],
                    "score": {"z": z}}
        its = engine.theatre_items([row("a", -4.0), row("b", 3.0)], "ukraine")
        self.assertEqual({i["id"]: i["z"] for i in its}, {"a": 0.0, "b": 3.0})

    def test_zero_weight_series_are_ignored_by_the_composite(self):
        import engine
        row = {"id": "ooni_iran", "theatre": "iran", "domain": "information", "direction": "up", "lag": False, "kind": "daily",
               "points": [], "score": {"z": 5.0}, "scored": False}
        self.assertEqual(engine.theatre_items([row], "iran"), [])
        zero = [s["id"] for s in catalog.SERIES if not s["scored"]]
        self.assertTrue(zero and all(i.startswith(catalog.ZERO_WEIGHT) for i in zero))
        self.assertTrue(any(i.startswith("ooni_") for i in zero))

    def test_levels_do_not_depend_on_the_day_s_other_readings(self):
        import engine
        self.assertEqual(engine.evaluate_all([], [], {})[1], (0.0, 1.0))
        self.assertFalse(hasattr(engine, "estimate_calib"))

    def test_mpi_penalises_lopsided_profile(self):
        import engine
        even = engine.mpi([1, 1, 1, 1, 1], [.2] * 5)[2]
        lop = engine.mpi([0, 0, 0, 0, 5], [.2] * 5)[2]
        self.assertGreater(lop, even)

    def test_correlated_series_count_once(self):
        import engine
        ch = {str(i): float(i % 5) for i in range(30)}
        a = {"id": "a", "kind": "daily", "z": 3.0, "sign": 1, "ch": ch}
        b = {"id": "b", "kind": "daily", "z": 3.0, "sign": 1, "ch": {k: v * 2 for k, v in ch.items()}}
        c = {"id": "c", "kind": "daily", "z": 0.0, "sign": 1, "ch": {k: float((int(k) * 7) % 11) for k in ch}}
        g, pairs = engine.groups_of([a, b, c])
        self.assertEqual(sorted(len(x) for x in g), [1, 2])

    def test_deterministic_and_weights_sum_to_one(self):
        import engine
        import demo
        a = run.evaluate(demo.scenario("buildup"))["theatres"]["ukraine"]["zc"]
        b = run.evaluate(demo.scenario("buildup"))["theatres"]["ukraine"]["zc"]
        self.assertEqual(a, b)
        for t, w in engine.load_weights()["weights"].items():
            self.assertAlmostEqual(sum(w.values()), 1.0, msg=t)
