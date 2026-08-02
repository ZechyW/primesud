"""Per-module boot import cost on-device, measured in the first slot. [PRIMESUD]

The HP Prime auto-imports every .py in the app directory in REVERSE
alphabetical filename order, then the game starts when it reaches
``primesud``.  A file named ``zz_import_bench`` sorts ahead of every game
module, so this module body runs FIRST, with nothing from src/ loaded
yet.  It then walks the same reverse-alpha list the firmware would and
times each ``__import__``, reproducing the exact order (and therefore the
exact cost attribution) of a real boot.  When this body returns, the
firmware carries on down its own list: every module is already in
sys.modules, so those are fast no-ops, and ``primesud`` still launches the
game normally at the end.

What the numbers mean: each measurement is the FIRST-import closure cost
of that filename -- compile + module-level execution of the module itself
plus every not-yet-loaded dependency it pulls in.  It is an attribution,
not an isolated per-module cost: whichever module first imports ``config``
is charged for ``config``, exactly as the real boot charges it.  Read the
list as "where boot time goes", never as "what this file costs alone".

Deliberate omissions:
  - ``primesud`` is NOT imported -- its module level launches the game.
  - This module does not import itself.
  - No ``gc.collect()`` anywhere in the timing loop; natural boot GC
    behaviour is part of what is being measured.
  - ``util`` cannot be imported up front (it is one of the timed
    modules), so the loop collects RAW ints only and every number is
    rendered afterwards with ``util.int_str`` -- which also keeps bulk
    ``str(int)`` out of a hot loop (pitfall 8, str(int)-GC bug).

MODULES must track ``src/*.py``: reverse-alphabetical, minus ``primesud``.
Re-derive it whenever a module is added, removed, or renamed.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx + src/*.bin)
INCLUDING src/primesud.py -- unlike the other probes, this one wants the
real boot to continue.  Standing rule still applies: only ONE self-running
.py may be in the appdir, i.e. this bench OR loadworld_bench.py OR
keyidx_bench.py OR save_smoke.py etc., never more than one.  Results are
printed and written to zz_import_bench.log.
"""
import gc
from hpprime import eval as ppleval

LOG = "zz_import_bench.log"

# Reverse-alphabetical src/*.py minus primesud -- the firmware's own
# auto-import order.  Keep in sync with the directory listing.
MODULES = (
    "world", "util", "update", "training", "tml_prime", "tml",
    "terminal", "system_cmds", "stances", "special", "socials",
    "skills_table", "skill_utils", "shop", "scan", "recommend",
    "races", "quest", "prime_platform", "player", "picker", "path",
    "pager", "namegen", "music", "movement", "mobprog", "mob", "magic",
    "macros", "keyidx", "item", "inventory", "info", "hunt", "homes",
    "healer", "handler", "groups", "gquest", "game_time", "game_state",
    "explored", "effects", "economy", "debug", "config", "commands",
    "comm", "combat", "colors", "classes", "autoskill", "automap",
    "aliases",
)

TOP_N = 10

_out = []


def log(msg):
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def ticks():
    return int(ppleval("Ticks"))


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


def env_lines():
    """Raw interpreter identification strings, or a one-line failure note.

    ``sys`` is present but unverified on-device, so the whole probe is
    guarded.  Values are collected raw and logged later with everything
    else.

    Returns:
        list: str lines to log verbatim.
    """
    try:
        import sys
        lines = ["sys.version: " + sys.version]  # str-ok: already a str
        lines.append("sys.implementation: " + repr(sys.implementation))
        lines.append("sys.implementation._mpy: "
                     + repr(getattr(sys.implementation, "_mpy", "absent")))
        return lines
    except Exception as exc:
        return ["sys unavailable: " + repr(exc)]


def main():
    env = env_lines()

    # -- timing loop: raw ints only, no rendering, no gc.collect ----------
    results = []
    errors = []
    start_free = free()
    for name in MODULES:
        t0 = ticks()
        try:
            __import__(name)
            dt = ticks() - t0
        except Exception as exc:
            dt = -1
            errors.append((name, repr(exc)))
        results.append((name, dt, free()))
        # Progress only -- no int rendering, and after the measurement is
        # banked.  If the device dies mid-run the screen still shows how
        # far it got (the log file is only written once the loop ends).
        print(name)
    end_free = free()

    # -- rendering: util is resident now ---------------------------------
    from util import int_str

    log("zz_import_bench: per-module first-import cost at boot")
    for line in env:
        log(line)
    log("mem free start: " + int_str(start_free))
    log("modules: " + int_str(len(MODULES)))
    log("")

    total = 0
    failed = 0
    for name, dt, memfree in results:
        if dt < 0:
            failed += 1
            log("import " + name + ": FAILED (mem " + int_str(memfree) + ")")
            continue
        total += dt
        log("import " + name + ": " + int_str(dt) + "ms (mem "
            + int_str(memfree) + ")")

    log("")
    log("total import: " + int_str(total) + "ms over "
        + int_str(len(MODULES) - failed) + " modules")
    log("mem free end: " + int_str(end_free) + " (delta "
        + int_str(start_free - end_free) + ")")
    if failed:
        log("failures: " + int_str(failed))
        for name, msg in errors:
            log("  " + name + ": " + msg)

    log("")
    log("top " + int_str(TOP_N) + " by ms:")
    ranked = list(results)
    ranked.sort(key=lambda r: -r[1])
    for name, dt, _memfree in ranked[:TOP_N]:
        if dt < 0:
            continue
        log("  " + name + ": " + int_str(dt) + "ms")

    log("Done. Results in " + LOG)


main()
