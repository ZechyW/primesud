"""Convert 1stMud help.dat to the PrimeSUD lazy-scan help file.

Usage:
    python tools/help_to_primesud.py

Reads reference/1stMud4.5.3/data/help.dat (tagged #HELP...#END records,
'~'-terminated string fields) and writes primesud.hpappdir/help.dat in a
line-oriented format built for low-memory sequential scanning on the
HP Prime:

    #<level>|<keywords>
    <text line>
    <text line>
    ...
    #<level>|<keywords>
    ...

Records are sorted case-insensitively by keyword (cf. 1stMud add_help in
db2.c, which insertion-sorts by str_cmp). Entries above mortal visibility
(effective level > MAX_MORTAL_LEVEL) are dropped -- PrimeSUD is
single-user with no immortals. Negative levels (hidden-keyword helps) are
kept with their sign, matching 1stMud level semantics. The leading '.'
whitespace guard is stripped at conversion time (cf. 1stMud help_text in
macro.h). The 'category' field is dropped (do_index not ported).
"""

import re
import sys
from pathlib import Path

SRC = Path("reference/1stMud4.5.3/data/help.dat")
DST = Path("primesud.hpappdir/help.dat")
MAX_MORTAL_LEVEL = 51  # cf. primesud.hpappdir/config.py

# cp1252 punctuation found in upstream data -> ASCII
CP1252_FIXES = {"\x91": "'", "\x92": "'", "\x96": "-"}

# [PRIMESUD] extra records with no 1stMud equivalent: (level, keywords, text)
EXTRA_RECORDS = [
    (0, "KEYS KEYPAD CALCULATOR",
     "HP Prime keypad quick reference:\n"
     "\n"
     "Move: 2/8=n/s  4/6=w/e  7/9=u/d (or n/s/e/w/u/d)\n"
     "5=look  i=inv  wear  remove  eat  quaff  recite  zap\n"
     "brandish  st=stats  sk=skills  k/kill=fight  kick\n"
     "cast <spell>  flee  save  credits  q=quit\n"),
]

# [PRIMESUD] linguistic slips in upstream help text
TYPO_FIXES = {
    "and costs more experience points, then fleeing":
        "and costs more experience points, than fleeing",
}


def parse_records(raw):
    records = []
    for chunk in raw.split("#HELP")[1:]:
        chunk = chunk.split("#END")[0]
        m_level = re.search(r"^level[ \t]+(-?\d+)", chunk, re.M)
        m_keyword = re.search(r"^keyword[ \t]+(.*?)~", chunk, re.M | re.S)
        m_text = re.search(r"^text[ \t]+(.*?)~", chunk, re.M | re.S)
        if not (m_level and m_keyword and m_text):
            sys.exit("Malformed record: %r..." % chunk[:60])
        level = int(m_level.group(1))
        keyword = m_keyword.group(1).replace("\r\n", " ").strip()
        text = m_text.group(1).replace("\r\n", "\n")
        if text.startswith("."):  # help_text() whitespace guard
            text = text[1:]
        records.append((level, keyword, text))
    return records


def main():
    raw = SRC.read_bytes().decode("latin-1")
    for bad, good in CP1252_FIXES.items():
        raw = raw.replace(bad, good)
    for bad, good in TYPO_FIXES.items():
        raw = raw.replace(bad, good)

    records = parse_records(raw)
    kept = []
    for level, keyword, text in records:
        eff = -level - 1 if level < 0 else level
        if eff > MAX_MORTAL_LEVEL:
            continue
        kept.append((level, keyword, text))
    kept.extend(EXTRA_RECORDS)
    kept.sort(key=lambda r: r[1].lower())

    out = []
    for level, keyword, text in kept:
        assert "|" not in keyword, keyword
        out.append("#%d|%s" % (level, keyword))
        for line in text.split("\n"):
            assert not line.startswith("#"), line
            out.append(line)
        # drop trailing blank from texts that end with newline-before-~
        if out[-1] == "":
            out.pop()

    data = "\n".join(out) + "\n"
    assert all(ord(c) < 128 for c in data), "non-ASCII output"
    DST.write_bytes(data.encode("ascii"))
    print("Wrote %s: %d/%d entries, %d bytes"
          % (DST, len(kept), len(records), len(data)))


if __name__ == "__main__":
    main()
