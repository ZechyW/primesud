"""MOBprogram interpreter core (cf. 1stMud programs.c). [PRIMESUD port]

Scripted mob behaviour: a mob template carries ``mob_triggers`` tuples
``(trig_type, mprog_vnum, phrase)``; each mprog vnum maps (via
``world.MOBPROGS``) to a small line-interpreted program.  This module covers
Phases A-C of MOBPROG_PLAN.md: the interpreter engine (A), the trigger-firing
entry points wired into the combat/movement/comm/inventory seams (B/C), and the
``mob <subcmd>`` command set (C).

Public surface:
    has_trigger(mob, ttype) -- cheap empty-tuple early-out; True if the mob's
        template has a trigger of that type.
    program_flow(prog_vnum, code, mob, ch, arg1, arg2) -- run one program.
    cmd_eval(check, line, mob, ch, arg1, arg2, rch, prog_vnum) -- if-check.
    expand_arg(fmt, mob, ch, arg1, arg2, rch) -- $-code expansion.
    num_eval(lval, oper, rval) -- comparison primitive.
    Trigger firing (cf. programs.c p_*_trigger): pulse_mob (random/delay),
        speech_trigger, greet_trigger, entry_trigger, give_trigger,
        bribe_trigger, fight_trigger, kill_trigger, death_trigger; the generic
        percent_trigger / act_trigger primitives underlie them.
    mob_interpret(mob, argument, prog_vnum, call_level) -- run a ``mob``
        prog command through the MP_COMMANDS table.

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
    * ARGUMENT CASE: fixed 2026-07-09 -- interpret() dispatches the free-text
      commands (say/emote/tell/reply/yell, see commands._FREETEXT_FUNS) with the
      verbatim argument tail instead of a lowercased split_args token list, so a
      mob say/emote through interpret() preserves its text and colour codes
      ("{G" stays "{G").  The Phase-C ``mob echo`` family remains available for
      output that must bypass the interpreter entirely.
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
from handler import (
    act, can_see, is_name, number_argument, _HE_SHE, _HIM_HER, _HIS_HER,
    TO_ROOM, TO_CHAR, TO_VICT, TO_NOTVICT,
)

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


def _is_number(s):
    """C is_number: whole string is an integer, optional single sign (cf. 1stMud is_number). [PRIMESUD]"""
    s = s.strip()
    if not s:
        return False
    if s[0] in ("+", "-"):
        s = s[1:]
    return bool(s) and s.isdigit()


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


# -- trigger firing (cf. programs.c p_*_trigger) ------------------------------

def _mob_trigs(mob):
    """Template mob_triggers list for *mob*, or None. [PRIMESUD]"""
    import world
    tpl = world.MOB_DEFS.get(mob.get("tpl")) if mob else None
    return tpl.get("mob_triggers") if tpl else None


def _run_prog(mob, prog_vnum, ch, arg1, arg2):
    """Fetch a program's source and run it (cf. the program_flow call sites). [PRIMESUD]"""
    import world
    code = world.MOBPROGS.get(prog_vnum)
    if code is None:
        dbg("mobprog: missing prog " + str(prog_vnum))
        return
    program_flow(prog_vnum, code, mob, ch, arg1, arg2)


def percent_trigger(mob, ch, arg1, arg2, ttype):
    """Fire the first matching percent-type trigger (cf. p_percent_trigger, programs.c:2895).

    Rolls ``number_percent() < atoi(phrase)`` per *ttype* trigger; runs the
    first that passes.

    Returns:
        bool: True if a program ran.
    """
    trigs = _mob_trigs(mob)
    if not trigs:
        return False
    for t in trigs:
        if t[0] == ttype and _number_percent() < _atoi(t[2]):
            _run_prog(mob, t[1], ch, arg1, arg2)
            return True
    return False


def act_trigger(argument, mob, ch, arg1, arg2, ttype):
    """Fire the first ttype trigger whose phrase is a substring of *argument*.

    Case-sensitive substring match, mirroring 1stMud's ``strstr`` (an empty
    phrase matches everything, as ``strstr(s, "")`` returns s).
    (cf. p_act_trigger, programs.c:2835)
    """
    trigs = _mob_trigs(mob)
    if not trigs:
        return
    for t in trigs:
        if t[0] == ttype and t[2] in argument:
            _run_prog(mob, t[1], ch, arg1, arg2)
            return


