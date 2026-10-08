"""Tests for the event-study helpers. Need numpy, pandas and scipy (skipped where they are absent, as in the live build)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import numpy as np
    import eventstudy as ES
except ImportError:
    np = None


@unittest.skipIf(np is None, "analysis libraries not installed")
class EventStudy(unittest.TestCase):
    def test_runs_bridge_short_gaps_only(self):
        f = np.array([0, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1], bool)
        self.assertEqual(ES.runs(f, bridge=2), [(1, 5), (15, 15)])
        self.assertEqual(ES.runs(f, bridge=0), [(1, 2), (5, 5), (15, 15)])
        self.assertEqual(ES.runs(np.zeros(5, bool)), [])

    def test_isotonic_fit_is_monotone_and_averages_ties(self):
        x = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        y = np.array([0, 1, 0, 1, 1])
        m = ES.pav(x, y)
        q = ES.iso_apply(m, x)
        self.assertTrue(all(b >= a for a, b in zip(q, q[1:])))
        self.assertAlmostEqual(q[1], 0.5)
        self.assertAlmostEqual(q[2], 0.5)

    def test_platt_shift_recovers_known_offset(self):
        rng = np.random.default_rng(0)
        p = rng.uniform(0.02, 0.3, 20000)
        y = (rng.uniform(size=p.size) < ES.V.sigmoid(ES.V.logit(p) + 0.7)).astype(int)
        c, b = ES.platt(p, y, False)
        self.assertAlmostEqual(c, 0.7, delta=0.1)
        self.assertEqual(b, 1.0)


if __name__ == "__main__":
    unittest.main()
