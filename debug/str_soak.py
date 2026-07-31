"""Post-sweep heap soak: real num_str/sstr paths under storm+collect. [PRIMESUD]

Validates the 01/08 bare-str() sweep (0de25e7) on the physical G1: the
28 Jul soak numbers predate it, and the sweep touched the two
str(int)-in-loop sites the static audits had missed (route RLE builder
in info.py, mobprog trace).  Each phase piles fresh garbage through the
REAL src code paths, drops it, then takes an explicit gc.collect() --
the documented death roll (~25-30%/collect in probe-era conditions, so
~70 clean collects here beats the prior 60-collect cachedstr standard).

Phases (log() rewrites the file per call, so everything up to a death
survives; each phase ends with a canary scan for delayed
type-confusion, the save_bench-13 failure mode):

  A  route hammer -- info._route to every area tag from a rotating
     source room: Dijkstra dict/tuple churn + _compress_path/_merge_runs
     RLE strings via num_str, ~49 routes per iteration, collect per
     iteration.  This is missed tier-A site #1 exercised for real.
  B  ncache overflow -- >4096 fresh ints through util.num_str per
     iteration forces the _NCACHE clear-and-rebuild (4096 small strings
     dumped at once), then collect: the TODO.md second-order residual,
     rolled deliberately 20 times.
  C  sstr storm -- save-shaped lines built from mixed int/str/None/bool
     tokens through util.sstr, drop, collect.
  D  save drive -- real save_world passes (redirected slot) with
     gameplay-shaped churn gaps and an explicit collect after each:
     re-validates the serializer + threshold-gated post-save collect on
     post-sweep code.

If it dies, record the SYMPTOM first: hard reset vs uninterruptible
stall vs impossible TypeError discriminates the bug family
(docs/PRIME_FIRMWARE_BUGS.md sec. Manifestation spectrum); the last
".." line in str_soak.log bounds where.

Ship the full game closure (src/*.py + *.txt + *.idx) in the appdir
alongside this probe -- EXCEPT src/primesud.py (its module level
launches the game).  Only self-running .py in the appdir must be this
probe (swap save_smoke.py out).  Safety: SAVE_VAR is redirected to
"soaktest" before load_world and SAVE_FILE to str_soak.sav; the real
primesud.sav copy is only read.  Results in str_soak.log.
"""
import gc

import terminal

ROUTE_ITERS = 20
NCACHE_ITERS = 20
SSTR_ITERS = 20
DRIVE_SAVES = 10
CHURN_BYTES = 120000  # per-save gameplay-shaped garbage gap in phase D


class _TRStub:
    """Swallow tprint/dbg output -- probe runs without a real terminal."""

    def print(self, *args, **kwargs):
        pass

    def set_status(self, text):
        pass


terminal.tr = _TRStub()

from prime_platform import ticks, hvars_set  # noqa: E402
from config import R_STARTING_ROOM  # noqa: E402
import util  # noqa: E402
from util import int_str, num_str, sstr  # noqa: E402
import world  # noqa: E402
import game_state  # noqa: E402
from info import _route  # noqa: E402
from player import create_char  # noqa: E402

LOG = "str_soak.log"

_out = []


def log(msg):
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


# Resident canary: known (int, str) pairs held live all run.  A scan
# mismatch after a phase = delayed type-confusion in data (the
# save_bench-13 signature) even if nothing crashed.
CANARY = []


def build_canary():
    for i in range(200):
        CANARY.append((i * 7, int_str(i * 7)))


def scan_canary(tag):
    bad = 0
    for i in range(len(CANARY)):
        e = CANARY[i]
        ok = (isinstance(e, tuple) and len(e) == 2
              and isinstance(e[0], int) and isinstance(e[1], str)
              and e[0] == i * 7 and e[1] == int_str(i * 7))
        if not ok:
            bad += 1
            if bad <= 5:
                log("CANARY " + tag + ": elem " + int_str(i) + " -> "
                    + str(type(e)))
    log("canary " + tag + ": " + int_str(bad) + " bad of "
        + int_str(len(CANARY)))


def churn(target):
    """Burn ~target bytes of combat-message-shaped garbage (validated
    render path: int_str + concat), the save_smoke churn-gap shape."""
    if not hasattr(gc, "mem_free"):
        return 0
    start = free()
    low = start
    lines = []
    n = 0
    while True:
        f = free()
        if f < low:
            low = f
        if start - f >= target or f > low + 1024:
            return start - low
        n += 1
        v = n % 997
        lines.append("You hit a beggar for " + int_str(v) + " damage.")
        lines.append("{R" + int_str(v) + "/" + int_str(v + 5) + "hp {M"
                     + int_str(v * 3) + "mn{x")
        if len(lines) > 32:
            lines = []


