#!/usr/bin/env python3
"""Add photographs to the site: plate-solve with astrometry.net, resize, and update catalog.json.
See README.md for the full guide. Quick reference:

  python3 tools/add_photo.py --template m31        create import/m31.json to fill in
  python3 tools/add_photo.py --all                 add everything in import/ (photo.jpg + optional photo.json)
  python3 tools/add_photo.py photo.jpg [options]   add one photo (reads photo.json next to it if present)
  python3 tools/add_photo.py --list                show the ids in the catalog
  python3 tools/add_photo.py --remove ID           remove a photo
  python3 tools/add_photo.py --remove-samples      remove all sample photos
Add --push to commit and push to GitHub afterwards.
Add --check to also run the optional star check that looks for mirrored photos (needs numpy; see check_orientation.py).
Needs: pip install requests pillow
"""
import argparse, json, math, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import requests
from PIL import Image, ImageOps

import skycalc   # Moon and planet calculations (needs astronomy-engine only when a Moon or planet photo is added)

ROOT = Path(__file__).resolve().parent.parent
IMPORT = ROOT / "import"
API = "https://nova.astrometry.net/api"
FIELDS = ["id", "title", "category", "subject", "planet", "designation", "date", "time_local", "timezone", "hint", "distance_ly",
          "object_type", "messier", "caldwell", "constellation", "location", "telescope", "camera", "lens", "focal_length_mm",
          "f_number", "iso", "exposure_seconds", "sub_exposure_seconds", "frames", "mosaic", "filters", "software", "seeing",
          "direction", "story", "story_credit", "ra", "dec", "width_deg", "rotation", "flip"]
# values calculated for Moon and planet photos (you can override any of them in the JSON file)
CALC = ["datetime_utc", "phase", "illumination_percent", "moon_age_days", "moon_distance_km", "moon_angular_diameter_arcmin",
        "supermoon", "planet_distance_au", "planet_distance_million_km", "apparent_diameter_arcsec", "magnitude"]
CATEGORIES = {"deepsky": "deepsky", "deep sky": "deepsky", "deep-sky": "deepsky", "moon": "moon", "lunar": "moon",
              "planets": "planets", "planet": "planets", "planetary": "planets", "nightsky": "nightsky", "night sky": "nightsky",
              "night-sky": "nightsky", "startrails": "nightsky", "star trails": "nightsky", "star-trails": "nightsky"}
NUMS = {"distance_ly": float, "exposure_seconds": float, "sub_exposure_seconds": float, "frames": int, "messier": int,
        "caldwell": int, "ra": float, "dec": float, "width_deg": float, "rotation": float, "focal_length_mm": float,
        "f_number": float, "iso": int, "illumination_percent": float, "moon_age_days": float, "moon_distance_km": float,
        "moon_angular_diameter_arcmin": float, "planet_distance_au": float, "planet_distance_million_km": float,
        "apparent_diameter_arcsec": float, "magnitude": float}
TYPES = {"G": "Galaxy", "GPair": "Galaxy", "GTrpl": "Galaxy", "GGroup": "Galaxy", "PN": "Planetary nebula", "HII": "Emission nebula",
         "EmN": "Emission nebula", "RfN": "Reflection nebula", "DrkN": "Dark nebula", "Neb": "Nebula", "SNR": "Supernova remnant",
         "OCl": "Open cluster", "GCl": "Globular cluster", "Cl+N": "Emission nebula", "*Ass": "Asterism", "*": "Star",
         "**": "Double star", "Nova": "Nova"}


class SkipPhoto(Exception):
    """Raised when you choose to skip a photo so that you can review it first."""