def _at_default_pos(mob):
    """True if *mob* is at its template default position (cf. update.c:444).

    Consumes the template ``default_pos`` field (a short word like ``stand``);
    the mob's runtime ``pos`` is the long form (``standing``).
    """
    import world
    tpl = world.MOB_DEFS.get(mob.get("tpl")) if mob else None
    if tpl is None:
        return False
    from config import POS_FROM_SHORT
    dpos = POS_FROM_SHORT.get(tpl.get("default_pos", "stand"), "standing")
    return mob.get("pos") == dpos


def pulse_mob(mob):
    """Random/delay mobprog pulse for one mob (cf. char_update, update.c:444-462).

    Gated on ``position == default_pos`` so a fighting or knocked-down mob
    skips it.  Decrements the delay counter and fires TRIG_DELAY at zero, then
    rolls TRIG_RANDOM.

    Returns:
        bool: True if a program ran (caller should ``continue``, as in 1stMud).
    """
    if not _at_default_pos(mob):
        return False
    if has_trigger(mob, "delay") and mob.get("mprog_delay", 0) > 0:
        mob["mprog_delay"] = mob.get("mprog_delay", 0) - 1
        if mob["mprog_delay"] <= 0:
            percent_trigger(mob, None, None, None, "delay")
            return True
    if has_trigger(mob, "random"):
        if percent_trigger(mob, None, None, None, "random"):
            return True
    return False


def entry_trigger(mob):
    """Fire an ENTRY trigger when an NPC moves into a room (cf. act_move.c:259)."""
    percent_trigger(mob, None, None, None, "entry")


def greet_trigger(ch):
    """Fire GREET/GRALL triggers on room mobs when *ch* enters (cf. p_greet_trigger, programs.c:3154).

    GREET fires only if the mob is at its default position and can see *ch*;
    GRALL fires regardless.  GREET takes precedence over GRALL on the same mob.
    """
    import world
    rs = _room_of(ch)
    if rs is None:
        return
    for mid in list(rs.get("mobs", [])):
        mob = world.chars.get(mid)
        if mob is None or mob is ch or not mob.get("is_npc"):
            continue
        if has_trigger(mob, "greet") and _at_default_pos(mob) and can_see(mob, ch):
            percent_trigger(mob, ch, None, None, "greet")
        elif has_trigger(mob, "grall"):
            percent_trigger(mob, ch, None, None, "grall")


def speech_trigger(argument, speaker):
    """Fire SPEECH triggers on every other NPC in the speaker's room (cf. do_say, act_comm.c:376).

    [PRIMESUD] The speaker itself is skipped: unlike 1stMud (which relies on the
    global MOBtrigger latch), excluding self is the simplest guard against a
    mob's speech prog re-triggering itself into unbounded recursion.
    """
    import world
    rs = _room_of(speaker)
    if rs is None:
        return
    for mid in list(rs.get("mobs", [])):
        mob = world.chars.get(mid)
        # 1stMud do_say gates the mob speech trigger on position == default_pos
        # (a fighting/knocked-down mob does not react); do_tell does not.
        if (mob is not None and mob is not speaker and mob.get("is_npc")
                and _at_default_pos(mob)):
            act_trigger(argument, mob, speaker, None, None, "speech")


def bribe_trigger(mob, ch, amount):
    """Fire a BRIBE trigger if *amount* (in silver) meets the phrase (cf. p_bribe_trigger, programs.c:2949)."""
    trigs = _mob_trigs(mob)
    if not trigs:
        return
    for t in trigs:
        if t[0] == "bribe" and amount >= _atoi(t[2]):
            _run_prog(mob, t[1], ch, None, None)
            return


def give_trigger(mob, ch, obj):
    """Fire a GIVE trigger matching *obj* by vnum, keyword, or ``all`` (cf. p_give_trigger, programs.c:3063).

    The given object is passed as arg1, so the program sees it as ``$o``/``$O``.
    """
    trigs = _mob_trigs(mob)
    if not trigs:
        return
    from item import obj_vnum
    ovnum = obj_vnum(obj)
    kw = _obj_keywords(obj)
    for t in trigs:
        if t[0] != "give":
            continue
        phrase = t[2]
        if _is_number(phrase):
            if ovnum == _atoi(phrase):
                _run_prog(mob, t[1], ch, obj, None)
                return
        else:
            for word in phrase.split():
                if word == "all" or is_name(word, kw):
                    _run_prog(mob, t[1], ch, obj, None)
                    return


def fight_trigger(mob, victim):
    """Fire FIGHT (percent) and HPCNT triggers for a fighting mob (cf. fight.c:91-98).

    The prog's triggering char is the mob's opponent (*victim*).
    """
    if has_trigger(mob, "fight"):
        percent_trigger(mob, victim, None, None, "fight")
    if has_trigger(mob, "hpcnt"):
        _hpcnt_trigger(mob, victim)


