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
    m = _char_base()
    m.update({"name": "big guard", "short_descr": "the big guard",
              "is_npc": True, "sex": "male", "level": 10,
              "mprog_target": None, "affected_by": {}})
    m.update(kw)
    return m


def _pc(**kw):
    c = _char_base()
    c.update({"name": "John Doe", "short_descr": None, "is_npc": False,
              "sex": "female", "level": 5, "affected_by": {}})
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


def test_cmd_eval_world_presence_checks(mp_world):
    """mobhere/objhere by vnum or name; mobexists/objexists (programs.c:448-461)."""
    player, mob, out = mp_world
    def ce(check, args):
        return mobprog.cmd_eval(check, args, mob, player, None, None, None, 1)
    assert ce("mobhere", "9405")            # own template counts (NPC in room)
    assert not ce("mobhere", "9999")
    assert ce("mobhere", "guard")
    assert ce("mobhere", "tester")          # PCs match the name form
    assert not ce("mobhere", "dragon")
    assert ce("mobexists", "tester")
    assert not ce("mobexists", "dragon")
    # a ring on this room's floor, then on a remote floor
    world.rooms._data[9001]["items"].append(9100)
    assert ce("objhere", "9100")
    assert ce("objhere", "ring")
    world.rooms._data[9001]["items"].remove(9100)
    assert not ce("objhere", "ring")
    world.rooms._data[9002]["items"].append(9100)
    assert ce("objexists", "ring")
    world.rooms._data[9002]["items"].remove(9100)
    assert not ce("objexists", "ring")


def test_get_char_room_self_and_can_see_gate(mp_world):
    """'self' resolves to the acting mob; invisible chars are skipped (handler.c:1886)."""
    player, mob, out = mp_world
    assert mobprog._get_char_room(mob, "self") is mob
    assert mobprog._get_char_room(mob, "tester") is player
    player["affected_by"]["invisible"] = True
    assert mobprog._get_char_room(mob, "tester") is None
    assert mobprog._get_char_world(mob, "tester") is None
    del player["affected_by"]["invisible"]


def test_find_location_world_wide(mp_world):
    """A char name anywhere in the loaded world resolves to its room (act_wiz.c:721)."""
    player, mob, out = mp_world
    player["room"] = 9002
    assert mobprog._find_location(mob, "tester") == 9002
    player["room"] = 9001


def test_cmd_eval_clan_is_faithfully_false():
    # 'clan' is implemented (PROGS_PLAN Phase 3) as faithful-False: no clan
    # system is ported, so no char can ever match one
    mob = _mob()
    assert mobprog.cmd_eval("clan", "$n whatever", mob, _pc(), None, None, None, 1) is False


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
    mobprog._call_depth = mobprog.MAX_CALL_LEVEL
    try:
        mobprog.program_flow(1, "say x", _mob(), None)
    finally:
        mobprog._call_depth = 0
    assert calls == []
    assert any("max call level" in m for m in errs)


def test_trigger_cascade_bounded(monkeypatch):
    """Reentrant trigger cascades (not via 'mob call') hit the global depth cap."""
    errs = []
    entries = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: errs.append(m))

    # _dispatch that simulates a prog command synchronously firing another prog
    def reenter(prog_vnum, mob, ctrl, expanded):
        entries.append(prog_vnum)
        mobprog.program_flow(prog_vnum + 1, "say again", mob, None)
    monkeypatch.setattr(mobprog, "_dispatch", reenter)

    mobprog.program_flow(1, "say x", _mob(), None)
    assert mobprog._call_depth == 0                     # counter unwound
    assert len(entries) == mobprog.MAX_CALL_LEVEL       # bounded, not infinite
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
    # deterministic percent roll: phrase-"100" triggers roll 1stMud's
    # number_percent() < 100, a real 1% miss that flakes the suite
    monkeypatch.setattr(mobprog, "_number_percent", lambda: 1)

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


