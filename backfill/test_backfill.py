#!/usr/bin/env python3
"""Run: python3 backfill/test_backfill.py   (parsers only; no network)"""
import datetime as dt
import gzip
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["BACKFILL_DATA"] = tempfile.mkdtemp()
import common as K  # noqa: E402
import config as C  # noqa: E402
import sources_adsb as A  # noqa: E402
import sources_fast as F  # noqa: E402
import sources_slow as L  # noqa: E402


class T(unittest.TestCase):
    def test_gfw_boxes_match_catalogue(self):
        import catalog
        self.assertEqual(F.GFW_BOX, catalog.GFW_BOX)

    def test_fred_skips_holidays(self):
        self.assertEqual(F.parse_fred({"observations": [{"date": "2024-01-01", "value": "."}, {"date": "2024-01-02", "value": "39.05"}]}), {"2024-01-02": 39.05})

    def test_firms_counts(self):
        self.assertEqual(F.parse_firms_counts("latitude,acq_date,frp\n1,2019-03-01,1.5\n1,2019-03-01,2\n1,2019-03-02,4\n"),
                         {"2019-03-01": [2, 3.5], "2019-03-02": [1, 4.0]})

    def test_gfw_sums_flags(self):
        p = {"entries": [{"public-global-presence:v4.0": [{"date": "2018-01-01", "hours": 16}, {"date": "2018-01-01", "hours": 15}, {"date": "2018-01-02", "hours": 1}]}]}
        self.assertEqual(F.parse_gfw(p, "hours"), {"2018-01-01": 31.0, "2018-01-02": 1.0})

    def test_advisory(self):
        self.assertEqual(L.parse_advisory("Taiwan - Level 1: Exercise Normal Precautions"), (1, 0))
        self.assertEqual(L.parse_advisory("Level 4: Do Not Travel. The Department ordered departure of family members"), (4, 1))
        self.assertIsNone(L.parse_advisory("nothing"))
        kyiv = "<p>Level 4: Do Not Travel</p><p>On January 23, the Department of State ordered the departure of eligible family members</p>"
        self.assertEqual(L.parse_advisory(kyiv), (4, 1))
        nav = "<title>Iraq - Level 4: Do Not Travel</title><nav>Level 1: Exercise Normal Precautions</nav>"
        self.assertEqual(L.parse_advisory(nav, strict=True), (4, 0))      # the heading wins over the navigation
        self.assertIsNone(L.parse_advisory("<title>Iraq</title><nav>Level 1: Exercise Normal Precautions</nav>", strict=True))
        self.assertEqual(L.parse_advisory("<title>Iraq</title><nav>Level 1: x</nav>"), (1, 0))
        self.assertEqual(L.parse_departure("the Department authorized the departure of family members"), 1)
        self.assertEqual(L.parse_departure("Level 3: Reconsider Travel"), 0)

    def test_fill_forward_carry_limit(self):
        out = L.fill_forward([("2024-01-02", 2)], dt.date(2024, 1, 1), dt.date(2024, 1, 8), max_carry=3)
        self.assertEqual(sorted(out), ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])

    def test_country_and_theatre_files_are_named_apart(self):
        """The Iran and Ukraine slugs are also theatre names: the per-country ordered-departure file must not be
        the theatre total, or deriving the totals overwrites a country (and a second derive double counts)."""
        theatres = set(C.STATE_ISO)
        for code, slug in L.SLUG.items():
            self.assertNotIn(f"od_country_{slug}", {f"od_{t}" for t in theatres})
        self.assertIn("ukraine", theatres)
        self.assertEqual(L.SLUG["UP"], "ukraine")
        self.assertEqual(set(L.ISO3), set(L.SLUG))

    def test_derive_state_needs_every_country(self):
        import tempfile
        old = K.DATA
        K.DATA = tempfile.mkdtemp()
        try:
            K.write_csv(K.path("state_israel"), {"2026-01-01": 10.0})      # an older sum without Israel itself
            K.write_csv(K.path("state_level_lebanon"), {"2026-01-01": 4.0})
            K.write_csv(K.path("state_od_country_lebanon"), {"2026-01-01": 0.0})
            L.derive_state(["israel"])
            self.assertEqual(K.load("state_israel"), {})        # Israel, Jordan and Egypt have no history: no sum
            for slug, lv in (("israel-west-bank-and-gaza", 3.0), ("jordan", 3.0), ("egypt", 2.0)):
                K.write_csv(K.path(f"state_level_{slug}"), {"2026-01-01": lv})
                K.write_csv(K.path(f"state_od_country_{slug}"), {"2026-01-01": 1.0 if slug == "jordan" else 0.0})
            L.derive_state(["israel"])
            self.assertEqual(K.load("state_israel"), {"2026-01-01": 12.0})
            self.assertEqual(K.load("state_od_israel"), {"2026-01-01": 1.0})
            L.replace_from("state_level_jordan", {"2026-01-02": 2.0}, dt.date(2026, 1, 1))
            self.assertEqual(K.load("state_level_jordan"), {"2026-01-02": 2.0})
        finally:
            K.DATA = old

    def test_weekly_skips_unchanged(self):
        s = [("20240101000000", "a"), ("20240103000000", "b"), ("20240110000000", "b"), ("20240117000000", "c")]
        self.assertEqual(L.weekly(s), ["20240101000000", "20240110000000", "20240117000000"])

    def test_fill_forward(self):
        out = L.fill_forward([("2024-01-02", 2), ("2024-01-04", 3)], dt.date(2024, 1, 1), dt.date(2024, 1, 5))
        self.assertEqual(out, {"2024-01-02": 2, "2024-01-03": 2, "2024-01-04": 3, "2024-01-05": 3})

    def test_bulletin(self):
        r = L.parse_bulletin("今日共機24架次，其中18架次逾越中線，共艦7艘、公務船1艘")
        self.assertEqual(r, {"total": 24, "median": 18, "vessels": 7, "official": 1})
        quiet = L.parse_bulletin("偵獲共艦8艘及公務船9艘，持續活動。三、上述期間未偵獲共機，故無提供航跡圖。")
        self.assertEqual((quiet["total"], quiet["vessels"], quiet["official"]), (0, 8, 9))
        self.assertEqual(L.strip_tags("<p>&#x5171;&#x6A5F;24&#x67B6;&#x6B21;</p>").strip(), "共機24架次")
        self.assertEqual(L.parse_date("113/01/15"), dt.date(2024, 1, 15))

    def test_adsb_counts_one_day(self):
        def member(tar, hexid, t, flags, pts):
            b = gzip.compress(json.dumps({"icao": hexid, "t": t, "dbFlags": flags, "timestamp": 0, "trace": pts}).encode())
            ti = tarfile.TarInfo(f"./traces/{hexid[-2:]}/trace_full_{hexid}.json")
            ti.size = len(b)
            tar.addfile(ti, io.BytesIO(b))
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            member(tar, "aaaaaa", "K35R", 1, [[1, 26.0, 52.0], [2, 26.1, 52.1]])      # tanker over Iran, twice: counted once
            member(tar, "bbbbbb", "B738", 0, [[1, 26.0, 52.0]])                        # civil: ignored
            member(tar, "cccccc", "F16", 1, [[1, 48.0, 30.0], [2, None, None]])       # fighter over Ukraine
        buf.seek(0)
        seen = {("global", "mil"): set()}
        boxes = {"iran": C.BOXES["iran"], "ukraine": C.BOXES["ukraine"]}
        for th in boxes:
            for c in ["mil"] + list(A.CLASSES):
                seen[(th, c)] = set()
        tf = tarfile.open(fileobj=buf, mode="r|")
        for m in tf:
            b = gzip.decompress(tf.extractfile(m).read())
            if int(A.FLAGS.search(b[:600]).group(1)) & 1:
                d = json.loads(b)
                A.count_trace(d, d["trace"], boxes, seen)
        self.assertEqual(len(seen[("global", "mil")]), 2)
        self.assertEqual((len(seen[("iran", "tanker")]), len(seen[("iran", "mil")]), len(seen[("ukraine", "fighter")])), (1, 1, 1))

    def test_adsb_theatre_filter_rereads_held_days_and_writes_only_those_theatres(self):
        import datetime as dt
        import tempfile
        d, old_data = tempfile.mkdtemp(), K.DATA
        K.DATA = d
        K.save("adsb_global_mil", {"2026-10-01": 5})       # the day is already held for every older theatre
        day = dt.date(2026, 10, 1)
        seen = []
        orig = (A.releases, A.run_day)
        A.releases = lambda years, token=None: {day: ["u"]}
        A.run_day = lambda urls, boxes, day=None, mil=True: (seen.append(sorted(boxes)) or {("global", "mil"): 9.0, ("iraq", "mil"): 3.0, ("gulf", "mil"): 0.0}, 1, 1)
        try:
            A.cmd_adsb(day, day, only=["iraq", "gulf"])
        finally:
            A.releases, A.run_day = orig
            K.DATA = old_data
        self.assertEqual(seen, [["gulf", "iraq"]])
        K.DATA = d
        self.assertEqual(K.load("adsb_iraq_mil"), {"2026-10-01": 3.0})
        self.assertEqual(K.load("adsb_global_mil"), {"2026-10-01": 5.0})   # the denominator is left alone
        K.DATA = old_data

    def test_news_backfill_skips_held_days_and_leaves_failed_days_empty(self):
        import sources_news as N
        d, old_data = tempfile.mkdtemp(), K.DATA
        K.DATA = d
        K.save("news_iraq", {"2024-01-01": 7})
        calls = []
        orig = N.S.gnews_day

        def fake(q, day):
            calls.append(day.isoformat())
            if day == dt.date(2024, 1, 3):
                raise RuntimeError("429")
            return 4.0
        N.S.gnews_day = fake
        orig_sleep = N.time.sleep
        N.time.sleep = lambda s: None
        try:
            N.cmd_news(["iraq"], dt.date(2024, 1, 1), dt.date(2024, 1, 4))
            rows = K.load("news_iraq")
        finally:
            N.S.gnews_day, N.time.sleep, K.DATA = orig, orig_sleep, old_data
        self.assertEqual(rows, {"2024-01-01": 7.0, "2024-01-02": 4.0, "2024-01-04": 4.0})   # 3 Jan failed: absent, not zero
        self.assertNotIn("2024-01-01", calls)

    def test_series_merge_keeps_old_rows(self):
        K.save("x", {"2024-01-01": 1})
        K.save("x", {"2024-01-02": 2, "2024-01-01": 3})
        self.assertEqual(K.load("x"), {"2024-01-01": 3.0, "2024-01-02": 2.0})


