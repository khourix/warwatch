"""Check which blocked sites open from the home runner, and with which method.

Tries plain urllib, then curl_cffi with a Chrome TLS fingerprint, then a real
Chrome window driven by zendriver (in a virtual display). Records the first
method that returns real content, not a challenge or block page.
"""
import asyncio
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


async def _browser(url):
    import zendriver as zd
    browser = await zd.start(headless=False)
    try:
        page = await browser.get(url)
        await asyncio.sleep(10)
        html = await page.get_content()
    finally:
        stop = browser.stop()
        if asyncio.iscoroutine(stop):
            await stop
    return 200, html


def try_browser(url):
    return asyncio.run(_browser(url))


METHODS = [("urllib", try_urllib), ("curl_cffi", try_curl_cffi), ("zendriver", try_browser)]


def main(out):
    results = []
    for name, url in SITES:
        row = {"name": name, "url": url, "attempts": [], "works_with": None}
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
                row["works_with"] = label
                break
        print(f"{name}: {row['works_with'] or 'blocked by all three'}", flush=True)
        results.append(row)
    with open(out, "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/sites.json")
