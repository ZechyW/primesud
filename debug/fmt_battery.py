"""Differentiation battery: %-format output bug vs str(int)-GC crash bug. [PRIMESUD]

Run standalone on physical HP Prime hardware (G1 AND G2 -- the two
bugs have different device reach and this battery maps it).  Needs no
game modules and no save file; swap it into the minimal "Python
debug" appdir in place of save_bench.py (one probe .py per appdir).

Background (docs/PRIME_STRING_FORMAT_BUG.md + docs/BUILTINS.md sec.
G1 memory-corruption bug): two distinct string-subsystem defects are
confirmed on hardware --
  1. OUTPUT bug: %/.format() results get their first byte zeroed in
     comprehension/nested-dict contexts (near-deterministic,
     content-dependent, seen on G2, MWE did not fire on G1).
  2. CRASH bug: bulk str(int) transients + any gc collect corrupt
     the heap (stochastic, G1-probed; "%d" and slice-made strings
     acquitted; number-string cache + int_str fix validated).

v2 (28/07) completes the operator x context matrix: v1 confounded
operator with context (.format tested in the trigger context, % only
flat-arg), so the % ban rested purely on 2026 trigger-1 evidence.
New phases A0/A1/A1t/A2 run FIRST because the G1 dies at fmt-comp
(2/2 prior sessions) and everything after a death is lost.

Phases (each fully logged/flushed before the next starts):
  A0 pct-comp   -- % in the comprehension + nested-dict trigger
                   context: the untested quadrant.
  A1 pct-loop   -- % in a plain loop, same data.
  A1t pct-t1    -- % in a plain loop with the HISTORICAL trigger-1
                   content ("a.%s.age=%s", mud_school/age-0 kept
                   verbatim -- the bug is content-sensitive).
  A2 fmt-loop   -- .format() in a plain loop (context axis for the
                   fmt operator).
  A  fmt-comp   -- 30 reps of the .format() comprehension MWE,
                   every result string verified in full.  Baseline
                   corruption rate per device (G1: known killer).
  B  mwe-gc     -- same with gc.collect() before each rep.  Output
                   bug rate tracking collects => evidence the two
                   bugs share a root.
  C  mwe-press  -- same with ~2.5MB of small live ballast (the
                   original bug's "memory pressure" condition).
  D  pct-verify -- 20 iters x 690 '"%d" % v' vs precomputed
                   expected strings, collect per iter: is % output
                   CORRECT under the collect pressure that already
                   acquitted it of crashing?
  D2 fmt-verify -- same with '"{}".format(v)': does .format()
                   follow %'s clean path or str()'s deadly one?
  E  strint     -- 20 iters of the smallonly-style str(int) storm +
                   collect.  LAST because it kills G1 sessions in
                   ~2-9 iterations; on the G2 it answers whether the
                   GC bug exists there at all.

The battery's own bookkeeping never calls str(int)/%%/.format --
all numbers are rendered via int_str (digit-table concat, the
validated safe path) so the harness cannot contaminate its phases.

Results in fmt_battery.log; copy back per device as
fmt_battery-g1.log / fmt_battery-g2.log.
"""
import gc

LOG = "fmt_battery.log"
REPS = 30
ITERS = 20

_out = []


def log(msg):
    """Print and rewrite the log per line -- crash-survivable."""
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


_DIG = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def int_str(n):
    """str(int) replacement avoiding the firmware formatter (G1
    string-GC bug); digit table + concat only."""
    if n == 0:
        return "0"
    neg = n < 0
    if neg:
        n = -n
    s = ""
    while n:
        s = _DIG[n % 10] + s
        n //= 10
    return ("-" + s) if neg else s


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