def _hpcnt_trigger(mob, victim):
    """Fire the first HPCNT trigger whose phrase exceeds the mob's hp%% (cf. p_hprct_trigger, programs.c:3218)."""
    trigs = _mob_trigs(mob)
    if not trigs:
        return
    pct = (100 * mob.get("hit", 0)) // max(1, mob.get("max_hit", 1))
    for t in trigs:
        if t[0] == "hpcnt" and pct < _atoi(t[2]):
            _run_prog(mob, t[1], victim, None, None)
            return


def kill_trigger(mob, ch):
    """Fire a KILL trigger when *mob* is attacked and joins combat (cf. fight.c:920)."""
    percent_trigger(mob, ch, None, None, "kill")


def death_trigger(mob, ch):
    """Fire a DEATH trigger before the mob is extracted (cf. fight.c:1141).

    Restores the mob to standing first so the program can act, matching 1stMud.
    """
    mob["pos"] = "standing"
    percent_trigger(mob, ch, None, None, "death")


# -- $-code expansion (cf. expand_arg_mob, programs.c:1433) --------------------

def _room_of(mob):
    import world
    return world.rooms._data.get(mob.get("room")) if mob else None


def _target_of(mob):
    """Resolve a mob's mprog_target id to its char instance, or None. [PRIMESUD]

    mprog_target is stored as a char id (like ``master``/``reply``, per
    MOBPROG_PLAN decision 3), not a dict ref: an extracted target drops out of
    ``world.chars`` and resolves to None, matching 1stMud nulling the pointer
    in extract_char -- no explicit clear-on-extract hook needed.
    """
    if mob is None:
        return None
    tid = mob.get("mprog_target")
    if tid is None:
        return None
    import world
    return world.chars.get(tid)


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


def _obj_keywords(obj):
    """Full keyword list of an object (instance dict or bare vnum). [PRIMESUD]"""
    if isinstance(obj, dict):
        kw = obj.get("keywords")
        if kw:
            return kw
        vnum = obj.get("vnum")
    else:
        vnum = obj
    import world
    tpl = world.ITEM_DEFS.get(vnum)
    return tpl.get("keywords", "") if tpl else ""


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
    tgt = _target_of(mob)

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
            # [PRIMESUD] Source (programs.c case 'R') reads `ch` here, not
            # `rch` -- a copy-paste slip that makes $R render the triggering
            # char instead of the random one. We use rch (the intended random
            # char), matching $r/$J/$K/$L. See docs/FIXES.md "mobprog: $R".
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
        return _target_of(mob), None
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
        # ponytail: floor // vs 1stMud's trunc-toward-zero / diverges only for
        # negative hit (dying mob mid-check) with a non-divisible remainder,
        # where the < phrase boolean almost never flips. Use trunc in Phase C
        # if an hpcnt trigger ever misfires on a sub-zero mob.
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
        tgt = _target_of(c)
        return tgt is not None and tgt.get("room") == c.get("room")
    if check == "istarget":
        tid = mob.get("mprog_target")
        return c is not None and tid is not None and tid == c.get("id")
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
    # ponytail: unlike 1stMud one_argument (per-token tolower), we don't
    # lowercase the extracted $-code / flag word / operator here. Real prog
    # data is lowercase by convention and stock data ships zero mobprogs, so an
    # uppercase flag arg ("if pos Standing") or $-code ("if isnpc $N") is the
    # only miss. Lowercase toks in Phase C when real flag/numeric checks land.
    toks = line.split()
    if not toks or mob is None:
        return False
    if mob.get("mprog_target") is None and ch is not None:
        # [PRIMESUD] stored as char id, not a dict ref (see _target_of).
        mob["mprog_target"] = ch.get("id")
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


def _dispatch(prog_vnum, mob, ctrl, expanded, call_level=0):
    """Route an expanded command line (cf. program_flow tail, programs.c:2793)."""
    if ctrl == "mob":
        # strip the leading "mob" token; dispatch the rest to the mp-command set
        parts = expanded.split(None, 1)
        mob_interpret(mob, parts[1] if len(parts) > 1 else "", prog_vnum, call_level)
        return
    if ctrl == "obj" or ctrl == "room":
        # obj/room progs are out of scope; such a line in a MOBprog is a 1stMud
        # bug ("obj command in non MOBprog") -- log and skip.
        dbg("prog " + str(prog_vnum) + " '" + ctrl + "' command in MOBprog")
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
            _dispatch(prog_vnum, mob, ctrl, expanded, call_level)


