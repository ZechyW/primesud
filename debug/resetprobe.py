"""Reset-phase timing probe: fresh + reload reset cost, spawn micro-bench. [PRIMESUD]

Run standalone on physical HP Prime (same transfer bundle as loadprobe;
remove loadprobe.py first -- Prime auto-imports every .py).  Restart the
Python app first so the heap is fresh.

Before the 25/07 reset optimisations (create_mobile merge-into-base diet +
_mob_count_maps replacing per-M-reset world.chars scans): fresh newthalos
total=7337ms reset=4473, reload reset ~1050ms, create_mobile 3160us each.
The fresh "reset" number includes the cross-pulled midgaard's full
read+exec+reset (loads triggered inside the reset drain land in the
wrapper); reload cycles are the clean per-area comparison.

Passes: fresh load, then two unload+reload cycles, then 50x
create_mobile / create_object micro-loops for per-spawn cost, then
component micros (_char_base, dict copy, MOB_DEFS lookup, race_lookup)
to attribute create_mobile's per-call cost.
Results printed and written to resetprobe.log.
"""
import gc
from hpprime import eval as ppleval

import world
import mob
import item

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


def cycle(tag, label):
    world._unload_area(tag)
    gc.collect()
    _reset_ms[0] = 0
    t0 = ticks()
    world._load_area(tag)
    t_total = ticks() - t0
    nmobs = 0
    for c in world.chars.values():
        if c.get("is_npc"):
            nmobs += 1
    log(label + ": total=" + str(t_total) + "ms reset=" + str(_reset_ms[0])
        + " mobs=" + str(nmobs) + " free=" + str(free()))


def micro(label, fn, arg, n):
    gc.collect()
    t0 = ticks()
    if arg is None:
        for _ in range(n):
            fn()
    else:
        for _ in range(n):
            fn(arg)
    dt = ticks() - t0
    log(label + " x" + str(n) + ": " + str(dt) + "ms ("
        + str(dt * 1000 // n) + "us each)")


def run():
    world.init_world()
    big = world._AREA_FILES[-1][1]
    log("target: " + big + " free=" + str(free()))

    gc.collect()
    _reset_ms[0] = 0
    t0 = ticks()
    world._load_area(big)
    log("fresh: total=" + str(ticks() - t0) + "ms reset="
        + str(_reset_ms[0]) + " free=" + str(free()))

    cycle(big, "reload0")
    cycle(big, "reload1")

    mob_tpl = None
    for c in world.chars.values():
        if c.get("is_npc"):
            mob_tpl = c["tpl"]
            break
    item_vnum = None
    for rs in world.rooms.values():
        for o in rs.get("items", []):
            if isinstance(o, dict):
                item_vnum = o["vnum"]
                break
        if item_vnum is not None:
            break
    if mob_tpl is not None:
        micro("create_mobile(" + str(mob_tpl) + ")",
              mob.create_mobile, mob_tpl, 50)
    if item_vnum is not None:
        micro("create_object(" + str(item_vnum) + ")",
              item.create_object, item_vnum, 50)

    # Component attribution for create_mobile's per-call cost.
    micro("_char_base", mob._char_base, None, 50)
    _snap = mob._char_base()
    micro("dict(base-copy)", dict, _snap, 50)
    if mob_tpl is not None:
        micro("MOB_DEFS[tpl]", world.MOB_DEFS.__getitem__, mob_tpl, 50)
        _race = world.MOB_DEFS[mob_tpl].get("race", "Human")
        micro("race_lookup(" + _race + ")", mob.race_lookup, _race, 50)


try:
    run()
finally:
    with open("resetprobe.log", "w") as f:
        f.write("\n".join(_lines))
