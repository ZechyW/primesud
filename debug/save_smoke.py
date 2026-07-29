"""Full-game save-path smoke test: real save, per-segment timings. [PRIMESUD]

Loads the REAL primesud.sav (copy it from the game appdir into this
debug appdir first, Connectivity Kit) through the full game code, then
runs three timed save_world passes with the "save" debug channel on, so
game_state._SAVE_TIMING attributes the cost per segment:
  lines / snap / sweep / join / hvset / verify / fwrite
"snap" is the item-template snapshot block (codec) -- the suspected
save-lag source (348ms/40 records in hvar_cap run 3). This is also the
end-to-end validation of the hvars_set backslash-doubling fix against
the exact payload that failed on 29/07: ok=True means the readback
verification passed.

Safety: the game's real HVar/save are never written -- SAVE_VAR is
redirected to "smoketest" BEFORE load_world (so even a migration _bak
write lands on smoketest_bak) and SAVE_FILE to save_smoke.sav after
load. The real primesud.sav copy is only read.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx) in the
appdir alongside this probe; terminal.tr is stubbed, so no font file is
needed. Only self-running probe .py in the appdir (Prime auto-imports
all). Results printed and written to save_smoke.log.
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
        n_it = payload.count("~it.")
        log("payload: " + int_str(len(payload)) + "B, it-lines="
            + int_str(n_it))
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
