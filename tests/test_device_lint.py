"""Guard: src/ must not call str methods missing on-device. [PRIMESUD]

CPython has these, so the regular suite can't catch them; they raise
AttributeError only on the HP Prime. Banned list = docs/BUILTINS.md
"Not available (CPython only)" table.
"""
import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
BANNED = re.compile(
    r"\.(capitalize|casefold|expandtabs|format_map|isalnum|isascii|isdecimal"
    r"|isidentifier|isnumeric|isprintable|istitle|ljust|maketrans"
    r"|removeprefix|removesuffix|rjust|swapcase|title|translate|zfill)\(")


def test_no_banned_str_methods():
    hits = []
    for py in sorted(SRC.rglob("*.py")):
        for i, line in enumerate(py.read_text().splitlines(), 1):
            if BANNED.search(line):
                hits.append("%s:%d: %s" % (py.name, i, line.strip()))
    assert not hits, ("str methods missing on HP Prime "
                      "(docs/BUILTINS.md):\n" + "\n".join(hits))


def test_no_banned_syntax():
    """f-strings, {**a} dict unpacking, and 2-arg next() are SyntaxError
    on-device (docs/BUILTINS.md sec. Language / Syntax Restrictions) but
    parse fine on CPython, so only this lint catches them."""
    hits = []
    for py in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=py.name)
        for node in ast.walk(tree):
            bad = None
            if isinstance(node, ast.JoinedStr):
                bad = "f-string"
            elif isinstance(node, ast.Dict) and None in node.keys:
                bad = "{**...} dict unpacking"
            elif (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "next" and len(node.args) == 2):
                bad = "2-arg next()"
            if bad:
                hits.append("%s:%d: %s" % (py.name, node.lineno, bad))
    assert not hits, ("syntax not supported on HP Prime "
                      "(docs/BUILTINS.md):\n" + "\n".join(hits))