def ask_mirror(why, mode="ask"):
    """What to do with a photo that looks like a mirror image of the sky: 'flip', 'decline' or 'skip'."""
    if mode in ("flip", "decline", "skip"):
        return mode
    if not sys.stdin.isatty():
        print("  This photo looks like a mirror image, and there is no keyboard to ask: skipping it for review.")
        return "skip"
    print(f"\n  This photo looks like a MIRROR IMAGE of the sky ({why}).")
    print('    [a] Show it flipped on the Cosmos tab (saves "flip": true)')
    print("    [b] Decline: show it as it is (it will not line up with the stars)")
    print("    [c] Skip this photo for now, so you can review it (it stays in the import folder)")
    while True:
        c = input("  Choose a, b or c: ").strip().lower()
        if c in ("a", "b", "c"):
            return {"a": "flip", "b": "decline", "c": "skip"}[c]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "photo"


def norm_category(c):
    k = str(c or "deepsky").strip().lower()
    if k not in CATEGORIES:
        raise RuntimeError(f"Unknown category '{c}'. Use deepsky, moon, planets or nightsky.")
    return CATEGORIES[k]


def canon(k):
    """JSON keys may carry a note after ' - ' (for example 'date - YYYY-MM-DD'); only the part before it is the field name."""
    return str(k).split(" - ")[0].strip().lower()


def exif_info(img):
    """Camera details the camera wrote into the JPEG (when your editing program kept them)."""
    out = {}
    try:
        ex = img.getexif()
        sub = ex.get_ifd(0x8769)
    except Exception:
        return out

    def num(v):
        try:
            return float(v)
        except Exception:
            return None
    make, model = str(ex.get(0x010F) or "").strip(), str(ex.get(0x0110) or "").strip()
    if model:
        out["camera"] = model if model.lower().startswith(make.lower()) else f"{make} {model}".strip()
    if str(sub.get(0xA434) or "").strip():
        out["lens"] = str(sub.get(0xA434)).strip()
    if num(sub.get(0x920A)):
        out["focal_length_mm"] = round(num(sub.get(0x920A)), 1)
    if num(sub.get(0x829D)):
        out["f_number"] = round(num(sub.get(0x829D)), 1)
    iso = sub.get(0x8827)
    iso = iso[0] if isinstance(iso, (tuple, list)) and iso else iso
    if iso:
        out["iso"] = int(iso)
    if num(sub.get(0x829A)):
        out["exposure"] = num(sub.get(0x829A))
    mt = re.match(r"(\d{4})[:-](\d\d)[:-](\d\d)[ T](\d\d:\d\d:\d\d)", str(sub.get(0x9003) or ""))   # capture time, not the editing time
    if mt:
        out["date"], out["time_local"] = f"{mt[1]}-{mt[2]}-{mt[3]}", mt[4]
    off = str(sub.get(0x9011) or "").strip()
    if re.match(r"^[+-]\d\d:\d\d$", off):
        out["timezone"] = off
    return out


def _tpl(*rows):
    return {(f"{k} - {note}" if note else k): v for k, note, v in rows}


_STORY = (("story", "text shown under Wiki; write \\n\\n for a new paragraph", ""),
          ("story_credit", "small credit line under the text, if it is not your own", ""))
_WHEN = (("date", "YYYY-MM-DD, the LOCAL date where you were; used for the calculations", ""),
         ("time_local", "HH:MM:SS, 24-hour LOCAL clock time; used for the calculations", ""),
         ("timezone", "IANA name such as America/New_York (best: handles daylight saving) or a UTC offset such as -05:00; used for the calculations", ""))
_GEAR = (("location", "place name, for example Williamstown, MA (not used for the calculations)", ""),
         ("telescope", "telescope or lens, free text", ""), ("camera", "free text", ""),
         ("focal_length_mm", "millimetres (with a barlow or reducer, the effective focal length)", ""),
         ("f_number", "number only: write 8 for f/8", ""), ("iso", "whole number", ""))
_SHOTS = (("sub_exposure_seconds", "ONE frame, in seconds; for 1/500 s write 0.002", ""),
          ("frames", "number of frames stacked, whole number", ""),
          ("exposure_seconds", "TOTAL exposure in seconds; optional, it is calculated from frames x sub_exposure_seconds", ""))


