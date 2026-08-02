"""Phase-split of game_state.load_world()'s boot cost on-device. [PRIMESUD]

keyidx_bench-1.log measured "boot: load_world 13003ms" against the real
save on a G1 but gave no breakdown.  This probe re-runs the same boot
with the interior decomposed into attributable segments, so the
optimization wave that follows knows which part to attack.

The save under test (debug appdir primesud.sav, ~27KB / 194 "~" lines)
contains 39 "it.*" item-snapshot lines (~14KB of encoded records, decoded
by world._snap_decode -- a recursive per-char string walker), one "m="
line with 344 mob entries, and zero "r.*.items" lines, so load_world's
pending-token prewarm loop is a no-op for this save.  The trailing
``player["room"] not in world.rooms`` membership test is NOT free: it
triggers a full lazy _load_area of the starting area (player room 2133),
and big-area loads are a 6-11s class on G1 (docs/PERFORMANCE.md sec.
Area loading).  Phase 5 isolates exactly that.

Setup mirrors keyidx_bench.py: copy the REAL primesud.sav into this debug
appdir first (Connectivity Kit) -- it is only ever read.  SAVE_VAR is
redirected to "smoketest" before world.init_world(); SAVE_FILE to
loadworld_bench.sav only after load_world() has read the real file, so
nothing here can write the real save slot or file.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx + src/*.bin)
EXCEPT src/primesud.py (its module level launches the game).  Only ONE
self-running .py may be in the appdir (Prime auto-imports all): this
probe OR keyidx_bench.py OR recommend_bench.py OR save_smoke.py etc.,
never more than one.  Results printed and written to loadworld_bench.log,
flushed line by line so a hard reset keeps everything up to the crash
point.

Phases (N=3 where repeats are meaningful, once where they are not):
  1 read            -- open + f.read() of the save file
  2 split           -- data.split("~")
  3 snap_decode     -- world._snap_decode over every "it.*" record
  4 m_parse         -- replica of load_world's "m=" branch
  5 area_load       -- ONCE: ``room_vnum in world.rooms`` (lazy area load)
  6 load_world_rest -- ONCE: the real load_world(), player area already
                       resident, so this is everything BUT the area load
  7 cross-check     -- phases 5 + 6 should land near the 13,003ms G1
                       baseline from keyidx_bench-1.log (same save, same
                       device); phases 1-4 attribute the parse interior.

Phases 1-4 are pure: they decode/parse into throwaway locals and never
touch world.ITEM_SNAPSHOTS, world._SNAP_ENC_CACHE, world._PENDING_MOB_CACHE
or world._pending_mob_saves, so phase 6 still does the full real work.

One bench-only state divergence: pre-loading the player's area in phase 5
means the "m=" pending mob deltas for that area are not applied when
load_world runs in phase 6 (_load_area already ran, and it is what applies
them).  Harmless here -- the save slot and save file are both redirected,
so the resulting world state is never persisted or played.
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

LOG = "loadworld_bench.log"
N = 3

# Index of "room" within game_state._PLAYER_NUMBER_SAVE_KEYS, i.e. field 9
# of the "p.n=" pipe-packed line.  Hardcoded rather than imported: the
# tuple is private and importing it would let a reorder silently pass.
_PN_ROOM_INDEX = 9

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


def timed_once(label, fn):
    """Run fn() exactly once (gc.collect untimed first); log ms.

    For the two phases whose cost is inherently first-run-only: a lazy
    area load and the load_world() that follows it are resident no-ops on
    a repeat pass, so an average over N would be meaningless.

    Returns:
        tuple: (fn() result, elapsed ms).
    """
    gc.collect()
    t0 = ticks()
    result = fn()
    dt = ticks() - t0
    log(label + ": " + int_str(dt) + "ms")
    return result, dt


def _read_save():
    with open(game_state.SAVE_FILE, "r") as f:
        return f.read()


def _collect_snapshots(lines):
    """Encoded "it.*" records (the part after the revision prefix)."""
    records = []
    for line in lines:
        if not line.startswith("it.") or "=" not in line:
            continue
        _key, val = line.split("=", 1)
        if "|" in val:
            records.append(val.split("|", 1)[1])
    return records


def _decode_snapshots(records):
    """Decode every collected record into a throwaway local. [PRIMESUD]

    Deliberately does NOT store into world.ITEM_SNAPSHOTS /
    world._SNAP_ENC_CACHE, so phase 6 still pays the real decode.
    """
    count = 0
    for enc in records:
        _record = world._snap_decode(enc)
        count += 1
    return count


def _find_line_value(lines, prefix):
    """Value of the first line starting with prefix, or None."""
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):]
    return None


def _parse_m(val):
    """Replica of load_world's "m" branch, into a throwaway dict."""
    saves = {}
    for entry in val.split(";"):
        if "," in entry:
            tpl, rooms = entry.split(",", 1)
            _tpl_i = int(tpl)
            _rl = [int(r) for r in rooms.split("|") if r]
            saves[_tpl_i] = _rl
    return len(saves)


