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

## Jelenlegi üzem: saját gép + Cloudflare Pages

- Cím: **https://esti-film.pages.dev/** (a saját Cloudflare-fiókon, `esti-film` Pages-projekt).
- A Windows ütemezett feladata (**„Esti film”**) naponta 14:00-kor és 19:00-kor futtatja a `run.bat`-ot, ablak nélkül. Ha a gép ki volt kapcsolva, bekapcsolás után pótolja a futást.
- `run.bat` = címindex (havonta) → `build.py` → `wrangler pages deploy`. Napló: `logs/run.log`. Kézzel is indítható dupla kattintással.
- Ha lejár a Cloudflare-belépés (a naplóban `DEPLOY HIBA`): `login.bat` dupla kattintással, majd a böngészőben „Allow”.

## Alternatíva: GitHub Actions (gép nélkül)

A `.github/workflows/build.yml` kész, de jelenleg nincs használatban. Gép nélküli futáshoz kell egy GitHub-fiók; a kitétel GitHub Pagesre megy (ingyen csak publikus repóval), vagy át lehet írni Cloudflare Pagesre (`CLOUDFLARE_API_TOKEN` secret), és akkor a repó maradhat privát.

### GitHub-beállítás (egyszer)

1. Új repó a GitHubon (Pageshez ingyenes fióknál **publikus** kell; a watchlist/ratings CSV is látszik majd benne).
2. `git remote add origin https://github.com/<fiók>/esti-film.git` és `git push -u origin main`
3. Settings → Pages → Source: **GitHub Actions**.
4. Settings → Secrets and variables → Actions → New repository secret: `TMDB_API_KEY` (themoviedb.org → Settings → API; v3 kulcs vagy v4 „Read Access Token” is jó).
5. Actions → Esti film → Run workflow. Az oldal címe: `https://<fiók>.github.io/esti-film/`
6. iPhone Safari → Megosztás → Főképernyőhöz adás.

Futás: naponta 14:00 és 19:00 (Budapest) – a workflow mind a négy UTC-időpontot elindítja, és csak az aktuális időszámításnak megfelelő fut tovább.

## Helyi futtatás

```
pip install tzdata          # csak Windowson kell
python scripts/build.py
```