def template_for(category):
    if category == "moon":
        return _tpl(("_read_me", "", "Moon photo. The phase, illumination, age, distance and supermoon flag are CALCULATED from date, time_local and timezone "
                     "(they are the same wherever you stand, so location is not needed). Empty fields are ignored. To override a calculated value, add the key yourself "
                     "(phase, illumination_percent, moon_age_days, moon_distance_km, moon_angular_diameter_arcmin, supermoon). Needs: pip install astronomy-engine. "
                     "EXIF (camera, lens, ISO, aperture, shutter, time) is read from the JPEG when present and only fills fields you left empty."),
                    ("title", "name shown on the site, for example Waxing gibbous over the lake", ""),
                    ("id", "optional unique name: letters, numbers and dashes", ""), ("category", "moon", "moon"),
                    *_WHEN, *_GEAR, *_SHOTS, ("filters", "text or a list", ""), ("mosaic", "for example 2 x 2 panels", ""),
                    ("software", "processing software", ""), *_STORY)
    if category == "planets":
        return _tpl(("_read_me", "", "Planet photo. The distance, apparent size, illuminated percent, magnitude and constellation are CALCULATED from planet, date, time_local and timezone "
                     "(the same wherever you stand, so location is not needed). Empty fields are ignored. Needs: pip install astronomy-engine. Apparent size is the planet's disk without Saturn's rings."),
                    ("title", "name shown on the site, for example Jupiter with Io", ""),
                    ("id", "optional unique name: letters, numbers and dashes", ""), ("category", "planets", "planets"),
                    ("planet", "Mercury, Venus, Mars, Jupiter, Saturn, Uranus or Neptune; used for the calculations", ""),
                    *_WHEN, *_GEAR, *_SHOTS, ("filters", "for example RGB or IR-pass; text or a list", ""),
                    ("seeing", "free text, for example 3/5 or 1.8 arcsec", ""), ("software", "processing software", ""), *_STORY)
    if category == "nightsky":
        return _tpl(("_read_me", "", "Night-sky photo, including star trails. EXIF (camera, lens, focal length, aperture, ISO, shutter speed and capture time) is read from the JPEG when "
                     "present and only fills fields you left empty. For star trails made in StarStaX enter frames and sub_exposure_seconds; the total time is calculated unless you enter "
                     "exposure_seconds. Nothing is calculated from the sky and the photo is not placed on the Cosmos map."),
                    ("title", "name shown on the site", ""), ("id", "optional unique name: letters, numbers and dashes", ""),
                    ("category", "nightsky", "nightsky"),
                    ("subject", "what it shows: Star trails, Milky Way, Meteors, Aurora, Constellations, Landscape or Other", ""),
                    ("date", "YYYY-MM-DD, the LOCAL date where you were", ""), ("time_local", "HH:MM:SS, 24-hour local clock time when the exposure or sequence started", ""),
                    ("timezone", "IANA name such as America/New_York, or a UTC offset such as -05:00", ""),
                    ("location", "place name", ""), ("camera", "free text", ""), ("lens", "free text", ""),
                    ("focal_length_mm", "millimetres", ""), ("f_number", "number only: write 2.8 for f/2.8", ""), ("iso", "whole number", ""),
                    ("sub_exposure_seconds", "ONE frame, in seconds", ""), ("frames", "number of frames, whole number", ""),
                    ("exposure_seconds", "TOTAL time in seconds; optional, it is calculated from frames x sub_exposure_seconds", ""),
                    ("direction", "where the camera pointed, free text, for example North toward Polaris", ""),
                    ("software", "for example StarStaX", ""), *_STORY)
    return _tpl(("_read_me", "", "Deep-sky photo. Position, size and rotation come from astrometry.net, and the object type and Messier/Caldwell numbers from the object catalog. "
                 "Empty fields are ignored. The notes after ' - ' in the keys are ignored too."),
                ("title", "name shown on the site, for example Andromeda Galaxy", ""),
                ("id", "optional unique name: letters, numbers and dashes, for example m31-2025-10", ""), ("category", "deepsky", "deepsky"),
                ("designation", "catalog name, for example M31 or NGC 7000", ""),
                ("date", "YYYY-MM-DD, capture date", ""), ("distance_ly", "light years, plain number", ""),
                ("location", "place name", ""), ("telescope", "telescope and camera, free text", ""), ("filters", "text or a list", ""),
                ("exposure_seconds", "TOTAL exposure in seconds", ""), ("sub_exposure_seconds", "ONE frame, in seconds", ""),
                ("frames", "number of frames, whole number", ""), ("mosaic", "for example 2 x 2 panels", ""), *_STORY,
                ("hint", "object name that speeds up solving, for example M31", ""),
                ("object_type", "filled in automatically; type here to override", ""),
                ("messier", "number only; filled in automatically", ""), ("caldwell", "number only; filled in automatically", ""),
                ("constellation", "name, optional", ""),
                ("ra", "decimal degrees (J2000); only to skip astrometry.net", ""), ("dec", "decimal degrees (J2000); only to skip astrometry.net", ""),
                ("width_deg", "degrees, width of the picture on the sky; only to skip astrometry.net", ""),
                ("rotation", "degrees clockwise, as astrometry.net reports it; only to skip astrometry.net", ""),
                ("flip", "true or false; true shows a mirror-image photo flipped", ""))


