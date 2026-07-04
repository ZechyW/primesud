"""Build mob_index.dat: "tag|vnum|keywords" per line for every M-reset mob.

Feeds _find_unloaded_mob (magic.py) so portal/nexus/gate/summon can target
mobs in areas that are not loaded yet. Line order follows _AREA_FILES
(ascending size), so ambiguous names resolve to the cheapest area load.
Re-run after re-converting any area:

    python tools/build_mob_index.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = os.path.join(ROOT, "primesud.hpappdir")
sys.path.insert(0, APPDIR)
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world


def main():
    lines = []
    for fname, tag, _name, _lo, _hi in world._AREA_FILES:
        ns = {}
        with open(os.path.join(APPDIR, fname)) as f:
            exec(f.read(), ns)
        mobiles = ns["MOBILES"]
        seen = set()
        for reset in ns.get("RESETS", ()):
            if reset[0] != "M" or reset[1] in seen:
                continue
            seen.add(reset[1])
            # flatten whitespace: some source keywords carry stray newlines
            # (e.g. quest.are mob 202)
            kw = " ".join(mobiles.get(reset[1], {}).get("keywords", "").split())
            assert "|" not in kw, "pipe in keywords of mob %d" % reset[1]
            if kw:
                lines.append(tag + "|" + str(reset[1]) + "|" + kw)
    out_path = os.path.join(APPDIR, "mob_index.dat")
    with open(out_path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("Wrote", out_path, "-", len(lines), "mobs")


if __name__ == "__main__":
    main()
