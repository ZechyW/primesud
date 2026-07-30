"""Full-game save-path smoke test: real save, per-segment timings. [PRIMESUD]

Loads the REAL primesud.sav (copy it from the game appdir into this
debug appdir first, Connectivity Kit) through the full game code, then
runs three timed save_world passes with the "save" debug channel on, so
game_state._SAVE_TIMING attributes the cost per segment:
  ln.plr1 (scalars) / ln.pinv (inv+eq tokens) / ln.plearn (learned)
  / ln.rle / ln.paff (affects/pet/macros/aliases) / ln.wstate
  (area age+weather, time) / ln.stats (kill+explore stats, gquests)
  / ln.mob / ln.room (resident items) / ln.rpend (pending passthrough)
  / snap / sweep / join / hvset / verify / fwrite
(Split further 30/07 for the next save diet: the old ln.plr2 255ms /
ln.room 246ms buckets each mixed unrelated costs.) A per-prefix payload
breakdown (line count + bytes) prints after the saves so ms/item and
hvset's ~1.1ms/KB attribution fall out of the same run.
load_world now includes the pending-token cache prewarm, so its time
absorbs what used to be save 1's one-time snap spike (4518ms in
save_smoke-2). This probe also end-to-end validates the hvars_set
backslash-doubling fix against the exact payload that failed on 29/07:
ok=True means the readback verification passed.

Safety: the game's real HVar/save are never written -- SAVE_VAR is
redirected to "smoketest" BEFORE load_world (so even a migration _bak
write lands on smoketest_bak) and SAVE_FILE to save_smoke.sav after
load. The real primesud.sav copy is only read.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx) in the
appdir alongside this probe -- EXCEPT src/primesud.py: its module level
ends in PrimeSud().run(), so auto-import would launch the real game
(whose quit path saves to the REAL slot, outside this probe's
redirect). terminal.tr is stubbed, so no font file is needed. Only
self-running .py in the appdir (Prime auto-imports all) must be this
probe. Results printed and written to save_smoke.log.
"""
import gc

import terminal


class _TRStub:
    """Swallow tprint/dbg output -- probe runs without a real terminal."""

    def print(self, *args, **kwargs):
        pass


terminal.tr = _TRStub()

from prime_platform import ticks, hvars_get, hvars_set  # noqa: E402
from util import int_str  # noqa: E402
from config import R_STARTING_ROOM  # noqa: E402
import world  # noqa: E402
import game_state  # noqa: E402
from debug import DBG  # noqa: E402
from player import create_char  # noqa: E402

LOG = "save_smoke.log"

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


def main():
    log("save_smoke: full-game load + timed saves")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    game_state.SAVE_VAR = "smoketest"
    DBG.add("save")

    player = create_char()
    player["_macros"] = {}
    player["room"] = R_STARTING_ROOM
    world.chars[1] = player

    t0 = ticks()
    src = game_state.load_world()
    log("load_world: " + int_str(ticks() - t0) + "ms source=" + str(src))
    log("areas loaded: " + int_str(len(world._LOADED_AREAS))
        + ", snapshots: " + int_str(len(world.ITEM_SNAPSHOTS)))
    log("mem free after load: " + int_str(free()))

    # Real primesud.sav stays read-only; saves go to a scratch file.
    game_state.SAVE_FILE = "save_smoke.sav"

    for i in range(3):
        t0 = ticks()
        ok = game_state.save_world(quiet=True)
        total = ticks() - t0
        segs = []
        for seg, ms in game_state._SAVE_TIMING:
            segs.append(seg + "=" + int_str(ms))
        log("save " + int_str(i + 1) + ": ok=" + str(ok) + " total="
            + int_str(total) + "ms  " + " ".join(segs))

    payload = hvars_get("smoketest")
    if isinstance(payload, str):
        log("payload: " + int_str(len(payload)) + "B total")
        # Per-prefix breakdown: first matching prefix wins, "other" catches
        # the rest (v=, p.pos, ...). Maps onto the timing segments above.
        groups = ["p.inv", "p.eq", "p.learned", "p.explored", "s.m.",
                  "s.a.", "p.", "a.", "g.", "m=", "r.", "it."]
        stats = {}
        for line in payload.split("~"):
            for pre in groups:
                if line.startswith(pre):
                    break
            else:
                pre = "other"
            n, b = stats.get(pre, (0, 0))
            stats[pre] = (n + 1, b + len(line))
        for pre in groups + ["other"]:
            if pre in stats:
                n, b = stats[pre]
                log("  " + pre + " lines=" + int_str(n)
                    + " bytes=" + int_str(b))
        # r. lines merge resident + pending; split from live world state.
        n_res = 0
        for rv in world.rooms:
            if world.rooms[rv]["items"]:
                n_res += 1
        log("  r. resident-rooms=" + int_str(n_res)
            + " pending-rooms=" + int_str(len(world._pending_room_items)))
    else:
        log("payload readback non-str: " + str(type(payload)))
    log("mem free end: " + int_str(free()))

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    DBG.discard("save")
    log("Done. Results in " + LOG)


main()
