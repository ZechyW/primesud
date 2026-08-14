"""Run PrimeSUD on PC using the built dist version.

Rebuilds dist/ first, then launches using minified sources (with PC shims).
Usage: python run_dist.py
"""
import subprocess
import sys
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))

# Build dist
rc = subprocess.call(
    [sys.executable, os.path.join(_ROOT, "tools", "build_dist.py"), "--check"],
    cwd=_ROOT,
)
if rc != 0:
    sys.exit("dist build failed")

print("\n--- launching from dist ---\n")

sys.path.insert(0, os.path.join(_ROOT, "pc_shim"))
sys.path.insert(1, os.path.join(_ROOT, "dist", "primesud.hpappdir"))
os.chdir(os.path.join(_ROOT, "dist", "primesud.hpappdir"))

import gc
gc.mem_free = lambda: 0

# PC saves live at repo root (gitignored) so dist stays a clean transfer
# artifact for the physical Prime
import game_state
game_state.SAVE_FILE = os.path.join(_ROOT, "primesud.sav")
game_state.BACKUP_FILE = os.path.join(_ROOT, "primesud_backup.sav")

import primesud