# --- MWE data (verbatim shapes from the original test_fmt_bug.py) ---
_skills = {
    101: {"name": "recall"},
    102: {"name": "wands"},
    103: {"name": "bash"},
    104: {"name": "dodge"},
    105: {"name": "parry"},
    106: {"name": "shield block"},
    107: {"name": "second attack"},
    108: {"name": "third attack"},
    109: {"name": "hand to hand"},
    110: {"name": "kick"},
}

_learned = {101: 50, 102: 1, 103: 25, 104: 40, 105: 35,
            106: 20, 107: 15, 108: 10, 109: 75, 110: 60}


def mwe_fmt():
    # The original trigger shape: .format() in a comprehension with a
    # nested dict lookup.
    return ["{} ({}%)".format(_skills[k]["name"], v)
            for k, v in _learned.items()]


def mwe_pct():
    # Same trigger context, % operator: the untested quadrant of the
    # operator x context matrix (v2, 28/07).
    return ["%s (%d%%)" % (_skills[k]["name"], v)
            for k, v in _learned.items()]


def mwe_fmt_loop():
    # .format() in a plain loop (no comprehension).
    out = []
    for k, v in _learned.items():
        out.append("{} ({}%)".format(_skills[k]["name"], v))
    return out


def mwe_pct_loop():
    # % in a plain loop.
    out = []
    for k, v in _learned.items():
        out.append("%s (%d%%)" % (_skills[k]["name"], v))
    return out


# Historical trigger-1 shape and content: "%"-built area-age lines,
# including the content-sensitive mud_school/age-0 pair (renaming the
# tag to "mudschool" made the 2026 probe pass -- content matters, so
# the known-bad content is preserved verbatim).
_areas = (("mud_school", 0), ("midgaard", 15), ("plains", 3),
          ("smurfville", 42), ("mirror", 0), ("gstrand", 7),
          ("dwarven", 11), ("chapel", 0), ("thalos", 28),
          ("sewers", 5))


def t1_pct():
    out = []
    for tag, age in _areas:
        out.append("a.%s.age=%s" % (tag, age))
    return out


def t1_expected():
    exp = []
    for tag, age in _areas:
        exp.append("a." + tag + ".age=" + int_str(age))
    return exp


def mwe_expected():
    # Safe construction: plain concat + int_str.  Same items() order
    # as mwe_fmt within a run (dict unchanged between iterations).
    exp = []
    for k, v in _learned.items():
        exp.append(_skills[k]["name"] + " (" + int_str(v) + "%)")
    return exp


def first_byte(s):
    return int_str(ord(s[0])) if s else "EMPTY"


def check_names(names, exp, tag):
    """Full-string compare; logs each mismatch with its first byte
    (the known corruption signature is a zeroed first byte)."""
    bad = 0
    for i in range(len(exp)):
        if names[i] != exp[i]:
            bad += 1
            log("  BAD " + tag + " entry " + int_str(i)
                + " fb=" + first_byte(names[i])
                + " want-fb=" + first_byte(exp[i])
                + " len=" + int_str(len(names[i]))
                + "/" + int_str(len(exp[i])))
    return bad


def run_mwe_phase(name, build, exp, collect_each, ballast_live):
    log("phase " + name + " reps=" + int_str(REPS)
        + " free=" + int_str(free()))
    total_bad = 0
    for r in range(REPS):
        if collect_each:
            gc.collect()
        names = build()
        total_bad += check_names(names, exp, name + "/r" + int_str(r + 1))
        names = None
        if (r + 1) % 10 == 0:
            log(".. " + name + " " + int_str(r + 1) + "/"
                + int_str(REPS) + " bad-so-far=" + int_str(total_bad))
    log("phase " + name + " done: " + int_str(total_bad)
        + " bad entries of " + int_str(REPS * len(exp))
        + (" (ballast live)" if ballast_live else ""))
    return total_bad


def make_ballast():
    """~2.5MB of small live objects (copy of save_bench's)."""
    ballast = []
    start = free()
    i = 0
    while i < 200000:
        ballast.append([i, "x" + int_str(i), (i, i + 1)])
        i += 1
        if i % 1024 == 0:
            f = free()
            if start:
                if start - f >= 2500000 or f < 1500000:
                    break
            elif i >= 60000:
                break
    return ballast


