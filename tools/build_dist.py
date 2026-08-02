"""Build minified dist copy of src for HP Prime deployment.

Usage:
    python tools/build_dist.py          Build dist
    python tools/build_dist.py --check  Build dist + verify symbol preservation
    python tools/build_dist.py --zip    Also write dist/PrimeSUD-hpprime.zip
                                        (hpappdir at zip root, for Connectivity Kit)
    python tools/build_dist.py --zip v1.0.1
                                        Same, named dist/PrimeSUD-<ver>-hpprime.zip
                                        (release asset)
    python tools/build_dist.py --skip-preflight
                                        Skip the uncommitted-src drift warning
    python tools/build_dist.py --area-bench --zip bench
                                        Build dist/PrimeSUD-bench-hpprime.zip
    python tools/build_dist.py --help   Print this usage text and exit (no build)

Run from the repo root (paths are cwd-relative).
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
EXCLUDE = {"primesud.sav", "hvars.json", "area_load_bench.log"}
AREA_BENCH_TARGETS = (
    "area_pestates.txt",
    "area_catacomb.txt",
    "area_newthalos.txt",
)
AREA_BENCH_SCRIPT = Path("debug/area_load_bench.py")
# python-minifier renames _best_hand_layout's captured locals onto names its
# nested closure also binds as comprehension targets. Where an inlined
# listcomp and a genexp bind that name in the same scope, CPython 3.12+
# (PEP 709) stops resolving the free variable: `_strength_after_swap` then
# receives the closure cell instead of the player dict.
#
# Only reproduced on desktop CPython. MicroPython does not inline
# comprehensions, and `wear best` has been observed working on-device from a
# minified build -- so this is not a known device bug. Preserve the names
# anyway: the collision is gratuitous, it costs a few bytes, and without it
# the dist cannot be verified against CPython (see
# tests/test_minified_inventory.py).
PRESERVE_LOCALS = {
    "inventory.py": ["player", "equip", "current", "locked", "small",
                     "scores"],
}
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


def minify_source(source, preserve_locals=None):
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
        preserve_locals=preserve_locals,
        rename_globals=False,
        convert_posargs_to_args=False,
        remove_asserts=False,
    )


def _share_area_flag_dicts(source):
    """Share repeated immutable flag dicts in generated area source.

    Repeated all-True flag maps become references to one helper dict. Runtime
    shape remains dict-compatible, while exec builds fewer containers and key
    tables. Benchmark builds leave normal area files untouched so their
    separate ``bench_`` variants can still measure this transform.

    Args:
        source: Generated area Python source.

    Returns:
        tuple: (transformed source, number of avoided duplicate dicts).
    """
    fields = {
        "MOBILES": {
            "act_flags", "affected_by", "off_flags", "imm_flags",
            "res_flags", "vuln_flags", "form_flags", "part_flags",
        },
        "ROOMS": {"flags"},
        "OBJECTS": {
            "wear_flags", "extra_flags", "weapon_flags", "container_flags",
        },
    }
    tree = ast.parse(source)
    groups = {}
    for stmt in tree.body:
        if (not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1
                or not isinstance(stmt.targets[0], ast.Name)):
            continue
        section = stmt.targets[0].id
        wanted = fields.get(section)
        if wanted is None or not isinstance(stmt.value, ast.Dict):
            continue
        for row in stmt.value.values:
            if not isinstance(row, ast.Dict):
                continue
            for i, key in enumerate(row.keys):
                value = row.values[i]
                # Empty dicts are excluded deliberately: sharing them saves
                # nothing measurable, and `{}` is the shape runtime code is
                # most likely to reach for with setdefault -- an in-place
                # mutation there would leak across every sharing template.
                if (not isinstance(key, ast.Constant) or key.value not in wanted
                        or not isinstance(value, ast.Dict) or not value.values
                        or any(not isinstance(v, ast.Constant) or v.value is not True
                               for v in value.values)):
                    continue
                signature = ast.dump(value, include_attributes=False)
                groups.setdefault(signature, []).append((row, i, value))

    helpers = []
    shared = 0
    helper_no = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        name = "_F" + str(helper_no)
        helper_no += 1
        helpers.append(ast.Assign(
            targets=[ast.Name(id=name, ctx=ast.Store())],
            value=group[0][2],
        ))
        for row, i, _value in group:
            row.values[i] = ast.Name(id=name, ctx=ast.Load())
        shared += len(group) - 1

    tree.body = helpers + tree.body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree), shared


def _area_payload(source):
    """Exec generated source and return runtime-consumed values."""
    ns = {}
    exec(source, ns)
    keys = (
        "AREA", "MOBILES", "ROOMS", "OBJECTS", "RESETS",
        "MOBPROGS", "OBJPROGS", "ROOMPROGS",
    )
    return {key: ns.get(key) for key in keys}


def _build_area_bench_files(errors):
    """Add transfer-only benchmark runner and shared-flag area variants."""
    try:
        probe = minify_source(AREA_BENCH_SCRIPT.read_text(encoding="utf-8"))
        raw = probe.encode("utf-8")
        if any(b > 127 for b in raw):
            raise ValueError("minifier produced non-ASCII output")
        (DIST_DIR / "area_load_bench.txt").write_bytes(raw)
        print("  area_load_bench.txt          benchmark runner")
    except Exception as e:
        errors.append("area_load_bench.txt: %s" % e)

    for name in AREA_BENCH_TARGETS:
        try:
            source = (SRC_DIR / name).read_text(encoding="utf-8")
            transformed, shared = _share_area_flag_dicts(source)
            minified = minify_source(transformed)
            if _area_payload(source) != _area_payload(minified):
                raise ValueError("shared-flag transform changed area payload")
            raw = minified.encode("utf-8")
            if any(b > 127 for b in raw):
                raise ValueError("minifier produced non-ASCII output")
            target = DIST_DIR / ("bench_" + name)
            target.write_bytes(raw)
            print("  %-30s %d duplicate flag dicts avoided" %
                  (target.name, shared))
        except Exception as e:
            errors.append("bench_%s: %s" % (name, e))

    config_path = DIST_DIR / "config.py"
    if config_path.exists():
        with config_path.open("ab") as f:
            f.write(b"\nAREA_LOAD_BENCH=True\n")
    else:
        errors.append("area benchmark: minified config.py missing")


def _is_area_data(path):
    """area_*.txt: Python source exec'd at load time (see world._load_area)."""
    return path.suffix == ".txt" and path.name.startswith("area_")


