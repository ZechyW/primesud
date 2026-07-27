"""Small runtime utility wrappers."""

import gc
from hpprime import eval as ppl_eval


def wait(seconds):
    """Wait for seconds via PPL WAIT."""
    ppl_eval("WAIT(" + str(seconds) + ")")


def fmt_bytes(n, precision=1):
    """Format a byte count as a human-readable string."""
    unit = "G"
    for u in ("B", "K", "M"):
        if n < 1024:
            unit = u
            break
        n /= 1024
    # manual fixed-point render: %/.format banned on-device (CLAUDE.md
    # pitfall 8) and this reproduces "{:.<p>f}" rounding for positive n
    p10 = 1
    for _ in range(precision):
        p10 *= 10
    scaled = int(n * p10 + 0.5)
    whole = int_str(scaled // p10)
    if precision == 0:
        return whole + unit
    f = int_str(scaled % p10)
    while len(f) < precision:
        f = "0" + f
    return whole + "." + f + unit


def free_mem():
    """Return current free heap as a human-readable string."""
    return fmt_bytes(gc.mem_free())

def gc_collect():
    """Convenience function for gc within the game"""
    return gc.collect()


# -- Firmware-safe int rendering [PRIMESUD] ------------------------------------
# The physical G1 corrupts its heap when bulk str(int) transients meet a
# garbage collection (explicit or automatic) -- see docs/BUILTINS.md sec.
# G1 memory-corruption bug.  int_str() renders ints by digit-table lookup +
# concat, never touching the firmware int formatter; num_str() fronts it
# with a persistent cache so repeat values (save payloads re-render the
# same few hundred numbers every save) cost one dict hit, no allocation.
# Probe-validated at 60 clean collects (debug/save_bench.py, cachedstr).

_DIG = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
_NCACHE = {}


def int_str(n):
    """Render an int as a decimal string without the firmware int formatter. [PRIMESUD]"""
    if n == 0:
        return "0"
    neg = n < 0
    if neg:
        n = -n
    s = ""
    while n:
        s = _DIG[n % 10] + s
        n //= 10
    return ("-" + s) if neg else s


def num_str(n):
    """Cached int_str: int -> decimal str via persistent cache. [PRIMESUD]

    Cache lives across saves; bounded by a rare clear-and-rebuild so a long
    session's drifting counters (xp, played) cannot grow it without limit.
    """
    s = _NCACHE.get(n)
    if s is None:
        if len(_NCACHE) > 4096:
            _NCACHE.clear()
        s = int_str(n)
        _NCACHE[n] = s
    return s


def sstr(v):
    """Safe str() for save payloads: cached digit path for ints, pass-through
    for strs, plain str() for anything else (bools keep their str() form). [PRIMESUD]
    """
    t = type(v)
    if t is int:
        return num_str(v)
    if t is str:
        return v
    return str(v)


# str.ljust/rjust are missing on-device and %-padding is banned (see
# CLAUDE.md pitfall 8); these pad by byte length, like the old % specs.
# For strings carrying {X colour codes use info._pad_color instead.

def pad_right(s, w):
    """Left-justify: pad s with trailing spaces to byte width w. [PRIMESUD]"""
    d = w - len(s)
    return s + " " * d if d > 0 else s


def pad_left(s, w):
    """Right-justify: pad s with leading spaces to byte width w. [PRIMESUD]"""
    d = w - len(s)
    return " " * d + s if d > 0 else s


def zpad(n, w):
    """Render int n zero-padded to byte width w, sign preserved. [PRIMESUD]"""
    s = int_str(n)
    if s[0] == "-":
        d = w - len(s)
        return ("-" + "0" * d + s[1:]) if d > 0 else s
    d = w - len(s)
    return ("0" * d + s) if d > 0 else s
