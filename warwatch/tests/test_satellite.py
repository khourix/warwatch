#!/usr/bin/env python3
"""Fire classes (firecls, fireref) and the satellite base watch. Imported by test_warwatch.py, so its runs include these.
Run alone: python3 warwatch/tests/test_satellite.py"""
import datetime as dt
import gzip
import io
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("WARWATCH_HISTORY", tempfile.mkdtemp())
import firecls as F  # noqa: E402
import fireref as R  # noqa: E402


def row(t1=0, t2=0, t3=0, frp95=10.0, n95=2.0, d=None):
    return {"t1": t1, "t2": t2, "t3": t3, "frp95": frp95, "frpmax": frp95 * 2, "n95": n95, "last": "2025-12-01", "d": d or {}}


def ref(cells=None, coarse=None, sites=(), box="iran", years=range(2012, 2026), grid=None):
    return F.Ref(box, cells or {}, list(years), grid, coarse or {}, list(years), F.Sites(list(sites)))


def det(lat, lon, frp=10.0, date="2026-10-10", ts=None, dn="D", b4=330.0):
    return {"lat": lat, "lon": lon, "frp": frp, "date": date, "ts": ts or f"{date}T10:30Z", "daynight": dn, "bright_ti4": b4}


def full_grid(box_lat, box_lon, first=0, rows=20, cols=20):
    """A small first-year grid centred on a point; every cell has first year `first` (0 = never burned)."""
    i0, j0 = F.fine(box_lat, box_lon)
    i0, j0 = i0 - rows // 2, j0 - cols // 2
    return (i0, j0, rows, cols, bytes([first - 2000 if first else 0]) * (rows * cols))


