"""The switch-over: the new app (web/, built into web/dist) becomes the page at /warwatch/, and each theatre gets an address of
its own (/warwatch/iran/) with its own link preview. Standard library only. The workflow runs it after the web build:

    python3 warwatch/pages.py site web/dist

It reads what run.py wrote to site/ (data/v1/ from contract.py, the old page as index.html) and:
- moves the old page to classic/ until CLASSIC_UNTIL, with <base href="../"> so its files still load from the root; after
  that date it is left out;
- writes the app's index.html once per address (the root, each theatre, each base, signals/, record/, map/) with its own title,
  description and og/twitter tags, and <base href> at the root so data, images and routes resolve from any depth;
- writes 404.html, the same page: GitHub Pages serves it for any other address (a theatre's tab, a signal) and the app reads
  the path;
- writes next/index.html, which sends the preview's links (/warwatch/next/#/theatre/iran) on to the root, where the app moves
  them to their path.
Each theatre's preview image is og/<theatre>.jpg when the workflow drew it from og-card-<theatre>.html, else the site's og.jpg.
If this fails, the workflow keeps site/ as run.py wrote it, so the old page stays at /warwatch/.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import sys

import share

CLASSIC_UNTIL = "2026-12-07"   # about 30 days after the switch-over; the old page is dropped after this date
URL = f"https://{share.SITE}/"
ROOT = "/" + share.SITE.split("/", 1)[1].strip("/") + "/" if "/" in share.SITE else "/"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def page(shell, path, title, desc, image, alt, noindex=False):
    """The app's index.html for one address. path is relative to the root ('' or 'iran/')."""
    e = lambda s: html.escape(s, quote=True)
    tags = (f'\n<base href="{ROOT}">\n<link rel="canonical" href="{URL}{path}">\n'
            + ('<meta name="robots" content="noindex">\n' if noindex else "")
            + '<link rel="alternate" type="application/rss+xml" title="WarWatch: this week" href="feed.xml">\n'
            + '<link rel="manifest" href="site.webmanifest">\n'
            + f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="WarWatch">\n'
            + f'<meta property="og:title" content="{e(title)}">\n<meta property="og:description" content="{e(desc)}">\n'
            + f'<meta property="og:url" content="{URL}{path}">\n<meta property="og:image" content="{e(image)}">\n'
            + '<meta property="og:image:type" content="image/jpeg">\n<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            + f'<meta property="og:image:alt" content="{e(alt)}">\n<meta name="twitter:card" content="summary_large_image">\n'
            + f'<meta name="twitter:title" content="{e(title)}">\n<meta name="twitter:description" content="{e(desc)}">\n<meta name="twitter:image" content="{e(image)}">')
    for anchor in ('<meta charset="utf-8">', "<title>WarWatch</title>", '<meta name="description" content="'):
        if anchor not in shell:
            raise ValueError(f"the app's index.html has no {anchor}")
    out = shell.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + tags, 1).replace("<title>WarWatch</title>", f"<title>{e(title)}</title>", 1)
    return re.sub(r'<meta name="description" content="[^"]*">', lambda _: f'<meta name="description" content="{e(desc)}">', out, count=1)


def classic(old, until):
    """The old page, served from classic/: its files load from the root, search engines skip it, and a bar says it is going."""
    day = dt.date.fromisoformat(until)
    bar = ('<div style="position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:9999;max-width:calc(100% - 32px);padding:8px 14px;border-radius:10px;'
           'background:#16213a;border:1px solid #2c5ad8;color:#e9edf3;font:13px/1.4 system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.4)">'
           f'This is the old WarWatch page. It stays here until {day.day} {day:%b %Y}. <a href="../" style="color:#7da8ff">Open the new WarWatch</a></div>')
    if '<meta charset="utf-8">' not in old or "<body>" not in old:
        raise ValueError("the old page has no charset or body tag")
    old = old.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="../">\n<meta name="robots" content="noindex">', 1)
    return old.replace("<body>", "<body>" + bar, 1)


NEXT = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>WarWatch</title>
<script>location.replace('../' + location.hash)</script></head>
<body><p>WarWatch has moved to <a href="../">the main address</a>.</p></body></html>
"""


def build(site, dist, today=None, until=CLASSIC_UNTIL):
    """-> the number of pages written. Nothing in site/ changes until every page is ready."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    v1 = os.path.join(site, "data", "v1")
    brief = json.loads(_read(os.path.join(v1, "brief.json")))
    try:
        bases = json.loads(_read(os.path.join(v1, "map", "live.json"))).get("bases") or []
    except (OSError, ValueError):
        bases = []
    shell = _read(os.path.join(dist, "index.html"))
    old = _read(os.path.join(site, "index.html"))
    if 'id="root"' in old:
        raise ValueError("site/index.html is already the app; run.py must write the old page first")
    stamp = "".join(c for c in brief.get("generated", "") if c.isdigit())
    img = lambda name: f"{URL}{name}?v={stamp}"
    c = brief.get("counts") or {}
    about = f"Early warning for {c.get('theatres', len(brief['theatres']))} war theatres, from {c.get('signals', 0)} public signals. Updated every 30 minutes."
    head = brief.get("headline", "")
    site_img, site_alt = img("og.jpg"), "WarWatch: " + head

    pages = {"": page(shell, "", "WarWatch", f"{head} {about}".strip(), site_img, site_alt)}
    for t in brief["theatres"]:
        h = share.theatre_headline(t["name"], t.get("level", "Normal"), t.get("tellsOn", 0))
        has_card = os.path.exists(os.path.join(site, "og", f"{t['id']}.jpg"))
        pages[f"{t['id']}/"] = page(shell, f"{t['id']}/", f"{t['name']} · WarWatch", " ".join(x for x in (t.get("context") and t["context"] + ".", h, about) if x),
                                    img(f"og/{t['id']}.jpg") if has_card else site_img, f"WarWatch: {h}" if has_card else site_alt)
    for b in bases:
        if not re.fullmatch(r"[\w.-]+", b.get("id", "")):
            continue
        name = b.get("name", "").split(",")[0] or b["id"]
        why = b.get("why") or "A base watched on free satellite radar."
        pages[f"base/{b['id']}/"] = page(shell, f"base/{b['id']}/", f"{name} · WarWatch", why, site_img, site_alt)
    for path, title in (("signals/", "Signals"), ("record/", "Track record"), ("map/", "Map")):
        pages[path] = page(shell, path, f"{title} · WarWatch", f"{head} {about}".strip(), site_img, site_alt)
    not_found = page(shell, "", "WarWatch", about, site_img, site_alt, noindex=True)
    keep_classic = today <= dt.date.fromisoformat(until)
    old_page = classic(old, until) if keep_classic else None

    # every page is ready: now change site/
    for name in os.listdir(dist):
        src, dst = os.path.join(dist, name), os.path.join(site, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif name != "index.html":
            shutil.copyfile(src, dst)
    if old_page:
        _write(os.path.join(site, "classic", "index.html"), old_page)
    for path, text in pages.items():
        _write(os.path.join(site, path, "index.html"), text)
    _write(os.path.join(site, "404.html"), not_found)
    _write(os.path.join(site, "next", "index.html"), NEXT)
    return len(pages) + 2 + bool(old_page)


if __name__ == "__main__":
    site, dist = sys.argv[1], sys.argv[2]
    print("pages:", build(site, dist))
