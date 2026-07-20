"""Tests for debug subcommands (goto/load/purge/restore/peace/mwhere/owhere/memory)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import debug
import terminal
import world
from handler import _char_base
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    """Capture terminal.tr.print output (debug module prints via terminal.tr)."""
    lines = []

    class _FakeTr:
        def print(self, s="", end="\n"):
            lines.append(s)

    monkeypatch.setattr(terminal, "tr", _FakeTr())
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)
    old_room_defs = dict(ROOM_DEFS._data)

    r1 = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    r2 = {"name": "Away Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data.clear()
    world.rooms._data[3001] = r1
    world.rooms._data[3002] = r2
    ROOM_DEFS._data[3001] = r1
    ROOM_DEFS._data[3002] = r2

    MOB_DEFS._data[9001] = {"short_descr": "a guard", "keywords": "guard",
                            "level": 10, "description": "A guard.",
                            "hp_dice": (1, 1, 10), "hitroll": 0,
                            "damage": (1, 4, 0), "armor": (0, 0, 0, 0)}
    MOB_DEFS._data[9002] = {"short_descr": "the shopkeeper",
                            "keywords": "shopkeeper keeper",
                            "level": 10, "description": "A keeper.",
                            "hp_dice": (1, 1, 10), "hitroll": 0,
                            "damage": (1, 4, 0), "armor": (0, 0, 0, 0)}

    ITEM_DEFS._data[8001] = {"keywords": "sword test", "short_descr": "a test sword",
                             "wear_flags": {"take": True}, "level": 1,
                             "weight": 1, "value": 0, "type": "weapon"}
    ITEM_DEFS._data[8002] = {"keywords": "fountain", "short_descr": "a fountain",
                             "wear_flags": {}, "level": 1,
                             "weight": 1000, "value": 0, "type": "fountain"}
    ITEM_DEFS._data[8003] = {"keywords": "altar", "short_descr": "an altar",
                             "wear_flags": {}, "extra_flags": {"nopurge": True},
                             "level": 1, "weight": 1000, "value": 0, "type": "furniture"}

    guard = _char_base()
    guard.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                  "level": 10, "hit": 50, "max_hit": 50,
                  "act_flags": {"aggressive": True}})
    world.chars.clear()
    world.chars[2] = guard
    r1["mobs"] = [2]

    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": 3001, "level": 10,
                   "hit": 30, "max_hit": 100, "mana": 5, "max_mana": 50,
                   "move": 5, "max_move": 80})
    world.chars[1] = player  # real game keeps the player at world.chars[1]

    yield {"player": player, "guard": guard, "r1": r1, "r2": r2}

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_room_defs)


def _run(player, argstr):
    debug.do_debug(player, argstr.split())


# -- goto ------------------------------------------------------------------

def test_goto_vnum(scene, out):
    _run(scene["player"], "goto 3002")
    assert scene["player"]["room"] == 3002


def test_goto_mob_name(scene, out):
    _run(scene["player"], "goto guard")
    assert scene["player"]["room"] == 3001  # guard is here; stays put


def test_goto_bad_location(scene, out):
    _run(scene["player"], "goto 99999")
    assert "No such location." in out
    assert scene["player"]["room"] == 3001


def test_goto_no_args(scene, out):
    _run(scene["player"], "goto")
    assert "Goto where?" in out


def test_goto_brings_pet(scene, out):
    pet = _char_base()
    pet.update({"is_npc": True, "id": 3, "tpl": 9001, "room": 3001,
                "act_flags": {"pet": True}, "master": 1})
    world.chars[3] = pet
    scene["r1"]["mobs"].append(3)
    scene["player"]["pet"] = 3
    _run(scene["player"], "goto 3002")
    assert pet["room"] == 3002
    assert 3 in scene["r2"]["mobs"]
    assert 3 not in scene["r1"]["mobs"]


# -- load ------------------------------------------------------------------

def test_load_mob(scene, out):
    _run(scene["player"], "load mob 9002")
    assert "Ok." in out
    ids = scene["r1"]["mobs"]
    spawned = [world.chars[i] for i in ids if world.chars[i]["tpl"] == 9002]
    assert len(spawned) == 1


def test_load_obj_takeable_goes_to_inv(scene, out):
    _run(scene["player"], "load obj 8001")
    assert "Ok." in out
    assert any(isinstance(o, dict) and o["vnum"] == 8001
               for o in scene["player"]["inv"])


def test_load_obj_notake_goes_to_room(scene, out):
    _run(scene["player"], "load obj 8002")
    assert any(isinstance(o, dict) and o["vnum"] == 8002
               for o in scene["r1"]["items"])


def test_load_bad_vnum(scene, out):
    _run(scene["player"], "load mob 4242")
    assert "No mob has that vnum." in out


def test_load_syntax(scene, out):
    _run(scene["player"], "load")
    assert "debug load mob|obj <vnum>" in out


# -- purge -----------------------------------------------------------------

def test_purge_removes_mobs_and_items(scene, out):
    scene["r1"]["items"].extend([8001, 8003])
    _run(scene["player"], "purge")
    assert scene["r1"]["mobs"] == []
    assert 2 not in world.chars
    assert scene["r1"]["items"] == [8003]  # nopurge altar survives


def test_purge_keeps_nopurge_mob(scene, out):
    scene["guard"]["act_flags"]["nopurge"] = True
    _run(scene["player"], "purge")
    assert 2 in world.chars


def test_purge_keeps_pet(scene, out):
    pet = _char_base()
    pet.update({"is_npc": True, "id": 3, "tpl": 9001, "room": 3001,
                "act_flags": {"pet": True}, "master": 1})
    world.chars[3] = pet
    scene["r1"]["mobs"].append(3)
    scene["player"]["pet"] = 3
    _run(scene["player"], "purge")
    assert 3 in world.chars
    assert scene["player"]["pet"] == 3


# -- restore ---------------------------------------------------------------

def test_restore_heals_room(scene, out):
    scene["guard"]["hit"] = 1
    _run(scene["player"], "restore")
    assert "Room restored." in out
    p = scene["player"]
    assert (p["hit"], p["mana"], p["move"]) == (100, 50, 80)
    assert scene["guard"]["hit"] == scene["guard"]["max_hit"]


def test_restore_strips_poison(scene, out):
    from skills_table import GSN_POISON
    p = scene["player"]
    p["affect_list"].append({"type": GSN_POISON, "where": "to_affects",
                             "location": "none", "modifier": 0,
                             "level": 10, "duration": 5, "bitvector": "poison"})
    p["affected_by"]["poison"] = True
    _run(p, "restore")
    assert p["affect_list"] == []
    assert not p["affected_by"].get("poison")


# -- peace -----------------------------------------------------------------

def test_peace_stops_fighting_and_strips_aggressive(scene, out):
    p, g = scene["player"], scene["guard"]
    p["fighting"] = 2
    g["fighting"] = 1
    _run(p, "peace")
    assert p["fighting"] is None
    assert g["fighting"] is None
    assert "aggressive" not in g["act_flags"]
    assert "Ok." in out


# -- mwhere / owhere -------------------------------------------------------

def test_mwhere_finds_guard(scene, out):
    _run(scene["player"], "mwhere guard")
    assert any("a guard" in l and "3001" in l for l in out)


def test_mwhere_no_match(scene, out):
    _run(scene["player"], "mwhere dragon")
    assert "You didn't find any dragon." in out


def test_owhere_room_inv_equip(scene, out):
    scene["r1"]["items"].append(8001)
    scene["player"]["inv"].append({"vnum": 8001, "cost": 0})
    scene["player"]["equip"]["wield"] = {"vnum": 8001, "cost": 0}
    _run(scene["player"], "owhere sword")
    assert any("in room 3001" in l for l in out)
    assert any("carried by you" in l for l in out)
    assert any("worn by you" in l for l in out)


def test_owhere_no_match(scene, out):
    _run(scene["player"], "owhere unobtanium")
    assert "Nothing like that in heaven or earth." in out


# -- memory / dispatch -----------------------------------------------------

def test_memory_runs(scene, out):
    _run(scene["player"], "memory")
    assert any(l.startswith("Heap:") for l in out)
    assert any(l.startswith("Rooms:") for l in out)


def test_exact_channel_beats_subcmd_prefix(scene, out):
    # "move" is an exact channel name; must toggle, not hit mwhere/memory
    _run(scene["player"], "move")
    assert "move" in debug.DBG
    _run(scene["player"], "move")
    assert "move" not in debug.DBG


def test_subcmd_prefix_dispatch(scene, out):
    _run(scene["player"], "mem")  # prefix of memory
    assert any(l.startswith("Heap:") for l in out)


def test_debug_slay(scene, out, monkeypatch):
    # combat.py no longer imports tprint (output now routes via chprintln/act
    # through handler, which does the local-player gating) -- patch handler.tprint
    cap = lambda s="", end="\n": out.append(s)
    import handler
    monkeypatch.setattr(handler, "tprint", cap)
    # raw_kill builds a corpse from the limbo template
    ITEM_DEFS._data[10] = {"keywords": "corpse", "short_descr": "The corpse of %s",
                           "description": "The corpse of %s is lying here.",
                           "type": "npc_corpse", "wear_flags": {"take": True},
                           "level": 0, "weight": 1000, "value": 0}
    _run(scene["player"], "slay guard")
    assert 2 not in world.chars
    assert 2 not in scene["r1"]["mobs"]


# -- advance / set ----------------------------------------------------------

def test_advance_player_to_level(scene, out, monkeypatch):
    import game_state
    import handler
    monkeypatch.setattr(game_state, "save_world", lambda quiet=False: True)
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))
    p = scene["player"]
    p["level"] = 1
    p["xp"] = 0
    p["perm_hit"] = p["max_hit"]
    p["perm_mana"] = p["max_mana"]
    p["perm_move"] = p["max_move"]
    p["practice"] = 0
    p["train"] = 0
    p["learned"] = {}
    _run(p, "advance self 3")
    assert p["level"] == 3
    assert p["xp"] == 0
    assert any("Raising a player's level!" in l for l in out)
    assert "You are now level 3." in out


def test_advance_demotes_and_rebuilds(scene, out, monkeypatch):
    import game_state
    import handler
    monkeypatch.setattr(game_state, "save_world", lambda quiet=False: True)
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))
    p = scene["player"]
    p["level"] = 1
    p["xp"] = 0
    p["perm_hit"] = p["max_hit"]
    p["perm_mana"] = p["max_mana"]
    p["perm_move"] = p["max_move"]
    p["practice"] = 0
    p["train"] = 0
    p["learned"] = {}
    _run(p, "advance self 5")
    prac = p["practice"]
    _run(p, "advance self 2")
    assert p["level"] == 2
    # 1stMud temp_prac: practices survive the demote (not reset with stats),
    # then the raise loop grants more on top
    assert p["practice"] >= prac
    assert any("Lowering a player's level!" in l for l in out)
    assert "You are now level 2." in out


def test_advance_rejects_npc(scene, out):
    _run(scene["player"], "advance guard 20")
    assert "Not on NPC's." in out


def test_set_char_resources_for_remort(scene, out):
    p = scene["player"]
    _run(p, "set char self level 49")
    _run(p, "set char self gold 500000")
    _run(p, "set player self quest.points 500")
    assert p["level"] == 49
    assert p["gold"] == 500000
    assert p["quest_points"] == 500
    assert out.count("Ok.") == 3


def test_set_mobile_field(scene, out):
    _run(scene["player"], "set mobile guard level 20")
    assert scene["guard"]["level"] == 20
    assert "Ok." in out


def test_set_object_field(scene, out):
    scene["player"]["inv"].append({"vnum": 8001, "cost": 0})
    _run(scene["player"], "set object sword cost 123")
    assert scene["player"]["inv"][0]["cost"] == 123
    assert "Ok." in out


def test_bare_debug_lists_subcommands(scene, out, monkeypatch):
    pages = []
    monkeypatch.setattr(debug, "tpage", lambda lines: pages.extend(lines))
    _run(scene["player"], "")
    joined = "\n".join(pages)
    for sub in debug._SUBCMDS:
        assert sub[0] in joined
    assert "spawn" in joined  # channels listed too


def test_set_str_field_keeps_digits_as_string(scene, out):
    _run(scene["player"], "set char self name 123")
    assert scene["player"]["name"] == "123"


def test_set_rejects_malformed_int(scene, out):
    p = scene["player"]
    lvl = p["level"]
    _run(p, "set char self level --3")
    assert p["level"] == lvl
    assert "Value must be numeric." in out
    _run(p, "advance self --3")
    assert "Syntax: advance <char> <level>" in out


def test_set_prefix_matches_sorted_keys(scene, out):
    p = scene["player"]
    p["mana"] = p["max_hit"] = 1
    _run(p, "set char self man 42")  # "man" -> mana, not max_*
    assert p["mana"] == 42
    assert p["max_hit"] == 1


def test_set_bare_vnum_object_promotes_to_instance(scene, out):
    from world import ITEM_DEFS
    tpl_cost = ITEM_DEFS[8001].get("value", 0)
    scene["player"]["inv"].append(8001)
    _run(scene["player"], "set object sword cost 55")
    inst = scene["player"]["inv"][0]
    assert isinstance(inst, dict) and inst["cost"] == 55
    assert ITEM_DEFS[8001].get("value", 0) == tpl_cost  # template untouched


# -- vnum (do_vnum) ---------------------------------------------------------

@pytest.fixture
def paged(monkeypatch):
    lines = []
    monkeypatch.setattr(debug, "tpage", lambda ls: lines.extend(ls))
    return lines


def test_vnum_loaded_template(scene, out, paged):
    _run(scene["player"], "vnum mob guard")
    assert any("9001" in l and "a guard" in l for l in paged)


def test_vnum_unloaded_via_idx(scene, out, paged, monkeypatch, tmp_path):
    idx = tmp_path / "mobs.idx"
    idx.write_text("# header\nfaraway|9500|red dragon\n")
    monkeypatch.setattr(debug, "MOBS_IDX", str(idx))
    _run(scene["player"], "vnum mob dragon")
    assert any("9500" in l and "faraway, unloaded" in l for l in paged)


def test_vnum_idx_skips_loaded_areas(scene, out, paged, monkeypatch, tmp_path):
    # nonsense keyword so real loaded-area defs can't match either
    idx = tmp_path / "mobs.idx"
    idx.write_text("loadedtag|9500|qqxzdragon\n")
    monkeypatch.setattr(debug, "MOBS_IDX", str(idx))
    world._LOADED_AREAS.add("loadedtag")
    try:
        _run(scene["player"], "vnum mob qqxzdragon")
    finally:
        world._LOADED_AREAS.discard("loadedtag")
    assert "No mobiles by that name." in paged


def test_vnum_untyped_searches_both(scene, out, paged, monkeypatch, tmp_path):
    for name in ("mobs.idx", "objs.idx"):
        (tmp_path / name).write_text("")
    monkeypatch.setattr(debug, "MOBS_IDX", str(tmp_path / "mobs.idx"))
    monkeypatch.setattr(debug, "OBJS_IDX", str(tmp_path / "objs.idx"))
    _run(scene["player"], "vnum sword")
    assert any("8001" in l and "a test sword" in l for l in paged)


def test_vnum_is_subcommand_not_channel(scene, out):
    # display overlay folded into holylight; "vnum" must dispatch as lookup
    assert "vnum" not in debug._CHANNELS
    _run(scene["player"], "vnum")
    assert "debug vnum [mob|obj] <name>" in out


# -- flag ------------------------------------------------------------------

def test_flag_toggle_and_ops(scene, out):
    g = scene["guard"]
    _run(scene["player"], "flag mob guard act aggressive")     # toggle off
    assert "aggressive" not in g["act_flags"]
    _run(scene["player"], "flag mob guard act + sentinel")     # add
    assert g["act_flags"].get("sentinel")
    _run(scene["player"], "flag mob guard act = wimpy")        # set equal
    assert g["act_flags"] == {"wimpy": True}
    _run(scene["player"], "flag mob guard act -wimpy")         # fused remove
    assert g["act_flags"] == {}


def test_flag_obj_extra_instance_override(scene, out):
    from world import ITEM_DEFS
    scene["player"]["inv"].append({"vnum": 8001, "cost": 0})
    _run(scene["player"], "flag obj sword extra + glow")
    inst = scene["player"]["inv"][0]
    assert inst["extra_flags"].get("glow")
    assert not ITEM_DEFS[8001].get("extra_flags", {}).get("glow")


def test_flag_bad_field(scene, out):
    _run(scene["player"], "flag mob guard bogus + glow")
    assert "That's not an acceptable flag." in out


# -- force -----------------------------------------------------------------

def test_force_self(scene, out):
    _run(scene["player"], "force self smile")
    assert "Aye aye, right away!" in out


def test_force_mob_runs_command(scene, out, monkeypatch):
    import handler
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))
    _run(scene["player"], "force guard say hello")
    assert "Ok." in out
    assert any("hello" in l for l in out)  # guard's say echoed to the room


# -- spellup ---------------------------------------------------------------

def test_spellup_self_applies_buffs(scene, out, monkeypatch):
    import handler
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))
    from handler import is_affected
    from magic import _skill_lookup
    p = scene["player"]
    _run(p, "spellup")
    assert "OK." in out
    for name in ("armor", "sanctuary", "shield"):
        assert is_affected(p, _skill_lookup(name)), name


# -- clone -----------------------------------------------------------------

def test_clone_mob_independent_copy(scene, out):
    scene["guard"]["hit"] = 17
    _run(scene["player"], "clone guard")
    clones = [world.chars[i] for i in scene["r1"]["mobs"]
              if world.chars[i]["tpl"] == 9001]
    assert len(clones) == 2
    a, b = clones
    assert a["id"] != b["id"]
    assert b["hit"] == 17  # live state copied
    a["act_flags"]["sentinel"] = True
    assert "sentinel" not in b["act_flags"]  # deep copy, not aliased


def test_clone_carried_obj_goes_to_inv(scene, out):
    scene["player"]["inv"].append({"vnum": 8001, "cost": 7})
    _run(scene["player"], "clone sword")
    swords = [o for o in scene["player"]["inv"] if o["vnum"] == 8001]
    assert len(swords) == 2
    assert swords[1]["cost"] == 7
    assert swords[0] is not swords[1]


# -- pstat / pdump / prog channel ------------------------------------------

def test_pstat_lists_triggers(scene, out):
    MOB_DEFS._data[9001]["mob_triggers"] = [("speech", 9901, "hello")]
    _run(scene["player"], "pstat guard")
    assert any("speech" in l and "9901" in l and "hello" in l for l in out)


def test_pstat_no_progs(scene, out):
    _run(scene["player"], "pstat 9002")
    assert "[No programs set]" in out


def test_pdump_prints_source(scene, out, paged):
    world.MOBPROGS[9901] = "say hi\nmob echo done"
    try:
        _run(scene["player"], "pdump 9901")
    finally:
        del world.MOBPROGS[9901]
    assert "say hi" in paged and "mob echo done" in paged


def test_prog_channel_traces_fire(scene, out, monkeypatch):
    import handler
    import mobprog
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": out.append(s))
    world.MOBPROGS[9901] = "say hi"
    debug.DBG.add("prog")
    try:
        mobprog._run_prog(scene["guard"], 9901, scene["player"], None, None)
    finally:
        debug.DBG.discard("prog")
        del world.MOBPROGS[9901]
    assert any("prog 9901 fires" in l for l in out)
