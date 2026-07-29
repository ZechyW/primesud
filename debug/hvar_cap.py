"""HVar backslash-doubling transport fix: on-device validation. [PRIMESUD]

Run 2 (hvar_cap-2.log, 29/07) found the save-failure root cause: PPL
string literals INTERPRET backslash escapes -- \\t -> tab, \\n -> LF,
\\r -> CR, \\\\ -> \\, and an unknown sequence like \\q makes the whole
eval fail SILENTLY (HVar keeps its previous value).  The snapshot
codec's escape choice assumed PPL ignores backslashes -- false.  A
payload carrying codec escapes is either transformed (readback
mismatch) or rejected outright (stale HVar, also a mismatch).  The
run-1 alnum payload contained no backslash, which is why it was clean.

Proposed game fix (prime_platform.hvars_set, one line): double every
backslash in the embedded literal; the PPL parser un-doubles, so the
stored value equals the original.  The read path returns stored bytes
verbatim (run 2: transformed chars read back raw), so hvars_get needs
no change.  Relies only on \\\\ -> \\, confirmed on-device.

This probe validates that before it reaches the game:
  ctrl -- one UNdoubled \\t roundtrip, expected MISMATCH: confirms
          escape interpretation is active this session.
  dblmx -- every nasty string from the run-2 matrix through the
          doubled transport; all must round-trip byte-identical.
  dblrep -- codec-built 40-record replica payload (escapes, colour
          codes, punctuation) through doubled transport, x5 with
          collects.
  dbl80K -- ~80KB backslash-free payload through doubled transport:
          regression + confirms the replace() pass costs nothing when
          there is nothing to double.

Run standalone on the physical HP Prime -- needs NO game modules.
Only self-running probe .py in the appdir (Prime auto-imports all).
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


def hvars_set_raw(name, value):
    """Current game wrapper (prime_platform.py) -- known bad for
    backslash payloads; kept for the control case."""
    ppleval('HVars("' + name + '"):="' + value + '"')


def hvars_set_dbl(name, value):
    """Proposed fix: backslashes doubled so the PPL literal parser
    un-doubles them back to the original bytes."""
    ppleval('HVars("' + name + '"):="'
            + value.replace("\\", "\\\\") + '"')


def hvars_get(name):
    return ppleval('HVars("' + name + '")')


_DIG = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def int_str(n):
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


def roundtrip(tag, s, setter):
    try:
        setter(HVAR, s)
    except Exception as e:
        log(tag + ": set EXC " + str(e))
        return False
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
    log(tag + ": MISMATCH sent=" + int_str(len(s)) + " rb="
        + int_str(len(rb)) + " div@" + int_str(cut))
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
    ("bs-tail ", "trailing\\"),
    ("raw-tab ", "a\tb"),
    ("raw-nl  ", "a\nb"),
    ("colour  ", "{Ggreen{x {rred{x {Bblue{x"),
    ("punct   ", "|=:.,;!?@#&*+-/()[]<>^_`{}'%$"),
    ("mixed   ", "s9:conditioni90d0:~it.3001=2f4e|t2:d15:"),
)


def main():
    log("hvar_cap v3: backslash-doubling transport validation")

    # -- control: interpretation still active? -------------------------
    ok = roundtrip("ctrl raw bs-t (EXPECT MISMATCH)", "a\\tb",
                   hvars_set_raw)
    log("ctrl: escape interpretation " + ("NOT active?!" if ok
                                          else "active, as run 2"))

    # -- doubled matrix ------------------------------------------------
    bad = []
    for tag, s in MATRIX:
        if not roundtrip("dblmx " + tag, s, hvars_set_dbl):
            bad.append(tag.strip())
    log("dblmx: " + (int_str(len(bad)) + " bad: " + " ".join(bad)
                     if bad else "all clean"))

    # -- doubled replica x5 --------------------------------------------
    rep = build_replica(40)
    log("dblrep: " + int_str(len(rep)) + "B, 40 records")
    fails = 0
    for i in range(5):
        gc.collect()
        if not roundtrip("dblrep " + int_str(i + 1), rep,
                         hvars_set_dbl):
            fails += 1
    log("dblrep: " + int_str(fails) + "/5 failed")

    # -- doubled 80KB backslash-free regression + replace() cost -------
    blk = "abcdefghijklmnopqrstuvwxyz0123456789" * 8
    big = blk * 285
    gc.collect()
    t0 = int(ppleval("Ticks"))
    roundtrip("dbl80K", big, hvars_set_dbl)
    log("dbl80K set+get: " + int_str(int(ppleval("Ticks")) - t0) + "ms")

    try:
        hvars_set_raw(HVAR, "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
