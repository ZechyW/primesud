import os
import sys
import types
import random

# Make game modules importable from the test runner
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "primesud.hpappdir"))

# Stub HP Prime modules that don't exist on PC

_hpprime = types.ModuleType("hpprime")
_hpprime.eval = lambda s: 0
_hpprime.keyboard = lambda: 0
sys.modules["hpprime"] = _hpprime

_uio = types.ModuleType("uio")
_uio.FileIO = open          # standard open() is compatible: supports rb/wb + context manager
sys.modules["uio"] = _uio

_cas = types.ModuleType("cas")
_cas.get_key = lambda: None
sys.modules["cas"] = _cas

_urandom = types.ModuleType("urandom")
_urandom.randint = random.randint
sys.modules["urandom"] = _urandom