# -- mp-command set (cf. prog_cmds.c mob_cmd_table) ----------------------------
#
# Every function takes (mob, args, prog_vnum, call_level); *args* is the
# already-$-expanded remainder of the line (program_flow expands the whole line
# before dispatch, so command args are literal text -- there are no $-codes left
# to re-expand).  Most map onto existing PrimeSUD helpers; imports are lazy to
# avoid a circular import (combat/magic/movement all reach back into mobprog).


def _room_persons(mob):
    """Player + all mobs in *mob*'s room (cf. in_room->person_first walk). [PRIMESUD]"""
    import world
    rs = _room_of(mob)
    if rs is None:
        return []
    persons = []
    p = world.chars.get(1)
    if p is not None and p.get("room") == mob.get("room"):
        persons.append(p)
    for mid in rs.get("mobs", []):
        c = world.chars.get(mid)
        if c is not None:
            persons.append(c)
    return persons


def _char_kw(c):
    """Name-match keywords for a char (mob keywords / player name). [PRIMESUD]"""
    import world
    if c.get("is_npc"):
        return c.get("keywords") or world.MOB_DEFS[c["tpl"]].get("keywords", "")
    return c.get("name", "")


def _get_char_room(mob, arg):
    """Find a char in *mob*'s room by name; N. counted syntax (cf. get_char_room). [PRIMESUD]"""
    if not arg:
        return None
    number, name = number_argument(arg)
    count = 0
    for c in _room_persons(mob):
        if not is_name(name, _char_kw(c)):
            continue
        count += 1
        if count == number:
            return c
    return None


def _get_char_world(mob, arg):
    """Find any char in the world by name (cf. get_char_world). [PRIMESUD]"""
    if not arg:
        return None
    import world
    number, name = number_argument(arg)
    count = 0
    for c in world.chars.values():
        if not is_name(name, _char_kw(c)):
            continue
        count += 1
        if count == number:
            return c
    return None


def _char_from_room(ch):
    """Detach a char from its room; NPCs leave the room mob-list. [PRIMESUD]"""
    import world
    if ch.get("is_npc"):
        rs = world.rooms._data.get(ch.get("room"))
        if rs is not None and ch["id"] in rs["mobs"]:
            rs["mobs"].remove(ch["id"])


def _char_to_room(ch, room_vnum):
    """Place a char into a room; NPCs join the room mob-list. [PRIMESUD]"""
    import world
    ch["room"] = room_vnum
    if ch.get("is_npc"):
        rs = world.rooms.get(room_vnum)
        if rs is None:
            rs = {"items": [], "mobs": []}
            world.rooms[room_vnum] = rs
        if ch["id"] not in rs["mobs"]:
            rs["mobs"].append(ch["id"])


def _find_location(mob, arg):
    """Resolve a location arg to a room vnum (cf. find_location). [PRIMESUD]

    Accepts a numeric room vnum (must be a known/resident room) or the name of a
    char in the mob's room (returns that char's room).  1stMud also resolves
    world-wide char/object locations; stock progs use vnums.
    """
    import world
    if _is_number(arg):
        v = _atoi(arg)
        return v if v in world.ROOM_DEFS._data else None
    c = _get_char_room(mob, arg)
    return c.get("room") if c is not None else None


def _detach_obj(mob, obj):
    """Remove *obj* from the mob's room floor, inventory, or equipment. [PRIMESUD]"""
    rs = _room_of(mob)
    if rs is not None and obj in rs.get("items", []):
        rs["items"].remove(obj)
        return
    if obj in mob.get("inv", []):
        mob["inv"].remove(obj)
        return
    for slot, o in list(mob.get("equip", {}).items()):
        if o is obj:
            mob["equip"][slot] = None
            return


def _obj_has_nopurge(obj):
    """True if *obj* carries the nopurge extra flag (kept by a room purge). [PRIMESUD]"""
    from item import obj_vnum
    import world
    if isinstance(obj, dict) and "extra_flags" in obj:
        ef = obj["extra_flags"]
    else:
        tpl = world.ITEM_DEFS.get(obj_vnum(obj))
        ef = tpl.get("extra_flags", {}) if tpl else {}
    return bool(ef.get("nopurge"))


# -- echoes (rendered as plain output; channels/immortal prefixes not ported) --

def _mp_echo(mob, args, pv, cl):
    if not args:
        return
    act(args, mob, None, None, TO_ROOM)


def _mp_echoaround(mob, args, pv, cl):
    parts = args.split(None, 1)
    if not parts:
        return
    victim = _get_char_room(mob, parts[0])
    if victim is None:
        return
    act(parts[1] if len(parts) > 1 else "", mob, None, victim, TO_NOTVICT)


