"""musor.tv napi műsor letöltése és feldolgozása (csak stdlib)."""
import html
import re
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BUD = ZoneInfo("Europe/Budapest")
UA = "Mozilla/5.0 (esti-film; napi 2 lekeres)"
PAUSE = 1.2  # másodperc két kérés között
_last = [0.0]


def fetch(url, tries=3):
    wait = PAUSE - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            _last[0] = time.time()
            return body.decode("utf-8", "replace")
        except Exception as e:  # hálózati hiba: rövid szünet, újrapróbálás
            err = e
            _last[0] = time.time()
            time.sleep(3 * (i + 1))
    raise err


def day_url(code, day, today):
    if day == today:
        return f"https://musor.tv/mai/tvmusor/{code}"
    return f"https://musor.tv/napi/tvmusor/{code}/{day:%Y.%m.%d}"


_text = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse(page):
    """BroadcastEvent blokkok, csak a csatorna saját listájából (van address)."""
    out, seen = [], set()
    for p in page.split('itemtype="https://schema.org/BroadcastEvent"')[1:]:
        addr = re.search(r'itemprop="address" content="([^"]*)"', p)
        if not addr or not addr.group(1).strip():
            continue  # "most" doboz más csatornákról, oldalsáv
        t = re.search(r'itemprop="startDate" content="([^"]+)"', p)
        a = re.search(r'<a[^>]*href="(/tvmusor/[^"]+)"[^>]*>(.*?)</a>', p, re.S)
        if not t or not a:
            continue
        start = datetime.strptime(t.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(BUD)
        if start in seen:
            continue
        seen.add(start)
        d = re.search(r'progshortdesc"[^>]*>(.*?)</div>', p, re.S)
        out.append({
            "start": start.isoformat(),
            "title": _text(a.group(2)),
            "desc": _text(d.group(1)) if d else "",
            "url": "https://musor.tv" + a.group(1),
            "channel_name": _text(addr.group(1)),
        })
    return out