class TestFireCls(unittest.TestCase):
    def test_static_cell_is_routine_industry(self):
        i, j = F.fine(30.4, 47.4)
        r = ref({(i, j): row(t2=40, d={y: 300 for y in range(2012, 2026)})})
        p = F.classify([det(30.4, 47.4, frp=12)], "iran", ref=r)[0]
        self.assertEqual(p["c"], "ind")
        self.assertTrue(p["routine"])
        self.assertIn("burns on 82% of days", p["why"])

    def test_much_hotter_than_its_normal_is_hot(self):
        i, j = F.fine(25.93, 49.68)
        site = {"name": "Abqaiq plant", "kind": "oilgas", "lat": 25.93, "lon": 49.68}
        r = ref({(i, j): row(t2=40, frp95=40, d={y: 300 for y in range(2012, 2026)})}, sites=[site])
        p = F.classify([det(25.93, 49.68, frp=640)], "iran", ref=r)[0]
        self.assertEqual(p["c"], "hot")
        self.assertIn("Abqaiq plant", p["why"])
        self.assertIn("usual 40 MW", p["why"])

    def test_saturated_pixel_at_a_plant_is_hot(self):
        i, j = F.fine(25.93, 49.68)
        r = ref({(i, j): row(t2=40, frp95=40, d={y: 300 for y in range(2012, 2026)})})
        p = F.classify([det(25.93, 49.68, frp=0, b4=367.0)], "iran", ref=r)[0]
        self.assertEqual(p["c"], "hot")

    def test_new_fire_by_a_base_at_night_is_an_anomaly(self):
        base = {"name": "Isfahan air base", "kind": "military", "lat": 32.76, "lon": 51.86}
        r = ref(sites=[base], grid=full_grid(32.75, 51.86))
        p = F.classify([det(32.75, 51.86, frp=80, dn="N")], "iran", ref=r)[0]
        self.assertEqual(p["c"], "anom")
        self.assertGreaterEqual(p["a"], 60)
        self.assertIn("Isfahan air base", p["why"])
        self.assertIn("No fire here", p["why"])

    def test_farm_area_in_its_season_is_seasonal_and_not_out_of_it(self):
        I, J = F.coarse(36.4, 40.9)
        june = 1 << 5
        r = ref(coarse={(I, J): {y: june for y in range(2012, 2022)}}, box="iran")
        self.assertEqual(F.classify([det(36.4, 40.9, date="2026-06-15")], "iran", ref=r)[0]["c"], "seas")
        self.assertIn(F.classify([det(36.4, 40.9, date="2026-10-15")], "iran", ref=r)[0]["c"], ("unex", "anom"))

    def test_war_years_are_left_out_of_the_seasonal_baseline(self):
        I, J = F.coarse(48.1, 37.7)
        july = 1 << 6
        # the front line burned every July since 2022, but never before: Ukraine's baseline stops in 2021
        r = ref(coarse={(I, J): {y: july for y in range(2022, 2026)}}, box="ukraine")
        p = F.classify([det(48.1, 37.7, date="2026-07-15")], "ukraine", ref=r)[0]
        self.assertNotEqual(p["c"], "seas")

    def test_seasonal_but_next_to_a_depot_stays_unexplained(self):
        I, J = F.coarse(36.4, 40.9)
        depot = {"name": "Fuel tanks", "kind": "fuel", "lat": 36.405, "lon": 40.9}
        r = ref(coarse={(I, J): {y: 1 << 5 for y in range(2012, 2026)}}, sites=[depot])
        p = F.classify([det(36.4, 40.9, date="2026-06-15")], "iran", ref=r)[0]
        self.assertIn(p["c"], ("unex", "anom"))
        self.assertIn("often burns in June", p["why"])

    def test_volcano_and_offshore(self):
        i, j = F.fine(13.4, 41.7)
        r = ref({(i, j): row(t1=10)})
        self.assertEqual(F.classify([det(13.4, 41.7)], "yemen", ref=r)[0]["c"], "volc")
        i, j = F.fine(26.5, 52.8)
        r = ref({(i, j): row(t3=900, d={y: 300 for y in range(2012, 2026)})})       # a platform: over water and every day
        self.assertEqual(F.classify([det(26.5, 52.8)], "iran", ref=r)[0]["c"], "off")
        r = ref({(i, j): row(t3=30, d={y: 6 for y in range(2012, 2026)})})          # reeds or a river front: over water, now and then
        self.assertNotEqual(F.classify([det(26.5, 52.8)], "iran", ref=r)[0]["c"], "off")

    def test_cluster_in_one_pass_adds_to_the_score(self):
        r = ref(grid=full_grid(35.65, 51.32))
        one = F.classify([det(35.65, 51.32, frp=30)], "iran", ref=r)[0]["a"]
        many = F.classify([det(35.65 + k * 0.003, 51.32, frp=30) for k in range(4)], "iran", ref=r)
        self.assertGreater(many[0]["a"], one)
        self.assertEqual(len({p["cid"] for p in many}), 1)       # one cluster

    def test_no_reference_falls_back_to_the_seven_day_rule(self):
        pts = [det(30.4, 47.4, date=f"2026-10-0{k}") for k in range(1, 5)] + [det(33.0, 44.0)]
        out = F.classify(pts, "nowhere", ref=None) if F.load("nowhere") is None else None
        self.assertEqual([p["c"] for p in out], ["ind"] * 4 + ["unex"])

    def test_review_turns_a_burnt_field_seasonal_and_adds_a_scar_note(self):
        r = ref(grid=full_grid(35.65, 51.32))
        pts = F.classify([det(35.65, 51.32, frp=30), det(32.0, 50.0, frp=90, dn="N")], "iran", ref=r)
        rev = {pts[0]["cid"]: {"verdict": "scar", "ha": 4.0, "lc": "cropland", "bd": "2026-10-01", "ad": "2026-10-12"},
               pts[1]["cid"]: {"verdict": "scar", "ha": 2.5, "lc": "built", "bd": "2026-10-01", "ad": "2026-10-12"}}
        F.review(pts, rev)
        self.assertEqual(pts[0]["c"], "seas")
        self.assertIn("burn scar (2.5 ha)", pts[1]["why"])

    def test_payload_keeps_r_for_explained_and_adds_class_fields(self):
        import dashboard
        p = dict(det(30.4, 47.4), c="ind", a=10, why="Gas flare.", routine=True)
        d = dashboard.fire_json(p, lambda la, lo: [lo, la])
        self.assertEqual((d["r"], d["c"], d["ll"]), (1, "ind", [30.4, 47.4]))
        self.assertNotIn("u", d)
        self.assertNotIn("url", d)

    def test_daily_counts_and_anomaly_cache(self):
        today = dt.date(2026, 10, 15)
        pts = [dict(det(32.75, 51.86, date="2026-10-14"), c="anom", a=80, cid="iran_1_2_2026-10-14", box="iran", sat="SNPP"),
               dict(det(32.75, 51.86, date="2026-10-14"), c="anom", a=70, cid="iran_1_2_2026-10-14", box="iran", sat="NOAA20"),
               dict(det(30.4, 47.4, date="2026-10-13"), c="ind", a=10, box="iran", sat="SNPP")]
        F.save_daily(pts, today)
        self.assertEqual(dict(F.daily_series("iran"))["2026-10-14"], 1.0)    # S-NPP only
        self.assertEqual(dict(F.daily_series("iran"))["2026-10-13"], 0.0)
        self.assertEqual(F.save_anoms(pts, today), 1)


    def test_economist_war_fire_upgrades_a_seasonal_fire_in_ukraine_only(self):
        import store
        store.cache_rows_save(F.ECON, [["2026-07-15", "48.1000", "37.7000"]])
        F._ECON.clear()
        I, J = F.coarse(48.1, 37.7)
        r = ref(coarse={(I, J): {y: 1 << 6 for y in range(2012, 2022)}}, box="ukraine")
        p = F.classify([det(48.1005, 37.7, date="2026-07-15")], "ukraine", ref=r)[0]
        self.assertEqual(p["c"], "unex")
        self.assertIn("The Economist", p["why"])
        q = F.classify([det(48.1005, 37.7, date="2026-07-15")], "europe_east", ref=ref(coarse={(I, J): {y: 1 << 6 for y in range(2012, 2022)}}, box="europe_east"))[0]
        self.assertNotIn("Economist", q["why"])
        F._ECON.clear()