def _mp_echoat(mob, args, pv, cl):
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        return
    victim = _get_char_room(mob, parts[0])
    if victim is None:
        return
    act(parts[1], mob, None, victim, TO_VICT)


def _mp_gecho(mob, args, pv, cl):
    """Global echo (cf. do_mpgecho).  [PRIMESUD] single-player: to the one player."""
    if not args:
        return
    import world
    from handler import chprintln
    p = world.chars.get(1)
    if p is not None:
        chprintln(p, args)


def _mp_zecho(mob, args, pv, cl):
    """Zone echo (cf. do_mpzecho).  [PRIMESUD] to the player if in the mob's area."""
    if not args:
        return
    import world
    from handler import chprintln
    p = world.chars.get(1)
    if p is None:
        return
    proom = world.ROOM_DEFS._data.get(p.get("room"))
    mroom = world.ROOM_DEFS._data.get(mob.get("room"))
    if proom is not None and mroom is not None and proom.get("area") == mroom.get("area"):
        chprintln(p, args)


def _mp_asound(mob, args, pv, cl):
    """Sound heard from every adjacent room (cf. do_mpasound)."""
    if not args:
        return
    import world
    was = mob.get("room")
    in_room = world.ROOM_DEFS._data.get(was)
    if in_room is None:
        return
    for _d, ev in in_room.get("exits", {}).items():
        dest = ev.get("to") if isinstance(ev, dict) else ev
        if dest is None or dest == was:
            continue
        mob["room"] = dest
        act(args, mob, None, None, TO_ROOM)
    mob["room"] = was


# -- combat / targeting --------------------------------------------------------

def _mp_kill(mob, args, pv, cl):
    arg = _first(args)
    if not arg:
        return
    victim = _get_char_room(mob, arg)
    if victim is None:
        return
    if victim is mob or victim.get("is_npc") or mob.get("pos") == "fighting":
        return
    if mob.get("affected_by", {}).get("charm") and mob.get("master") == victim.get("id"):
        dbg("mobprog: charmed mob attacking master, mob " + str(mob.get("tpl", 0)))
        return
    from combat import multi_hit
    multi_hit(mob, victim)


def _mp_assist(mob, args, pv, cl):
    arg = _first(args)
    if not arg:
        return
    victim = _get_char_room(mob, arg)
    if victim is None or victim is mob or mob.get("fighting") is not None:
        return
    if victim.get("fighting") is None:
        return
    import world
    target = world.chars.get(victim["fighting"])
    if target is None:
        return
    from combat import multi_hit
    multi_hit(mob, target)


def _mp_damage(mob, args, pv, cl):
    parts = args.split()
    if not parts:
        dbg("mobprog: mpdamage bad syntax")
        return
    target = parts[0]
    minv = parts[1] if len(parts) > 1 else ""
    maxv = parts[2] if len(parts) > 2 else ""
    if not _is_number(minv) or not _is_number(maxv):
        dbg("mobprog: mpdamage bad range")
        return
    low, high = _atoi(minv), _atoi(maxv)
    if high < low:
        high = low
    fkill = len(parts) > 3 and bool(parts[3])
    from combat import damage, DAM_NONE
    from config import TYPE_UNDEFINED

    def _hit(v):
        amt = randint(low, high)
        if not fkill:
            amt = min(v.get("hit", 0), amt)
        # attacker == victim -> no retaliation / no TRIG_KILL (cf. do_mpdamage,
        # fight.c: damage(victim, victim, ...); victim != ch is false).
        damage(v, v, amt, TYPE_UNDEFINED, DAM_NONE, False)

    if target == "all":
        for c in list(_room_persons(mob)):
            if c is not mob:
                _hit(c)
    else:
        v = _get_char_room(mob, target)
        if v is None:
            return
        _hit(v)


