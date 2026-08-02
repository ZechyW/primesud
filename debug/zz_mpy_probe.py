"""Toy .mpy import probe, on-device. [PRIMESUD]

Decisive go/no-go for the .mpy precompilation track: the 37s G1 boot
import phase is 98-99% compiler time (see zz_compile_probe), so shipping
precompiled bytecode removes nearly all of it -- IF the firmware's
import machinery can load .mpy files at all (MICROPY_PERSISTENT_CODE_LOAD
plus a filesystem .mpy lookup, both unknowable from the REPL on 1.9.4).

Two toy modules ship alongside, compiled with mpy-cross 1.9.4
(bytecode format v3, matching sys.implementation 1.9.4):

  mpytoy.mpy   default flags (unicode, feature byte 0x02)
  mpytoy2.mpy  -mno-unicode variant (in case firmware flag byte differs)

Each toy sets a sentinel const and computes one via a function call, so
a passing import proves const loading AND code-object execution. Either
toy importing = track alive.

CRITICAL payload rule: the toy .py SOURCES must NOT ship -- a .py in
the appdir auto-imports and masks the .mpy test. Only the .mpy files go.
Standing rules: one self-running .py per appdir (this file); probe
payloads exclude primesud.py (no game boot).
Results printed and written to zz_mpy_probe.log.
"""

LOG = "zz_mpy_probe.log"
_out = []


def log(msg):
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def try_toy(name, expect):
    try:
        m = __import__(name)
    except Exception as exc:
        log(name + ": IMPORT FAILED " + repr(exc))
        return False
    ok = getattr(m, "MPYTOY_OK", None)
    tw = getattr(m, "MPYTOY_TWICE", None)
    if ok == expect and tw == expect + expect:
        log(name + ": import OK, consts OK, function-call OK")
    else:
        log(name + ": import OK but values BAD " + repr(ok) + " " + repr(tw))
    return True


def main():
    log("zz_mpy_probe: can firmware import .mpy? (mpy-cross 1.9.4, format v3)")
    ok1 = try_toy("mpytoy", 12345)
    ok2 = try_toy("mpytoy2", 21212)
    if ok1 or ok2:
        log("VERDICT: .mpy loading WORKS -- proceed to --mpy dist track")
        if ok1 != ok2:
            log("(only one flag variant loads -- note which)")
    else:
        log("VERDICT: .mpy loading DEAD on this firmware -- track closed")
    log("Done. Results in " + LOG)


main()
