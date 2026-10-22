"""IMDb nyilvános adatfájlok: pontszámok és egy magyar címindex (TMDb-tartalék)."""
import csv
import gzip
import json
import os
import sys
import time
import urllib.request

from textnorm import norm

BASE = "https://datasets.imdbws.com/"
FILM_TYPES = {"movie", "tvMovie", "video"}
csv.field_size_limit(10**7)


def download(name, dest_dir, max_age_h):
    path = os.path.join(dest_dir, name)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_h * 3600:
        return path
    os.makedirs(dest_dir, exist_ok=True)
    tmp = path + ".part"
    urllib.request.urlretrieve(BASE + name, tmp)
    os.replace(tmp, path)
    return path


def _rows(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(r)
        yield from r


def load_ratings(dest_dir):
    """tconst -> (pontszám, szavazatok)"""
    path = download("title.ratings.tsv.gz", dest_dir, 20)
    return {r[0]: (float(r[1]), int(r[2])) for r in _rows(path)}


def build_hu_index(dest_dir, out_path, min_votes_primary=300):
    """Normalizált cím -> [[tconst, év, típus], ...] filmekre.

    Magyar (region=HU) alternatív címek mind bekerülnek; az eredeti/elsődleges
    címek csak elég szavazattal, hogy a fájl kicsi maradjon."""
    ratings = load_ratings(dest_dir)
    basics = {}
    for r in _rows(download("title.basics.tsv.gz", dest_dir, 24 * 25)):
        if r[1] in FILM_TYPES and r[4] == "0":
            basics[r[0]] = (r[2], r[3], int(r[5]) if r[5].isdigit() else None, r[1])
    print("filmek:", len(basics), file=sys.stderr)
    idx = {}

    def add(title, t):
        k = norm(title)
        if not k:
            return
        b = basics[t]
        lst = idx.setdefault(k, [])
        if not any(x[0] == t for x in lst):
            lst.append([t, b[2], b[3], b[1]])

    for t, b in basics.items():
        if ratings.get(t, (0, 0))[1] >= min_votes_primary:
            add(b[0], t)
            add(b[1], t)
    for r in _rows(download("title.akas.tsv.gz", dest_dir, 24 * 25)):
        if r[3] == "HU" and r[0] in basics:
            add(r[2], r[0])
    print("indexkulcsok:", len(idx), file=sys.stderr)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    # python scripts/imdb_data.py [--if-older NAP]  -> cache/hu_index.json.gz (+ .date)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "cache", "hu_index.json.gz")
    stamp = out + ".date"
    if "--if-older" in sys.argv and os.path.exists(stamp):
        import datetime
        days = int(sys.argv[sys.argv.index("--if-older") + 1])
        built = datetime.date.fromisoformat(open(stamp).read().strip())
        if (datetime.date.today() - built).days < days:
            print("címindex friss:", built)
            sys.exit(0)
    build_hu_index(os.path.join(root, "work", "imdb"), out)
    import datetime
    with open(stamp, "w") as f:
        f.write(datetime.date.today().isoformat())
