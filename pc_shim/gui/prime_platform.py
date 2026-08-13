"""PC platform calls for Tkinter graphical mode."""

import hpprime
from pc_shim.prime_platform import hvars_get, hvars_set, ticks


def wait_ms(ms):
    hpprime.wait_ms(ms)


def clear_graphics(*args):
    hpprime.close_display()
