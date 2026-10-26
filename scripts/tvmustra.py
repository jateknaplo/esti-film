"""tvmustra.hu csatornánkénti napi oldal (NEM az /este oldal) -- a port.hu-n hiányzó csatornákhoz.

A napi oldal csak időt és címet ad; a részleteket (év, műfaj, sorozatrész-e) ugyanaz az
ajax-végpont adja, amit az oldal JavaScriptje hív. Részletet csak a napon belül egyszer
szereplő címekre kérünk (az ismétlődő cím sorozat), és a válaszokat cache-eljük.
"""
import json
import re
from datetime import datetime, timedelta

from musortv import BUD, fetch

BASE = "https://www.tvmustra.hu"
ROW = re.compile(r"loadDetailsVertical\(this,\s*'([a-z0-9_]+)',\s*(\d+),\s*'(\d\d:\d\d)'\)\">\s*"
                 r"<div class=\"v-time\">[^<]*</div>\s*<div class=\"v-title\">([^<]*)</div>")


def day(code, d, details_cache):
    """[esemény] az adott napra; details_cache: {id: részlet-dict}, a hívó menti."""
    import html
    page = fetch(f"{BASE}/tvmusor/{code}/{d:%Y-%m-%d}")
    rows = [(t, int(i), hm, html.unescape(title).strip()) for t, i, hm, title in ROW.findall(page)]
    counts = {}
    for _, _, _, title in rows:
        counts[title] = counts.get(title, 0) + 1
    out, prev, shift = [], None, 0
    for table, pid, hm, title in rows:
        h, m = map(int, hm.split(":"))
        if prev is not None and h * 60 + m < prev:
            shift = 1  # éjfél után a következő nap
        prev = h * 60 + m
        start = datetime(d.year, d.month, d.day, h, m, tzinfo=BUD) + timedelta(days=shift)
        if counts[title] > 1:
            desc = "sorozat"
        else:
            key = str(pid)
            if key not in details_cache:
                raw = json.loads(fetch(f"{BASE}/index.php?ajax_action=get_details&table={table}&id={pid}"))
                details_cache[key] = raw.get("data", raw)
            x = details_cache[key]
            series = x.get("epizod") or x.get("evad") or re.search(r"\d+\.\s*rész", x.get("short") or "")
            genre = (x.get("kategoria") or "").strip()
            desc = (f"{genre} sorozat" if series else f"{genre} film").strip()
            if x.get("gyartasiev") and not series:
                desc += f",{x['gyartasiev']}"
        out.append({
            "start": start.isoformat(),
            "title": title,
            "desc": desc,
            "url": f"{BASE}/tvmusor/{code}/{d:%Y-%m-%d}",
            "channel_name": code,
        })
    return out
