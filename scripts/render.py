"""HTML-generálás (egyetlen statikus oldal, két füllel)."""
import html
import urllib.parse
from datetime import date, datetime, time, timedelta

from textnorm import norm

NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]
NAP3 = ["h", "k", "sze", "cs", "p", "szo", "v"]
HONAP = ["jan.", "febr.", "márc.", "ápr.", "máj.", "jún.", "júl.", "aug.", "szept.", "okt.", "nov.", "dec."]
e = lambda s: html.escape(str(s or ""), quote=True)


def good(f, ctx):
    return f["rating"] is not None and f["rating"] >= 7.0 and f["votes"] >= ctx["min_votes"]


def score(f):
    if f["rating"] is None:
        return '<td class="sc">' + search_link(f, "–") + "</td>"
    cls = "s3" if f["rating"] >= 7.5 else "s2" if f["rating"] >= 7.0 else "s1" if f["rating"] >= 6.0 else "s0"
    low = f' title="csak {f["votes"]} szavazat"' if f["votes"] < 500 else ""
    return f'<td class="sc {cls}"{low}>{f["rating"]:.1f}'.replace(".", ",") + "</td>"


def search_link(f, text):
    q = urllib.parse.quote(f"{f['title']} {f['year'] or ''}".strip())
    return f'<a class="nolink" href="https://www.imdb.com/find/?q={q}" title="nincs biztos IMDb-találat — keresés">{e(text)}</a>'


def film_cell(f, tags=""):
    if f["imdb"]:
        a = f'<a href="https://www.imdb.com/title/{e(f["imdb"])}/">{e(f["title"])}</a>'
    else:
        a = search_link(f, f["title"])
    sub = []
    if f["orig"] and norm(f["orig"]) != norm(f["title"]):
        sub.append(e(f["orig"]))
    if f["year"]:
        sub.append(str(f["year"]))
    genre = f["desc"].rsplit(",", 1)[0].strip() if f["desc"] else ""
    if genre and not genre.isdigit():
        sub.append(e(genre))
    return f'<td class="film">{a}{tags}<small>{" · ".join(sub)}</small></td>'


def chan(f):
    warn = f'<span class="warn" title="{e(f["blocked"])}">⚠️</span>' if f["blocked"] else ""
    return f'<td class="ch">{warn}{e(f["ch"])}</td>'


def wl(f):
    return '<td class="wl">✅</td>' if f["wl"] else '<td class="wl"></td>'


def table(rows, empty="Nincs ilyen film."):
    if not rows:
        return f'<p class="empty">{empty}</p>'
    head = '<tr><th>Idő</th><th>Csatorna</th><th>Film</th><th>IMDb</th><th>WL</th></tr>'
    body = "".join(
        f'<tr class="{"past" if f.get("_past") else ""}"><td class="t">{f["start"]:%H:%M}</td>{chan(f)}{film_cell(f)}{score(f)}{wl(f)}</tr>'
        for f in rows)
    return f'<table class="grid tonight"><thead>{head}</thead><tbody>{body}</tbody></table>'


def by_score(f):
    return (f["rating"] is None, -(f["rating"] or 0), f["start"])


def between(f, d, a, b):
    s = f["start"]
    return s.date() == d and a <= s.time() < b


def tonight(ctx):
    d, films = ctx["today"], ctx["films"]
    fo = [f for f in films if f["group"] == "fo"]
    main = sorted([f for f in fo if between(f, d, time(20, 30), time(21, 30, 1))], key=by_score)
    ids = {id(f) for f in main}
    rec = [f for f in fo if id(f) not in ids and between(f, d, time(17), time(23, 59, 59))
           and (good(f, ctx) or f["wl"])]
    rec.sort(key=lambda f: f["start"])
    proba = sorted([f for f in films if f["group"] == "proba" and between(f, d, time(17), time(23, 59, 59))],
                   key=lambda f: f["start"])
    kiz = sorted([f for f in films if f["group"] == "kizart" and between(f, d, time(17), time(23, 59, 59))
                  and ((f["rating"] or 0) >= 7.5 and f["votes"] >= ctx["min_votes"] or f["wl"])],
                 key=lambda f: f["start"])
    out = [f'<h2>{NAPOK[d.weekday()].capitalize()}, {HONAP[d.month - 1]} {d.day}. — 20:30 és 21:30 között</h2>',
           table(main),
           '<h2>Felvehető <span class="hint">17:00–24:00, IMDb ≥ 7,0 vagy watchlist</span></h2>',
           table(rec, "Ma este nincs más jó film.")]
    if ctx["proba_kulon"]:
        note = ""
        if ctx.get("proba_kezdete"):
            end = date.fromisoformat(ctx["proba_kezdete"]) + timedelta(days=14)
            note = (f'próba {end:%m.%d.}-ig' if d <= end else
                    'a 2 hét letelt — a config/channels.json-ban döntsd el: fő listába vagy ki')
        out += [f'<h2>Próba-csatornák <span class="hint">TV4, Story4, Prime · {note}</span></h2>',
                table(proba, "Ma este nincs film a próba-csatornákon.")]
    out += ['<h2>Ezt se hagyd ki <span class="hint">kizárt csatornák, IMDb ≥ 7,5 vagy watchlist</span></h2>',
            table(kiz, "Ma este nincs kivételes film a kizárt csatornákon.")]
    return "\n".join(out)


