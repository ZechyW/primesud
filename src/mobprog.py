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

-- Tri-modal interpreter (PROGS_PLAN Phase 1) --

program_flow runs MOB, OBJ, and ROOM programs (cf. programs.c) -- exactly one
origin per run.  A mob origin is the mob dict; an obj origin is a mutable
context dict ``{"obj": obj_dict, "room": room_vnum, "carrier": char_or_None}``
(PrimeSUD objects carry no location back-pointer, so fire sites supply it;
``obj goto``/``otransfer`` update it in place); a room origin is its vnum.
Obj/room progs may only issue control lines and ``obj <cmd>`` /
``room <cmd>`` lines (obj_interpret / room_interpret over OP_COMMANDS /
RP_COMMANDS); a raw command line outside a MOBprog is a bug() skip, exactly
as upstream (programs.c:2782-2828).  If-checks route to _cmd_eval_other and
$-expansion to expand_arg_other for obj/room origins.  Per-instance state:
``oprog_delay``/``oprog_target`` on obj dicts, ``rprog_delay``/
``rprog_target`` on runtime room dicts -- transient by design (save surface
is player-only; world rebuilds each boot).

Trigger word ``surr`` is rejected upstream (the converter accepts it but the
mechanic is unported); every other trigger word is engine-supported.  Obj/room
trigger firing (PROGS_PLAN Phase 2): has_otrigger/has_rtrigger walk the
template ``obj_triggers``/``room_triggers`` tuples; the o*/r* trigger
functions below build the obj context at fire time and are wired into the
same seams as their mob counterparts (get/drop/give, move exit/greet, say,
act, the violence round, and the obj/room random-delay pulses).  Obj TRIG_SIT
has no seam -- furniture is not ported (see movement.py).
"""

from urandom import randint

import world
from classes import class_lookup, prime_class
from combat import (
    damage, is_same_group, multi_hit, stop_fighting, _extract_char, DAM_NONE,
)
from commands import interpret
from config import EXIT_ORDER, POS_FROM_SHORT, POS_ORDER, TYPE_UNDEFINED
from debug import DBG, dbg
from game_time import time_info
from handler import (
    act, can_see, can_see_obj, chprintln, is_name, number_argument,
    _HE_SHE, _HIM_HER, _HIS_HER, TO_ROOM, TO_CHAR, TO_VICT, TO_NOTVICT,
    PLR_AUTOMAP, PLR_AUTOSKILL, PLR_AUTOASSIST, PLR_AUTOEXIT, PLR_AUTOLOOT,
    PLR_AUTOSAC, PLR_AUTOGOLD, PLR_AUTOSPLIT, PLR_AUTODAMAGE,
)
from inventory import wear_obj
from item import (
    create_object, get_carry_weight, get_obj_here, get_obj_list,
    item_wear_flags, obj_vnum, prog_obj_value,
)
from magic import _skill_lookup, SPELL_FUNS, TARGET_CHAR, TARGET_OBJ, TARGET_NONE
from mob import create_mobile
from movement import do_look, move_char
from quest import is_quester
from races import race_lookup
from skill_utils import get_skill
from skills_table import SKILLS

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

# Global act-trigger latch (cf. 1stMud MOBtrigger).  handler.act() fires
# TRIG_ACT on NPC recipients only while this is True; act output that must not
# spawn act triggers (an emote, an mpasound, or -- [PRIMESUD] -- anything a
# prog itself emits while its own act triggers are dispatching) clears it.
MOBtrigger = True

# Global program_flow depth (cf. 1stMud's static call_level, programs.c:2452):
# bumped on every entry, so ANY reentrant prog cascade -- mob call, or a prog
# whose commands synchronously fire another trigger -- is bounded by
# MAX_CALL_LEVEL, exactly as in the source.
_call_depth = 0


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
    """C is_number: whole string is an integer, optional single sign (cf. 1stMud is_number). [PRIMESUD]

    Deviation: a lone "+"/"-" is False here; 1stMud's loop quirk returns true
    for it (the stripped-empty string never fails the digit walk).
    """
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
    tpl = world.MOB_DEFS.get(mob.get("tpl")) if mob else None
    return tpl.get("mob_triggers") if tpl else None


def _run_prog(mob, prog_vnum, ch, arg1, arg2):
    """Fetch a program's source and run it (cf. the program_flow call sites). [PRIMESUD]"""
    code = world.MOBPROGS.get(prog_vnum)
    if code is None:
        dbg("mobprog: missing prog " + str(prog_vnum))
        return
    if "prog" in DBG:  # live trigger-fire trace (cf. 1stMud ptrace ring buffer)
        dbg("prog " + str(prog_vnum) + " fires, mob " + str(mob.get("tpl", 0))
            + " room " + str(mob.get("room", 0)))
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
    tpl = world.MOB_DEFS.get(mob.get("tpl")) if mob else None
    if tpl is None:
        return False
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


def exit_trigger(ch, direction):
    """Fire an EXIT/EXALL trigger when *ch* leaves a room (cf. p_exit_trigger, programs.c:2965).

    Walks the NPC mobs in *ch*'s room; the trigger phrase is the door number
    (0=N..5=D, matching ``EXIT_ORDER``).  EXIT fires only if the mob is at its
    default position and can see *ch*; EXALL fires regardless.  Only MOB progs
    are ported (obj/room progs skipped -- MOBPROG_PLAN decision 1).

    Args:
        ch (dict): The leaving character.
        direction (str): Single-char direction key (n/e/s/w/u/d).

    Returns:
        bool: True if a program fired (caller aborts the move, as in 1stMud).
    """
    try:
        dnum = EXIT_ORDER.index(direction)
    except ValueError:
        return False
    rs = _room_of(ch)
    if rs is None:
        return False
    for mid in list(rs.get("mobs", [])):
        mob = world.chars.get(mid)
        if mob is None or not mob.get("is_npc"):
            continue
        trigs = _mob_trigs(mob)
        if not trigs:
            continue
        for t in trigs:
            if t[0] == "exit" and _atoi(t[2]) == dnum and _at_default_pos(mob) and can_see(mob, ch):
                _run_prog(mob, t[1], ch, None, None)
                return True
            if t[0] == "exall" and _atoi(t[2]) == dnum:
                _run_prog(mob, t[1], ch, None, None)
                return True
    return False


def speech_trigger(argument, speaker):
    """Fire SPEECH triggers for a player's say: per room person the mob check
    then that person's carried objects (the speaker's own included), then
    floor objects, then the room (cf. do_say, act_comm.c:371-403).

    The caller (do_say) invokes this only for a *player* speaker, mirroring
    1stMud's ``if (!IsNPC(ch))`` gate (act_comm.c:371): a mob's prog ``say``
    fires no speech triggers, which is what bounds mob-to-mob speech recursion.
    The self-skip below is then belt-and-braces (the speaker is never an NPC in
    the loop anyway).
    """
    rvnum = speaker.get("room")
    rs = world.rooms._data.get(rvnum)
    if rs is None:
        return
    for person in list(_persons_at(rvnum)):
        # 1stMud do_say gates the mob speech trigger on position == default_pos
        # (a fighting/knocked-down mob does not react); do_tell does not.
        if (person is not speaker and person.get("is_npc")
                and _at_default_pos(person)):
            act_trigger(argument, person, speaker, None, None, "speech")
        for o in _carried_objs(person):
            if has_otrigger(o, "speech"):
                oact_trigger(argument,
                             {"obj": o, "room": rvnum, "carrier": person},
                             speaker, "speech")
    for o in list(rs.get("items", [])):
        if has_otrigger(o, "speech"):
            oact_trigger(argument, {"obj": o, "room": rvnum, "carrier": None},
                         speaker, "speech")
    if has_rtrigger(rvnum, "speech"):
        ract_trigger(argument, rvnum, speaker, "speech")


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
    # [PRIMESUD] max(1, ...) guards div-by-zero; 1stMud divides by max_hit raw.
    # ponytail: // floors where C truncates toward zero -- differs only for a
    # negative-hp mob on a non-exact division, off by one pct point (same
    # accepted divergence as _char_num_lval's hpcnt).
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


# -- obj/room trigger firing (cf. programs.c tri-mode p_*_trigger branches) ----

def _obj_trigs(obj):
    """Template obj_triggers tuple for *obj* (instance dict or vnum), or None. [PRIMESUD]"""
    tpl = world.ITEM_DEFS.get(obj_vnum(obj)) if obj is not None else None
    return tpl.get("obj_triggers") if tpl else None


def has_otrigger(obj, ttype):
    """True if *obj*'s template has a trigger of *ttype* (cf. 1stMud HasTriggerObj)."""
    trigs = _obj_trigs(obj)
    if not trigs:  # empty tuple / absent -- cheap short-circuit
        return False
    for t in trigs:
        if t[0] == ttype:
            return True
    return False


def _room_trigs(rvnum):
    """Template room_triggers tuple for room *rvnum*, or None. [PRIMESUD]

    ._data lookup: fire sites only concern already-resident rooms; a prog must
    never pull a foreign area into the heap.
    """
    tpl = world.ROOM_DEFS._data.get(rvnum) if rvnum is not None else None
    return tpl.get("room_triggers") if tpl else None


def has_rtrigger(rvnum, ttype):
    """True if room *rvnum*'s template has a trigger of *ttype* (cf. 1stMud HasTriggerRoom)."""
    trigs = _room_trigs(rvnum)
    if not trigs:
        return False
    for t in trigs:
        if t[0] == ttype:
            return True
    return False


def _run_oprog(octx, prog_vnum, ch, arg1, arg2):
    """Fetch an obj program's source and run it (cf. the OPROG program_flow call sites). [PRIMESUD]"""
    code = world.OBJPROGS.get(prog_vnum)
    if code is None:
        dbg("mobprog: missing objprog " + str(prog_vnum))
        return
    if "prog" in DBG:  # live trigger-fire trace (cf. 1stMud ptrace ring buffer)
        dbg("objprog " + str(prog_vnum) + " fires, obj "
            + str(obj_vnum(octx["obj"])) + " room " + str(_octx_room(octx)))
    program_flow(prog_vnum, code, None, ch, arg1, arg2, obj=octx)


def _run_rprog(rvnum, prog_vnum, ch, arg1, arg2):
    """Fetch a room program's source and run it (cf. the RPROG program_flow call sites). [PRIMESUD]"""
    code = world.ROOMPROGS.get(prog_vnum)
    if code is None:
        dbg("mobprog: missing roomprog " + str(prog_vnum))
        return
    if "prog" in DBG:
        dbg("roomprog " + str(prog_vnum) + " fires, room " + str(rvnum))
    program_flow(prog_vnum, code, None, ch, arg1, arg2, room=rvnum)


def opercent_trigger(octx, ch, arg1, arg2, ttype):
    """Percent-type trigger on an obj (cf. p_percent_trigger obj branch, programs.c:2919).

    Returns:
        bool: True if a program ran.
    """
    trigs = _obj_trigs(octx["obj"])
    if not trigs:
        return False
    for t in trigs:
        if t[0] == ttype and _number_percent() < _atoi(t[2]):
            _run_oprog(octx, t[1], ch, arg1, arg2)
            return True
    return False


def rpercent_trigger(rvnum, ch, arg1, arg2, ttype):
    """Percent-type trigger on a room (cf. p_percent_trigger room branch, programs.c:2931).

    Returns:
        bool: True if a program ran.
    """
    trigs = _room_trigs(rvnum)
    if not trigs:
        return False
    for t in trigs:
        if t[0] == ttype and _number_percent() < _atoi(t[2]):
            _run_rprog(rvnum, t[1], ch, arg1, arg2)
            return True
    return False


def oact_trigger(argument, octx, ch, ttype):
    """First *ttype* obj trigger whose phrase is a substring of *argument*
    (cf. p_act_trigger obj branch, programs.c:2865).  Every upstream obj/room
    act/speech call site passes NULL arg1/arg2, so they are omitted here."""
    trigs = _obj_trigs(octx["obj"])
    if not trigs:
        return
    for t in trigs:
        if t[0] == ttype and t[2] in argument:
            _run_oprog(octx, t[1], ch, None, None)
            return


def ract_trigger(argument, rvnum, ch, ttype):
    """First *ttype* room trigger whose phrase is a substring of *argument*
    (cf. p_act_trigger room branch, programs.c:2877)."""
    trigs = _room_trigs(rvnum)
    if not trigs:
        return
    for t in trigs:
        if t[0] == ttype and t[2] in argument:
            _run_rprog(rvnum, t[1], ch, None, None)
            return


