"""Explore tracking: per-room "have I been here" bitmask (cf. 1stMud explored.c).

[PRIMESUD] 1stMud sets the explored bit in char_to_room (handler.c:1360), a
single choke point hit on every room entry. PrimeSUD has no such choke point:
room assignment is scattered (movement.py, magic.py, combat.py, training.py,
debug.py, game_state.py). Instead mark_explored() is called once per command
dispatch (commands.interpret) and once per update tick (update.update_handler),
comparing the player's current room against a cached last-marked vnum and
setting the bit when it differs. The command seam catches player-driven moves;
the tick seam catches every room a player passes through WITHOUT a fresh
command dispatch -- speedwalk/run steps (run_buf_step runs per pulse in the
game loop, then update_handler right after) and mob-initiated drags (summon).
Do NOT add a per-step mark to do_run: the tick seam already covers it.

Storage: a bytearray on the player dict (bit index = room vnum), sized from the
static _AREA_FILES vnum ranges (max < 18000 -> ~2.2 KB). Persisted as an RLE
run-length string (str()+concat only, per PRIME_FIRMWARE_BUGS).
"""
from world import _AREA_FILES, AREA_ROOM_COUNTS
from handler import chprintln
from colors import color_len
from util import num_str, pad_left

# Static vnum ranges + names per area tag (cf. 1stMud area->min_vnum/max_vnum),
# from the generation-time _AREA_FILES table -- no area load required.
_AREA_RANGES = [(tag, lo, hi) for _f, tag, _n, lo, hi in _AREA_FILES]
_AREA_NAMES = {}
for _f, _t, _n, _lo, _hi in _AREA_FILES:
    _AREA_NAMES[_t] = _n

_MAX_VNUM = 0
for _t, _lo, _hi in _AREA_RANGES:
    if _hi > _MAX_VNUM:
        _MAX_VNUM = _hi
_MASK_BYTES = (_MAX_VNUM >> 3) + 1

# World total of explorable rooms (cf. 1stMud top_explored). No PrimeSUD room
# carries ROOM_NOEXPLORE (verified 08/07/2026), so "explorable" == "exists".
TOP_EXPLORED = sum(AREA_ROOM_COUNTS.values())


def _area_range(tag):
    """Return (min_vnum, max_vnum) for an area tag, or None. [PRIMESUD]"""
    for t, lo, hi in _AREA_RANGES:
        if t == tag:
            return (lo, hi)
    return None


def _tag_for_vnum(vnum):
    """Area tag owning a vnum, from static ranges (zero-load). [PRIMESUD]

    Deliberately avoids world.ROOM_DEFS.get(), whose LazyDict lookup would
    trigger an area load -- do_explored must never lazy-load an area.
    """
    if vnum is None:
        return None
    for t, lo, hi in _AREA_RANGES:
        if lo <= vnum <= hi:
            return t
    return None


def get_mask(player):
    """Return the player's explored bytearray, creating it if absent. [PRIMESUD]"""
    m = player.get("_explored")
    if m is None:
        m = bytearray(_MASK_BYTES)
        player["_explored"] = m
    return m


def mark_explored(player):
    """Set the explored bit for the player's current room if it changed.

    (cf. 1stMud StrSetBit(ch->pcdata->explored, vnum) in char_to_room,
    handler.c:1360). [PRIMESUD] cached-vnum seam -- see module docstring.
    """
    # NPCs have no explored map (1stMud tracks it in pcdata only); skip before
    # get_mask allocates a ~2KB mask on a mob acting via the interpreter
    # (mobprog command actor). [PRIMESUD]
    if player.get("is_npc"):
        return
    room = player.get("room")
    if room is None or room > _MAX_VNUM or room < 0:
        return
    if player.get("_last_marked_room") == room:
        return
    player["_last_marked_room"] = room
    m = get_mask(player)
    _bit = 1 << (room & 7)
    if not (m[room >> 3] & _bit):
        # [PRIMESUD] only a genuinely new room dirties the RLE cache, so
        # revisits (the steady state) keep encode_rle free.
        m[room >> 3] |= _bit
        player.pop("_rle_cache", None)


def roomcount(player):
    """Total explored rooms (cf. 1stMud roomcount in explored.c)."""
    count = 0
    for b in get_mask(player):
        while b:            # Kernighan popcount
            b &= b - 1
            count += 1
    return count


def areacount(player, tag):
    """Explored rooms within an area's vnum range (cf. 1stMud areacount)."""
    r = _area_range(tag)
    if r is None:
        return 0
    lo, hi = r
    m = get_mask(player)
    count = 0
    for v in range(lo, hi + 1):
        if (m[v >> 3] >> (v & 7)) & 1:
            count += 1
    return count


def arearooms(tag):
    """Explorable rooms in an area (cf. 1stMud arearooms). Static, zero-load."""
    return AREA_ROOM_COUNTS.get(tag, 0)


