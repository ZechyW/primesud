"""Run PrimeSUD on PC using Tkinter and the source pixel renderer.

Usage: python run_graphical.py
"""

import gc
import os
import sys


_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[0:0] = [
    os.path.join(_ROOT, "pc_gui_shim"),
    os.path.join(_ROOT, "src"),
    os.path.join(_ROOT, "pc_shim"),
]
os.chdir(os.path.join(_ROOT, "src"))

gc.mem_free = lambda: 0

import hpprime
hpprime.init_display()

import game_state
game_state.SAVE_FILE = os.path.join(_ROOT, "primesud.sav")

try:
    import primesud
except KeyboardInterrupt:
    pass
finally:
    hpprime.close_display()