def main():
    gc.collect()
    log("loadworld_bench: load_world() phase split")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    # SAVE_FILE stays pointed at the real primesud.sav until phase 6 has
    # read it (see below).
    game_state.SAVE_VAR = "smoketest"

    world.init_world()

    player = create_char()
    player["_macros"] = {}
    player["room"] = R_STARTING_ROOM
    world.chars[1] = player

    gc.collect()
    log("mem free after init_world: " + int_str(free()))

    # -- Phase 1: file read ------------------------------------------------
    data = timed("read", _read_save)
    if not data:
        log("read: NO SAVE DATA -- copy the real primesud.sav in first")
        return
    log("read: " + int_str(len(data)) + " bytes")

    # -- Phase 2: line split -----------------------------------------------
    lines = timed("split", lambda: data.split("~"))
    log("split: " + int_str(len(lines)) + " lines")

    gc.collect()
    log("mem free after read+split: " + int_str(free()))

    # -- Phase 3: item-snapshot decode -------------------------------------
    records = _collect_snapshots(lines)
    enc_bytes = 0
    for enc in records:
        enc_bytes += len(enc)
    decoded = timed("snap_decode", lambda: _decode_snapshots(records))
    log("snap_decode: " + int_str(decoded) + " records, "
        + int_str(enc_bytes) + " encoded bytes")

    gc.collect()
    log("mem free after snap_decode: " + int_str(free()))

    # -- Phase 4: pending mob line -----------------------------------------
    m_val = _find_line_value(lines, "m=")
    if m_val is None:
        log("m_parse: no 'm=' line in this save")
    else:
        entries = timed("m_parse", lambda: _parse_m(m_val))
        log("m_parse: " + int_str(entries) + " mob entries, "
            + int_str(len(m_val)) + " bytes")

    gc.collect()
    log("mem free after m_parse: " + int_str(free()))

    # -- Phase 5: the player's lazy area load ------------------------------
    # Field 9 of "p.n=" is the "room" key of _PLAYER_NUMBER_SAVE_KEYS.
    rv = None
    pn_val = _find_line_value(lines, "p.n=")
    if pn_val is not None:
        _parts = pn_val.split("|")
        if len(_parts) > _PN_ROOM_INDEX:
            try:
                rv = int(_parts[_PN_ROOM_INDEX])
            except ValueError:
                rv = None
    if rv is None:
        log("area_load: could not read saved room vnum from 'p.n='")
        area_ms = 0
    else:
        tag = world._vnum_to_tag(rv)
        log("area_load: saved room=" + int_str(rv) + " area="
            + (tag if tag else "?")
            + " loaded_before=" + int_str(len(world._LOADED_AREAS)))
        present, area_ms = timed_once("area_load",
                                      lambda: rv in world.rooms)
        log("area_load: present=" + ("yes" if present else "no")
            + " loaded_after=" + int_str(len(world._LOADED_AREAS)))

    gc.collect()
    log("mem free after area_load: " + int_str(free()))

    # -- Phase 6: everything else load_world does --------------------------
    # The player's area is resident now, so this pass measures the parse
    # loop + snapshot decode-and-store + m parse + pending-token prewarm
    # (0 rooms for this save) + pet spawn, but NOT the area load.
    src, rest_ms = timed_once("load_world_rest", game_state.load_world)
    # Real save file has now been read for the last time -- redirect so
    # any later write lands in a scratch file.
    game_state.SAVE_FILE = "loadworld_bench.sav"
    log("load_world_rest: source=" + str(src)  # str-ok
        + " areas=" + int_str(len(world._LOADED_AREAS))
        + " snapshots=" + int_str(len(world.ITEM_SNAPSHOTS)))

    player = world.chars[1]
    log("player: level=" + int_str(player.get("level", 1))
        + " room=" + int_str(player.get("room", 0)))

    gc.collect()
    log("mem free after load_world: " + int_str(free()))

    # -- Phase 7: cross-check ----------------------------------------------
    log("cross-check: area_load + load_world_rest = "
        + int_str(area_ms + rest_ms) + "ms (keyidx_bench-1.log G1 baseline"
        + " for the same save: 13003ms)")

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
