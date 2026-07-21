"""Benchmark line-by-line vs batched colour rendering on device.

Run standalone on the physical HP Prime (same dir as the game modules,
so imports resolve). Renders a synthetic room-look screen (title,
automap+desc rows, exits, items, mobs -- realistic colour-run mix) N
times per method, alternating per-line and batched passes, then writes
min/avg ms per method to renderbench.log and exits WITHOUT loading the
game world.

Per-line = the pre-batching draw path (one tr.print call per line).
Batched  = one tr.print(list) call -> terminal.print_lines, colour-
grouped, biggest group first.

Note: batching targets total time (fewer font recolours); the
biggest-group-first order additionally improves perceived fill-in,
which this benchmark cannot measure -- eyeball that part.
"""
import gc
from hpprime import eval as ppleval

import terminal
from terminal import init_terminal

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

    out = []
    out.append("render_bench: " + str(len(LINES)) + " lines x " + str(N) + " passes")
    out.append(_fmt("per-line", a))
    out.append(_fmt("batched ", b))
    out.append("raw per-line: " + _raw(a))
    out.append("raw batched : " + _raw(b))

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
