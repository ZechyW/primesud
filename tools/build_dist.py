"""Build minified dist copy of src for HP Prime deployment.

Usage:
    python tools/build_dist.py          Build dist
    python tools/build_dist.py --check  Build dist + verify symbol preservation
    python tools/build_dist.py --zip v1.0.1
                                        Also write dist/PrimeSUD-<ver>-hpprime.zip
                                        (release asset layout: hpappdir at zip root)
"""

import ast
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import python_minifier

# tml.py (external lib) uses "\e"-style escapes; harmless on-device, noisy
# when CPython compiles it inside the minifier
warnings.filterwarnings("ignore", category=SyntaxWarning)

SRC_DIR = Path("src")
DIST_DIR = Path("dist/primesud.hpappdir")
BOM = b"\xef\xbb\xbf"
# Save files -- packaging these would overwrite on-calc data
EXCLUDE = {"primesud.sav", "hvars.json"}
RELEASE_DOCS = (
    (Path("README.md"), Path("README.md")),
    (Path("LICENSES.md"), Path("LICENSES.md")),
    (Path("reference/1stMud4.5.3/doc/Diku/license.doc"),
     Path("licenses/DIKU-LICENSE.txt")),
    (Path("reference/1stMud4.5.3/doc/Merc/license.txt"),
     Path("licenses/MERC-LICENSE.txt")),
    (Path("reference/1stMud4.5.3/doc/Rom/rom.license"),
     Path("licenses/ROM-LICENSE.txt")),
    (Path("reference/1stMud4.5.3/doc/1stMud/LICENSE"),
     Path("licenses/1STMUD-LICENSE.txt")),
    (Path("reference/1stMud4.5.3/doc/Merc/rom.credits"),
     Path("licenses/ROM-CREDITS.txt")),
    (Path("reference/1stMud4.5.3/doc/1stMud/CREDITS"),
     Path("licenses/1STMUD-CREDITS.txt")),
)


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
        # Enabled 21/07/2026 after desktop checks and device walk.
        # hoist_literals dedups repeated area-data strings (-816KB);
        # rename_locals shrinks source + on-device qstr pool (-90KB).
        hoist_literals=True,
        rename_locals=True,
        rename_globals=False,
        convert_posargs_to_args=False,
        remove_asserts=False,
    )


def _is_area_data(path):
    """area_*.txt: Python source exec'd at load time (see world._load_area)."""
    return path.suffix == ".txt" and path.name.startswith("area_")


def preflight():
    """Regenerate all derived data (areas, world static tables, mob index,
    help + index).

    Order matters: mobs.idx is built from the area .txt files.
    Regen writes into SRC_DIR, so a dirty git tree afterwards means the
    checked-in data had drifted from the generators -- inspect before
    copying to the calculator.
    """
    steps = [
        # Areas + world.py static tables + mobs.idx/paths.idx, in
        # dependency order (regen refreshes world.py's tables before
        # the index builds that bootstrap the world from them).
        [sys.executable, "tools/regen_areas.py"],
        [sys.executable, "tools/build_help_idx.py"],
        [sys.executable, "tools/build_socials_idx.py"],
    ]
    for cmd in steps:
        print("==> preflight: %s" % cmd[-1])
        rc = subprocess.call(cmd)
        if rc != 0:
            sys.exit("Preflight step failed (%d): %s" % (rc, " ".join(cmd)))

    # Surface generator drift: regen writes into SRC_DIR, so any diff here
    # means checked-in data no longer matches the generators
    out = subprocess.run(
        ["git", "status", "--porcelain", str(SRC_DIR)],
        capture_output=True, text=True).stdout
    # Worktree column only ("XY path", Y != space): staged-but-identical
    # entries (e.g. mid-rename) are not generator drift
    drift = "\n".join(
        ln for ln in out.splitlines() if len(ln) > 1 and ln[1] != " ")
    if drift:
        print("\nWARNING: preflight changed checked-in data (generator drift):")
        print(drift)
        print("Review and commit before copying to the calculator.\n")


def main():
    if not SRC_DIR.is_dir():
        sys.exit("Source dir %s not found" % SRC_DIR)

    if "--skip-preflight" not in sys.argv:
        preflight()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)
    for source, destination in RELEASE_DOCS:
        target = DIST_DIR / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    total_before = 0
    total_after = 0
    errors = []

    for src_file in sorted(SRC_DIR.iterdir()):
        if src_file.is_dir() or src_file.name in EXCLUDE:
            continue
        dst_file = DIST_DIR / src_file.name

        # area_*.txt are Python source exec'd by world.py -- minify like
        # .py. Other .txt stay verbatim: help.txt's index is byte-offset
        # based; mobs.idx/commands.txt are custom line formats.
        if src_file.suffix != ".py" and not _is_area_data(src_file):
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


def check_area_data():
    """Exec source and dist area files, verify identical data content.

    Stronger than the .py symbol check: minified area data must produce
    byte-for-byte equal Python values, not just the same global names.
    """
    errors = []
    for src_file in sorted(SRC_DIR.glob("area_*.txt")):
        dst_file = DIST_DIR / src_file.name
        if not dst_file.exists():
            errors.append("%s: missing from dist" % src_file.name)
            continue
        try:
            src_ns, dst_ns = {}, {}
            exec(src_file.read_text(encoding="utf-8"), src_ns)
            exec(dst_file.read_text(encoding="utf-8"), dst_ns)
        except Exception as e:
            errors.append("%s: exec failed: %s" % (src_file.name, e))
            continue
        src_data = {k: v for k, v in src_ns.items() if not k.startswith("__")}
        # Compare on src's keyset: src is never hoisted, so its keys are
        # canonical. hoist_literals adds helper names to the dist namespace
        # (ignored here); a missing or wrong-valued key still mismatches.
        dst_data = {k: dst_ns.get(k) for k in src_data}
        if src_data != dst_data:
            diff_keys = [k for k in sorted(set(src_data) | set(dst_data))
                         if src_data.get(k) != dst_data.get(k)]
            errors.append("%s: data mismatch in %s" %
                          (src_file.name, ", ".join(diff_keys)))

    if errors:
        print("\nArea data check FAILED:")
        for e in errors:
            print("  " + e)
        return 1
    print("Area data check passed: minified area files exec to identical data")
    return 0


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


def build_zip(version):
    """Zip DIST_DIR into dist/PrimeSUD-<version>-hpprime.zip (release asset)."""
    base = DIST_DIR.parent / ("PrimeSUD-" + version + "-hpprime")
    path = shutil.make_archive(str(base), "zip", root_dir=DIST_DIR.parent,
                               base_dir=DIST_DIR.name)
    print("Release zip written to %s" % path)


if __name__ == "__main__":
    rc = main()
    if rc != 0:
        raise SystemExit(rc)
    if "--check" in sys.argv:
        rc = check_symbols() or check_area_data()
        if rc != 0:
            raise SystemExit(rc)
    if "--zip" in sys.argv:
        i = sys.argv.index("--zip")
        if i + 1 >= len(sys.argv) or sys.argv[i + 1].startswith("-"):
            raise SystemExit("--zip requires a version, e.g. --zip v1.0.1")
        build_zip(sys.argv[i + 1])
    raise SystemExit(0)