def blank(v):
    return v is None or v == "" or v == [] or v == {}


def angsep(ra1, dec1, ra2, dec2):
    a, b, c, d = map(math.radians, (ra1, dec1, ra2, dec2))
    x = math.sin(b) * math.sin(d) + math.cos(b) * math.cos(d) * math.cos(a - c)
    return math.degrees(math.acos(max(-1, min(1, x))))


def find_object(texts, ra, dec, field):
    """Look up NGC/IC/Messier/Caldwell data (OpenNGC) by name in the texts, else by position near the image centre."""
    cat = json.loads((ROOT / "tools" / "catalog.json").read_text())
    kinds = {"messier": "m", "m": "m", "caldwell": "c", "c": "c", "ngc": "ngc", "ic": "ic"}
    for t in texts:
        for k, n in re.findall(r"\b(NGC|IC|Messier|Caldwell|M|C)\s*0*(\d{1,4})\b", t or "", re.I):
            k, n = kinds[k.lower()], int(n)
            for o in cat:
                if (k == "ngc" and o[0] == f"NGC {n}") or (k == "ic" and o[0] == f"IC {n}") or (k == "m" and o[5] == n) or (k == "c" and o[6] == n):
                    return o, "name"
    best = None
    for o in cat:
        if o[4] < 3 and not (o[5] or o[6]):
            continue
        sep = angsep(ra, dec, o[2], o[3])
        if sep <= 0.3 * field and (best is None or sep < best[0]):
            best = (sep, o)
    return (best[1], "position") if best else (None, None)


def resolve(name):
    r = requests.get("https://cds.unistra.fr/cgi-bin/nph-sesame/-oI/SNV?" + requests.utils.quote(name), timeout=30)
    m = re.search(r"%J\s+([\d.]+)\s+([+-][\d.]+)", r.text)
    return (float(m[1]), float(m[2])) if m else None


def exif_date(im):
    try:
        ex = im.getexif()
        v = ex.get_ifd(0x8769).get(36867) or ex.get(306)
        return str(v)[:10].replace(":", "-") if v else ""
    except Exception:
        return ""


def api_key():
    k = os.environ.get("ASTROMETRY_API_KEY")
    f = ROOT / "tools" / "api_key.txt"
    return k or (f.read_text().strip() if f.exists() else None)


