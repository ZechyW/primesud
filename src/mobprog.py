"""MOBprogram interpreter core (cf. 1stMud programs.c). [PRIMESUD port]

Scripted mob behaviour: a mob template carries ``mob_triggers`` tuples
``(trig_type, mprog_vnum, phrase)``; each mprog vnum maps (via
``world.MOBPROGS``) to a small line-interpreted program.  This module is
Phase A of MOBPROG_PLAN.md: the interpreter engine only -- no trigger wiring
(Phase B) and no ``mob <subcmd>`` command set (Phase C).

Public surface:
    has_trigger(mob, ttype) -- cheap empty-tuple early-out; True if the mob's
        template has a trigger of that type.
    program_flow(prog_vnum, code, mob, ch, arg1, arg2) -- run one program.
    cmd_eval(check, line, mob, ch, arg1, arg2, rch, prog_vnum) -- if-check.
    expand_arg(fmt, mob, ch, arg1, arg2, rch) -- $-code expansion.
    num_eval(lval, oper, rval) -- comparison primitive.

program_flow is iterative (a state/cond stack sized MAX_NESTED_LEVEL) -- the
only recursion source in 1stMud is ``mpcall``, deferred to Phase C, and it is
guarded by MAX_CALL_LEVEL.  A malformed program (misplaced if/or/and/else/
endif, unknown if-check keyword, over-nesting) aborts the whole program via
dbg(), matching 1stMud's ``buggy_prog``.

-- Phase A spike: the mob-as-command-actor path --

Decision 6 of the plan routes any prog line that is not a control keyword or a
``mob <subcmd>`` through the *real* command interpreter as the mob
(1stMud ``interpret(mob, data)``).  The spike drove a fabricated prog making a
mob ``say``, ``emote``, and walk ``north`` through ``commands.interpret`` and
observed the result (see tests/test_mobprog.py::test_spike_*).  Findings on
which command categories are prog-safe:

  PROG-SAFE (verified in the spike):
    * say / '  -- do_say uses act() TO_ROOM/TO_CHAR.  The mob is the actor;
      the player sees "<Mob> says '...'".  TO_CHAR routes only to the player,
      so a mob actor's self-line is correctly suppressed. OK.
    * emote / , -- same act() model. OK.
    * movement (north..down) -- move_char is already actor-generic: an NPC
      gets leave/arrive acts and per-room mob-list bookkeeping, followers
      recurse.  The mob moved rooms and both room mob-lists updated. OK.
    * Most look/act commands that emit only through act()/chprintln route to
      the player only when the player qualifies (same room, SENDOK), so a mob
      actor produces no stray output to the player.

  ASSUMES A PLAYER -- guard or avoid (failure modes actually hit / reasoned):
    * ARGUMENT CASE: PrimeSUD one_argument() lowercases the *entire* argument
      (not just the command word, unlike 1stMud), so a bare verb dispatched
      through interpret() lowercases its text AND colour codes ("{G" -> "{g").
      => Coloured / cased mob output must use the Phase-C ``mob echo`` family
         (mp-table, case-preserving), never a bare say/emote through interpret.
    * mark_explored(): interpret() marks the actor's room explored, allocating
      a ~2KB per-mob mask.  Guarded now -- mark_explored early-returns on
      is_npc (explored maps are a PC-only concept).
    * leading blank line: interpret() prints a blank separator echoing player
      input.  Guarded now -- suppressed when the actor is_npc.
    * commands that call the picker UI, tprint() directly, or read player-only
      pcdata (train/practice/score/quest/save/quit/macro/debug, shop pickers)
      assume the local player and would emit to the screen or touch missing
      fields.  Progs must not invoke these; the ``mob`` command set (Phase C)
      exposes only NPC-safe verbs, mirroring 1stMud's separate mp-command
      table.  This is the same stance as comm._order_interpret, which
      hand-dispatches an NPC-safe subset rather than calling interpret().

Only MOB programs are supported (obj/room progs are out of scope -- the
converter emits neither).  Trigger word ``surr`` is rejected upstream (the
converter accepts it but the mechanic is unported); every other trigger word
is engine-supported.
"""

from urandom import randint

from debug import dbg
from game_time import time_info
from handler import can_see, is_name, _HE_SHE, _HIM_HER, _HIS_HER

