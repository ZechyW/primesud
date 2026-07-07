"""Touch probe v3: which primitive corrupts mouse() lift detection?

v1 (tight loop, no ppleval per iter): lifts clean, 60Hz updates, no
glitches. v2 phase C (game-loop cycle: keyboard + GETKEY drain + mouse
+ WAIT(0.01) per poll): pointer read as DOWN continuously for 2.7s
across ~4 separate fast swipes, final y=0 -- lift never seen. So WAIT
and/or GETKEY per iteration breaks mouse() lift reporting.

v2 phase P costs (2026-07-07): GETKEY/Ticks ppleval ~0.3ms, keyboard()/
mouse() ~0ms, WAIT(0.001) ~5ms actual, utime unavailable.

Four 8s capture phases isolate the culprit:
  T: tight loop (control -- expect clean lifts, as v1)
  G: + GETKEY drain per iteration
  W: + WAIT(0.01) per iteration
  B: both (game-loop equivalent -- expect broken, as v2)

Each phase: make 2 FAST downward swipes, then hands off until the
window closes. Reports every mouse() transition (deduped), stroke
count, whether lifts were seen, and the last few raw samples.

Run standalone on physical HP Prime. Results printed and written to
touch.log.
"""
from hpprime import eval as ppleval, keyboard, mouse

_lines = []


def log(msg):
    print(msg)
    _lines.append(msg)


def ticks():
    return int(ppleval("Ticks"))


def capture(name, use_getkey, use_wait):
    log("--- Phase " + name + ": getkey=" + str(use_getkey)
        + " wait=" + str(use_wait) + " ---")
    print("2 FAST downward swipes, then hands off (8s).")
    print(">>> SWIPE NOW <<<")
    samples = []  # (t, x, y); x=-1 marks lifted
    last = None
    t0 = ticks()
    while True:
        t = ticks()
        if t - t0 > 8000 or len(samples) >= 900:
            break
        if use_getkey:
            while int(ppleval("GETKEY")) >= 0:
                pass
        keyboard()
        pt = mouse()[0]
        if pt and pt[0] >= 0:
            cur = (int(pt[0]), int(pt[1]))
        else:
            cur = (-1, -1)
        if cur != last:
            samples.append((t - t0, cur[0], cur[1]))
            last = cur
        if use_wait:
            ppleval("WAIT(0.01)")
    print(">>> WINDOW CLOSED <<<")

    strokes = 0
    lifts = 0
    down = False
    for s in samples:
        if s[1] >= 0 and not down:
            strokes += 1
            down = True
        elif s[1] < 0 and down:
            lifts += 1
            down = False
    log("transitions=" + str(len(samples)) + " strokes=" + str(strokes)
        + " lifts=" + str(lifts) + " end_down=" + str(down))
    log("  tail: " + repr(samples[-6:]))


try:
    capture("T", False, False)
    capture("G", True, False)
    capture("W", False, True)
    capture("B", True, True)
    log("done.")
finally:
    with open("touch.log", "w") as f:
        f.write("\n".join(_lines))
