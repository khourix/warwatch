"""Civil flights from the archive traces (flights.py) and ships from Global Fishing Watch (gfw.py). Run with test_warwatch.py."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flights as F  # noqa: E402
import gfw  # noqa: E402

AIRPORTS = F.Airports([("OTHH", "Hamad", "QA", 25.273, 51.608), ("OMDB", "Dubai", "AE", 25.253, 55.364), ("EGLL", "Heathrow", "GB", 51.470, -0.454),
                       ("LLBG", "Ben Gurion", "IL", 32.011, 34.887), ("LCLK", "Larnaca", "CY", 34.875, 33.625)])
ROUTES = {"QTR1": ["OTHH", "EGLL"], "ELY1": ["EGLL", "LLBG"], "QTR2": ["OTHH", "OMDB"]}


def leg(a, b, t0, minutes, call, cat="A3", gap_at=None, gap_s=0, ground=True, step=60):
    """Points from airport a to airport b: ground at both ends (unless ground=False), cruising at 35,000 ft in between."""
    (la0, lo0), (la1, lo1) = a, b
    n = int(minutes * 60 / step)
    pts = []
    if ground:
        pts.append([t0 - 120, la0, lo0, "ground", 10, 0, 0, None, {"flight": call, "category": cat}])
    t = t0
    for i in range(n + 1):
        f = i / n
        if gap_at is not None and abs(f - gap_at) < 1e-9:
            t += gap_s
        alt = min(35000, 3000 + 60000 * min(f, 1 - f))
        trk = 90.0
        pts.append([t, la0 + (la1 - la0) * f, lo0 + (lo1 - lo0) * f, int(alt), 450, trk, 0, None, {"flight": call, "category": cat}])
        t += step
    if ground:
        pts.append([t + 120, la1, lo1, "ground", 10, 0, 0, None, {"flight": call, "category": cat}])
    return pts, t + 240


OTHH, OMDB, EGLL, LLBG, LCLK = [AIRPORTS.info[k][2:4] for k in ("OTHH", "OMDB", "EGLL", "LLBG", "LCLK")]


class TestFlights(unittest.TestCase):
    def test_coverage_gap_at_altitude_keeps_one_leg(self):
        pts, _ = leg(OTHH, EGLL, 0, 400, "QTR1", gap_at=0.5, gap_s=7200)
        ls = F.legs(pts, AIRPORTS)
        self.assertEqual([(x["dep"], x["arr"]) for x in ls], [("OTHH", "EGLL")])
        self.assertEqual(F.judge(ls[0], ROUTES, AIRPORTS), "normal")

    def test_new_flight_number_splits_legs(self):
        a, t = leg(OTHH, EGLL, 0, 400, "QTR1", ground=False)
        b, _ = leg(EGLL, OTHH, t + 600, 400, "QTR9", ground=False)
        self.assertEqual(len(F.legs(a + b, AIRPORTS)), 2)

    def test_diversion_needs_an_approach_to_the_planned_airport(self):
        # Descends towards Ben Gurion, then lands at Larnaca: a diversion. Straight to Larnaca without coming near Ben Gurion: unknown.
        near = (LLBG[0] + 0.3, LLBG[1] - 0.9)
        a, t = leg(EGLL, near, 0, 240, "ELY1", ground=False)
        a[0][3] = "ground"
        b, _ = leg(near, LCLK, t, 30, "ELY1")
        lg = F.legs(a + b[1:], AIRPORTS)[0]
        self.assertEqual((lg["dep"], lg["arr"]), ("EGLL", "LCLK"))
        self.assertEqual(F.judge(lg, ROUTES, AIRPORTS), "diversion")
        far = F.legs(leg(EGLL, LCLK, 0, 240, "ELY1")[0], AIRPORTS)[0]
        self.assertIsNone(F.judge(far, ROUTES, AIRPORTS))

    def test_turnback_needs_an_airliner_in_view(self):
        out, t = leg(OTHH, (26.5, 52.5), 0, 20, "QTR2", ground=False)
        back, _ = leg((26.5, 52.5), OTHH, t, 20, "QTR2", ground=False)
        pts = [[-120, OTHH[0], OTHH[1], "ground", 0, 0, 0, None, {"flight": "QTR2", "category": "A3"}]] + out + back + \
              [[t + 1500, OTHH[0], OTHH[1], "ground", 0, 0, 0, None, {"flight": "QTR2", "category": "A3"}]]
        day = F.Day(AIRPORTS, ROUTES)
        day.add({"t": "A320", "dbFlags": 0}, pts)
        self.assertEqual(day.series()["flights_turnback_gulf"], 1.0)
        school = F.Day(AIRPORTS, ROUTES)       # a flight school under an airline-style callsign
        school.add({"t": "SR22", "dbFlags": 0}, [p[:8] + [dict(p[8], category="A1")] for p in pts])
        self.assertEqual(school.series()["flights_turnback_gulf"], 0.0)
        self.assertEqual(school.series()["flights_dep_gulf"], 0.0)

    def test_day_counts_and_hides_ladd_aircraft(self):
        near = (LLBG[0] + 0.3, LLBG[1] - 0.9)
        a, t = leg(EGLL, near, 0, 240, "ELY1", ground=False)
        a[0][3] = "ground"
        b, _ = leg(near, LCLK, t, 30, "ELY1")
        for flags, listed in ((0, 1), (8, 0)):
            day = F.Day(AIRPORTS, ROUTES)
            day.add({"t": "B738", "dbFlags": flags}, a + b[1:])
            self.assertEqual(day.series()["flights_div_israel"], 1.0)
            self.assertEqual(len(day.events), listed)
        self.assertEqual(day.apt["LLBG"]["div_away"], 1)

    def test_business_jet_leaving_the_theatre(self):
        pts, _ = leg(OMDB, EGLL, 0, 420, "N1GX", cat="A2")
        day = F.Day(AIRPORTS, ROUTES)
        day.add({"t": "GLF6", "dbFlags": 0}, pts)
        s = day.series()
        self.assertEqual((s["bizjet_dep_gulf"], s["bizjet_out_gulf"], s["flights_dep_gulf"]), (1.0, 1.0, 0.0))
        day.add({"t": "GLF6", "dbFlags": 1}, pts)     # military: counted by the military pass, not here
        self.assertEqual(day.series()["bizjet_dep_gulf"], 1.0)

    def test_raw_prefilter_matches_parsed_test(self):
        near, _ = leg(OTHH, OMDB, 0, 60, "QTR2")
        far, _ = leg((40.6, -73.8), (41.9, -87.9), 0, 60, "AAL1")
        for pts, want in ((near, True), (far, False)):
            raw = json.dumps({"icao": "abc123", "timestamp": 0, "trace": pts}).encode()
            self.assertEqual(AIRPORTS.maybe_near(raw), want)
            self.assertEqual(AIRPORTS.touches(pts), want)

    def test_airliner_types(self):
        for t in ("A320", "A21N", "B38M", "B77W", "B789", "E190", "AT76", "DH8D", "A388", "BCS3", "CRJ9"):
            self.assertTrue(F.AIRLINER.match(t), t)
        for t in ("SR22", "DA42", "C172", "EC35", "GLF6", "B429", "PC12"):
            self.assertFalse(F.AIRLINER.match(t), t)


class TestGFW(unittest.TestCase):
    def test_sar_rows_by_day(self):
        p = {"entries": [{"public-global-sar-presence:v4.0": [{"date": "2026-10-19", "detections": 3, "lat": 25.9, "lon": 56.9},
                                                               {"date": "2026-10-19", "detections": 2, "lat": 25.6, "lon": 56.9},
                                                               {"date": "2026-10-16", "detections": 1, "lat": 25.0, "lon": 57.3}]}]}
        by, cells = gfw.parse_sar(p)
        self.assertEqual(by, {"2026-10-19": 5, "2026-10-16": 1})
        self.assertEqual(len(cells), 3)

    def test_event_stats_fill_gaps_but_not_the_tail(self):
        p = {"timeseries": [{"date": "2026-10-01T00:00:00.000Z", "value": 3}, {"date": "2026-10-04T00:00:00.000Z", "value": 1}]}
        self.assertEqual(sorted(gfw.parse_stats(p).items()), [("2026-10-01", 3.0), ("2026-10-02", 0.0), ("2026-10-03", 0.0), ("2026-10-04", 1.0)])
        self.assertEqual(gfw.parse_stats({}), {})


if __name__ == "__main__":
    unittest.main()
