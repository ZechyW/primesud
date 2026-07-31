"""Regenerate all shipped area data and dependent indexes.

Usage:
    python tools/regen_areas.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "pc_shim"))

import world


def run(*args):
    subprocess.run([sys.executable, "-u"] + list(args),
                   cwd=str(ROOT), check=True)


def main():
    # world._AREA_FILES is the shipped-area source of truth; areas/chess2.are
    # intentionally exists without being shipped.
    for filename, _tag, _name, _lo, _hi in world._AREA_FILES:
        area = Path(filename).stem[5:]  # strip "area_"
        print("==> " + area, flush=True)
        run("tools/are_to_primesud.py",
            "areas/" + area + ".are", "src/" + filename)

    for script, label in (
            ("tools/gen_area_adj.py", "world.py static tables"),
            ("tools/build_mob_index.py", "mob, object, and gear indexes"),
            ("tools/build_path_index.py", "path index"),
            ("tools/check_ascii_py.py", "ASCII check")):
        print("==> " + label, flush=True)
        run(script)


if __name__ == "__main__":
    main()