def week(ctx):
    now = ctx["now"]
    films = [f for f in ctx["films"] if f["group"] in ("fo", "proba") and f["start"] >= now - timedelta(minutes=10)]
    groups = {}
    for f in films:
        k = f["imdb"] or f"{norm(f['title'])}|{f['year']}"
        groups.setdefault(k, []).append(f)
    rows = []
    for k, shows in groups.items():
        f = shows[0]
        is_new = good(f, ctx) and not f["seen"]
        kid = any(s["kid"] for s in shows)
        if not (kid or is_new or f["wl"]):
            continue
        shows.sort(key=lambda s: (bool(s["blocked"]), s["start"]))
        rows.append((shows[0]["start"].date(), is_new, kid, shows))
    days = {}
    for r in rows:
        days.setdefault(r[0], []).append(r)
    out = ['<div class="chips" role="group" aria-label="Szűrés">'
           '<button data-f="all" class="on">Mind</button><button data-f="uj">⭐ Jó, nem láttam</button>'
           '<button data-f="kid">🧸 Mesék</button><button data-f="wl">✅ Watchlist</button></div>']
    if not ctx["has_seen"]:
        out.append('<p class="note">Nincs <code>data/ratings.csv</code>, ezért a „nem láttam” most minden ≥ 7,0-s filmet jelent.</p>')
    for d in sorted(days):
        lst = sorted(days[d], key=lambda r: (not r[1], r[3][0]["rating"] is None, -(r[3][0]["rating"] or 0)))
        out.append(f'<h2>{NAPOK[d.weekday()].capitalize()}, {HONAP[d.month - 1]} {d.day}.</h2>')
        out.append('<table class="grid week"><thead><tr><th>Film</th><th>IMDb</th><th>WL</th><th>Vetítések</th></tr></thead><tbody>')
        for _, is_new, kid, shows in lst:
            f = shows[0]
            cls = " ".join(c for c, on in (("uj", is_new), ("kid", kid), ("wl", f["wl"])) if on)
            tags = (' <span class="tag t-uj">⭐</span>' if is_new else "") + (' <span class="tag">🧸</span>' if kid else "")
            sh = "".join(
                f'<li class="{"blk" if s["blocked"] else ""}">'
                + (f'<span class="warn" title="{e(s["blocked"])}">⚠️</span>' if s["blocked"] else "")
                + f'{NAP3[s["start"].weekday()]} {s["start"]:%H:%M} <b>{e(s["ch"])}</b></li>'
                for s in shows)
            out.append(f'<tr class="{cls}">{film_cell(f, tags)}{score(f)}{wl(f)}<td class="shows"><ul>{sh}</ul></td></tr>')
        out.append("</tbody></table>")
    if not days:
        out.append('<p class="empty">A következő 7 napban nincs ajánlott film.</p>')
    return "\n".join(out)


def errors_box(ctx):
    errs = ctx["errors"]
    notes = []
    if not ctx["has_watchlist"]:
        notes.append("Nincs <code>data/watchlist.csv</code> — a WL oszlop üres.")
    if not ctx["has_tmdb"]:
        notes.append("Nincs TMDb-kulcs — csak az IMDb magyar címindexe párosít.")
    if not errs and not notes:
        return ""
    by = {}
    for x in errs:
        by.setdefault((x["ch"], x["msg"]), []).append(x["day"])
    items = [f'<li><b>{e(ch)}</b>: {e(msg)} ({", ".join(date.fromisoformat(d).strftime("%m.%d.") for d in sorted(days))})</li>'
             for (ch, msg), days in sorted(by.items())]
    items += [f"<li>{n}</li>" for n in notes]
    cls = "errors" if errs else "errors soft"
    return f'<details class="{cls}" {"open" if errs else ""}><summary>{len(errs)} lekérési hiba' \
           f'{" · " + str(len(notes)) + " megjegyzés" if notes else ""}</summary><ul>{"".join(items)}</ul></details>'