def ogive_trigger(octx, ch, ttype):
    """GIVE/GET/DROP-family trigger on the obj itself (cf. p_give_trigger obj
    branch, programs.c:3110): no phrase match -- the first program of *ttype*
    fires, with the obj itself as arg1 (the prog sees it as $o)."""
    trigs = _obj_trigs(octx["obj"])
    if not trigs:
        return
    for t in trigs:
        if t[0] == ttype:
            _run_oprog(octx, t[1], ch, octx["obj"], None)
            return


def rgive_trigger(rvnum, ch, dropped, ttype):
    """GIVE/GET/DROP-family trigger on a room, phrase-matched against *dropped*
    by vnum, keyword, or ``all`` (cf. p_give_trigger room branch, programs.c:3119).

    The moved object is passed as arg1 ($o)."""
    trigs = _room_trigs(rvnum)
    if not trigs:
        return
    dvnum = obj_vnum(dropped)
    kw = _obj_keywords(dropped)
    for t in trigs:
        if t[0] != ttype:
            continue
        phrase = t[2]
        if _is_number(phrase):
            if dvnum == _atoi(phrase):
                _run_rprog(rvnum, t[1], ch, dropped, None)
                return
        else:
            for word in phrase.split():
                if word == "all" or is_name(word, kw):
                    _run_rprog(rvnum, t[1], ch, dropped, None)
                    return


def _carried_objs(c):
    """Every object *c* carries, worn included (cf. carrying_first walk). [PRIMESUD]"""
    objs = list(c.get("inv", []))
    for o in (c.get("equip") or {}).values():
        if o is not None:
            objs.append(o)
    return objs


def oexit_trigger(ch, direction):
    """EXALL objprog check when *ch* leaves a room (cf. p_exit_trigger
    PRG_OPROG, programs.c:3002).

    Floor objects first, then every room person's carried objects.  The obj
    trigger vocabulary has no "exit" word, so only EXALL exists.

    Returns:
        bool: True if a program fired (caller aborts the move, as in 1stMud).
    """
    if not world.OBJPROGS:  # ponytail: no obj progs loaded -> skip the scan
        return False
    try:
        dnum = EXIT_ORDER.index(direction)
    except ValueError:
        return False
    rvnum = ch.get("room")
    rs = world.rooms._data.get(rvnum)
    if rs is None:
        return False
    for o in list(rs.get("items", [])):
        trigs = _obj_trigs(o)
        if not trigs:
            continue
        for t in trigs:
            if t[0] == "exall" and _atoi(t[2]) == dnum:
                _run_oprog({"obj": o, "room": rvnum, "carrier": None},
                           t[1], ch, None, None)
                return True
    for person in list(_persons_at(rvnum)):
        for o in _carried_objs(person):
            trigs = _obj_trigs(o)
            if not trigs:
                continue
            for t in trigs:
                if t[0] == "exall" and _atoi(t[2]) == dnum:
                    _run_oprog({"obj": o, "room": rvnum, "carrier": person},
                               t[1], ch, None, None)
                    return True
    return False


def rexit_trigger(ch, direction):
    """EXALL roomprog check when *ch* leaves (cf. p_exit_trigger PRG_RPROG,
    programs.c:3042).  The room trigger vocabulary has no "exit" word either.

    Returns:
        bool: True if a program fired (caller aborts the move, as in 1stMud).
    """
    try:
        dnum = EXIT_ORDER.index(direction)
    except ValueError:
        return False
    rvnum = ch.get("room")
    trigs = _room_trigs(rvnum)
    if not trigs:
        return False
    for t in trigs:
        if t[0] == "exall" and _atoi(t[2]) == dnum:
            _run_rprog(rvnum, t[1], ch, None, None)
            return True
    return False


def ogreet_trigger(ch):
    """GRALL objprog check when a player arrives (cf. p_greet_trigger
    PRG_OPROG, programs.c:3181).

    The first floor object carrying a GRALL trigger rolls and ends the scan
    (upstream returns whether or not the percent roll passes); failing that,
    the first such carried object of any room person.  "greet" is dead
    vocabulary for objs -- only GRALL fires.
    """
    if not world.OBJPROGS:  # ponytail: no obj progs loaded -> skip the scan
        return
    rvnum = ch.get("room")
    rs = world.rooms._data.get(rvnum)
    if rs is None:
        return
    for o in list(rs.get("items", [])):
        if has_otrigger(o, "grall"):
            opercent_trigger({"obj": o, "room": rvnum, "carrier": None},
                             ch, None, None, "grall")
            return
    for person in list(_persons_at(rvnum)):
        for o in _carried_objs(person):
            if has_otrigger(o, "grall"):
                opercent_trigger({"obj": o, "room": rvnum, "carrier": person},
                                 ch, None, None, "grall")
                return


def rgreet_trigger(ch):
    """GRALL roomprog check when a player arrives (cf. p_greet_trigger
    PRG_RPROG, programs.c:3207)."""
    rvnum = ch.get("room")
    if has_rtrigger(rvnum, "grall"):
        rpercent_trigger(rvnum, ch, None, None, "grall")


def act_trigger_objs_room(argument, ch):
    """One pass of the obj/room TRIG_ACT block (cf. perform_act, comm.c:2049-2072).

    Floor objects, then carried objects, then the room.  Upstream's carried
    sweep starts its person walk AT *ch* (``for (tch = ch; ...)``), covering
    only ch and persons after it in the room list; [PRIMESUD] there is no
    room-list order here, so ch's objects sweep first, then every other
    person's.  *argument* is the UNRENDERED act format string (upstream
    passes ``orig``, $-codes intact).
    """
    rvnum = ch.get("room")
    rs = world.rooms._data.get(rvnum)
    if rs is None:
        return
    for o in list(rs.get("items", [])):
        if has_otrigger(o, "act"):
            oact_trigger(argument, {"obj": o, "room": rvnum, "carrier": None},
                         ch, "act")
    persons = [ch] + [p for p in _persons_at(rvnum) if p is not ch]
    for person in persons:
        for o in _carried_objs(person):
            if has_otrigger(o, "act"):
                oact_trigger(argument,
                             {"obj": o, "room": rvnum, "carrier": person},
                             ch, "act")
    if has_rtrigger(rvnum, "act"):
        ract_trigger(argument, rvnum, ch, "act")


def pulse_obj(obj, rvnum, carrier, random_ok):
    """Random/delay objprog pulse for one located object (cf. obj_update,
    update.c:822-835).

    [PRIMESUD] intent-parity: upstream's trigger block sits behind the
    decay-timer expiry gate (update.c:819), which would fire obj random/delay
    only on the tick an object crumbles -- contradicting the ``obj delay``/
    ``cancel`` command surface and the room analogue (db.c:1380).  Ported as a
    per-tick pulse like the room one; the branch logic inside matches upstream.

    Args:
        obj (dict): Object instance.
        rvnum (int): Room the object (or its carrier) is in.
        carrier (dict or None): Carrying character, if any.
        random_ok (bool): TRIG_RANDOM eligibility -- carried, or on the floor
            of a non-empty (player-occupied) area (cf. update.c:832).

    Returns:
        bool: True if a program ran (the caller re-checks the obj's residence
        before touching it further).
    """
    if not _obj_trigs(obj):  # one template lookup per obj per tick, then out
        return False
    if has_otrigger(obj, "delay") and obj.get("oprog_delay", 0) > 0:
        obj["oprog_delay"] = obj["oprog_delay"] - 1
        if obj["oprog_delay"] <= 0:
            return opercent_trigger(
                {"obj": obj, "room": rvnum, "carrier": carrier},
                None, None, None, "delay")
    elif random_ok and has_otrigger(obj, "random"):
        return opercent_trigger(
            {"obj": obj, "room": rvnum, "carrier": carrier},
            None, None, None, "random")
    return False


def pulse_room(rvnum):
    """Random/delay roomprog pulse for one room (cf. area_update tail,
    db.c:1374-1389).  The caller restricts the sweep to the player's area,
    matching the upstream ``room->area->empty`` skip (single-player: every
    other area is empty).

    Returns:
        bool: True if a program ran.
    """
    if not _room_trigs(rvnum):
        return False
    rs = world.rooms._data.get(rvnum)
    if rs is None:
        return False
    if has_rtrigger(rvnum, "delay") and rs.get("rprog_delay", 0) > 0:
        rs["rprog_delay"] = rs["rprog_delay"] - 1
        if rs["rprog_delay"] <= 0:
            return rpercent_trigger(rvnum, None, None, None, "delay")
    elif has_rtrigger(rvnum, "random"):
        return rpercent_trigger(rvnum, None, None, None, "random")
    return False


# -- $-code expansion (cf. expand_arg_mob, programs.c:1433) --------------------

def _room_of(mob):
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
    "isimmort", "onquest", "hunter",
))
_CHAR_NUM = frozenset((
    "level", "align", "money", "hpcnt", "vnum", "room", "sex",
    "weight", "grpsize", "objval0", "objval1", "objval2", "objval3",
    "objval4",
))
_CHAR_FLAG = frozenset((
    "name", "pos", "act", "affected",
    "plr", "imm", "off", "carries", "wears", "has", "uses", "skill",
    "clan", "race", "class", "objtype",
))

# cf. 1stMud LEVEL_IMMORTAL (defines.h:134, MAX_LEVEL 60 - 8); no trust
# system ported, so level stands in for get_trust
LEVEL_IMMORTAL = 52

# Upstream plr_flags names (tables.c:84) for the PLR_* bits PrimeSUD ports;
# unported names (pk, holylight, can_loot, nosummon, ...) miss the dict and
# evaluate False, like a flag_value NO_FLAG
_PLR_WORD = {
    "automap": PLR_AUTOMAP,
    "autoskill": PLR_AUTOSKILL,  # [PRIMESUD]
    "autoassist": PLR_AUTOASSIST,
    "autoexit": PLR_AUTOEXIT,
    "autoloot": PLR_AUTOLOOT,
    "autosac": PLR_AUTOSAC,
    "autogold": PLR_AUTOGOLD,
    "autosplit": PLR_AUTOSPLIT,
    "autodamage": PLR_AUTODAMAGE,
}


def _count_people_room(mob, iflag):
    """Count characters in the mob's room by class (cf. count_people_room)."""
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
        if iflag == 4 and not is_same_group(mob, c):
            continue
        if can_see(mob, c):
            count += 1
    return count


def _get_order_mob(mob):
    """Index of *mob* among same-vnum NPCs in its room, walk order
    (cf. get_order, programs.c:298: the char branch)."""
    if not mob.get("is_npc"):
        return 0
    i = 0
    for c in _room_persons(mob):
        if c is mob:
            return i
        if c.get("is_npc") and c.get("tpl") == mob.get("tpl"):
            i += 1
    return 0


def _get_order_obj(octx):
    """Index of the origin obj among same-vnum floor objects in its room
    (cf. get_order, programs.c:298: the obj branch).  A carried origin walks
    the carrier's room floor and is never found -> 0, as upstream."""
    obj = octx["obj"]
    rvnum = _octx_room(octx)
    rs = world.rooms._data.get(rvnum) if rvnum is not None else None
    if rs is None:
        return 0
    i = 0
    v = obj_vnum(obj)
    for it in rs.get("items", []):
        if it is obj:
            return i
        if obj_vnum(it) == v:
            i += 1
    return 0


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
    if check.startswith("objval"):
        # cf. CHK_OBJVAL0-4: lval stays 0 without an obj lvalue
        if lval_obj is not None:
            return prog_obj_value(lval_obj, int(check[6]))
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
    if check == "weight":
        return get_carry_weight(lval_char)
    if check == "grpsize":
        # cf. count_people_room(lval_char, ..., 4): visible group members in
        # lval_char's room, excluding lval_char itself
        return _count_people_room(lval_char, 4)
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
        master = world.chars.get(c.get("master"))
        return master is not None and master.get("room") == c.get("room")
    if check == "isactive":
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
    if check == "isimmort":
        # cf. IsImmortal (macro.h:266): get_trust >= LEVEL_IMMORTAL; no trust
        # system ported, so raw level stands in
        return c is not None and c.get("level", 0) >= LEVEL_IMMORTAL
    if check == "onquest":
        return c is not None and is_quester(c)
    if check == "hunter":
        # cf. CHK_HUNTER (lval_char->hunting == mob): dead-wired upstream --
        # hunt.c only ever NULLs ->hunting, nothing sets it -- so the check
        # can never be true; faithfully False
        return False
    return False


