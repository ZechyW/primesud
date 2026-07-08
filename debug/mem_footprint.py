"""Measure on-device heap cost of skills_table/groups/classes imports.

Run standalone on physical HP Prime (same dir as the game modules, so
imports resolve). Results printed and written to memtest.log.

Import order isolates each module's cost: deps first (config, races),
then skills_table (149 skills), then classes, then groups.

IMPORTANT: module imports are cached for the whole Python session; a
cached import costs ~0 bytes and reports nothing useful. Run this as the
FIRST Python program after (re)entering the Python app. The script
detects cached modules (sys.modules if available, plus import timing --
a fresh 74KB parse takes visible ms, a cached one ~0ms) and flags them.
"""
import gc
from hpprime import eval as ppleval

_lines = []


def log(msg):
    print(msg)
    _lines.append(msg)


def free():
    gc.collect()
    return gc.mem_free()


def ticks():
    return int(ppleval("Ticks"))


def check_cached(names):
    try:
        import sys
    except ImportError:
        log("(no sys module; relying on import timing to spot caching)")
        return
    cached = [n for n in names if n in sys.modules]
    if cached:
        log("STALE RUN: already imported: " + str(cached))
        log("restart Python app and re-run for real numbers")


def run():
    if not hasattr(gc, "mem_free"):
        log("gc.mem_free missing; dir(gc)=" + str(dir(gc)))
        return
    check_cached(["config", "races", "skills_table", "classes", "groups"])
    f0 = free()
    log("baseline free=" + str(f0))

    t0 = ticks()
    import config
    import races
    dt = ticks() - t0
    f1 = free()
    log("deps config+races: cost=" + str(f0 - f1) + " (" + str(dt) + "ms)")

    t0 = ticks()
    import skills_table
    dt = ticks() - t0
    f2 = free()
    log("skills_table: cost=" + str(f1 - f2) + " (" + str(dt) + "ms)")

    t0 = ticks()
    import classes
    dt = ticks() - t0
    f3 = free()
    log("classes: cost=" + str(f2 - f3) + " (" + str(dt) + "ms)")

    t0 = ticks()
    import groups
    dt = ticks() - t0
    f4 = free()
    log("groups: cost=" + str(f3 - f4) + " (" + str(dt) + "ms)")

    log("total cost=" + str(f0 - f4) + " free=" + str(f4))


try:
    run()
finally:
    with open("memtest.log", "w") as f:
        f.write("\n".join(_lines))
