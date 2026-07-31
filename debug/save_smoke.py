"""Full-game save-path smoke test: real save, per-segment timings. [PRIMESUD]

Loads the REAL primesud.sav (copy it from the game appdir into this
debug appdir first, Connectivity Kit) through the full game code, then
runs timed save_world passes with the "save" debug channel on, so
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

Each mark also carries gc.mem_free() at that boundary, and the saves run
in three modes -- baseline (no segment checkpoints, the shape the 28/07
soak validated), pump (checkpoints, no echo), pump+echo (checkpoints
plus a prompt redraw at each). "collects=" counts boundaries where free
memory ROSE, which can only mean a collect fired mid-serialize. Collects
appearing in the later modes but not baseline confirms that the
save-stall UX work pushed the save path into taking collects it was
tuned to avoid -- the documented precondition for both G1 heap bugs
(docs/PRIME_FIRMWARE_BUGS.md, TODO.md sec. Save path lost its soak
cover). Desktop CPython has no gc.mem_free, so free reads 0 there and
only the device run answers the question.

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

# Keys "typed" per segment boundary in the pump+echo mode (a real FIFO
# drain yields 1-4; the translated queue caps at _KEY_QUEUE_SIZE = 16).
KEYS_PER_BOUNDARY = 1
SAVES_PER_MODE = 3
_ECHO = [False]
# Pumps and echoes actually executed in the last save. Reported per save:
# a mode that silently no-ops (the reason the pre-31/07 harness measured a
# straight-line save without noticing) shows up as zeroes instead of
# passing for a clean result.
_COUNTS = [0, 0]


class _TRStub:
    """Swallow tprint/dbg output -- probe runs without a real terminal.

    Has no _pump_keyboard, so _serialize_world's `_pump` stays None and
    every segment checkpoint is skipped: this is the straight-line save
    the 28/07 soak validated (baseline mode).
    """

    def print(self, *args, **kwargs):
        pass

    def set_status(self, text):
        pass


class _TRPump(_TRStub):
    """Stub with the keyboard surface _serialize_world's checkpoints use.

    _pump_keyboard queues KEYS_PER_BOUNDARY events per boundary when
    _ECHO is on, which is what makes the pump wrapper fire
    SAVE_ECHO_HOOK; with _ECHO off the count never moves, so the
    checkpoints run but nothing echoes. That splits the two suspects
    (pump call vs echo render) instead of testing them fused.
    """

    _KEY_QUEUE_SIZE = 16

    def __init__(self):
        self._key_queue_count = 0

    def _pump_keyboard(self, key_commands=None):
        _COUNTS[0] += 1
        if _ECHO[0]:
            self._key_queue_count = min(self._KEY_QUEUE_SIZE,
                                        self._key_queue_count
                                        + KEYS_PER_BOUNDARY)

    def peek_queued_events(self):
        # (char, key_command) pairs, same shape as the real translated
        # queue; plain chars so _save_echo appends them to the buffer.
        return [("k", None)] * self._key_queue_count


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


def collects(marks):
    """Segment names whose free-heap mark ROSE against the previous one.

    Free memory falls monotonically as the payload builds, so a rise can
    only mean a collect fired between the two boundaries -- the thing the
    save path is tuned to take none of.
    """
    out = []
    for i in range(1, len(marks)):
        if marks[i][2] > marks[i - 1][2]:
            out.append(marks[i][0])
    return out


class _EchoGame:
    """Minimal stand-in for the Game object _save_echo closes over."""

    input_buf = ""


def echo_hook():
    """SAVE_ECHO_HOOK body: the real _save_echo, counted."""
    _COUNTS[1] += 1
    game_state._save_echo(_EchoGame())


def main():
    log("save_smoke: full-game load + timed saves")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    game_state.SAVE_VAR = "smoketest"
    DBG.add("save")

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
    log("mem free after load: " + int_str(free()))

    # Load the two areas owning the most pending-room lines: their items
    # become resident, so ln.room (per-item serialize_item_token, uncached)
    # is measured alongside the pending-line caches -- save_smoke-5 ran
    # with 0 resident rooms and left ln.room unattributed.
    counts = {}
    for rv in world._pending_room_items:
        tag = world._vnum_to_tag(rv)
        if tag is None:  # room outside every area range: nothing to load
            continue
        counts[tag] = counts.get(tag, 0) + 1
    for tag in sorted(counts, key=lambda t: -counts[t])[:2]:
        t0 = ticks()
        world._load_area(tag)
        log("loaded " + str(tag) + ": " + int_str(ticks() - t0)
            + "ms (had " + int_str(counts[tag]) + " pending rooms)")

    # Real primesud.sav stays read-only; saves go to a scratch file.
    game_state.SAVE_FILE = "save_smoke.sav"

    # Three modes, same save, isolating the two suspects added since the
    # 28/07 soak (TODO.md sec. Save path lost its soak cover):
    #   baseline   -- no _pump_keyboard on tr: checkpoints skipped entirely
    #   pump       -- 16 checkpoints run, nothing echoes
    #   pump+echo  -- every checkpoint also redraws the prompt
    # A collect appearing in the later modes but not baseline is the
    # hypothesis confirmed: the new work pushes the save into a
    # mid-serialize collect, the documented precondition for both G1 heap
    # bugs (docs/PRIME_FIRMWARE_BUGS.md).
    game_state.SAVE_ECHO_HOOK = echo_hook
    for mode, tr, echo in (("baseline", _TRStub(), False),
                           ("pump", _TRPump(), False),
                           ("pump+echo", _TRPump(), True)):
        terminal.tr = tr
        _ECHO[0] = echo
        log("-- mode " + mode + " (free " + int_str(free()) + ")")
        for i in range(SAVES_PER_MODE):
            _COUNTS[0] = _COUNTS[1] = 0
            # game_loop drains the queue after each save; without this the
            # stub's count saturates at _KEY_QUEUE_SIZE and stops changing,
            # so the pump wrapper stops firing the hook and later saves in
            # the mode quietly echo less than the first.
            tr._key_queue_count = 0
            t0 = ticks()
            ok = game_state.save_world(quiet=True)
            total = ticks() - t0
            marks = game_state._SAVE_TIMING
            segs = []
            for seg, ms, _f in marks:
                segs.append(seg + "=" + int_str(ms))
            gcs = collects(marks)
            log("  save " + int_str(i + 1) + ": ok=" + str(ok) + " total="
                + int_str(total) + "ms collects=" + int_str(len(gcs))
                + (" [" + " ".join(gcs) + "]" if gcs else "")
                + " free " + int_str(marks[0][2]) + "->"
                + int_str(marks[-1][2]) + " pumps=" + int_str(_COUNTS[0])
                + " echoes=" + int_str(_COUNTS[1]))
            log("    " + " ".join(segs))

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
