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
        self.assertEqual(sum(got.values()), 2)

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

    def test_calm_is_below_warning(self):
        for t, v in run.evaluate(demo.scenario("calm"))["theatres"].items():
            self.assertIn(v["level"], ("Normal", "Watch"), t)

    def test_buildup_alerts_with_both_basis(self):
        v = run.evaluate(demo.scenario("buildup"))["theatres"]["ukraine"]
        self.assertEqual(v["level"], "Alert")
        self.assertEqual(v["basis"], "leading and lagging")

    def test_lone_series_cannot_fire_a_domain(self):
        s = {"id": "a", "domain": "logistics", "theatre": "ukraine", "lag": True, "direction": "up",
             "score": {"z": 9.0}}
        d = scoring.theatre_view([s], "ukraine")["logistics"]
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

    def test_firms_parse(self):
        import osint
        t = "latitude,longitude,bright_ti4,acq_date,confidence,frp\n48.1,37.2,340,2026-10-05,n,12.5\n48.2,37.3,330,2026-10-05,l,3\n"
        out = osint.parse_firms(t)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["frp"], 12.5)

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

if __name__ == "__main__":
    unittest.main()
