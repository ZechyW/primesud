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
#   "bigloop" -- REPLACES the normal run: 20 iterations of [16/32KB
#                concat chain -> full build_pass small-alloc storm ->
#                drop -> collect], logged per iteration.  bignohv
#                overturned the HVars conviction (reset with zero HVars
#                traffic, clean pool, 27/07) but split 1 dead / 1 clean
#                -- the failure is stochastic, so single runs carry ~1
#                bit each.  This mode yields ~20 trials per session:
#                death rate + iteration counts, or 20 survivals to
#                weaken the big-string hypothesis too.
#                First device run died in iteration 3 (save_bench-6.log)
#                -- high-rate repro confirmed.
HV_MODE = "bigloop"

# bigloop composition bisect.  build-storm-only is effectively
# acquitted (clean -4/-5 runs each executed ~25 build_pass calls with
# no big strings), so:
#   "both"    -- concat chain + build storm (the -6.log death repro)
#   "bigonly" -- concat chain only, no build storm.  CLEAN over ~60+
#                trials (20/20 + several clear-rerun sessions, 27/07):
#                big strings alone acquitted; the interaction with the
#                small-alloc storm is required.
#   "bigmul"  -- like bigonly but the 32KB string is made by
#                (payload+"~")*4 (2 allocs, no 16/24KB chain temps).
#   "both8k"  -- ONE fresh ~8KB concat + build storm + collect per
#                iteration: the real game save's exact allocation
#                pattern.  DIED after iteration 2 on-device (27/07):
#                the in-game occasional G1 crashes are this bug at
#                today's payload size; the tight-cycle repetition is
#                what concentrates the rate vs. minutes-apart saves.
#   "chunked" -- proposed size mitigation: storm + collect per
#                iteration, payload assembled as hard-capped 2048B
#                pieces.  DIED iteration 4 on-device (save_bench-7.log)
#                -- size is NOT the knob; mitigation-by-chunking
#                falsified before it reached the game.
#   "chunkedng" -- chunked without the explicit per-cycle gc.collect.
#                CLEAN over multiple sessions (save_bench-8.log,
#                27/07): no collect = no death.  (Early "explicit
#                collect is the trigger" read was overturned by the
#                autogc death -- see below.)
#   "autogc"  -- chunkedng at 300 iterations (~30MB garbage):
#                guarantees several alloc-triggered auto-collects
#                (mem_free logged every 10 iters shows them fire).
#                DIED at ~iter 33 (save_bench-9.log) -- exactly when
#                heap exhaustion forced the first auto-collect (free
#                fell 5.5MB -> 0.5MB with no dips before death).
#                Verdict: any collect over churned mixed garbage is
#                unsafe; explicit-vs-auto irrelevant.
# Garbage-composition matrix (27/07, post-verdict): the deadly kinds
# all mixed a small-alloc storm WITH medium/big payload strings; the
# clean kinds had one ingredient or no collect.  These isolate which
# ingredient loads the gun -- each runs 20x [make garbage -> drop ->
# explicit collect]:
#   "smallonly"  -- token-str storm only (~965 small str allocs + 173
#                list allocs per iter), NO line/medium/big strings.
#                RESET in iteration 4 (save_bench-10.log, 27/07):
#                small string churn alone is sufficient; medium/big
#                strings were passengers in every earlier deadly kind.
#                Caveat: the clean -4/-5 sessions survived ~25
#                storm+collect build passes, improbably lucky at this
#                rate -- per-collect risk also depends on heap state,
#                not garbage type alone.
#   "smallnostr" -- same alloc count/shape but tuples of existing
#                refs: zero new string objects.  CLEAN 20/20 collects
#                in the same session whose smallonly phase then died
#                at its iteration 4 (save_bench-11.log, 27/07):
#                string-object-specific, generic allocator bug
#                excluded (str-format-bug family).
#   "medonly" -- 2KB payload slices only (4 medium strs per iter), no
#                small churn.  Complements bigonly (which was 8-32KB).
#   "matrix"  -- all three in one session, 20 iters each (smallnostr
#                -> smallonly -> medonly).  Phase boundaries are
#                scrubbed by the per-iteration collects, so a clean
#                run acquits all three at once; a death only
#                provisionally convicts its phase (cross-phase pinned
#                residue possible) -- rerun that kind isolated.
BIGLOOP_KIND = "medonly"

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


