"""Save-path primitive timings: alloc build / join / HVars / file write. [PRIMESUD]

Run standalone on the physical HP Prime -- needs NO game modules, so it
runs from the minimal "Python debug" appdir.  If a real primesud.sav is
copied into the appdir (Connectivity Kit, from the PrimeSUD appdir) the
probe uses that payload verbatim; otherwise it synthesizes a
representative one (~6KB, same line/field mix as _serialize_world).

Segments mirror _serialize_world (game_state.py):
  gc     -- the up-front gc.collect() (mark cost over live heap only;
            game-heap garbage sweep is not simulated)
  build  -- per-line str()+append+join alloc workload rebuilt from the
            parsed payload (same token count and data volume)
  join   -- final "~".join(lines)
  hvset  -- HVars write: payload embedded in a PPL string literal and
            parsed by eval (hvars_set in prime_platform.py)
  hvget  -- HVars readback + full-payload compare (the verify step)
  fwrite -- one open/write of the payload

Each segment runs N passes bare, then again with ~2.5MB of small live
objects as ballast: alloc cost scales with live heap (~35us standalone
vs ~490us at full game heap, BUILTINS.md sec. Text rendering
performance), so bare numbers under-rank alloc-heavy segments; the
ballast pass approximates game conditions.  hvset/hvget also run at
1x/2x/4x payload size (bare heap) to check PPL parse-cost linearity.

Results printed and written to save_bench.log -- flushed line by line,
so a hard reset mid-run keeps everything logged up to the crash point,
including per-pass ".." trace lines.  Repeated alloc-heavy build
passes hard-reset the G1 (27/07 device log dies at build entry with
the 8MB heap; all other segments survive), so ordering is
data-before-death: HVars size-scaling first, then the cheap segments,
then a build-variant ladder (quarter workload / pre-stringed tokens /
no per-pass collect / full) that doubles as a crash-trigger bisect --
whichever rung the reset lands on narrows the cause (volume vs
str(int) vs gc interplay).  Uses HVar "savebench" (never the real
primesud_save); reset to "0" at the end.  Leaves save_bench.tmp in
the appdir (fwrite target).
"""
import gc
from hpprime import eval as ppleval

N = 5
SAV = "primesud.sav"
LOG = "save_bench.log"
HVAR = "savebench"

# Bisect toggle (G1 stall hunt, 27/07).  Evidence so far: "full"
# stalls 2/2 on clean pool; "off" and "1x" complete clean
# (save_bench-4/5.log) -- BUT "full" is confounded: it also builds the
# 16/32KB payload strings Python-side before the HVars calls, and the
# clean modes skipped both.  The bignohv/4xonce pair decouples them;
# the two runs differ by exactly one hvars_set call.  Modes:
#   "off"     -- no HVars at all (clean-run control)
#   "1x"      -- all HVars call sites, ~8KB literals only (clean, -5.log)
#   "full"    -- original incl. 2x/4x scaling (the stall repro)
#   "bignohv" -- build 2x/4x strings, keep them live all run, ZERO
#                HVars traffic.  Clean => big str concat acquitted.
#   "4xonce"  -- bignohv plus a single hvars_set of the 32KB string.
#                Stall => one-call minimal repro, HVars convicted.
HV_MODE = "bignohv"

_out = []


def log(msg):
    """Print and append to the log file immediately -- a firmware-level
    crash mid-run (hard reset, no Python traceback) must not lose the
    lines already produced.  Full rewrite per call: ~20ms/write is
    nothing next to the segments, and append mode is unverified on
    device."""
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def ticks():
    return int(ppleval("Ticks"))


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


# Inlined from prime_platform.py (hvars_get/hvars_set) so the probe has
# no game imports -- keep in sync if the wrappers change.
def hvars_set(name, value):
    ppleval('HVars("' + name + '"):="' + value + '"')


def hvars_get(name):
    return ppleval('HVars("' + name + '")')


