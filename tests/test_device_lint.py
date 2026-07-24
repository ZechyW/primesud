"""Guard: src/ must not call str methods missing on-device. [PRIMESUD]

CPython has these, so the regular suite can't catch them; they raise
AttributeError only on the HP Prime. Banned list = docs/BUILTINS.md
"Not available (CPython only)" table.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
BANNED = re.compile(
    r"\.(capitalize|casefold|expandtabs|format_map|isalnum|isascii|isdecimal"
    r"|isidentifier|isnumeric|isprintable|ljust|maketrans|removeprefix"
    r"|removesuffix|rjust|title|translate|zfill)\(")


def test_no_banned_str_methods():
    hits = []
    for py in sorted(SRC.rglob("*.py")):
        for i, line in enumerate(py.read_text().splitlines(), 1):
            if BANNED.search(line):
                hits.append("%s:%d: %s" % (py.name, i, line.strip()))
    assert not hits, ("str methods missing on HP Prime "
                      "(docs/BUILTINS.md):\n" + "\n".join(hits))
