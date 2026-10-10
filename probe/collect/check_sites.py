"""Check which blocked sites open from the home runner, and with which method.

Runs every site through four methods and records each result, so the stealth
browsers can be compared: plain urllib, curl_cffi with a Chrome TLS fingerprint,
Camoufox (stealth Firefox) and CloakBrowser (stealth Chromium, free tier), both
in a virtual display. "ok" means real content, not a challenge or block page.
"""
import json
import sys
import time
import urllib.request

SITES = [
    ("control: example.com", "https://example.com/"),
    ("MARAD advisories", "https://www.maritime.dot.gov/msci-advisories"),
    ("JMIC products (UKMTO)", "https://www.ukmto.org/partner-products/jmic-products"),
    ("Crisis Group CrisisWatch", "https://www.crisisgroup.org/crisiswatch"),
    ("Japan Joint Staff press", "https://www.mod.go.jp/js/press/index.html"),
    ("Japan Coast Guard warnings", "https://www1.kaiho.mlit.go.jp/TUHO/"),
    ("China MSA navigation warnings", "https://www.msa.gov.cn/page/outter/weather.jsp"),
    ("China Customs statistics", "http://stats.customs.gov.cn/"),
    ("Smartraveller export", "https://www.smartraveller.gov.au/destinations-export"),
    ("Israel Home Front Command history", "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json"),
    ("Bluesky post search", "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=mobilization&limit=3"),
]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
BLOCK_MARKS = ("Just a moment", "Access Denied", "403 Forbidden", "ERROR: ACCESS DENIED", "cf-chl", "captcha")


def blocked(text):
    head = text[:5000]
    return any(m.lower() in head.lower() for m in BLOCK_MARKS)


def try_urllib(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(4000).decode("utf-8", "replace")


def try_curl_cffi(url):
    from curl_cffi import requests as cr
    r = cr.get(url, impersonate="chrome", timeout=40)
    return r.status_code, r.text[:400_000]


def try_camoufox(url):
    from camoufox.sync_api import Camoufox
    with Camoufox(headless="virtual", humanize=True) as browser:
        page = browser.new_page()
        resp = page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        page.wait_for_timeout(8_000)
        return (resp.status if resp else 200), page.content()


def try_cloakbrowser(url):
    # CloakBrowser's wrapper returns a Playwright browser; check the call against
    # its README if the API has changed.
    from cloakbrowser import launch
    browser = launch(headless=False)
    try:
        page = browser.new_page()
        resp = page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        page.wait_for_timeout(8_000)
        return (resp.status if resp else 200), page.content()
    finally:
        browser.close()


METHODS = [("urllib", try_urllib), ("curl_cffi", try_curl_cffi),
           ("camoufox", try_camoufox), ("cloakbrowser", try_cloakbrowser)]


def main(out):
    results = []
    for name, url in SITES:
        row = {"name": name, "url": url, "attempts": [], "works_with": []}
        for label, fn in METHODS:
            t0 = time.time()
            try:
                status, text = fn(url)
                ok = status == 200 and not blocked(text) and len(text) > 200
                row["attempts"].append({"method": label, "status": status, "bytes": len(text), "ok": ok,
                                        "secs": round(time.time() - t0, 1), "head": text[:160]})
            except Exception as e:  # noqa: BLE001 - every failure is a result here
                ok = False
                row["attempts"].append({"method": label, "error": f"{type(e).__name__}: {e}"[:300],
                                        "secs": round(time.time() - t0, 1)})
            if ok:
                row["works_with"].append(label)
        print(f"{name}: {', '.join(row['works_with']) or 'blocked by all four'}", flush=True)
        results.append(row)
    with open(out, "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/sites.json")
