import re
import unicodedata

_ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6"}


def norm(s):
    """Címösszevetéshez: kisbetű, ékezet nélkül, írásjelek nélkül, '2.' = 'ii' = '2'."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s).split()
    s = [_ROMAN.get(w, w) for w in s]
    if s and s[0] in ("a", "az", "the"):
        s = s[1:]
    return " ".join(s)


def loose(n):
    """Normalizált címből sorrend- és számfüggetlen kulcs (alcím elöl/hátul, '3.' hiánya)."""
    return " ".join(sorted(w for w in n.split() if not w.isdigit() and w not in ("a", "az", "the", "and", "es")))
