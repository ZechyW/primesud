"""Probe v3: GETKEY queue depth + capture during PURE-Python computation.

Findings so far (2026-07-06, physical Prime):
  v1: keyboard() bitmask misses press+release inside busy loop; PPL GETKEY
      drains it afterwards, in order; cas.get_key reads same queue.
  v2: GETKEY codes == keyboard() bit indices (10/10 MATCH); no hold
      auto-repeat; repeated same-key presses do enqueue ([37,38,39,37]);
      but mashing ~15 keys during busy loop drained only 4 -- limiter
      unknown (queue depth? firmware scan rate under load? tap speed?).

CAVEAT the v1/v2 busy loop called ppleval("Ticks") EVERY iteration; real
game computations are pure Python and never yield into firmware eval.
If the firmware only enqueues key events while Python sits in
eval()/WAIT(), GETKEY-drain won't fix real drops. v3 separates all this:

  Phase H: queue depth. IDLE 10s window; tap ~15 keys at a comfortable
           pace (distinct full presses); drain once at end. Count < taps
           = queue capacity found.
  Phase I: PURE-Python busy loop 5s (zero ppleval inside); press ~6 keys
           deliberately (~1 per second, firm presses). Drain after.
           This mirrors real game lag. All 6 captured = fix is valid.
  Phase J: same as I but ppleval("Ticks") each iteration (v1-style).
           Compare capture rate against I.
  Phase G: retry. Shift then digit (fast, in order) during phase-I-style
           pure busy loop; expect [41, digit] -- modifiers reach queue.

Run standalone on physical HP Prime. Results printed and written to
keydrop.log. On key exits; log flushed either way.

Report alongside the log: how many keys you actually pressed in H and I/J.
"""
from hpprime import eval as ppleval, keyboard

_lines = []


def log(msg):
    print(msg)
    _lines.append(msg)


def ticks():
    return int(ppleval("Ticks"))


def busy_iters(target):
    """Pure-Python busy loop, no ppleval -- mirrors real game computation.

    Single shared loop for calibration AND phases: identical bytecode,
    identical speed (locals only; a globals-based compare runs several
    times slower on MicroPython and wrecks the calibration).
    """
    n = 0
    while n < target:
        n += 1


def _calibrate():
    """Iterations of busy_iters per ms (min 200ms sample)."""
    iters = 200000
    while True:
        t0 = ticks()
        busy_iters(iters)
        dt = ticks() - t0
        if dt >= 200:
            return iters // dt
        iters *= 10


def busy_pure(ms, iters_per_ms):
    """Run busy_iters for ~ms; returns actual elapsed ms (measured)."""
    t0 = ticks()
    busy_iters(ms * iters_per_ms)
    return ticks() - t0


def busy_eval(ms):
    """v1-style busy loop: ppleval('Ticks') every iteration."""
    t0 = ticks()
    n = 0
    while ticks() - t0 < ms:
        n += 1


def drain_getkey(limit=64):
    codes = []
    while len(codes) < limit:
        k = int(ppleval("GETKEY"))
        if k < 0:
            break
        codes.append(k)
    return codes


def arm(msg):
    log(msg)
    print("(hands off keys...)")
    while keyboard() != 0:
        ppleval("WAIT(0.05)")
    ppleval("WAIT(1)")
    drain_getkey()


def phase_h():
    log("--- Phase H: queue depth while idle ---")
    arm("Tap ~15 DIFFERENT-ish keys, comfortable pace, full presses,"
        " while '>>> PRESS NOW <<<' shows (10s). Count your presses.")
    print(">>> PRESS NOW <<<")
    t0 = ticks()
    while ticks() - t0 < 10000:
        ppleval("WAIT(0.05)")
    codes = drain_getkey()
    print(">>> WINDOW CLOSED <<<")
    log("drained=" + str(len(codes)) + " codes=" + str(codes))


def phase_i(ipms):
    log("--- Phase I: PURE-Python busy loop 5s ---")
    arm("Press ~6 keys, one per second, FIRM presses, while"
        " '>>> PRESS NOW <<<' shows. Count your presses.")
    print(">>> PRESS NOW <<<")
    dt = busy_pure(5000, ipms)
    codes = drain_getkey()
    print(">>> WINDOW CLOSED <<<")
    log("window=" + str(dt) + "ms drained=" + str(len(codes))
        + " codes=" + str(codes)
        + " (all captured = GETKEY fix valid for real game lag)")


def phase_j():
    log("--- Phase J: ppleval-per-iter busy loop 5s (comparison) ---")
    arm("Same as before: ~6 keys, one per second, firm, during"
        " '>>> PRESS NOW <<<'. Count your presses.")
    print(">>> PRESS NOW <<<")
    busy_eval(5000)
    codes = drain_getkey()
    print(">>> WINDOW CLOSED <<<")
    log("drained=" + str(len(codes)) + " codes=" + str(codes))


def phase_g(ipms):
    log("--- Phase G: Shift+digit combo inside pure busy loop ---")
    arm("Press Shift then a digit (fast, in order) DURING"
        " '>>> PRESS NOW <<<' (5s).")
    print(">>> PRESS NOW <<<")
    dt = busy_pure(5000, ipms)
    codes = drain_getkey()
    print(">>> WINDOW CLOSED <<<")
    log("window=" + str(dt) + "ms codes=" + str(codes)
        + " (expect [41, digit-code] in order)")


try:
    log("calibrating pure loop...")
    ipms = _calibrate()
    log("iters_per_ms=" + str(ipms))
    phase_h()
    phase_i(ipms)
    phase_j()
    phase_g(ipms)
    log("done.")
finally:
    with open("keydrop.log", "w") as f:
        f.write("\n".join(_lines))
