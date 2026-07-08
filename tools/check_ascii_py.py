"""Check project Python files are ASCII-only and BOM-free."""

from pathlib import Path
import sys


DEFAULT_PATHS = ("src", "tools")
SKIP_PARTS = {".git", "__pycache__"}
BOM = b"\xef\xbb\xbf"


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
        if reasons:
            bad.append("%s: %s" % (path, ", ".join(reasons)))

    if bad:
        sys.stderr.write("Python source encoding check failed:\n")
        for line in bad:
            sys.stderr.write("  " + line + "\n")
        return 1

    print("OK: Python files are ASCII-only and BOM-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
