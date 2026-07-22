"""Import 1stMud help categories without changing PrimeSUD help text.

Usage:
    python tools/import_help_categories.py

Matches canonical PrimeSUD entries to 1stMud help.dat by level and exact
keywords, then changes only help.txt marker lines from
'#<level>|<keywords>' to '#<level>|<category>|<keywords>'. The script is
safe to rerun after the markers already contain categories.
"""

import hashlib
import re
import sys
from pathlib import Path


SRC = Path("reference/1stMud4.5.3/data/help.dat")
DST = Path("src/help.txt")
MAX_MORTAL_LEVEL = 51
CUSTOM_CATEGORIES = {
    (0, b"KEYS KEYPAD CALCULATOR"): b"commands",
    (0, b"PATH"): b"commands",
}
HEADER = (b"# Canonical help source: '#<level>|<category>|<keywords>' marker "
          b"line then text lines per entry, ASCII + LF only. Edit directly, "
          b"then run: python tools/build_help_idx.py\n")


def upstream_categories(raw):
    """Return mortal-visible {(level, keywords): category} from help.dat."""
    categories = {}
    for chunk in raw.split(b"#HELP")[1:]:
        chunk = chunk.split(b"#END", 1)[0]
        level_match = re.search(rb"^level[ \t]+(-?\d+)", chunk, re.M)
        keyword_match = re.search(
            rb"^keyword[ \t]+(.*?)~", chunk, re.M | re.S)
        category_match = re.search(
            rb"^category[ \t]+([^~\r\n]+)~\r?$", chunk, re.M)
        if not (level_match and keyword_match and category_match):
            sys.exit("Malformed upstream help record: %r" % chunk[:60])
        level = int(level_match.group(1))
        effective_level = -level - 1 if level < 0 else level
        if effective_level > MAX_MORTAL_LEVEL:
            continue
        keywords = keyword_match.group(1).replace(b"\r\n", b" ").strip()
        key = (level, keywords)
        if key in categories:
            sys.exit("Duplicate upstream help entry: %r" % (key,))
        categories[key] = category_match.group(1).strip()
    return categories


def add_categories(data, categories):
    """Return categorized help.txt bytes while preserving every body byte."""
    out = []
    used = set()
    custom = set()
    before_body = []
    after_body = []
    entries = 0
    for lineno, line in enumerate(data.splitlines(True), 1):
        if lineno == 1:
            if not line.startswith(b"# "):
                sys.exit("Line 1 must be the '# ' header comment")
            out.append(HEADER)
            continue
        if not line.startswith(b"#"):
            before_body.append(line)
            after_body.append(line)
            out.append(line)
            continue
        if not line.endswith(b"\n") or line.endswith(b"\r\n"):
            sys.exit("Line %d: help.txt must use LF endings" % lineno)
        fields = line[1:-1].split(b"|", 2)
        if len(fields) == 2:
            level_s, keywords = fields
        elif len(fields) == 3:
            level_s, _old_category, keywords = fields
        else:
            sys.exit("Line %d: malformed help marker" % lineno)
        try:
            key = (int(level_s), keywords)
        except ValueError:
            sys.exit("Line %d: non-integer help level" % lineno)
        category = categories.get(key)
        if category is not None:
            used.add(key)
        else:
            category = CUSTOM_CATEGORIES.get(key)
            if category is None:
                sys.exit("No category for PrimeSUD help entry: %r" % (key,))
            custom.add(key)
        out.append(b"#" + level_s + b"|" + category + b"|" + keywords + b"\n")
        entries += 1

    missing = set(categories) - used
    if missing:
        sys.exit("Upstream help entries missing from PrimeSUD: %r" %
                 (sorted(missing),))
    if custom != set(CUSTOM_CATEGORIES):
        sys.exit("PrimeSUD custom help entries missing: %r" %
                 (sorted(set(CUSTOM_CATEGORIES) - custom),))
    if before_body != after_body:
        sys.exit("Help body changed while importing categories")
    result = b"".join(out)
    digest = hashlib.sha256(b"".join(after_body)).hexdigest()
    return result, entries, len(used), len(custom), digest


def main():
    categories = upstream_categories(SRC.read_bytes())
    result, entries, imported, custom, digest = add_categories(
        DST.read_bytes(), categories)
    if any(byte >= 128 for byte in result):
        sys.exit("Non-ASCII byte in categorized help.txt")
    DST.write_bytes(result)
    print("Wrote %s: %d entries (%d upstream, %d PrimeSUD); bodies sha256 %s"
          % (DST, entries, imported, custom, digest))


if __name__ == "__main__":
    main()