# -- Interpreter limits (cf. programs.c:1942/1950) -----------------------------
MAX_NESTED_LEVEL = 12
MAX_CALL_LEVEL = 5

# Block states (cf. programs.c:1943-1946); values matter only for equality.
BEGIN_BLOCK = 0
IN_BLOCK = -1
END_BLOCK = -2

# Comparison operators (cf. fn_evals, programs.c:166).
_EVAL_OPS = ("==", ">=", "<=", ">", "<", "!=")

# Every if-check keyword 1stMud knows (fn_keyword, programs.c:106).  Membership
# gates program_flow: a keyword outside this set is a buggy-prog abort, exactly
# as in the source; a keyword inside it but outside the Phase A subset returns
# false with a dbg() note (see cmd_eval).
KNOWN_CHECKS = frozenset((
    "rand", "mobhere", "objhere", "mobexists", "objexists", "people",
    "players", "mobs", "clones", "order", "hour", "ispc", "isnpc", "isgood",
    "isevil", "isneutral", "isimmort", "ischarm", "isfollow", "isactive",
    "isdelay", "isvisible", "hastarget", "istarget", "affected", "act", "off",
    "imm", "carries", "wears", "has", "uses", "name", "pos", "clan", "race",
    "class", "objtype", "vnum", "hpcnt", "room", "sex", "level", "align",
    "money", "objval0", "objval1", "objval2", "objval3", "objval4", "grpsize",
    "onquest", "hunter", "plr", "skill", "weight",
))

# 1stMud sex is an int (SEX_NEUTRAL 0 / MALE 1 / FEMALE 2); PrimeSUD stores a
# word.  Mapped for the ``sex`` numeric if-check.
_SEX_NUM = {"neutral": 0, "either": 0, "male": 1, "female": 2}


# -- small helpers -------------------------------------------------------------

def _atoi(s):
    """C atoi: leading (optionally signed) integer, 0 on non-numeric. [PRIMESUD]"""
    s = s.strip()
    neg = False
    if s[:1] in ("+", "-"):
        neg = s[0] == "-"
        s = s[1:]
    d = ""
    for c in s:
        if c.isdigit():
            d += c
        else:
            break
    if not d:
        return 0
    return -int(d) if neg else int(d)


def _number_percent():
    """1..100 inclusive (cf. 1stMud number_percent). [PRIMESUD]"""
    return randint(1, 100)


def _first(s):
    """First whitespace-delimited word of s (empty string if none). [PRIMESUD]"""
    if not s:
        return ""
    parts = s.split()
    return parts[0] if parts else ""


def _cap(s):
    """Capitalize first char only (cf. 1stMud capitalize). [PRIMESUD]"""
    return s[:1].upper() + s[1:] if s else s


def num_eval(lval, oper, rval):
    """Integer comparison by operator string (cf. 1stMud num_eval, programs.c:186)."""
    if oper == "==":
        return lval == rval
    if oper == ">=":
        return lval >= rval
    if oper == "<=":
        return lval <= rval
    if oper == ">":
        return lval > rval
    if oper == "<":
        return lval < rval
    if oper == "!=":
        return lval != rval
    dbg("mobprog: invalid oper '" + str(oper) + "'")
    return False


# -- triggers ------------------------------------------------------------------

def has_trigger(mob, ttype):
    """True if the mob's template has a trigger of *ttype* (cf. 1stMud HAS_TRIGGER).

    Early-outs on the empty/absent case before any other work -- 99% of mobs
    carry no triggers, and this is called per-mob per-pulse once wired.

    Args:
        mob (dict): Mob instance.
        ttype (str): Trigger word (e.g. "speech", "random").

    Returns:
        bool: True if a matching trigger exists.
    """
    import world
    tpl = world.MOB_DEFS.get(mob.get("tpl")) if mob else None
    if tpl is None:
        return False
    trigs = tpl.get("mob_triggers")
    if not trigs:  # empty tuple / absent -- cheap short-circuit
        return False
    for t in trigs:
        if t[0] == ttype:
            return True
    return False


# -- $-code expansion (cf. expand_arg_mob, programs.c:1433) --------------------

def _room_of(mob):
    import world
    return world.rooms._data.get(mob.get("room")) if mob else None