def _eval_char_flag(check, word, lval_char, lval_obj, rest=""):
    """Flag/word char if-check (cf. cmd_eval_mob, programs.c:589).

    Flag words match exact dict keys (the same stance as Phase A act/affected:
    no flag_value prefix walk).  *rest* is the remainder after the flag word;
    only the skill check consumes it (its minimum percentage).
    """
    c = lval_char
    if check == "name":
        if lval_obj is not None:
            # instance keywords, falling back to the template (cf. obj->name)
            return is_name(word, _obj_keywords(lval_obj))
        return c is not None and is_name(word, c.get("name", ""))
    if check == "pos":
        return c is not None and c.get("pos") == word
    if check == "act":
        return c is not None and bool(c.get("is_npc")) and bool(c.get("act_flags", {}).get(word))
    if check == "affected":
        return c is not None and bool(c.get("affected_by", {}).get(word))
    if check == "plr":
        # cf. CHK_PLR: player act-field bits; PrimeSUD keeps them in the
        # player-only "flags" bitmask (see handler.py PLR_*)
        bit = _PLR_WORD.get(word)
        return (c is not None and not c.get("is_npc") and bit is not None
                and bool(c.get("flags", 0) & bit))
    if check == "imm":
        return c is not None and bool(c.get("imm_flags", {}).get(word))
    if check == "off":
        return c is not None and bool(c.get("off_flags", {}).get(word))
    if check == "carries":
        # number -> any carried (worn included, cf. has_item); name -> unworn
        # inventory by keyword, self-visibility gated (cf. get_obj_carry)
        if c is None:
            return False
        if _is_number(word):
            v = _atoi(word)
            return any(obj_vnum(o) == v for o in _carried_objs(c))
        return any(is_name(word, _obj_keywords(o)) and _can_see_obj(c, o)
                   for o in c.get("inv", []))
    if check == "wears":
        # number -> worn vnum (cf. has_item fWear); name -> worn by keyword
        # (cf. get_obj_wear; the obj-origin eval skips its can_see_obj gate --
        # self-viewer visibility applied uniformly here)
        if c is None:
            return False
        worn = [o for o in (c.get("equip") or {}).values() if o is not None]
        if _is_number(word):
            v = _atoi(word)
            return any(obj_vnum(o) == v for o in worn)
        return any(is_name(word, _obj_keywords(o)) and _can_see_obj(c, o)
                   for o in worn)
    if check == "has":
        # word is an item-type name in PrimeSUD's type vocabulary (which
        # splits 1stMud's container into corpse types, [PRIMESUD])
        return c is not None and any(_obj_type(o) == word
                                     for o in _carried_objs(c))
    if check == "uses":
        worn = [o for o in ((c or {}).get("equip") or {}).values()
                if o is not None]
        return c is not None and any(_obj_type(o) == word for o in worn)
    if check == "skill":
        # cf. CHK_SKILL: players only; "<skill> <min%>".  Prefix lookup like
        # upstream skill_lookup (multi-word names arrive truncated to one
        # token, e.g. "magic" for magic missile)
        if c is None or c.get("is_npc"):
            return False
        sn = _skill_prefix_lookup(word)
        return sn is not None and get_skill(c, sn) >= _atoi(rest)
    if check == "clan":
        # cf. CHK_CLAN: no clan system ported -- faithfully False
        return False
    if check == "race":
        rd = race_lookup(word)
        return (c is not None and rd is not None
                and race_lookup(c.get("race", "")) is rd)
    if check == "class":
        # cf. CHK_CLASS prime_class(lval_char): NPCs have no classes
        # (prime_class -> -1, never equal to a real class index)
        cl = class_lookup(word)
        return c is not None and cl != -1 and prime_class(c) == cl
    if check == "objtype":
        return (lval_obj is not None and _obj_type(lval_obj) == word)
    return False


def _obj_type(obj):
    """Template item-type word for an obj (instance dict or vnum). [PRIMESUD]"""
    tpl = world.ITEM_DEFS.get(obj_vnum(obj))
    return tpl.get("type", "") if tpl else ""


def _skill_prefix_lookup(word):
    """First skill sn whose name starts with *word*, table order (cf. 1stMud
    skill_lookup's str_prefix walk; magic._skill_lookup is exact-only). [PRIMESUD]"""
    if not word:
        return None
    for sn in sorted(SKILLS):
        if SKILLS[sn].get("name", "").startswith(word):
            return sn
    return None


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

    # -- world presence checks: bare vnum or name (programs.c:448-461) --
    if check == "mobhere":
        if _is_number(buf):
            v = _atoi(buf)
            return any(c.get("is_npc") and c.get("tpl") == v
                       for c in _room_persons(mob))
        return _get_char_room(mob, buf) is not None
    if check == "objhere":
        if _is_number(buf):
            v = _atoi(buf)
            rs = _room_of(mob)
            return any(obj_vnum(it) == v
                       for it in (rs.get("items", []) if rs else []))
        return get_obj_here(mob, buf) is not None
    if check == "mobexists":
        return _get_char_world(mob, buf) is not None
    if check == "objexists":
        return _get_obj_world(mob, buf) is not None

    # -- room population counts: "<check> <op> <n>" --
    if check in _COUNT_FLAG:
        lval = _count_people_room(mob, _COUNT_FLAG[check])
        if len(toks) < 2 or toks[0] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        return num_eval(lval, toks[0], _atoi(toks[1]))
    if check == "order":
        if len(toks) < 2 or toks[0] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        return num_eval(_get_order_mob(mob), toks[0], _atoi(toks[1]))
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
        return _eval_char_flag(check, toks[1], lval_char, lval_obj,
                               toks[2] if len(toks) > 2 else "")

    if check in _CHAR_NUM:
        if len(toks) < 3 or toks[1] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        lval = _char_num_lval(check, lval_char, lval_obj)
        return num_eval(lval, toks[1], _atoi(toks[2]))

    # Unreachable for well-formed KNOWN_CHECKS vocabulary (all checks are
    # implemented as of PROGS_PLAN Phase 3); kept as a guard.
    dbg("prog " + str(prog_vnum) + " check '" + check + "' not ported")
    return False


# -- obj/room origin helpers (NULL-viewer lookups) -----------------------------
#
# Upstream obj/room prog code passes a NULL char to get_char_room /
# get_char_world / get_obj_here / get_random_char / count_people_room: no
# visibility filtering, no self-exclusion.  These variants mirror that.


def _octx_room(octx):
    """Current room vnum of an obj-origin context (carrier's room wins). [PRIMESUD]"""
    c = octx.get("carrier")
    return c.get("room") if c is not None else octx.get("room")


def _origin_state(kind, origin):
    """Dict holding the origin's prog target/delay fields: the obj dict for an
    obj origin, the runtime room state for a room origin. [PRIMESUD]"""
    if kind == "obj":
        return origin["obj"]
    return world.rooms._data.get(origin)


def _char_at(rvnum, arg):
    """Char in room *rvnum* by name, N. counted (cf. get_char_room(NULL, room, arg)):
    no visibility filter, no "self". [PRIMESUD]"""
    if not arg:
        return None
    number, name = number_argument(arg)
    count = 0
    for c in _persons_at(rvnum):
        if not is_name(name, _char_kw(c)):
            continue
        count += 1
        if count == number:
            return c
    return None


def _char_world_nv(arg):
    """Any char in the loaded world by name (cf. get_char_world(NULL, arg)):
    no visibility filter. [PRIMESUD]"""
    if not arg:
        return None
    number, name = number_argument(arg)
    count = 0
    for c in world.chars.values():
        if c.get("room") is None or not is_name(name, _char_kw(c)):
            continue
        count += 1
        if count == number:
            return c
    return None


def _obj_at(rvnum, arg):
    """Obj on room *rvnum*'s floor by name (cf. get_obj_here(NULL, room, arg)):
    floor only, no visibility filter. [PRIMESUD]"""
    if not arg:
        return None
    rs = world.rooms._data.get(rvnum) if rvnum is not None else None
    if rs is None:
        return None
    number, name = number_argument(arg)
    count = 0
    for it in rs.get("items", []):
        if not is_name(name, _obj_keywords(it)):
            continue
        count += 1
        if count == number:
            return it
    return None


def _find_location_nv(arg):
    """find_location with a NULL viewer: numeric room vnum or the name of a
    char anywhere in the loaded world (cf. _find_location). [PRIMESUD]"""
    if _is_number(arg):
        v = _atoi(arg)
        return v if v in world.ROOM_DEFS._data else None
    c = _char_world_nv(arg)
    return c.get("room") if c is not None else None


def _random_char_at(rvnum):
    """Random character in a room for an obj/room prog (cf. get_random_char
    else-branch, programs.c:239): no visibility gate, no self-exclusion."""
    best = None
    highest = 0
    for c in _persons_at(rvnum):
        n = _number_percent()
        if n > highest:
            highest = n
            best = c
    return best


def _count_people_other(rvnum, iflag):
    """count_people_room for an obj/room origin (cf. programs.c:287): only the
    people/players/mobs classes, no visibility filter, no self-skip."""
    count = 0
    for c in _persons_at(rvnum):
        is_npc = bool(c.get("is_npc"))
        if iflag == 1 and is_npc:
            continue
        if iflag == 2 and not is_npc:
            continue
        count += 1
    return count


# -- obj/room if-check evaluation (cf. cmd_eval_obj/_room, programs.c:762/1101)


def _cmd_eval_other(check, line, kind, origin, ch, arg1, arg2, rch, prog_vnum):
    """Evaluate one if-check for an obj/room prog (cf. cmd_eval_obj,
    programs.c:762 and cmd_eval_room, programs.c:1101).

    The two upstream functions are near-identical; *kind* ("obj"/"room")
    covers the differences: $i resolution (the obj itself / a bug for rooms),
    the $q/istarget target holder, the origin room, and the clones/order
    checks.  Checks outside the ported subset return False with a dbg() note,
    as in the mob cmd_eval.

    Args:
        check (str): If-check keyword (guaranteed in KNOWN_CHECKS).
        line (str): Arguments after the keyword.
        kind (str): "obj" or "room".
        origin: Obj context dict or room vnum.
        ch (dict or None): Triggering character.
        arg1: Object argument.
        arg2: Target character or object.
        rch (dict or None): Preselected random char.
        prog_vnum (int): Program vnum, for diagnostics.

    Returns:
        bool: The check result.
    """
    toks = line.split()
    if not toks:
        return False
    st = _origin_state(kind, origin)
    if st is None:
        return False
    rvnum = _octx_room(origin) if kind == "obj" else origin
    tkey = "oprog_target" if kind == "obj" else "rprog_target"
    if st.get(tkey) is None and ch is not None:
        # [PRIMESUD] stored as char id, not a dict ref (see _target_of)
        st[tkey] = ch.get("id")
    buf = toks[0]

    if check == "rand":
        return _number_percent() < _atoi(buf)

    if check == "mobhere":
        if _is_number(buf):
            v = _atoi(buf)
            return any(c.get("is_npc") and c.get("tpl") == v
                       for c in _persons_at(rvnum))
        return _char_at(rvnum, buf) is not None
    if check == "objhere":
        if _is_number(buf):
            v = _atoi(buf)
            rs = world.rooms._data.get(rvnum) if rvnum is not None else None
            return any(obj_vnum(it) == v
                       for it in (rs.get("items", []) if rs else []))
        return _obj_at(rvnum, buf) is not None
    if check == "mobexists":
        return _char_world_nv(buf) is not None
    if check == "objexists":
        return _get_obj_world(None, buf) is not None

    if check in _COUNT_FLAG:
        if check == "clones":
            # cf. cmd_eval_obj/_room "received CHK_CLONES" bug -> false
            dbg("prog " + str(prog_vnum) + " clones check in " + kind + "prog")
            return False
        lval = _count_people_other(rvnum, _COUNT_FLAG[check])
        if len(toks) < 2 or toks[0] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        return num_eval(lval, toks[0], _atoi(toks[1]))
    if check == "order":
        if kind == "room":
            # cf. cmd_eval_room "received CHK_ORDER." bug -> false
            dbg("prog " + str(prog_vnum) + " order check in roomprog")
            return False
        if len(toks) < 2 or toks[0] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        return num_eval(_get_order_obj(origin), toks[0], _atoi(toks[1]))
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
    lval_char = None
    lval_obj = None
    if code == "i":
        if kind == "obj":
            lval_obj = origin["obj"]
        else:
            # cf. cmd_eval_room "received code case 'i'." -> both lvals NULL
            dbg("prog " + str(prog_vnum) + " $i in roomprog")
            return False
    elif code == "n":
        lval_char = ch
    elif code == "t":
        lval_char = arg2 if isinstance(arg2, dict) else None
    elif code == "r":
        lval_char = rch if rch is not None else _random_char_at(rvnum)
    elif code == "o":
        lval_obj = arg1
    elif code == "p":
        lval_obj = arg2 if not isinstance(arg2, dict) else None
    elif code == "q":
        tid = st.get(tkey)
        lval_char = world.chars.get(tid) if tid is not None else None
    else:
        dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
        return False
    if lval_char is None and lval_obj is None:
        return False

    if check == "isvisible":
        # upstream cmd_eval_obj/_room have no CHK_ISVISIBLE case; the keyword
        # falls through to the numeric section and bugs out false
        dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
        return False
    if check in _CHAR_BOOL:
        # istarget reads mob.get("mprog_target"); shim the origin's target in
        return _eval_char_bool(check, code, lval_char, lval_obj,
                               {"mprog_target": st.get(tkey)})

    if check == "hunter":
        # absent from cmd_eval_obj/_room: the keyword falls through their
        # switches to the numeric section and bugs out false
        dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
        return False
    if check in _CHAR_FLAG:
        if len(toks) < 2:
            return False
        return _eval_char_flag(check, toks[1], lval_char, lval_obj,
                               toks[2] if len(toks) > 2 else "")

    if check in _CHAR_NUM:
        if len(toks) < 3 or toks[1] not in _EVAL_OPS:
            dbg("prog " + str(prog_vnum) + " syntax error '" + line + "'")
            return False
        if check == "room" and lval_char is None and lval_obj is not None:
            # upstream reads lval_obj->in_room/carried_by; PrimeSUD objects
            # have no location back-pointer, so only the prog's own obj ($i)
            # is resolvable -- other obj args compare as 0
            lval = rvnum if (kind == "obj" and lval_obj is origin["obj"]
                             and rvnum is not None) else 0
        else:
            lval = _char_num_lval(check, lval_char, lval_obj)
        return num_eval(lval, toks[1], _atoi(toks[2]))

    # Unreachable for well-formed KNOWN_CHECKS vocabulary (all checks are
    # implemented as of PROGS_PLAN Phase 3); kept as a guard.
    dbg("prog " + str(prog_vnum) + " check '" + check + "' not ported")
    return False


