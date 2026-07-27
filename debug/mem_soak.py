"""Heap soak: map usable Python heap and hunt corruption on device. [PRIMESUD]

Run standalone on the physical HP Prime (no game modules).  Fills the
heap with 32KB pattern chunks until MemoryError, then verifies every
chunk twice.  One run answers four questions the save_bench crashes
raised (27/07, G1):

  usable heap    -- chunks reached before MemoryError vs the configured
                    heap size: quantifies firmware-pool depletion when
                    run as a second session without an on+symb restore
  fixed landmine -- a hang/reset always at the same fill count marks a
                    bad physical RAM region / firmware hole at a fixed
                    offset into heap growth (progress logs every 8
                    chunks bound it to a 256KB window)
  silent flips   -- verify passes catch pattern mismatches: chunk index
                    + byte offset + got/want logged for the first 5
  churn at full  -- the verify loop allocates a 32KB expected chunk per
                    compare under a near-full heap (small headroom is
                    made by dropping the last 4 chunks), which is
                    exactly the alloc-churn condition the save_bench
                    failures implicated

Log flushed line by line (survives hard reset/hang) to mem_soak.log.
Swap this file with save_bench.py in the debug appdir -- the Prime
executes every .py in the appdir at app start, so only one probe may
be present per session.
"""
import gc
from hpprime import eval as ppleval

CHUNK = 32 * 1024
MAX_CHUNKS = 400  # 12.5MB cap: bounds PC smoke runs / oversized heaps
FLUSH_EVERY = 8
LOG = "mem_soak.log"

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


def pat(i):
    """Per-chunk fill byte: varies chunk to chunk, never 0x00/0xFF-only."""
    return (i * 37 + 13) & 0xFF


def main():
    log("mem_soak: chunk=" + str(CHUNK) + "B max=" + str(MAX_CHUNKS))
    log("free at start: " + str(free()))
    gc.collect()
    log("free after collect: " + str(free()))

    chunks = []
    err = ""
    t0 = ticks()
    try:
        for i in range(MAX_CHUNKS):
            chunks.append(bytes([pat(i)]) * CHUNK)
            if (i + 1) % FLUSH_EVERY == 0:
                log("fill " + str(i + 1) + " ~"
                    + str((i + 1) * CHUNK // 1024) + "KB free=" + str(free()))
    except MemoryError:
        err = " (MemoryError)"
    filled = len(chunks)
    log("filled " + str(filled) + " chunks = " + str(filled * CHUNK // 1024)
        + "KB in " + str(ticks() - t0) + "ms" + err)

    # Headroom for the verify loop's 32KB expected-pattern alloc and the
    # per-line log writes: drop the last 4 chunks (128KB).
    while len(chunks) > 0 and len(chunks) > filled - 4:
        chunks.pop()
    gc.collect()
    filled = len(chunks)

    for p in (1, 2):
        bad = 0
        t0 = ticks()
        for i in range(filled):
            if chunks[i] != bytes([pat(i)]) * CHUNK:
                bad += 1
                if bad <= 5:
                    c = chunks[i]
                    e = pat(i)
                    off = -1
                    got = -1
                    for j in range(len(c)):
                        if c[j] != e:
                            off = j
                            got = c[j]
                            break
                    log("MISMATCH chunk " + str(i) + " off " + str(off)
                        + " got " + str(got) + " want " + str(e))
            if (i + 1) % 64 == 0:
                log(".. verify " + str(p) + " at " + str(i + 1))
        log("verify pass " + str(p) + ": " + str(bad) + " bad of "
            + str(filled) + " in " + str(ticks() - t0) + "ms")

    chunks = None
    gc.collect()
    log("free after release: " + str(free()))
    log("Done. Results in " + LOG)


main()