def test_mp_refund_returns_bribe(mp_world):
    """[PRIMESUD] 'mob refund' repays the stashed bribe in its original
    denomination; one-shot (stash popped)."""
    player, mob, out = mp_world
    player["gold"] = 100
    MOBPROGS[6006] = "\n".join([
        "if isdelay $i",
        "  mob refund $n",
        "else",
        "  mob delay 1",
        "endif"])
    from inventory import do_give
    do_give(player, ["50", "gold", "guard"])   # first bribe kept, delay armed
    assert player["gold"] == 50 and mob.get("gold", 0) == 50
    do_give(player, ["30", "gold", "guard"])   # isdelay -> refunded
    assert player["gold"] == 50 and mob.get("gold", 0) == 50
    assert mob.get("mprog_bribe") is None      # stash consumed
    assert any("returns your 30 gold" in l for l in out)


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


def test_mp_gforce_reaches_group(mp_world):
    # gforce is implemented (PROGS_PLAN Phase 3): the victim's whole group
    # acts; a solo player is a group of one
    player, mob, out = mp_world
    mob_interpret(mob, "gforce Tester say hi")
    assert any("hi" in l for l in out)


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


# -- Phase D: content pilot (the authored Mud School acolyte demo prog) ---------
#
# End-to-end validation of the [PRIMESUD] demo content authored in
# areas/school.are (M mob trailers + #MOBPROGS section): the
# acolyte of Zump (mob 3700) greets arriving players, rewards the first coin
# donation per mob instance, and returns donated items.  Loads the *real* area
# file so the mob_triggers tuple + MOBPROGS dict are exercised exactly as
# world.py loads them; the actors are staged in a synthetic room to stay isolated.


@pytest.fixture
def school_world(monkeypatch):
    """Real school area data loaded; acolyte 3700 + a player staged in one room."""
    snap = {
        "chars": dict(world.chars), "rooms": dict(world.rooms._data),
        "loaded": set(world._LOADED_AREAS), "room_defs": dict(ROOM_DEFS._data),
        "mob_defs": dict(MOB_DEFS._data), "item_defs": dict(ITEM_DEFS._data),
        "door_defs": dict(world.DOOR_DEFS), "areas": list(world.areas),
        "area_defs": list(world.AREA_DEFS), "vnum_ranges": list(world._VNUM_RANGES),
        "tag_to_file": dict(world._TAG_TO_FILE), "tag_to_name": dict(world._TAG_TO_NAME),
        "ready": world._WORLD_READY, "mobprogs": dict(MOBPROGS),
    }
    world.init_world()
    _ = MOB_DEFS[3700]          # lazy-load Mud School -> MOBILES/OBJECTS/MOBPROGS

    # synthetic single-room stage (avoids pulling school's whole room graph)
    room = {"name": "Test Yard", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "mud_school", "flags": {}, "sector": "inside"}
    ROOM_DEFS._data[9001] = room
    world.rooms._data[9001] = room
    # a gift item for the give trigger
    ITEM_DEFS._data[9100] = {"short_descr": "a gold ring", "keywords": "ring gold",
                             "type": "treasure", "weight": 1, "value": 0,
                             "wear_flags": {"take": True}, "extra_flags": {}}

    player = _char_base()
    player.update(id=1, is_npc=False, name="Tester", room=9001, pos="standing",
                  level=3, silver=2, learned={})
    world.chars[1] = player

    from mob import create_mobile
    mob = create_mobile(3700)
    mob.update(id=2, room=9001, mprog_target=None)
    world.chars[2] = mob
    room["mobs"].append(2)

    # deterministic percent roll so the greet trigger (phrase "100") fires
    monkeypatch.setattr(mobprog, "_number_percent", lambda: 1)
    out = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))

    yield player, mob, out

    world.chars.clear(); world.chars.update(snap["chars"])
    world.rooms._data.clear(); world.rooms._data.update(snap["rooms"])
    world._LOADED_AREAS.clear(); world._LOADED_AREAS.update(snap["loaded"])
    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(snap["room_defs"])
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(snap["mob_defs"])
    ITEM_DEFS._data.clear(); ITEM_DEFS._data.update(snap["item_defs"])
    world.DOOR_DEFS.clear(); world.DOOR_DEFS.update(snap["door_defs"])
    world.areas = snap["areas"]; world.AREA_DEFS[:] = snap["area_defs"]
    world._VNUM_RANGES[:] = snap["vnum_ranges"]
    world._TAG_TO_FILE.clear(); world._TAG_TO_FILE.update(snap["tag_to_file"])
    world._TAG_TO_NAME.clear(); world._TAG_TO_NAME.update(snap["tag_to_name"])
    world._WORLD_READY = snap["ready"]
    MOBPROGS.clear(); MOBPROGS.update(snap["mobprogs"])


