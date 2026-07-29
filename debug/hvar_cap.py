"""HVar length-cap hunt + save-path I/O timings + chunked mitigation. [PRIMESUD]

Motivated by the 29/07 device failure: save_world raised "save
verification failed (readback mismatch)" and the HVar held a payload
truncated mid-token ("...conditioni90d0:") once item-template snapshot
"it." lines pushed the save past some PPL-side length cap.  hvars_set
embeds the whole payload in ONE eval string ('HVars("x"):="<payload>"',
prime_platform.py) -- prime suspect.  PC shim has no such cap.

Run standalone on the physical HP Prime -- needs NO game modules.
Remove other self-running probes (resetprobe.py etc.) from the appdir
first: Prime auto-imports every .py.

Sections, data-before-death order (log flushed per line):
  cap    -- size ladder 1K..80K: hvars_set, then PPL-side stored length
            (DIM) vs Python readback length vs full compare.  Separates
            write cap (stored < sent) from read cap (stored ok,
            readback short).  First failure -> bisect the exact byte.
  timing -- hvset / hvget+cmp / fwrite / fread at each size that fits
            under the cap, N=3, min/avg.  Answers "where did save
            block": PPL eval parse vs file I/O.
  chunk  -- proposed mitigation measured before it reaches the game:
            append-loop writes (HVars(x):=HVars(x)+"piece") and MID()
            piece reads at 1K/2K/4K piece sizes, target 2x the write
            cap; verified byte-identical round trip.  Also times a
            PLAIN hvars_get over the chunk-written value: direct
            read-cap test independent of the write path.
  codec  -- inlined _snap_encode (world.py) over 30 synthetic item
            templates: cost of building the new "it." save block.
            Int rendering via cached digit-concat (game's num_str
            pattern, validated by save_bench cachedstr) -- NEVER bulk
            str(int) (G1 str(int)-GC bug, PRIME_FIRMWARE_BUGS.md).

Results printed and written to hvar_cap.log.  Uses HVar "hvcap" (never
the real primesud_save); reset to "0" at the end.  Leaves hvar_cap.tmp
in the appdir (fwrite/fread target).
"""
import gc
from hpprime import eval as ppleval

LOG = "hvar_cap.log"
HVAR = "hvcap"
TMP = "hvar_cap.tmp"
N = 3
SIZES = (1024, 2048, 4096, 8192, 12288, 16384, 24576, 32768, 49152,
         65536, 81920)

_out = []


def log(msg):
    """Print and flush to the log file immediately -- a firmware crash
    mid-run must not lose lines already produced (save_bench.py
    convention)."""
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def ticks():
    return int(ppleval("Ticks"))


# Inlined from prime_platform.py (keep in sync if the wrappers change).
def hvars_set(name, value):
    ppleval('HVars("' + name + '"):="' + value + '"')


def hvars_get(name):
    return ppleval('HVars("' + name + '")')


def hvars_dim(name):
    """PPL-side stored length of the HVar -- what actually landed,
    independent of the eval return path."""
    return int(ppleval('DIM(HVars("' + name + '"))'))


_DIG = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def int_str(n):
    """str(int) replacement: digit-table concat, never the firmware
    formatter (G1 str(int)-GC bug avoidance, save_bench-validated)."""
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


_FILL = "abcdefghijklmnopqrstuvwxyz0123456789" * 2


def make_payload(n):
    """n bytes of 64-char blocks, each tagged with its own offset, so a
    truncation point reads straight off the log/HVar tail."""
    blocks = []
    pos = 0
    while pos < n:
        tag = "@" + int_str(pos) + "|"
        blocks.append((tag + _FILL)[:64])
        pos += 64
    return "".join(blocks)[:n]


def common_prefix(a, b):
    """Length of the shared prefix, by binary search on slice compares
    (a handful of big allocs, no per-char loop)."""
    lo = 0
    hi = min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def probe_size(sz):
    """One ladder rung: set, stored-length, readback, compare.

    Returns:
        tuple: (stored, rblen, match) -- stored/rblen -1 on error.
    """
    p = make_payload(sz)
    log("cap " + int_str(sz) + ": set...")  # pre-log: names a crash point
    try:
        hvars_set(HVAR, p)
    except Exception as e:
        log("cap " + int_str(sz) + ": set EXC " + str(e))
        return -1, -1, False
    try:
        stored = hvars_dim(HVAR)
    except Exception as e:
        log("cap " + int_str(sz) + ": DIM EXC " + str(e))
        stored = -1
    try:
        rb = hvars_get(HVAR)
        rblen = len(rb) if isinstance(rb, str) else -1
    except Exception as e:
        log("cap " + int_str(sz) + ": get EXC " + str(e))
        rb = None
        rblen = -1
    match = rb == p
    line = ("cap " + int_str(sz) + ": stored=" + int_str(stored)
            + " rb=" + int_str(rblen) + " match=" + str(match))
    if not match and isinstance(rb, str):
        line += " cut@" + int_str(common_prefix(p, rb))
    log(line)
    return stored, rblen, match


