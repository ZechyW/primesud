"""Build minified dist copy of primesud.hpappdir for HP Prime deployment.

Usage:
    python tools/build_dist.py          Build dist
    python tools/build_dist.py --check  Build dist + verify symbol preservation
"""

import ast
import shutil
import sys
import warnings
from pathlib import Path

import python_minifier

# tml.py (external lib) uses "\e"-style escapes; harmless on-device, noisy
# when CPython compiles it inside the minifier
warnings.filterwarnings("ignore", category=SyntaxWarning)

SRC_DIR = Path("primesud.hpappdir")
DIST_DIR = Path("dist/primesud.hpappdir")
BOM = b"\xef\xbb\xbf"
# Save files -- packaging these would overwrite on-calc data
EXCLUDE = {"primesud.sav", "hvars.json"}


def minify_source(source):
    return python_minifier.minify(
        source,
        remove_annotations=True,
        remove_pass=True,
        remove_literal_statements=True,
        combine_imports=True,
        remove_object_base=True,
        remove_explicit_return_none=True,
        remove_builtin_exception_brackets=True,
        constant_folding=True,
        # Risky on HP Prime -- disable
        hoist_literals=False,
        rename_locals=False,
        rename_globals=False,
        convert_posargs_to_args=False,
        remove_asserts=False,
    )


def main():
    if not SRC_DIR.is_dir():
        sys.exit("Source dir %s not found" % SRC_DIR)

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    total_before = 0
    total_after = 0
    errors = []

    for src_file in sorted(SRC_DIR.iterdir()):
        if src_file.is_dir() or src_file.name in EXCLUDE:
            continue
        dst_file = DIST_DIR / src_file.name

        if src_file.suffix != ".py":
            shutil.copy2(src_file, dst_file)
            continue

        source = src_file.read_text(encoding="utf-8")
        before = len(source.encode("utf-8"))

        try:
            minified = minify_source(source)
        except Exception as e:
            errors.append("%s: %s" % (src_file.name, e))
            shutil.copy2(src_file, dst_file)
            total_before += before
            total_after += before
            continue

        raw = minified.encode("utf-8")
        if raw.startswith(BOM):
            raw = raw[3:]
        if any(b > 127 for b in raw):
            errors.append("%s: minifier produced non-ASCII output" % src_file.name)
            shutil.copy2(src_file, dst_file)
            total_before += before
            total_after += before
            continue

        dst_file.write_bytes(raw)
        after = len(raw)
        total_before += before
        total_after += after

        pct = (1 - after / before) * 100 if before else 0
        print("  %-30s %6d -> %6d  (%.0f%%)" % (src_file.name, before, after, pct))

    print()
    pct_total = (1 - total_after / total_before) * 100 if total_before else 0
    print("  TOTAL: %d -> %d bytes (%.0f%% reduction)" % (total_before, total_after, pct_total))

    if errors:
        print("\nErrors:")
        for e in errors:
            print("  " + e)
        return 1

    print("\nDist written to %s" % DIST_DIR)
    return 0


def extract_public_names(source):
    """Extract top-level function, class, and assignment names from source."""
    tree = ast.parse(source)
    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
    return names


def check_symbols():
    """Verify all public names from source survive in dist."""
    errors = []
    for src_file in sorted(SRC_DIR.glob("*.py")):
        dst_file = DIST_DIR / src_file.name
        if not dst_file.exists():
            errors.append("%s: missing from dist" % src_file.name)
            continue
        try:
            src_names = extract_public_names(src_file.read_text(encoding="utf-8"))
            dst_names = extract_public_names(dst_file.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errors.append("%s: parse error: %s" % (src_file.name, e))
            continue
        missing = src_names - dst_names
        if missing:
            errors.append("%s: missing symbols: %s" % (src_file.name, ", ".join(sorted(missing))))

    if errors:
        print("\nSymbol check FAILED:")
        for e in errors:
            print("  " + e)
        return 1
    print("\nSymbol check passed: all public names preserved")
    return 0


if __name__ == "__main__":
    rc = main()
    if rc != 0:
        raise SystemExit(rc)
    if "--check" in sys.argv:
        raise SystemExit(check_symbols())
    raise SystemExit(rc)