# -- obj/room $-code expansion (cf. expand_arg_other, programs.c:1664) ---------


def expand_arg_other(fmt, kind, origin, ch, arg1, arg2, rch):
    """Expand $-codes for an obj/room prog (cf. expand_arg_other, programs.c:1664).

    Differences from the mob expand_arg, all upstream-faithful: no visibility
    gating (there is no viewing mob), $j/$k/$l are invalid (the origin has no
    sex), $q/$Q/$X/$Y/$Z read the origin's oprog/rprog target, $o/$O/$p/$P
    have no can_see_obj gate, and $J does not lazily pick a random char (only
    $r/$R/$K/$L do).

    [PRIMESUD] $R renders the random char; upstream reads ``ch`` -- the same
    copy-paste slip as expand_arg_mob's $R (see docs/FIXES.md "mobprog: $R").

    Args:
        fmt (str): Format string.
        kind (str): "obj" or "room".
        origin: Obj context dict or room vnum.
        ch (dict or None): Triggering character.
        arg1: Object argument.
        arg2: Target character or object.
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
    o = origin["obj"] if kind == "obj" else None
    rvnum = _octx_room(origin) if kind == "obj" else origin
    st = _origin_state(kind, origin)
    tid = st.get("oprog_target" if kind == "obj" else "rprog_target") if st else None
    tgt = world.chars.get(tid) if tid is not None else None

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
            if o is not None:
                piece = _obj_name(o)
            else:
                dbg("expand_arg_other: room had an 'i' case")
                piece = "<@@@>"
        elif code == "I":
            if o is not None:
                piece = _obj_short(o)
            else:
                dbg("expand_arg_other: room had an 'I' case")
                piece = "<@@@>"
        elif code == "n":
            piece = _cap(_first(ch.get("name", ""))) if ch is not None else someone
        elif code == "N":
            piece = _char_short(ch) if ch is not None else someone
        elif code == "t":
            piece = _cap(_first(vch.get("name", ""))) if vch is not None else someone
        elif code == "T":
            piece = _char_short(vch) if vch is not None else someone
        elif code == "r":
            if rch is None:
                rch = _random_char_at(rvnum)
            piece = _cap(_first(rch.get("name", ""))) if rch is not None else someone
        elif code == "R":
            if rch is None:
                rch = _random_char_at(rvnum)
            piece = _char_short(rch) if rch is not None else someone
        elif code == "q":
            piece = _cap(_first(tgt.get("name", ""))) if tgt is not None else someone
        elif code == "Q":
            piece = _char_short(tgt) if tgt is not None else someone
        elif code in ("j", "k", "l"):
            # cf. expand_arg_other cases 'j'/'k'/'l': origin has no pronouns
            dbg("expand_arg_other: received case '" + code + "'")
            piece = "<@@@>"
        elif code == "e":
            piece = sex_of(ch, _HE_SHE, "it") if ch is not None else someone
        elif code == "E":
            piece = sex_of(vch, _HE_SHE, "it") if vch is not None else someone
        elif code == "J":
            # no lazy random pick here, per upstream (only $r/$R/$K/$L pick)
            piece = sex_of(rch, _HE_SHE, "it") if rch is not None else someone
        elif code == "X":
            piece = sex_of(tgt, _HE_SHE, "it") if tgt is not None else someone
        elif code == "m":
            piece = sex_of(ch, _HIM_HER, "it") if ch is not None else someone
        elif code == "M":
            piece = sex_of(vch, _HIM_HER, "it") if vch is not None else someone
        elif code == "K":
            if rch is None:
                rch = _random_char_at(rvnum)
            piece = sex_of(rch, _HIM_HER, "it") if rch is not None else someone
        elif code == "Y":
            piece = sex_of(tgt, _HIM_HER, "it") if tgt is not None else someone
        elif code == "s":
            piece = sex_of(ch, _HIS_HER, "its") if ch is not None else someones
        elif code == "S":
            piece = sex_of(vch, _HIS_HER, "its") if vch is not None else someones
        elif code == "L":
            if rch is None:
                rch = _random_char_at(rvnum)
            piece = sex_of(rch, _HIS_HER, "its") if rch is not None else someones
        elif code == "Z":
            piece = sex_of(tgt, _HIS_HER, "its") if tgt is not None else someones
        elif code == "o":
            piece = _obj_name(obj1) if obj1 is not None else something
        elif code == "O":
            piece = _obj_short(obj1) if obj1 is not None else something
        elif code == "p":
            piece = _obj_name(obj2) if obj2 is not None else something
        elif code == "P":
            piece = _obj_short(obj2) if obj2 is not None else something
        else:
            dbg("expand_arg_other: bad code '" + code + "'")
            piece = "<@@@>"
        out.append(piece)
    return "".join(out)


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


def _buggy(prog_vnum, kind, ovnum, msg):
    """Report a malformed program and abort it (cf. buggy_prog, programs.c)."""
    dbg("mobprog: " + msg + ", " + str(kind) + " " + str(ovnum)
        + " prog " + str(prog_vnum))


def _dispatch(prog_vnum, mob, ctrl, expanded, call_level=0, obj=None, room=None):
    """Route an expanded command line (cf. program_flow tail, programs.c:2793).

    ``mob``/``obj``/``room`` keyword lines dispatch to the matching command
    table only when the program's origin matches; a mismatch is a bug() skip,
    as is a raw command line in a non-MOBprog.
    """
    if ctrl == "mob":
        # strip the leading "mob" token; dispatch the rest to the mp-command set
        parts = expanded.split(None, 1)
        rest = parts[1] if len(parts) > 1 else ""
        if mob is None:
            dbg("prog " + str(prog_vnum) + " mob command in non MOBprog")
            return
        mob_interpret(mob, rest, prog_vnum, call_level)
        return
    if ctrl == "obj":
        parts = expanded.split(None, 1)
        rest = parts[1] if len(parts) > 1 else ""
        if obj is None:
            dbg("prog " + str(prog_vnum) + " obj command in non OBJprog")
            return
        obj_interpret(obj, rest, prog_vnum)
        return
    if ctrl == "room":
        parts = expanded.split(None, 1)
        rest = parts[1] if len(parts) > 1 else ""
        if room is None:
            dbg("prog " + str(prog_vnum) + " room command in non ROOMprog")
            return
        room_interpret(room, rest, prog_vnum)
        return
    if mob is None:
        dbg("prog " + str(prog_vnum) + " normal mud command in non-MOBprog")
        return
    interpret(expanded, mob)


def program_flow(prog_vnum, code, mob, ch, arg1=None, arg2=None, call_level=0,
                 obj=None, room=None):
    """Run one program (cf. program_flow, programs.c:2495).

    Iterative line loop over a fixed state/cond stack.  Control keywords
    (if/or/and/else/endif, ``*`` comment, break/end) drive the stack; any other
    line is $-expanded then dispatched (``mob``/``obj``/``room`` <subcmd> ->
    the matching command table, else through the real interpreter as the mob;
    raw commands in non-mobprogs bug-skip).  A malformed program aborts via
    dbg(), as in 1stMud's buggy_prog.

    Args:
        prog_vnum (int): Program vnum (for diagnostics).
        code (str): The program source lines.
        mob (dict or None): The acting mob instance (mob origin).
        ch (dict or None): Triggering character.
        arg1: Object argument.
        arg2: Target character or object.
        call_level (int): Unused legacy parameter; depth is tracked by the
            module-global counter below.
        obj (dict or None): Obj-origin context {"obj", "room", "carrier"}.
        room (int or None): Room-origin vnum.

    Exactly one of mob/obj/room must be non-None.
    """
    # cf. programs.c:2452 (++call_level > MAX_CALL_LEVEL): the counter is
    # GLOBAL, bumped on every program_flow entry -- it bounds not just "mob
    # call" nesting but any reentrant trigger cascade (a prog's kill firing
    # another mob's fight/death prog, act triggers, ...).  Critical on the
    # HP Prime's small stack.
    global _call_depth
    if _call_depth >= MAX_CALL_LEVEL:
        dbg("prog " + str(prog_vnum) + " exceeded max call level")
        return
    origins = (mob is not None) + (obj is not None) + (room is not None)
    if origins != 1:
        # cf. p_act_trigger "Multiple program types" bug guard
        dbg("prog " + str(prog_vnum) + " has " + str(origins)
            + " origins (need exactly 1)")
        return
    if mob is not None:
        kind, ovnum = "mob", mob.get("tpl", 0)
    elif obj is not None:
        kind, ovnum = "obj", obj_vnum(obj["obj"])
    else:
        kind, ovnum = "room", room
    state = [IN_BLOCK] * MAX_NESTED_LEVEL
    cond = [True] * MAX_NESTED_LEVEL
    level = 0

    _call_depth += 1
    try:
        _run_flow(prog_vnum, code, mob, ch, arg1, arg2,
                  kind, ovnum, obj, room, state, cond, level)
    finally:
        _call_depth -= 1


def _run_flow(prog_vnum, code, mob, ch, arg1, arg2, kind, ovnum, obj, room,
              state, cond, level):
    """program_flow body, split out so the depth counter always unwinds. [PRIMESUD]"""

    def _eval(checkname, rest):
        if mob is not None:
            return cmd_eval(checkname, rest, mob, ch, arg1, arg2, None, prog_vnum)
        origin = obj if kind == "obj" else room
        return _cmd_eval_other(checkname, rest, kind, origin, ch, arg1, arg2,
                               None, prog_vnum)

    for raw in code.split("\n"):
        buf, ctrl, data = _parse_line(raw)
        if buf == "":            # NullStr(buf) -> end of program
            break
        if buf[0] == "*":        # comment line
            continue

        if ctrl == "if":
            if state[level] == BEGIN_BLOCK:
                _buggy(prog_vnum, kind, ovnum, "misplaced if statement")
                return
            state[level] = BEGIN_BLOCK
            level += 1
            if level >= MAX_NESTED_LEVEL:
                _buggy(prog_vnum, kind, ovnum, "Max nested level exceeded")
                return
            if cond[level - 1] is False:
                cond[level] = False
                continue
            checkname, rest = _split_first(data)
            if checkname in KNOWN_CHECKS:
                cond[level] = _eval(checkname, rest)
            else:
                _buggy(prog_vnum, kind, ovnum, "invalid if_check (if)")
                return
            state[level] = END_BLOCK

        elif ctrl == "or":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, kind, ovnum, "or without if")
                return
            if cond[level - 1] is False:
                continue
            checkname, rest = _split_first(data)
            if checkname in KNOWN_CHECKS:
                ev = _eval(checkname, rest)
            else:
                _buggy(prog_vnum, kind, ovnum, "invalid if_check (or)")
                return
            if ev:
                cond[level] = True

        elif ctrl == "and":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, kind, ovnum, "and without if")
                return
            if cond[level - 1] is False:
                continue
            checkname, rest = _split_first(data)
            if checkname in KNOWN_CHECKS:
                ev = _eval(checkname, rest)
            else:
                _buggy(prog_vnum, kind, ovnum, "invalid if_check (and)")
                return
            cond[level] = bool(cond[level]) and bool(ev)

        elif ctrl == "endif":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, kind, ovnum, "endif without if")
                return
            cond[level] = True
            state[level] = IN_BLOCK
            level -= 1
            state[level] = END_BLOCK

        elif ctrl == "else":
            if level == 0 or state[level - 1] != BEGIN_BLOCK:
                _buggy(prog_vnum, kind, ovnum, "else without if")
                return
            if cond[level - 1] is False:
                continue
            state[level] = IN_BLOCK
            cond[level] = not cond[level]

        elif cond[level] is True and (ctrl == "break" or ctrl == "end"):
            return

        elif (level == 0 or cond[level] is True):
            state[level] = IN_BLOCK
            if mob is not None:
                expanded = expand_arg(buf, mob, ch, arg1, arg2, None)
                # mob-origin call keeps the legacy 4-arg shape
                _dispatch(prog_vnum, mob, ctrl, expanded)
            else:
                origin = obj if kind == "obj" else room
                expanded = expand_arg_other(buf, kind, origin, ch, arg1, arg2, None)
                _dispatch(prog_vnum, None, ctrl, expanded, 0, obj, room)


# -- mp-command set (cf. prog_cmds.c mob_cmd_table) ----------------------------
#
# Every function takes (mob, args, prog_vnum, call_level); *args* is the
# already-$-expanded remainder of the line (program_flow expands the whole line
# before dispatch, so command args are literal text -- there are no $-codes left
# to re-expand).  Most map onto existing PrimeSUD helpers; imports are lazy to
# avoid a circular import (combat/magic/movement all reach back into mobprog).


def _persons_at(rvnum):
    """Player + all mobs in room *rvnum* (cf. room->person_first walk). [PRIMESUD]"""
    rs = world.rooms._data.get(rvnum) if rvnum is not None else None
    if rs is None:
        return []
    persons = []
    p = world.chars.get(1)
    if p is not None and p.get("room") == rvnum:
        persons.append(p)
    for mid in rs.get("mobs", []):
        c = world.chars.get(mid)
        if c is not None:
            persons.append(c)
    return persons


def _room_persons(mob):
    """Player + all mobs in *mob*'s room (cf. in_room->person_first walk). [PRIMESUD]"""
    return _persons_at(mob.get("room")) if mob is not None else []