CSS = """
:root{--bg:#f6f4ef;--card:#fff;--fg:#1d1b18;--mut:#6f6a62;--line:#e4dfd5;--acc:#b5471b;--s3:#1d7a3a;--s2:#4f8a2a;--s1:#8a7a2a;--s0:#9a5a4a;--hl:#fff3d6;--chip:#ece7dc}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--card:#1d1c19;--fg:#ece8e0;--mut:#9a948a;--line:#2f2d29;--acc:#f08a5d;--s3:#5fd07e;--s2:#a5d65a;--s1:#d6c35a;--s0:#d08a7a;--hl:#3a2f17;--chip:#2a2824}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:0 0 40px}
header{position:sticky;top:0;z-index:5;background:var(--bg);padding:calc(env(safe-area-inset-top) + 8px) 12px 0;border-bottom:1px solid var(--line)}
.top{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
h1{font-size:18px;margin:0}.upd{color:var(--mut);font-size:12px}
nav{display:flex;gap:4px;margin-top:8px}
nav button{flex:1;border:0;background:none;color:var(--mut);font:inherit;font-weight:600;padding:8px 4px;border-bottom:3px solid transparent}
nav button.on{color:var(--fg);border-bottom-color:var(--acc)}
main{padding:0 8px;max-width:760px;margin:0 auto}
section{display:none}section.on{display:block}
h2{font-size:14px;margin:18px 4px 6px;font-weight:700}.hint{color:var(--mut);font-weight:400;font-size:12px}
table.grid{width:100%;border-collapse:collapse;background:var(--card);border-radius:8px;overflow:hidden;font-size:14px}
.grid th{text-align:left;font-size:11px;color:var(--mut);font-weight:600;padding:5px 6px;border-bottom:1px solid var(--line)}
.grid td{padding:6px;border-bottom:1px solid var(--line);vertical-align:top}
.grid tr:last-child td{border-bottom:0}
.t{font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:600}
.ch{color:var(--mut);font-size:12.5px;width:78px;line-height:1.2}
.film a{color:var(--fg);font-weight:600;text-decoration:none}.film a:active{color:var(--acc)}
.film small{display:block;color:var(--mut);font-size:11.5px;margin-top:1px}
a.nolink{color:inherit;text-decoration:none;border-bottom:1px dotted var(--mut)}
.sc{font-weight:700;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.s3{color:var(--s3)}.s2{color:var(--s2)}.s1{color:var(--s1)}.s0{color:var(--s0)}.sc a.nolink{color:var(--mut);border:0}
.wl{text-align:center;width:28px}
.warn{margin-right:3px;cursor:help}
.empty,.note{color:var(--mut);font-size:13px;margin:6px 4px}
.week tr.uj td{background:var(--hl)}
.tag{font-size:12px}
.shows ul{list-style:none;margin:0;padding:0;font-size:12.5px;white-space:nowrap}
.shows li.blk{color:var(--mut)}.shows b{font-weight:600}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:12px 4px 0}
.chips button{border:0;background:var(--chip);color:var(--fg);font:inherit;font-size:13px;padding:6px 10px;border-radius:16px}
.chips button.on{background:var(--acc);color:#fff}
.week.f-uj tr:not(.uj),.week.f-kid tr:not(.kid),.week.f-wl tr:not(.wl){display:none}
.week.f-uj thead tr,.week.f-kid thead tr,.week.f-wl thead tr{display:table-row}
details.errors{margin:8px 0 4px;font-size:12.5px;background:#fde3dc;color:#5a1d0e;border-radius:8px;padding:6px 10px}
details.errors.soft{background:var(--chip);color:var(--fg)}
@media (prefers-color-scheme:dark){details.errors{background:#4a1f14;color:#ffd9cc}}
details.errors ul{margin:4px 0;padding-left:18px}
code{font-size:12px}
@media (max-width:420px){.grid td{padding:5px 4px}.ch{width:68px}}
"""

JS = """
(function(){
var tabs=document.querySelectorAll('nav button'),secs=document.querySelectorAll('section');
function show(id){tabs.forEach(function(b){b.classList.toggle('on',b.dataset.t===id)});
secs.forEach(function(s){s.classList.toggle('on',s.id===id)});try{localStorage.setItem('tab',id)}catch(e){}}
tabs.forEach(function(b){b.onclick=function(){show(b.dataset.t);window.scrollTo(0,0)}});
var t=null;try{t=localStorage.getItem('tab')}catch(e){}
if(location.hash==='#het')t='het';show(t==='het'?'het':'ma');
var chips=document.querySelectorAll('.chips button');
chips.forEach(function(c){c.onclick=function(){chips.forEach(function(x){x.classList.toggle('on',x===c)});
document.querySelectorAll('table.week').forEach(function(tb){tb.classList.remove('f-uj','f-kid','f-wl');
if(c.dataset.f!=='all')tb.classList.add('f-'+c.dataset.f);
var vis=[].some.call(tb.tBodies[0].rows,function(r){return getComputedStyle(r).display!=='none'});
tb.style.display=vis?'':'none';tb.previousElementSibling.style.display=vis?'':'none'})}});
})();
"""


def page(ctx):
    now = ctx["now"]
    upd = f"Frissítve: {now:%Y.%m.%d. %H:%M}"
    return f"""<!doctype html>
<html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Esti film</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Esti film">
<meta name="theme-color" content="#f6f4ef" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#141311" media="(prefers-color-scheme: dark)">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" href="icon-192.png">
<link rel="manifest" href="manifest.json">
<style>{CSS}</style></head>
<body>
<header><div class="top"><h1>🎬 Esti film</h1><span class="upd">{upd}</span></div>
{errors_box(ctx)}
<nav><button data-t="ma" class="on">Ma este</button><button data-t="het">Heti ajánló</button></nav></header>
<main>
<section id="ma" class="on">
{tonight(ctx)}
</section>
<section id="het">
{week(ctx)}
</section>
</main>
<script>{JS}</script>
</body></html>
"""
