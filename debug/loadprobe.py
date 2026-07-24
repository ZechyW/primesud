"""Per-phase area load timings: read / exec / merge / reset. [PRIMESUD]

Run standalone on physical HP Prime in the same dir as the game modules
(full dist present).  Restart the Python app first so the heap is fresh.

Pass A (fresh heap): smallest / middle / largest area from _AREA_FILES.
Pass B (pressured heap): fill the area cache to AREA_CACHE_MAX, then
evict+reload the largest area twice -- with and without gc.collect()
before the load -- to test whether a pre-load collect cuts alloc cost.

Phase attribution: read+exec are timed on a throwaway pass before the
real load, reset via a wrapper inside it; merge = total - read - exec -
reset, so a small negative merge means ~0.  Pass B reset time includes
eviction-delta replay (the realistic gameplay reload).  Heap numbers are
raw mem_free deltas (no collect before reading), indicative only.

Results printed and written to loadprobe.log.
"""
import gc
from hpprime import eval as ppleval

import config
import world

_lines = []


def log(msg):
    print(msg)
    _lines.append(msg)


def ticks():
    return int(ppleval("Ticks"))


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


_reset_ms = [0]
_orig_reset = world._reset_loaded_area


def _timed_reset(*a):
    _t0 = ticks()
    _orig_reset(*a)
    _reset_ms[0] += ticks() - _t0


world._reset_loaded_area = _timed_reset


def probe(tag, label, collect_first=True):
    fname = world._TAG_TO_FILE[tag]
    t_gc = 0
    if collect_first:
        t0 = ticks()
        gc.collect()
        t_gc = ticks() - t0
    f0 = free()
    # Throwaway read+exec pass for phase attribution.
    t0 = ticks()
    with open(fname) as f:
        src = f.read()
    t_read = ticks() - t0
    ns = {}
    t0 = ticks()
    exec(src, ns)
    t_exec = ticks() - t0
    src = None
    ns = None
    gc.collect()
    _reset_ms[0] = 0
    t0 = ticks()
    world._load_area(tag)
    t_total = ticks() - t0
    t_reset = _reset_ms[0]
    f1 = free()
    log(label + " " + tag + ": total=" + str(t_total)
        + "ms read=" + str(t_read) + " exec=" + str(t_exec)
        + " reset=" + str(t_reset)
        + " merge~=" + str(t_total - t_read - t_exec - t_reset)
        + " gc=" + str(t_gc)
        + " heap+=" + str(f0 - f1) + " free=" + str(f1))


def run():
    world.init_world()
    small = world._AREA_FILES[0][1]
    mid = world._AREA_FILES[len(world._AREA_FILES) // 2][1]
    big = world._AREA_FILES[-1][1]
    log("targets: " + small + " / " + mid + " / " + big)
    log("free at start=" + str(free()))

    log("-- pass A: fresh heap --")
    for tag in (small, mid, big):
        probe(tag, "A")

    log("-- pass B: pressured heap (cache "
        + str(config.AREA_CACHE_MAX) + ") --")
    for _entry in world._AREA_FILES:
        if len(world._LOADED_AREAS) >= config.AREA_CACHE_MAX:
            break
        if _entry[1] not in world._LOADED_AREAS:
            world._load_area(_entry[1])
    log("loaded areas=" + str(len(world._LOADED_AREAS))
        + " free=" + str(free()))

    world._unload_area(big)
    probe(big, "B+gc", collect_first=True)
    world._unload_area(big)
    probe(big, "B-nogc", collect_first=False)


try:
    run()
finally:
    with open("loadprobe.log", "w") as f:
        f.write("\n".join(_lines))