def solve(path, key, hint, log):
    r = requests.post(f"{API}/login", data={"request-json": json.dumps({"apikey": key})}, timeout=60)
    r.raise_for_status()
    args = {"session": r.json()["session"], "publicly_visible": "n", "allow_commercial_use": "n", "allow_modifications": "n"}
    if hint:
        args.update(center_ra=hint[0], center_dec=hint[1], radius=15)
    with open(path, "rb") as fh:
        r = requests.post(f"{API}/upload", data={"request-json": json.dumps(args)}, files={"file": fh}, timeout=300)
    r.raise_for_status()
    subid = r.json()["subid"]
    log(f"  Submitted to astrometry.net (submission {subid}). Solving, this can take a few minutes...")
    for _ in range(180):
        time.sleep(5)
        jobs = requests.get(f"{API}/submissions/{subid}", timeout=60).json().get("jobs") or []
        job = next((j for j in jobs if j), None)
        if job:
            status = requests.get(f"{API}/jobs/{job}", timeout=60).json().get("status")
            if status == "success":
                break
            if status == "failure":
                raise RuntimeError("astrometry.net could not solve this image. Add a 'hint' object name, or set ra, dec and width_deg yourself.")
    else:
        raise RuntimeError("Timed out waiting for astrometry.net.")
    c = requests.get(f"{API}/jobs/{job}/calibration/", timeout=60).json()
    log(f"  Solved: RA {c['ra']:.4f}, Dec {c['dec']:.4f}, {c['pixscale']:.2f} arcsec/px, rotation {c['orientation']:.1f}, parity {c.get('parity')}")
    return c["ra"], c["dec"], c["pixscale"], c["orientation"], c.get("parity")