def scan_work(work, tag):
    """Integrity-check the work list after a spurious failure: logs the
    first 5 elements whose shape/types no longer match what
    parse_workload built.  0 bad + an impossible TypeError means the
    corruption sits in VM stack/iterator slots, not in the data."""
    bad = 0
    for i in range(len(work)):
        e = work[i]
        ok = isinstance(e, tuple) and len(e) == 2
        if ok:
            k = e[0]
            toks = e[1]
            ok = isinstance(k, str) and isinstance(toks, list)
        if not ok:
            bad += 1
            if bad <= 5:
                log("SCAN " + tag + ": elem " + str(i) + " -> "
                    + str(type(e)))
    log("SCAN " + tag + ": " + str(bad) + " bad of " + str(len(work)))
    return bad


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
    if HV_MODE == "bigloop":
        # ~20 trials of the death-zone pattern per session: big concat
        # chain + full small-alloc storm, drop, collect.  Per-iteration
        # log flush pinpoints a hard death; caught exceptions (the
        # spurious TypeErrors) are counted and the blamed data scanned.
        log("bigloop kind=" + BIGLOOP_KIND)
        errs = 0
        if BIGLOOP_KIND == "matrix":
            plan = (["smallnostr"] * 20 + ["smallonly"] * 20
                    + ["medonly"] * 20)
        else:
            plan = [BIGLOOP_KIND] * (300 if BIGLOOP_KIND == "autogc"
                                     else 20)
        iters = len(plan)
        n_str = "/" + str(iters)
        for it in range(iters):
            kind = plan[it]
            try:
                b2 = None
                b4 = None
                lines = None
                if kind in ("chunked", "chunkedng", "autogc"):
                    # Mitigated save assembly: storm as usual, but the
                    # payload only ever exists as ~2KB join groups.
                    lines = build_pass(work)
                    # Streaming chunker, hard 2048B cap: pieces may
                    # split mid-line (load rejoins before parsing), so
                    # a long m=/p.eq line cannot inflate a piece.
                    groups = []
                    buf = ""
                    for ln in lines:
                        s = ln + "~"
                        while s:
                            room = 2048 - len(buf)
                            if len(s) <= room:
                                buf = buf + s
                                s = ""
                            else:
                                buf = buf + s[:room]
                                groups.append(buf)
                                buf = ""
                                s = s[room:]
                    if buf:
                        groups.append(buf)
                    mx = 0
                    tot = 0
                    for g in groups:
                        if len(g) > mx:
                            mx = len(g)
                        tot += len(g)
                    log("bigloop " + str(it + 1) + n_str + " ok chunked "
                        + str(len(groups)) + " groups, max " + str(mx)
                        + "B, tot " + str(tot) + "B")
                    groups = None
                elif kind == "smallonly":
                    # Token-str storm only: same str()/append churn as
                    # build_pass but no line strings, so every garbage
                    # object is a small str or a small list.
                    nal = 0
                    for _key, toks in work:
                        parts = []
                        for t in toks:
                            parts.append(str(t))
                        nal += len(parts)
                        parts = None
                    log("bigloop " + str(it + 1) + n_str + " ok small "
                        + str(nal) + " str allocs")
                elif kind == "smallnostr":
                    # Same alloc count/shape, zero new string objects:
                    # tuples of existing refs + list churn only.
                    nal = 0
                    for _key, toks in work:
                        parts = []
                        for t in toks:
                            parts.append((t, it))
                        nal += len(parts)
                        parts = None
                    log("bigloop " + str(it + 1) + n_str + " ok nostr "
                        + str(nal) + " tuple allocs")
                elif kind == "medonly":
                    # Medium strings only: 2KB slices of the payload,
                    # no small-alloc churn at all.
                    groups = []
                    i = 0
                    while i < len(payload):
                        groups.append(payload[i:i + 2048])
                        i += 2048
                    log("bigloop " + str(it + 1) + n_str + " ok med "
                        + str(len(groups)) + " x <=2048B slices")
                    groups = None
                else:
                    if kind == "bigmul":
                        b2 = (payload + "~") * 2
                        b4 = (payload + "~") * 4
                    elif kind == "both8k":
                        b2 = payload + "~"  # one fresh game-save-sized alloc
                    else:
                        b2 = payload + "~" + payload
                        b4 = (payload + "~" + payload + "~" + payload
                              + "~" + payload)
                    lines = (build_pass(work)
                             if kind in ("both", "both8k") else None)
                    log("bigloop " + str(it + 1) + n_str + " ok "
                        + str(len(b2) + (len(b4) if b4 else 0)) + "B big"
                        + ((", " + str(len(lines)) + " lines")
                           if lines else ""))
            except Exception as e:
                errs += 1
                log("bigloop " + str(it + 1) + n_str + " EXC " + str(e))
                scan_work(work, "work/iter" + str(it + 1))
            b2 = None
            b4 = None
            lines = None
            if kind == "autogc":
                # No explicit collect; watch auto-GC via mem_free dips.
                if (it + 1) % 10 == 0:
                    log(".. " + str(it + 1) + " free=" + str(free()))
            elif kind == "chunkedng":
                log(".. " + str(it + 1) + " end (no collect)")
            else:
                gc.collect()
                # Separate flush: a death here blames the collect, not
                # the next iteration's concat/build.
                log(".. " + str(it + 1) + " collect ok")
        log("bigloop: " + str(errs) + " caught errors in " + str(iters)
            + " iterations")
        log("Done. Results in " + LOG)
        return
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
            # Spurious 'list is not an iterator' TypeErrors observed
            # here on-device (27/07): fingerprint the data they blame.
            scan_work(work, "work/" + name.strip())
            scan_work(work_s, "work_s/" + name.strip())

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