def test_school_demo_data_loaded(school_world):
    """The authored triggers + progs ride the real area file as world loads it."""
    trigs = MOB_DEFS[3700].get("mob_triggers")
    assert "zump" in MOB_DEFS[3700]["keywords"]
    assert ("greet", 3790, "100") in trigs
    assert ("bribe", 3791, "1") in trigs
    assert ("give", 3792, "all") in trigs
    assert MOBPROGS.get(3790) and MOBPROGS.get(3791) and MOBPROGS.get(3792)


def test_school_demo_full_interaction(school_world, monkeypatch):
    """Greet, one-time coin reward, and unwanted-item return work end to end."""
    player, mob, out = school_world
    import inventory
    from mobprog import greet_trigger

    # 1) entering the room prompts the player without requiring "say help"
    greet_trigger(player)
    assert any("Welcome to Mud School, Tester." in l for l in out)
    assert any("one silver coin is enough" in l for l in out)

    # 2) first coin donation rewards this low-level student with one gold coin
    del out[:]
    # Money contributes zero carry count, so a nominally full player can receive it.
    with monkeypatch.context() as m:
        m.setattr(inventory, "can_carry_n", lambda ch: 0)
        picks = iter((0, 0))  # silver, then acolyte
        m.setattr(inventory, "pick_from", lambda title, options: next(picks))
        m.setattr(inventory.terminal.tr, "input",
                  lambda *args, **kwargs: "1")
        # picker resolves to the typed coin form (full recipient keywords --
        # the typed target lookup joins args[2:])
        assert inventory.do_give(player, []) == (
            "give 1 silver " + MOB_DEFS[3700]["keywords"])
    assert player["silver"] == 1 and mob["silver"] == 1
    assert any("students this fund was made for" in l for l in out)
    assert player["gold"] == 1
    assert not any(o.get("vnum") == 2 for o in player["inv"])
    assert not any(o.get("vnum") == 2 for o in mob["inv"])
    assert not any(o.get("vnum") == 2 for o in world.rooms._data[9001]["items"])
    assert mob["mprog_delay"] == 1

    # 3) marker suppresses repeat rewards for this mob instance
    del out[:]
    inventory.do_give(player, ["1", "silver", "zump"])
    assert any("already shown your generosity" in l for l in out)
    assert player["gold"] == 1
    assert mobprog.pulse_mob(mob) is False
    assert mob["mprog_delay"] == 1

    # 4) non-money gifts are politely returned
    ring = create_object(9100)
    player["inv"].append(ring)
    del out[:]
    inventory.do_give(player, ["ring", "zump"])
    assert ring in player["inv"] and ring not in mob["inv"]
    assert any("hardship fund accepts coins only" in l for l in out)


