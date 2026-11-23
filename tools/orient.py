"""Checks a photograph's orientation against a star catalogue (needs numpy).

Given the sky position and size of a photo (from astrometry.net), it tries every rotation, with and without mirroring,
and counts how many catalogue stars (data/sky.json, magnitude 8 and brighter) land on a star in the picture.
"""
import json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
_stars = None


def stars():
    global _stars
    if _stars is None:
        s = json.loads((ROOT / "data" / "sky.json").read_text())["stars"]
        _stars = np.array([[a, b, m] for a, b, m, _ in s], dtype=float)
    return _stars


def detect(img, n=300, long_side=1000):
    """Bright star-like peaks of a picture, as pixel positions in a copy no larger than long_side."""
    im = img.convert("L")
    if max(im.size) > long_side:
        k = long_side / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    g = np.asarray(im, dtype=np.float32)
    hp = g - np.asarray(im.filter(ImageFilter.GaussianBlur(4)), dtype=np.float32)
    p = np.pad(hp, 2, constant_values=-1e9)
    mx = np.ones(hp.shape, dtype=bool)
    for dy in range(5):
        for dx in range(5):
            mx &= hp >= p[dy:dy + hp.shape[0], dx:dx + hp.shape[1]]
    mx &= hp > 6
    ys, xs = np.nonzero(mx)
    o = np.argsort(-hp[ys, xs])[:n]
    return np.c_[xs[o], ys[o]].astype(float), im.size


def _project(ra0, dec0, sel):
    r = math.pi / 180
    a, d, d0 = (sel[:, 0] - ra0) * r, sel[:, 1] * r, dec0 * r
    cosc = math.sin(d0) * np.sin(d) + math.cos(d0) * np.cos(d) * np.cos(a)
    ok = cosc > 0.01
    xi = np.cos(d) * np.sin(a) / cosc / r                                    # degrees towards east
    eta = (math.cos(d0) * np.sin(d) - math.sin(d0) * np.cos(d) * np.cos(a)) / cosc / r   # degrees towards north
    return xi[ok], eta[ok], sel[ok, 2]


def _pixels(xi, eta, alpha, mirror, s, cx, cy):
    """Where catalogue stars fall in a picture whose top edge points alpha degrees east of north.
    Not mirrored: the picture looks like the sky (north up, east left when alpha is 0). Mirrored: left and right swapped."""
    a = math.radians(alpha)
    up = xi * math.sin(a) + eta * math.cos(a)
    right = (xi * math.cos(a) - eta * math.sin(a)) if mirror else (-xi * math.cos(a) + eta * math.sin(a))
    return cx + s * right, cy - s * up


def verify(img, ra, dec, width_deg, stored_rot, height_deg=None):
    """Returns a dict describing how well each orientation fits, or None when the picture has too few stars."""
    peaks, (w, h) = detect(img)
    if len(peaks) < 20:
        return None
    s = w / width_deg
    hd = height_deg or width_deg * h / w
    st = stars()
    xi, eta, mag = _project(ra, dec, st[st[:, 2] <= 8.0])
    keep = np.hypot(xi, eta) < 0.55 * math.hypot(width_deg, hd)
    xi, eta, mag = xi[keep], eta[keep], mag[keep]
    wt, tol = 1 + (8 - mag) / 3, 0.006 * w

    def score(alpha, mirror):
        px, py = _pixels(xi, eta, alpha, mirror, s, w / 2, h / 2)
        ins = (abs(px - w / 2) < 0.485 * w) & (abs(py - h / 2) < 0.485 * h)
        if not ins.any():
            return 0.0, 0, 0
        d = np.hypot(px[ins, None] - peaks[None, :, 0], py[ins, None] - peaks[None, :, 1]).min(1)
        hit = d < tol
        return float((wt[ins] * np.exp(-0.5 * (d / tol) ** 2) * hit).sum()), int(hit.sum()), int(ins.sum())

    table = {(m, a): score(a, m) for m in (False, True) for a in range(360)}
    (bm, ba), best = max(table.items(), key=lambda kv: kv[1][0])
    for a in np.arange(ba - 1, ba + 1.01, 0.25):
        sc = score(a, bm)
        if sc[0] > best[0]:
            best, ba = sc, float(a)
    ba %= 360
    far = [v[0] for (m, a), v in table.items() if m != bm or min(abs(a - ba), 360 - abs(a - ba)) > 8]
    stored = max((score(a, False) for a in np.arange(stored_rot - 3, stored_rot + 3.01, 0.5)), key=lambda v: v[0])
    return dict(alpha=round(ba, 2), mirror=bm, score=best[0], hits=best[1], inside=best[2], second=max(far), stored_score=stored[0], stored_hits=stored[1])


def decide(r, stored_pa, stored_mirror=False):
    """'ok', 'fix' or 'unknown', plus a short explanation. stored_pa is the true angle of the picture's top edge, east of north."""
    if r is None:
        return "unknown", "too few stars found in the picture"
    if r["hits"] < 3 or r["score"] < 1.5 * max(r["second"], 0.5):
        return "unknown", f"not conclusive ({r['hits']} of {r['inside']} catalogue stars matched)"
    diff = min(abs(r["alpha"] - stored_pa) % 360, 360 - abs(r["alpha"] - stored_pa) % 360)
    if r["mirror"] == stored_mirror and diff < 4:
        return "ok", f"{r['hits']} of {r['inside']} catalogue stars match"
    return "fix", f"{r['hits']} of {r['inside']} catalogue stars match an angle of {r['alpha']}" + (", mirrored" if r["mirror"] else ", not mirrored")