class NightLights(unittest.TestCase):
    """Black Marble tile maths and the HDF5 read, on a small synthetic tile (needs h5py and numpy, like the workflow)."""

    def test_tile_ids_and_boxes(self):
        import sources_nightlights as NL
        self.assertEqual(NL.tile_of(35.69, 51.39), "h23v05")      # Tehran
        self.assertEqual(NL.tile_of(-1.68, 29.22), "h20v09")      # Goma, south of the equator
        r0, r1, c0, c1 = NL.box_px(35.69, 51.39)
        self.assertEqual((r1 - r0, c1 - c0), (25, 25))
        self.assertTrue(0 <= r0 < r1 <= 2400 and 0 <= c0 < c1 <= 2400)

    def test_read_tile_keeps_only_good_pixels(self):
        try:
            import h5py
            import numpy as np
        except ImportError:
            self.skipTest("h5py not installed")
        import sources_nightlights as NL
        ntl = np.full((2400, 2400), 100, dtype="uint16")           # 10.0 nW after the 0.1 scale
        qf = np.zeros((2400, 2400), dtype="uint8")
        r0, r1, c0, c1 = NL.box_px(35.69, 51.39)
        ntl[r0:r1, c0:c0 + 5] = 900                                  # a bright strip that is cloud-flagged: must not count
        qf[r0:r1, c0:c0 + 5] = 2
        p = os.path.join(tempfile.mkdtemp(), "t.h5")
        with h5py.File(p, "w") as f:
            g = f.create_group("HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields")
            d = g.create_dataset("DNB_BRDF-Corrected_NTL", data=ntl)
            d.attrs["scale_factor"], d.attrs["_FillValue"] = 0.1, 65535
            g.create_dataset("Mandatory_Quality_Flag", data=qf)
            g.create_dataset("Gap_Filled_DNB_BRDF-Corrected_NTL", data=ntl * 0 + 5000)
        got = NL.read_tile(p, [("iran", "Tehran", 35.69, 51.39), ("iran", "Isfahan", 32.65, 51.67)])
        self.assertEqual(got[("iran", "Tehran")], (10.0, 0.8))
        self.assertEqual(got[("iran", "Isfahan")], (10.0, 1.0))