def get_random_char(mob):
    """Random visible character in the mob's room (cf. get_random_char, programs.c:208).

    [PRIMESUD] Returns a random *visible* other character (weighted by a random
    roll, as in the source).  1stMud's mob branch technically also lets its
    ``else if`` fall through to pick invisible NPCs or the mob itself; that is
    a source quirk -- here $r means "a random visible other in the room", which
    is what the code is reaching for.

    Returns:
        dict or None: Chosen character, or None if the room is empty of others.
    """
    import world
    rs = _room_of(mob)
    if rs is None:
        return None
    cands = []
    p = world.chars.get(1)
    room = mob.get("room")
    if p is not None and p is not mob and p.get("room") == room:
        cands.append(p)
    for mid in rs.get("mobs", []):
        c = world.chars.get(mid)
        if c is not None and c is not mob:
            cands.append(c)
    best = None
    highest = 0
    for c in cands:
        if can_see(mob, c):
            n = _number_percent()
            if n > highest:
                highest = n
                best = c
    return best


def _obj_name(obj):
    """First keyword word of an object (instance dict or bare vnum). [PRIMESUD]"""
    if isinstance(obj, dict):
        kw = obj.get("keywords")
        if kw:
            return _first(kw)
        vnum = obj.get("vnum")
    else:
        vnum = obj
    import world
    tpl = world.ITEM_DEFS.get(vnum)
    return _first(tpl.get("keywords", "")) if tpl else "something"


def _obj_short(obj):
    """Short description of an object (instance dict or bare vnum). [PRIMESUD]"""
    if isinstance(obj, dict):
        sd = obj.get("short_descr")
        if sd:
            return sd
        vnum = obj.get("vnum")
    else:
        vnum = obj
    import world
    tpl = world.ITEM_DEFS.get(vnum)
    return tpl.get("short_descr", "something") if tpl else "something"


def _char_short(c):
    """$N/$T-style display: mob short_descr, else name. [PRIMESUD]"""
    if c.get("is_npc"):
        return c.get("short_descr") or c.get("name") or "someone"
    return c.get("name") or "someone"