def _char_kw(c):
    """Name-match keywords for a char (mob keywords / player name). [PRIMESUD]"""
    if c.get("is_npc"):
        tpl = world.MOB_DEFS._data.get(c.get("tpl"))
        return c.get("keywords") or (tpl.get("keywords", "") if tpl else "")
    return c.get("name", "")


def _get_char_room(mob, arg):
    """Find a visible char in *mob*'s room by name; "self" and N. counted
    syntax (cf. get_char_room, handler.c:1886). [PRIMESUD]"""
    if not arg:
        return None
    number, name = number_argument(arg)
    if name == "self":
        return mob
    count = 0
    for c in _room_persons(mob):
        if not can_see(mob, c) or not is_name(name, _char_kw(c)):
            continue
        count += 1
        if count == number:
            return c
    return None


def _get_char_world(mob, arg):
    """Find any visible char, own room first then the loaded world
    (cf. get_char_world, handler.c:1920). [PRIMESUD]"""
    if not arg:
        return None
    c = _get_char_room(mob, arg)
    if c is not None:
        return c
    number, name = number_argument(arg)
    count = 0
    for c in world.chars.values():
        if (c.get("room") is None or not can_see(mob, c)
                or not is_name(name, _char_kw(c))):
            continue
        count += 1
        if count == number:
            return c
    return None


def _get_obj_world(mob, arg):
    """Find any visible obj, nearby first then the loaded world
    (cf. get_obj_world, handler.c:2104). [PRIMESUD]

    There is no global object list; scans loaded rooms' floors (one container
    level deep, like the reset count map) plus every char's inventory and
    equipment.  Unloaded areas hold no instances, matching lazy loading.
    A None *mob* means a NULL viewer (cf. get_obj_world(NULL, ...) in the
    obj/room prog paths): no here-first pass, no visibility filter.
    """
    if not arg:
        return None
    obj = get_obj_here(mob, arg) if mob is not None else None
    if obj is not None:
        return obj

    def _kw(it):
        tpl = world.ITEM_DEFS._data.get(obj_vnum(it))
        kw = it.get("keywords") if isinstance(it, dict) else None
        return kw or (tpl.get("keywords", "") if tpl else "")

    def _all_objs():
        for rs in world.rooms._data.values():
            for it in rs.get("items", []):
                yield it
                if isinstance(it, dict):
                    for sub in it.get("contents", []):
                        yield sub
        for c in world.chars.values():
            for it in c.get("inv", []):
                yield it
                if isinstance(it, dict):
                    for sub in it.get("contents", []):
                        yield sub
            for it in (c.get("equip") or {}).values():
                if it is not None:
                    yield it

    number, name = number_argument(arg)
    count = 0
    for it in _all_objs():
        if not is_name(name, _kw(it)) or (mob is not None
                                          and not can_see_obj(mob, it)):
            continue
        count += 1
        if count == number:
            return it
    return None


def _char_from_room(ch):
    """Detach a char from its room; NPCs leave the room mob-list. [PRIMESUD]"""
    if ch.get("is_npc"):
        rs = world.rooms._data.get(ch.get("room"))
        if rs is not None and ch["id"] in rs["mobs"]:
            rs["mobs"].remove(ch["id"])


def _char_to_room(ch, room_vnum):
    """Place a char into a room; NPCs join the room mob-list. [PRIMESUD]"""
    ch["room"] = room_vnum
    if ch.get("is_npc"):
        rs = world.rooms.get(room_vnum)
        if rs is None:
            rs = {"items": [], "mobs": []}
            world.rooms[room_vnum] = rs
        if ch["id"] not in rs["mobs"]:
            rs["mobs"].append(ch["id"])


def _find_location(mob, arg):
    """Resolve a location arg to a room vnum (cf. find_location, act_wiz.c:721). [PRIMESUD]

    Accepts a numeric room vnum (must be a known/resident room) or the name of
    a char anywhere in the loaded world (returns that char's room).  1stMud's
    area-name and world-object fallbacks are not ported; stock progs use vnums.
    """
    if _is_number(arg):
        v = _atoi(arg)
        return v if v in world.ROOM_DEFS._data else None
    c = _get_char_world(mob, arg)
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
    p = world.chars.get(1)
    if p is not None:
        chprintln(p, args)


def _mp_zecho(mob, args, pv, cl):
    """Zone echo (cf. do_mpzecho).  [PRIMESUD] to the player if in the mob's area."""
    if not args:
        return
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
    was = mob.get("room")
    in_room = world.ROOM_DEFS._data.get(was)
    if in_room is None:
        return
    # cf. do_mpasound: MOBtrigger off so the relayed sound does not fire act
    # triggers in the adjacent rooms.
    global MOBtrigger
    saved = MOBtrigger
    MOBtrigger = False
    try:
        for _d, ev in in_room.get("exits", {}).items():
            dest = ev.get("to") if isinstance(ev, dict) else ev
            if dest is None or dest == was:
                continue
            mob["room"] = dest
            act(args, mob, None, None, TO_ROOM)
    finally:
        mob["room"] = was
        MOBtrigger = saved


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
    target = world.chars.get(victim["fighting"])
    if target is None:
        return
    multi_hit(mob, target)


def _parse_damage_args(parts, label):
    """target/min/max/kill parse shared by the mp/op/rp damage commands. [PRIMESUD]

    Returns:
        tuple or None: (target, low, high, fkill), or None on bad syntax.
    """
    if not parts:
        dbg(label + " bad syntax")
        return None
    minv = parts[1] if len(parts) > 1 else ""
    maxv = parts[2] if len(parts) > 2 else ""
    if not _is_number(minv) or not _is_number(maxv):
        dbg(label + " bad range")
        return None
    low, high = _atoi(minv), _atoi(maxv)
    if high < low:
        high = low   # [PRIMESUD] clamp; 1stMud passes low>high to number_range unchecked
    fkill = len(parts) > 3 and bool(parts[3])
    return parts[0], low, high, fkill


def _prog_damage(v, low, high, fkill):
    """One prog damage hit (the mp/op/rp damage tail). [PRIMESUD]

    attacker == victim -> no retaliation / no TRIG_KILL (cf. do_mpdamage:
    damage(victim, victim, ...); victim != ch is false).
    """
    amt = randint(low, high)
    if not fkill:
        amt = min(v.get("hit", 0), amt)
    damage(v, v, amt, TYPE_UNDEFINED, DAM_NONE, False)


def _mp_damage(mob, args, pv, cl):
    parsed = _parse_damage_args(args.split(), "mobprog: mpdamage")
    if parsed is None:
        return
    target, low, high, fkill = parsed
    if target == "all":
        for c in list(_room_persons(mob)):
            if c is not mob:
                _prog_damage(c, low, high, fkill)
    else:
        v = _get_char_room(mob, target)
        if v is None:
            return
        _prog_damage(v, low, high, fkill)


def _mp_cast(mob, args, pv, cl):
    parts = args.split()
    spell = parts[0] if parts else ""
    target_name = parts[1] if len(parts) > 1 else ""
    if not spell:
        dbg("mobprog: mpcast bad syntax")
        return
    sn = _skill_lookup(spell)
    if sn is None:
        dbg("mobprog: mpcast no such spell '" + spell + "'")
        return
    sk = SKILLS.get(sn)
    if sk is None:
        return
    vch = _get_char_room(mob, target_name) if target_name else None
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


def _peace_room(rvnum):
    """Stop all fights and clear aggression in a room (the mp/op/rp peace
    tail). [PRIMESUD]"""
    for c in list(_persons_at(rvnum)):
        if c.get("fighting") is not None:
            stop_fighting(c, both=True)
        if c.get("is_npc") and c.get("act_flags", {}).get("aggressive"):
            c["act_flags"]["aggressive"] = False


def _mp_peace(mob, args, pv, cl):
    _peace_room(mob.get("room"))


def _mp_flee(mob, args, pv, cl):
    if mob.get("fighting") is not None:
        return
    was = mob.get("room")
    in_room = world.ROOM_DEFS._data.get(was)
    if in_room is None:
        return
    exits = in_room.get("exits", {})
    order = list(exits.keys())
    for i in range(len(order) - 1, 0, -1):    # Fisher-Yates (cf. number_door attempts)
        j = randint(0, i)
        order[i], order[j] = order[j], order[i]
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

def _spawn_mob_at(vnum, rvnum):
    """Create a mob instance in room *rvnum* (the mp/op/rp mload tail). [PRIMESUD]"""
    victim = create_mobile(vnum)
    victim["room"] = rvnum
    victim["home_area"] = world.ROOM_DEFS[rvnum].get("area")
    nid = max(world.chars, default=1) + 1
    victim["id"] = nid
    world.chars[nid] = victim
    world.rooms[rvnum]["mobs"].append(nid)
    return victim


def _mp_mload(mob, args, pv, cl):
    arg = _first(args)
    if not arg or not _is_number(arg):
        return
    vnum = _atoi(arg)
    if vnum not in world.MOB_DEFS:
        dbg("mobprog: mpmload bad mob " + str(vnum))
        return
    _spawn_mob_at(vnum, mob.get("room"))


def _mp_oload(mob, args, pv, cl):
    parts = args.split()
    if not parts or not _is_number(parts[0]):
        dbg("mobprog: mpoload bad syntax")
        return
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
    obj = create_object(vnum)
    to_room = arg3[:1] in ("R", "r")
    to_wear = arg3[:1] in ("W", "w")
    can_take = "take" in item_wear_flags(obj, world.ITEM_DEFS[vnum])
    if (to_wear or not to_room) and can_take:
        mob["inv"].append(obj)
        if to_wear:
            wear_obj(mob, obj, True)
    else:
        world.rooms[mob["room"]]["items"].append(obj)


