#!/usr/bin/env python3
"""Checks the orientation of photographs already in catalog.json against a star catalogue (needs numpy: pip install numpy).

  python3 tools/check_orientation.py              report only
  python3 tools/check_orientation.py --fix        asks what to do with each photo that looks mirrored (flip / decline / skip)
  python3 tools/check_orientation.py --id heart   check one photo

Photos with few bright stars in the frame give "unknown": that is normal, and nothing is changed for them.
A photo you declined to flip is stored with "flip": false and is not asked about again.
"""
import argparse, json
from PIL import Image
import orient
from add_photo import ask_mirror


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--fix", action="store_true")
    a.add_argument("--id")
    o = a.parse_args()
    cp = orient.ROOT / "catalog.json"
    cat = json.loads(cp.read_text())
    changed = 0
    for e in cat:
        if o.id and e["id"] != o.id:
            continue
        p = orient.ROOT / e["image"].split("?")[0]
        if not p.exists():
            print(f"{e['id']:28} image file missing")
            continue
        r = orient.verify(Image.open(p).convert("RGB"), e["ra"], e["dec"], e["width_deg"], e.get("height_deg"))
        flip = bool(e.get("flip"))
        declined = e.get("flip") is False   # you decided earlier to leave it unflipped
        verdict, why = orient.decide(r, (-e.get("rotation", 0)) % 360, flip)
        note = ""
        if verdict == "fix" and r["mirror"] != flip:
            if declined and r["mirror"]:
                note = " -> looks mirrored; you declined flipping earlier (flip: false), so it is left alone"
            else:
                note = " -> looks mirrored" if r["mirror"] else " -> looks NOT mirrored"
                if o.fix:
                    choice = ask_mirror(why) if r["mirror"] else "unflip"
                    if choice == "flip":
                        e["flip"] = True; changed += 1; note += " (flipped)"
                    elif choice == "decline":
                        e["flip"] = False; changed += 1; note += " (declined, will not ask again)"
                    elif choice == "unflip":
                        e.pop("flip", None); changed += 1; note += " (flip removed)"
                    else:
                        note += " (skipped)"
        elif verdict == "fix":
            note = f" -> the stored rotation {e.get('rotation')} may be wrong; the stars suggest {(-r['alpha']) % 360:.1f}"
        print(f"{e['id']:28} {verdict:8} {why}{note}")
    if changed:
        cp.write_text(json.dumps(cat, indent=1))
        print(f"Updated {changed} photograph(s) in catalog.json.")


if __name__ == "__main__":
    main()
