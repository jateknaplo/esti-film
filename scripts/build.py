"""Esti film: musor.tv (+ port.hu) műsor -> filmek -> IMDb pont -> site/index.html.

Futtatás:  python scripts/build.py            (élő lekérés)
           python scripts/build.py --offline  (csak a cache-ből)
Környezet: TMDB_API_KEY (v3 kulcs vagy v4 token; nélküle csak az IMDb-címindex párosít)
"""
import argparse
import csv
import difflib
import gzip
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imdb_data  # noqa: E402
import musortv  # noqa: E402
import porthu  # noqa: E402
import render  # noqa: E402
from musortv import BUD  # noqa: E402
from textnorm import loose, norm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

MIN_VOTES = 500        # ennél kevesebb szavazatnál a pontszám nem számít "jónak"
NEG_RETRY_DAYS = 7     # sikertelen párosítást ennyi nap múlva próbálunk újra
WEEK_DAYS = 7


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load_consts(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["Const"].strip() for r in csv.DictReader(f) if r.get("Const")}


# ---------------------------------------------------------------- műsor

def fetch_schedules(channels, today, offline, log):
    """{kód: [esemény]} -- a napi oldalak cache/schedule/<kód>/<nap>.json-ban."""
    errors = []
    plan = []  # (csatorna, nap)
    for ch in channels:
        days = 1 if ch["group"] == "kizart" else WEEK_DAYS
        plan += [(ch, today + timedelta(days=i)) for i in range(days)]

    def cpath(ch, d):
        return P("cache", "schedule", ch["kod"], f"{d:%Y-%m-%d}.json")

    def stale(ch, d):
        c = load_json(cpath(ch, d), None)
        if c is None:
            return True
        age = time.time() - c["fetched"]
        limit = 1800 if d == today else 6 * 3600 if d == today + timedelta(days=1) else 20 * 3600
        return age > limit

    failed = []
    streak = 0  # egymás utáni hibák: 5 után a musor.tv-t erre a futásra feladjuk
    for ch, d in plan:
        if offline or not stale(ch, d):
            continue
        if streak >= 5:
            failed.append((ch, d, "musor.tv nem elérhető"))
            continue
        url = musortv.day_url(ch["kod"], d, today)
        try:
            evs = musortv.parse(musortv.fetch(url, tries=2))
            if not evs:
                raise ValueError("üres műsor")
            save_json(cpath(ch, d), {"fetched": time.time(), "src": "musor.tv", "events": evs})
            log(f"  {ch['kod']} {d:%m.%d} {len(evs)} műsor")
            streak = 0
        except Exception as e:
            log(f"  {ch['kod']} {d:%m.%d} HIBA: {e}")
            failed.append((ch, d, str(e)))
            streak += 1

    # tartalék: port.hu, naponta egy kérés az összes hiányzó csatornára
    by_day = {}
    for ch, d, err in failed:
        by_day.setdefault(d, []).append((ch, err))
    for d, items in sorted(by_day.items()):
        ids = [ch["port"] for ch, _ in items if ch.get("port")]
        got = {}
        if ids:
            try:
                got = porthu.day(ids, d)
            except Exception as e:
                log(f"  port.hu {d:%m.%d} HIBA: {e}")
        for ch, err in items:
            evs = got.get(ch.get("port"), [])
            if evs:
                save_json(cpath(ch, d), {"fetched": time.time(), "src": "port.hu", "events": evs})
                errors.append({"ch": ch["nev"], "day": d.isoformat(), "msg": "musor.tv hiba, port.hu-ról pótolva"})
            elif os.path.exists(cpath(ch, d)):
                errors.append({"ch": ch["nev"], "day": d.isoformat(), "msg": "nem sikerült frissíteni, régebbi adat"})
            else:
                errors.append({"ch": ch["nev"], "day": d.isoformat(), "msg": "nincs adat (musor.tv és port.hu sem)"})

    out = {}
    for ch, d in plan:
        c = load_json(cpath(ch, d), None)
        if c is None:
            if offline:
                errors.append({"ch": ch["nev"], "day": d.isoformat(), "msg": "nincs adat a cache-ben"})
            continue
        seen = {e["start"] for e in out.get(ch["kod"], [])}
        out.setdefault(ch["kod"], []).extend(e for e in c["events"] if e["start"] not in seen)
    # régi napok törlése
    sched = P("cache", "schedule")
    for code in os.listdir(sched) if os.path.isdir(sched) else []:
        for fn in os.listdir(os.path.join(sched, code)):
            if fn[:10] < f"{today - timedelta(days=1):%Y-%m-%d}":
                os.remove(os.path.join(sched, code, fn))
    return out, errors


