"""Keyword-index scan timings on-device: mobs.bin / objs.bin. [PRIMESUD]

Companion probe to the KX01 binary re-shape of the last two hot text
indexes (design in DESIGN.md sec. Lazy area loading, "Keyword indexes").
Times the non-interactive scan core the consumers sit on --
keyidx.load() + keyidx.candidates() and the full record walk that
info._mob_stats does -- so exact numbers come out of a log with zero
player action. _mob_stats itself is NOT called (tpage blocks on keys) and
neither is magic._find_unloaded_mob (it loads areas, which would swamp
the numbers being measured).

Setup mirrors recommend_bench.py: copy the REAL primesud.sav into this
debug appdir first (Connectivity Kit) -- it is only read. SAVE_VAR is
redirected to "smoketest" before world.init_world()/load_world();
SAVE_FILE to keyidx_bench.sav after, so nothing here can touch the real
save slot or file.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx + src/*.bin)
EXCEPT src/primesud.py (its module level launches the game).  Only ONE
self-running .py may be in the appdir (Prime auto-imports all): this
probe OR recommend_bench.py OR save_smoke.py etc., never more than one.
Results printed and written to keyidx_bench.log, flushed line by line so
a hard reset keeps everything up to the crash point.

Scenarios (N=3 each, gc.collect before every timed pass):
  1 boot           -- load_world() timing + player context lines
  2 mob_find_hit   -- load("mobs.bin") + candidates("guard")
  3 mob_find_miss  -- same with "xyzzyq": full find sweep, zero hits
  4 obj_find       -- load("objs.bin") + candidates("sword")
  5 mob_stats_walk -- _mob_stats' record walk over a seeded counts dict
"""
import gc

import terminal

terminal.init_terminal()

from prime_platform import ticks, hvars_set  # noqa: E402
from util import int_str  # noqa: E402
from config import R_STARTING_ROOM  # noqa: E402
import world  # noqa: E402
import game_state  # noqa: E402
from player import create_char  # noqa: E402
import keyidx  # noqa: E402

LOG = "keyidx_bench.log"
N = 3

# Real mob vnums sampled evenly across the shipped mobs.bin (30 of 1003),
# so the counters walk resolves hits spread over the whole record region.
# Re-sample with tools/dump_key_bin.py if the index is rebuilt.
_STAT_VNUMS = (303, 9404, 8312, 5101, 6317, 6516, 2108, 2225, 1601, 7805,
               5204, 9304, 3704, 1116, 9219, 8713, 4001, 5300, 5333, 611,
               2309, 7008, 10418, 10452, 1313, 1346, 3020, 3100, 9514,
               9547)

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


def timed(label, fn, n=N):
    """Run fn() n times (gc.collect untimed before each), log per-pass and
    aggregate ms; returns the last fn() result for sanity logging."""
    total = 0
    mx = 0
    mn = 999999999
    result = None
    for i in range(n):
        gc.collect()
        t0 = ticks()
        result = fn()
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
        log(".. " + label + " pass " + int_str(i + 1) + "/" + int_str(n)
            + " " + int_str(dt) + "ms")
    log(label + ": min=" + int_str(mn) + "ms max=" + int_str(mx)
        + "ms avg=" + int_str(total // n) + "ms")
    return result


def _find(fname, target):
    """One consumer-shaped lookup: whole-file read plus name scan."""
    index = keyidx.load(fname)
    if index is None:
        return None
    data, meta = index
    return keyidx.candidates(data, meta, target)


def scenario_find(label, fname, target):
    rows = timed(label, lambda: _find(fname, target))
    if rows is None:
        log(label + ": index " + fname + " missing or malformed")
    else:
        log(label + ": " + int_str(len(rows)) + " candidates for " + target)


def _stats_walk(fname, counts):
    """Replica of info._mob_stats' metadata walk (that function itself
    ends in tpage, which blocks on a keypress)."""
    index = keyidx.load(fname)
    if index is None:
        return None
    data, meta = index
    kw_off = meta[1]
    strings_off = meta[2]
    tags = meta[4]
    metadata = {}
    pos = meta[0]
    while pos < kw_off:
        vnum = data[pos] | data[pos + 1] << 8
        if vnum in counts:
            name_off = strings_off + (data[pos + 7] | data[pos + 8] << 8)
            metadata[vnum] = (
                data[name_off:name_off + data[pos + 9]].decode(),
                data[pos + 2], tags[data[pos + 3]])
        pos += 11 + data[pos + 10]
    return metadata


def main():
    gc.collect()
    log("keyidx_bench: mobs.bin / objs.bin scan timings")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    game_state.SAVE_VAR = "smoketest"

    world.init_world()

    player = create_char()
    player["_macros"] = {}
    player["room"] = R_STARTING_ROOM
    world.chars[1] = player

    t0 = ticks()
    src = game_state.load_world()
    dt = ticks() - t0
    log("boot: load_world " + int_str(dt) + "ms source=" + str(src))  # str-ok
    game_state.SAVE_FILE = "keyidx_bench.sav"

    player = world.chars[1]
    log("player: level=" + int_str(player.get("level", 1))
        + " room=" + int_str(player.get("room", 0))
        + " areas=" + int_str(len(world._LOADED_AREAS)))

    gc.collect()
    log("mem free after boot: " + int_str(free()))

    scenario_find("mob_find_hit", "mobs.bin", "guard")
    gc.collect()
    scenario_find("mob_find_miss", "mobs.bin", "xyzzyq")
    gc.collect()
    scenario_find("obj_find", "objs.bin", "sword")
    gc.collect()
    log("mem free after finds: " + int_str(free()))

    counts = {}
    for vnum in _STAT_VNUMS:
        counts[vnum] = 3
    metadata = timed("mob_stats_walk",
                     lambda: _stats_walk("mobs.bin", counts))
    log("mob_stats_walk: " + int_str(len(metadata) if metadata else 0)
        + " of " + int_str(len(counts)) + " vnums resolved")
    gc.collect()
    log("mem free after walk: " + int_str(free()))

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
