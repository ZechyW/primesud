"""Tests for the five magic.c/update.c fidelity TODOs resolved 10/07/2026:
spell_heat_metal equipment drop/sear, spell_energy_drain gain_exp,
spell_bless/spell_curse worn-item caster saving_throw, spell_create_rose,
and mob.py ACT_SCAVENGER floor pickup.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import handler
import inventory
import magic
import mob
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS

MOB_TPL = 9501
ARMOR_VNUM = 9510
WEAPON_VNUM = 9511
NONMETAL_ARMOR_VNUM = 9512
FLAMING_WEAPON_VNUM = 9513
TRINKET_VNUM = 9514
SCAV_MOB_TPL = 9520
JUNK_LOW_VNUM = 9530
JUNK_NOTAKE_VNUM = 9531
JUNK_BEST_VNUM = 9532
JUNK_FLOOR_VNUM = 9533


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


def _make_mob(mid, room=9001, tpl=MOB_TPL, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = tpl
    ch["name"] = "a test dummy"
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
    # The scavenger tests call mobile_update, which sweeps *all* of
    # world.chars; real mobs left over from earlier area loads would be
    # walked (and despawned) alongside the stubs below.  Restored at teardown.
    world.chars.clear()
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test dummy", "long_descr": "A test dummy is here.",
        "keywords": "dummy test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    MOB_DEFS._data[SCAV_MOB_TPL] = {
        "short_descr": "a scavenging rat", "long_descr": "A scavenging rat is here.",
        "keywords": "rat scavenger test", "level": 3, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0), "act_flags": {"scavenger": True},
        "default_pos": "stand",
    }
    ITEM_DEFS._data[ARMOR_VNUM] = {
        "keywords": "breastplate test", "short_descr": "a test breastplate",
        "type": "armor", "level": 9, "weight": 50, "extra_flags": {},
        "wear_flags": {"take": True, "body": True},
    }
    ITEM_DEFS._data[WEAPON_VNUM] = {
        "keywords": "sword test", "short_descr": "a test sword",
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "weapon_flags": {}, "level": 9, "extra_flags": {},
        "wear_flags": {"take": True, "wield": True},
    }
    ITEM_DEFS._data[NONMETAL_ARMOR_VNUM] = {
        "keywords": "robe test", "short_descr": "a test robe",
        "type": "armor", "level": 9, "weight": 20,
        "extra_flags": {"nonmetal": True},
        "wear_flags": {"take": True, "body": True},
    }
    ITEM_DEFS._data[FLAMING_WEAPON_VNUM] = {
        "keywords": "flame sword test", "short_descr": "a flaming test sword",
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "weapon_flags": {"flaming": True}, "level": 9,
        "extra_flags": {},
        "wear_flags": {"take": True, "wield": True},
    }
    ITEM_DEFS._data[TRINKET_VNUM] = {
        "keywords": "trinket test", "short_descr": "a test trinket",
        "type": "treasure", "level": 5, "extra_flags": {},
        "wear_flags": {"take": True, "light": True},
    }
    ITEM_DEFS._data[world.OBJ_VNUM_ROSE] = {
        "keywords": "rose", "short_descr": "a red rose",
        "type": "treasure", "level": 0, "weight": 80, "extra_flags": {},
        "wear_flags": {"take": True, "head": True},
    }
    ITEM_DEFS._data[JUNK_LOW_VNUM] = {
        "keywords": "pebble test", "short_descr": "a test pebble",
        "type": "trash", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
    }
    ITEM_DEFS._data[JUNK_NOTAKE_VNUM] = {
        "keywords": "statue test", "short_descr": "a test statue",
        "type": "trash", "level": 0, "extra_flags": {},
        "wear_flags": {},
    }
    ITEM_DEFS._data[JUNK_BEST_VNUM] = {
        "keywords": "gem test", "short_descr": "a test gem",
        "type": "treasure", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
    }
    ITEM_DEFS._data[JUNK_FLOOR_VNUM] = {
        "keywords": "coin test", "short_descr": "a test trinket coin",
        "type": "trash", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
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
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


def _dmg_capture(monkeypatch):
    calls = []
    monkeypatch.setattr(magic, "damage",
                         lambda ch, v, dam, dt, dam_type, show, **kw: calls.append((dam, dam_type)))
    return calls


# -- spell_heat_metal ------------------------------------------------------

def test_heat_metal_no_effect_fire_immune(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    victim["imm_flags"] = {"fire": True}
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is False
    assert dmg == []
    assert any("no effect" in l for l in out)


def test_heat_metal_worn_armor_dropped(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    armor = {"vnum": ARMOR_VNUM}
    victim["equip"]["body"] = armor
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(magic, "randint", lambda a, b: b)
    monkeypatch.setattr(magic, "get_curr_stat", lambda ch, stat: 18)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is True
    assert victim["equip"]["body"] is None
    assert armor not in victim["inv"]
    assert armor in world.rooms[victim["room"]]["items"]
    assert dmg and dmg[0][0] == 9 // 3  # dam roll pinned to obj level (randint->b)


def test_heat_metal_worn_armor_seared_when_noremove(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    armor = {"vnum": ARMOR_VNUM, "extra_flags": {"noremove": True}}
    victim["equip"]["body"] = armor
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(magic, "randint", lambda a, b: b)
    monkeypatch.setattr(magic, "get_curr_stat", lambda ch, stat: 18)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is True
    assert victim["equip"]["body"] is armor  # stayed equipped -- seared, not dropped
    assert dmg and dmg[0][0] == 9  # seared branch: randint(1, obj_level) -> b == 9


def test_heat_metal_nonmetal_armor_exempt(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    robe = {"vnum": NONMETAL_ARMOR_VNUM}
    victim["equip"]["body"] = robe
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(magic, "randint", lambda a, b: b)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is False
    assert victim["equip"]["body"] is robe
    assert dmg == []
    assert any("no effect" in l for l in out)


def test_heat_metal_worn_flaming_weapon_exempt(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    fsword = {"vnum": FLAMING_WEAPON_VNUM}
    victim["equip"]["wield"] = fsword
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(magic, "randint", lambda a, b: b)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is False  # sole item skipped entirely -> spell fails
    assert victim["equip"]["wield"] is fsword
    assert dmg == []


def test_heat_metal_carried_flaming_weapon_not_exempt(out, monkeypatch):
    # cf. 1stMud magic.c:3029-3032 -- the WEAPON_FLAMING skip only guards the
    # worn (wear_loc != WEAR_NONE) branch; a carried flaming weapon still
    # burns/drops like any other weapon. Source quirk, ported verbatim.
    ch = _make_player()
    victim = _make_mob(2)
    fsword = {"vnum": FLAMING_WEAPON_VNUM}
    victim["inv"].append(fsword)
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(magic, "randint", lambda a, b: b)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is True
    assert fsword not in victim["inv"]
    assert fsword in world.rooms[victim["room"]]["items"]


def test_heat_metal_level_zero_item_no_crash(out, monkeypatch):
    # cf. 1stMud number_range(1, obj->level): an inverted range returns
    # `from` (db.c:2682), but Python randint(1, 0) raises ValueError.
    # spell_heat_metal clamps the damage roll to 1 for level-0 items --
    # uses the REAL randint on purpose (a lambda a, b: b stub would mask
    # the crash).
    ch = _make_player()
    victim = _make_mob(2)
    ITEM_DEFS._data[9515] = {
        "keywords": "tin cup test", "short_descr": "a level-zero tin cup",
        "type": "armor", "level": 0, "weight": 10, "extra_flags": {},
        "wear_flags": {"take": True, "hold": True},
    }
    cup = {"vnum": 9515}
    victim["inv"].append(cup)
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is True  # gate randint(1, 40) > 0 always passes
    assert cup not in victim["inv"]
    assert cup in world.rooms[victim["room"]]["items"]
    assert dmg and dmg[0][0] >= 0  # clamped roll: randint(1, 1) // 6 == 0


def test_heat_metal_no_items_fails(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_heat_metal(1, 20, ch, victim, magic.TARGET_CHAR)
    assert result is False
    assert dmg == []
    assert any("no effect" in l for l in out)


# -- spell_energy_drain -----------------------------------------------------

def test_energy_drain_npc_victim_gain_exp_noop(out, monkeypatch):
    ch = _make_player()
    victim = _make_mob(2)
    victim["level"] = 10
    victim["mana"] = 100
    victim["move"] = 100
    victim["xp"] = 500
    ch["hit"] = 10
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(magic, "dice", lambda n, s: 5)
    dmg = _dmg_capture(monkeypatch)
    result = magic.spell_energy_drain(1, 10, ch, victim, magic.TARGET_CHAR)
    assert result is True
    assert dmg  # damage() was invoked, no crash
    assert victim["mana"] == 50 and victim["move"] == 50
    assert ch["hit"] == 15
    # gain_exp guards is_npc internally -- NPC victim's xp is untouched
    assert victim["xp"] == 500


# -- spell_bless / spell_curse worn-item caster saving_throw ----------------

def test_bless_worn_object_adjusts_caster_saving_throw(out):
    ch = _make_player()
    trinket = {"vnum": TRINKET_VNUM}
    ch["equip"]["light"] = trinket
    ch["saving_throw"] = 0
    result = magic.spell_bless(1, 20, ch, trinket, magic.TARGET_OBJ)
    assert result is True
    assert ch["saving_throw"] == -1


def test_bless_carried_object_does_not_adjust_saving_throw(out):
    ch = _make_player()
    trinket = {"vnum": TRINKET_VNUM}
    ch["inv"].append(trinket)
    ch["saving_throw"] = 0
    result = magic.spell_bless(1, 20, ch, trinket, magic.TARGET_OBJ)
    assert result is True
    assert ch["saving_throw"] == 0


def test_curse_worn_object_adjusts_caster_saving_throw(out):
    ch = _make_player()
    trinket = {"vnum": TRINKET_VNUM}
    ch["equip"]["light"] = trinket
    ch["saving_throw"] = 0
    result = magic.spell_curse(1, 20, ch, trinket, magic.TARGET_OBJ)
    assert result is True
    assert ch["saving_throw"] == 1


def test_curse_carried_object_does_not_adjust_saving_throw(out):
    ch = _make_player()
    trinket = {"vnum": TRINKET_VNUM}
    ch["inv"].append(trinket)
    ch["saving_throw"] = 0
    result = magic.spell_curse(1, 20, ch, trinket, magic.TARGET_OBJ)
    assert result is True
    assert ch["saving_throw"] == 0


# -- spell_create_rose --------------------------------------------------------

def test_create_rose_adds_to_caster_inventory(out):
    ch = _make_player()
    result = magic.spell_create_rose(1, 20, ch, ch, magic.TARGET_NONE)
    assert result is True
    roses = [o for o in ch["inv"] if o["vnum"] == world.OBJ_VNUM_ROSE]
    assert len(roses) == 1
    assert any("create a beautiful red rose" in l for l in out)


# -- mob.py ACT_SCAVENGER floor pickup ---------------------------------------

def _scav_mob(mid=3, room=9001):
    inst = _make_mob(mid, room=room, tpl=SCAV_MOB_TPL)
    inst["pos"] = "standing"
    inst["fighting"] = None
    inst["hunting"] = None
    inst["affected_by"] = {}
    inst["home_area"] = "test"
    return inst


def test_scavenger_picks_best_take_flagged_item(monkeypatch):
    inst = _scav_mob()
    room_items = world.rooms[9001]["items"]
    low = {"vnum": JUNK_LOW_VNUM, "cost": 1}       # cost == max(1) -> excluded
    notake = {"vnum": JUNK_NOTAKE_VNUM, "cost": 999}  # no take flag -> excluded
    best = {"vnum": JUNK_BEST_VNUM, "cost": 12}
    floor_only = {"vnum": JUNK_FLOOR_VNUM, "cost": 5}
    room_items.extend([low, notake, best, floor_only])
    monkeypatch.setattr(mob, "randint", lambda a, b: 0)  # cf. number_bits(6)==0
    mob.mobile_update(None, _make_player())
    assert best in inst["inv"]
    assert best not in room_items
    assert low in room_items and notake in room_items and floor_only in room_items


def test_scavenger_gate_not_triggered(monkeypatch):
    inst = _scav_mob()
    room_items = world.rooms[9001]["items"]
    best = {"vnum": JUNK_BEST_VNUM, "cost": 12}
    room_items.append(best)
    monkeypatch.setattr(mob, "randint", lambda a, b: b)  # never rolls 0
    mob.mobile_update(None, _make_player())
    assert best in room_items
    assert best not in inst["inv"]


def test_scavenger_no_floor_items_noop(monkeypatch):
    inst = _scav_mob()
    monkeypatch.setattr(mob, "randint", lambda a, b: 0)
    mob.mobile_update(None, _make_player())
    assert inst["inv"] == []
