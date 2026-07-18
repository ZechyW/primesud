"""Convert 1stMud social.dat to the PrimeSUD lazy-scan socials file.

Usage:
    python tools/socials_to_primesud.py

Reads reference/1stMud4.5.3/data/social.dat (tagged #SOCIAL...#END records,
'~'-terminated tab-delimited fields) and writes src/socials.txt +
src/socials.idx in the same off-heap index+seek shape as help.txt/help.idx
(cf. tools/help_to_primesud.py):

    socials.txt -- per social, exactly 7 lines in fixed order:
        char_no_arg, others_no_arg, char_found, others_found, vict_found,
        char_auto, others_auto
    (char_not_found is parsed but not emitted -- check_social (interp.c)
    never reads cmd->char_not_found; it always prints a hardcoded "They
    aren't here." instead.)

    socials.idx -- one line per social, sorted by name:
        <offset>|<length>|<name>
    offset is the byte position of the entry's first line in socials.txt;
    length is the total byte length of its 7 lines, so check_social can do
    exactly one seek + one read(length).

Records are sorted case-insensitively by name (cf. 1stMud social.dat load
order is insertion order via add_social in db2.c; PrimeSUD's find_social
does a straight alphabetical-prefix index scan instead of a hash-bucket
walk, so the data must be pre-sorted -- see src/socials.py find_social).
"""

import re
import sys
from pathlib import Path

SRC = Path("reference/1stMud4.5.3/data/social.dat")
DST = Path("src/socials.txt")
IDX = Path("src/socials.idx")

FIELD_KEYS = ["name", "char_no_arg", "others_no_arg", "char_found",
              "others_found", "vict_found", "char_not_found",
              "char_auto", "others_auto"]

# Fields written to socials.txt, in emitted order (char_not_found dropped --
# see module docstring).
EMIT_KEYS = ["char_no_arg", "others_no_arg", "char_found", "others_found",
             "vict_found", "char_auto", "others_auto"]

# cp1252/latin-1 punctuation -> ASCII (cf. help_to_primesud.py CP1252_FIXES)
CP1252_FIXES = {"\x91": "'", "\x92": "'", "\x93": '"', "\x94": '"', "\x96": "-"}

# [PRIMESUD] linguistic slips in upstream social text.
# An automated scan for common misspellings/grammar slips (recieve,
# beleive, seperate, "a outlaw"-style article errors, etc.) found no hits
# across all 244 stock entries.  Not an exhaustive manual read of every
# field; flag any further ones found on review.
TYPO_FIXES = {
    # aargh.others_no_arg: 1stMud corrupted QuickMUD's "profound" (cf.
    # reference/quickmud/area/social.are) into the field tag "others_found"
    "prothers_found": "profound",
}


def parse_records(raw):
    records = []
    for chunk in raw.split("#SOCIAL")[1:]:
        chunk = chunk.split("#END")[0]
        fields = {}
        for key in FIELD_KEYS:
            m = re.search(r"^" + key + r"[ \t]+(.*?)~", chunk, re.M | re.S)
            if not m:
                sys.exit("Missing field %r in record: %r..." % (key, chunk[:60]))
            fields[key] = m.group(1)
        records.append(fields)
    return records


def sanitize(text, warnings, name, key):
    """Replace non-ASCII bytes with the closest ASCII equivalent or '?'."""
    out = []
    changed = False
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
            continue
        repl = CP1252_FIXES.get(ch, "?")
        out.append(repl)
        changed = True
        warnings.append("%s.%s: %r -> %r" % (name, key, ch, repl))
    return "".join(out) if changed else text


def main():
    raw = SRC.read_bytes().decode("latin-1")
    raw = raw.replace("\r\n", "\n")

    records = parse_records(raw)

    warnings = []
    typo_hits = []
    entries = []  # (name, [7 emitted field values])
    for fields in records:
        name = fields["name"]
        values = []
        for key in EMIT_KEYS:
            text = fields[key]
            for bad, good in TYPO_FIXES.items():
                if bad in text:
                    typo_hits.append("%s.%s: %r -> %r" % (name, key, bad, good))
                    text = text.replace(bad, good)
            text = sanitize(text, warnings, name, key)
            values.append(text)
        entries.append((name, values))

    entries.sort(key=lambda r: r[0].lower())

    # Header is dead bytes at runtime: check_social reads by socials.idx
    # byte offset/length only, so it just shifts every offset.
    header = ("# 7 lines per social (char_no_arg, others_no_arg, char_found,"
              " others_found, vict_found, char_auto, others_auto); blank ="
              " unset field.  Read via byte offsets in socials.idx -- built"
              " by tools/socials_to_primesud.py, do not edit\n")
    lines = []
    idx_lines = []
    pos = len(header)
    for name, values in entries:
        idx_lines.append("%d|%d|%s" % (pos, sum(len(v) + 1 for v in values), name))
        for v in values:
            assert "\n" not in v, (name, v)
            lines.append(v)
            pos += len(v) + 1  # +1 for the "\n" this line will be written with

    data = header + "\n".join(lines) + "\n"
    assert all(ord(c) < 128 for c in data), "non-ASCII output"
    with open(DST, "w", newline="\n", encoding="ascii") as f:
        f.write(data)

    idx_data = "\n".join(idx_lines) + "\n"
    assert all(ord(c) < 128 for c in idx_data), "non-ASCII index"
    with open(IDX, "w", newline="\n", encoding="ascii") as f:
        f.write(idx_data)

    print("Wrote %s: %d entries, %d bytes" % (DST, len(entries), len(data)))
    print("Wrote %s: %d entries, %d bytes" % (IDX, len(entries), len(idx_data)))
    if warnings:
        print("Non-ASCII replacements (%d):" % len(warnings))
        for w in warnings:
            print("  " + w)
    if typo_hits:
        print("Typo fixes applied (%d):" % len(typo_hits))
        for t in typo_hits:
            print("  " + t)


if __name__ == "__main__":
    main()