def phase_route(player, tags):
    log("-- phase A: route hammer (" + int_str(ROUTE_ITERS)
        + " iters x " + int_str(len(tags)) + " tags)")
    sources = sorted(world.rooms)
    step = len(sources) // ROUTE_ITERS
    if step < 1:
        step = 1
    home = player.get("room")
    for it in range(ROUTE_ITERS):
        src_room = sources[(it * step) % len(sources)]
        player["room"] = src_room
        n_ok = 0
        n_none = 0
        chars = 0
        t0 = ticks()
        for tag in tags:
            route, steps = _route(player, tag)
            if route is None:
                n_none += 1
            else:
                n_ok += 1
                chars += len(route)
        log(".. A " + int_str(it + 1) + "/" + int_str(ROUTE_ITERS)
            + " src " + int_str(src_room) + ": " + int_str(n_ok)
            + " routes (" + int_str(chars) + "ch, " + int_str(n_none)
            + " unreachable) " + int_str(ticks() - t0) + "ms")
        gc.collect()
        log(".. A " + int_str(it + 1) + " collect ok, free "
            + int_str(free()))
    player["room"] = home
    scan_canary("A")


def phase_ncache():
    log("-- phase B: ncache overflow (" + int_str(NCACHE_ITERS)
        + " iters x 4200 fresh ints)")
    for it in range(NCACHE_ITERS):
        base = 1000000 + it * 5000
        lines = []
        for i in range(4200):
            lines.append("hp " + num_str(base + i) + "/" + num_str(base))
            if len(lines) > 32:
                lines = []
        lines = None
        log(".. B " + int_str(it + 1) + "/" + int_str(NCACHE_ITERS)
            + " cache " + int_str(len(util._NCACHE)))
        gc.collect()
        log(".. B " + int_str(it + 1) + " collect ok, free "
            + int_str(free()))
    scan_canary("B")


def phase_sstr():
    log("-- phase C: sstr storm (" + int_str(SSTR_ITERS)
        + " iters x 3000 mixed tokens)")
    for it in range(SSTR_ITERS):
        lines = []
        parts = []
        for i in range(3000):
            m = i % 4
            if m == 0:
                v = it * 3000 + i
            elif m == 1:
                v = "tok"
            elif m == 2:
                v = None
            else:
                v = True
            parts.append(sstr(v))
            if len(parts) >= 24:
                lines.append("|".join(parts))
                parts = []
                if len(lines) > 32:
                    lines = []
        lines = None
        parts = None
        log(".. C " + int_str(it + 1) + "/" + int_str(SSTR_ITERS) + " ok")
        gc.collect()
        log(".. C " + int_str(it + 1) + " collect ok, free "
            + int_str(free()))
    scan_canary("C")


def phase_saves():
    log("-- phase D: save drive (" + int_str(DRIVE_SAVES)
        + " saves, churn gaps, explicit collect each)")
    game_state.SAVE_FILE = "str_soak.sav"
    for i in range(DRIVE_SAVES):
        b = churn(CHURN_BYTES)
        log(".. D " + int_str(i + 1) + "/" + int_str(DRIVE_SAVES)
            + " churned " + int_str(b) + "B, free " + int_str(free()))
        t0 = ticks()
        ok = game_state.save_world(quiet=True)
        log(".. D " + int_str(i + 1) + " save ok=" + str(ok) + " "
            + int_str(ticks() - t0) + "ms")
        gc.collect()
        log(".. D " + int_str(i + 1) + " collect ok, free "
            + int_str(free()))
    scan_canary("D")


def main():
    log("str_soak: post-sweep heap soak (route/ncache/sstr/save)")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    game_state.SAVE_VAR = "soaktest"

    world.init_world()  # before create_char: its reset_lazy clears chars
    player = create_char()
    player["_macros"] = {}
    player["room"] = R_STARTING_ROOM
    world.chars[1] = player

    t0 = ticks()
    src = game_state.load_world()
    log("load_world: " + int_str(ticks() - t0) + "ms source=" + str(src))
    if not world.rooms:
        # Fresh state (no sav): load the starting area so phase A has
        # source rooms and the save drive has resident content.
        world._load_area(world._vnum_to_tag(R_STARTING_ROOM))
    log("areas loaded: " + int_str(len(world._LOADED_AREAS))
        + ", rooms " + int_str(len(world.rooms))
        + ", free " + int_str(free()))

    build_canary()
    tags = []
    for _fname, tag, _name, _lo, _hi in world._AREA_FILES:
        tags.append(tag)

    phase_route(player, tags)
    phase_ncache()
    phase_sstr()
    phase_saves()

    try:
        hvars_set("soaktest", "0")
        hvars_set("soaktest_bak", "0")
    except Exception:
        pass
    log("mem free end: " + int_str(free()))
    log("Done. Results in " + LOG)


main()