def expand_arg(fmt, mob, ch, arg1, arg2, rch):
    """Expand $-codes in *fmt* (cf. expand_arg_mob, programs.c:1433).

    Codes ported verbatim from the source: $i/$I mob, $n/$N ch, $t/$T arg2
    char, $r/$R random char, $q/$Q mprog_target, $o/$O arg1 obj, $p/$P arg2
    obj, and the pronoun families j/e/E/J/X (subject), k/m/M/K/Y (object),
    l/s/S/L/Z (possessive).  An unknown code logs and expands to "<@@@>".

    Args:
        fmt (str): Format string.
        mob (dict): The prog's mob.
        ch (dict or None): Triggering character.
        arg1: Object argument (obj dict / vnum / None).
        arg2 (dict or None): Target character.
        rch (dict or None): Preselected random char, or None to pick lazily.

    Returns:
        str: Expanded string.
    """
    if not fmt:
        return ""
    someone = "someone"
    something = "something"
    someones = "someone's"
    vch = arg2 if isinstance(arg2, dict) else None
    obj1 = arg1
    obj2 = arg2 if not isinstance(arg2, dict) else None
    tgt = mob.get("mprog_target") if mob else None

    def sex_of(c, table, dflt):
        return table.get((c or {}).get("sex", "neutral"), dflt)

    out = []
    i = 0
    n = len(fmt)
    while i < n:
        ch0 = fmt[i]
        if ch0 != "$":
            out.append(ch0)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        code = fmt[i]
        i += 1
        if code == "i":
            piece = _first(mob.get("name", ""))
        elif code == "I":
            piece = mob.get("short_descr", "") or ""
        elif code == "n":
            piece = _cap(_first(ch.get("name", ""))) if (ch is not None and can_see(mob, ch)) else someone
        elif code == "N":
            piece = _char_short(ch) if (ch is not None and can_see(mob, ch)) else someone
        elif code == "t":
            piece = _cap(_first(vch.get("name", ""))) if (vch is not None and can_see(mob, vch)) else someone
        elif code == "T":
            piece = _char_short(vch) if (vch is not None and can_see(mob, vch)) else someone
        elif code == "r":
            if rch is None:
                rch = get_random_char(mob)
            piece = _cap(_first(rch.get("name", ""))) if (rch is not None and can_see(mob, rch)) else someone
        elif code == "R":
            if rch is None:
                rch = get_random_char(mob)
            piece = _char_short(rch) if (rch is not None and can_see(mob, rch)) else someone
        elif code == "q":
            piece = _cap(_first(tgt.get("name", ""))) if (tgt is not None and can_see(mob, tgt)) else someone
        elif code == "Q":
            piece = _char_short(tgt) if (tgt is not None and can_see(mob, tgt)) else someone
        # subject pronoun (he/she/it)
        elif code == "j":
            piece = sex_of(mob, _HE_SHE, "it")
        elif code == "e":
            piece = sex_of(ch, _HE_SHE, "it") if (ch is not None and can_see(mob, ch)) else someone
        elif code == "E":
            piece = sex_of(vch, _HE_SHE, "it") if (vch is not None and can_see(mob, vch)) else someone
        elif code == "J":
            if rch is None:
                rch = get_random_char(mob)
            piece = sex_of(rch, _HE_SHE, "it") if (rch is not None and can_see(mob, rch)) else someone
        elif code == "X":
            piece = sex_of(tgt, _HE_SHE, "it") if (tgt is not None and can_see(mob, tgt)) else someone
        # object pronoun (him/her/it)
        elif code == "k":
            piece = sex_of(mob, _HIM_HER, "it")
        elif code == "m":
            piece = sex_of(ch, _HIM_HER, "it") if (ch is not None and can_see(mob, ch)) else someone
        elif code == "M":
            piece = sex_of(vch, _HIM_HER, "it") if (vch is not None and can_see(mob, vch)) else someone
        elif code == "K":
            if rch is None:
                rch = get_random_char(mob)
            piece = sex_of(rch, _HIM_HER, "it") if (rch is not None and can_see(mob, rch)) else someone
        elif code == "Y":
            piece = sex_of(tgt, _HIM_HER, "it") if (tgt is not None and can_see(mob, tgt)) else someone
        # possessive pronoun (his/her/its)
        elif code == "l":
            piece = sex_of(mob, _HIS_HER, "its")
        elif code == "s":
            piece = sex_of(ch, _HIS_HER, "its") if (ch is not None and can_see(mob, ch)) else someones
        elif code == "S":
            piece = sex_of(vch, _HIS_HER, "its") if (vch is not None and can_see(mob, vch)) else someones
        elif code == "L":
            if rch is None:
                rch = get_random_char(mob)
            piece = sex_of(rch, _HIS_HER, "its") if (rch is not None and can_see(mob, rch)) else someones
        elif code == "Z":
            piece = sex_of(tgt, _HIS_HER, "its") if (tgt is not None and can_see(mob, tgt)) else someones
        # objects
        elif code == "o":
            piece = _obj_name(obj1) if (obj1 is not None and _can_see_obj(mob, obj1)) else something
        elif code == "O":
            piece = _obj_short(obj1) if (obj1 is not None and _can_see_obj(mob, obj1)) else something
        elif code == "p":
            piece = _obj_name(obj2) if (obj2 is not None and _can_see_obj(mob, obj2)) else something
        elif code == "P":
            piece = _obj_short(obj2) if (obj2 is not None and _can_see_obj(mob, obj2)) else something
        else:
            dbg("mobprog: bad code '" + code + "'")
            piece = "<@@@>"
        out.append(piece)
    return "".join(out)


def _can_see_obj(mob, obj):
    """Object visibility, tolerant of Phase A fabricated objects. [PRIMESUD]"""
    try:
        from handler import can_see_obj
        return can_see_obj(mob, obj)
    except Exception:
        return True


# -- if-check evaluation (cf. cmd_eval_mob, programs.c:421) --------------------

# Room population iFlag codes (cf. count_people_room, programs.c:248): players,
# mobs, clones (same-vnum NPCs), everyone.
_COUNT_FLAG = {"people": 0, "players": 1, "mobs": 2, "clones": 3}

_CHAR_BOOL = frozenset((
    "ispc", "isnpc", "isgood", "isevil", "isneutral", "ischarm", "isfollow",
    "isactive", "isdelay", "isvisible", "hastarget", "istarget",
))
_CHAR_NUM = frozenset((
    "level", "align", "money", "hpcnt", "vnum", "room", "sex",
))
_CHAR_FLAG = frozenset(("name", "pos", "act", "affected"))


