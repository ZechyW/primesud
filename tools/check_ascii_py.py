"""Check project Python files are ASCII-only and BOM-free.

src/ files additionally must not use %-formatting, .format(), or f-strings
(firmware format bug, CLAUDE.md pitfall 8). tools/ runs on the dev PC and is
exempt.
"""

import ast
from pathlib import Path
import sys


DEFAULT_PATHS = ("src", "tools")
SKIP_PARTS = {".git", "__pycache__"}
BOM = b"\xef\xbb\xbf"


def format_violations(source):
    """Format-bug call sites in on-device source: line-numbered reasons.

    Flags a str-literal left operand of %, any .format() attribute call,
    and f-strings. ponytail: a hoisted variable holding a format string
    (fmt % args) is not caught; add simple assignment tracking if one
    ever slips through review.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["line " + str(exc.lineno) + ": syntax error (unparseable)"]
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)):
            hits.append("line " + str(node.lineno) + ": % string formatting")
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"):
            hits.append("line " + str(node.lineno) + ": .format() call")
        elif isinstance(node, ast.JoinedStr):
            hits.append("line " + str(node.lineno) + ": f-string")
    return hits


def iter_py_files(paths):
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            if path.suffix == ".py":
                yield path
            continue
        for py in path.rglob("*.py"):
            if not any(part in SKIP_PARTS for part in py.parts):
                yield py


def main(argv):
    paths = argv[1:] or list(DEFAULT_PATHS)
    bad = []
    for path in iter_py_files(paths):
        data = path.read_bytes()
        reasons = []
        if data.startswith(BOM):
            reasons.append("UTF-8 BOM")
        if any(byte > 127 for byte in data):
            reasons.append("non-ASCII byte")
        elif "src" in path.parts:
            reasons.extend(format_violations(data.decode("ascii")))
        if reasons:
            bad.append("%s: %s" % (path, ", ".join(reasons)))

    if bad:
        sys.stderr.write("Python source encoding check failed:\n")
        for line in bad:
            sys.stderr.write("  " + line + "\n")
        return 1

    print("OK: Python files are ASCII-only, BOM-free, and src is format-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
