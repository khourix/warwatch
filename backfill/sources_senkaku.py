"""Japan Coast Guard daily counts of China Coast Guard vessels around the Senkaku Islands, September 2012 on. Free, public.

The Coast Guard publishes one PDF per month with a row per day: vessels in the contiguous zone and vessels that entered the
territorial sea. This step only downloads each month's PDF and keeps its text (backfill/data/senkaku/raw/<file>.txt), so the
table layout can be checked before anything is parsed. The test plan is docs/SENKAKU_PLAN.md.
"""
import io
import os
import re
import subprocess
import tempfile

import common as K

PAGE = "https://www.kaiho.mlit.go.jp/mission/senkaku/senkaku.html"
BASE = "https://www.kaiho.mlit.go.jp/mission/senkaku/"
OUT = os.path.join(K.DATA, "senkaku", "raw")


def _text(pdf):
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.flush()
            return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, check=True).stdout.decode("utf-8", "replace")
    except Exception:
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)


def cmd_senkaku():
    html = K.get(PAGE, raw=True).decode("utf-8", "replace")
    files = sorted(set(re.findall(r'href="(?:\./)?(data_[^"]+\.pdf)"', html)))
    K.log("senkaku:", len(files), "monthly files", files[:2], files[-2:])
    os.makedirs(OUT, exist_ok=True)
    for f in files:
        dest = os.path.join(OUT, f[:-4] + ".txt")
        if os.path.exists(dest) and not f.startswith("data_R8_"):      # the current year's files are revised as days are added
            continue
        try:
            open(dest, "w").write(_text(K.get(BASE + f, raw=True)))
        except Exception as e:
            K.log("skip", f, str(e)[:100])