def _count_people_room(mob, iflag):
    """Count characters in the mob's room by class (cf. count_people_room)."""
    import world
    rs = _room_of(mob)
    if rs is None:
        return 0
    room = mob.get("room")
    count = 0
    people = []
    p = world.chars.get(1)
    if p is not None and p.get("room") == room:
        people.append(p)
    for mid in rs.get("mobs", []):
        c = world.chars.get(mid)
        if c is not None:
            people.append(c)
    my_tpl = mob.get("tpl")
    for c in people:
        if c is mob:
            continue
        is_npc = bool(c.get("is_npc"))
        if iflag == 1 and is_npc:
            continue
        if iflag == 2 and not is_npc:
            continue
        if iflag == 3 and not (is_npc and c.get("tpl") == my_tpl):
            continue
        if can_see(mob, c):
            count += 1
    return count


def _resolve_target(code, mob, ch, arg1, arg2):
    """Map a $-code to (char, obj) lvalues (cf. cmd_eval_mob switch, programs.c:505)."""
    if code == "i":
        return mob, None
    if code == "n":
        return ch, None
    if code == "t":
        return (arg2 if isinstance(arg2, dict) else None), None
    if code == "r":
        return get_random_char(mob), None
    if code == "q":
        return (mob.get("mprog_target") if mob else None), None
    if code == "o":
        return None, arg1
    if code == "p":
        return None, (arg2 if not isinstance(arg2, dict) else None)
    return None, None


def _char_num_lval(check, lval_char, lval_obj):
    """Left-hand value for a numeric if-check (cf. cmd_eval_mob, programs.c:684)."""
    if check == "vnum":
        if lval_obj is not None:
            return lval_obj.get("vnum", 0) if isinstance(lval_obj, dict) else lval_obj
        if lval_char is not None and lval_char.get("is_npc"):
            return lval_char.get("tpl", 0)
        return 0
    if lval_char is None:
        return 0
    if check == "hpcnt":
        return (lval_char.get("hit", 0) * 100) // max(1, lval_char.get("max_hit", 1))
    if check == "room":
        return lval_char.get("room", 0)
    if check == "sex":
        return _SEX_NUM.get(lval_char.get("sex", "neutral"), 0)
    if check == "level":
        return lval_char.get("level", 0)
    if check == "align":
        return lval_char.get("alignment", 0)
    if check == "money":
        return lval_char.get("gold", 0)
    return 0


def _eval_char_bool(check, code, lval_char, lval_obj, mob):
    """Boolean char/obj if-check (cf. cmd_eval_mob, programs.c:536)."""
    c = lval_char
    if check == "ispc":
        return c is not None and not c.get("is_npc")
    if check == "isnpc":
        return c is not None and bool(c.get("is_npc"))
    if check == "isgood":
        return c is not None and c.get("alignment", 0) >= 350
    if check == "isevil":
        return c is not None and c.get("alignment", 0) <= -350
    if check == "isneutral":
        return c is not None and -350 < c.get("alignment", 0) < 350
    if check == "ischarm":
        return c is not None and bool(c.get("affected_by", {}).get("charm"))
    if check == "isfollow":
        if c is None or c.get("master") is None:
            return False
        import world
        master = world.chars.get(c.get("master"))
        return master is not None and master.get("room") == c.get("room")
    if check == "isactive":
        from config import POS_ORDER
        return c is not None and POS_ORDER.get(c.get("pos", "standing"), 0) > POS_ORDER.get("sleeping", 0)
    if check == "isdelay":
        return c is not None and c.get("mprog_delay", 0) > 0
    if check == "isvisible":
        if code in ("o", "p"):
            return lval_obj is not None and _can_see_obj(mob, lval_obj)
        return c is not None and can_see(mob, c)
    if check == "hastarget":
        if c is None:
            return False
        tgt = c.get("mprog_target")
        return tgt is not None and tgt.get("room") == c.get("room")
    if check == "istarget":
        return c is not None and mob.get("mprog_target") is c
    return False


