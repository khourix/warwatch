"""Open sources from the Argos Atlas review (openfeeds.py, sanctions.py) and the evidence grade. Run with test_warwatch.py.
Fixtures copy the shape of real responses read on 26 November 2026."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import catalog  # noqa: E402
import config as C  # noqa: E402
import openfeeds as O  # noqa: E402
import sanctions as SN  # noqa: E402
import store  # noqa: E402


class _TmpHistory:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = store.ROOT
        store.ROOT = self.tmp.name
        O._CACHE.clear()

    def tearDown(self):
        store.ROOT = self.old
        O._CACHE.clear()
        self.tmp.cleanup()


class TestHormuz(_TmpHistory, unittest.TestCase):
    DAILY = {"days": [{"date": "2026-11-23", "in": 4, "out": 3, "total": 7, "tankers": 2, "source": "ais", "avg7": 7.4},
                      {"date": "2026-11-24", "in": 5, "out": 4, "total": 9, "tankers": 3, "source": "ais", "avg7": 7.6},
                      {"date": "2026-11-25", "in": 1, "out": 0, "total": 1, "tankers": 0, "source": "ais", "partial": True}],
             "definition": "...", "generatedAt": "2026-11-25T09:00:00Z", "license": "CC BY 4.0"}

    def test_partial_day_is_left_out(self):
        self.assertEqual(O.parse_hormuz_daily(self.DAILY), [("2026-11-23", 7.0), ("2026-11-24", 9.0)])

    def test_crossings_keep_days_the_source_has_dropped(self):
        store.cache_save("hormuz_cross_days", [("2026-10-19", 60.0)], stamp=False)
        saved = O.S.get
        O.S.get = lambda url, **kw: self.DAILY
        try:
            got = O.hormuz_crossings()
        finally:
            O.S.get = saved
        self.assertEqual(got[0], ("2026-10-19", 60.0))
        self.assertEqual(got[-1], ("2026-11-24", 9.0))

    def test_areas(self):
        got = O.parse_hormuz_areas({"aisSilent": [{"mmsi": 1}, {"mmsi": 2}], "waiting": {"total": 610}, "fleet": {"nearStrait": 900}})
        self.assertEqual(got, {"silent": 2.0, "waiting": 610.0})
        with self.assertRaises(RuntimeError):
            O.parse_hormuz_areas({"waiting": {}})


class TestGeoConfirmed(_TmpHistory, unittest.TestCase):
    FILE = [{"factionId": "a", "name": "Russia", "color": "#f00", "icons": [{"placemarks": [
        {"id": "e1", "date": "2026-11-20T00:00:00", "la": 48.5, "lo": 37.9, "ds": "strike"},
        {"id": "e2", "date": None, "la": 48.5, "lo": 37.9, "ds": "no date"},
        {"id": "e3", "date": "2026-10-01T00:00:00", "la": 50.1, "lo": 24.0, "ds": "Lviv"}]}]}]

    def test_events_without_a_date_are_skipped(self):
        got = O.parse_geoconf(self.FILE)
        self.assertEqual([e[0] for e in got], ["e1", "e3"])
        self.assertEqual(got[0][1], dt.date(2026, 11, 20))

    def test_thirty_day_count_in_the_box(self):
        ev = O.parse_geoconf(self.FILE)
        got = dict(O.geoconf_series("ukraine", today=dt.date(2026, 11, 25), events=ev))
        self.assertEqual(got["2026-11-19"], 0.0)      # e3 (1 Oct) has left the 30 days, e1 (20 Nov) not yet in
        self.assertEqual(got["2026-11-25"], 1.0)      # e1 only
        self.assertEqual(got["2026-10-30"], 1.0)
        self.assertEqual(got["2026-10-31"], 0.0)
        # western Ukraine sits in the eastern-flank box too, but it is Ukraine's
        self.assertEqual(max(v for _, v in O.geoconf_series("europe_east", today=dt.date(2026, 11, 25), events=ev)), 0.0)

    def test_rolling_counts_events_before_the_first_day(self):
        got = O.rolling([dt.date(2026, 1, 1), dt.date(2026, 1, 20)], dt.date(2026, 1, 25), dt.date(2026, 2, 2))
        self.assertEqual(got[0], ("2026-01-25", 2.0))
        self.assertEqual(dict(got)["2026-01-30"], 2.0)    # 1 Jan is the window's first day
        self.assertEqual(dict(got)["2026-01-31"], 1.0)


class TestDeepState(_TmpHistory, unittest.TestCase):
    AREAS = [{"hash": "#bcaaa4", "area": 1718.2, "percent": "0.285", "type": "unspecified"},
             {"hash": "#a52714", "area": 73213.8, "percent": "12.128", "type": "occupied_after_24_02_2022"},
             {"hash": "#ff5252", "area": 139991.5, "percent": "23.189", "type": "other_territories"},
             {"hash": "#880e4f", "area": 43969.6, "percent": "7.283", "type": "occupied_to_24_02_2022"},
             {"hash": "#0f9d58", "area": 41289.5, "percent": "6.839", "type": "liberated"}]

    def test_occupied_area_sums_both_kinds(self):
        self.assertAlmostEqual(O.parse_deepstate_areas(self.AREAS), 117183.4, places=1)

    def test_update_reads_only_new_versions_and_gain_is_weekly(self):
        listing = [{"id": 1795000000, "createdAt": "2026-11-10T08:00:00.000Z"}, {"id": 1795557210, "createdAt": "2026-11-24T21:53:30.000Z"}]
        area = {1795000000: 100.0, 1795557210: 130.0}
        calls = []

        def get(url, **kw):
            calls.append(url)
            if url.endswith("/public"):
                return listing
            return [{"type": "occupied_after_24_02_2022", "area": area[int(url.split("/")[-2])]}]
        rows = O.deepstate_update(get=get, sleep=lambda s: None)
        self.assertEqual(len(rows), 2)
        O.deepstate_update(get=get, sleep=lambda s: None)
        self.assertEqual(sum(1 for u in calls if u.endswith("/areas")), 2)    # nothing re-read on the second run
        self.assertEqual(O.deepstate_gain(rows), [("2026-11-24", 30.0)])


class TestWarSpotting(_TmpHistory, unittest.TestCase):
    def test_pages_until_short_and_weekly_sum(self):
        calls = []

        def get(url, **kw):
            calls.append(url)
            self.assertIn("User-Agent", kw["headers"])
            day, page = url.split("/")[-2:]
            n = 100 if (day == "2026-11-20" and page == "1") else 5 if day == "2026-11-20" else 2
            return {"losses": [{"id": i, "date": day} for i in range(n)]}
        have = O.warspot_update(today=dt.date(2026, 11, 25), recent=10, older=3, get=get, sleep=lambda s: None)
        self.assertEqual(have["2026-11-20"], 105.0)
        self.assertEqual(len(calls), 14)          # 13 days, one of them with a second page
        self.assertIn("2026-11-13", have)         # older days filled after the recent window
        got = dict(O.warspot_series(today=dt.date(2026, 11, 25), have=have))
        self.assertEqual(got["2026-11-25"], 6 * 2 + 105.0)
        self.assertNotIn("2026-11-12", got)       # its week is not all kept yet


class TestAdvisories(_TmpHistory, unittest.TestCase):
    def test_canada_levels_and_missing_country(self):
        lv = O.parse_canada({"metadata": {}, "data": {"UA": {"advisory-state": 3}, "BY": {"advisory-state": 3}, "MD": {"advisory-state": 1}}})
        self.assertEqual(lv, {"UA": 4, "BY": 4, "MD": 2})
        self.assertEqual(O.level_sum(lv, O.ISO2["ukraine"]), 10.0)
        with self.assertRaises(RuntimeError):
            O.level_sum(lv, O.ISO2["iran"])

    def test_smartraveller_table(self):
        page = ('<table><tr><td class="views-field-title"><a href="/destinations/europe/ukraine">Ukraine</a></td>'
                '<td class="views-field views-field-field-overall-advice-level"><span>Do not travel</span></td>'
                '<td><time datetime="2026-11-20T00:00:00Z">20 Nov</time></td></tr>'
                '<tr><td><a href="/destinations/europe/moldova">Moldova</a></td>'
                '<td class="views-field-field-overall-advice-level">Exercise a high degree of caution</td></tr></table>')
        self.assertEqual(O.parse_smartraveller(page), {"ukraine": 4, "moldova": 2})

    def test_every_theatre_country_has_an_australian_slug(self):
        for codes in O.ISO2.values():
            for c in codes:
                self.assertIn(c, O.AU_SLUG)

    def test_smartraveller_file_from_home_runner(self):
        full = {slug: 2 for slug in O.AU_SLUG.values()}
        t = dt.datetime(2026, 11, 27, 6, 0, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "smartraveller.json")
            self.assertIsNone(O.smartraveller_saved(path, now=t))
            self.assertEqual(O.smartraveller_save(path, now=t, fetch=lambda: full), len(full))
            self.assertEqual(O.smartraveller_saved(path, now=t + dt.timedelta(hours=30)), full)
            self.assertIsNone(O.smartraveller_saved(path, now=t + dt.timedelta(hours=40)))   # stale: the build tries the site

    def test_smartraveller_fetch_refuses_a_partial_table(self):
        old = O.S.get
        O.S.get = lambda *a, **k: ('<tr><td><a href="/destinations/europe/ukraine">Ukraine</a></td>'
                                   '<td class="views-field-field-overall-advice-level">Do not travel</td></tr>')
        try:
            with self.assertRaises(RuntimeError):
                O.smartraveller_fetch()
        finally:
            O.S.get = old


class TestHazards(_TmpHistory, unittest.TestCase):
    def test_gdacs_and_eonet_rows(self):
        g = O.parse_gdacs({"features": [
            {"geometry": {"type": "Point", "coordinates": [44.1, 40.2]},
             "properties": {"eventtype": "WF", "name": "Forest fire in Armenia", "fromdate": "2026-11-20T00:00:00", "todate": "2026-11-22T00:00:00"}},
            {"geometry": {"type": "Point", "coordinates": [10, 10]}, "properties": {"eventtype": "EQ", "fromdate": "2026-11-20"}}]})
        self.assertEqual(g, [["2026-11-20", "2026-11-22", "40.2000", "44.1000", "fire", "Forest fire in Armenia", "GDACS"]])
        e = O.parse_eonet({"events": [{"title": "Etna", "categories": [{"id": "volcanoes"}],
                                       "geometry": [{"date": "2026-11-21T00:00:00Z", "type": "Point", "coordinates": [15.0, 37.75]}]}]})
        self.assertEqual(e[0][4], "volc")

    def test_one_list_failing_keeps_the_other(self):
        def get(url, **kw):
            if "gdacs" in url:
                raise RuntimeError("timeout")
            return {"events": [{"title": "Fire", "categories": [{"id": "wildfires"}],
                                "geometry": [{"date": "2026-11-21T00:00:00Z", "type": "Point", "coordinates": [44.0, 40.0]}]}]}
        n, errs = O.hazards_refresh(today=dt.date(2026, 11, 25), get=get)
        self.assertEqual(n, 1)
        self.assertTrue(errs and "GDACS" in errs[0])

    def test_fire_classifier_marks_a_listed_wildfire(self):
        import firecls
        idx = [{"a": dt.date(2026, 11, 20), "b": dt.date(2026, 11, 22), "lat": 40.0, "lon": 44.0, "kind": "fire", "name": "Fire", "src": "GDACS"}]
        near = {"lat": 40.05, "lon": 44.05, "date": "2026-11-21", "c": "anom", "a": 70, "why": "No fire here."}
        far = {"lat": 42.0, "lon": 44.0, "date": "2026-11-21", "c": "anom", "a": 70, "why": "No fire here."}
        firecls.natural_check([near, far], "iran", idx)
        self.assertEqual((near["c"], near["a"], near.get("natural")), ("unex", 40, 1))
        self.assertIn("GDACS", near["why"])
        self.assertEqual(far["c"], "anom")
        p = {"lat": 40.05, "lon": 44.05, "date": "2026-11-21", "c": "anom", "a": 70, "why": ""}
        firecls.natural_check([p], "ukraine", idx)       # Ukraine is judged by The Economist's model instead
        self.assertEqual(p["c"], "anom")


SDN = ('36,"ATLANTIC STAR","vessel","IRAN","-0- ","9HXA7","Crude Oil Tanker","-0- ","-0- ","Panama","-0- ",'
       '"Vessel Registration Identification IMO 9187629; MMSI 352001234; Linked To: X."\n'
       '37,"EP-MMB","aircraft","SDGT","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ",'
       '"Aircraft Model A340-642; Aircraft Operator MAHAN AIR; Aircraft Tail Number EP-MMB; Aircraft Mode S Transponder Code 730C7E;"\n'
       '38,"SOME PERSON","individual","RUSSIA-EO14024","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","DOB 1970."\n'
       '39,"CARGO ONE","aircraft","RUSSIA-EO14024","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","Aircraft Model Il-76TD;"\n')
COMMENTS = '39,"Aircraft Tail Number RA-76502."\n'


class TestSanctions(unittest.TestCase):
    def test_parse_sdn(self):
        rows = SN.parse_sdn(SDN, COMMENTS)
        keys = {(r[0], r[1]) for r in rows}
        self.assertEqual(keys, {("imo", "9187629"), ("mmsi", "352001234"), ("tail", "EPMMB"), ("hex", "730c7e"), ("tail", "RA76502")})

    def test_matching(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv")
            SN.refresh(p, get=lambda url, **kw: COMMENTS if "COMMENTS" in url.upper() else SDN)
            w = SN.watch(p)
        self.assertEqual(SN.aircraft_match({"r": "EP-MMB", "icao": "000000"}, w), "EP-MMB")
        self.assertEqual(SN.aircraft_match({"r": "", "icao": "730C7E"}, w), "EP-MMB")
        self.assertEqual(SN.aircraft_match({"r": "D-AIXA", "icao": "3c0000"}, w), "")
        self.assertEqual(SN.ship_match(9187629, "1", w), "ATLANTIC STAR")
        self.assertEqual(SN.ship_match(None, "352001234", w), "ATLANTIC STAR")

    def test_ais_counts_sanctioned_ships_per_region(self):
        import aiswatch
        w = {"imo": {"9187629": "ATLANTIC STAR"}}
        today = {"baltic": {"tanker": ["111", "222"]}}
        ships = {"111": {"imo": 9187629}, "222": {"imo": 1234567}}
        got = aiswatch.counts(today, {}, ships, w)
        self.assertEqual(got["aisday_sanctioned_baltic"], 1.0)
        self.assertEqual(got["aisday_sanctioned_blacksea"], 0.0)
        self.assertNotIn("aisday_sanctioned_baltic", aiswatch.counts(today, {}, ships, {}))   # no list yet: no series, not zeros


class TestEvidenceGrade(unittest.TestCase):
    def test_grades(self):
        import eventdesk as E
        h = lambda s: {"src": s, "t": "x", "d": "2026-11-20", "u": ""}   # noqa: E731
        self.assertEqual(E.grade([h("Reuters"), h("BBC"), h("TASS")]), ("several outlets", 3))
        self.assertEqual(E.grade([h("Reuters"), h("Reuters")]), ("one outlet", 1))
        self.assertEqual(E.grade([h("TASS"), h("RIA Novosti"), h("Press TV")]), ("state media only", 3))
        self.assertEqual(E.grade([h("Reuters"), h("Xinhua")]), ("one outlet", 2))


class TestCatalogue(unittest.TestCase):
    def test_new_families_are_untested_and_unscored(self):
        new = [s for s in catalog.SERIES if s["id"].startswith(("hormuz_", "geoconf_", "ca_", "aisday_sanctioned_", "flights_sanc_"))]
        self.assertTrue(new)
        self.assertTrue(all(not s["scored"] and s.get("untested") for s in new))
        ids = {s["id"] for s in new}
        self.assertIn("hormuz_cross_iran", ids)
        self.assertEqual({f"geoconf_{t}" for t in C.BOXES} - ids, set())
