"""Compile-vs-exec split of boot import cost, on-device. [PRIMESUD]

Follow-up to zz_import_bench: the 37s G1 import phase proved
structure-bound, not byte-bound (52% minification changed nothing).
``.mpy`` precompilation can only remove the lex/parse/compile share, so
this probe splits a module's first-import cost into its two halves:

  compile share:  ``compile(src, name, "exec")`` -- pure translation,
                  no imports run, nothing executed.
  exec share:     ``exec(code_obj, fresh_ns)`` with the module's whole
                  dependency closure already resident, so its import
                  statements are sys.modules hits and the timing is the
                  module body itself (function objects, tables, qstrs).

Per target the order is: read source, import the module normally
(untimed -- makes deps resident, mirrors boot heap growth), compile N
passes, exec N passes into throwaway namespaces. Targets were checked
for module-level cross-module side effects (none: bodies only build
their own namespace), so repeated exec is safe; the throwaway
namespaces are discarded and the game later boots off the real import.

``compile()`` is unverified on-device (``exec()`` is proven -- area
files load through it); the probe tests it first and logs a dead-end
verdict if absent.

Runs in the firmware's first auto-import slot (zz_ prefix, reverse-alpha
order). Standing rule: only ONE self-running .py in the appdir -- swap
this in FOR zz_import_bench.py, never alongside. Ship with the full
game closure including primesud.py; boot continues into the game.
Results printed and written to zz_compile_probe.log.
"""
import gc
from hpprime import eval as ppleval
from util import int_str

LOG = "zz_compile_probe.log"
# code-heavy / data-heavy / code-huge
TARGETS = ("combat", "skills_table", "mobprog")
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


def ticks():
    return int(ppleval("Ticks"))


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


def probe(name):
    fname = name + ".py"
    with open(fname) as f:
        src = f.read()
    log(name + ": " + int_str(len(src)) + " bytes source")

    # Deps resident first so compile and exec run at the same heap state
    # (alloc cost grows with heap occupancy) and exec's imports no-op.
    gc.collect()
    t0 = ticks()
    __import__(name)
    log(".. real import (closure, reference) " + int_str(ticks() - t0) + "ms")

    code = None
    ctotal = 0
    for i in range(N):
        gc.collect()
        t0 = ticks()
        code = compile(src, fname, "exec")
        dt = ticks() - t0
        ctotal += dt
        log(".. compile pass " + int_str(i + 1) + "/" + int_str(N) + " "
            + int_str(dt) + "ms")

    etotal = 0
    for i in range(N):
        ns = {"__name__": "zzprobe"}
        gc.collect()
        t0 = ticks()
        exec(code, ns)
        dt = ticks() - t0
        etotal += dt
        log(".. exec pass " + int_str(i + 1) + "/" + int_str(N) + " "
            + int_str(dt) + "ms")

    cavg = ctotal // N
    eavg = etotal // N
    share = cavg * 100 // (cavg + eavg) if (cavg + eavg) else 0
    log(name + ": compile " + int_str(cavg) + "ms, exec " + int_str(eavg)
        + "ms -- compile share " + int_str(share) + "%")
    log("mem free: " + int_str(free()))
    log("")


def main():
    log("zz_compile_probe: compile-vs-exec split per module")
    log("mem free start: " + int_str(free()))
    try:
        compile("0", "probe", "exec")
    except NameError:
        log("compile() UNAVAILABLE -- split unmeasurable on-device;")
        log(".mpy prize cannot be sized this way. Done.")
        return
    log("compile() available")
    log("")
    for name in TARGETS:
        try:
            probe(name)
        except Exception as exc:
            log(name + ": FAILED " + repr(exc))
    log("Done. Results in " + LOG)


main()
