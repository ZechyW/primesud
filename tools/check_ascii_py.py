"""Check project Python files are ASCII-only and BOM-free.

src/ files additionally must not use %-formatting, .format(), or f-strings
(firmware format bug, CLAUDE.md pitfall 8), nor bare str() calls (str(int)-GC
heap bug; render ints via util.num_str/int_str, mixed values via util.sstr).
A trailing `# str-ok` comment exempts an audited line: argument provably
neither int nor str, or a site that must not depend on util (tml.py).
src/ also must not call .setdefault() on an item *_flags dict: instance
flag dicts shadow the template whole (item.py contract), so an empty
default silently erases every template flag.
tools/ runs on the dev PC and is exempt.
"""

import ast
from pathlib import Path
import re
import sys


DEFAULT_PATHS = ("src", "tools")
SKIP_PARTS = {".git", "__pycache__"}
BOM = b"\xef\xbb\xbf"

# printf conversion spec in a string literal; only chprintf & friends may
# carry one (they format via handler._safe_fmt, never the firmware formatter)
CONV_SPEC = re.compile(r"%[-0-9.]*[sdcxfu]")
SAFE_FORMATTERS = {"chprintf", "chprintlnf", "printf", "_safe_fmt"}

# Item instance flag dicts fully SHADOW the template (item.py contract):
# .setdefault("extra_flags", {}) hides every template flag. Mutate via
# item.ensure_item_extra_flags / set_item_extra_flag (copy-then-edit).
SHADOWED_FLAG_KEYS = {"extra_flags", "weapon_flags", "container_flags",
                      "wear_flags"}


def _exempt_literals(tree):
    """Ids of str literals allowed to hold conversion specs: docstrings and
    safe-formatter arguments."""
    exempt = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = node.body[0] if node.body else None
            if (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)
                    and isinstance(doc.value.value, str)):
                exempt.add(id(doc.value))
        elif isinstance(node, ast.Call):
            name = (node.func.id if isinstance(node.func, ast.Name)
                    else getattr(node.func, "attr", ""))
            if name in SAFE_FORMATTERS:
                for arg in node.args:
                    exempt.add(id(arg))
    return exempt


def format_violations(source):
    """Format-bug call sites in on-device source: line-numbered reasons.

    Flags a str-literal left operand of %, any .format() attribute call,
    f-strings, any other string literal carrying a printf conversion
    spec, and bare str() calls without a `# str-ok` marker. The literal
    rule is what catches a format string hoisted into a variable or table
    before the % is applied (scan.py's _DISTANCE was one).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["line " + str(exc.lineno) + ": syntax error (unparseable)"]
    exempt = _exempt_literals(tree)
    lines = source.splitlines()
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
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "str"
                and "# str-ok" not in lines[node.lineno - 1]):
            hits.append("line " + str(node.lineno)
                        + ": bare str() call (num_str/sstr, or # str-ok)")
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setdefault" and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in SHADOWED_FLAG_KEYS):
            hits.append("line " + str(node.lineno)
                        + ": setdefault on a template-shadowing *_flags dict"
                          " (use item.ensure/set_item_extra_flag)")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in exempt and CONV_SPEC.search(node.value)):
            hits.append("line " + str(node.lineno)
                        + ": conversion spec in string literal")
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
