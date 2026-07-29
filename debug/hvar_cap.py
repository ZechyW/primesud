"""HVar content-transform hunt: which payload bytes PPL mangles. [PRIMESUD]

hvar_cap run 1 (hvar_cap-1.log, 29/07) falsified the length-cap
hypothesis: 80KB stores and reads back byte-identical, hvset ~1ms/KB.
Re-read of the device failure: "it." lines are appended LAST by
_serialize_world and "condition" sorts last among template keys, so a
payload ending "...conditioni90d0:" is a COMPLETE payload, not a cut.
The readback mismatch is therefore a content difference somewhere
earlier -- either PPL transforming a char class the old save format
never contained (snapshot escape sequences \\q \\t \\\\, colour codes,
punctuation) or the G1 heap-corruption family biting the giant
literal/readback (stochastic).  Run 1's payload was plain alnum --
exactly why it stayed clean.

Run standalone on the physical HP Prime -- needs NO game modules.
Only self-running probe .py in the appdir (Prime auto-imports all).

Sections (log flushed per line):
  matrix  -- per-char-class roundtrip: each candidate string set/get
             through HVars alone; mismatch logs lengths, divergence
             offset, and char codes both sides.  Includes a raw '"'
             case marked EXPECTED-BAD (PPL literal cannot hold it;
             codec escapes it) to record the failure mode.
  replica -- realistic save payload built with the inlined snapshot
             codec over templates whose strings contain tildes,
             quotes, newlines, backslashes, colour codes (so the
             payload carries real escape sequences), joined with "~"
             like _serialize_world.  10 roundtrips with a gc.collect
             between -- a deterministic transform fails every pass at
             the same offset; G1-family corruption fails some passes
             at moving offsets.
  sanity  -- one 80KB plain roundtrip (run-1 regression check).

Results printed and written to hvar_cap.log.  Uses HVar "hvcap";
reset to "0" at the end.
"""
import gc
from hpprime import eval as ppleval

LOG = "hvar_cap.log"
HVAR = "hvcap"

_out = []


def log(msg):
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


# Inlined from prime_platform.py (keep in sync).
def hvars_set(name, value):
    ppleval('HVars("' + name + '"):="' + value + '"')


def hvars_get(name):
    return ppleval('HVars("' + name + '")')


def hvars_dim(name):
    return int(ppleval('DIM(HVars("' + name + '"))'))


_DIG = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def int_str(n):
    """Digit-table concat, never the firmware int formatter (G1
    str(int)-GC bug avoidance)."""
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


def common_prefix(a, b):
    lo = 0
    hi = min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def dump_at(tag, want, got, pos):
    """Char codes around the divergence, both sides."""
    for s, nm in ((want, "want"), (got, "got ")):
        cs = []
        i = pos - 8
        if i < 0:
            i = 0
        end = pos + 8
        if end > len(s):
            end = len(s)
        while i < end:
            cs.append(int_str(ord(s[i])))
            i += 1
        log(tag + " " + nm + " codes @" + int_str(pos) + ": "
            + " ".join(cs))


def roundtrip(tag, s):
    """One set/get/compare; full diagnostics on mismatch.

    Returns:
        bool: True when the readback matched byte for byte.
    """
    try:
        hvars_set(HVAR, s)
    except Exception as e:
        log(tag + ": set EXC " + str(e))
        return False
    try:
        stored = hvars_dim(HVAR)
    except Exception:
        stored = -1
    try:
        rb = hvars_get(HVAR)
    except Exception as e:
        log(tag + ": get EXC " + str(e))
        return False
    if rb == s:
        log(tag + ": ok (" + int_str(len(s)) + "B)")
        return True
    if not isinstance(rb, str):
        log(tag + ": MISMATCH non-str readback " + str(type(rb)))
        return False
    cut = common_prefix(s, rb)
    log(tag + ": MISMATCH sent=" + int_str(len(s)) + " stored="
        + int_str(stored) + " rb=" + int_str(len(rb)) + " div@"
        + int_str(cut))
    dump_at(tag, s, rb, cut)
    return False


# -- Inlined snapshot codec (world.py; keep in sync), cached ints.
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
    """Template whose strings exercise every escape class the codec
    emits, plus colour codes and punctuation the run-1 payload lacked."""
    return {
        "name": "test item " + int_str(vnum),
        "short_descr": "{Ga \"gleaming\" item " + int_str(vnum) + "{x",
        "desc": "Line one.\nLine two with a ~tilde~ and a \\backslash.",
        "keywords": "test item probe's",
        "type": "armor",
        "slot": "body",
        "weight": 10,
        "cost": 100 + vnum,
        "level": 10 + vnum % 40,
        "condition": 90,
        "value": [1, 2, 3, 4, 0],
        "extra_flags": ["glow", "magic"],
        "affects": [("ac", -5), ("hitroll", 2)],
        "extra_descs": [("probe", "It says: \"don't touch\" -- 100% odd!")],
    }


def build_replica(nrec):
    """Save-shaped payload: a few plain lines, then nrec it. records,
    "~"-joined -- same section order as _serialize_world."""
    lines = ["v=10", "p.name=Probe", "p.title= the {RTester{x",
             "g.time=14|12|6|1462"]
    for i in range(nrec):
        vnum = 3000 + i
        rec = _snap_encode((synth_tpl(vnum), {}))
        lines.append("it." + sstr(vnum) + "=2f4e7d7226b9|" + rec)
    return "~".join(lines)


MATRIX = (
    ("plain   ", "plain text 1234567890"),
    ("tilde   ", "before~mid~after"),
    ("esc-bsq ", "a\\qb"),
    ("esc-bst ", "a\\tb"),
    ("esc-bsbs", "a\\\\b"),
    ("esc-bsn ", "a\\nb"),
    ("esc-bsr ", "a\\rb"),
    ("bs-solo ", "a\\b"),
    ("colour  ", "{Ggreen{x {rred{x {Bblue{x"),
    ("punct1  ", "|=:.,;!?@#&*+-/"),
    ("punct2  ", "()[]<>^_`"),
    ("braces  ", "{}{}{}"),
    ("squote  ", "it's a probe's test"),
    ("pct     ", "100% and 50%"),
    ("dollar  ", "$5 and $10"),
    ("mixed   ", "s9:conditioni90d0:~it.3001=2f4e|t2:d15:"),
)


def main():
    log("hvar_cap v2: content-transform hunt")

    # -- matrix --------------------------------------------------------
    bad = []
    for tag, s in MATRIX:
        if not roundtrip("mx " + tag, s):
            bad.append(tag.strip())
    # Raw double quote: codec escapes these away; recorded here only to
    # capture PPL's failure mode for the docs.
    log("mx rawquote (EXPECTED-BAD): probing...")
    roundtrip("mx rawquote", 'a"b')
    log("matrix: " + (int_str(len(bad)) + " bad: " + " ".join(bad)
                      if bad else "all clean"))

    # -- replica x10 ---------------------------------------------------
    rep = build_replica(40)
    log("replica: " + int_str(len(rep)) + "B, 40 records")
    fails = 0
    for i in range(10):
        gc.collect()
        if not roundtrip("rep " + int_str(i + 1), rep):
            fails += 1
    log("replica: " + int_str(fails) + "/10 failed"
        + ("" if fails in (0, 10) else " (STOCHASTIC -- G1 family?)"))

    # -- sanity: run-1 plain 80KB regression ---------------------------
    blk = "abcdefghijklmnopqrstuvwxyz0123456789" * 8  # 288B
    big = blk * 285  # ~82KB
    roundtrip("sanity 80K", big)

    try:
        hvars_set(HVAR, "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