def test_idle_triggerless_mob_short_circuits(monkeypatch):
    """A room of trigger-less mobs never reaches prog execution on the pulse.

    has_trigger's empty-tuple early-out is the guard that keeps the 99% of
    mobs with no triggers cheap; assert the pulse touches no program at all.
    """
    MOB_DEFS._data[9600] = {"short_descr": "a plain rat", "keywords": "rat",
                            "level": 1, "default_pos": "stand"}
    ran = []
    monkeypatch.setattr(mobprog, "_run_prog",
                        lambda mob, pv, ch, a1, a2: ran.append(pv))
    try:
        mobs = [{"tpl": 9600, "pos": "standing", "mprog_delay": 0}
                for _ in range(50)]
        for m in mobs:
            assert mobprog.pulse_mob(m) is False
        assert ran == []                                 # no prog ever fetched/run
    finally:
        MOB_DEFS._data.pop(9600, None)


# -- Phase E: act trigger + exit/exall triggers + MOBtrigger latch --------------


def test_mob_speaker_fires_no_speech_trigger(mp_world):
    """A mob's say fires no speech triggers (1stMud !IsNPC gate) -> no mob-mob recursion."""
    player, mob, out = mp_world
    from comm import do_say
    b = _char_base()
    b.update(id=3, is_npc=True, tpl=9405, name="guard", short_descr="a test guard",
             room=9001, pos="standing", mprog_target=None)
    world.chars[3] = b
    world.rooms._data[9001]["mobs"].append(3)
    do_say(mob, "hello there")             # mob A speaks -> phrase "hello" ignored
    assert not any("Greetings" in l for l in out)
    # sanity: the same words from the player still fire the speech trigger
    do_say(player, "hello there")
    assert any("Greetings, Tester." in l for l in out)


def test_give_announce_does_not_fire_act_trigger(mp_world):
    """do_give latches MOBtrigger off: the 'gives you' text can't trip an act trigger.

    The mob still reacts through its give trigger -- only the spurious act-on-
    announce path is suppressed (cf. do_give latch, act_obj.c:845).
    """
    player, mob, out = mp_world
    # act phrase "gives" would match the give announcement text if unlatched
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6040, "gives"),)
    MOBPROGS[6040] = "say ACT ON GIVE"
    from inventory import do_give
    ring = create_object(9100)
    player["inv"].append(ring)
    do_give(player, ["ring", "guard"])
    assert not any("ACT ON GIVE" in l for l in out)        # announce latched off
    assert any("Thank you for a gold ring." in l for l in out)   # give trigger fired


def test_act_trigger_fires_on_room_text(mp_world):
    """A room mob reacts to act() text whose phrase it carries (cf. TRIG_ACT)."""
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6020, "dances"),)
    MOBPROGS[6020] = "say I see you dancing!"
    handler.act("$n dances a jig.", player, None, None, handler.TO_ROOM)
    assert any("I see you dancing!" in l for l in out)


def test_act_trigger_no_phrase_match(mp_world):
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6020, "dances"),)
    MOBPROGS[6020] = "say I see you dancing!"
    handler.act("$n sits down quietly.", player, None, None, handler.TO_ROOM)
    assert not any("dancing" in l for l in out)


def test_act_trigger_excludes_the_actor(mp_world):
    """A mob's own act output must not fire its own act trigger (actor skipped)."""
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6020, "dances"),)
    MOBPROGS[6020] = "say self loop!"
    handler.act("$n dances.", mob, None, None, handler.TO_ROOM)   # mob is subject
    assert not any("self loop!" in l for l in out)


def test_emote_does_not_fire_act_trigger(mp_world):
    """do_emote latches MOBtrigger off: player emote text can't trip mob progs."""
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6020, "waves"),)
    MOBPROGS[6020] = "say caught the wave!"
    from comm import do_emote
    do_emote(player, "waves grandly")
    assert not any("caught the wave!" in l for l in out)


