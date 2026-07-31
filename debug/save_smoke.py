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

Each mark also carries gc.mem_free() at that boundary. "collects=" counts
boundaries where free memory ROSE, which can only mean a collect fired
mid-serialize. Desktop CPython has no gc.mem_free, so free reads 0 there
and only a device run answers anything.

Phases, in order (log() rewrites the file every call, so everything up to
a death survives):

  A/B  three save modes -- baseline (no segment checkpoints, the shape
       the 28/07 soak validated), pump (checkpoints, no echo), pump+echo
       (checkpoints plus a prompt redraw at each), then the payload
       breakdown. save_smoke-8 settled this: 0 collects in all modes,
       pump costs 0 bytes, echo costs +6,352 B/save (+2%). The
       save-stall UX work is not what pressures the heap.
  C    one explicit collect, measured. save_smoke-8 showed every save
       burning exactly 307,024 B with free falling monotonically and
       never recovering. This says whether that is transient garbage (a
       collect hands it back) or retained (a leak). Doubles as a probe:
       an explicit collect right after churn is the documented
       worst-case roll for the str(int)-GC bug.
  D    drive to exhaustion. The save path takes no collects of its own,
       so the collect that eventually walks save-shaped garbage is an
       AUTO one at whatever moment the heap fills -- the documented
       trigger. In play that is ~10-20 autosaves apart (2 min each);
       here it is driven flat out until TARGET_COLLECTS auto-collects
       have been survived. A death in this phase is the crash
       reproduced on the bench.
       Since save_smoke-9: each save is preceded by a gameplay-shaped
       churn gap ((i % 8) * CHURN_STEP bytes of combat-message-style
       small-string garbage). save_smoke-9's four auto-collects all
       landed mid-hvset -- back-to-back saves tip the heap over at the
       same deterministic (and apparently safe) spot every cycle. Real
       play interleaves ~2 min of gameplay allocation between
       autosaves, so the collect can land at ANY allocation site with
       save-shaped garbage still on the heap; the varying churn gap
       rotates the tip-over point to model that.

Since 31/07 the game ships a threshold-gated collect at the save tail
(game_state._GC_FREE_FLOOR, timing mark "gcpost"), so runs against
current code see deliberate [gcpost] rises roughly every 7-11 phase-D
saves instead of arbitrary-site autos; results -8/-9/-10 predate it.

See TODO.md sec. G1 crash watch and docs/PRIME_FIRMWARE_BUGS.md.

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
# Phase D drive: keep saving until this many auto-collects have been seen
# (each one is a death roll, ~25-30% in probe conditions -- 5 rolls is
# >80% odds of a kill if the crash really is this bug) or the save cap is
# hit, whichever comes first.
TARGET_COLLECTS = 5
MAX_DRIVE_SAVES = 60
# Phase D churn gap: save i burns (i % 8) * CHURN_STEP bytes of
# gameplay-shaped garbage before saving, cycling the tip-over point
# through 0..420KB of the ~420KB/save span so the auto-collect lands
# somewhere different each cycle (see phase D note above).
CHURN_STEP = 60000
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