class TestFireRef(unittest.TestCase):
    def test_reduce_counts_days_types_first_year_and_skips_static_in_coarse(self):
        a = R.Acc("iran", (22, 40, 38, 64))
        a.start_year(2020)
        for k in range(70):    # a flare: 70 days
            d = (dt.date(2020, 1, 1) + dt.timedelta(k)).isoformat()
            a.add(30.4, 47.4, d, 12.0, 2)
        a.add(36.4, 40.9, "2020-06-15", 5.0, 0)    # a field fire
        a.add(36.4, 40.9, "2020-06-15", 6.0, 0)    # same cell, same day: one day
        a.end_year()
        flare, field = F.fine(30.4, 47.4), F.fine(36.4, 40.9)
        self.assertEqual(a.days[flare][2020], 70)
        self.assertEqual(a.days[field][2020], 1)
        self.assertEqual(a.types[flare], [0, 70, 0])
        self.assertEqual(a.coarse[F.coarse(36.4, 40.9)][2020], 1 << 5)
        self.assertNotIn(F.coarse(30.4, 47.4), a.coarse)        # the flare does not make its area seasonal
        r, c = field[0] - a.i0, field[1] - a.j0
        self.assertEqual(a.first[r * a.cols + c], 20)
        self.assertEqual(a.pick_notable(), {flare})

    def test_tables_round_trip(self):
        cells = {(1, 2): row(t2=5, d={2012: 3, 2013: 0})}
        buf = io.StringIO()
        F.write_cells(buf, cells, [2012, 2013])
        back, years = F.read_cells(io.StringIO(buf.getvalue()))
        self.assertEqual(years, [2012, 2013])
        self.assertEqual(back[(1, 2)]["t2"], 5)
        self.assertEqual(back[(1, 2)]["d"], {2012: 3, 2013: 0})
        g = F.read_grid(F.write_grid(5, 6, 2, 3, bytearray(b"\x00\x0c\x00\x00\x00\x0e")))
        rf = F.Ref("iran", {}, [], g, {}, [], F.Sites([]))
        self.assertEqual((rf.first_year(5, 7), rf.first_year(6, 8), rf.first_year(5, 6), rf.first_year(9, 9)), (2012, 2014, 0, None))

    def test_frp_quantile_from_histogram(self):
        h = [0] * len(R.FRP_EDGES)
        h[R.frp_bin(4.0)] = 95
        h[R.frp_bin(400.0)] = 5
        self.assertLess(R.frp_pct(h, 0.9), 5.0)
        self.assertGreater(R.frp_pct(h, 0.99), 300)

    def test_storage_tanks_merge_within_400_m(self):
        t = lambda la, lo, c="": {"id": f"t{la}{lo}", "name": "", "kind": "fuel", "lat": la, "lon": lo, "src": "osm", "content": c}
        near = [t(30.0, 47.0, "crude oil"), t(30.0027, 47.0)]        # 300 m apart: one site
        far = [t(31.0, 48.0, "oil"), t(31.0054, 48.0, "oil")]          # 600 m apart: two sites
        lone = [t(32.0, 49.0)]                                           # untagged single tank: dropped
        out = R.merge_tanks(near + far + lone)
        self.assertEqual(len(out), 3)

    def test_osm_kinds(self):
        self.assertEqual(R.osm_kind({"man_made": "flare"}), "flare")
        self.assertEqual(R.osm_kind({"landuse": "military"}), "military")
        self.assertEqual(R.osm_kind({"power": "substation", "voltage": "400000;220000"}), "substation")
        self.assertIsNone(R.osm_kind({"power": "substation", "voltage": "110000"}))
        self.assertEqual(R.osm_kind({"man_made": "works", "product": "Steel"}), "steel")

    def test_xlsx_reader(self):
        sheet = ('<worksheet><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                 '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>30.5</v></c></row></sheetData></worksheet>')
        ss = '<sst><si><t>Country</t></si><si><t>Latitude</t></si><si><t>Iraq</t></si></sst>'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/worksheets/sheet1.xml", sheet)
            z.writestr("xl/sharedStrings.xml", ss)
        self.assertEqual(R.xlsx_rows(buf.getvalue()), [["Country", "Latitude"], ["Iraq", 30.5]])


if __name__ == "__main__":
    unittest.main()