def _mp_purge(mob, args, pv, cl):
    rs = _room_of(mob)
    arg = _first(args)
    if not arg:
        if rs is None:
            return
        for mid in list(rs.get("mobs", [])):
            v = world.chars.get(mid)
            if (v is not None and v is not mob and v.get("is_npc")
                    and not v.get("act_flags", {}).get("nopurge")):
                _extract_char(v, pull=True)
        rs["items"] = [o for o in rs.get("items", []) if _obj_has_nopurge(o)]
        return
    victim = _get_char_room(mob, arg)
    if victim is None:
        obj = get_obj_here(mob, arg)
        if obj is not None:
            _detach_obj(mob, obj)
        else:
            dbg("mobprog: mppurge bad arg, mob " + str(mob.get("tpl", 0)))
        return
    if not victim.get("is_npc"):
        dbg("mobprog: mppurge PC, mob " + str(mob.get("tpl", 0)))
        return
    _extract_char(victim, pull=True)


def _mp_junk(mob, args, pv, cl):
    arg = _first(args)
    if not arg:
        return
    al = arg.lower()
    if al != "all" and not al.startswith("all."):
        # cf. 1stMud do_mpjunk single-item path gates on the mob's own sight
        # (get_obj_wear ch/true + get_obj_carry ch/ch, prog_cmds.c:344-350)
        for slot, o in list(mob.get("equip", {}).items()):
            if o is not None and _can_see_obj(mob, o) and is_name(arg, _obj_keywords(o)):
                mob["equip"][slot] = None
                return
        o = get_obj_list(arg, mob.get("inv", []), world.ITEM_DEFS, mob)
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
    obj = get_obj_here(mob, parts[0])
    if obj is None:
        return
    _detach_obj(mob, obj)
    world.rooms[loc]["items"].append(obj)


def _remove_objs(victim, spec, label):
    """Strip and extract objects from a char by vnum or ``all`` (the mp/op/rp
    remove tail). [PRIMESUD]"""
    fall = (spec == "all")
    if not fall and not _is_number(spec):
        dbg(label)
        return
    vnum = _atoi(spec) if _is_number(spec) else 0
    for o in list(victim.get("inv", [])):
        if fall or obj_vnum(o) == vnum:
            victim["inv"].remove(o)
    for slot, o in list(victim.get("equip", {}).items()):
        if o is not None and (fall or obj_vnum(o) == vnum):
            victim["equip"][slot] = None


def _mp_remove(mob, args, pv, cl):
    parts = args.split()
    if not parts:
        return
    victim = _get_char_room(mob, parts[0])
    if victim is None:
        return
    _remove_objs(victim, parts[1] if len(parts) > 1 else "",
                 "mobprog: mpremove invalid object, mob " + str(mob.get("tpl", 0)))


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
    original = mob.get("room")
    _char_from_room(mob)
    _char_to_room(mob, loc)
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
    _transfer_char_to(victim, loc)


def _transfer_char_to(victim, loc):
    """The mp/op/rp transfer tail: stop fighting, move, look + the three greet
    passes for a player (cf. prog_cmds.c:697-707). [PRIMESUD]"""
    if victim.get("fighting") is not None:
        stop_fighting(victim, both=True)
    _char_from_room(victim)
    _char_to_room(victim, loc)
    if not victim.get("is_npc"):
        do_look(victim, [])
        greet_trigger(victim)
        ogreet_trigger(victim)
        rgreet_trigger(victim)


def _mp_force(mob, args, pv, cl):
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("mobprog: mpforce bad syntax")
        return
    arg, rest = parts[0], parts[1]
    if arg == "all":
        # [PRIMESUD] 1stMud also filters get_trust(vch) < get_trust(ch); no trust
        # system ported, so a prog can force the player (the intended use).
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
    prog_vnum = _atoi(parts[0])
    code = world.MOBPROGS.get(prog_vnum)
    if code is None:
        dbg("mobprog: mpcall invalid prog " + str(prog_vnum))
        return
    vch = _get_char_room(mob, parts[1]) if len(parts) > 1 and parts[1] else None
    obj1 = get_obj_here(mob, parts[2]) if len(parts) > 2 and parts[2] else None
    obj2 = get_obj_here(mob, parts[3]) if len(parts) > 3 and parts[3] else None
    # nested program_flow entry bumps the global _call_depth itself
    program_flow(prog_vnum, code, mob, vch, obj1, obj2)


def _mp_gtransfer(mob, args, pv, cl):
    """Transfer a char's whole group (cf. do_mpgtransfer, prog_cmds.c:711).

    ``gtransfer <who> [location]``: every room person grouped with *who*
    (who included) is re-dispatched through mptransfer by name, as upstream.
    """
    parts = args.split()
    if not parts:
        dbg("mobprog: mpgtransfer bad syntax")
        return
    who = _get_char_room(mob, parts[0])
    if who is None:
        return
    arg2 = parts[1] if len(parts) > 1 else ""
    for victim in list(_room_persons(mob)):
        if is_same_group(who, victim):
            _mp_transfer(mob, _first(_char_kw(victim))
                         + ((" " + arg2) if arg2 else ""), pv, cl)


def _mp_gforce(mob, args, pv, cl):
    """Force a char's whole group to act (cf. do_mpgforce, prog_cmds.c:743).

    ``gforce <who> <command>``; the mob cannot gforce itself.
    """
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("mobprog: mpgforce bad syntax")
        return
    victim = _get_char_room(mob, parts[0])
    if victim is None or victim is mob:
        return
    for vch in list(_persons_at(victim.get("room"))):
        if is_same_group(victim, vch):
            interpret(parts[1], vch)


def _mp_vforce(mob, args, pv, cl):
    """Force every non-fighting NPC of a vnum, worldwide (cf. do_mpvforce,
    prog_cmds.c:775).  ``vforce <vnum> <command>``; the mob itself is skipped."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("mobprog: mpvforce bad syntax")
        return
    if not _is_number(parts[0]):
        dbg("mobprog: mpvforce non-number arg")
        return
    v = _atoi(parts[0])
    for victim in list(world.chars.values()):
        if (victim.get("is_npc") and victim.get("tpl") == v
                and victim is not mob and victim.get("fighting") is None):
            interpret(parts[1], victim)


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
    ("gtransfer", _mp_gtransfer),
    ("otransfer", _mp_otransfer),
    ("force", _mp_force),
    ("gforce", _mp_gforce),
    ("vforce", _mp_vforce),
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


# -- op-command set (cf. prog_cmds.c obj_cmd_table) ----------------------------
#
# Every function takes (octx, args, pv); *octx* is the obj-origin context dict
# {"obj", "room", "carrier"} (see program_flow), *args* the already-$-expanded
# remainder of the line.  Upstream lookups here pass a NULL viewer -- the _at/
# _nv helpers above mirror that (no visibility filtering).


def _obj_level(obj):
    """Object level, instance override then template (cf. obj->level). [PRIMESUD]"""
    if isinstance(obj, dict) and "level" in obj:
        return obj["level"]
    tpl = world.ITEM_DEFS.get(obj_vnum(obj))
    return tpl.get("level", 0) if tpl else 0


def _echo_actor(rvnum, carrier=None):
    """Carrier, else first person in the room -- the actor upstream hangs an
    actor-less obj/room act() on (cf. do_opecho/do_rpecho). [PRIMESUD]"""
    if carrier is not None:
        return carrier
    persons = _persons_at(rvnum)
    return persons[0] if persons else None


def _octx_detach(octx):
    """Remove the origin obj from its floor spot or carrier. [PRIMESUD]"""
    o = octx["obj"]
    c = octx.get("carrier")
    if c is not None:
        if o in c.get("inv", []):
            c["inv"].remove(o)
        else:
            for slot, it in list(c.get("equip", {}).items()):
                if it is o:
                    c["equip"][slot] = None
    else:
        rs = world.rooms._data.get(octx.get("room"))
        if rs is not None and o in rs.get("items", []):
            rs["items"].remove(o)


def _op_gecho(octx, args, pv):
    """Global echo (cf. do_opgecho).  [PRIMESUD] single-player: to the one player."""
    if not args:
        dbg("objprog: opgecho missing argument")
        return
    p = world.chars.get(1)
    if p is not None:
        chprintln(p, args)


def _op_zecho(octx, args, pv):
    """Zone echo (cf. do_opzecho).  [PRIMESUD] to the player if in the obj's area."""
    if not args:
        dbg("objprog: opzecho missing argument")
        return
    rvnum = _octx_room(octx)
    p = world.chars.get(1)
    if rvnum is None or p is None:
        return
    proom = world.ROOM_DEFS._data.get(p.get("room"))
    oroom = world.ROOM_DEFS._data.get(rvnum)
    if proom is not None and oroom is not None and proom.get("area") == oroom.get("area"):
        chprintln(p, args)


def _op_echo(octx, args, pv):
    """Room echo from an object (cf. do_opecho): everyone in the room sees it."""
    if not args:
        return
    actor = _echo_actor(_octx_room(octx), octx.get("carrier"))
    if actor is None:
        return
    act(args, actor, None, None, TO_ROOM)
    act(args, actor, None, None, TO_CHAR)


def _op_echoaround(octx, args, pv):
    """Echo to everyone but one char (cf. do_opechoaround: raw chprint per
    non-victim, not act())."""
    parts = args.split(None, 1)
    if not parts:
        return
    rvnum = _octx_room(octx)
    victim = _char_at(rvnum, parts[0])
    if victim is None:
        return
    msg = parts[1] if len(parts) > 1 else ""
    for c in _persons_at(rvnum):
        if c is not victim:
            chprintln(c, msg)


def _op_echoat(octx, args, pv):
    """Echo to one char (cf. do_opechoat)."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        return
    rvnum = _octx_room(octx)
    victim = _char_at(rvnum, parts[0])
    if victim is None:
        return
    actor = _echo_actor(rvnum, octx.get("carrier"))
    if actor is None:
        return
    act(parts[1], actor, octx["obj"], victim, TO_VICT)


def _op_mload(octx, args, pv):
    """Load a mob into the obj's room (cf. do_opmload)."""
    arg = _first(args)
    rvnum = _octx_room(octx)
    if rvnum is None or not arg or not _is_number(arg):
        return
    vnum = _atoi(arg)
    if vnum not in world.MOB_DEFS:
        dbg("objprog: opmload bad mob " + str(vnum))
        return
    _spawn_mob_at(vnum, rvnum)


def _op_oload(octx, args, pv):
    """Load an obj onto the obj's room floor (cf. do_opoload).

    The optional level arg is validated (numeric, 0..obj level) then ignored
    ([PRIMESUD] no per-load level scaling, as mpoload).
    """
    parts = args.split()
    if not parts or not _is_number(parts[0]):
        dbg("objprog: opoload bad syntax")
        return
    arg2 = parts[1] if len(parts) > 1 else ""
    if arg2:
        if not _is_number(arg2):
            dbg("objprog: opoload bad syntax")
            return
        lv = _atoi(arg2)
        if lv < 0 or lv > _obj_level(octx["obj"]):
            dbg("objprog: opoload bad level")
            return
    vnum = _atoi(parts[0])
    if vnum not in world.ITEM_DEFS:
        dbg("objprog: opoload bad obj " + str(vnum))
        return
    rvnum = _octx_room(octx)
    if rvnum is None:
        return
    world.rooms[rvnum]["items"].append(create_object(vnum))


def _op_purge(octx, args, pv):
    """Purge the room or one target (cf. do_oppurge).

    The no-arg sweep spares only nopurge items and the prog's own obj; a named
    target resolves char-in-room, floor obj, then the carrier's inventory and
    equipment, as upstream.
    """
    rvnum = _octx_room(octx)
    rs = world.rooms._data.get(rvnum) if rvnum is not None else None
    o = octx["obj"]
    arg = _first(args)
    if not arg:
        if rs is None:
            return
        for c in list(_persons_at(rvnum)):
            if c.get("is_npc") and not c.get("act_flags", {}).get("nopurge"):
                _extract_char(c, pull=True)
        rs["items"] = [it for it in rs.get("items", [])
                       if _obj_has_nopurge(it) or it is o]
        return
    victim = _char_at(rvnum, arg)
    if victim is None:
        vobj = _obj_at(rvnum, arg)
        if vobj is not None:
            if rs is not None and vobj in rs.get("items", []):
                rs["items"].remove(vobj)
            return
        carrier = octx.get("carrier")
        if carrier is not None:
            vobj = get_obj_list(arg, carrier.get("inv", []), world.ITEM_DEFS, carrier)
            if vobj is not None:
                carrier["inv"].remove(vobj)
                return
            for slot, it in list(carrier.get("equip", {}).items()):
                if it is not None and is_name(arg, _obj_keywords(it)):
                    carrier["equip"][slot] = None
                    return
        dbg("objprog: oppurge bad argument from obj " + str(obj_vnum(o)))
        return
    if not victim.get("is_npc"):
        dbg("objprog: oppurge PC from obj " + str(obj_vnum(o)))
        return
    _extract_char(victim, pull=True)