def synth_payload():
    """Representative save payload: same line/field mix as _serialize_world."""
    lines = ["v=10"]
    for k in ("name=Hero", "title= the Acolyte", "race=Human", "sex=male",
              "true_sex=male", "quest_mob_name=", "quest_room_name=",
              "quest_area_name="):
        lines.append("p." + k)
    nums = []
    for i in range(35):
        nums.append(str(100 + i * 37))
    lines.append("p.n=" + "|".join(nums))
    lines.append("p.classes=0,2")
    lines.append("p.pos=standing")
    lines.append("p.groups=1,4,7,12")
    lines.append("p.stance=0,0,0,0,0,0,0,0,0,0")
    lines.append("p.armor=95|95|95|90")
    inv = []
    for i in range(15):
        inv.append(str(3000 + i) + "," + str(i % 5) + ",0," + str(40 + i))
    lines.append("p.inv=" + "|".join(inv))
    eq = []
    for i in range(19):
        eq.append((str(3100 + i) + "," + str(i % 3) + ",0," + str(50 + i))
                  if i % 4 else "")
    lines.append("p.eq=" + "|".join(eq))
    lrn = []
    for i in range(60):
        lrn.append(str(i) + ":" + str(1 + (i * 13) % 100))
    lines.append("p.learned=" + "|".join(lrn))
    rparts = []
    for i in range(100):
        rparts.append(str(1 + (i * 7) % 60))
    lines.append("p.explored=" + ".".join(rparts))
    af = []
    for i in range(4):
        af.append(str(20 + i) + ",40,12,none," + str(i) + ",,")
    lines.append("p.affects=" + "|".join(af))
    for i in range(40):
        aparts = [str(i * 3)]
        for j in range(6):
            aparts.append(str((i * j) % 100 - 50))
        lines.append("a.area" + str(i) + "=" + "|".join(aparts))
    lines.append("g.time=14|12|6|1462")
    lines.append("g.share=1030")
    for i in range(120):
        lines.append("s.m." + str(3000 + i) + "=" + str(i % 30) + "|"
                     + str(i % 7))
    for i in range(40):
        lines.append("s.a.area" + str(i) + "=" + str(i * 11) + "|"
                     + str(i * 3))
    mparts = []
    for i in range(60):
        rooms = []
        for j in range(1 + i % 3):
            rooms.append(str(3700 + i + j))
        mparts.append(str(3000 + i) + "," + "|".join(rooms))
    lines.append("m=" + ";".join(mparts))
    for i in range(10):
        items = []
        for j in range(1 + i % 4):
            items.append(str(3200 + j) + "," + str(j) + ",0," + str(10 + j))
        lines.append("r." + str(3001 + i * 7) + ".items=" + "|".join(items))
    return "~".join(lines)


def load_payload():
    try:
        with open(SAV, "r") as f:
            data = f.read()
        if data and isinstance(data, str):
            return data, "file"
    except Exception:
        pass
    return synth_payload(), "synthetic"


def parse_workload(payload):
    """Split payload into (key, tokens) per line; numeric tokens become
    ints so build_pass pays the same str(int) conversion allocs as
    _serialize_world."""
    work = []
    for line in payload.split("~"):
        if "=" in line:
            key, val = line.split("=", 1)
        else:
            key, val = line, ""
        toks = []
        for t in val.split("|"):
            if t and (t.isdigit() or (t[0] == "-" and t[1:].isdigit())):
                toks.append(int(t))
            else:
                toks.append(t)
        work.append((key, toks))
    return work


def build_pass(work):
    """Rebuild all save lines -- same append/str()/join alloc pattern as
    _serialize_world's line loop."""
    lines = []
    for key, toks in work:
        parts = []
        for t in toks:
            parts.append(str(t))
        lines.append(key + "=" + "|".join(parts))
    return lines


def _fwrite(payload):
    with open("save_bench.tmp", "w") as f:
        f.write(payload)


def time_n(name, fn, n=N, collect=True):
    ts = []
    for i in range(n):
        if collect:
            gc.collect()
        t0 = ticks()
        fn()
        ts.append(ticks() - t0)
        # Per-pass trace: pinpoints which pass a hard reset lands on
        # (file flush happens outside the timed region).
        log(".. " + name.strip() + " pass " + str(i + 1) + "/" + str(n)
            + " " + str(ts[i]) + "ms")
    return ts