# ---------------------------------------------------------------- film-e

BAD = re.compile(r"sorozat|műsor|show|reality|híradó|hírek|magazin|vetélked|stand ?up|talk|"
                 r"telenovella|\brész\b|közvetítés|sport|kvíz|riport|valóság", re.I)
EPISODE = re.compile(r"\b[IVXLC]+\.\s*/\s*\d+|\d+\.\s*/\s*\d+|\b\d+\.\s*rész")
GOOD = re.compile(r"film|vígjáték|thriller|western|dráma|krimi|akció|horror|animációs|mese|kaland|"
                  r"sci-fi|fantasy|romantikus|musical|háborús|életrajzi|történelmi|családi|misztikus|"
                  r"katasztrófa|paródia|szatíra|noir|szörny|music|komédia", re.I)
KID = re.compile(r"animációs|családi|mese|rajzfilm|bábfilm", re.I)
NOT_FILM_TITLE = re.compile(r"^(labdarúgás|tenisz|snooker|forma[- ]1|műsorszünet|képújság)", re.I)


def classify(ev):
    """(True/False/None, év) -- None = bizonytalan, a párosítás típusa dönt."""
    desc, title = ev["desc"], ev["title"]
    if BAD.search(desc) or EPISODE.search(title) or EPISODE.search(desc) or NOT_FILM_TITLE.search(title):
        return False, None
    if re.search(r"\d{4}\s*[-–]\s*\d{4}", desc):
        return False, None
    years = re.findall(r"\b(18[89]\d|19\d\d|20\d\d)\b", desc)
    if not years:
        return False, None
    year = int(years[-1])
    genre = desc[: desc.rfind(years[-1])]
    if GOOD.search(genre):
        return True, year
    return None, year


# ---------------------------------------------------------------- párosítás

