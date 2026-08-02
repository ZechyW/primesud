"""Recommend-scan timings on-device: gear summary, slot detail, mobs. [PRIMESUD]

Companion probe to RECOMMEND_PLAN.md perf rounds (4c3b0d8 + e8d753c).
Times the non-interactive scan core the `recommend` command sits on --
recommend._scan_gear(player) / _scan_gear(player, "wield") /
recommend._mob_candidates(player) -- so exact numbers come out of a log
with zero player action.  The interactive layers (pick_from / tpage) are
deliberately NOT driven: they block on keys, and render cost is already
characterised elsewhere.

Also measures the I/O floor: the exact chunked seek+read pattern
_scan_gear issues (head read + greedy-packed <=_CHUNK runs), with all
parsing skipped.  scan-minus-floor = pure parse/score cost, so the two
remaining PC-side levers (row split volume vs read count) can be ranked
from device data.

Setup mirrors combat_bench.py: copy the REAL primesud.sav into this
debug appdir first (Connectivity Kit) -- it is only read, so the timed
scans see the real character (level, learned weapon skills, funds,
equipment baselines).  SAVE_VAR is redirected to "smoketest" before
world.init_world()/load_world(); SAVE_FILE to recommend_bench.sav after,
so nothing here can touch the real save slot or file.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx + gear.bin)
EXCEPT
src/primesud.py (its module level launches the game).  Only ONE
self-running .py may be in the appdir (Prime auto-imports all): this
probe OR combat_bench.py OR save_smoke.py etc., never more than one.
Results printed and written to recommend_bench.log, flushed line by
line so a hard reset keeps everything up to the crash point.

Scenarios (N=3 each, gc.collect before every timed pass):
  1 boot          -- load_world() timing + player context lines
  2 io_summary    -- chunked-read replica, all 16 slot segments, no parse
  3 io_wield      -- chunked-read replica, wield segment only
  4 scan_summary  -- _scan_gear(player): the `recommend gear` scan
  5 scan_wield    -- _scan_gear(player, "wield"): slot-detail scan
  6 scan_mobs     -- _mob_candidates(player): the `recommend mobs` scan
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
import recommend  # noqa: E402

LOG = "recommend_bench.log"
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
        + "ms avg=" + int_str(total // n) + "ms")
    return result


# -- Binary read fidelity: does device open("rb") return faithful bytes? ----

# PC-computed ground truth for src/gear.bin as shipped in this bundle.
# Regenerate via tools/build_mob_index.py + a quick len/sum/slice check if
# gear.bin changes.
_BIN_LEN = 80283
_BIN_SUM = 4853482
_BIN_FIRST16 = (71, 66, 48, 49, 243, 1, 30, 0, 111, 223, 0, 0, 45, 0, 76, 0)
_BIN_STRINGS_OFF = 57199
_BIN_AT_STRINGS = (97, 110, 32, 105, 109, 112, 101, 114)


def scenario_uioprobe():
    """Does uio.open exist and differ from builtin open? If it returns real
    bytes with byte-counted sized reads, the _as_bytes cast can go."""
    try:
        import uio
    except ImportError:
        log("uioprobe: no uio module")
        return
    members = []
    for name in dir(uio):
        members.append(name)
    log("uioprobe: uio has " + " ".join(members))
    if not hasattr(uio, "open"):
        return
    try:
        with uio.open(recommend.GEAR_INDEX_FILE, "rb") as f:
            head = f.read(16)
        log("uioprobe: uio.open read type=" + type(head).__name__
            + " len=" + int_str(len(head)))
    except Exception as exc:
        log("uioprobe: uio.open failed: " + type(exc).__name__)


def scenario_binprobe():
    """One-transfer diagnosis of open('rb') semantics on-device: read type,
    length, high-byte fidelity (first16 includes 0xF3), EOL/EOF translation
    (file holds 651 CRs + 221 0x1A), seek addressing."""
    with open(recommend.GEAR_INDEX_FILE, "rb") as f:
        head = f.read(16)
        tname = type(head).__name__
        head = recommend._as_bytes(head)
        parts = []
        for value in head:
            parts.append(int_str(value))
        log("binprobe: head type=" + tname + " len=" + int_str(len(head))
            + " [" + " ".join(parts) + "]")
        # Device read(n) counts characters, not bytes (G1, 02/08/2026): a
        # high byte is a UTF-8 lead and drags continuation bytes along, so
        # sized reads can over-return. Compare the first 16 values only.
        ok = len(head) >= 16
        if ok:
            for i in range(16):
                if head[i] != _BIN_FIRST16[i]:
                    ok = False
                    break
        log("binprobe: first16 " + ("MATCH" if ok else "MISMATCH"))
        f.seek(_BIN_STRINGS_OFF)
        probe = recommend._as_bytes(f.read(8))
        ok = len(probe) == 8
        if ok:
            for i in range(8):
                if probe[i] != _BIN_AT_STRINGS[i]:
                    ok = False
                    break
        log("binprobe: seek(57199) " + ("MATCH" if ok else "MISMATCH"))
        f.seek(0)
        data = recommend._as_bytes(f.read())
        total = 0
        for value in data:
            total += value
        log("binprobe: full len=" + int_str(len(data))
            + (" MATCH" if len(data) == _BIN_LEN else " MISMATCH expect "
               + int_str(_BIN_LEN))
            + " sum=" + int_str(total)
            + (" MATCH" if total == _BIN_SUM else " MISMATCH expect "
               + int_str(_BIN_SUM)))


# -- I/O floor: _scan_gear's exact read pattern, no parsing -----------------

def _gear_runs(wield_only):
    """Return ([(start, size)], strings_off) -- the greedy-packed record
    runs _scan_gear would issue for summary mode (all slots) or
    wield-only, plus the string-table offset for the winner-name read.
    Keep in sync with _scan_gear if the packing changes."""
    with open(recommend.GEAR_INDEX_FILE, "rb") as f:
        head = recommend._as_bytes(f.read(4096))
    hsize = head[4] | head[5] << 8
    strings_off = (head[8] | head[9] << 8 | head[10] << 16
                   | head[11] << 24)
    pos = hsize
    needed = []
    for seg_index in range(len(recommend._GEAR_SLOTS)):
        slot = recommend._GEAR_SLOTS[seg_index]
        size = (head[12 + 2 * seg_index]
                | head[13 + 2 * seg_index] << 8) * recommend._REC
        if size and (not wield_only or slot == "wield"):
            needed.append((pos, size))
        pos += size
    runs = []
    index = 0
    while index < len(needed):
        run_start = needed[index][0]
        stop = index + 1
        while (stop < len(needed)
                and needed[stop][0] + needed[stop][1] - run_start
                    <= recommend._CHUNK):
            stop += 1
        runs.append((run_start,
                     needed[stop - 1][0] + needed[stop - 1][1] - run_start))
        index = stop
    return runs, strings_off


def _io_pass(runs, strings_off):
    with open(recommend.GEAR_INDEX_FILE, "rb") as f:
        f.read(4096)
        for start, size in runs:
            f.seek(start)
            data = f.read(size)
            data = None
        f.seek(strings_off)
        data = f.read()
        data = None


def scenario_io(label, wield_only):
    runs, strings_off = _gear_runs(wield_only)
    total = 0
    for _start, size in runs:
        total += size
    log(label + ": " + int_str(len(runs)) + " record reads, "
        + int_str(total) + "B (+4096B head +strings)")
    timed(label, lambda: _io_pass(runs, strings_off))


# -- Sanity logging ---------------------------------------------------------

def _log_gear_results(label, results):
    if results is None:
        log(label + ": RESULTS None -- gear.bin missing?")
        return
    hits = 0
    for slot in results:
        rows = results[slot]
        if rows:
            hits += 1
            log(".. " + label + " " + slot + ": " + int_str(len(rows))
                + " rows, top +" + int_str(rows[0]["gain"])
                + " " + rows[0]["name"][:32])
    if not hits:
        log(label + ": no upgrades found (check character/save)")


def main():
    gc.collect()
    log("recommend_bench: recommend-scan timings")
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
    game_state.SAVE_FILE = "recommend_bench.sav"

    player = world.chars[1]
    log("player: level=" + int_str(player.get("level", 1))
        + " room=" + int_str(player.get("room", 0))
        + " learned=" + int_str(len(player.get("learned", {})))
        + " gold=" + int_str(player.get("gold", 0))
        + " silver=" + int_str(player.get("silver", 0)))

    gc.collect()
    log("mem free after boot: " + int_str(free()))

    scenario_uioprobe()
    scenario_binprobe()
    gc.collect()

    scenario_io("io_summary", False)
    scenario_io("io_wield", True)
    gc.collect()
    log("mem free after io: " + int_str(free()))

    results = timed("scan_summary", lambda: recommend._scan_gear(player))
    _log_gear_results("scan_summary", results)
    gc.collect()
    log("mem free after scan_summary: " + int_str(free()))

    results = timed("scan_wield",
                    lambda: recommend._scan_gear(player, "wield"))
    _log_gear_results("scan_wield", results)
    gc.collect()
    log("mem free after scan_wield: " + int_str(free()))

    mobs = timed("scan_mobs", lambda: recommend._mob_candidates(player))
    log("scan_mobs: " + int_str(len(mobs) if mobs else 0) + " candidates")
    gc.collect()
    log("mem free after scan_mobs: " + int_str(free()))

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