def bisect_cap(lo, hi, check):
    """Largest n in [lo, hi] with check(n) true; check(lo) known true,
    check(hi) known false."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if check(mid):
            lo = mid
        else:
            hi = mid
    return lo


def time_n(fn, n=N):
    ts = []
    for _i in range(n):
        gc.collect()
        t0 = ticks()
        fn()
        ts.append(ticks() - t0)
    return ts


def fmt(name, ts):
    lo = ts[0]
    tot = 0
    for t in ts:
        tot += t
        if t < lo:
            lo = t
    parts = []
    for t in ts:
        parts.append(int_str(t))
    return (name + ": min=" + int_str(lo) + "ms avg="
            + int_str(tot // len(ts)) + "ms  raw " + " ".join(parts))


def _fwrite(payload):
    with open(TMP, "w") as f:
        f.write(payload)


def _fread():
    with open(TMP, "r") as f:
        return f.read()


def chunked_set(name, value, piece):
    ppleval('HVars("' + name + '"):=""')
    i = 0
    n = len(value)
    while i < n:
        ppleval('HVars("' + name + '"):=HVars("' + name + '")+"'
                + value[i:i + piece] + '"')
        i += piece


def chunked_get(name, piece):
    n = hvars_dim(name)
    parts = []
    i = 1  # PPL MID is 1-based
    while i <= n:
        parts.append(ppleval('MID(HVars("' + name + '"),' + int_str(i)
                             + ',' + int_str(piece) + ')'))
        i += piece
    return "".join(parts)


# -- Inlined snapshot codec (world.py _snap_escape/_snap_encode; keep in
# sync) with cached int rendering standing in for util.sstr/num_str.
_SNAP_ESC = {"\\": "\\\\", "~": "\\t", '"': "\\q", "\n": "\\n",
             "\r": "\\r"}
_NCACHE = {}


def sstr(v):
    if type(v) is str:
        return v
    s = _NCACHE.get(v)
    if s is None:
        s = int_str(v)
        _NCACHE[v] = s
    return s


def _snap_escape(s):
    if ("\\" not in s and "~" not in s and '"' not in s
            and "\n" not in s and "\r" not in s):
        return s
    parts = []
    for ch in s:
        esc = _SNAP_ESC.get(ch)
        parts.append(esc if esc is not None else ch)
    return "".join(parts)


def _snap_encode_into(value, parts):
    t = type(value)
    if value is None:
        parts.append("n")
    elif t is bool:
        parts.append("T" if value else "F")
    elif t is int:
        parts.append("i")
        parts.append(sstr(value))
    elif t is str:
        esc = _snap_escape(value)
        parts.append("s")
        parts.append(sstr(len(esc)))
        parts.append(":")
        parts.append(esc)
    elif t is list or t is tuple:
        parts.append("l" if t is list else "t")
        parts.append(sstr(len(value)))
        parts.append(":")
        for item in value:
            _snap_encode_into(item, parts)
    elif t is dict:
        pairs = []
        for k, v in value.items():
            pairs.append((_snap_encode(k), v))
        pairs.sort(key=lambda kv: kv[0])
        parts.append("d")
        parts.append(sstr(len(pairs)))
        parts.append(":")
        for kenc, v in pairs:
            parts.append(kenc)
            _snap_encode_into(v, parts)
    else:
        raise ValueError("_snap_encode: unsupported type " + str(t))


def _snap_encode(value):
    parts = []
    _snap_encode_into(value, parts)
    return "".join(parts)


def synth_tpl(vnum):
    """Representative item template -- same field mix/shape as area
    OBJECTS entries."""
    return {
        "name": "test item " + int_str(vnum),
        "short_descr": "a test item " + int_str(vnum),
        "desc": "A test item numbered " + int_str(vnum) + " lies here.",
        "keywords": "test item probe",
        "type": "armor",
        "slot": "body",
        "weight": 10,
        "cost": 100 + vnum,
        "level": 10 + vnum % 40,
        "condition": 90,
        "value": [1, 2, 3, 4, 0],
        "extra_flags": ["glow", "magic"],
        "affects": [("ac", -5), ("hitroll", 2)],
        "extra_descs": [("test probe", "Nothing special about it.")],
    }


def codec_block(tpls):
    lines = []
    for vnum, tpl in tpls:
        lines.append("it." + sstr(vnum) + "=rev0cafe2f4e|"
                     + _snap_encode((tpl, {})))
    return "~".join(lines)


def main():
    log("hvar_cap: HVar length cap + save I/O timings, N=" + int_str(N))

    # -- cap ladder ----------------------------------------------------
    write_lo = 0     # largest fully-stored size seen
    write_hi = None  # smallest size whose store came up short
    read_hi = None   # smallest size stored fine but read back short
    for sz in SIZES:
        stored, rblen, match = probe_size(sz)
        if stored == sz and match:
            write_lo = sz
        elif stored >= 0 and stored < sz and write_hi is None:
            write_hi = sz
        elif stored == sz and rblen < sz and read_hi is None:
            read_hi = sz
        if write_hi is not None or read_hi is not None:
            break

    if write_hi is not None:
        def _fits(n):
            p = make_payload(n)
            try:
                hvars_set(HVAR, p)
                return hvars_dim(HVAR) == n
            except Exception:
                return False
        cap = bisect_cap(write_lo, write_hi, _fits)
        log("WRITE CAP: " + int_str(cap) + " bytes stored ok, "
            + int_str(cap + 1) + " truncates")
    elif read_hi is not None:
        def _reads(n):
            p = make_payload(n)
            try:
                hvars_set(HVAR, p)
                return hvars_get(HVAR) == p
            except Exception:
                return False
        cap = bisect_cap(write_lo, read_hi, _reads)
        log("READ CAP: " + int_str(cap) + " bytes read back ok, "
            + int_str(cap + 1) + " truncates (store itself fine)")
    else:
        cap = write_lo
        log("NO CAP up to " + int_str(write_lo) + " bytes")

    # -- timing ladder (sizes under the cap) ---------------------------
    for sz in SIZES:
        if sz > write_lo:
            break
        p = make_payload(sz)
        tag = "t " + int_str(sz) + " "
        try:
            log(fmt(tag + "hvset ", time_n(lambda: hvars_set(HVAR, p))))
            log(fmt(tag + "hvget+cmp",
                    time_n(lambda: hvars_get(HVAR) == p)))
        except Exception as e:
            log(tag + "hv: FAILED " + str(e))
        try:
            log(fmt(tag + "fwrite", time_n(lambda: _fwrite(p))))
            log(fmt(tag + "fread ", time_n(lambda: _fread())))
        except Exception as e:
            log(tag + "file: FAILED " + str(e))

    # -- chunked mitigation bench --------------------------------------
    tgt = cap * 2 if cap and cap * 2 <= 65536 else 32768
    big = make_payload(tgt)
    log("chunk target " + int_str(tgt) + "B")
    for piece in (1024, 2048, 4096):
        ptag = "chunk " + int_str(piece) + " "
        try:
            ts = time_n(lambda: chunked_set(HVAR, big, piece))
            stored = hvars_dim(HVAR)
            log(fmt(ptag + "set", ts) + "  stored=" + int_str(stored))
            t0 = ticks()
            rb = chunked_get(HVAR, piece)
            t1 = ticks() - t0
            log(ptag + "get: " + int_str(t1) + "ms roundtrip="
                + str(rb == big))
            # Plain single-eval read over the chunk-written value:
            # isolates a read-side cap from the write path.
            t0 = ticks()
            rb2 = hvars_get(HVAR)
            t1 = ticks() - t0
            rb2len = len(rb2) if isinstance(rb2, str) else -1
            log(ptag + "plainget: " + int_str(t1) + "ms len="
                + int_str(rb2len) + " match=" + str(rb2 == big))
        except Exception as e:
            log(ptag + "FAILED " + str(e))

    # -- snapshot codec build cost -------------------------------------
    tpls = []
    for i in range(30):
        tpls.append((3000 + i, synth_tpl(3000 + i)))
    blk = codec_block(tpls)  # first pass fills the int cache
    log("codec block: 30 records, " + int_str(len(blk)) + "B")
    log(fmt("codec build", time_n(lambda: codec_block(tpls))))

    try:
        hvars_set(HVAR, "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
