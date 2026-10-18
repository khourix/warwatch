"""Activity v1 (warwatch/activity.py, docs/ACTIVITY.md). Run through test_warwatch.py, which imports these classes."""
import csv
import datetime as dt
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import activity as A  # noqa: E402

TODAY = dt.date(2026, 10, 17)


def _write(path, days, value, spike=None):
    """A flat daily series of `days` days to yesterday; `spike` = (days ago, value) raises the last few days."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for k in range(days, 0, -1):
            d = TODAY - dt.timedelta(k)
            v = spike[1] if spike and k <= spike[0] else value + (k % 3)
            w.writerow([d.isoformat(), v])


class TestActivity(unittest.TestCase):
    def setUp(self):
        self.bf, self.old = tempfile.mkdtemp(), A.BF
        A.BF = self.bf

    def tearDown(self):
        A.BF = self.old
        shutil.rmtree(self.bf, ignore_errors=True)

    def test_cut_is_the_base_family_alone(self):
        self.assertAlmostEqual(A.CUT, 1.03616, places=4)   # the study's cut

    def test_a_wiki_spike_turns_the_theatre_on(self):
        _write(os.path.join(self.bf, "wiki_yemen.csv"), 400, 1000, spike=(4, 5000))
        _write(os.path.join(self.bf, "wiki_korea.csv"), 400, 1000)
        act = A.compute([], {}, TODAY)
        self.assertTrue(act["yemen"]["on"])
        self.assertTrue(act["yemen"]["families"]["wiki"])
        self.assertAlmostEqual(act["yemen"]["index"], round(100 * A.WEIGHTS["wiki"] / sum(A.WEIGHTS.values()), 1))
        self.assertFalse(act["korea"]["on"])
        self.assertIs(act["korea"]["families"]["wiki"], False)
        self.assertIn("adsb_fighter", act["korea"]["missing"])

    def test_stale_data_reads_as_missing_not_quiet(self):
        _write(os.path.join(self.bf, "wiki_yemen.csv"), 400, 1000, spike=(4, 5000))
        act = A.compute([], {}, TODAY + dt.timedelta(10))   # the newest data is now 11 days old
        self.assertIsNone(act["yemen"]["families"]["wiki"])
        self.assertFalse(act["yemen"]["on"])

    def test_aliases_read_the_neighbouring_boxes(self):
        _write(os.path.join(self.bf, "adsb_gulf_fighter.csv"), 400, 10, spike=(3, 60))
        self.assertTrue(A.compute([], {}, TODAY)["iran"]["families"]["adsb_fighter"])

    def test_tells_and_bases_from_the_run(self):
        tells = {"lebanon": [{"id": "sea", "on": True}], "korea": [{"id": "airspace", "on": True}, {"id": "sea", "on": False}]}
        series = [{"id": "bases_out_taiwan", "points": [[(TODAY - dt.timedelta(2)).isoformat(), 1]]},
                  {"id": "bases_in_scs", "points": [[(TODAY - dt.timedelta(2)).isoformat(), 0]]}]
        act = A.compute(series, tells, TODAY)
        self.assertTrue(act["israel"]["families"]["tells"])
        self.assertIs(act["korea"]["families"]["tells"], False)   # airspace is not one of the study's tells
        self.assertTrue(act["taiwan"]["families"]["base"] and act["taiwan"]["on"])
        self.assertIs(act["scs"]["families"]["base"], False)
        self.assertIsNone(act["drc"]["families"]["base"])

    def test_forward_record_chains_and_appends_once_a_day(self):
        _write(os.path.join(self.bf, "wiki_yemen.csv"), 400, 1000, spike=(4, 5000))
        act, path = A.compute([], {}, TODAY), os.path.join(self.bf, "log_activity.csv")
        self.assertEqual(A.forward_append(act, "2026-10-17", path), len(A.THEATRES))
        self.assertEqual(A.forward_append(act, "2026-10-17", path), 0)
        self.assertEqual(A.forward_append(act, "2026-10-18", path), len(A.THEATRES))
        ok, bad, rows = A.forward_verify(path)
        self.assertTrue(ok and bad is None and len(rows) == 2 * len(A.THEATRES))
        self.assertEqual(next(r for r in rows if r["theatre"] == "yemen")["families_on"], "wiki")
        with open(path) as f:
            text = f.read()
        with open(path, "w") as f:
            f.write(text.replace(",yemen,17.3,1,", ",yemen,0.0,0,", 1))
        self.assertFalse(A.forward_verify(path)[0])

    def test_the_page_gets_the_chip_beside_the_level(self):
        import dashboard
        import demo
        import run
        _write(os.path.join(self.bf, "wiki_yemen.csv"), 400, 1000, spike=(4, 5000))
        res = run.evaluate(demo.scenario("buildup"))
        res["activity"] = A.compute(res["series"], {}, TODAY)
        d = dashboard.build_data(res, "2026-10-17 12:00 UTC", True, None, None)
        self.assertEqual(d["theatres"]["yemen"]["act"]["on"], True)
        self.assertNotIn("act", d["theatres"]["gulf"])   # not a study theatre: read under Iran
        page = dashboard.page_html(d, "2026-10-17 12:00 UTC")
        self.assertIn("const actChip", page)
        self.assertIn("${lvPill(th.level)} ${actChip(t)}", page)


if __name__ == "__main__":
    unittest.main()
