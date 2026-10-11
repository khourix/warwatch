#!/usr/bin/env python3
"""Layout checks for the rendered page in a real browser, on a phone, a tablet and a desktop.

Run: python3 warwatch/tests/test_layout.py
Needs Playwright with Chromium; skipped when it is not installed. Set CHROMIUM to use a browser binary that
Playwright did not download itself.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("WARWATCH_HISTORY", tempfile.mkdtemp())
import dashboard  # noqa: E402
import demo  # noqa: E402
import run  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

WIDTHS = [(390, 844, "phone"), (820, 1180, "tablet"), (1440, 900, "desktop")]
ROUTES = ["overview", "region/mideast", "iran", "gulf", "iran/signals", "israel/history", "signals", "activity", "record",
          "settings/health", "settings/method"]


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class TestLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        res = run.evaluate(demo.scenario("buildup"))
        page = dashboard.render(res, "2026-10-11 03:51 UTC", demo=True)
        if isinstance(page, tuple):
            page = page[0]
        cls.dir = tempfile.mkdtemp()
        cls.path = os.path.join(cls.dir, "index.html")
        with open(cls.path, "w") as f:
            f.write(page)
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
        except Exception as e:  # no browser binary
            cls.pw.stop()
            raise unittest.SkipTest(f"Chromium did not start: {e}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def visit(self, w, h, fn):
        ctx = self.browser.new_context(viewport={"width": w, "height": h}, has_touch=w < 900, is_mobile=w < 500)
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto("file://" + self.path + "#overview")
        pg.wait_for_timeout(400)
        try:
            fn(pg)
        finally:
            ctx.close()
        self.assertEqual(errors, [], f"script errors at {w}px")

    def test_no_page_scrolls_sideways(self):
        for w, h, name in WIDTHS:
            def check(pg):
                for r in ROUTES:
                    pg.evaluate(f"location.hash = '{r}'")
                    pg.wait_for_timeout(250)
                    sw = pg.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
                    self.assertLessEqual(sw, w + 1, f"{name} {r} is {sw}px wide")
            with self.subTest(name):
                self.visit(w, h, check)

    def test_phone_has_bottom_bar_and_theatre_list(self):
        def check(pg):
            self.assertTrue(pg.is_visible("#bnav"))
            self.assertFalse(pg.is_visible("#sb"))
            rows = pg.locator("#plist .prow")
            self.assertGreater(rows.count(), 10)
            self.assertTrue(rows.first.is_visible())
            self.assertFalse(pg.is_visible("#mapwrap"))
            pg.click("[data-pm=map]")
            self.assertTrue(pg.is_visible("#mapwrap"))
            pg.click("[data-pm=list]")
            rows.first.click()
            pg.wait_for_timeout(250)
            self.assertTrue(pg.is_visible(".ttl .bk"))
            self.assertNotEqual(pg.evaluate("location.hash"), "#overview")
        self.visit(390, 844, check)

    def test_desktop_keeps_sidebar_and_map(self):
        def check(pg):
            self.assertTrue(pg.is_visible("#sb"))
            self.assertTrue(pg.is_visible("#mapwrap"))
            self.assertFalse(pg.is_visible("#bnav"))
            self.assertFalse(pg.is_visible("#plist"))
        self.visit(1440, 900, check)


if __name__ == "__main__":
    unittest.main(verbosity=2)