def preflight():
    """Regenerate all derived data (areas, world static tables, mob index,
    help + index).

    Order matters: mobs.bin is built from the area .txt files.
    Regen writes into SRC_DIR, so a dirty git tree afterwards means the
    checked-in data had drifted from the generators -- inspect before
    copying to the calculator.
    """
    steps = [
        # Areas + world.py static tables + mobs.bin/paths.idx, in
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
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        raise SystemExit(0)  # skip --check/--zip handling in __main__ too

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
    total_shared = 0
    errors = []
    # Benchmark builds leave the normal area files unshared so their separate
    # bench_ variants can still A/B the transform.
    bench_build = "--area-bench" in sys.argv

    for src_file in sorted(SRC_DIR.iterdir()):
        if src_file.is_dir() or src_file.name in EXCLUDE:
            continue
        dst_file = DIST_DIR / src_file.name

        # area_*.txt are Python source exec'd by world.py -- minify like
        # .py. Other .txt stay verbatim: help.txt's index is byte-offset
        # based; commands.txt is a custom line format, *.bin are
        # binary and copied verbatim.
        if src_file.suffix != ".py" and not _is_area_data(src_file):
            shutil.copy2(src_file, dst_file)
            continue

        source = src_file.read_text(encoding="utf-8")
        before = len(source.encode("utf-8"))

        try:
            if _is_area_data(src_file) and not bench_build:
                source, shared = _share_area_flag_dicts(source)
                total_shared += shared
            minified = minify_source(source,
                                     PRESERVE_LOCALS.get(src_file.name))
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

    if bench_build:
        _build_area_bench_files(errors)

    print()
    if total_shared:
        print("  Shared flag dicts: %d duplicates avoided across area files"
              % total_shared)
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


def build_zip(version=None):
    """Zip DIST_DIR into dist/PrimeSUD[-<version>]-hpprime.zip.

    Args:
        version: Release tag for the filename, or None for an unversioned
            local build.
    """
    stem = "PrimeSUD-" + (version + "-" if version else "") + "hpprime"
    base = DIST_DIR.parent / stem
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
        versioned = i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-")
        build_zip(sys.argv[i + 1] if versioned else None)
    raise SystemExit(0)