def _eval_char_flag(check, word, lval_char, lval_obj):
    """Flag/word char if-check (cf. cmd_eval_mob, programs.c:589)."""
    c = lval_char
    if check == "name":
        if lval_obj is not None:
            kw = lval_obj.get("keywords", "") if isinstance(lval_obj, dict) else ""
            return is_name(word, kw)
        return c is not None and is_name(word, c.get("name", ""))
    if check == "pos":
        return c is not None and c.get("pos") == word
    if check == "act":
        return c is not None and bool(c.get("is_npc")) and bool(c.get("act_flags", {}).get(word))
    if check == "affected":
        return c is not None and bool(c.get("affected_by", {}).get(word))
    return False


def cmd_eval(check, line, mob, ch, arg1, arg2, rch, prog_vnum):
    """Evaluate one if-check (cf. cmd_eval_mob, programs.c:421).

    A keyword that is valid 1stMud vocabulary (in KNOWN_CHECKS) but outside the
    Phase A subset logs via dbg() and returns False -- the enclosing block is
    simply treated as not taken.  program_flow guarantees *check* is in
    KNOWN_CHECKS before calling.

    Args:
        check (str): If-check keyword.
        line (str): Arguments after the keyword.
        mob (dict): The prog's mob.
        ch (dict or None): Triggering character.
        arg1: Object argument.
        arg2: Target character or object.
        rch (dict or None): Preselected random char.
        prog_vnum (int): Program vnum, for diagnostics.

    Returns:
        bool: The check result.
    """
    toks = line.split()
    if not toks or mob is None:
        return False
    if mob.get("mprog_target") is None:
        mob["mprog_target"] = ch
    buf = toks[0]

    # -- rand: percent roll --
    if check == "rand":
        return _number_percent() < _atoi(buf)

    # -- room population counts: "<check> <op> <n>" --
    if check in _COUNT_FLAG:
        lval = _count_people_room(mob, _COUNT_FLAG[check])
        if len(toks) < 2 or toks[0] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        return num_eval(lval, toks[0], _atoi(toks[1]))
    if check == "hour":
        if len(toks) < 2 or toks[0] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        return num_eval(time_info["hour"], toks[0], _atoi(toks[1]))

    # -- everything else needs a $-code target --
    if len(buf) < 2 or buf[0] != "$":
        dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
        return False
    code = buf[1]
    if code not in ("i", "n", "t", "r", "o", "p", "q"):
        dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
        return False
    lval_char, lval_obj = _resolve_target(code, mob, ch, arg1, arg2)
    if rch is not None and code == "r":
        lval_char = rch
    if lval_char is None and lval_obj is None:
        return False

    if check in _CHAR_BOOL:
        return _eval_char_bool(check, code, lval_char, lval_obj, mob)

    if check in _CHAR_FLAG:
        if len(toks) < 2:
            return False
        return _eval_char_flag(check, toks[1], lval_char, lval_obj)

    if check in _CHAR_NUM:
        if len(toks) < 3 or toks[1] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        lval = _char_num_lval(check, lval_char, lval_obj)
        return num_eval(lval, toks[1], _atoi(toks[2]))

    # Valid 1stMud check, not in the Phase A subset (obj/item/skill/clan/
    # group-order checks land in Phase B/C).
    dbg("prog " + str(prog_vnum) + " check '" + check + "' not ported")
    return False


# -- program flow (cf. program_flow, programs.c:2495) --------------------------

def _parse_line(raw):
    """Split one prog line into (buf, ctrl_lower, data) (cf. programs.c:2506-2532).

    buf keeps original case (drives echo/expansion); ctrl (routing keyword) is
    lowercased for case-insensitive matching; data is everything after the
    first token and the single whitespace that follows it, verbatim.
    """
    s = raw.lstrip()
    if s.endswith("\r"):
        s = s[:-1]
    if s == "":
        return ("", "", "")
    j = 0
    length = len(s)
    while j < length and not s[j].isspace():
        j += 1
    ctrl = s[:j].lower()
    data = s[j + 1:] if j < length else ""
    return (s, ctrl, data)


def _split_first(data):
    """Return (first_word_lower, rest) for an if-check line. [PRIMESUD]"""
    parts = data.split(None, 1)
    if not parts:
        return ("", "")
    return (parts[0].lower(), parts[1] if len(parts) > 1 else "")


def _buggy(prog_vnum, mvnum, msg):
    """Report a malformed program and abort it (cf. buggy_prog, programs.c)."""
    dbg("mobprog: " + msg + ", mob " + str(mvnum) + " prog " + str(prog_vnum))