def add_other(image, m, category, max_size, log):
    """Moon, planet and night-sky photos: no plate solving, no place on the Cosmos map."""
    orig = Image.open(image)
    im = ImageOps.exif_transpose(orig).convert("RGB")
    title = m.get("title") or image.stem
    pid = slug(m.get("id") or title)
    if category in ("moon", "nightsky"):   # camera details the JPEG carries; they only fill what you left empty
        ex = exif_info(orig)
        for k in ("camera", "lens", "focal_length_mm", "f_number", "iso"):
            if k in ex:
                m.setdefault(k, ex[k])
        if "exposure" in ex:
            if m.get("frames", 1) > 1:
                m.setdefault("sub_exposure_seconds", ex["exposure"])
            else:
                m.setdefault("exposure_seconds", ex["exposure"])
        mine = skycalc.norm_date(m.get("date"))
        if "date" in ex and not mine:
            m["date"] = ex["date"]
        if not mine or mine == ex.get("date"):   # the camera's clock only helps when it is about the same day you named
            for k in ("time_local", "timezone"):
                if k in ex:
                    m.setdefault(k, ex[k])
    if "exposure_seconds" not in m and "sub_exposure_seconds" in m and "frames" in m:
        m["exposure_seconds"] = m["sub_exposure_seconds"] * m["frames"]
    iso_date = skycalc.norm_date(m.get("date"))
    if m.get("date") and not iso_date:
        log(f"  WARNING: could not read the date '{m['date']}'. Use YYYY-MM-DD.")
    m["date"] = iso_date or m.get("date")
    if category == "moon":
        m.setdefault("subject", "Moon")
    if category == "planets":
        name = str(m.pop("planet", None) or m.get("subject") or "").strip().title()
        if not name:
            raise RuntimeError("Planet photos need a planet name (Mercury, Venus, Mars, Jupiter, Saturn, Uranus or Neptune).")
        m["subject"] = name
    if iso_date and (category in ("moon", "planets") or m.get("time_local")):
        dt, notes = skycalc.to_utc(iso_date, m.get("time_local"), m.get("timezone"))
        for n in notes:
            log(f"  Note: {n}.")
        m["datetime_utc"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        if category in ("moon", "planets"):
            try:
                calc = skycalc.moon_info(dt) if category == "moon" else skycalc.planet_info(m["subject"], dt)
                for k, v in calc.items():
                    m.setdefault(k, v)
                log("  Calculated: " + ", ".join(f"{k} {v}" for k, v in calc.items() if k != "constellation") + f", in {calc.get('constellation', '?')}.")
            except ImportError:
                log("  Moon/planet calculations skipped: run 'pip install astronomy-engine' and import the photo again (or fill the values in by hand).")
    elif category in ("moon", "planets"):
        log("  No date given, so nothing could be calculated.")
    web = im.copy(); web.thumbnail((max_size, max_size))
    thumb = im.copy(); thumb.thumbnail((400, 400))
    (ROOT / "photos" / "thumbs").mkdir(parents=True, exist_ok=True)
    web.save(ROOT / "photos" / f"{pid}.jpg", quality=88, optimize=True, progressive=True)
    thumb.save(ROOT / "photos" / "thumbs" / f"{pid}.jpg", quality=82, optimize=True)
    entry = {"id": pid, "title": title, "category": category}
    for k in FIELDS + CALC:
        if k not in ("id", "title", "category", "planet", "hint", "ra", "dec", "width_deg", "rotation", "flip") and not blank(m.get(k)):
            entry[k] = m[k]
    entry.update(v=int(time.time()), image=f"photos/{pid}.jpg", thumb=f"photos/thumbs/{pid}.jpg")
    cp = ROOT / "catalog.json"
    cat = [c for c in json.loads(cp.read_text()) if c["id"] != pid] + [entry]
    cp.write_text(json.dumps(cat, indent=1))
    log(f"  Added '{title}' ({category}, id {pid}), dated {entry.get('date') or 'unknown'}. The catalog has {len(cat)} photographs.")
    return entry


def add_photo(image, meta, key=None, max_size=2400, log=print, check=False, mirror="ask"):
    image = Path(image)
    m = {k: v for k, v in meta.items() if not blank(v)}
    if "story" not in m and "notes" in m:
        m["story"] = m["notes"]
    for k, f in NUMS.items():
        if k in m:
            m[k] = f(m[k])
    category = norm_category(m.get("category"))
    m["category"] = category
    if category != "deepsky":
        return add_other(image, m, category, max_size, log)
    orig = Image.open(image)
    im = ImageOps.exif_transpose(orig).convert("RGB")  # saving without EXIF also strips GPS data
    title = m.get("title") or m.get("designation") or image.stem
    pid = slug(m.get("id") or title)
    web = im.copy(); web.thumbnail((max_size, max_size))   # thumbnail() only shrinks, never enlarges
    thumb = im.copy(); thumb.thumbnail((400, 400))
    if all(k in m for k in ("ra", "dec", "width_deg")):
        ra, dec, width, rot = m["ra"], m["dec"], m["width_deg"], m.get("rotation", 0.0)
    else:
        if not key:
            raise RuntimeError("No astrometry.net API key (see README), and no ra, dec and width_deg given.")
        small = im.copy(); small.thumbnail((2000, 2000))  # a 2000 px copy solves faster and is plenty
        name = m.get("hint") or m.get("designation")
        hint = None
        if name:
            try:
                hint = resolve(name)
            except Exception:
                hint = None
            log(f"  Position hint for '{name}': {hint}" if hint else f"  Could not look up '{name}'; solving without a hint.")
        with tempfile.TemporaryDirectory() as tmp:
            sp = Path(tmp) / "solve.jpg"; small.save(sp, quality=90)
            ra, dec, ps, rot, parity = solve(sp, key, hint, log)
        width = ps * small.width / 3600
    flip = str(m.get("flip", "")).lower() in ("1", "true", "yes")
    declined = str(m.get("flip", "")).lower() in ("0", "false", "no")   # "flip": false in the JSON file means you already decided
    if check:   # optional extra (--check): do the stars in the picture agree with the position and rotation from astrometry.net?
        try:
            import orient   # imported only here; needs numpy
        except ImportError:
            orient = None
            log("  Star check skipped: it needs numpy ('pip install numpy').")
        if orient is not None:
            try:
                r = orient.verify(im, ra, dec, width, width * im.height / im.width)
                verdict, why = orient.decide(r, (-rot) % 360, flip)
                if verdict == "ok":
                    log(f"  Star check: orientation confirmed ({why}).")
                elif verdict == "fix" and r["mirror"] != flip and "flip" not in m:
                    choice = ask_mirror(why, mirror)
                    if choice == "flip":
                        flip = True
                        log("  You chose: show it flipped on the Cosmos tab.")
                    elif choice == "decline":
                        declined = True
                        log("  You chose: show it as it is (it will not line up with the stars).")
                    else:
                        raise SkipPhoto("skipped so that you can review it")
                elif verdict == "fix":
                    log(f"  WARNING: the star check disagrees with the rotation from astrometry.net ({why}). Look at the photo in the Cosmos tab; you can set rotation yourself.")
                else:
                    log(f"  Star check: {why}; orientation not verified.")
            except SkipPhoto:
                raise
            except Exception as e:
                log(f"  Star check skipped ({e})")
    obj, how = find_object([m.get("designation"), m.get("hint"), title], ra, dec, max(width, width * im.height / im.width))
    if obj:
        log(f"  Catalog match ({how}): {obj[0]}, {TYPES.get(obj[1], 'Other')}" + (f", Messier {obj[5]}" if obj[5] else "") + (f", Caldwell {obj[6]}" if obj[6] else ""))
        m.setdefault("object_type", TYPES.get(obj[1], "Other"))
        if obj[5]: m.setdefault("messier", obj[5])
        if obj[6]: m.setdefault("caldwell", obj[6])
    if "exposure_seconds" not in m and "sub_exposure_seconds" in m and "frames" in m:
        m["exposure_seconds"] = m["sub_exposure_seconds"] * m["frames"]
    m["date"] = skycalc.norm_date(m.get("date")) or m.get("date") or exif_date(orig)   # always stored as YYYY-MM-DD
    (ROOT / "photos" / "thumbs").mkdir(parents=True, exist_ok=True)
    web.save(ROOT / "photos" / f"{pid}.jpg", quality=88, optimize=True, progressive=True)
    thumb.save(ROOT / "photos" / "thumbs" / f"{pid}.jpg", quality=82, optimize=True)
    entry = {"id": pid, "title": title}
    for k in FIELDS:
        if k not in ("id", "title", "hint", "ra", "dec", "width_deg", "rotation", "flip") and not blank(m.get(k)):
            entry[k] = m[k]
    entry.update(ra=round(ra, 4), dec=round(dec, 4), width_deg=round(width, 3), height_deg=round(width * web.height / web.width, 3),
                 rotation=round(rot, 2), v=int(time.time()), image=f"photos/{pid}.jpg", thumb=f"photos/thumbs/{pid}.jpg")
    if flip:
        entry["flip"] = True
    elif declined:
        entry["flip"] = False   # reviewed and declined: the page does not flip it, and the check tool will not ask again
    cp = ROOT / "catalog.json"
    cat = [c for c in json.loads(cp.read_text()) if c["id"] != pid] + [entry]
    cp.write_text(json.dumps(cat, indent=1))
    log(f"  Added '{title}' (id {pid}), dated {entry.get('date') or 'unknown'}. The catalog has {len(cat)} photographs.")
    return entry


def remove_photo(pid):
    cp = ROOT / "catalog.json"
    cat = json.loads(cp.read_text())
    e = next((c for c in cat if c["id"] == pid), None)
    if not e:
        raise RuntimeError(f"No photograph with id '{pid}'. Use --list to see the ids.")
    for f in (e.get("image"), e.get("thumb")):
        p = (ROOT / f).resolve() if f else None
        if p and (ROOT / "photos").resolve() in p.parents and p.exists():
            p.unlink()
    cp.write_text(json.dumps([c for c in cat if c["id"] != pid], indent=1))


def sidecar(image):
    p = Path(image).with_suffix(".json")
    if not p.exists():
        return {}
    try:
        return {canon(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not str(k).startswith("_")}
    except ValueError as e:
        raise RuntimeError(f"{p.name} is not valid JSON ({e}). Check commas and quotes.")


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("image", nargs="?")
    a.add_argument("--all", action="store_true", help="add every photo in the import folder")
    a.add_argument("--template", metavar="NAME", help="create import/NAME.json to fill in (with --category moon, planets or nightsky for those kinds)")
    a.add_argument("--list", action="store_true"); a.add_argument("--remove", metavar="ID")
    a.add_argument("--remove-samples", action="store_true", help="remove all sample photographs (ids starting with sample-)")
    a.add_argument("--max-size", type=int, default=2400); a.add_argument("--push", action="store_true"); a.add_argument("--check", action="store_true", help="run the optional star check that looks for mirrored photos (needs numpy)"); a.add_argument("--no-check", action="store_true", help=argparse.SUPPRESS)
    a.add_argument("--mirror", choices=["ask", "flip", "decline", "skip"], default="ask", help="what to do with a photo the star check finds mirrored (used with --check; default: ask)")
    a.add_argument("--notes", help=argparse.SUPPRESS)
    for f in FIELDS:
        a.add_argument("--" + f.replace("_", "-"), dest=f)
    o = a.parse_args()
    try:
        if o.list:
            for c in json.loads((ROOT / "catalog.json").read_text()):
                print(f"{c['id']:30} {c['title']}")
            return
        if o.template:
            IMPORT.mkdir(exist_ok=True)
            p = IMPORT / (slug(o.template) + ".json")
            p.write_text(json.dumps(template_for(norm_category(o.category)), indent=2, ensure_ascii=False), encoding="utf-8")
            return print(f"Created {p}. Fill in what you know and delete nothing: empty fields are ignored. (Add --category moon, planets or nightsky for the other kinds.)")
        if o.remove_samples:
            ids = [c["id"] for c in json.loads((ROOT / "catalog.json").read_text()) if c["id"].startswith("sample-")]
            for i in ids:
                remove_photo(i)
            print(f"Removed {len(ids)} sample photographs.")
        elif o.remove:
            remove_photo(o.remove); print(f"Removed '{o.remove}'.")
        else:
            cli = {k: getattr(o, k) for k in FIELDS + ["notes"] if getattr(o, k, None) is not None}
            key = api_key()
            if o.all:
                files = sorted(p for p in IMPORT.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) if IMPORT.exists() else []
                if not files:
                    sys.exit(f"No photos found in {IMPORT}.")
                (IMPORT / "done").mkdir(exist_ok=True)
                failed = skipped = 0
                for p in files:
                    print(f"{p.name}:")
                    try:
                        add_photo(p, {**sidecar(p), **cli}, key, o.max_size, check=o.check and not o.no_check, mirror=o.mirror)
                        for q in (p, p.with_suffix(".json")):
                            if q.exists():
                                shutil.move(str(q), str(IMPORT / "done" / q.name))
                    except SkipPhoto as e:
                        skipped += 1; print(f"  SKIPPED: {e}. It stays in import/.")
                    except (RuntimeError, OSError, requests.RequestException) as e:
                        failed += 1; print(f"  FAILED: {e}")
                print(f"Done. {len(files) - failed - skipped} added, {skipped} skipped for review, {failed} failed. Finished photos were moved to import/done/.")
            else:
                if not o.image:
                    a.error("give a photo, or use --all, --template, --list or --remove")
                try:
                    add_photo(o.image, {**sidecar(o.image), **cli}, key, o.max_size, check=o.check and not o.no_check, mirror=o.mirror)
                except SkipPhoto as e:
                    sys.exit(f"Skipped: {e}. Nothing was added.")
        if o.push:
            for c in (["git", "add", "-A"], ["git", "commit", "-m", "Update photographs"], ["git", "push"]):
                subprocess.run(c, cwd=ROOT, check=True)
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
