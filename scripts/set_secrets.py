"""GitHub-titkok frissítése a helyi fájlokból: WATCHLIST_IDS (data/watchlist.csv) és TMDB_API_KEY.

A GitHub-hozzáférést a git hitelesítője adja (git credential fill). Kell hozzá: pip install pynacl
"""
import base64
import csv
import json
import os
import subprocess
import urllib.request

from nacl import encoding, public

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://api.github.com/repos/jateknaplo/esti-film"


def token():
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, check=True).stdout
    return next(l.split("=", 1)[1] for l in out.splitlines() if l.startswith("password="))


def api(tok, path, data=None, method=None):
    req = urllib.request.Request(REPO + path, data=json.dumps(data).encode() if data else None, method=method,
                                 headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read() or b"{}")


def main():
    tok = token()
    _, key = api(tok, "/actions/secrets/public-key")
    box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    values = {}
    wl = os.path.join(ROOT, "data", "watchlist.csv")
    if os.path.exists(wl):
        with open(wl, encoding="utf-8-sig", newline="") as f:
            values["WATCHLIST_IDS"] = " ".join(r["Const"].strip() for r in csv.DictReader(f) if r.get("Const"))
    kf = os.path.join(ROOT, "config", "tmdb_key.txt")
    if os.path.exists(kf):
        values["TMDB_API_KEY"] = open(kf).read().strip()
    for name, val in values.items():
        enc = base64.b64encode(box.encrypt(val.encode())).decode()
        st, _ = api(tok, f"/actions/secrets/{name}", {"encrypted_value": enc, "key_id": key["key_id"]}, "PUT")
        print(name, "beállítva" if st in (201, 204) else st, f"({len(val)} karakter)")


if __name__ == "__main__":
    main()
