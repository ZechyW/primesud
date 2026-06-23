"""PC entry point for PrimeSUD -- run with: python primesud_pc.py"""
import sys
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, 'pc_shim'))
sys.path.insert(1, os.path.join(_ROOT, 'primesud.hpappdir'))
os.chdir(os.path.join(_ROOT, 'primesud.hpappdir'))

import gc
gc.mem_free = lambda: 0  # HP Prime MicroPython built-in, not in CPython gc

import primesud