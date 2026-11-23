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
Needs: pip install requests pillow
"""
import argparse, json, math, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path
import requests
from PIL import Image, ImageOps

try:
    import orient  # needs numpy; double-checks orientation and mirroring against a star catalogue
except ImportError:
    orient = None

ROOT = Path(__file__).resolve().parent.parent
IMPORT = ROOT / "import"
API = "https://nova.astrometry.net/api"
FIELDS = ["id", "title", "designation", "date", "hint", "distance_ly", "object_type", "messier", "caldwell", "constellation",
          "location", "telescope", "exposure_seconds", "sub_exposure_seconds", "frames", "mosaic",
          "filters", "story", "story_credit", "ra", "dec", "width_deg", "rotation", "flip"]
NUMS = {"distance_ly": float, "exposure_seconds": float, "sub_exposure_seconds": float, "frames": int, "messier": int,
        "caldwell": int, "ra": float, "dec": float, "width_deg": float, "rotation": float}
TYPES = {"G": "Galaxy", "GPair": "Galaxy", "GTrpl": "Galaxy", "GGroup": "Galaxy", "PN": "Planetary nebula", "HII": "Emission nebula",
         "EmN": "Emission nebula", "RfN": "Reflection nebula", "DrkN": "Dark nebula", "Neb": "Nebula", "SNR": "Supernova remnant",
         "OCl": "Open cluster", "GCl": "Globular cluster", "Cl+N": "Emission nebula", "*Ass": "Asterism", "*": "Star",
         "**": "Double star", "Nova": "Nova"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "photo"


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


def add_photo(image, meta, key=None, max_size=2400, log=print, check=True):
    image = Path(image)
    m = {k: v for k, v in meta.items() if not blank(v)}
    if "story" not in m and "notes" in m:
        m["story"] = m["notes"]
    for k, f in NUMS.items():
        if k in m:
            m[k] = f(m[k])
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
    if check and orient is not None:   # does the picture's star pattern agree with the position and rotation from astrometry.net?
        try:
            r = orient.verify(im, ra, dec, width, width * im.height / im.width)
            verdict, why = orient.decide(r, (-rot) % 360, flip)
            if verdict == "ok":
                log(f"  Star check: orientation confirmed ({why}).")
            elif verdict == "fix" and r["mirror"] != flip and "flip" not in m:
                flip = r["mirror"]
                log(f"  Star check: this photo is {'a MIRROR IMAGE of the sky and will be shown flipped' if flip else 'not mirrored'} ({why}).")
            elif verdict == "fix":
                log(f"  WARNING: the star check disagrees with the rotation from astrometry.net ({why}). Look at the photo in the Cosmos tab; you can set rotation yourself.")
            else:
                log(f"  Star check: {why}; orientation not verified.")
        except Exception as e:
            log(f"  Star check skipped ({e})")
    elif check:
        log("  (Install numpy with 'pip install numpy' to let the script double-check orientation and mirroring against a star catalogue.)")
    obj, how = find_object([m.get("designation"), m.get("hint"), title], ra, dec, max(width, width * im.height / im.width))
    if obj:
        log(f"  Catalog match ({how}): {obj[0]}, {TYPES.get(obj[1], 'Other')}" + (f", Messier {obj[5]}" if obj[5] else "") + (f", Caldwell {obj[6]}" if obj[6] else ""))
        m.setdefault("object_type", TYPES.get(obj[1], "Other"))
        if obj[5]: m.setdefault("messier", obj[5])
        if obj[6]: m.setdefault("caldwell", obj[6])
    if "exposure_seconds" not in m and "sub_exposure_seconds" in m and "frames" in m:
        m["exposure_seconds"] = m["sub_exposure_seconds"] * m["frames"]
    m["date"] = m.get("date") or exif_date(orig)
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
        return {k.lower(): v for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    except ValueError as e:
        raise RuntimeError(f"{p.name} is not valid JSON ({e}). Check commas and quotes.")


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("image", nargs="?")
    a.add_argument("--all", action="store_true", help="add every photo in the import folder")
    a.add_argument("--template", metavar="NAME", help="create import/NAME.json to fill in")
    a.add_argument("--list", action="store_true"); a.add_argument("--remove", metavar="ID")
    a.add_argument("--remove-samples", action="store_true", help="remove all sample photographs (ids starting with sample-)")
    a.add_argument("--max-size", type=int, default=2400); a.add_argument("--push", action="store_true"); a.add_argument("--no-check", action="store_true", help="skip the star check")
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
            p.write_text(json.dumps({k: "" for k in FIELDS}, indent=2))
            return print(f"Created {p}. Fill in what you know and delete nothing: empty fields are ignored.")
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
                failed = 0
                for p in files:
                    print(f"{p.name}:")
                    try:
                        add_photo(p, {**sidecar(p), **cli}, key, o.max_size, check=not o.no_check)
                        for q in (p, p.with_suffix(".json")):
                            if q.exists():
                                shutil.move(str(q), str(IMPORT / "done" / q.name))
                    except (RuntimeError, OSError, requests.RequestException) as e:
                        failed += 1; print(f"  FAILED: {e}")
                print(f"Done. {len(files) - failed} added, {failed} failed. Finished photos were moved to import/done/.")
            else:
                if not o.image:
                    a.error("give a photo, or use --all, --template, --list or --remove")
                add_photo(o.image, {**sidecar(o.image), **cli}, key, o.max_size, check=not o.no_check)
        if o.push:
            for c in (["git", "add", "-A"], ["git", "commit", "-m", "Update photographs"], ["git", "push"]):
                subprocess.run(c, cwd=ROOT, check=True)
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
