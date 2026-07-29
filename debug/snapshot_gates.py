"""Item-snapshot device gates: heap soak, corrective load, snapshot prog. [PRIMESUD]

Runs the three remaining hardware gates from TODO.md sec. Items against the
real game world (DESIGN.md sec. Item template snapshots):

  gate 1  heap across travel/eviction cycles -- tours ~13 areas x 4 cycles
          through maybe_evict (AREA_CACHE_MAX=12 forces evictions each
          cycle); per-cycle mem_free after gc.collect should flatten, not
          drift down.
  gate 2  one content-revision mismatch causes exactly ONE corrective
          load -- a carried foreign item's ITEM_SNAPSHOTS entry is poisoned
          to a stale revision, then item_tpl(vnum) must load only the
          owning area and leave the vnum resident.
  gate 3  snapshot obj program fires from an unloaded owner -- a prog
          source is injected into the item's snapshot entry and
          mobprog._run_oprog must run it via the snapshot fallback without
          the owner area loading.

Setup mirrors save_smoke.py: copy the REAL primesud.sav into this debug
appdir first (Connectivity Kit) -- it is only read.  SAVE_VAR is redirected
to "smoketest" BEFORE load_world and SAVE_FILE to snapshot_gates.sav after,
so the game's real HVar/save are never written.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx) EXCEPT
src/primesud.py (its module level launches the game).  Only ONE
self-running .py may be in the appdir (Prime auto-imports all): this probe
OR save_smoke.py, not both.  Results printed and written to
snapshot_gates.log.
"""
import gc

import terminal


class _TRStub:
    """Swallow tprint/dbg output -- probe runs without a real terminal."""

    def print(self, *args, **kwargs):
        pass


terminal.tr = _TRStub()

from prime_platform import ticks, hvars_set  # noqa: E402
from util import int_str  # noqa: E402
from config import R_STARTING_ROOM  # noqa: E402
import world  # noqa: E402
import game_state  # noqa: E402
import mobprog  # noqa: E402
from item import create_object  # noqa: E402
from player import create_char  # noqa: E402

LOG = "snapshot_gates.log"
CYCLES = 4
AREA_STEP = 4  # every 4th area file -> ~13 of 49, spread over vnum space
PROG_VNUM = 999901  # outside every area's vnum range

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


def _first_room(lo, hi):
    """Lowest loaded room vnum in [lo, hi], or -1."""
    best = -1
    for rv in world.ROOM_DEFS._data:
        if lo <= rv <= hi and (best < 0 or rv < best):
            best = rv
    return best


def _pick_item_area(exclude):
    """First area file (not in exclude) that defines items; loads it.

    Returns:
        (tag, item_vnum) or (None, -1).
    """
    for entry in world._AREA_FILES:
        tag = entry[1]
        lo = entry[3]
        hi = entry[4]
        if tag in exclude:
            continue
        world._ensure_area_by_tag(tag)
        best = -1
        for v in world.ITEM_DEFS._data:
            if lo <= v <= hi and (best < 0 or v < best):
                best = v
        if best >= 0:
            return tag, best
    return None, -1


