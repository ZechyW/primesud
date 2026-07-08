"""Tests for do_envenom/do_quaff (act_obj.c) and weapon flag procs (fight.c one_hit)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import combat
import handler
import inventory
import magic
from item import item_affect_find, serialize_item_token, parse_item_token
from skills_table import GSN_POISON
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS

MOB_TPL = 9401
SWORD_VNUM = 9410
MACE_VNUM = 9411
BREAD_VNUM = 9412
POTION_VNUM = 9413


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    world.chars[1] = ch
    return ch


def _make_mob(mid, room=9001, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = MOB_TPL
    ch["name"] = "a test dog"
    ch["level"] = 5
    ch["room"] = room
    ch.update(overrides)
    world.chars[mid] = ch
    if room in world.rooms._data:
        world.rooms._data[room]["mobs"].append(mid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test dog", "long_descr": "A test dog is here.",
        "keywords": "dog test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    ITEM_DEFS._data[SWORD_VNUM] = {
        "keywords": "sword test", "short_descr": "a test sword",
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "weapon_flags": {}, "level": 20,
        "wear_flags": {"take": True, "wield": True},
    }
    ITEM_DEFS._data[MACE_VNUM] = {
        "keywords": "mace test", "short_descr": "a test mace",
        "type": "weapon", "weapon_type": "mace", "dam_type": "pound",
        "dice": (1, 4, 0), "weapon_flags": {}, "level": 20,
        "wear_flags": {"take": True, "wield": True},
    }
    ITEM_DEFS._data[BREAD_VNUM] = {
        "keywords": "bread test", "short_descr": "a loaf of bread",
        "type": "food", "level": 0, "wear_flags": {"take": True},
    }
    ITEM_DEFS._data[POTION_VNUM] = {
        "keywords": "potion test", "short_descr": "a test potion",
        "type": "potion", "level": 1, "wear_flags": {"take": True},
    }
    _stub_room(9001)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(inventory, "tprint", capture)
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


@pytest.fixture
def skilled(monkeypatch):
    monkeypatch.setattr(inventory, "get_skill", lambda ch, sn, *a: 100)
    monkeypatch.setattr(inventory, "check_improve", lambda *a, **kw: None)
    # Pin the skill roll: success paths assert on roll < skill, and the
    # shared RNG stream shifts whenever earlier tests consume randint calls.
    monkeypatch.setattr(inventory, "randint", lambda a, b: a)


# -- do_envenom ----------------------------------------------------------------

def test_envenom_weapon_sets_poison_flag(out, skilled):
    player = _make_player()
    sword = {"vnum": SWORD_VNUM}
    player["inv"].append(sword)
    inventory.do_envenom(player, ["sword"])
    assert sword["weapon_flags"].get("poison")
    af = item_affect_find(sword, GSN_POISON)
    assert af is not None and af["where"] == "to_weapon"
    assert any("You coat" in l for l in out)


def test_envenom_requires_skill(out, monkeypatch):
    monkeypatch.setattr(inventory, "get_skill", lambda ch, sn, *a: 0)
    player = _make_player()
    player["inv"].append({"vnum": SWORD_VNUM})
    inventory.do_envenom(player, ["sword"])
    assert any("Are you crazy" in l for l in out)


def test_envenom_rejects_blunt_weapon(out, skilled):
    player = _make_player()
    player["inv"].append({"vnum": MACE_VNUM})
    inventory.do_envenom(player, ["mace"])
    assert any("only envenom edged weapons" in l for l in out)


def test_envenom_rejects_flagged_or_already(out, skilled):
    player = _make_player()
    sword = {"vnum": SWORD_VNUM, "weapon_flags": {"flaming": True}}
    player["inv"].append(sword)
    inventory.do_envenom(player, ["sword"])
    assert any("can't seem to envenom" in l for l in out)
    del out[:]
    sword["weapon_flags"] = {"poison": True}
    inventory.do_envenom(player, ["sword"])
    assert any("already envenomed" in l for l in out)


def test_envenom_food(out, skilled):
    player = _make_player()
    bread = {"vnum": BREAD_VNUM}
    player["inv"].append(bread)
    inventory.do_envenom(player, ["bread"])
    assert bread["poisoned"] is True
    assert any("deadly poison" in l for l in out)


def test_envenom_respects_instance_type_override(out, skilled):
    player = _make_player()
    sword = {"vnum": SWORD_VNUM, "type": "trash"}
    player["inv"].append(sword)
    inventory.do_envenom(player, ["sword"])
    assert any("can't poison" in l for l in out)
    assert "weapon_flags" not in sword


def test_quaff_respects_instance_type_override(out, monkeypatch):
    player = _make_player()
    potion = {"vnum": POTION_VNUM, "type": "trash"}
    player["inv"].append(potion)
    called = []
    monkeypatch.setattr(inventory, "validate_item_spell_payload", lambda obj: obj)
    monkeypatch.setattr(inventory, "cast_item_spells",
                        lambda ch, obj, victim, target: called.append(obj))
    inventory.do_quaff(player, ["potion"])
    assert "You can quaff only potions." in out
    assert called == []
    assert potion in player["inv"]


# -- weapon procs ----------------------------------------------------------------

def _armed_fight(weapon_flags, affects=None):
    player = _make_player()
    mob = _make_mob(2)
    player["fighting"] = 2
    mob["fighting"] = 1
    wobj = {"vnum": SWORD_VNUM, "level": 20, "weapon_flags": dict(weapon_flags)}
    if affects:
        wobj["affect_list"] = affects
    player["equip"]["wield"] = wobj
    return player, mob, wobj


def test_poison_proc_applies_and_decays(out, monkeypatch):
    affects = [{"where": "to_weapon", "type": GSN_POISON, "level": 20,
                "duration": 10, "location": "none", "modifier": 0,
                "bitvector": "poison"}]
    player, mob, wobj = _armed_fight({"poison": True}, affects)
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    combat._weapon_procs(player, mob, wobj, ITEM_DEFS[SWORD_VNUM])
    assert mob.get("affected_by", {}).get("poison")
    assert any(af.get("type") == GSN_POISON for af in mob["affect_list"])
    # weapon venom decays per hit (level -2, duration -1)
    assert affects[0]["level"] == 18 and affects[0]["duration"] == 9


def test_poison_proc_saved_no_affect(out, monkeypatch):
    player, mob, wobj = _armed_fight(
        {"poison": True},
        [{"where": "to_weapon", "type": GSN_POISON, "level": 20,
          "duration": 10, "location": "none", "modifier": 0,
          "bitvector": "poison"}])
    monkeypatch.setattr(magic, "saves_spell", lambda *a: True)
    combat._weapon_procs(player, mob, wobj, ITEM_DEFS[SWORD_VNUM])
    assert not mob.get("affected_by", {}).get("poison")


def test_vampiric_proc_drains(out, monkeypatch):
    player, mob, wobj = _armed_fight({"vampiric": True})
    player["hit"] = 10
    player["alignment"] = 0
    dmg = []
    monkeypatch.setattr(combat, "randint", lambda a, b: b)
    monkeypatch.setattr(combat, "damage",
                        lambda ch, v, dam, dt, dam_type, show, **kw: dmg.append((dam, dam_type)))
    combat._weapon_procs(player, mob, wobj, ITEM_DEFS[SWORD_VNUM])
    assert dmg and dmg[0][1] == combat.DAM_NEGATIVE
    assert player["hit"] > 10
    assert player["alignment"] == -1


def test_elemental_procs_deal_typed_damage(out, monkeypatch):
    player, mob, wobj = _armed_fight(
        {"flaming": True, "frost": True, "shocking": True})
    dmg = []
    monkeypatch.setattr(combat, "randint", lambda a, b: b)
    monkeypatch.setattr(combat, "damage",
                        lambda ch, v, dam, dt, dam_type, show, **kw: dmg.append(dam_type))
    combat._weapon_procs(player, mob, wobj, ITEM_DEFS[SWORD_VNUM])
    assert dmg == [combat.DAM_FIRE, combat.DAM_COLD, combat.DAM_LIGHTNING]


def test_weapon_flags_roundtrip_save():
    wobj = {"vnum": SWORD_VNUM, "weapon_flags": {"poison": True},
            "affect_list": [{"where": "to_weapon", "type": GSN_POISON,
                             "level": 12, "duration": 5, "location": "none",
                             "modifier": 0, "bitvector": "poison"}]}
    back = parse_item_token(serialize_item_token(wobj))
    assert back["weapon_flags"] == {"poison": True}
    assert back["affect_list"][0]["where"] == "to_weapon"
    assert back["affect_list"][0]["bitvector"] == "poison"