class Matcher:
    def __init__(self, log, offline):
        self.log = log
        self.offline = offline
        self.cache = load_json(P("cache", "matches.json"), {})
        self.manual = {self._mkey(k): v for k, v in load_json(P("config", "manual_matches.json"), {}).items()
                       if not k.startswith("_")}
        self.key = os.environ.get("TMDB_API_KEY", "").strip()
        self.index = None
        self.tmdb_calls = 0
        self.tmdb_dead = False

    @staticmethod
    def _mkey(k):
        t, _, y = k.rpartition("|") if "|" in k else (k, "", "")
        return f"{norm(t)}|{y.strip()}" if y.strip().isdigit() else norm(k)

    def _index(self):
        if self.index is None:
            path = P("cache", "hu_index.json.gz")
            if os.path.exists(path):
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    self.index = json.load(f)
            else:
                self.index = {}
            self.loose = {}
            for k, lst in self.index.items():
                self.loose.setdefault(loose(k), []).extend(lst)
        return self.index

    @staticmethod
    def variants(title):
        v = [title]
        for sep in (" - ", ": ", " – "):
            if sep in title:
                v.append(title.split(sep)[0])
                v.append(title.split(sep, 1)[1])
        v.append(re.sub(r"\s*\(.*?\)", "", title))
        out = []
        for x in v:
            n = norm(x)
            if n and n not in out:
                out.append(n)
        return out

    # --- TMDb
    def _tmdb(self, path, **params):
        if self.tmdb_dead:
            return None
        headers = {"Accept": "application/json"}
        if self.key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + self.key
        else:
            params["api_key"] = self.key
        url = "https://api.themoviedb.org/3" + path + "?" + urllib.parse.urlencode(params)
        for attempt in range(3):
            try:
                time.sleep(0.12)
                self.tmdb_calls += 1
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(3)
                    continue
                if e.code == 401:
                    self.log("  TMDb: érvénytelen kulcs, TMDb kikapcsolva")
                    self.tmdb_dead = True
                    return None
                return None
            except Exception:
                time.sleep(2)
        return None

    def _tmdb_match(self, title, year):
        for q in [title] + [v for v in re.split(r" - |: ", title)[:1] if v != title]:
            nq = norm(q)
            for params in ({"primary_release_year": year}, {"year": year}, {}):
                res = self._tmdb("/search/movie", query=q, language="hu-HU", include_adult="false", **params)
                if res is None:
                    return None
                best = None
                for r in res.get("results", [])[:10]:
                    ry = int(r["release_date"][:4]) if r.get("release_date", "")[:4].isdigit() else None
                    if ry is None or abs(ry - year) > 1:
                        continue
                    names = {norm(r.get("title", "")), norm(r.get("original_title", ""))}
                    sim = max(difflib.SequenceMatcher(None, nq, n).ratio() for n in names)
                    score = (nq in names, sim, ry == year, r.get("vote_count", 0))
                    if (nq in names or sim >= 0.85) and (best is None or score > best[0]):
                        best = (score, r, ry)
                if best:
                    r = best[1]
                    ext = self._tmdb(f"/movie/{r['id']}/external_ids") or {}
                    if ext.get("imdb_id"):
                        return {"imdb": ext["imdb_id"], "orig": r.get("original_title"), "y": best[2],
                                "kind": "movie", "src": "tmdb"}
            # nem film? -- sorozat
            res = self._tmdb("/search/tv", query=q, language="hu-HU") or {}
            for r in res.get("results", [])[:5]:
                if nq in {norm(r.get("name", "")), norm(r.get("original_name", ""))}:
                    return {"imdb": None, "kind": "tv", "src": "tmdb"}
        return {"imdb": None, "src": "tmdb"}

    def _index_match(self, title, year, ratings):
        """Pontos cím, majd sorrend- és számfüggetlen cím (év ±1), végül a teljes cím év ±4-gyel."""
        idx = self._index()
        vs = self.variants(title)
        for tol, table, keys in ((1, idx, vs), (1, self.loose, [loose(v) for v in vs]), (4, idx, vs[:1])):
            for v in keys:
                cands = [c for c in table.get(v, []) if c[1] and abs(c[1] - year) <= tol]
                if cands:
                    cands.sort(key=lambda c: (-abs(c[1] - year), c[2] == "movie",
                                              ratings.get(c[0], (0, 0))[1]), reverse=True)
                    c = cands[0]
                    return {"imdb": c[0], "orig": c[3], "y": c[1], "kind": "movie", "src": "index"}
        return {"imdb": None, "src": "index"}

    def match(self, title, year, ratings):
        k = f"{norm(title)}|{year}"
        if k in self.manual or norm(title) in self.manual:
            tt = self.manual.get(k, self.manual.get(norm(title)))
            return {"imdb": tt if tt and tt.startswith("tt") else None, "src": "manual", "kind": "movie" if tt else None}
        today = date.today().isoformat()
        c = self.cache.get(k)
        retry_tmdb = self.key and not self.tmdb_dead and c and c.get("src") == "index" and not c.get("tmdb_tried")
        fresh = c and (c.get("imdb") or c.get("kind") == "tv" or
                       (date.fromisoformat(c["ts"]) > date.today() - timedelta(days=NEG_RETRY_DAYS)))
        if c and fresh and not retry_tmdb:
            return c
        if self.offline and c:
            return c
        m = None
        if self.key and not self.offline and not self.tmdb_dead:
            m = self._tmdb_match(title, year)
        if m is None or (not m.get("imdb") and m.get("kind") != "tv"):
            im = self._index_match(title, year, ratings)
            if im.get("imdb"):
                im["tmdb_tried"] = bool(self.key and not self.tmdb_dead)
                m = im
            elif m is None:
                m = im
        m["ts"] = today
        self.cache[k] = m
        return m

    def save(self):
        save_json(P("cache", "matches.json"), self.cache)


# ---------------------------------------------------------------- tiltólista