def _mp_cast(mob, args, pv, cl):
    parts = args.split()
    spell = parts[0] if parts else ""
    target_name = parts[1] if len(parts) > 1 else ""
    if not spell:
        dbg("mobprog: mpcast bad syntax")
        return
    from magic import _skill_lookup, SPELL_FUNS, TARGET_CHAR, TARGET_OBJ, TARGET_NONE
    from skills_table import SKILLS
    sn = _skill_lookup(spell)
    if sn is None:
        dbg("mobprog: mpcast no such spell '" + spell + "'")
        return
    sk = SKILLS.get(sn)
    if sk is None:
        return
    vch = _get_char_room(mob, target_name) if target_name else None
    from item import get_obj_here
    obj = get_obj_here(mob, target_name) if target_name else None
    tgt = sk.get("target")
    if tgt == "ignore":
        victim, tconst = None, TARGET_NONE
    elif tgt == "char_offensive":
        if vch is None or vch is mob:
            return
        victim, tconst = vch, TARGET_CHAR
    elif tgt == "char_defensive":
        victim, tconst = (vch if vch is not None else mob), TARGET_CHAR
    elif tgt == "char_self":
        victim, tconst = mob, TARGET_CHAR
    elif tgt in ("obj_char_offensive", "obj_char_defensive", "obj_inventory"):
        if obj is None:
            return
        victim, tconst = obj, TARGET_OBJ
    else:
        return
    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"))
    if fun is None:
        return
    fun(sn, mob.get("level", 1), mob, victim, tconst)


def _mp_peace(mob, args, pv, cl):
    from combat import stop_fighting
    for c in list(_room_persons(mob)):
        if c.get("fighting") is not None:
            stop_fighting(c, both=True)
        if c.get("is_npc") and c.get("act_flags", {}).get("aggressive"):
            c["act_flags"]["aggressive"] = False


def _mp_flee(mob, args, pv, cl):
    if mob.get("fighting") is not None:
        return
    import world
    was = mob.get("room")
    in_room = world.ROOM_DEFS._data.get(was)
    if in_room is None:
        return
    exits = in_room.get("exits", {})
    order = list(exits.keys())
    for i in range(len(order) - 1, 0, -1):    # Fisher-Yates (cf. number_door attempts)
        j = randint(0, i)
        order[i], order[j] = order[j], order[i]
    from movement import move_char
    for d in order:
        ev = exits[d]
        if isinstance(ev, dict) and ev.get("closed"):
            continue
        dest = ev.get("to") if isinstance(ev, dict) else ev
        droom = world.ROOM_DEFS._data.get(dest)
        if droom is None or droom.get("flags", {}).get("no_mob"):
            continue
        move_char(mob, d)
        if mob.get("room") != was:
            return


# -- loading / purging / moving objects ----------------------------------------

def _mp_mload(mob, args, pv, cl):
    arg = _first(args)
    if not arg or not _is_number(arg):
        return
    import world
    vnum = _atoi(arg)
    if vnum not in world.MOB_DEFS:
        dbg("mobprog: mpmload bad mob " + str(vnum))
        return
    from mob import create_mobile
    victim = create_mobile(vnum)
    room = mob.get("room")
    victim["room"] = room
    victim["home_area"] = world.ROOM_DEFS[room].get("area")
    nid = max(world.chars, default=1) + 1
    victim["id"] = nid
    world.chars[nid] = victim
    world.rooms[room]["mobs"].append(nid)


def _mp_oload(mob, args, pv, cl):
    parts = args.split()
    if not parts or not _is_number(parts[0]):
        dbg("mobprog: mpoload bad syntax")
        return
    import world
    vnum = _atoi(parts[0])
    if vnum not in world.ITEM_DEFS:
        dbg("mobprog: mpoload bad obj " + str(vnum))
        return
    # arg2 = level (ignored: create_object has no per-load level scaling in
    # PrimeSUD); arg3 = R (to room) / W (worn).
    arg2 = parts[1] if len(parts) > 1 else ""
    arg3 = parts[2] if len(parts) > 2 else ""
    if arg2 and not _is_number(arg2):
        dbg("mobprog: mpoload bad level")
        return
    from item import create_object, item_wear_flags
    obj = create_object(vnum)
    to_room = arg3[:1] in ("R", "r")
    to_wear = arg3[:1] in ("W", "w")
    can_take = "take" in item_wear_flags(obj, world.ITEM_DEFS[vnum])
    if (to_wear or not to_room) and can_take:
        mob["inv"].append(obj)
        if to_wear:
            from inventory import wear_obj
            wear_obj(mob, obj, True)
    else:
        world.rooms[mob["room"]]["items"].append(obj)


def _mp_purge(mob, args, pv, cl):
    import world
    rs = _room_of(mob)
    arg = _first(args)
    if not arg:
        if rs is None:
            return
        from combat import _extract_char
        for mid in list(rs.get("mobs", [])):
            v = world.chars.get(mid)
            if (v is not None and v is not mob and v.get("is_npc")
                    and not v.get("act_flags", {}).get("nopurge")):
                _extract_char(v, pull=True)
        rs["items"] = [o for o in rs.get("items", []) if _obj_has_nopurge(o)]
        return
    victim = _get_char_room(mob, arg)
    if victim is None:
        from item import get_obj_here
        obj = get_obj_here(mob, arg)
        if obj is not None:
            _detach_obj(mob, obj)
        else:
            dbg("mobprog: mppurge bad arg, mob " + str(mob.get("tpl", 0)))
        return
    if not victim.get("is_npc"):
        dbg("mobprog: mppurge PC, mob " + str(mob.get("tpl", 0)))
        return
    from combat import _extract_char
    _extract_char(victim, pull=True)


