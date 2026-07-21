"""Benchmark line-by-line vs batched colour rendering on device.

Run standalone on the physical HP Prime (same dir as the game modules,
so imports resolve). Renders a synthetic room-look screen (title,
automap+desc rows, exits, items, mobs -- realistic colour-run mix) N
times per method, alternating per-line and batched passes, then writes
min/avg ms per method to renderbench.log and exits WITHOUT loading the
game world.

Per-line = the pre-batching draw path (one tr.print call per line).
Batched  = one tr.print(list) call -> terminal.print_lines: colour-
grouped, composed offscreen in SCRATCH_GROB, blitted once.

Blit-only = the single scratch->screen blit re-timed alone.  With
offscreen compose the screen stays unchanged while the batch composes
(total = batched ms), then updates in one blit -- so blit-only IS the
perceived transition time; there is no char-by-char fill-in to eyeball.

Noblit = batched pass with strblit2/pixon/dimgrob no-op'd inside
terminal: the pure Python side (wrap + group + compose loop).  Blit
share of a batch = batched - noblit.  Raw strblit2/pixon = tight
constant-arg loops, the true native per-call cost with zero Python
allocation -- run standalone AND with the full dist to expose how much
of the per-call cost scales with live heap.
"""
import gc
from hpprime import eval as ppleval, strblit2

import terminal
from terminal import init_terminal
from config import SCRATCH_GROB

N = 10

# Synthetic look output: 1 title + 8 automap+desc rows + exits +
# 2 items + 3 mobs. Colour-run structure mimics a busy Midgaard room.
LINES = [
    "{YTemple Square{x",
    "{D+-----------+{x {wYou are standing in the temple square.  Huge",
    "{D|{x   {g:{x   {g:{x   {D|{x {wmarble steps lead up to the temple gate.  The",
    "{D|{x {g:{x {Y#{x {g:{x {Y#{x {D|{x {wentrance to the Grunting Boar Inn is to the",
    "{D|{x   {R@{x   {g:{x   {D|{x {wwest, and the famous market square lies east",
    "{D|{x {g:{x {Y#{x {g:{x {Y#{x {D|{x {wof here.  A large sign hangs over the temple",
    "{D|{x   {g:{x   {g:{x   {D|{x {wdoors, and the city gates lie beyond the",
    "{D+-----------+{x {wsquare to the north and south.",
    "{g[Exits: north east south west up]{x",
    "     A large fountain made of white marble is here.",
    "( 2) A shiny gold coin lies on the ground here.",
    "{MA beastly fido wanders around looking for food.{x",
    "{MThe temple guard watches over the square.{x",
    "{MHassan is here, waiting for a fight.{x",
]


def ticks():
    return int(ppleval("Ticks"))


def per_line():
    tr = terminal.tr
    for line in LINES:
        tr.print(line)


def batched():
    terminal.tr.print(LINES)


def main():
    init_terminal()
    tr = terminal.tr
    a = []  # per-line ms
    b = []  # batched ms
    for _ in range(N):
        tr.clear()
        gc.collect()
        t0 = ticks()
        per_line()
        a.append(ticks() - t0)

        tr.clear()
        gc.collect()
        t0 = ticks()
        batched()
        b.append(ticks() - t0)

    # Batched-noblit: no-op the draw primitives inside terminal, re-run
    # the batched pass -- isolates the Python side (wrap + group + loop)
    # from the blit calls.  Blit share = batched - noblit.
    # hasattr: pc_shim's terminal has no draw primitives (blits no-op
    # there anyway, the unpatched pass measures the same thing).
    _prims = hasattr(terminal, "strblit2")
    if _prims:
        _real_sb = terminal.strblit2
        _real_px = terminal.pixon
        _real_dg = terminal.dimgrob
        _noop = lambda *a: None
        terminal.strblit2 = _noop
        terminal.pixon = _noop
        terminal.dimgrob = _noop
    c = []
    for _ in range(N):
        tr.clear()
        gc.collect()
        t0 = ticks()
        batched()
        c.append(ticks() - t0)
    if _prims:
        terminal.strblit2 = _real_sb
        terminal.pixon = _real_px
        terminal.dimgrob = _real_dg

    # Raw per-call cost of the draw primitives: tight loops, constant
    # args, no Python allocation -- what does one native call cost?
    from hpprime import pixon
    n_raw = 500
    cw = getattr(tr, "char_width", 5)
    chh = getattr(tr, "char_height", 10)
    gc.collect()
    t0 = ticks()
    for _ in range(n_raw):
        strblit2(SCRATCH_GROB, 0, 0, cw, chh, 9, 0, 0, cw, chh)
    raw_sb = ticks() - t0
    gc.collect()
    t0 = ticks()
    for _ in range(n_raw):
        pixon(SCRATCH_GROB, 0, 0, 0)
    raw_px = ticks() - t0

    # Blit-only: SCRATCH_GROB still holds the last composed batch; re-time
    # just the scratch->screen blit (Ticks is 1ms-grained, so loop it).
    n_blit = 20
    # getattr: pc_shim's tml lacks the pixel-geometry attrs (blits no-op).
    h = len(LINES) * getattr(tr, "char_height", 10)
    w = getattr(tr, "width", 320)
    gc.collect()
    t0 = ticks()
    for _ in range(n_blit):
        strblit2(0, 0, 0, w, h, SCRATCH_GROB, 0, 0, w, h)
    blit_total = ticks() - t0

    out = []
    out.append("render_bench: " + str(len(LINES)) + " lines x " + str(N) + " passes")
    out.append(_fmt("per-line", a))
    out.append(_fmt("batched ", b))
    out.append(_fmt("noblit  ", c))
    out.append("raw strblit2 char-size x" + str(n_raw) + ": "
               + str(raw_sb) + "ms = " + str(raw_sb * 1000 // n_raw)
               + "us/call")
    out.append("raw pixon x" + str(n_raw) + ": " + str(raw_px)
               + "ms = " + str(raw_px * 1000 // n_raw) + "us/call")
    out.append("blit-only: " + str(blit_total) + "ms / " + str(n_blit)
               + " blits = ~" + str(blit_total // n_blit)
               + "ms perceived transition")
    out.append("raw per-line: " + _raw(a))
    out.append("raw batched : " + _raw(b))
    out.append("raw noblit  : " + _raw(c))

    # str()+concat payload throughout, then joined -- pitfall 8 safe
    with open("renderbench.log", "w") as f:
        f.write("\n".join(out) + "\n")

    tr.clear()
    for line in out:
        tr.print(line)
    tr.print("Done. Results in renderbench.log")


def _fmt(name, times):
    lo = times[0]
    total = 0
    for t in times:
        total += t
        if t < lo:
            lo = t
    return (name + ": min=" + str(lo) + "ms avg="
            + str(total // len(times)) + "ms")


def _raw(times):
    parts = []
    for t in times:
        parts.append(str(t))
    return " ".join(parts)


main()
