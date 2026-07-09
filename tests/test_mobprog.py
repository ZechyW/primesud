"""Tests for the MOBprogram interpreter core (cf. 1stMud programs.c).

Phase A of MOBPROG_PLAN.md: the pure interpreter (num_eval, expand_arg,
cmd_eval, program_flow control flow, buggy-prog aborts) plus the
mob-as-command-actor spike driving say/emote/north through the real
command interpreter.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import mobprog
import handler
import world
from handler import _char_base
from world import ROOM_DEFS, MOB_DEFS


# -- num_eval ------------------------------------------------------------------

def test_num_eval_operators():
    assert mobprog.num_eval(5, "==", 5)
    assert not mobprog.num_eval(5, "==", 6)
    assert mobprog.num_eval(5, "!=", 6)
    assert mobprog.num_eval(6, ">", 5)
    assert mobprog.num_eval(5, "<", 6)
    assert mobprog.num_eval(5, ">=", 5)
    assert mobprog.num_eval(5, "<=", 5)
    assert not mobprog.num_eval(5, ">", 5)


def test_num_eval_bad_operator_false(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    assert mobprog.num_eval(5, "=<", 5) is False
    assert logged  # logged the invalid oper


# -- expand_arg ----------------------------------------------------------------

def _mob(**kw):
    m = {"name": "big guard", "short_descr": "the big guard", "is_npc": True,
         "sex": "male", "level": 10, "mprog_target": None, "affected_by": {}}
    m.update(kw)
    return m


def _pc(**kw):
    c = {"name": "John Doe", "short_descr": None, "is_npc": False,
         "sex": "female", "level": 5, "affected_by": {}}
    c.update(kw)
    return c


def test_expand_arg_char_codes():
    mob = _mob()
    ch = _pc()
    # $i mob first word (no capitalize), $I mob short, $n ch cap first word
    assert mobprog.expand_arg("$i", mob, ch, None, None, None) == "big"
    assert mobprog.expand_arg("$I", mob, ch, None, None, None) == "the big guard"
    assert mobprog.expand_arg("$n", mob, ch, None, None, None) == "John"
    # $N of a PC = name; of an NPC = short_descr
    assert mobprog.expand_arg("$N", mob, ch, None, None, None) == "John Doe"
    npc_ch = _pc(name="rat", short_descr="a small rat", is_npc=True)
    assert mobprog.expand_arg("$N", mob, npc_ch, None, None, None) == "a small rat"


def test_expand_arg_missing_char_is_someone():
    mob = _mob()
    assert mobprog.expand_arg("$n", mob, None, None, None, None) == "someone"


def test_expand_arg_pronouns():
    mob = _mob(sex="male")
    ch = _pc(sex="female")
    assert mobprog.expand_arg("$j", mob, ch, None, None, None) == "he"   # subject
    assert mobprog.expand_arg("$k", mob, ch, None, None, None) == "him"  # object
    assert mobprog.expand_arg("$l", mob, ch, None, None, None) == "his"  # possessive
    assert mobprog.expand_arg("$e", mob, ch, None, None, None) == "she"
    assert mobprog.expand_arg("$m", mob, ch, None, None, None) == "her"
    assert mobprog.expand_arg("$s", mob, ch, None, None, None) == "her"


def test_expand_arg_literal_and_bad_code(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    mob = _mob()
    out = mobprog.expand_arg("hi $n, meet $i.", mob, _pc(), None, None, None)
    assert out == "hi John, meet big."
    bad = mobprog.expand_arg("x$zy", mob, None, None, None, None)
    assert "<@@@>" in bad
    assert logged


# -- cmd_eval ------------------------------------------------------------------

def test_cmd_eval_rand_bounds(monkeypatch):
    mob = _mob()
    monkeypatch.setattr(mobprog, "_number_percent", lambda: 50)
    assert mobprog.cmd_eval("rand", "100", mob, None, None, None, None, 1)
    assert not mobprog.cmd_eval("rand", "10", mob, None, None, None, None, 1)


def test_cmd_eval_numeric_char_check():
    mob = _mob(level=10)
    assert mobprog.cmd_eval("level", "$i > 5", mob, None, None, None, None, 1)
    assert not mobprog.cmd_eval("level", "$i > 50", mob, None, None, None, None, 1)


def test_cmd_eval_bool_checks():
    mob = _mob()
    pc = _pc()
    # $n is the triggering PC
    assert mobprog.cmd_eval("ispc", "$n", mob, pc, None, None, None, 1)
    assert not mobprog.cmd_eval("isnpc", "$n", mob, pc, None, None, None, 1)
    assert mobprog.cmd_eval("isnpc", "$i", mob, pc, None, None, None, 1)


def test_cmd_eval_flag_check():
    mob = _mob()
    pc = _pc(name="John Doe")
    assert mobprog.cmd_eval("name", "$n john", mob, pc, None, None, None, 1)
    assert not mobprog.cmd_eval("name", "$n mary", mob, pc, None, None, None, 1)


def test_cmd_eval_unported_check_logs_false(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    mob = _mob()
    # 'clan' is valid 1stMud vocab but outside the Phase A subset
    assert mobprog.cmd_eval("clan", "$n", mob, _pc(), None, None, None, 1) is False
    assert any("not ported" in m for m in logged)


def test_mprog_target_stored_as_id_and_resolved():
    """cmd_eval records the trigger char's id; $q/istarget resolve it back."""
    mob = _mob(mprog_target=None)
    pc = _pc(id=7, room=5)
    mob["room"] = 5
    world.chars[7] = pc
    try:
        # first if-check binds mob->mprog_target = ch (as 1stMud does)
        mobprog.cmd_eval("ispc", "$n", mob, pc, None, None, None, 1)
        assert mob["mprog_target"] == 7          # id, not the dict
        assert mobprog._target_of(mob) is pc     # resolves back to the char
        # istarget compares by id
        assert mobprog.cmd_eval("istarget", "$n", mob, pc, None, None, None, 1)
        # $q expands the resolved target's name
        assert mobprog.expand_arg("$q", mob, pc, None, None, None) == "John"
        # extracted target (dropped from world.chars) resolves to None
        del world.chars[7]
        assert mobprog._target_of(mob) is None
    finally:
        world.chars.pop(7, None)