def _mp_junk(mob, args, pv, cl):
    arg = _first(args)
    if not arg:
        return
    from item import get_obj_list
    import world
    al = arg.lower()
    if al != "all" and not al.startswith("all."):
        for slot, o in list(mob.get("equip", {}).items()):
            if o is not None and is_name(arg, _obj_keywords(o)):
                mob["equip"][slot] = None
                return
        o = get_obj_list(arg, mob.get("inv", []), world.ITEM_DEFS)
        if o is None:
            return
        mob["inv"].remove(o)
    else:
        name = arg[4:] if al.startswith("all.") else ""
        for o in list(mob.get("inv", [])):
            if not name or is_name(name, _obj_keywords(o)):
                mob["inv"].remove(o)
        for slot, o in list(mob.get("equip", {}).items()):
            if o is not None and (not name or is_name(name, _obj_keywords(o))):
                mob["equip"][slot] = None


def _mp_otransfer(mob, args, pv, cl):
    parts = args.split()
    if not parts:
        dbg("mobprog: mpotransfer missing arg")
        return
    loc = _find_location(mob, parts[1] if len(parts) > 1 else "")
    if loc is None:
        dbg("mobprog: mpotransfer no location")
        return
    from item import get_obj_here
    obj = get_obj_here(mob, parts[0])
    if obj is None:
        return
    _detach_obj(mob, obj)
    import world
    world.rooms[loc]["items"].append(obj)


def _mp_remove(mob, args, pv, cl):
    parts = args.split()
    if not parts:
        return
    victim = _get_char_room(mob, parts[0])
    if victim is None:
        return
    spec = parts[1] if len(parts) > 1 else ""
    fall = (spec == "all")
    if not fall and not _is_number(spec):
        dbg("mobprog: mpremove invalid object, mob " + str(mob.get("tpl", 0)))
        return
    from item import obj_vnum
    vnum = _atoi(spec) if _is_number(spec) else 0
    for o in list(victim.get("inv", [])):
        if fall or obj_vnum(o) == vnum:
            victim["inv"].remove(o)
    for slot, o in list(victim.get("equip", {}).items()):
        if o is not None and (fall or obj_vnum(o) == vnum):
            victim["equip"][slot] = None


# -- movement / redirection ----------------------------------------------------

def _mp_goto(mob, args, pv, cl):
    arg = _first(args)
    if not arg:
        dbg("mobprog: mpgoto no arg")
        return
    loc = _find_location(mob, arg)
    if loc is None:
        dbg("mobprog: mpgoto no location")
        return
    if mob.get("fighting") is not None:
        from combat import stop_fighting
        stop_fighting(mob, both=True)
    _char_from_room(mob)
    _char_to_room(mob, loc)


def _mp_at(mob, args, pv, cl):
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("mobprog: mpat bad syntax")
        return
    loc = _find_location(mob, parts[0])
    if loc is None:
        dbg("mobprog: mpat no location")
        return
    import world
    original = mob.get("room")
    _char_from_room(mob)
    _char_to_room(mob, loc)
    from commands import interpret
    interpret(parts[1], mob)
    if world.chars.get(mob.get("id")) is mob:   # command may have moved/killed the mob
        _char_from_room(mob)
        _char_to_room(mob, original)


def _mp_transfer(mob, args, pv, cl):
    parts = args.split()
    if not parts:
        dbg("mobprog: mptransfer bad syntax")
        return
    arg1 = parts[0]
    arg2 = parts[1] if len(parts) > 1 else ""
    if arg1 == "all":
        for c in list(_room_persons(mob)):
            if not c.get("is_npc"):
                _mp_transfer(mob, c.get("name", "") + ((" " + arg2) if arg2 else ""), pv, cl)
        return
    if not arg2:
        loc = mob.get("room")
    else:
        loc = _find_location(mob, arg2)
        if loc is None:
            dbg("mobprog: mptransfer no location")
            return
    victim = _get_char_world(mob, arg1)
    if victim is None or victim.get("room") is None:
        return
    if victim.get("fighting") is not None:
        from combat import stop_fighting
        stop_fighting(victim, both=True)
    _char_from_room(victim)
    _char_to_room(victim, loc)
    if not victim.get("is_npc"):
        from movement import do_look
        do_look(victim, [])
        greet_trigger(victim)