def _op_goto(octx, args, pv):
    """Move the object itself (cf. do_opgoto): room vnum or char name.
    [PRIMESUD] world-object location fallback not ported (as _find_location)."""
    arg = _first(args)
    if not arg:
        dbg("objprog: opgoto no argument")
        return
    loc = _find_location_nv(arg)
    if loc is None:
        dbg("objprog: opgoto no such location")
        return
    _octx_detach(octx)
    world.rooms[loc]["items"].append(octx["obj"])
    octx["room"] = loc
    octx["carrier"] = None


def _op_transfer(octx, args, pv):
    """Transfer a char (or all players) to a location (cf. do_optransfer)."""
    parts = args.split()
    if not parts:
        dbg("objprog: optransfer bad syntax")
        return
    arg1 = parts[0]
    arg2 = parts[1] if len(parts) > 1 else ""
    rvnum = _octx_room(octx)
    if arg1 == "all":
        for c in list(_persons_at(rvnum)):
            if not c.get("is_npc"):
                _op_transfer(octx, c.get("name", "") + ((" " + arg2) if arg2 else ""), pv)
        return
    if not arg2:
        loc = rvnum
    else:
        loc = _find_location_nv(arg2)
        if loc is None:
            dbg("objprog: optransfer no such location")
            return
    if loc is None:
        return
    victim = _char_world_nv(arg1)
    if victim is None or victim.get("room") is None:
        return
    _transfer_char_to(victim, loc)


def _op_force(octx, args, pv):
    """Force chars in the obj's room to act (cf. do_opforce).

    [PRIMESUD] the upstream ``all`` filter is get_trust(vch) < obj level; with
    no trust system, char level stands in for trust.
    """
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("objprog: opforce bad syntax")
        return
    arg, rest = parts[0], parts[1]
    rvnum = _octx_room(octx)
    if arg == "all":
        olev = _obj_level(octx["obj"])
        for c in list(_persons_at(rvnum)):
            if c.get("level", 0) < olev:
                interpret(rest, c)
    else:
        victim = _char_at(rvnum, arg)
        if victim is None:
            return
        interpret(rest, victim)


def _op_damage(octx, args, pv):
    """Prog damage (cf. do_opdamage).

    Bug-faithful: the ``all`` branch damages only when the obj has a carrier,
    and spares the carrier (upstream's ``obj->carried_by && victim !=
    obj->carried_by`` gate makes a floor obj's ``damage all`` a no-op).
    """
    parsed = _parse_damage_args(args.split(), "objprog: opdamage")
    if parsed is None:
        return
    target, low, high, fkill = parsed
    rvnum = _octx_room(octx)
    carrier = octx.get("carrier")
    if target == "all":
        for c in list(_persons_at(rvnum)):
            if carrier is not None and c is not carrier:
                _prog_damage(c, low, high, fkill)
    else:
        v = _char_at(rvnum, target)
        if v is None:
            return
        _prog_damage(v, low, high, fkill)


def _op_remember(octx, args, pv):
    arg = _first(args)
    if not arg:
        dbg("objprog: opremember missing argument")
        return
    victim = _char_world_nv(arg)
    # [PRIMESUD] stored as char id (see _target_of), not a dict ref
    octx["obj"]["oprog_target"] = victim.get("id") if victim is not None else None


def _op_forget(octx, args, pv):
    octx["obj"]["oprog_target"] = None


def _op_delay(octx, args, pv):
    arg = _first(args)
    if not _is_number(arg):
        dbg("objprog: opdelay invalid argument")
        return
    octx["obj"]["oprog_delay"] = _atoi(arg)


def _op_cancel(octx, args, pv):
    octx["obj"]["oprog_delay"] = -1


def _op_call(octx, args, pv):
    """Run another OBJprog on this object (cf. do_opcall)."""
    parts = args.split()
    if not parts:
        dbg("objprog: opcall missing arguments")
        return
    if not _is_number(parts[0]):
        dbg("objprog: opcall invalid prog")
        return
    prog_vnum = _atoi(parts[0])
    code = world.OBJPROGS.get(prog_vnum)
    if code is None:
        dbg("objprog: opcall invalid prog " + str(prog_vnum))
        return
    rvnum = _octx_room(octx)
    vch = _char_at(rvnum, parts[1]) if len(parts) > 1 and parts[1] else None
    obj1 = _obj_at(rvnum, parts[2]) if len(parts) > 2 and parts[2] else None
    obj2 = _obj_at(rvnum, parts[3]) if len(parts) > 3 and parts[3] else None
    # nested program_flow entry bumps the global _call_depth itself
    program_flow(prog_vnum, code, None, vch, obj1, obj2, obj=octx)


def _op_otransfer(octx, args, pv):
    """Move a floor object to a location (cf. do_opotransfer)."""
    parts = args.split()
    if not parts:
        dbg("objprog: opotransfer missing argument")
        return
    loc = _find_location_nv(parts[1] if len(parts) > 1 else "")
    if loc is None:
        dbg("objprog: opotransfer no such location")
        return
    rvnum = _octx_room(octx)
    vobj = _obj_at(rvnum, parts[0])
    if vobj is None:
        return
    rs = world.rooms._data.get(rvnum)
    if rs is not None and vobj in rs.get("items", []):
        rs["items"].remove(vobj)
    world.rooms[loc]["items"].append(vobj)


def _op_remove(octx, args, pv):
    """Strip and extract objects from a char (cf. do_opremove)."""
    parts = args.split()
    if not parts:
        return
    victim = _char_at(_octx_room(octx), parts[0])
    if victim is None:
        return
    _remove_objs(victim, parts[1] if len(parts) > 1 else "",
                 "objprog: opremove invalid object from obj "
                 + str(obj_vnum(octx["obj"])))


def _attrib_num(spec, cur, chlev, label):
    """One do_opattrib slot: a literal, ``none`` (keep current), or a +-*/N
    modifier applied to the target char's level (cf. do_opattrib).

    Returns:
        int or None: The slot value; None aborts the whole command.
    """
    if spec == "none":
        return cur
    if spec and not spec[0].isdigit():
        mod = spec[0]
        num = spec[1:]
        if not _is_number(num):
            dbg(label + " non-number argument")
            return None
        n = _atoi(num)
        if mod == "+":
            return chlev + n
        if mod == "-":
            return chlev - n
        if mod == "*":
            return chlev * n
        if mod == "/":
            if n == 0:   # [PRIMESUD] guard; upstream divides by zero
                dbg(label + " division by zero")
                return None
            return chlev // n
        dbg(label + " invalid modifier")
        return None
    if _is_number(spec):
        return _atoi(spec)
    dbg(label + " non-number argument")
    return None


def _op_attrib(octx, args, pv):
    """Set the obj's level/condition/value[0..4] (cf. do_opattrib).

    Slots: ``target level condition v0 v1 v2 v3 v4``; target ``worn`` means
    the carrier.  All-or-nothing: any bad slot aborts with no writes, as
    upstream.  [PRIMESUD] values land on the instance dict ("level",
    "condition", "values" 5-tuple); runtime consumers arrive with the objval
    if-checks in Phase 3.
    """
    parts = args.split()
    o = octx["obj"]
    target = parts[0] if parts else ""
    if target == "worn":
        chv = octx.get("carrier")
        if chv is None:
            return
    else:
        chv = _char_at(_octx_room(octx), target)
        if chv is None:
            return
    label = "objprog: opattrib obj " + str(obj_vnum(o))
    chlev = chv.get("level", 0)
    tpl = world.ITEM_DEFS.get(obj_vnum(o)) or {}
    cur_vals = list(o.get("values", tpl.get("values", (0, 0, 0, 0, 0))))
    while len(cur_vals) < 5:
        cur_vals.append(0)
    specs = list(parts[1:8])
    while len(specs) < 7:
        specs.append("")
    curs = [_obj_level(o), o.get("condition", tpl.get("condition", 0))] + cur_vals[:5]
    new = []
    for spec, cur in zip(specs, curs):
        v = _attrib_num(spec, cur, chlev, label)
        if v is None:
            return
        new.append(v)
    o["level"] = new[0]
    o["condition"] = new[1]
    o["values"] = (new[2], new[3], new[4], new[5], new[6])


def _op_peace(octx, args, pv):
    """(cf. do_oppeace)"""
    _peace_room(_octx_room(octx))


def _op_gtransfer(octx, args, pv):
    """Transfer a char's whole group (cf. do_opgtransfer, prog_cmds.c:1590)."""
    parts = args.split()
    if not parts:
        dbg("objprog: opgtransfer bad syntax")
        return
    rvnum = _octx_room(octx)
    who = _char_at(rvnum, parts[0])
    if who is None:
        return
    arg2 = parts[1] if len(parts) > 1 else ""
    for victim in list(_persons_at(rvnum)):
        if is_same_group(who, victim):
            _op_transfer(octx, _first(_char_kw(victim))
                         + ((" " + arg2) if arg2 else ""), pv)


def _op_gforce(octx, args, pv):
    """Force a char's whole group to act (cf. do_opgforce, prog_cmds.c:1687).
    Unlike the mob variant there is no self-exclusion (an obj is not a char)."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("objprog: opgforce bad syntax")
        return
    victim = _char_at(_octx_room(octx), parts[0])
    if victim is None:
        return
    for vch in list(_persons_at(victim.get("room"))):
        if is_same_group(victim, vch):
            interpret(parts[1], vch)


def _op_vforce(octx, args, pv):
    """Force every non-fighting NPC of a vnum, worldwide (cf. do_opvforce,
    prog_cmds.c:1719).  No self-exclusion, as upstream."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("objprog: opvforce bad syntax")
        return
    if not _is_number(parts[0]):
        dbg("objprog: opvforce non-number arg")
        return
    v = _atoi(parts[0])
    for victim in list(world.chars.values()):
        if (victim.get("is_npc") and victim.get("tpl") == v
                and victim.get("fighting") is None):
            interpret(parts[1], victim)


# Table order matches 1stMud obj_cmd_table (prog_cmds.c:77); dispatch is a
# case-insensitive prefix match in this order (first match wins).
OP_COMMANDS = (
    ("gecho", _op_gecho),
    ("zecho", _op_zecho),
    ("echo", _op_echo),
    ("echoaround", _op_echoaround),
    ("echoat", _op_echoat),
    ("mload", _op_mload),
    ("oload", _op_oload),
    ("purge", _op_purge),
    ("goto", _op_goto),
    ("transfer", _op_transfer),
    ("gtransfer", _op_gtransfer),
    ("otransfer", _op_otransfer),
    ("force", _op_force),
    ("gforce", _op_gforce),
    ("vforce", _op_vforce),
    ("damage", _op_damage),
    ("remember", _op_remember),
    ("forget", _op_forget),
    ("delay", _op_delay),
    ("cancel", _op_cancel),
    ("call", _op_call),
    ("remove", _op_remove),
    ("attrib", _op_attrib),
    ("peace", _op_peace),
)


def obj_interpret(octx, argument, prog_vnum=0):
    """Dispatch an ``obj <subcmd>`` prog command (cf. obj_interpret, prog_cmds.c:1168).

    Prefix-matched against OP_COMMANDS in table order (first match wins).  An
    unknown subcommand logs a bug and is skipped.
    """
    parts = argument.split(None, 1)
    if not parts:
        return
    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    for name, fn in OP_COMMANDS:
        if name[0] == command[0] and name.startswith(command):
            fn(octx, rest, prog_vnum)
            return
    dbg("objprog: invalid cmd '" + command + "' from obj "
        + str(obj_vnum(octx["obj"])))


# -- rp-command set (cf. prog_cmds.c room_cmd_table) ---------------------------
#
# Every function takes (rvnum, args, pv); *rvnum* is the room-origin vnum.


def _rp_state(rvnum):
    """Runtime room state dict for *rvnum*, or None if unloaded. [PRIMESUD]"""
    return world.rooms._data.get(rvnum)


def _rp_gecho(rvnum, args, pv):
    """Global echo (cf. do_rpgecho).  [PRIMESUD] single-player: to the one player."""
    if not args:
        dbg("roomprog: rpgecho missing argument")
        return
    p = world.chars.get(1)
    if p is not None:
        chprintln(p, args)