# -- program_flow control flow -------------------------------------------------

@pytest.fixture
def dispatched(monkeypatch):
    """Capture dispatched command lines instead of running the interpreter."""
    calls = []
    monkeypatch.setattr(mobprog, "_dispatch",
                        lambda pv, mob, ctrl, expanded, cl=0: calls.append(expanded))
    return calls


def test_flow_simple_true_branch(dispatched):
    prog = "\n".join([
        "if level $i > 5",
        "say yes",
        "endif",
        "say always",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say yes", "say always"]


def test_flow_false_branch_skips(dispatched):
    prog = "\n".join([
        "if level $i > 50",
        "say no",
        "endif",
        "say always",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say always"]


def test_flow_if_else_nesting(dispatched):
    prog = "\n".join([
        "if level $i > 5",
        "say outer",
        "if level $i > 50",
        "say inner-skip",
        "else",
        "say inner-else",
        "endif",
        "say after-inner",
        "endif",
        "say end",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say outer", "say inner-else", "say after-inner", "say end"]


def test_flow_or_combines(dispatched):
    prog = "\n".join([
        "if level $i > 50",
        "or level $i > 5",
        "say b",
        "endif",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say b"]


def test_flow_and_combines(dispatched):
    prog = "\n".join([
        "if level $i > 5",
        "and level $i > 50",
        "say b",
        "endif",
        "say c",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say c"]


def test_flow_comment_and_break(dispatched):
    prog = "\n".join([
        "* this is a comment",
        "say one",
        "break",
        "say unreachable",
    ])
    mobprog.program_flow(1, prog, _mob(level=10), None)
    assert dispatched == ["say one"]


def test_flow_expands_codes_before_dispatch(dispatched):
    prog = "say hi $n"
    mobprog.program_flow(1, prog, _mob(), _pc(name="John Doe"))
    assert dispatched == ["say hi John"]


# -- program_flow abort paths (buggy_prog) -------------------------------------

@pytest.fixture
def flow_errors(monkeypatch):
    calls = []
    errs = []
    monkeypatch.setattr(mobprog, "_dispatch",
                        lambda pv, mob, ctrl, expanded, cl=0: calls.append(expanded))
    monkeypatch.setattr(mobprog, "dbg", lambda m: errs.append(m))
    return calls, errs


def test_abort_endif_without_if(flow_errors):
    calls, errs = flow_errors
    prog = "\n".join(["say before", "endif", "say after"])
    mobprog.program_flow(1, prog, _mob(), None)
    assert calls == ["say before"]        # aborted at the stray endif
    assert any("endif without if" in m for m in errs)


def test_abort_else_without_if(flow_errors):
    calls, errs = flow_errors
    prog = "\n".join(["say before", "else", "say after"])
    mobprog.program_flow(1, prog, _mob(), None)
    assert calls == ["say before"]
    assert any("else without if" in m for m in errs)


def test_abort_unknown_if_check(flow_errors):
    calls, errs = flow_errors
    prog = "\n".join(["if boguscheck $n", "say x", "endif", "say y"])
    mobprog.program_flow(1, prog, _mob(), None)
    assert calls == []                    # aborted at the invalid if_check
    assert any("invalid if_check" in m for m in errs)


def test_abort_max_call_level(flow_errors):
    calls, errs = flow_errors
    mobprog.program_flow(1, "say x", _mob(), None,
                         call_level=mobprog.MAX_CALL_LEVEL)
    assert calls == []
    assert any("max call level" in m for m in errs)


# -- Phase A spike: mob-as-command-actor through the real interpreter ----------

@pytest.fixture
def spike_world(monkeypatch):
    """Two connected rooms, a player and a mob, with captured act() output."""
    old_rd = dict(ROOM_DEFS._data)
    old_wr = dict(world.rooms._data)
    old_ch = dict(world.chars)
    old_md = dict(MOB_DEFS._data)

    def _room(vnum, exits):
        r = {"name": "Room %d" % vnum, "desc": "x", "exits": exits,
             "items": [], "mobs": [], "area": "test", "flags": {},
             "sector": "inside"}
        ROOM_DEFS._data[vnum] = r
        world.rooms._data[vnum] = r
        return r

    _room(9001, {"n": {"to": 9002}})
    _room(9002, {"s": {"to": 9001}})
    MOB_DEFS._data[9405] = {"short_descr": "a test guard", "keywords": "guard",
                            "level": 10}

    player = _char_base()
    player["id"] = 1
    player["is_npc"] = False
    player["name"] = "Tester"
    player["room"] = 9001
    player["pos"] = "standing"
    world.chars[1] = player

    mob = _char_base()
    mob["id"] = 2
    mob["is_npc"] = True
    mob["tpl"] = 9405
    mob["name"] = "guard"
    mob["short_descr"] = "a test guard"
    mob["room"] = 9001
    mob["pos"] = "standing"
    mob["mprog_target"] = None
    world.chars[2] = mob
    world.rooms._data[9001]["mobs"].append(2)

    out = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))

    yield player, mob, out

    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rd)
    world.rooms._data.clear(); world.rooms._data.update(old_wr)
    world.chars.clear(); world.chars.update(old_ch)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_md)


def test_spike_mob_say(spike_world):
    player, mob, out = spike_world
    mobprog.program_flow(1, "say Hello There", mob, player)
    # act() TO_ROOM reaches the player.  Free-text tail is verbatim now (only
    # the command word is lowercased), so the case survives.  The {G..{g
    # wrapping is from do_say's own template, not the mob text.
    assert any("says" in l and "Hello There" in l for l in out)
    # TO_CHAR (the mob's own line) must NOT leak to the player
    assert not any("You say" in l for l in out)


def test_spike_mob_emote(spike_world):
    player, mob, out = spike_world
    mobprog.program_flow(1, "emote waves happily.", mob, player)
    # act $n renders the actor's *name* ("Guard"), not the short_descr
    assert any("Guard waves happily." in l for l in out)


def test_player_say_preserves_case_and_colour(spike_world):
    """say passes its tail verbatim: case and {C colour codes survive."""
    player, mob, out = spike_world
    from commands import interpret
    del out[:]
    interpret("say Hello {CWorld", player)
    assert any("Hello {CWorld" in l for l in out)
    # command word still case-insensitive
    del out[:]
    interpret("SAY Bye {RNow", player)
    assert any("Bye {RNow" in l for l in out)


def test_player_emote_preserves_case_and_colour(spike_world):
    player, mob, out = spike_world
    from commands import interpret
    del out[:]
    interpret("emote Waves {Rwildly", player)
    assert any("Waves {Rwildly" in l for l in out)


def test_spike_mob_walks_north(spike_world):
    player, mob, out = spike_world
    mobprog.program_flow(1, "north", mob, player)
    assert mob["room"] == 9002
    assert 2 not in world.rooms._data[9001]["mobs"]
    assert 2 in world.rooms._data[9002]["mobs"]
    # the player, left behind in 9001, saw the mob leave
    assert any("leaves" in l for l in out)


def test_spike_full_prog_chain(spike_world):
    player, mob, out = spike_world
    prog = "\n".join(["say hi $n", "emote nods.", "north"])
    mobprog.program_flow(1, prog, mob, player)
    assert any("says" in l and "hi Tester" in l for l in out)
    assert any("nods." in l for l in out)
    assert mob["room"] == 9002


# -- Phase B: trigger firing ---------------------------------------------------

from world import ITEM_DEFS, MOBPROGS
from item import create_object


def test_percent_trigger_roll_boundary(monkeypatch):
    """percent_trigger fires when number_percent() < atoi(phrase) (cf. p_percent_trigger)."""
    MOB_DEFS._data[9500] = {"short_descr": "a test mob", "keywords": "mob",
                            "level": 1, "mob_triggers": (("random", 9500, "50"),)}
    MOBPROGS[9500] = "* noop"
    fired = []
    monkeypatch.setattr(mobprog, "_run_prog",
                        lambda mob, pv, ch, a1, a2: fired.append(pv))
    mob = {"tpl": 9500}
    try:
        monkeypatch.setattr(mobprog, "_number_percent", lambda: 49)   # 49 < 50 -> fire
        assert mobprog.percent_trigger(mob, None, None, None, "random") is True
        assert fired == [9500]
        del fired[:]
        monkeypatch.setattr(mobprog, "_number_percent", lambda: 50)   # 50 < 50 -> no
        assert mobprog.percent_trigger(mob, None, None, None, "random") is False
        assert fired == []
    finally:
        MOB_DEFS._data.pop(9500, None)
        MOBPROGS.pop(9500, None)


def test_has_trigger_empty_shortcircuit():
    MOB_DEFS._data[9501] = {"short_descr": "x", "keywords": "x", "level": 1}
    try:
        assert mobprog.has_trigger({"tpl": 9501}, "random") is False
        MOB_DEFS._data[9501]["mob_triggers"] = (("speech", 1, "hi"),)
        assert mobprog.has_trigger({"tpl": 9501}, "speech") is True
        assert mobprog.has_trigger({"tpl": 9501}, "random") is False
    finally:
        MOB_DEFS._data.pop(9501, None)


@pytest.fixture
def mp_world(monkeypatch):
    """A room with a player and a trigger-carrying mob; captured act() output."""
    old_rd = dict(ROOM_DEFS._data); old_wr = dict(world.rooms._data)
    old_ch = dict(world.chars); old_md = dict(MOB_DEFS._data)
    old_id = dict(ITEM_DEFS._data); old_mp = dict(MOBPROGS)

    def _room(vnum, exits):
        r = {"name": "Room %d" % vnum, "desc": "x", "exits": exits,
             "items": [], "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
        ROOM_DEFS._data[vnum] = r
        world.rooms._data[vnum] = r
        return r

    _room(9001, {"n": {"to": 9002}})
    _room(9002, {"s": {"to": 9001}})
    MOB_DEFS._data[9405] = {
        "short_descr": "a test guard", "keywords": "guard", "level": 10,
        "default_pos": "stand", "start_pos": "stand",
        # create_mobile inputs (for mpmload)
        "hp_dice": (1, 1, 20), "damage": (1, 4, 2), "armor": (5, 5, 5, 5),
        "hitroll": 5, "race": "Human", "sex": "male", "alignment": 0,
        "size": "medium", "wealth": 0,
        "mob_triggers": (("speech", 6001, "hello"), ("give", 6002, "all"),
                         ("delay", 6003, "100"), ("greet", 6004, "100"),
                         ("bribe", 6006, "50")),
    }
    MOBPROGS[6001] = "say Greetings, $n."
    MOBPROGS[6002] = "\n".join(["mob delay 2", "say Thank you for $O."])
    MOBPROGS[6003] = "say The magic happens now."
    MOBPROGS[6004] = "say Welcome, $n."
    MOBPROGS[6006] = "say Bribe taken."
    ITEM_DEFS._data[9100] = {"short_descr": "a gold ring", "keywords": "ring gold",
                             "type": "treasure", "weight": 1, "value": 0,
                             "wear_flags": {"take": True}, "extra_flags": {}}
    # corpse template (OBJ_VNUM_CORPSE_NPC) so a death-trigger test can raw_kill
    ITEM_DEFS._data[10] = {"short_descr": "corpse", "keywords": "corpse",
                           "type": "corpse_npc", "weight": 0, "value": 0,
                           "extra_flags": {}}

    player = _char_base()
    player.update(id=1, is_npc=False, name="Tester", room=9001, pos="standing",
                  learned={})   # pcdata field the combat path reads directly
    world.chars[1] = player

    mob = _char_base()
    mob.update(id=2, is_npc=True, tpl=9405, name="guard",
               short_descr="a test guard", room=9001, pos="standing",
               mprog_target=None)
    world.chars[2] = mob
    world.rooms._data[9001]["mobs"].append(2)

    out = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))

    yield player, mob, out

    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rd)
    world.rooms._data.clear(); world.rooms._data.update(old_wr)
    world.chars.clear(); world.chars.update(old_ch)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_md)
    ITEM_DEFS._data.clear(); ITEM_DEFS._data.update(old_id)
    MOBPROGS.clear(); MOBPROGS.update(old_mp)


def test_speech_trigger_via_do_say(mp_world):
    player, mob, out = mp_world
    from comm import do_say
    do_say(player, "well hello there")   # phrase "hello" is a substring
    assert any("Greetings, Tester." in l for l in out)


def test_speech_trigger_no_match(mp_world):
    player, mob, out = mp_world
    from comm import do_say
    do_say(player, "goodbye")
    assert not any("Greetings" in l for l in out)


def test_speech_trigger_via_do_tell(mp_world):
    player, mob, out = mp_world
    from comm import do_tell
    do_tell(player, "guard hello there")   # PC tells the NPC -> speech fires
    assert any("Greetings, Tester." in l for l in out)


def test_greet_trigger_on_player_arrival(mp_world):
    player, mob, out = mp_world
    # player starts in 9001 with the mob; move away then back to trigger greet
    from movement import move_char
    move_char(player, "n")          # to 9002 (no mob there)
    del out[:]
    move_char(player, "s")          # back to 9001 -> greet fires
    assert any("Welcome, Tester." in l for l in out)


def test_greet_trigger_gated_on_default_pos(mp_world):
    player, mob, out = mp_world
    mob["pos"] = "sitting"          # not default_pos -> greet suppressed
    from movement import move_char
    move_char(player, "n")
    del out[:]
    move_char(player, "s")
    assert not any("Welcome" in l for l in out)


def test_speech_give_delay_chain(mp_world):
    """Scripted integration: say -> give -> delay follow-up (MOBPROG_PLAN verification)."""
    player, mob, out = mp_world
    from comm import do_say
    from inventory import do_give
    from mobprog import pulse_mob

    # 1) speech
    do_say(player, "hello guard")
    assert any("Greetings, Tester." in l for l in out)

    # 2) give -> give prog arms a 2-tick delay and thanks the player
    ring = create_object(9100)
    player["inv"].append(ring)
    del out[:]
    do_give(player, ["ring", "guard"])
    assert any("Thank you for a gold ring." in l for l in out)
    assert mob["mprog_delay"] == 2         # "mob delay 2" ran

    # 3) delay counts down over pulses; fires the follow-up at zero
    del out[:]
    assert pulse_mob(mob) is False         # 2 -> 1, not yet
    assert mob["mprog_delay"] == 1
    assert pulse_mob(mob) is True          # 1 -> 0, delay prog fires
    assert any("The magic happens now." in l for l in out)


def test_bribe_trigger_via_do_give(mp_world):
    player, mob, out = mp_world
    player["gold"] = 100
    from inventory import do_give
    do_give(player, ["50", "gold", "guard"])   # 50 gold = 5000 silver >= 50
    assert any("Bribe taken." in l for l in out)


def test_random_pulse_fires_at_default_pos(mp_world):
    player, mob, out = mp_world
    # add a random trigger (phrase 100 always rolls < 100) to the template
    MOB_DEFS._data[9405]["mob_triggers"] += (("random", 6005, "100"),)
    MOBPROGS[6005] = "say I wander idly."
    from mobprog import pulse_mob
    assert pulse_mob(mob) is True
    assert any("I wander idly." in l for l in out)
    # not at default position -> pulse is skipped entirely
    mob["pos"] = "sitting"
    del out[:]
    assert pulse_mob(mob) is False
    assert out == []


# -- Phase C: mp-command set ---------------------------------------------------

from mobprog import mob_interpret


def test_mp_mload(mp_world):
    player, mob, out = mp_world
    before = sum(1 for c in world.chars.values()
                 if c.get("is_npc") and c.get("tpl") == 9405)
    mob_interpret(mob, "mload 9405")
    after = sum(1 for c in world.chars.values()
                if c.get("is_npc") and c.get("tpl") == 9405)
    assert after == before + 1
    # the new mob is in the mob's room
    assert len(world.rooms._data[9001]["mobs"]) == 2


def test_mp_oload_to_char_and_room(mp_world):
    player, mob, out = mp_world
    mob_interpret(mob, "oload 9100")          # takeable -> mob inventory
    assert any(o.get("vnum") == 9100 for o in mob["inv"])
    mob_interpret(mob, "oload 9100 0 R")      # forced to the room floor
    assert any(o.get("vnum") == 9100 for o in world.rooms._data[9001]["items"])


def test_mp_purge_room(mp_world):
    player, mob, out = mp_world
    # a second mob and a floor object to purge
    mob_interpret(mob, "mload 9405")
    world.rooms._data[9001]["items"].append(create_object(9100))
    assert len(world.rooms._data[9001]["mobs"]) == 2
    mob_interpret(mob, "purge")               # bare purge: other mobs + objects
    assert world.rooms._data[9001]["mobs"] == [2]   # only the acting mob remains
    assert world.rooms._data[9001]["items"] == []


def test_mp_transfer_player(mp_world):
    player, mob, out = mp_world
    player["room"] = 9002                       # move the player away
    mob_interpret(mob, "transfer Tester")       # no location -> mob's room
    assert player["room"] == 9001


def test_mp_damage_no_retaliation(mp_world):
    player, mob, out = mp_world
    start = player["hit"]
    mob_interpret(mob, "damage Tester 5 5")
    assert player["hit"] < start                # damage applied (amount randomized)
    assert player["fighting"] is None           # self-attacker path: no retaliation
    assert mob["fighting"] is None


def test_mp_force(mp_world):
    player, mob, out = mp_world
    mob_interpret(mob, "force Tester say obey")
    assert any("obey" in l for l in out)        # player was forced to say it


def test_mp_remember_forget(mp_world):
    player, mob, out = mp_world
    mob_interpret(mob, "remember Tester")
    assert mob["mprog_target"] == 1             # stored as char id
    mob_interpret(mob, "forget")
    assert mob["mprog_target"] is None


def test_mp_delay_cancel(mp_world):
    player, mob, out = mp_world
    mob_interpret(mob, "delay 5")
    assert mob["mprog_delay"] == 5
    mob_interpret(mob, "cancel")
    assert mob["mprog_delay"] == -1


def test_mp_call_runs_another_prog(mp_world):
    player, mob, out = mp_world
    MOBPROGS[6003] = "say called prog ran."
    mob_interpret(mob, "call 6003")
    assert any("called prog ran." in l for l in out)


def test_mp_junk(mp_world):
    player, mob, out = mp_world
    mob["inv"].append(create_object(9100))
    mob["inv"].append(create_object(9100))
    mob_interpret(mob, "junk all")
    assert mob["inv"] == []


def test_mp_skipped_command_logs(monkeypatch, mp_world):
    player, mob, out = mp_world
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    mob_interpret(mob, "gforce Tester say hi")   # skipped group command
    assert any("skipped" in m for m in logged)


def test_mp_unknown_command_logs(monkeypatch, mp_world):
    player, mob, out = mp_world
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    mob_interpret(mob, "bogus arg")
    assert any("invalid cmd" in m for m in logged)


# -- Phase C: combat triggers --------------------------------------------------

def test_combat_kill_and_death_triggers(mp_world):
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("kill", 6010, "100"),
                                             ("death", 6011, "100"))
    MOBPROGS[6010] = "say You dare attack me!"
    MOBPROGS[6011] = "say I am slain!"
    # An NPC attacker (create_mobile) keeps the death path off player pcdata/XP
    # (gain_exp early-returns for NPC killers).  It is never itself the victim,
    # so its own kill/death triggers never fire.
    from mob import create_mobile
    attacker = create_mobile(9405)
    attacker["id"] = 3
    attacker["room"] = 9001
    world.chars[3] = attacker
    world.rooms._data[9001]["mobs"].append(3)
    from combat import damage, DAM_NONE
    from config import TYPE_UNDEFINED
    mob["hit"] = 100; mob["max_hit"] = 100
    # KILL: victim engages when first attacked
    damage(attacker, mob, 5, TYPE_UNDEFINED, DAM_NONE, False)
    assert any("You dare attack me!" in l for l in out)
    # DEATH: lethal blow fires the death prog before extraction
    del out[:]
    damage(attacker, mob, 1000, TYPE_UNDEFINED, DAM_NONE, False)
    assert any("I am slain!" in l for l in out)


def test_combat_fight_and_hpcnt_triggers(mp_world):
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("fight", 6012, "100"),
                                             ("hpcnt", 6013, "50"))
    MOBPROGS[6012] = "say Feel my wrath!"
    MOBPROGS[6013] = "say I am wounded!"
    from combat import set_fighting, violence_update
    player["hit"] = 500; player["max_hit"] = 500
    mob["hit"] = 40; mob["max_hit"] = 100        # 40% < 50 -> hpcnt fires
    set_fighting(mob, player)
    set_fighting(player, mob)
    violence_update(player)
    assert any("Feel my wrath!" in l for l in out)
    assert any("I am wounded!" in l for l in out)