def encode_rle(player):
    """Serialise the mask as alternating 0/1 run counts (cf. 1stMud write_rle).

    Format: "<startbit> <run> <run> ... -1", e.g. "0 12 3 40 -1". str()+concat
    only -- this string is persisted (PRIME_FIRMWARE_BUGS).

    [PRIMESUD] Result cached on the player (_rle_cache) until a mask bit
    actually changes (mark_explored / decode_rle / explored reset): the
    full-mask encode cost ln.rle=113ms of a 937ms save (smoke-5), and at
    high exploration extent every save re-encoded an unchanged mask.
    """
    _cached = player.get("_rle_cache")
    if _cached is not None:
        return _cached
    m = get_mask(player)
    bit = 0
    count = 0
    parts = ["0"]
    for v in range(_MAX_VNUM + 1):
        b = (m[v >> 3] >> (v & 7)) & 1
        if b == bit:
            count += 1
        else:
            parts.append(num_str(count))
            count = 1
            bit = b
    parts.append(num_str(count))
    parts.append("-1")
    _out = " ".join(parts)
    player["_rle_cache"] = _out
    return _out


def decode_rle(player, s):
    """Rebuild the mask from an RLE string (cf. 1stMud read_rle)."""
    player.pop("_rle_cache", None)  # [PRIMESUD] mask rebuilt below
    m = get_mask(player)
    for i in range(len(m)):
        m[i] = 0
    toks = s.split()
    if not toks:
        return
    bit = int(toks[0])
    idx = 0
    pos = 0
    for t in toks[1:]:
        count = int(t)
        if count < 0:
            break
        # [PRIMESUD] 1stMud read_rle `continue`s on count==0 without flipping
        # the bit, which desyncs alternation if vnum 0 is ever set; we let a
        # 0-length run flip normally so encode/decode round-trips any mask.
        end = pos + count
        while idx < end and idx <= _MAX_VNUM:
            if bit == 1:
                m[idx >> 3] |= 1 << (idx & 7)
            idx += 1
        pos = end
        bit = 0 if bit == 1 else 1


def _pct2(part, whole):
    """Two-decimal percent string (part/whole*100) via integer math. [PRIMESUD]

    Matches 1stMud's Percent()/%.2f (explored.c, act_info.c) without floats.
    """
    if whole <= 0:
        return "0.00"
    hp = (part * 10000 + whole // 2) // whole   # rounded hundredths of a percent
    whole_pct, frac = divmod(hp, 100)
    f = num_str(frac)
    if len(f) < 2:
        f = "0" + f
    return num_str(whole_pct) + "." + f


def _pct0(part, whole):
    """Rounded integer percent (cf. 1stMud %3.0f). [PRIMESUD]"""
    if whole <= 0:
        return 0
    return (part * 100 + whole // 2) // whole


def do_explored(player, args):
    """Show explore progress (cf. 1stMud do_explored in explored.c).

    No arg -> world + current-area stats; "reset" -> zero the mask;
    "list"/prefix -> per-area percentages sorted high-to-low.
    """
    arg = args[0].lower() if args else ""

    if not arg:
        rcnt = roomcount(player)
        # [PRIMESUD] "ROM" rendered as the realm name, per quest.py {n precedent.
        chprintln(player, "The realm has {G" + num_str(TOP_EXPLORED)
                  + "{x explorable rooms.")
        chprintln(player, "You have explored {G" + num_str(rcnt) + " ("
                  + _pct2(rcnt, TOP_EXPLORED) + "%){x of the mud{x")
        tag = _tag_for_vnum(player.get("room"))
        acnt = areacount(player, tag)
        arooms = arearooms(tag)
        chprintln(player, "This area has {G" + num_str(arooms)
                  + "{x explorable rooms.")
        chprintln(player, "You have explored {G" + num_str(acnt) + " ("
                  + _pct2(acnt, arooms) + "%){x rooms in this area.{x")
    elif arg == "reset":
        m = get_mask(player)
        for i in range(len(m)):
            m[i] = 0
        player["_last_marked_room"] = None
        player.pop("_rle_cache", None)  # [PRIMESUD] mask changed
        chprintln(player, "Your explored rooms were set to 0.")
    elif "list".startswith(arg):
        rows = []
        for tag, _lo, _hi in _AREA_RANGES:
            pct = _pct0(areacount(player, tag), arearooms(tag))
            rows.append((pct, _AREA_NAMES.get(tag, tag)))
        # percent desc, then name asc for stable ties (1stMud qsort is unstable)
        rows.sort(key=lambda r: (-r[0], r[1]))
        cells = []
        for pct, name in rows:
            # str.rjust missing on-device; pad_left replaces the old %3d
            cells.append("{D[{Y" + pad_left(num_str(pct), 3) + "{y%{D]{x " + name)
        # two per line (cf. 1stMud print_cols 2-column layout)
        for i in range(0, len(cells), 2):
            left = cells[i]
            if i + 1 < len(cells):
                pad = " " * max(1, 32 - color_len(left))
                chprintln(player, left + pad + cells[i + 1])
            else:
                chprintln(player, left)
    else:
        # cf. 1stMud cmd_syntax(ch, NULL, n_fun, ...). [PRIMESUD] fixed
        # "Syntax:" title (no randomised Usage/Type), plain text per the
        # combat.py do_stance precedent; command name on each line as 1stMud.
        chprintln(player, "Syntax: explored " + "        - show current area and world.")
        chprintln(player, "        explored " + "list    - list percentages for all areas.")
        chprintln(player, "        explored " + "reset   - reset explored rooms.")
