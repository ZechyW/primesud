"""paths.idx parse timings on-device: split parse vs byte-walk. [PRIMESUD]

A/B probe for the byte-walk rewrite of info._parse_index.  The old
implementation split every line and int()'d every field, which put it on
the allocation floor documented in docs/PERFORMANCE.md secs. Recommend
scans / Boot load phase split (~0.5ms per small heap alloc at full game
heap); it measured ~4s per call before the parse got cached, i.e. one
stall the first time a player typed "path"/"run" in a session.

Scenario A is a frozen replica of that OLD split parse, copied verbatim
before the rewrite landed -- the same control trick loadworld_bench.py's
m_parse phase uses, so a device that has drifted (heap state, firmware,
battery) still shows an honest ratio.  Scenario B calls the SHIPPED
info._parse_index, with info._INDEX_CACHE reset inside the timed call
(one global store) so every pass does the real work instead of returning
the cache.

Both variants' results are tallied (S/X/V record counts plus vnum,
distance, direction and route-string checksums) and compared, so
correctness on-device is eyeballable from the log: the two lines must
match digit for digit.

Setup mirrors keyidx_bench.py: copy the REAL primesud.sav into this debug
appdir first (Connectivity Kit) -- it is only ever read, and it is what
makes the heap resemble mid-play conditions rather than a bare boot.
SAVE_VAR is redirected to "smoketest" before world.init_world(), and
SAVE_FILE to pathidx_bench.sav after load_world() has read the real file,
so nothing here can write the real save slot or file.  The probe runs
fine without a save, just at a lighter heap (logged as such).

Ship the full game closure (src/*.py + src/*.txt + src/*.idx + src/*.bin)
EXCEPT src/primesud.py (its module level launches the game); paths.idx in
particular must be present or there is nothing to parse.  Only ONE
self-running .py may be in the appdir (Prime auto-imports all): this
probe OR keyidx_bench.py OR loadworld_bench.py etc., never more than one.
Results printed and written to pathidx_bench.log, flushed line by line so
a hard reset keeps everything up to the crash point.

Scenarios (N=3 each, gc.collect before every timed pass):
  0 boot        -- load_world() timing + heap context
  1 parse_split -- frozen replica of the pre-rewrite split parse
  2 parse_walk  -- shipped info._parse_index (byte-walk), cache defeated
  3 tallies     -- record counts + checksums from both, must agree
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
import info  # noqa: E402

LOG = "pathidx_bench.log"
N = 3

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
        + "ms avg=" + int_str(total // n) + "ms total="
        + int_str(total) + "ms")
    return result


def parse_split():
    """Frozen replica of the pre-rewrite info._parse_index parse loop.

    Verbatim copy of the split()/int() body (minus the module-level
    cache, which the timed comparison must not short-circuit), kept here
    as a permanent A/B control.  Do NOT "modernise" it.
    """
    segs = {}
    xedges = {}
    slivers = set()
    with open(info.PATH_INDEX_FILE) as f:
        data = f.read()
    for line in data.split("\n"):
        if not line or line[0] == "#":
            continue
        parts = line.split("|")
        if parts[0] == "S":
            segs.setdefault(int(parts[1]), []).append(
                (int(parts[2]), int(parts[3]), parts[4]))
        elif parts[0] == "X":
            xedges.setdefault(int(parts[1]), []).append(
                (parts[2], int(parts[3])))
        elif parts[0] == "V":
            slivers.add(int(parts[1]))
    return segs, xedges, slivers


def parse_walk():
    """Shipped info._parse_index with its cache defeated per pass."""
    info._INDEX_CACHE = None
    return info._parse_index()


def tally(parsed):
    """Record counts and content checksums for an A/B comparison.

    Returns:
        tuple: (s_keys, s_rows, s_sum, dirs_sum, x_keys, x_rows, x_sum,
            v_count, v_sum) -- pure ints, so the log lines from the two
            parse variants must match character for character.
    """
    segs, xedges, slivers = parsed
    s_rows = 0
    s_sum = 0
    dirs_sum = 0
    for entry in segs:
        for row in segs[entry]:
            s_rows += 1
            s_sum += entry + row[0] + row[1]
            for byte in row[2].encode():
                dirs_sum += byte
    x_rows = 0
    x_sum = 0
    for exit_vnum in xedges:
        for row in xedges[exit_vnum]:
            x_rows += 1
            x_sum += exit_vnum + row[1] + ord(row[0])
    v_sum = 0
    for vnum in slivers:
        v_sum += vnum
    return (len(segs), s_rows, s_sum, dirs_sum, len(xedges), x_rows,
            x_sum, len(slivers), v_sum)


def log_tally(label, counts):
    log(label + ": S keys=" + int_str(counts[0]) + " rows="
        + int_str(counts[1]) + " sum=" + int_str(counts[2]) + " dirs="
        + int_str(counts[3]))
    log(label + ": X keys=" + int_str(counts[4]) + " rows="
        + int_str(counts[5]) + " sum=" + int_str(counts[6])
        + " | V count=" + int_str(counts[7]) + " sum="
        + int_str(counts[8]))


def main():
    gc.collect()
    log("pathidx_bench: paths.idx split parse vs byte-walk parse")
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
    game_state.SAVE_FILE = "pathidx_bench.sav"

    player = world.chars[1]
    log("player: level=" + int_str(player.get("level", 1))
        + " room=" + int_str(player.get("room", 0))
        + " areas=" + int_str(len(world._LOADED_AREAS)))

    gc.collect()
    log("mem free after boot: " + int_str(free()))

    try:
        with open(info.PATH_INDEX_FILE) as f:
            size = len(f.read())
    except Exception:
        size = 0
    if not size:
        log("index: " + info.PATH_INDEX_FILE + " missing or empty -- copy"
            + " src/paths.idx into this appdir")
        return
    log("index: " + info.PATH_INDEX_FILE + " " + int_str(size) + " bytes")

    old = timed("parse_split", parse_split)
    gc.collect()
    log("mem free after parse_split: " + int_str(free()))

    new = timed("parse_walk", parse_walk)
    gc.collect()
    log("mem free after parse_walk: " + int_str(free()))

    old_counts = tally(old)
    new_counts = tally(new)
    log_tally("parse_split", old_counts)
    log_tally("parse_walk ", new_counts)
    log("agree: " + ("yes" if old_counts == new_counts else "NO -- MISMATCH"))

    # Leave the shipped cache holding a correct parse, not a bench artefact.
    info._INDEX_CACHE = None

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
