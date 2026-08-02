"""Dump src/mobs.bin or src/objs.bin back to readable text for debugging.

Usage:

    python tools/dump_key_bin.py [path/to/mobs.bin]

One line per record in file order, pipe-separated. Layout knowledge lives
in build_mob_index.parse_key_index (the schema SSOT), so this tool cannot
drift from the builder.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_mob_index import APPDIR, parse_key_index  # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        APPDIR, "mobs.bin")
    with open(path, "rb") as f:
        rows, tags = parse_key_index(f.read())
    print("#", path, "-", len(rows), "records,", len(tags), "area tags")
    print("# vnum|level|home|keywords|name|tags")
    for row in rows:
        print("|".join(str(value) for value in (
            row["vnum"], row["level"], row["home"], row["keywords"],
            row["name"], ",".join(row["tags"]))))


if __name__ == "__main__":
    main()