def _dispatch(prog_vnum, mob, ctrl, expanded):
    """Route an expanded command line (cf. program_flow tail, programs.c:2793)."""
    if ctrl == "mob":
        # mp-command subset lands in Phase C; log and skip for now.
        parts = expanded.split(None, 2)
        sub = parts[1] if len(parts) > 1 else ""
        dbg("prog " + str(prog_vnum) + " mob command '" + sub + "' not ported (Phase C)")
        return
    from commands import interpret
    interpret(expanded, mob)


def program_flow(prog_vnum, code, mob, ch, arg1=None, arg2=None, call_level=0):
    """Run one mob program (cf. program_flow, programs.c:2495).

    Iterative line loop over a fixed state/cond stack.  Control keywords
    (if/or/and/else/endif, ``*`` comment, break/end) drive the stack; any other
    line is $-expanded then dispatched (``mob <subcmd>`` -> mp-table in Phase C,
    else through the real interpreter as the mob).  A malformed program aborts
    via dbg(), as in 1stMud's buggy_prog.

    Args:
        prog_vnum (int): Program vnum (for the MOBPROGS lookup / diagnostics).
        code (str): The program source lines.
        mob (dict): The acting mob instance.
        ch (dict or None): Triggering character.
        arg1: Object argument.
        arg2: Target character or object.
        call_level (int): mpcall recursion depth (Phase C); capped here.
    """
    if call_level >= MAX_CALL_LEVEL:
        dbg("prog " + str(prog_vnum) + " exceeded max call level")
        return
    mvnum = mob.get("tpl") if mob else 0
    state = [IN_BLOCK] * MAX_NESTED_LEVEL
    cond = [True] * MAX_NESTED_LEVEL
    level = 0

    for raw in code.split("\n"):
        buf, ctrl, data = _parse_line(raw)
        if buf == "":            # NullStr(buf) -> end of program
            break
        if buf[0] == "*":        # comment line
            continue

        if ctrl == "if":
            if state[level] == BEGIN_BLOCK:
                _buggy(prog_vnum, mvnum, "misplaced if statement")
                return
            state[level] = BEGIN_BLOCK
            level += 1
            if level >= MAX_NESTED_LEVEL:
                _buggy(prog_vnum, mvnum, "Max nested level exceeded")
                return
            if cond[level - 1] is False:
                cond[level] = False
                continue
            checkname, rest = _split_first(data)
            if checkname in KNOWN_CHECKS:
                cond[level] = cmd_eval(checkname, rest, mob, ch, arg1, arg2, None, prog_vnum)
            else:
                _buggy(prog_vnum, mvnum, "invalid if_check (if)")
                return
            state[level] = END_BLOCK

        elif ctrl == "or":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, mvnum, "or without if")
                return
            if cond[level - 1] is False:
                continue
            checkname, rest = _split_first(data)
            if checkname in KNOWN_CHECKS:
                ev = cmd_eval(checkname, rest, mob, ch, arg1, arg2, None, prog_vnum)
            else:
                _buggy(prog_vnum, mvnum, "invalid if_check (or)")
                return
            if ev:
                cond[level] = True

        elif ctrl == "and":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, mvnum, "and without if")
                return
            if cond[level - 1] is False:
                continue
            checkname, rest = _split_first(data)
            if checkname in KNOWN_CHECKS:
                ev = cmd_eval(checkname, rest, mob, ch, arg1, arg2, None, prog_vnum)
            else:
                _buggy(prog_vnum, mvnum, "invalid if_check (and)")
                return
            cond[level] = bool(cond[level]) and bool(ev)

        elif ctrl == "endif":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, mvnum, "endif without if")
                return
            cond[level] = True
            state[level] = IN_BLOCK
            level -= 1
            state[level] = END_BLOCK

        elif ctrl == "else":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, mvnum, "else without if")
                return
            if cond[level - 1] is False:
                continue
            state[level] = IN_BLOCK
            cond[level] = not cond[level]

        elif cond[level] is True and (ctrl == "break" or ctrl == "end"):
            return

        elif (level == 0 or cond[level] is True):
            state[level] = IN_BLOCK
            expanded = expand_arg(buf, mob, ch, arg1, arg2, None)
            _dispatch(prog_vnum, mob, ctrl, expanded)
