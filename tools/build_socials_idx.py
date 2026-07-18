"""Rebuild src/socials.idx from src/socials.txt.

Usage:
    python tools/build_socials_idx.py

src/socials.txt is the canonical socials source -- edit it directly,
then run this to rebuild the index (any edit shifts byte offsets).
Format: '#<name>' marker line, then exactly 7 text lines (char_no_arg,
others_no_arg, char_found, others_found, vict_found, char_auto,
others_auto; blank = unset field). Entries must stay sorted
case-insensitively by name -- find_social (src/socials.py) does an
alphabetical-prefix scan with early exit. Marker lines are dead bytes
at runtime: check_social seeks by socials.idx offset/length only.

Writes '<offset>|<length>|<name>' per social, where offset is the byte
offset of the entry's first text line in socials.txt and length spans
its 7 lines including newlines, so check_social can do exactly one
seek + one read(length). LF line endings -- .gitattributes marks both
files -text so git never normalizes them.

Originally part of tools/socials_to_primesud.py, the one-shot converter
from 1stMud social.dat (see git history).
"""

import sys
from pathlib import Path

SRC = Path("src/socials.txt")
IDX = Path("src/socials.idx")


def main():
    with open(SRC, "rb") as f:
        lines = f.readlines()
    for line in lines:
        assert not line.rstrip(b"\n").endswith(b"\r"), "CRLF in socials.txt"

    # Field text can itself start with '#' (conspire's others_auto is a
    # literal "# " upstream), so markers can't be found by prefix alone;
    # the fixed 7-line record length disambiguates: line 0 is the header,
    # then each entry is 1 marker line + exactly 7 data lines.
    assert lines and lines[0].startswith(b"# "), "missing header line"
    pos = len(lines[0])
    idx_lines = []
    prev_name = ""
    i = 1
    while i < len(lines):
        marker = lines[i]
        if not marker.startswith(b"#"):
            sys.exit("Line %d: expected '#<name>' marker, got %r"
                     % (i + 1, marker))
        name = marker[1:].rstrip(b"\n").decode("ascii")
        if name.lower() < prev_name.lower():
            sys.exit("Not sorted: %r after %r" % (name, prev_name))
        prev_name = name
        body = lines[i + 1:i + 8]
        if len(body) != 7:
            sys.exit("%s: %d lines, expected 7" % (name, len(body)))
        pos += len(marker)
        length = sum(len(l) for l in body)
        idx_lines.append("%d|%d|%s" % (pos, length, name))
        pos += length
        i += 8

    data = "\n".join(idx_lines) + "\n"
    assert all(ord(c) < 128 for c in data), "non-ASCII index"
    IDX.write_bytes(data.encode("ascii"))
    print("Wrote %s: %d entries" % (IDX, len(idx_lines)))


if __name__ == "__main__":
    main()