def blocked_fn(cfg):
    chans = cfg.get("csatornak", {})
    films = []
    for f in cfg.get("filmek", []):
        if isinstance(f, str):
            code, _, title = f.partition("|")
            f = {"csatorna": code, "cim": title}
        films.append((f.get("csatorna", "").strip(), norm(f.get("cim", "")), f.get("datum"), f.get("ok", "")))

    def blocked(code, title, start):
        if code in chans:
            return chans[code] or "felvétel tiltva ezen a csatornán"
        nt = norm(title)
        for c, t, d, why in films:
            if c in (code, "*") and t == nt and (not d or start.startswith(d)):
                return why or "ez a film nem volt felvehető"
        return None
    return blocked


# ---------------------------------------------------------------- fő

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="nincs letöltés, csak cache")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    log = (lambda *x: None) if a.quiet else (lambda *x: print(*x, flush=True))

    now = datetime.now(BUD)
    today = now.date()
    ccfg = load_json(P("config", "channels.json"), {})
    channels = [dict(c, group="fo") for c in ccfg["fo"]]
    if ccfg.get("proba_aktiv", True):
        g = "proba" if ccfg.get("proba_kulon", True) else "fo"
        channels += [dict(c, group=g) for c in ccfg.get("proba", [])]
    channels += [dict(c, group="kizart") for c in ccfg.get("kizart", [])]
    by_code = {c["kod"]: c for c in channels}

    log("Műsor letöltése…")
    sched, errors = fetch_schedules(channels, today, a.offline, log)

    log("IMDb pontszámok…")
    try:
        ratings = imdb_data.load_ratings(P("work", "imdb")) if not a.offline or os.path.exists(
            P("work", "imdb", "title.ratings.tsv.gz")) else {}
    except Exception as e:
        ratings = {}
        errors.append({"ch": "IMDb", "day": today.isoformat(), "msg": f"pontszámfájl nem tölthető le: {e}"})
    watch = load_consts(P("data", "watchlist.csv"))
    seen = load_consts(P("data", "ratings.csv")) or set()
    blocked = blocked_fn(load_json(P("config", "felvetel_tiltott.json"), {}))

    log("Filmek párosítása…")
    matcher = Matcher(log, a.offline)
    films = []
    for code, evs in sched.items():
        ch = by_code[code]
        for ev in evs:
            start = datetime.fromisoformat(ev["start"])
            if start.date() < today or start.date() >= today + timedelta(days=WEEK_DAYS):
                continue
            is_film, year = classify(ev)
            if is_film is False:
                continue
            m = matcher.match(ev["title"], year, ratings)
            if is_film is None and m.get("kind") != "movie":
                continue
            tt = m.get("imdb")
            r = ratings.get(tt) if tt else None
            films.append({
                "code": code, "ch": ch["nev"], "group": ch["group"], "start": start,
                "title": ev["title"], "desc": ev["desc"], "year": year, "url": ev.get("url"),
                "imdb": tt, "orig": m.get("orig"), "rating": r[0] if r else None, "votes": r[1] if r else 0,
                "wl": bool(watch and tt in watch), "seen": tt in seen if tt else False,
                "blocked": blocked(code, ev["title"], ev["start"]),
                "kid": bool(KID.search(ev["desc"])),
            })
    matcher.save()
    log(f"  {len(films)} filmvetítés, TMDb-hívás: {matcher.tmdb_calls}")

    ctx = {
        "now": now, "today": today, "films": films, "errors": errors,
        "has_watchlist": watch is not None, "has_seen": bool(seen), "has_tmdb": bool(matcher.key),
        "min_votes": MIN_VOTES, "proba_kezdete": ccfg.get("proba_kezdete"),
        "proba_kulon": ccfg.get("proba_kulon", True) and ccfg.get("proba_aktiv", True),
        "watch_n": len(watch or ()),
    }
    os.makedirs(P("site"), exist_ok=True)
    with open(P("site", "index.html"), "w", encoding="utf-8") as f:
        f.write(render.page(ctx))
    for fn in os.listdir(P("static")):
        shutil.copy(P("static", fn), P("site", fn))
    log(f"Kész: site/index.html ({len(errors)} hibajelzés)")


if __name__ == "__main__":
    main()