def make_vals():
    """690 deterministic ints matching the save-payload token mix."""
    vals = []
    for i in range(690):
        v = (i * 37 + (i % 7) * 1000) % 10000
        if i % 90 == 0:
            v = -v
        vals.append(v)
    return vals


def run_convert_phase(name, conv, vals, exp):
    """20 iters of [bulk convert -> verify -> drop -> collect]."""
    log("phase " + name + " iters=" + int_str(ITERS)
        + " vals=" + int_str(len(vals)) + " free=" + int_str(free()))
    total_bad = 0
    for it in range(ITERS):
        outs = []
        for v in vals:
            outs.append(conv(v))
        bad = 0
        for i in range(len(exp)):
            if outs[i] != exp[i]:
                bad += 1
                if bad <= 3:
                    log("  BAD " + name + "/i" + int_str(it + 1)
                        + " idx " + int_str(i)
                        + " fb=" + first_byte(outs[i]))
        total_bad += bad
        outs = None
        log(".. " + name + " " + int_str(it + 1) + "/" + int_str(ITERS)
            + " bad=" + int_str(bad))
        gc.collect()
        log(".. " + name + " " + int_str(it + 1) + " collect ok")
    log("phase " + name + " done: " + int_str(total_bad)
        + " bad conversions")
    return total_bad


def run_strint_phase(vals):
    """smallonly-style storm: known G1 killer, G2 exposure unknown."""
    log("phase strint iters=" + int_str(ITERS)
        + " (G1: expect death within ~2-9 iters)")
    for it in range(ITERS):
        parts = []
        for v in vals:
            parts.append(str(v))
        parts = None
        log(".. strint " + int_str(it + 1) + "/" + int_str(ITERS)
            + " storm ok")
        gc.collect()
        log(".. strint " + int_str(it + 1) + " collect ok")
    log("phase strint done: survived all " + int_str(ITERS)
        + " iterations")


def main():
    log("fmt_battery: format-bug vs str(int)-GC-bug differentiation")
    log("free at start=" + int_str(free()))

    exp_sk = mwe_expected()
    exp_t1 = t1_expected()

    # v2 phase order: % variants FIRST.  The G1 dies at fmt-comp
    # (2/2 prior sessions, fmt_battery-g1.log), so anything after it
    # never runs there; the prior sessions already supply the G1
    # fmt-comp data point, and a v2 death position localizes the %
    # question cleanly.
    run_mwe_phase("A0/pct-comp", mwe_pct, exp_sk, False, False)
    run_mwe_phase("A1/pct-loop", mwe_pct_loop, exp_sk, False, False)
    run_mwe_phase("A1t/pct-t1", t1_pct, exp_t1, False, False)
    run_mwe_phase("A2/fmt-loop", mwe_fmt_loop, exp_sk, False, False)
    run_mwe_phase("A/fmt-comp", mwe_fmt, exp_sk, False, False)
    run_mwe_phase("B/fmt-comp-gc", mwe_fmt, exp_sk, True, False)

    log("building ballast for C...")
    ballast = make_ballast()
    log("ballast " + int_str(len(ballast)) + " entries, free="
        + int_str(free()))
    run_mwe_phase("C/fmt-comp-press", mwe_fmt, exp_sk, False, True)
    ballast = None
    gc.collect()

    vals = make_vals()
    exp = []
    for v in vals:
        exp.append(int_str(v))

    run_convert_phase("D/pct", lambda v: "%d" % v, vals, exp)
    run_convert_phase("D2/fmt", lambda v: "{}".format(v), vals, exp)

    # E last: kills G1 sessions; everything above is already on disk.
    run_strint_phase(vals)

    log("Done. Results in " + LOG)


main()
