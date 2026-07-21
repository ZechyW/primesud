"""Build mob-template and object-template keyword indices.

mobs.idx has one row per mob template. Metadata feeds mob counters without
loading areas; ordered spawn tags feed portal/nexus/gate/summon lookups.
Line order preserves _AREA_FILES priority, so ambiguous names still resolve
to the cheapest area load.

objs.idx (every object template) feeds `debug find` name->vnum lookups
across unloaded areas (debug.py). It lists all templates, not just reset
ones, because `debug load obj` can spawn any template.

Re-run after re-converting any area:

    python tools/build_mob_index.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = os.path.join(ROOT, "src")
sys.path.insert(0, APPDIR)
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world


def main():
    # Two passes: an M-reset may spawn a template defined in another file
    # (haon.are places arachnos-defined spiders in room 6134), so template
    # lookup must span all areas. The emitted tag stays the reset-owning
    # area -- that's the load that makes the instance exist.
    areas = []
    all_mobiles = {}
    home_tags = {}
    area_order = {}
    for order, (fname, tag, _name, _lo, _hi) in enumerate(world._AREA_FILES):
        ns = {}
        with open(os.path.join(APPDIR, fname)) as f:
            exec(f.read(), ns)
        areas.append((tag, ns))
        area_order[tag] = order
        for vnum, mob in ns["MOBILES"].items():
            all_mobiles[vnum] = mob
            home_tags[vnum] = tag
    spawn_tags = {}
    for tag, ns in areas:
        seen = set()
        for reset in ns.get("RESETS", ()):
            if reset[0] != "M" or reset[1] in seen:
                continue
            seen.add(reset[1])
            spawn_tags.setdefault(reset[1], []).append(tag)
    # Reset-backed mobs retain old cheapest-area ordering. Resetless templates
    # follow their defining area and remain visible to debug/counter listings.
    vnums = sorted(all_mobiles, key=lambda v: (
        area_order[(spawn_tags.get(v) or [home_tags[v]])[0]], v))
    lines = []
    for vnum in vnums:
        mob = all_mobiles[vnum]
        # Flatten whitespace: some source fields carry stray newlines.
        kw = " ".join(mob.get("keywords", "").split())
        short = " ".join(mob.get("short_descr", "").split())
        assert "|" not in kw, "pipe in keywords of mob %d" % vnum
        assert "|" not in short, "pipe in short_descr of mob %d" % vnum
        lines.append(str(vnum) + "|" + home_tags[vnum] + "|"
                     + str(mob.get("level", 0)) + "|" + kw + "|" + short
                     + "|" + ",".join(spawn_tags.get(vnum, ())))
    out_path = os.path.join(APPDIR, "mobs.idx")
    header = ("# vnum|home_tag|level|keywords|short_descr|spawn_tags per mob"
              " template -- built by tools/build_mob_index.py, do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header + "\n".join(lines) + "\n")
    print("Wrote", out_path, "-", len(lines), "mobs")

    obj_lines = []
    for tag, ns in areas:
        for vnum in sorted(ns.get("OBJECTS", {})):
            kw = " ".join(ns["OBJECTS"][vnum].get("keywords", "").split())
            assert "|" not in kw, "pipe in keywords of obj %d" % vnum
            if kw:
                obj_lines.append(tag + "|" + str(vnum) + "|" + kw)
    out_path = os.path.join(APPDIR, "objs.idx")
    header = ("# tag|vnum|keywords per object template, areas ascending by"
              " size -- built by tools/build_mob_index.py, do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header + "\n".join(obj_lines) + "\n")
    print("Wrote", out_path, "-", len(obj_lines), "objects")


if __name__ == "__main__":
    main()