def _churn_gap(target):
    """Burn ~target bytes of gameplay-shaped garbage between saves.

    Combat-round-style small strings (int_str + concat, the game's
    validated render path), built into a short list and dropped, the way
    act()/show_prompt output churns in play. Returns (burned, collected):
    free() can only RISE mid-churn if an auto-collect fired -- that is
    the real-play scenario of a collect landing at a gameplay allocation
    site with save-shaped garbage still on the heap, the roll the
    back-to-back drive never makes.
    """
    if not hasattr(gc, "mem_free"):
        return 0, False  # desktop: free() is a constant 0, loop cannot end
    start = free()
    low = start
    lines = []
    n = 0
    while True:
        f = free()
        if f > low + 1024:
            return start - low, True
        if f < low:
            low = f
        if start - f >= target:
            return start - f, False
        n += 1
        v = n % 997
        lines.append("You hit a beggar for " + int_str(v) + " damage.")
        lines.append("{R" + int_str(v) + "/" + int_str(v + 5) + "hp {M"
                     + int_str(v * 3) + "mn{x")
        if len(lines) > 32:
            lines = []


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

    # -- Phase C: is the per-save heap cost garbage or a leak? ---------------
    # save_smoke-8: every save burned exactly 307,024 B and free fell
    # monotonically 6.17M -> 3.20M over 9 saves with zero collects. If one
    # collect hands most of that back it was transient garbage (bad, but the
    # heap recovers); if little comes back it is retained, and the game dies
    # of exhaustion eventually no matter what the GC bug does.
    # This collect is also itself a probe: an explicit collect right after a
    # churn burst is the documented worst-case roll, so if the crash is the
    # str(int)-GC bug it can land right here.
    log("-- phase C: reclaim test (one explicit collect after churn)")
    _before = free()
    log("  free before: " + int_str(_before))
    t0 = ticks()
    gc.collect()
    log("  free after:  " + int_str(free()) + " (" + int_str(ticks() - t0)
        + "ms, reclaimed " + int_str(free() - _before) + ")")

    # -- Phase D: drive to heap exhaustion ----------------------------------
    # The save path takes no collects of its own, so the collect that
    # eventually walks save-shaped garbage is an AUTO one, fired whenever
    # the heap happens to fill -- documented as the trigger ("died the
    # moment heap exhaustion forced the first auto-collect"). In play that
    # is ~10-20 autosaves apart at 2 min each; here it is driven flat out.
    # An auto-collect shows as free RISING, either between saves or across
    # marks within one. Runs in pump+echo, the real game's shape.
    log("-- phase D: drive to exhaustion (pump+echo, churn gaps, target "
        + int_str(TARGET_COLLECTS) + " auto-collects, cap "
        + int_str(MAX_DRIVE_SAVES) + " saves)")
    tr = _TRPump()
    terminal.tr = tr
    _ECHO[0] = True
    seen = 0
    prev_end = free()
    i = 0
    while seen < TARGET_COLLECTS and i < MAX_DRIVE_SAVES:
        i += 1
        tr._key_queue_count = 0
        f0 = free()
        if f0 > prev_end:
            seen += 1
            log("  (AUTO-COLLECT between saves, +" + int_str(f0 - prev_end)
                + ") seen=" + int_str(seen))
        # Churn gap before the save. Target logged BEFORE churning, result
        # after, so a death mid-churn is attributable to the churn site --
        # a churn-site death is the strongest possible signal here.
        _ct = (i % 8) * CHURN_STEP
        if _ct:
            log("  churn " + int_str(i) + ": target " + int_str(_ct)
                + "B, free " + int_str(f0))
            t0 = ticks()
            _burned, _hit = _churn_gap(_ct)
            if _hit:
                seen += 1
            log("    burned " + int_str(_burned) + "B in "
                + int_str(ticks() - t0) + "ms"
                + (" AUTO-COLLECT mid-churn seen=" + int_str(seen)
                   if _hit else ""))
        start = free()
        # Logged BEFORE the save, so a death mid-save still leaves the
        # save number and the heap state that preceded it in the file.
        log("  save " + int_str(i) + ": start free " + int_str(start))
        t0 = ticks()
        ok = game_state.save_world(quiet=True)
        total = ticks() - t0
        marks = game_state._SAVE_TIMING
        gcs = collects(marks)
        if gcs:
            seen += len(gcs)
        prev_end = marks[-1][2]
        log("    ok=" + str(ok) + " total=" + int_str(total)
            + "ms end free " + int_str(prev_end) + " used "
            + int_str(start - prev_end) + " in-save collects="
            + int_str(len(gcs)) + (" [" + " ".join(gcs) + "]" if gcs else "")
            + " seen=" + int_str(seen))
    log("  drive done: " + int_str(i) + " saves, " + int_str(seen)
        + " auto-collects survived, free " + int_str(free()))

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    DBG.discard("save")
    log("Done. Results in " + LOG)


main()