def _mp_force(mob, args, pv, cl):
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("mobprog: mpforce bad syntax")
        return
    arg, rest = parts[0], parts[1]
    from commands import interpret
    if arg == "all":
        for c in list(_room_persons(mob)):
            if c is not mob and can_see(mob, c):
                interpret(rest, c)
    else:
        victim = _get_char_room(mob, arg)
        if victim is None or victim is mob:
            return
        interpret(rest, victim)


# -- target memory / delay / recursion -----------------------------------------

def _mp_remember(mob, args, pv, cl):
    arg = _first(args)
    if not arg:
        dbg("mobprog: mpremember missing arg")
        return
    victim = _get_char_world(mob, arg)
    # [PRIMESUD] stored as char id (see _target_of), not a dict ref
    mob["mprog_target"] = victim.get("id") if victim is not None else None


def _mp_forget(mob, args, pv, cl):
    mob["mprog_target"] = None


def _mp_delay(mob, args, pv, cl):
    arg = _first(args)
    if not _is_number(arg):
        dbg("mobprog: mpdelay invalid arg")
        return
    mob["mprog_delay"] = _atoi(arg)


def _mp_cancel(mob, args, pv, cl):
    mob["mprog_delay"] = -1


def _mp_call(mob, args, pv, cl):
    parts = args.split()
    if not parts:
        dbg("mobprog: mpcall missing arg")
        return
    if not _is_number(parts[0]):
        dbg("mobprog: mpcall invalid prog")
        return
    import world
    prog_vnum = _atoi(parts[0])
    code = world.MOBPROGS.get(prog_vnum)
    if code is None:
        dbg("mobprog: mpcall invalid prog " + str(prog_vnum))
        return
    vch = _get_char_room(mob, parts[1]) if len(parts) > 1 and parts[1] else None
    from item import get_obj_here
    obj1 = get_obj_here(mob, parts[2]) if len(parts) > 2 and parts[2] else None
    obj2 = get_obj_here(mob, parts[3]) if len(parts) > 3 and parts[3] else None
    program_flow(prog_vnum, code, mob, vch, obj1, obj2, call_level=cl + 1)


def _mp_skip(mob, args, pv, cl):
    # [PRIMESUD] mpgtransfer / mpgforce / mpvforce skipped -- group / mass
    # multiplayer commands with no single-player meaning (MOBPROG_PLAN dec. 5).
    dbg("mobprog: group/mass mp-command skipped (not ported)")


# Table order matches 1stMud mob_cmd_table (prog_cmds.c:43); dispatch is a
# case-insensitive prefix match in this order (first match wins).
MP_COMMANDS = (
    ("asound", _mp_asound),
    ("gecho", _mp_gecho),
    ("zecho", _mp_zecho),
    ("kill", _mp_kill),
    ("assist", _mp_assist),
    ("junk", _mp_junk),
    ("echo", _mp_echo),
    ("echoaround", _mp_echoaround),
    ("echoat", _mp_echoat),
    ("mload", _mp_mload),
    ("oload", _mp_oload),
    ("purge", _mp_purge),
    ("goto", _mp_goto),
    ("at", _mp_at),
    ("transfer", _mp_transfer),
    ("gtransfer", _mp_skip),
    ("otransfer", _mp_otransfer),
    ("force", _mp_force),
    ("gforce", _mp_skip),
    ("vforce", _mp_skip),
    ("cast", _mp_cast),
    ("damage", _mp_damage),
    ("remember", _mp_remember),
    ("forget", _mp_forget),
    ("delay", _mp_delay),
    ("cancel", _mp_cancel),
    ("call", _mp_call),
    ("flee", _mp_flee),
    ("remove", _mp_remove),
    ("peace", _mp_peace),
)


def mob_interpret(mob, argument, prog_vnum=0, call_level=0):
    """Dispatch a ``mob <subcmd>`` prog command (cf. mob_interpret, prog_cmds.c:187).

    Prefix-matched against MP_COMMANDS in table order (first match wins),
    mirroring 1stMud's ``command[0]==name[0] && !str_prefix``.  An unknown
    subcommand logs a bug and is skipped (cf. 1stMud bugf).
    """
    parts = argument.split(None, 1)
    if not parts:
        return
    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    for name, fn in MP_COMMANDS:
        if name[0] == command[0] and name.startswith(command):
            fn(mob, rest, prog_vnum, call_level)
            return
    dbg("mobprog: invalid cmd '" + command + "' from mob " + str(mob.get("tpl", 0)))
