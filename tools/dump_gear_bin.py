"""Dump src/gear.bin back to readable text for debugging.

Usage:

    python tools/dump_gear_bin.py [path/to/gear.bin]

One line per record in file order, pipe-separated, grouped under a slot
header. Layout knowledge lives in build_mob_index.parse_gear_index (the
schema SSOT), so this tool cannot drift from the builder.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_mob_index import APPDIR, parse_gear_index  # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        APPDIR, "gear.bin")
    with open(path, "rb") as f:
        slots, wtypes, tags = parse_gear_index(f.read())
    print("#", path, "-", sum(len(rows) for rows in slots.values()),
          "records,", len(wtypes), "weapon types,", len(tags), "area tags")
    print("# vnum|bound|item_level|static|wbase|wtype|sharp|weight|flags|"
          "kind|source_level|source_vnum|room|tag|price|name|source_name")
    for slot, rows in slots.items():
        print("== " + slot + " (" + str(len(rows)) + " rows, "
              + str(sum(1 for row in rows if row["loot"])) + " loot)")
        for row in rows:
            print("|".join(str(value) for value in (
                row["vnum"], row["bound"], row["level"], row["static"],
                row["wbase"], row["wtype"], int(row["sharp"]),
                row["weight"], ",".join(row["flags"]), row["kind"],
                row["source_level"], row["source_vnum"], row["room"],
                row["tag"], row["price"], row["name"],
                row["source_name"])))


if __name__ == "__main__":
    main()
