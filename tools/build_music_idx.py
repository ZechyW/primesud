"""Rebuild src/music.idx from src/music.txt.

Usage:
    python tools/build_music_idx.py

src/music.txt is the canonical jukebox song source -- edit it directly,
then run this to rebuild the index (any edit shifts byte offsets). Format:

    #<name>|<group>|<lines>
    <lyric line>
    ...

Writes '<offset>|<length>|<lines>|<name>|<group>' per song, where offset is
the byte offset of the entry's first lyric line in music.txt and length
spans its <lines> lyric lines including newlines, so song_update/do_play
can do exactly one seek + one read(length) per song (cf. CLAUDE.md pitfall
7 -- never loop readline() at runtime). <lines> is carried through from the
marker so song_update's line-pointer bound check (cf. 1stMud
song_table[].lines) never needs a read just to learn a song's length.
LF line endings -- .gitattributes marks both files -text so git never
normalizes them. Songs stay in music.dat's original order (not sorted):
do_play's prefix match walks the table in that order, same as 1stMud's
top_song loop (cf. music.c do_play).

Originally converted from 1stMud data/music.dat via a throwaway script
(see git history / task notes -- not kept in tools/, per the
build_socials_idx.py precedent).
"""

import sys
from pathlib import Path

SRC = Path("src/music.txt")
IDX = Path("src/music.idx")


def main():
    idx_lines = []
    with open(SRC, "rb") as f:
        lines = f.readlines()
    for line in lines:
        assert not line.rstrip(b"\n").endswith(b"\r"), "CRLF in music.txt"

    assert lines and lines[0].startswith(b"# "), "missing header line"
    pos = len(lines[0])
    i = 1
    while i < len(lines):
        marker = lines[i]
        if not marker.startswith(b"#"):
            sys.exit("Line %d: expected '#<name>|<group>|<lines>' marker, got %r"
                      % (i + 1, marker))
        try:
            name, group, count_s = marker[1:].rstrip(b"\n").split(b"|", 2)
            count = int(count_s)
        except ValueError:
            sys.exit("Line %d: expected '#<name>|<group>|<lines>' marker, got %r"
                      % (i + 1, marker))
        pos += len(marker)
        body = lines[i + 1:i + 1 + count]
        if len(body) != count:
            sys.exit("%s: %d lyric lines, expected %d" % (name, len(body), count))
        length = sum(len(l) for l in body)
        idx_lines.append(str(pos) + "|" + str(length) + "|" + str(count) + "|"
                          + name.decode("ascii") + "|" + group.decode("ascii"))
        pos += length
        i += 1 + count

    data = "\n".join(idx_lines) + "\n"
    assert all(ord(c) < 128 for c in data), "non-ASCII index"
    IDX.write_bytes(data.encode("ascii"))
    print("Wrote %s: %d entries" % (IDX, len(idx_lines)))


if __name__ == "__main__":
    main()