def main():
    gc.collect()
    log("snapshot_gates: item-snapshot device gates")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    game_state.SAVE_VAR = "smoketest"

    world.init_world()  # before create_char: its reset_lazy clears chars

    player = create_char()
    player["_macros"] = {}
    player["room"] = R_STARTING_ROOM
    world.chars[1] = player

    t0 = ticks()
    src = game_state.load_world()
    log("load_world: " + int_str(ticks() - t0) + "ms source=" + str(src))
    log("areas loaded: " + int_str(len(world._LOADED_AREAS))
        + ", snapshots: " + int_str(len(world.ITEM_SNAPSHOTS)))
    game_state.SAVE_FILE = "snapshot_gates.sav"

    own_tag = world._vnum_to_tag(player["room"])

    # -- gate 1: heap across travel/eviction cycles ------------------------
    ranges = {}
    for _lo, _hi, _tag in world._VNUM_RANGES:
        ranges[_tag] = (_lo, _hi)
    tour = []
    i = 0
    while i < len(world._AREA_FILES):
        _tag = world._AREA_FILES[i][1]
        if _tag != own_tag:
            tour.append(_tag)
        i += AREA_STEP
    log("gate1: touring " + int_str(len(tour)) + " areas x "
        + int_str(CYCLES) + " cycles (cap 12)")
    room_of = {}
    for cyc in range(CYCLES):
        t0 = ticks()
        for tag in tour:
            lo, hi = ranges[tag]
            world._ensure_area_by_tag(tag)
            rv = room_of.get(tag, -2)
            if rv == -2:
                rv = _first_room(lo, hi)
                room_of[tag] = rv
            if rv < 0:
                continue
            player["room"] = rv
            world.maybe_evict(player)
        gc.collect()
        log("gate1 cycle " + int_str(cyc + 1) + ": " + int_str(ticks() - t0)
            + "ms  mem=" + int_str(free())
            + " loaded=" + int_str(len(world._LOADED_AREAS)))

    # -- setup for gates 2/3: carried foreign items, owners unloaded ------
    own_tag = world._vnum_to_tag(player["room"])
    excl = set()
    if own_tag:
        excl.add(own_tag)
    tag2, v2 = _pick_item_area(excl)
    excl.add(tag2)
    tag3, v3 = _pick_item_area(excl)
    if tag2 is None or tag3 is None:
        log("SETUP FAILED: no item-bearing areas found")
        return
    obj2 = create_object(v2)
    obj3 = create_object(v3)
    player["inv"].append(obj2)
    player["inv"].append(obj3)
    world._unload_area(tag2)
    world._unload_area(tag3)
    log("setup: v2=" + int_str(v2) + " (" + tag2 + ") v3=" + int_str(v3)
        + " (" + tag3 + ")  snap2=" + str(v2 in world.ITEM_SNAPSHOTS)
        + " snap3=" + str(v3 in world.ITEM_SNAPSHOTS))

    # -- gate 2: stale revision -> exactly one corrective load -------------
    entry = world.ITEM_SNAPSHOTS[v2]
    world.ITEM_SNAPSHOTS[v2] = ("stale-rev", entry[1], entry[2])
    before = set(world._LOADED_AREAS)
    t0 = ticks()
    tpl = world.item_tpl(v2)
    dt = ticks() - t0
    delta = [t for t in world._LOADED_AREAS if t not in before]
    ok2 = (len(delta) == 1 and delta[0] == tag2 and tpl is not None
           and v2 in world.ITEM_DEFS._data)
    log("gate2: " + ("PASS" if ok2 else "FAIL") + " loads=" + str(delta)
        + " ms=" + int_str(dt)
        + " resident=" + str(v2 in world.ITEM_DEFS._data)
        + " pruned=" + str(v2 not in world.ITEM_SNAPSHOTS))

    # -- gate 3: snapshot obj program fires, owner stays unloaded ----------
    entry = world.ITEM_SNAPSHOTS[v3]
    world.ITEM_SNAPSHOTS[v3] = (
        entry[0], entry[1], {PROG_VNUM: "obj echo The snapshot gate hums."})
    fired = []
    orig_flow = mobprog.program_flow

    def _wrap(pv, code, mob, ch, a1, a2, obj=None, room=None):
        fired.append(pv)
        return orig_flow(pv, code, mob, ch, a1, a2, obj=obj, room=room)

    mobprog.program_flow = _wrap
    err = ""
    t0 = ticks()
    try:
        octx = {"obj": obj3, "carrier": player, "room": None}
        mobprog._run_oprog(octx, PROG_VNUM, player, None, None)
    except Exception as e:
        err = repr(e)
    finally:
        mobprog.program_flow = orig_flow
    dt = ticks() - t0
    ok3 = (fired == [PROG_VNUM] and not world.is_area_loaded(tag3)
           and err == "")
    log("gate3: " + ("PASS" if ok3 else "FAIL") + " fired="
        + int_str(len(fired)) + " ms=" + int_str(dt)
        + " owner_loaded=" + str(world.is_area_loaded(tag3))
        + (" err=" + err if err else ""))

    # -- sanity: a full save over the synthesized state still round-trips --
    t0 = ticks()
    ok = game_state.save_world(quiet=True)
    log("save over gate state: ok=" + str(ok) + " "
        + int_str(ticks() - t0) + "ms")
    gc.collect()
    log("mem free end: " + int_str(free()))

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