def _rp_zecho(rvnum, args, pv):
    """Zone echo (cf. do_rpzecho).  [PRIMESUD] to the player if in the room's area."""
    if not args:
        dbg("roomprog: rpzecho missing argument")
        return
    p = world.chars.get(1)
    if p is None:
        return
    proom = world.ROOM_DEFS._data.get(p.get("room"))
    rroom = world.ROOM_DEFS._data.get(rvnum)
    if proom is not None and rroom is not None and proom.get("area") == rroom.get("area"):
        chprintln(p, args)


def _rp_asound(rvnum, args, pv):
    """Sound heard in every adjacent room (cf. do_rpasound).

    Unlike mob asound, upstream does not latch MOBtrigger off here -- kept
    bug-faithful.
    """
    if not args:
        return
    in_room = world.ROOM_DEFS._data.get(rvnum)
    if in_room is None:
        return
    for _d, ev in in_room.get("exits", {}).items():
        dest = ev.get("to") if isinstance(ev, dict) else ev
        if dest is None or dest == rvnum:
            continue
        persons = _persons_at(dest)
        if not persons:
            continue
        act(args, persons[0], None, None, TO_ROOM)
        act(args, persons[0], None, None, TO_CHAR)


def _rp_echoaround(rvnum, args, pv):
    """Echo to everyone but one char (cf. do_rpechoaround)."""
    parts = args.split(None, 1)
    if not parts:
        return
    victim = _char_at(rvnum, parts[0])
    if victim is None:
        return
    act(parts[1] if len(parts) > 1 else "", victim, None, victim, TO_NOTVICT)


def _rp_echoat(rvnum, args, pv):
    """Echo to one char (cf. do_rpechoat)."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        return
    victim = _char_at(rvnum, parts[0])
    if victim is None:
        return
    act(parts[1], victim, None, None, TO_CHAR)


def _rp_echo(rvnum, args, pv):
    """Room echo (cf. do_rpecho): everyone in the room sees it."""
    if not args:
        return
    persons = _persons_at(rvnum)
    if not persons:
        return
    act(args, persons[0], None, None, TO_ROOM)
    act(args, persons[0], None, None, TO_CHAR)


def _rp_mload(rvnum, args, pv):
    """Load a mob into the room (cf. do_rpmload)."""
    arg = _first(args)
    if not arg or not _is_number(arg):
        return
    vnum = _atoi(arg)
    if vnum not in world.MOB_DEFS:
        dbg("roomprog: rpmload bad mob " + str(vnum))
        return
    _spawn_mob_at(vnum, rvnum)


def _rp_oload(rvnum, args, pv):
    """Load an obj onto the room floor (cf. do_rpoload).

    The level arg is mandatory here, validated (numeric, non-negative) then
    ignored ([PRIMESUD] no per-load level scaling; upstream's LEVEL_IMMORTAL
    upper bound has no PrimeSUD equivalent).
    """
    parts = args.split()
    if len(parts) < 2 or not _is_number(parts[0]) or not _is_number(parts[1]):
        dbg("roomprog: rpoload bad syntax")
        return
    if _atoi(parts[1]) < 0:
        dbg("roomprog: rpoload bad level")
        return
    vnum = _atoi(parts[0])
    if vnum not in world.ITEM_DEFS:
        dbg("roomprog: rpoload bad obj " + str(vnum))
        return
    world.rooms[rvnum]["items"].append(create_object(vnum))


def _rp_purge(rvnum, args, pv):
    """Purge the room or one target (cf. do_rppurge)."""
    rs = _rp_state(rvnum)
    if rs is None:
        return
    arg = _first(args)
    if not arg:
        for c in list(_persons_at(rvnum)):
            if c.get("is_npc") and not c.get("act_flags", {}).get("nopurge"):
                _extract_char(c, pull=True)
        rs["items"] = [it for it in rs.get("items", []) if _obj_has_nopurge(it)]
        return
    victim = _char_at(rvnum, arg)
    if victim is None:
        vobj = _obj_at(rvnum, arg)
        if vobj is not None:
            if vobj in rs.get("items", []):
                rs["items"].remove(vobj)
        else:
            dbg("roomprog: rppurge bad argument from room " + str(rvnum))
        return
    if not victim.get("is_npc"):
        dbg("roomprog: rppurge PC from room " + str(rvnum))
        return
    _extract_char(victim, pull=True)


def _rp_transfer(rvnum, args, pv):
    """Transfer a char (or all players) to a location (cf. do_rptransfer)."""
    parts = args.split()
    if not parts:
        dbg("roomprog: rptransfer bad syntax")
        return
    arg1 = parts[0]
    arg2 = parts[1] if len(parts) > 1 else ""
    if arg1 == "all":
        for c in list(_persons_at(rvnum)):
            if not c.get("is_npc"):
                _rp_transfer(rvnum, c.get("name", "") + ((" " + arg2) if arg2 else ""), pv)
        return
    if not arg2:
        loc = rvnum
    else:
        loc = _find_location_nv(arg2)
        if loc is None:
            dbg("roomprog: rptransfer no such location")
            return
    victim = _char_world_nv(arg1)
    if victim is None or victim.get("room") is None:
        return
    _transfer_char_to(victim, loc)


def _rp_force(rvnum, args, pv):
    """Force chars in the room to act (cf. do_rpforce).

    [PRIMESUD] upstream's ``all`` branch skips immortals; no immortals in
    PrimeSUD, so everyone in the room is forced.
    """
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("roomprog: rpforce bad syntax")
        return
    arg, rest = parts[0], parts[1]
    if arg == "all":
        for c in list(_persons_at(rvnum)):
            interpret(rest, c)
    else:
        victim = _char_at(rvnum, arg)
        if victim is None:
            return
        interpret(rest, victim)


def _rp_damage(rvnum, args, pv):
    """Prog damage (cf. do_rpdamage); ``all`` hits everyone in the room."""
    parsed = _parse_damage_args(args.split(), "roomprog: rpdamage")
    if parsed is None:
        return
    target, low, high, fkill = parsed
    if target == "all":
        for c in list(_persons_at(rvnum)):
            _prog_damage(c, low, high, fkill)
    else:
        v = _char_at(rvnum, target)
        if v is None:
            return
        _prog_damage(v, low, high, fkill)


def _rp_remember(rvnum, args, pv):
    rs = _rp_state(rvnum)
    arg = _first(args)
    if not arg:
        dbg("roomprog: rpremember missing argument")
        return
    if rs is None:
        return
    victim = _char_world_nv(arg)
    # [PRIMESUD] stored as char id (see _target_of), not a dict ref
    rs["rprog_target"] = victim.get("id") if victim is not None else None


def _rp_forget(rvnum, args, pv):
    rs = _rp_state(rvnum)
    if rs is not None:
        rs["rprog_target"] = None


def _rp_delay(rvnum, args, pv):
    arg = _first(args)
    if not _is_number(arg):
        dbg("roomprog: rpdelay invalid argument")
        return
    rs = _rp_state(rvnum)
    if rs is not None:
        rs["rprog_delay"] = _atoi(arg)


def _rp_cancel(rvnum, args, pv):
    rs = _rp_state(rvnum)
    if rs is not None:
        rs["rprog_delay"] = -1


def _rp_call(rvnum, args, pv):
    """Run another ROOMprog on this room (cf. do_rpcall)."""
    parts = args.split()
    if not parts:
        dbg("roomprog: rpcall missing arguments")
        return
    if not _is_number(parts[0]):
        dbg("roomprog: rpcall invalid prog")
        return
    prog_vnum = _atoi(parts[0])
    code = world.ROOMPROGS.get(prog_vnum)
    if code is None:
        dbg("roomprog: rpcall invalid prog " + str(prog_vnum))
        return
    vch = _char_at(rvnum, parts[1]) if len(parts) > 1 and parts[1] else None
    obj1 = _obj_at(rvnum, parts[2]) if len(parts) > 2 and parts[2] else None
    obj2 = _obj_at(rvnum, parts[3]) if len(parts) > 3 and parts[3] else None
    # nested program_flow entry bumps the global _call_depth itself
    program_flow(prog_vnum, code, None, vch, obj1, obj2, room=rvnum)


def _rp_otransfer(rvnum, args, pv):
    """Move a floor object to a location (cf. do_rpotransfer)."""
    parts = args.split()
    if not parts:
        dbg("roomprog: rpotransfer missing argument")
        return
    loc = _find_location_nv(parts[1] if len(parts) > 1 else "")
    if loc is None:
        dbg("roomprog: rpotransfer no such location")
        return
    vobj = _obj_at(rvnum, parts[0])
    if vobj is None:
        return
    rs = _rp_state(rvnum)
    if rs is not None and vobj in rs.get("items", []):
        rs["items"].remove(vobj)
    world.rooms[loc]["items"].append(vobj)


def _rp_remove(rvnum, args, pv):
    """Strip and extract objects from a char (cf. do_rpremove)."""
    parts = args.split()
    if not parts:
        return
    victim = _char_at(rvnum, parts[0])
    if victim is None:
        return
    _remove_objs(victim, parts[1] if len(parts) > 1 else "",
                 "roomprog: rpremove invalid object from room " + str(rvnum))


def _rp_peace(rvnum, args, pv):
    """(cf. do_rppeace)"""
    _peace_room(rvnum)


def _rp_gtransfer(rvnum, args, pv):
    """Transfer a char's whole group (cf. do_rpgtransfer, prog_cmds.c:2752)."""
    parts = args.split()
    if not parts:
        dbg("roomprog: rpgtransfer bad syntax")
        return
    who = _char_at(rvnum, parts[0])
    if who is None:
        return
    arg2 = parts[1] if len(parts) > 1 else ""
    for victim in list(_persons_at(rvnum)):
        if is_same_group(who, victim):
            _rp_transfer(rvnum, _first(_char_kw(victim))
                         + ((" " + arg2) if arg2 else ""), pv)


def _rp_gforce(rvnum, args, pv):
    """Force a char's whole group to act (cf. do_rpgforce, prog_cmds.c:2821)."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("roomprog: rpgforce bad syntax")
        return
    victim = _char_at(rvnum, parts[0])
    if victim is None:
        return
    for vch in list(_persons_at(victim.get("room"))):
        if is_same_group(victim, vch):
            interpret(parts[1], vch)


def _rp_vforce(rvnum, args, pv):
    """Force every non-fighting NPC of a vnum, worldwide (cf. do_rpvforce,
    prog_cmds.c:2847)."""
    parts = args.split(None, 1)
    if len(parts) < 2 or not parts[1]:
        dbg("roomprog: rpvforce bad syntax")
        return
    if not _is_number(parts[0]):
        dbg("roomprog: rpvforce non-number arg")
        return
    v = _atoi(parts[0])
    for victim in list(world.chars.values()):
        if (victim.get("is_npc") and victim.get("tpl") == v
                and victim.get("fighting") is None):
            interpret(parts[1], victim)


# Table order matches 1stMud room_cmd_table (prog_cmds.c:105); dispatch is a
# case-insensitive prefix match in this order (first match wins).
RP_COMMANDS = (
    ("asound", _rp_asound),
    ("gecho", _rp_gecho),
    ("zecho", _rp_zecho),
    ("echo", _rp_echo),
    ("echoaround", _rp_echoaround),
    ("echoat", _rp_echoat),
    ("mload", _rp_mload),
    ("oload", _rp_oload),
    ("purge", _rp_purge),
    ("transfer", _rp_transfer),
    ("gtransfer", _rp_gtransfer),
    ("otransfer", _rp_otransfer),
    ("force", _rp_force),
    ("gforce", _rp_gforce),
    ("vforce", _rp_vforce),
    ("damage", _rp_damage),
    ("remember", _rp_remember),
    ("forget", _rp_forget),
    ("delay", _rp_delay),
    ("cancel", _rp_cancel),
    ("call", _rp_call),
    ("remove", _rp_remove),
    ("peace", _rp_peace),
)


def room_interpret(rvnum, argument, prog_vnum=0):
    """Dispatch a ``room <subcmd>`` prog command (cf. room_interpret, prog_cmds.c:2427).

    Prefix-matched against RP_COMMANDS in table order (first match wins).  An
    unknown subcommand logs a bug and is skipped.
    """
    parts = argument.split(None, 1)
    if not parts:
        return
    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    for name, fn in RP_COMMANDS:
        if name[0] == command[0] and name.startswith(command):
            fn(rvnum, rest, prog_vnum)
            return
    dbg("roomprog: invalid cmd '" + command + "' from room " + str(rvnum))
