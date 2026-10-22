"""port.hu tartalék: ugyanaz a JSON, amit a port.hu/tv oldal JavaScriptje kér le."""
import json
import urllib.parse
from datetime import datetime

from musortv import BUD, fetch


def day(port_ids, d):
    """{port_id: [esemény, ...]} az adott napra; a mezők a musortv.parse()-éval egyeznek."""
    q = [("channel_id[]", p) for p in port_ids] + [
        ("i_datetime_from", f"{d:%Y-%m-%d}"), ("i_datetime_to", f"{d:%Y-%m-%d}")]
    data = json.loads(fetch("https://port.hu/tvapi?" + urllib.parse.urlencode(q)))
    out = {}
    for block in data.values():
        for ch in block.get("channels", []):
            evs = out.setdefault(ch["id"], [])
            for p in ch.get("programs", []):
                start = datetime.fromisoformat(p["start_datetime"]).astimezone(BUD)
                desc = p.get("short_description") or ""
                cat = (p.get("restriction") or {}).get("category") or ""
                url = p.get("film_url") or ""
                if "/sorozat/" in url or cat == "filmsorozat":
                    desc = (desc + " sorozat").strip()
                evs.append({
                    "start": start.isoformat(),
                    "title": p.get("title", "").strip(),
                    "desc": desc,
                    "url": "https://port.hu" + url if url else "",
                    "channel_name": ch["id"],
                })
    return out
