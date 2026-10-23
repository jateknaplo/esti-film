# Esti film

Telefonra szánt, magától frissülő oldal: **Ma este** (≈21:00-kor kezdődő filmek IMDb-ponttal, watchlist-jellel, felvehető jó filmekkel) és **Heti ajánló** (7 nap mesék / jó és még nem látott / watchlistes filmek, vetítésenként, a nem felvehetők ⚠️-vel).

## Hogyan működik

```
musor.tv napi oldalak  ─┐ (hiba esetén port.hu /tvapi JSON)
                        ├─> filmszűrés (műfajsor) ─> párosítás ─> IMDb-pont ─> site/index.html
TMDb (hu-HU) / IMDb címindex ┘                     title.ratings.tsv.gz
```

- `scripts/build.py` – a teljes futás (`--offline`: csak cache-ből).
- `scripts/musortv.py`, `scripts/porthu.py` – műsorforrások, csatornánként/naponként egy kérés, 1,2 s szünettel.
- `scripts/imdb_data.py` – IMDb-adatfájlok: pontszámok (naponta) és a magyar címindex `cache/hu_index.json.gz` (havonta; a TMDb tartaléka, kulcs nélkül is működik).
- `scripts/render.py` – a HTML.

Párosítás sorrendje: `config/manual_matches.json` → `cache/matches.json` → TMDb (ha van `TMDB_API_KEY`) → IMDb magyar címindex (pontos cím, majd alcím/sorszám nélkül, év ±1, végül év ±4). Sikertelen párosítás 7 nap múlva újra próbálkozik.

## Fájlok, amiket kézzel szerkesztesz

| Fájl | Mire |
|---|---|
| `data/watchlist.csv` | IMDb watchlist export (a `Const` oszlop számít) |
| `data/ratings.csv` | nem kötelező; IMDb értékelések exportja = látott filmek |
| `config/felvetel_tiltott.json` | nem felvehető csatornák / filmek |
| `config/manual_matches.json` | téves vagy hiányzó IMDb-párosítás javítása: `"Cím\|év": "tt…"`, `"-"` = nem film |
| `config/channels.json` | csatornák; `proba_aktiv` / `proba_kulon` kapcsolók a próba-csatornákhoz |

Szabályok: „jó” = IMDb ≥ 7,0 legalább 500 szavazattal (a kevés szavazatú pont zajos). „Ezt se hagyd ki” = kizárt csatorna, IMDb ≥ 7,5 vagy watchlist.

## Üzem

Cím: **https://esti-film.pages.dev/** (saját Cloudflare-fiók, `esti-film` Pages-projekt). Az oldal mind a 7 nap estéjét tartalmazza, a telefon dátuma szerint mutatja a mait.

### Gép nélkül: GitHub Actions → GitHub Pages (fő üzem)

Cím: **https://jateknaplo.github.io/esti-film/** (a régi esti-film.pages.dev ide irányít át).

`.github/workflows/build.yml`: naponta 07:00, 14:00, 19:00 (Budapest; a 6 UTC-cronból a „gate” job az aktuális időszámításnak megfelelőt engedi), plusz kézi indítás (Actions → Esti film → Run workflow). Lépései: címindex (havonta) → `build.py` → `cache/matches.json` visszaírása → GitHub Pages.

- Forrás: a GitHub szervereit a musor.tv 403-mal tiltja, ezért ott a port.hu az elsődleges (`ESTI_FORRAS=port`); a Canal+ Action nincs a port.hu-n.
- A repó publikus, a watchlist nincs benne: a `WATCHLIST_IDS` titkos változó a tt-azonosítókat tartalmazza. Frissítés: új CSV a `data/` mappába, majd `python scripts/set_secrets.py`.
- Titkos változók: `TMDB_API_KEY`, `WATCHLIST_IDS`.

### Saját gépről (tartalék)

- „Esti film” ütemezett feladat: 07:00, 14:00, 19:00; „Esti film (pótlás)”: bejelentkezéskor/feloldáskor, ha az oldal 3 óránál régebbi.
- `run.bat` = címindex → `build.py` → `wrangler pages deploy`. Napló: `logs/run.log`. Kézzel is indítható.
- Ha lejár a Cloudflare-belépés (a naplóban `DEPLOY HIBA`): `login.bat`, majd a böngészőben „Allow”.

## Helyi futtatás

```
pip install tzdata          # csak Windowson kell
python scripts/build.py
```
