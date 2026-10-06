"""Series scores -> domain scores per theatre -> level.

Fails closed: a domain with no scorable series is unknown, and fewer than two
scorable domains gives 'insufficient data'. The level counts agreeing domains;
it is not a probability. A Warning or Alert with no fast (non-lagging) domain
firing is labelled lagging-only: a confirmed build-up, not an early warning.
"""
import config as C


def directed(z, direction):
    if z is None:
        return None
    return {"up": z, "down": -z}.get(direction, abs(z))


def theatre_view(series, theatre):
    """series: list of dicts with domain, theatre, lag, direction, score."""
    doms = {}
    for s in series:
        if s["theatre"] not in (theatre, "global") or not s.get("score"):
            continue
        z = directed(s["score"]["z"], s["direction"])
        d = doms.setdefault(s["domain"], {"items": []})
        d["items"].append((z, s))
    out = {}
    for dom in C.DOMAINS:
        items = doms.get(dom, {}).get("items", [])
        if not items:
            out[dom] = {"z": None, "n": 0, "drivers": [], "fast": False}
            continue
        items.sort(key=lambda t: -t[0])
        # one outlier among many series is expected by chance: a domain's
        # score is the mean of its two strongest series (a lone series is
        # discounted), so it takes two agreeing series to fire.
        top = [z for z, _ in items[:2]]
        zd = sum(top) / 2 if len(top) == 2 else top[0] * 0.7
        out[dom] = {"z": zd, "n": len(items), "fast": not items[0][1]["lag"],
                    "drivers": [(s["id"], round(z, 2)) for z, s in items[:3]]}
    return out


def level(domains):
    live = {d: s for d, s in domains.items() if s["z"] is not None}
    if len(live) < 2:
        return {"level": "insufficient data", "firing": [], "scorable": len(live), "basis": ""}
    firing = sorted(d for d, s in live.items() if s["z"] >= C.THRESH_SIGNAL)
    watching = [d for d, s in live.items() if s["z"] >= C.THRESH_WATCH]
    n = len(firing)
    lv = "Alert" if n >= 3 else "Warning" if n == 2 else "Watch" if (n == 1 or len(watching) >= 2) else "Normal"
    basis = ""
    if lv in ("Warning", "Alert"):
        basis = "leading and lagging" if any(live[d]["fast"] for d in firing) else "lagging only"
    return {"level": lv, "firing": firing, "scorable": len(live), "basis": basis}
