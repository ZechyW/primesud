"""Rebuild src/help.idx from src/help.txt.

Usage:
    python tools/build_help_idx.py

src/help.txt is the canonical help source -- edit it directly, then run
this to rebuild the index (any edit shifts byte offsets). Format:

    #<level>|<keywords>
    <text line>
    ...

Writes '<level>|<offset>|<keywords>' per entry, where offset is the byte
offset of the entry's first text line in help.txt (LF line endings --
.gitattributes marks both files -text so git never normalizes them).
do_help scans this ~7KB index instead of the full ~150KB file, then
seeks straight to the matched entry.

Originally part of tools/help_to_primesud.py, the one-shot converter
from 1stMud help.dat (see git history).
"""

from pathlib import Path

SRC = Path("src/help.txt")
IDX = Path("src/help.idx")


def main():
    pos = 0
    idx_lines = []
    with open(SRC, "rb") as f:
        for line in f:
            pos += len(line)
            assert not line.rstrip(b"\n").endswith(b"\r"), "CRLF in help.txt"
            if line.startswith(b"# "):
                continue  # header comment, not an entry marker
            if line.startswith(b"#"):
                level_s, kw = line[1:].rstrip(b"\n").split(b"|", 1)
                idx_lines.append(level_s + b"|" + b"%d" % pos + b"|" + kw)
    IDX.write_bytes(b"\n".join(idx_lines) + b"\n")
    print("Wrote %s: %d entries" % (IDX, len(idx_lines)))


if __name__ == "__main__":
    main()
