"""Toy module for zz_mpy_probe -- compiled to mpytoy.mpy, default flags.

NEVER ship this .py to the appdir (auto-import would mask the .mpy test).
"""
MPYTOY_OK = 12345


def _twice(n):
    return n + n


MPYTOY_TWICE = _twice(MPYTOY_OK)