class TestMergeFlights(unittest.TestCase):
    def test_shard_days_replace_same_days_and_places_union(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("backfill_cli", os.path.join(os.path.dirname(os.path.abspath(__file__)), "backfill.py"))
        B = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(B)
        d = tempfile.mkdtemp()
        def put(name, rows):
            with open(os.path.join(d, name), "w") as f:
                f.write("\n".join(",".join(r) for r in rows) + "\n")
        def get(name):
            with open(os.path.join(d, name)) as f:
                return [line.strip().split(",") for line in f if line.strip()]
        put("old.csv", [["date", "icao", "dep"], ["2026-10-01", "LLBG", "1"], ["2026-10-20", "LLBG", "5"]])
        put("new.csv", [["date", "icao", "dep"], ["2026-10-01", "LLBG", "2"], ["2026-10-01", "OTHH", "3"]])
        B.merge_flights(os.path.join(d, "new.csv"), os.path.join(d, "old.csv"))
        self.assertEqual(get("old.csv")[1:], [["2026-10-01", "LLBG", "2"], ["2026-10-01", "OTHH", "3"], ["2026-10-20", "LLBG", "5"]])
        os.makedirs(os.path.join(d, "a")); os.makedirs(os.path.join(d, "b"))
        put("a/places.csv", [["icao", "name"], ["LLBG", "Ben Gurion"]])
        put("b/places.csv", [["icao", "name"], ["OTHH", "Hamad"]])
        B.merge_flights(os.path.join(d, "a/places.csv"), os.path.join(d, "b/places.csv"))
        self.assertEqual(get("b/places.csv")[1:], [["LLBG", "Ben Gurion"], ["OTHH", "Hamad"]])


if __name__ == "__main__":
    unittest.main()


class TradeParse(unittest.TestCase):
    def test_pickups_use_the_4_digit_line_and_suvs_sum_their_6_digit_lines(self):
        import trade
        base = {"motCode": 0, "customsCode": "C00", "partner2Code": 0}
        rows = [dict(base, period=202301, cmdCode="8704", qty=144), dict(base, period=202301, cmdCode="870323", qty=3),
                dict(base, period=202301, cmdCode="870324", qty=2), dict(base, period=202302, cmdCode="870421", qty=10),
                dict(base, period=202302, cmdCode="870431", qty=5), dict(base, period=202303, cmdCode="8704", qty=9, motCode=6102)]
        got = trade.monthly(rows)
        self.assertEqual(got["pickup"], {"2023-01-01": 144.0, "2023-02-01": 15.0})     # the transport-mode split line is ignored
        self.assertEqual(got["suv"], {"2023-01-01": 5.0})


class EstatParse(unittest.TestCase):
    def test_month_columns_and_rows_sum_the_nine_digit_lines(self):
        import estat
        self.assertEqual(estat.monthly_cols({"150": "1月_数量1", "160": "1月_数量2", "190": "2月_数量2", "120": "合計_数量2"}), {"160": 1, "190": 2})
        rows = [{"@cat01": "870323915", "@cat02": "150", "@area": "50507", "@time": "2026000000", "$": "12"},
                {"@cat01": "870323919", "@cat02": "150", "@area": "50507", "@time": "2026000000", "$": "3"}]
        out = estat.rows_to_monthly(rows, {"870323915": "suv", "870323919": "suv"}, {"150": 1}, lambda t: int(str(t)[:4]))
        self.assertEqual(out, {("50507", "suv"): {"2026-01-01": 15.0}})