def test_act_trigger_latch_bounds_reentry(mp_world):
    """A prog fired by an act trigger cannot fire a second-order act trigger.

    The latch is held off for the whole dispatch, a hard recursion bound
    (stricter than 1stMud) suited to the Prime's small stack.
    """
    player, mob, out = mp_world
    # guard A (tpl 9405) reacts to "coughs" by relaying a line...
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6020, "coughs"),)
    MOBPROGS[6020] = "say aaah relayed"
    # ...guard B (tpl 9406) would catch A's "relayed" -- but the latch suppresses it.
    MOB_DEFS._data[9406] = dict(MOB_DEFS._data[9405])
    MOB_DEFS._data[9406]["mob_triggers"] = (("act", 6021, "relayed"),)
    MOBPROGS[6021] = "say SECOND ORDER"
    b = _char_base()
    b.update(id=3, is_npc=True, tpl=9406, name="guard", short_descr="a test guard",
             room=9001, pos="standing", mprog_target=None)
    world.chars[3] = b
    world.rooms._data[9001]["mobs"].append(3)
    handler.act("$n coughs loudly.", player, None, None, handler.TO_ROOM)
    assert any("aaah relayed" in l for l in out)          # A fired
    assert not any("SECOND ORDER" in l for l in out)      # B suppressed by the latch


def test_act_trigger_skips_extracted_recipient(mp_world):
    """A prog that purges a later act-trigger recipient must not fire it (extraction guard)."""
    player, mob, out = mp_world
    # mob A (id 2, tpl 9405): on "coughs", purges the victim mob
    MOB_DEFS._data[9405]["mob_triggers"] += (("act", 6050, "coughs"),)
    MOBPROGS[6050] = "mob purge victim"
    # mob B (id 3, tpl 9406, keyword "victim") would shout on the same act
    MOB_DEFS._data[9406] = dict(MOB_DEFS._data[9405])
    MOB_DEFS._data[9406]["keywords"] = "victim"
    MOB_DEFS._data[9406]["mob_triggers"] = (("act", 6051, "coughs"),)
    MOBPROGS[6051] = "say B FIRED"
    b = _char_base()
    b.update(id=3, is_npc=True, tpl=9406, name="victim", short_descr="a hapless victim",
             keywords="victim", room=9001, pos="standing", mprog_target=None)
    world.chars[3] = b
    world.rooms._data[9001]["mobs"].append(3)
    handler.act("$n coughs.", player, None, None, handler.TO_ROOM)
    assert 3 not in world.chars                     # B purged by A's prog
    assert not any("B FIRED" in l for l in out)     # never fired on the dead ref


def test_exit_trigger_fires_and_aborts_move(mp_world):
    """An exit trigger on the matching door number fires and cancels the move."""
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("exit", 6030, "0"),)   # 0 = north
    MOBPROGS[6030] = "say Halt!  You shall not pass north."
    from movement import move_char
    move_char(player, "n")
    assert any("Halt!  You shall not pass north." in l for l in out)
    assert player["room"] == 9001                         # move aborted


def test_exit_trigger_wrong_direction_allows_move(mp_world):
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("exit", 6030, "1"),)   # east only
    MOBPROGS[6030] = "say wrong way"
    from movement import move_char
    move_char(player, "n")                                # north != east
    assert not any("wrong way" in l for l in out)
    assert player["room"] == 9002


def test_exit_trigger_gated_on_pos_and_sight(mp_world):
    """A non-default-position mob does not fire exit (unlike exall)."""
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("exit", 6030, "0"),)
    MOBPROGS[6030] = "say blocked"
    mob["pos"] = "sitting"                                # not default_pos
    from movement import move_char
    move_char(player, "n")
    assert not any("blocked" in l for l in out)
    assert player["room"] == 9002                         # move proceeds


def test_exall_trigger_fires_regardless_of_pos(mp_world):
    player, mob, out = mp_world
    MOB_DEFS._data[9405]["mob_triggers"] += (("exall", 6031, "0"),)
    MOBPROGS[6031] = "say All shall be stopped."
    mob["pos"] = "sitting"                                # exall ignores pos + sight
    from movement import move_char
    move_char(player, "n")
    assert any("All shall be stopped." in l for l in out)
    assert player["room"] == 9001                         # aborted