def fmt(name, ts):
    lo = ts[0]
    tot = 0
    for t in ts:
        tot += t
        if t < lo:
            lo = t
    return name + ": min=" + str(lo) + "ms avg=" + str(tot // len(ts)) + "ms"


def raw(ts):
    parts = []
    for t in ts:
        parts.append(str(t))
    return " ".join(parts)


def run_segments(payload, work, tag):
    # No build here: repeated alloc-heavy build passes hard-reset the
    # G1 (27/07 device log dies exactly at build entry, everything
    # before survives) -- build runs via main's variant ladder instead,
    # after all of this has hit the log.
    lines = build_pass(work)
    segs = [
        ("gc    ", gc.collect),
        ("join  ", lambda: "~".join(lines)),
        ("fwrite", lambda: _fwrite(payload)),
    ]
    if HV_MODE in ("1x", "full"):
        segs.insert(2, ("hvset ", lambda: hvars_set(HVAR, payload)))
        segs.insert(3, ("hvget ", lambda: hvars_get(HVAR) == payload))
    for name, fn in segs:
        try:
            ts = time_n(tag.strip() + " " + name, fn)
            log(tag + " " + fmt(name, ts) + "  raw " + raw(ts))
        except Exception as e:
            log(tag + " " + name + ": FAILED " + str(e))


def make_ballast():
    """Grow ~2.5MB of small live objects (lists/strs/tuples) so the
    allocator scans a game-sized live heap during the ballast pass."""
    ballast = []
    start = free()
    i = 0
    while i < 200000:
        ballast.append([i, "x" + str(i), (i, i + 1)])
        i += 1
        if i % 1024 == 0:
            f = free()
            if start:
                if start - f >= 2500000 or f < 1500000:
                    break
            elif i >= 60000:
                break
    return ballast


def main():
    log("save_bench: save-path primitive timings, N=" + str(N))
    payload, src = load_payload()
    if '"' in payload:
        # PPL string literal cannot hold '"' (see _serialize_world
        # serialisation constraints) -- a real save never contains it.
        log("WARN: payload contains a double quote; using synthetic")
        payload = synth_payload()
        src = "synthetic"
    work = parse_workload(payload)
    ntok = 0
    for _k, toks in work:
        ntok += len(toks)
    log("payload: " + src + ", " + str(len(payload)) + " bytes, "
        + str(len(work)) + " lines, " + str(ntok) + " tokens")

    # HVars size-scaling first: cheapest, highest-value data -- get it
    # into the log before any alloc-heavy segment can hard-reset the G1.
    log("HV_MODE=" + HV_MODE)
    # bignohv/4xonce: build the big strings exactly as "full" does and
    # keep them live for the whole run (see the end-of-main log line);
    # the ONLY difference between the two modes is one hvars_set call.
    big2 = None
    big4 = None
    if HV_MODE in ("bignohv", "4xonce"):
        big2 = payload + "~" + payload
        big4 = payload + "~" + payload + "~" + payload + "~" + payload
        log("big strings built: " + str(len(big2)) + "B + "
            + str(len(big4)) + "B, held live")
        if HV_MODE == "4xonce":
            t0 = ticks()
            hvars_set(HVAR, big4)
            log("hv set 4x once: " + str(ticks() - t0) + "ms")
    if HV_MODE in ("1x", "full"):
        sizes = [("1x", payload)]
        if HV_MODE == "full":
            sizes.append(("2x", payload + "~" + payload))
            sizes.append(("4x", payload + "~" + payload + "~" + payload
                          + "~" + payload))
        for label, p in sizes:
            try:
                gc.collect()
                t0 = ticks()
                hvars_set(HVAR, p)
                w = ticks() - t0
                t0 = ticks()
                rb = hvars_get(HVAR)
                ok = rb == p
                r = ticks() - t0
                log("hv " + label + " (" + str(len(p)) + "B): set=" + str(w)
                    + "ms get+cmp=" + str(r) + "ms match=" + str(ok))
            except Exception as e:
                log("hv " + label + ": FAILED " + str(e))

    run_segments(payload, work, "bare   ")

    # Build-variant ladder, least to most demanding.  The G1 hard-
    # resets somewhere in build territory; whichever rung it dies on
    # narrows the trigger:
    #   bld-q  -- quarter workload, same mix      (volume threshold?)
    #   bld-s  -- pre-stringed tokens, no str(int) (int->str implicated,
    #             format-bug family?)
    #   bld-ng -- full workload, no per-pass collect (gc interplay?)
    #   build  -- the real thing
    work_q = work[:len(work) // 4]
    work_s = []
    for key, toks in work:
        sparts = []
        for t in toks:
            sparts.append(str(t))
        work_s.append((key, sparts))
    for name, fn, coll in (
            ("bld-q ", lambda: build_pass(work_q), True),
            ("bld-s ", lambda: build_pass(work_s), True),
            ("bld-ng", lambda: build_pass(work), False),
            ("build ", lambda: build_pass(work), True),
    ):
        try:
            ts = time_n("bare " + name, fn, collect=coll)
            log("bare    " + fmt(name, ts) + "  raw " + raw(ts))
        except Exception as e:
            log("bare    " + name + ": FAILED " + str(e))

    log("building ballast...")
    f0 = free()
    ballast = make_ballast()
    log("ballast: " + str(len(ballast)) + " entries, "
        + str(f0 - free()) + "B live delta")
    run_segments(payload, work, "ballast")
    try:
        ts = time_n("ballast build ", lambda: build_pass(work))
        log("ballast " + fmt("build ", ts) + "  raw " + raw(ts))
    except Exception as e:
        log("ballast build : FAILED " + str(e))
    ballast = None
    gc.collect()

    if big2 is not None:
        # Reference keeps big2/big4 live across the whole danger zone in
        # both bignohv and 4xonce -- identical liveness, one-call diff.
        log("big strings still live: " + str(len(big2) + len(big4)) + "B")
    if HV_MODE in ("1x", "full", "4xonce"):
        try:
            hvars_set(HVAR, "0")
        except Exception:
            pass

    log("Done. Results in " + LOG)


main()
