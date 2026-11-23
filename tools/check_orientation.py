#!/usr/bin/env python3
"""Checks the orientation of photographs already in catalog.json against a star catalogue (needs numpy: pip install numpy).

  python3 tools/check_orientation.py              report only
  python3 tools/check_orientation.py --fix        mark mirrored photos with "flip": true (and remove it where it is wrong)
  python3 tools/check_orientation.py --id heart   check one photo

Photos with few bright stars in the frame give "unknown": that is normal, and nothing is changed for them.
"""
import argparse, json
from PIL import Image
import orient


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
        verdict, why = orient.decide(r, (-e.get("rotation", 0)) % 360, flip)
        note = ""
        if verdict == "fix":
            if r["mirror"] != flip:
                note = " -> mirrored" if r["mirror"] else " -> not mirrored"
                if o.fix:
                    if r["mirror"]:
                        e["flip"] = True
                    else:
                        e.pop("flip", None)
                    changed += 1
                    note += " (fixed)"
            else:
                note = f" -> the stored rotation {e.get('rotation')} may be wrong; the stars suggest {(-r['alpha']) % 360:.1f}"
        print(f"{e['id']:28} {verdict:8} {why}{note}")
    if changed:
        cp.write_text(json.dumps(cat, indent=1))
        print(f"Updated {changed} photograph(s) in catalog.json.")


if __name__ == "__main__":
    main()
