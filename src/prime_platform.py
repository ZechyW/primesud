"""HP Prime platform wrappers and graphic primitive ownership."""

from hpprime import dimgrob, eval as ppl_eval
from util import num_str


def ticks():
    """Return HP Prime millisecond tick counter. [PRIMESUD]"""
    return int(ppl_eval("Ticks"))


def wait_ms(ms):
    """Wait for milliseconds via PPL WAIT. [PRIMESUD]

    num_str, not str(): this runs every idle pass of the main loop, and
    recurring str(int) transients feed the G1 GC-corruption bug (CLAUDE.md
    pitfall 8); the cache makes repeat delays allocation-free.
    """
    ppl_eval("WAIT(" + (num_str(ms) if type(ms) is int else str(ms)) + "/1e3)")


def clear_graphics(first=1, last=8):
    """Clear HP Prime graphic buffers in the inclusive range. [PRIMESUD]"""
    for n in range(first, last + 1):
        dimgrob(n, 0, 0, 0)


def hvars_get(name):
    """Read a PPL home variable through HVars. [PRIMESUD]"""
    return ppl_eval('HVars("' + name + '")')


def hvars_set(name, value):
    """Write a PPL home variable through HVars. [PRIMESUD]"""
    ppl_eval('HVars("' + name + '"):="' + value + '"')
