"""Rebuild src/help.idx from src/help.txt.

Usage:
    python tools/build_help_idx.py

src/help.txt is the canonical help source -- edit it directly, then run
this to rebuild the index (any edit shifts byte offsets). Format:

    #<level>|<category>|<keywords>
    <text line>
    ...

Flush-left body lines form reflowable paragraphs. Blank lines separate
paragraphs; indentation and ``Syntax:`` preserve source line breaks. Wrap
flush-left tables or ASCII art in ``.nf``/``.fi`` marker lines.

Writes '<level>|<category>|<offset>|<keywords>' per entry, where offset is
the byte offset of the entry's first text line in help.txt (LF line endings
-- .gitattributes marks both files -text so git never normalizes them).
do_help and do_index scan this index instead of the full ~150KB file.

Originally part of tools/help_to_primesud.py, the one-shot converter
from 1stMud help.dat (see git history).
"""

import sys
from pathlib import Path

SRC = Path("src/help.txt")
IDX = Path("src/help.idx")


def main():
    pos = 0
    idx_lines = []
    lineno = 0
    with open(SRC, "rb") as f:
        for line in f:
            lineno += 1
            pos += len(line)
            assert not line.rstrip(b"\n").endswith(b"\r"), "CRLF in help.txt"
            if lineno == 1:
                if not line.startswith(b"# "):
                    sys.exit("Line 1 must be the '# ' header comment")
                continue
            if line.startswith(b"#"):
                # Must be a '#<level>|<category>|<keywords>' marker: do_help
                # ends an entry body at any '#' line, so '#' text lines (or
                # stray '# ' comments past line 1) would truncate entries.
                try:
                    level_s, category, kw = line[1:].rstrip(b"\n").split(b"|", 2)
                    int(level_s)
                except ValueError:
                    sys.exit("Line %d: expected '#<level>|<category>|<keywords>'"
                             " marker, got %r" % (lineno, line))
                if not category:
                    sys.exit("Line %d: empty help category" % lineno)
                idx_lines.append(level_s + b"|" + category + b"|" +
                                 b"%d" % pos + b"|" + kw)
    IDX.write_bytes(b"\n".join(idx_lines) + b"\n")
    print("Wrote %s: %d entries" % (IDX, len(idx_lines)))


if __name__ == "__main__":
    main()
