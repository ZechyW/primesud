"""Tests for the tri-modal prog interpreter (PROGS_PLAN Phase 1).

Obj/room program flow (cf. 1stMud programs.c cmd_eval_obj/_room,
expand_arg_other) and the op/rp command tables (cf. prog_cmds.c
obj_cmd_table/room_cmd_table).
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

import handler
import mobprog
import world
from handler import _char_base
from world import ITEM_DEFS, MOB_DEFS, MOBPROGS, OBJPROGS, ROOMPROGS, ROOM_DEFS


@pytest.fixture
def prog_world(monkeypatch):
    """Two rooms, a player, a guard mob, and a floor obj; captured output."""
    old_rd = dict(ROOM_DEFS._data); old_wr = dict(world.rooms._data)
    old_ch = dict(world.chars); old_md = dict(MOB_DEFS._data)
    old_id = dict(ITEM_DEFS._data); old_mp = dict(MOBPROGS)
    old_op = dict(OBJPROGS); old_rp = dict(ROOMPROGS)
    old_fx = set(world.FIGHTERS)

    def _room(vnum, exits):
        r = {"name": "Room %d" % vnum, "desc": "x", "exits": exits,
             "items": [], "mobs": [], "area": "test", "flags": {},
             "sector": "inside"}
        ROOM_DEFS._data[vnum] = r
        world.rooms._data[vnum] = r
        return r

    _room(9001, {"n": {"to": 9002}})
    _room(9002, {"s": {"to": 9001}})
    MOB_DEFS._data[9405] = {
        "short_descr": "a test guard", "keywords": "guard", "level": 10,
        "default_pos": "stand", "start_pos": "stand",
        "hp_dice": (1, 1, 20), "damage": (1, 4, 2), "armor": (5, 5, 5, 5),
        "hitroll": 5, "race": "Human", "sex": "male", "alignment": 0,
        "size": "medium", "wealth": 0,
    }
    ITEM_DEFS._data[9100] = {"short_descr": "a humming sword",
                             "keywords": "sword humming", "type": "weapon",
                             "level": 42, "weight": 1, "value": 0,
                             "wear_flags": {"take": True}, "extra_flags": {}}
    ITEM_DEFS._data[9101] = {"short_descr": "a copper coin",
                             "keywords": "coin copper", "type": "treasure",
                             "weight": 1, "value": 0,
                             "wear_flags": {"take": True}, "extra_flags": {}}

    player = _char_base()
    player.update(id=1, is_npc=False, name="Tester", room=9001,
                  pos="standing", level=5, learned={})
    world.chars[1] = player

    mob = _char_base()
    mob.update(id=2, is_npc=True, tpl=9405, name="guard",
               short_descr="a test guard", room=9001, pos="standing",
               mprog_target=None)
    world.chars[2] = mob
    world.rooms._data[9001]["mobs"].append(2)

    sword = {"vnum": 9100}
    world.rooms._data[9001]["items"].append(sword)

    out = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))
    monkeypatch.setattr(mobprog, "_number_percent", lambda: 1)

    yield player, mob, sword, out

    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rd)
    world.rooms._data.clear(); world.rooms._data.update(old_wr)
    world.chars.clear(); world.chars.update(old_ch)
    world.FIGHTERS.clear(); world.FIGHTERS.update(old_fx)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_md)
    ITEM_DEFS._data.clear(); ITEM_DEFS._data.update(old_id)
    MOBPROGS.clear(); MOBPROGS.update(old_mp)
    OBJPROGS.clear(); OBJPROGS.update(old_op)
    ROOMPROGS.clear(); ROOMPROGS.update(old_rp)


def _octx(sword, room=9001, carrier=None):
    return {"obj": sword, "room": room, "carrier": carrier}


@pytest.fixture
def errs(monkeypatch):
    logged = []
    monkeypatch.setattr(mobprog, "dbg", lambda m: logged.append(m))
    return logged


# -- program_flow tri-mode routing ---------------------------------------------

def test_objprog_echo_reaches_player(prog_world):
    player, mob, sword, out = prog_world
    mobprog.program_flow(100, "obj echo The sword hums ominously.",
                         None, player, obj=_octx(sword))
    assert any("The sword hums ominously." in l for l in out)


def test_roomprog_echo_reaches_player(prog_world):
    player, mob, sword, out = prog_world
    mobprog.program_flow(101, "room echo The walls glow softly.",
                         None, player, room=9001)
    assert any("The walls glow softly." in l for l in out)


def test_raw_command_in_objprog_bug_skips(prog_world, errs):
    player, mob, sword, out = prog_world
    mobprog.program_flow(100, "say I should not speak", None, player,
                         obj=_octx(sword))
    assert not any("speak" in l for l in out)
    assert any("non-MOBprog" in m for m in errs)


def test_mob_command_in_roomprog_bug_skips(prog_world, errs):
    player, mob, sword, out = prog_world
    mobprog.program_flow(101, "mob echo nope", None, player, room=9001)
    assert not any("nope" in l for l in out)
    assert any("mob command in non MOBprog" in m for m in errs)


def test_room_command_in_mobprog_bug_skips(prog_world, errs):
    player, mob, sword, out = prog_world
    mobprog.program_flow(102, "room echo nope", mob, player)
    assert not any("nope" in l for l in out)
    assert any("room command in non ROOMprog" in m for m in errs)


def test_program_flow_requires_exactly_one_origin(prog_world, errs):
    player, mob, sword, out = prog_world
    mobprog.program_flow(103, "obj echo x", mob, player, obj=_octx(sword))
    assert not out
    assert any("origins" in m for m in errs)


# -- if-checks (cf. cmd_eval_obj/_room) ----------------------------------------

def test_objprog_ifcheck_dollar_i_is_the_obj(prog_world):
    player, mob, sword, out = prog_world
    code = "if name $i sword\nobj echo match\nendif"
    mobprog.program_flow(100, code, None, player, obj=_octx(sword))
    assert any("Match" in l for l in out)


def test_roomprog_ifcheck_dollar_i_bugs_false(prog_world, errs):
    player, mob, sword, out = prog_world
    code = "if name $i sword\nroom echo match\nendif"
    mobprog.program_flow(101, code, None, player, room=9001)
    assert not any("Match" in l for l in out)
    assert any("$i in roomprog" in m for m in errs)


def test_roomprog_ifcheck_dollar_n(prog_world):
    player, mob, sword, out = prog_world
    code = "if name $n Tester\nroom echo hello resident\nendif"
    mobprog.program_flow(101, code, None, player, room=9001)
    assert any("Hello resident" in l for l in out)


def test_objprog_ifcheck_mobhere_vnum(prog_world):
    player, mob, sword, out = prog_world
    code = "if mobhere 9405\nobj echo guard present\nendif"
    mobprog.program_flow(100, code, None, player, obj=_octx(sword))
    assert any("Guard present" in l for l in out)


def test_objprog_target_latches_on_first_eval(prog_world):
    player, mob, sword, out = prog_world
    code = "if rand 100\nobj echo hi $q\nendif"
    mobprog.program_flow(100, code, None, player, obj=_octx(sword))
    assert sword["oprog_target"] == 1
    assert any("Hi Tester" in l for l in out)


def test_objprog_isvisible_is_syntax_error(prog_world, errs):
    player, mob, sword, out = prog_world
    code = "if isvisible $n\nobj echo seen\nendif"
    mobprog.program_flow(100, code, None, player, obj=_octx(sword))
    assert not any("seen" in l for l in out)
    assert any("syntax error" in m for m in errs)


def test_carried_obj_room_follows_carrier(prog_world):
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    player["room"] = 9002
    octx = _octx(sword, room=9001, carrier=player)
    code = "if room $i == 9002\nobj echo travelling\nendif"
    mobprog.program_flow(100, code, None, player, obj=octx)
    assert any("Travelling" in l for l in out)


# -- expand_arg_other ----------------------------------------------------------

def test_expand_other_obj_codes(prog_world):
    player, mob, sword, out = prog_world
    octx = _octx(sword)
    got = mobprog.expand_arg_other("$i / $I / $n", "obj", octx, player,
                                   None, None, None)
    assert got == "sword / a humming sword / Tester"


def test_expand_other_mob_pronoun_codes_are_bugs(prog_world, errs):
    player, mob, sword, out = prog_world
    got = mobprog.expand_arg_other("$j$k$l", "obj", _octx(sword), player,
                                   None, None, None)
    assert got == "<@@@><@@@><@@@>"
    assert len(errs) == 3


def test_expand_other_room_dollar_i_is_bug(prog_world, errs):
    player, mob, sword, out = prog_world
    got = mobprog.expand_arg_other("$i", "room", 9001, player, None, None, None)
    assert got == "<@@@>"
    assert errs


# -- op-commands ---------------------------------------------------------------

def test_op_delay_and_cancel_state(prog_world):
    player, mob, sword, out = prog_world
    octx = _octx(sword)
    mobprog.obj_interpret(octx, "delay 5")
    assert sword["oprog_delay"] == 5
    mobprog.obj_interpret(octx, "cancel")
    assert sword["oprog_delay"] == -1


def test_op_remember_and_forget(prog_world):
    player, mob, sword, out = prog_world
    octx = _octx(sword)
    mobprog.obj_interpret(octx, "remember Tester")
    assert sword["oprog_target"] == 1
    mobprog.obj_interpret(octx, "forget")
    assert sword["oprog_target"] is None


def test_op_goto_moves_obj_and_updates_ctx(prog_world):
    player, mob, sword, out = prog_world
    octx = _octx(sword)
    mobprog.obj_interpret(octx, "goto 9002")
    assert sword not in world.rooms._data[9001]["items"]
    assert sword in world.rooms._data[9002]["items"]
    assert octx["room"] == 9002


def test_op_attrib_sets_instance_fields(prog_world):
    player, mob, sword, out = prog_world
    octx = _octx(sword)
    # target level condition v0 v1 v2 v3 v4; +2 applies to Tester's level (5)
    mobprog.obj_interpret(octx, "attrib Tester +2 none 1 2 3 4 5")
    assert sword["level"] == 7
    assert sword["condition"] == 0
    assert sword["values"] == (1, 2, 3, 4, 5)


def test_op_attrib_bad_slot_aborts_all_writes(prog_world, errs):
    player, mob, sword, out = prog_world
    mobprog.obj_interpret(_octx(sword), "attrib Tester 10 none 1 2 3 4 bogus")
    assert "level" not in sword
    assert errs


def test_op_call_runs_objprog(prog_world):
    player, mob, sword, out = prog_world
    OBJPROGS[7002] = "obj echo nested call fired"
    mobprog.program_flow(100, "obj call 7002", None, player, obj=_octx(sword))
    assert any("Nested call fired" in l for l in out)


def test_op_purge_spares_own_obj(prog_world):
    player, mob, sword, out = prog_world
    coin = {"vnum": 9101}
    world.rooms._data[9001]["items"].append(coin)
    mobprog.obj_interpret(_octx(sword), "purge")
    items = world.rooms._data[9001]["items"]
    assert sword in items and coin not in items
    assert 2 not in world.rooms._data[9001]["mobs"]      # guard purged


def test_op_damage_all_noop_without_carrier(prog_world):
    player, mob, sword, out = prog_world
    hp = player["hit"]
    # bug-faithful: floor obj (no carrier) -> `damage all` hits nobody
    mobprog.obj_interpret(_octx(sword), "damage all 5 5")
    assert player["hit"] == hp


def test_op_damage_all_spares_carrier(prog_world):
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    php, mhp = player["hit"], mob["hit"]
    mobprog.obj_interpret(_octx(sword, carrier=player), "damage all 5 5")
    # damage() applies its own reduction/variance pipeline; the gate under
    # test is only who gets hit
    assert player["hit"] == php
    assert mob["hit"] < mhp


def test_op_unknown_command_logs(prog_world, errs):
    player, mob, sword, out = prog_world
    mobprog.obj_interpret(_octx(sword), "frobnicate now")
    assert any("invalid cmd" in m for m in errs)


# -- rp-commands ---------------------------------------------------------------

def test_rp_force_all_forces_player(prog_world):
    player, mob, sword, out = prog_world
    mobprog.room_interpret(9001, "force all say compelled words")
    assert any("compelled words" in l for l in out)


def test_rp_transfer_moves_player(prog_world):
    player, mob, sword, out = prog_world
    mobprog.room_interpret(9001, "transfer Tester 9002")
    assert player["room"] == 9002


def test_rp_delay_state_on_room(prog_world):
    player, mob, sword, out = prog_world
    mobprog.room_interpret(9001, "delay 3")
    assert world.rooms._data[9001]["rprog_delay"] == 3
    mobprog.room_interpret(9001, "cancel")
    assert world.rooms._data[9001]["rprog_delay"] == -1


def test_rp_damage_all_hits_everyone(prog_world):
    player, mob, sword, out = prog_world
    php, mhp = player["hit"], mob["hit"]
    mobprog.room_interpret(9001, "damage all 5 5")
    # damage() applies its own reduction/variance pipeline; the gate under
    # test is only who gets hit
    assert player["hit"] < php
    assert mob["hit"] < mhp


def test_rp_oload_requires_level_arg(prog_world, errs):
    player, mob, sword, out = prog_world
    before = len(world.rooms._data[9001]["items"])
    mobprog.room_interpret(9001, "oload 9101")
    assert len(world.rooms._data[9001]["items"]) == before
    assert any("rpoload bad syntax" in m for m in errs)
    mobprog.room_interpret(9001, "oload 9101 1")
    assert len(world.rooms._data[9001]["items"]) == before + 1


def test_rp_asound_heard_in_adjacent_room(prog_world):
    player, mob, sword, out = prog_world
    player["room"] = 9002
    mobprog.room_interpret(9001, "asound A low rumble echoes.")
    assert any("A low rumble echoes." in l for l in out)


# -- fire seams (PROGS_PLAN Phase 2) -------------------------------------------

def test_get_fires_obj_and_room_get_triggers(prog_world):
    import inventory
    player, mob, sword, out = prog_world
    ITEM_DEFS._data[9100]["obj_triggers"] = (("get", 9308, "100"),)
    OBJPROGS[9308] = "obj echo You feel a hum."
    world.rooms._data[9001]["room_triggers"] = (("get", 9309, "all"),)
    ROOMPROGS[9309] = "room echo The room hums too."
    inventory.do_get(player, ["sword"])
    assert sword in player["inv"]
    assert any("You feel a hum." in l for l in out)
    assert any("The room hums too." in l for l in out)


def test_drop_fires_obj_and_room_drop_triggers(prog_world):
    import inventory
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    ITEM_DEFS._data[9100]["obj_triggers"] = (("drop", 9310, "100"),)
    OBJPROGS[9310] = "obj echo Do not drop me!"
    world.rooms._data[9001]["room_triggers"] = (("drop", 9311, "sword"),)
    ROOMPROGS[9311] = "room echo Clatter."
    inventory.do_drop(player, ["sword"])
    assert sword in world.rooms._data[9001]["items"]
    assert any("Do not drop me!" in l for l in out)
    assert any("Clatter." in l for l in out)


def test_drop_prog_moving_obj_skips_melt(prog_world):
    import inventory
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    ITEM_DEFS._data[9100]["extra_flags"] = {"melt_drop": True}
    ITEM_DEFS._data[9100]["obj_triggers"] = (("drop", 9312, "100"),)
    OBJPROGS[9312] = "obj goto 9002"
    inventory.do_drop(player, ["sword"])
    # the prog relocated the obj; the melt_drop branch must not fire
    assert sword in world.rooms._data[9002]["items"]
    assert not any("dissolves" in l for l in out)


def test_give_fires_obj_give_with_obj_as_arg1(prog_world):
    import inventory
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    ITEM_DEFS._data[9100]["obj_triggers"] = (("give", 9307, "100"),)
    OBJPROGS[9307] = "obj echo Given: $o"
    inventory.do_give(player, ["sword", "guard"])
    assert sword in mob["inv"]
    assert any("Given: sword" in l for l in out)


def test_exall_objprog_aborts_move(prog_world):
    import movement
    player, mob, sword, out = prog_world
    ITEM_DEFS._data[9100]["obj_triggers"] = (("exall", 9301, "0"),)
    OBJPROGS[9301] = "obj echo A force stops you."
    movement.move_char(player, "n")
    assert player["room"] == 9001
    assert any("A force stops you." in l for l in out)


def test_exall_roomprog_aborts_move(prog_world):
    import movement
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["room_triggers"] = (("exall", 9302, "0"),)
    ROOMPROGS[9302] = "room echo The room bars your way."
    movement.move_char(player, "n")
    assert player["room"] == 9001
    assert any("The room bars your way." in l for l in out)


def test_grall_roomprog_fires_on_entry(prog_world):
    import movement
    player, mob, sword, out = prog_world
    world.rooms._data[9002]["room_triggers"] = (("grall", 9303, "100"),)
    ROOMPROGS[9303] = "room echo You feel at peace."
    movement.move_char(player, "n")
    assert player["room"] == 9002
    assert any("You feel at peace." in l for l in out)


def test_grall_objprog_fires_on_entry(prog_world):
    import movement
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    world.rooms._data[9002]["items"].append(sword)
    ITEM_DEFS._data[9100]["obj_triggers"] = (("grall", 9304, "100"),)
    OBJPROGS[9304] = "obj echo The sword glints at you."
    movement.move_char(player, "n")
    assert player["room"] == 9002
    assert any("The sword glints at you." in l for l in out)


def test_speech_fires_carried_obj_and_room(prog_world):
    import comm
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)  # the speaker's OWN carried obj must react
    ITEM_DEFS._data[9100]["obj_triggers"] = (("speech", 9305, "hello"),)
    OBJPROGS[9305] = "obj echo The sword vibrates."
    world.rooms._data[9001]["room_triggers"] = (("speech", 9306, ""),)
    ROOMPROGS[9306] = "room echo The walls listen."
    comm.do_say(player, "why hello")
    assert any("The sword vibrates." in l for l in out)
    assert any("The walls listen." in l for l in out)


def test_act_room_trigger_fires_once_per_recipient(prog_world):
    player, mob, sword, out = prog_world
    mob2 = _char_base()
    mob2.update(id=3, is_npc=True, tpl=9405, name="guard",
                short_descr="a test guard", room=9001, pos="standing")
    world.chars[3] = mob2
    world.rooms._data[9001]["mobs"].append(3)
    world.rooms._data[9001]["room_triggers"] = (("act", 9300, "waves"),)
    ROOMPROGS[9300] = "room echo Someone gestures."
    handler.act("$n waves.", player, None, None, handler.TO_ROOM)
    # two qualifying recipients (both guards) -> the upstream per-recipient
    # perform_act block runs twice
    assert sum(1 for l in out if "Someone gestures." in l) == 2


def test_fight_fires_worn_obj_and_room_once(prog_world):
    import combat
    player, mob, sword, out = prog_world
    worn = {"vnum": 9100}
    player["equip"]["hold"] = worn
    ITEM_DEFS._data[9100]["obj_triggers"] = (("fight", 9313, "100"),)
    OBJPROGS[9313] = "obj echo The sword thirsts."
    world.rooms._data[9001]["room_triggers"] = (("fight", 9314, "100"),)
    ROOMPROGS[9314] = "room echo The room trembles."
    player["fighting"] = 2
    mob["fighting"] = 1
    # Direct fighting writes bypass set_fighting's autodrop/sleep-strip/stance
    # side effects (unwanted for this trigger-focused test) -- add to the
    # active-fighter index explicitly so violence_update visits both.
    world.FIGHTERS.add(player["id"])
    world.FIGHTERS.add(mob["id"])
    combat.violence_update(player)
    assert sum(1 for l in out if "The sword thirsts." in l) == 1
    # both combatants are in 9001; the room fires at most once per pulse
    assert sum(1 for l in out if "The room trembles." in l) == 1


def test_pulse_obj_delay_counts_down_then_fires(prog_world):
    player, mob, sword, out = prog_world
    ITEM_DEFS._data[9100]["obj_triggers"] = (("delay", 9315, "100"),)
    OBJPROGS[9315] = "obj echo Tick."
    sword["oprog_delay"] = 2
    assert mobprog.pulse_obj(sword, 9001, None, True) is False
    assert not any("Tick." in l for l in out)
    assert mobprog.pulse_obj(sword, 9001, None, True) is True
    assert any("Tick." in l for l in out)


def test_pulse_room_random_fires(prog_world):
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["room_triggers"] = (("random", 9316, "50"),)
    ROOMPROGS[9316] = "room echo Creak."
    assert mobprog.pulse_room(9001) is True
    assert any("Creak." in l for l in out)


# -- ifcheck completion (PROGS_PLAN Phase 3) -----------------------------------

def _ce(mob_, check, line, ch=None, arg1=None, arg2=None):
    return mobprog.cmd_eval(check, line, mob_, ch, arg1, arg2, None, 0)


def test_ifcheck_isimmort(prog_world):
    player, mob, sword, out = prog_world
    assert _ce(mob, "isimmort", "$n", ch=player) is False
    mob["level"] = 52
    assert _ce(mob, "isimmort", "$i") is True


def test_ifcheck_carries_and_wears(prog_world):
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    assert _ce(mob, "carries", "$n 9100", ch=player) is True
    assert _ce(mob, "carries", "$n sword", ch=player) is True
    assert _ce(mob, "carries", "$n 9101", ch=player) is False
    assert _ce(mob, "wears", "$n 9100", ch=player) is False
    player["inv"].remove(sword)
    player["equip"]["hold"] = sword
    # worn: has_item counts it for the number form, get_obj_carry (name form,
    # unworn inventory only) does not
    assert _ce(mob, "wears", "$n 9100", ch=player) is True
    assert _ce(mob, "wears", "$n sword", ch=player) is True
    assert _ce(mob, "carries", "$n 9100", ch=player) is True
    assert _ce(mob, "carries", "$n sword", ch=player) is False


def test_ifcheck_has_and_uses(prog_world):
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    assert _ce(mob, "has", "$n weapon", ch=player) is True
    assert _ce(mob, "uses", "$n weapon", ch=player) is False
    player["inv"].remove(sword)
    player["equip"]["hold"] = sword
    assert _ce(mob, "uses", "$n weapon", ch=player) is True


def test_ifcheck_objval_weapon_and_attrib_override(prog_world):
    player, mob, sword, out = prog_world
    ITEM_DEFS._data[9100]["weapon_type"] = "sword"
    ITEM_DEFS._data[9100]["dice"] = (2, 5, 0)
    assert _ce(mob, "objval0", "$o == 1", ch=player, arg1=sword) is True
    assert _ce(mob, "objval1", "$o == 2", ch=player, arg1=sword) is True
    assert _ce(mob, "objval2", "$o == 5", ch=player, arg1=sword) is True
    # an `obj attrib` write to the instance values tuple wins outright
    sword["values"] = (9, 8, 7, 6, 5)
    assert _ce(mob, "objval0", "$o == 9", ch=player, arg1=sword) is True


def test_ifcheck_objval0_staff_is_spear_class(prog_world):
    # data word "staff" -> WEAPON_SPEAR (3), cf. 1stMud weapon_class; an
    # unknown word falls back to exotic (0)
    player, mob, sword, out = prog_world
    ITEM_DEFS._data[9100]["weapon_type"] = "staff"
    assert _ce(mob, "objval0", "$o == 3", ch=player, arg1=sword) is True
    ITEM_DEFS._data[9100]["weapon_type"] = "polear"
    assert _ce(mob, "objval0", "$o == 0", ch=player, arg1=sword) is True


def test_ifcheck_objval_in_objprog(prog_world):
    player, mob, sword, out = prog_world
    ITEM_DEFS._data[9100]["dice"] = (3, 4, 0)
    assert mobprog._cmd_eval_other(
        "objval1", "$i == 3", "obj", _octx(sword), player, None, None,
        None, 0) is True


def test_ifcheck_grpsize_and_order(prog_world):
    player, mob, sword, out = prog_world
    mob["leader"] = 1  # guard grouped under the player
    assert _ce(mob, "grpsize", "$n == 1", ch=player) is True
    mob2 = _char_base()
    mob2.update(id=3, is_npc=True, tpl=9405, name="guard",
                short_descr="a test guard", room=9001, pos="standing")
    world.chars[3] = mob2
    world.rooms._data[9001]["mobs"].append(3)
    # mob2 is the second same-vnum NPC in the room walk
    assert _ce(mob2, "order", "== 1") is True
    assert _ce(mob, "order", "== 0") is True


def test_ifcheck_race_class_plr_imm_off(prog_world):
    from classes import CLASS_TABLE
    player, mob, sword, out = prog_world
    assert _ce(mob, "race", "$i human") is True
    assert _ce(mob, "race", "$i troll") is False
    cls_name = CLASS_TABLE[0]["names"][0].lower()
    player["classes"] = [0]
    player["prime_class"] = 0
    assert _ce(mob, "class", "$n " + cls_name, ch=player) is True
    assert _ce(mob, "class", "$i " + cls_name) is False  # NPCs have no class
    player["flags"] = handler.PLR_AUTOLOOT
    assert _ce(mob, "plr", "$n autoloot", ch=player) is True
    assert _ce(mob, "plr", "$n autosac", ch=player) is False
    mob["imm_flags"] = {"fire": True}
    mob["off_flags"] = {"dodge": True}
    assert _ce(mob, "imm", "$i fire") is True
    assert _ce(mob, "off", "$i dodge") is True
    assert _ce(mob, "off", "$i berserk") is False


def test_ifcheck_weight_onquest_clan_hunter(prog_world):
    player, mob, sword, out = prog_world
    world.rooms._data[9001]["items"].remove(sword)
    player["inv"].append(sword)
    assert _ce(mob, "weight", "$n > 0", ch=player) is True
    assert _ce(mob, "onquest", "$n", ch=player) is False
    player["quest_status"] = 1
    assert _ce(mob, "onquest", "$n", ch=player) is True
    assert _ce(mob, "clan", "$n whatever", ch=player) is False
    assert _ce(mob, "hunter", "$n", ch=player) is False


def test_ifcheck_objtype_and_skill(prog_world):
    player, mob, sword, out = prog_world
    assert _ce(mob, "objtype", "$o weapon", ch=player, arg1=sword) is True
    assert _ce(mob, "objtype", "$o potion", ch=player, arg1=sword) is False
    # learned=0 (no class access) -> below any positive minimum
    assert _ce(mob, "skill", "$n sword 10", ch=player) is False
    assert _ce(mob, "skill", "$i sword 10") is False  # NPCs never pass


# -- gtransfer / gforce / vforce (PROGS_PLAN Phase 3) --------------------------

def test_mp_gforce_forces_victims_group(prog_world):
    player, mob, sword, out = prog_world
    mob["leader"] = 1  # guard grouped under the player
    mob2 = _char_base()
    mob2.update(id=3, is_npc=True, tpl=9405, name="guard",
                short_descr="a test guard", room=9001, pos="standing")
    world.chars[3] = mob2
    world.rooms._data[9001]["mobs"].append(3)
    mobprog._mp_gforce(mob2, "tester say banzai", 0, 0)
    # player and grouped guard both say it; ungrouped mob2 does not
    assert sum(1 for l in out if "banzai" in l) == 2


def test_vforce_self_exclusion_mob_vs_obj(prog_world):
    player, mob, sword, out = prog_world
    mob2 = _char_base()
    mob2.update(id=3, is_npc=True, tpl=9405, name="guard",
                short_descr="a test guard", room=9001, pos="standing")
    world.chars[3] = mob2
    world.rooms._data[9001]["mobs"].append(3)
    mobprog._mp_vforce(mob, "9405 say vfmob", 0, 0)
    assert sum(1 for l in out if "vfmob" in l) == 1  # mob excludes itself
    del out[:]
    mobprog._op_vforce(_octx(sword), "9405 say vfobj", 0)
    assert sum(1 for l in out if "vfobj" in l) == 2  # obj forces both


def test_rp_gtransfer_moves_group(prog_world):
    player, mob, sword, out = prog_world
    mob["leader"] = 1
    mob2 = _char_base()
    mob2.update(id=3, is_npc=True, tpl=9405, name="wanderer",
                keywords="wanderer", short_descr="a wanderer", room=9001,
                pos="standing")
    world.chars[3] = mob2
    world.rooms._data[9001]["mobs"].append(3)
    mobprog._rp_gtransfer(9001, "tester 9002", 0)
    assert player["room"] == 9002
    assert mob["room"] == 9002
    assert mob2["room"] == 9001
