"""Tests for elemental item/room/char effects (cf. 1stMud effects.c). [PRIMESUD test]

Covers acid/fire/cold/shock/poison item destruction and character side
effects, container-content spill recursion, and the breath-spell/weapon-proc
call sites wired in magic.py/combat.py.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import combat
import effects
import handler
import magic
import world
from world import ROOM_DEFS, ITEM_DEFS, MOB_DEFS

MOB_TPL = 9501
ROOM_VNUM = 9001
BREAD_VNUM = 9510
DRINK_VNUM = 9511
WAND_VNUM = 9512
CHEST_VNUM = 9513
TRINKET_VNUM = 9514


def _stub_room(vnum=ROOM_VNUM, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=ROOM_VNUM, **overrides):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    ch.update(overrides)
    world.chars[1] = ch
    return ch


def _make_mob(mid, room=ROOM_VNUM, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = MOB_TPL
    ch["name"] = "a test dog"
    ch["level"] = 20
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
        "keywords": "dog test", "level": 20, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    ITEM_DEFS._data[BREAD_VNUM] = {
        "keywords": "bread test", "short_descr": "a loaf of bread",
        "type": "food", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
    }
    ITEM_DEFS._data[DRINK_VNUM] = {
        "keywords": "waterskin test", "short_descr": "a test waterskin",
        "type": "drink", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
        "liquid_total": 10, "liquid_left": 10, "liquid_type": "water",
    }
    ITEM_DEFS._data[WAND_VNUM] = {
        "keywords": "wand test", "short_descr": "a test wand",
        "type": "wand", "level": 10, "extra_flags": {},
        "wear_flags": {"take": True, "hold": True},
    }
    ITEM_DEFS._data[CHEST_VNUM] = {
        "keywords": "chest test", "short_descr": "a test chest",
        "type": "container", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
    }
    ITEM_DEFS._data[TRINKET_VNUM] = {
        "keywords": "trinket test", "short_descr": "a test trinket",
        "type": "trash", "level": 0, "extra_flags": {},
        "wear_flags": {"take": True},
    }
    _stub_room(ROOM_VNUM)
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
    cap = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


@pytest.fixture
def force_roll(monkeypatch):
    """Force every effects.py chance/skip roll to succeed. [PRIMESUD]

    randint(0, 4) == 0 is the early "immune this time" skip roll (must
    NOT return 0); randint(1, 100) is the destroy/mutate chance roll
    (must be low enough to clear the >=5 clamp floor).
    """
    monkeypatch.setattr(effects, "randint", lambda a, b: 1)


# -- Item destruction ------------------------------------------------------------

def test_fire_destroys_food_with_message(out, force_roll):
    """fire_effect destroys a carried food item and broadcasts the $p message.

    Carrier is a mob sharing the player's room; under ROM's room-scoped
    TO_ALL (see test_to_all_is_room_scoped_including_ch) the player receives
    it as a bystander.
    """
    _make_player()
    mob = _make_mob(2)
    mob["inv"].append({"vnum": BREAD_VNUM})
    effects.fire_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert not mob["inv"]
    assert any("blackens and crisps" in l for l in out)


def test_shock_destroys_equipped_wand_and_reverses_stat_bonus(out, force_roll):
    """shock_effect destroys a held item and properly unequips it first."""
    mob = _make_mob(2)
    mob["equip"] = {"hold": {"vnum": WAND_VNUM}}
    effects.shock_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert mob["equip"]["hold"] is None
    assert not mob["inv"]  # unequip_char's inv.append then destroy removed it again


def test_acid_leaves_armor_corroded_not_destroyed(force_roll):
    """acid_effect on worn armor adds an AC affect and bumps live armor, but
    does not destroy the item (cf. 1stMud acid_effect ITEM_ARMOR branch)."""
    ITEM_DEFS._data[9515] = {
        "keywords": "shield test", "short_descr": "a test shield",
        "type": "armor", "level": 5, "extra_flags": {},
        "wear_flags": {"take": True, "shield": True},
    }
    mob = _make_mob(2)
    shield = {"vnum": 9515}
    mob["equip"] = {"shield": shield}
    mob["armor"] = (100, 100, 100, 100)
    effects.acid_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert mob["equip"]["shield"] is shield  # survives, still equipped
    assert any(af.get("location") == "ac" for af in shield.get("affect_list", []))
    assert mob["armor"] == (101, 101, 101, 101)


# -- Container content spill -------------------------------------------------------

def test_fire_spills_container_contents_to_room_and_recurses(force_roll):
    """Destroying a container in a room dumps its contents to the room floor
    and recurses the effect on them at half level/dam (cf. 1stMud
    obj_to_room + recursive fire_effect(t_obj, level/2, dam/2, TARGET_OBJ))."""
    room = world.rooms[ROOM_VNUM]
    inner = {"vnum": TRINKET_VNUM}
    chest = {"vnum": CHEST_VNUM, "contents": [inner]}
    room["items"].append(chest)

    effects.fire_effect(room, 20, 50, effects.TARGET_ROOM)

    assert chest not in room["items"]
    assert inner in room["items"]


def test_container_dump_falls_back_to_carrier_room(force_roll):
    """A carried container's spilled contents land in the carrier's current
    room, not their inventory (cf. 1stMud obj_to_room(t_obj, carried_by->in_room))."""
    mob = _make_mob(2)
    inner = {"vnum": TRINKET_VNUM}
    chest = {"vnum": CHEST_VNUM, "contents": [inner]}
    mob["inv"].append(chest)

    effects.acid_effect(mob, 20, 50, effects.TARGET_CHAR)

    room = world.rooms[ROOM_VNUM]
    assert chest not in mob["inv"]
    assert inner in room["items"]


# -- Character side effects --------------------------------------------------------

def test_fire_blinds_char_when_save_fails(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    mob = _make_mob(2)
    effects.fire_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert mob["affected_by"].get("blind")
    assert any(af.get("bitvector") == "blind" for af in mob["affect_list"])


def test_fire_does_not_blind_char_when_save_succeeds(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: True)
    mob = _make_mob(2)
    effects.fire_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert not mob["affected_by"].get("blind")


def test_shock_dazes_char_when_save_fails(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    mob = _make_mob(2)
    effects.shock_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert mob["daze"] == max(12, 20 // 4 + 50 // 20)


def test_cold_chills_char_when_save_fails(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    mob = _make_mob(2)
    effects.cold_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert any(af.get("location") == "str" and af.get("modifier") == -1
               for af in mob["affect_list"])


def test_poison_sickens_char_when_save_fails(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    mob = _make_mob(2)
    effects.poison_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert mob["affected_by"].get("poison")


# -- Poison food/drink --------------------------------------------------------------

def test_poison_effect_poisons_food_and_open_drink(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: True)  # skip char-side affect
    mob = _make_mob(2)
    bread = {"vnum": BREAD_VNUM}
    open_drink = {"vnum": DRINK_VNUM, "liquid_total": 10, "liquid_left": 4}
    mob["inv"].extend([bread, open_drink])
    effects.poison_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert bread["poisoned"] is True
    assert open_drink["poisoned"] is True


def test_poison_effect_skips_full_unopened_drink(monkeypatch, force_roll):
    monkeypatch.setattr(magic, "saves_spell", lambda *a: True)
    mob = _make_mob(2)
    full_drink = {"vnum": DRINK_VNUM}  # liquid_total == liquid_left (unopened)
    mob["inv"].append(full_drink)
    effects.poison_effect(mob, 20, 50, effects.TARGET_CHAR)
    assert "poisoned" not in full_drink


# -- Breath-spell call-site wiring ---------------------------------------------------

def test_spell_lightning_breath_wires_shock_effect(out, monkeypatch, force_roll):
    """spell_lightning_breath's saved-branch calls shock_effect(victim,
    level/2, dam/4, TARGET_CHAR), which can destroy a held wand
    (cf. magic.c spell_lightning_breath)."""
    player = _make_player()
    caster = _make_mob(2)
    wand = {"vnum": WAND_VNUM}
    player["equip"] = {"hold": wand}
    monkeypatch.setattr(magic, "saves_spell", lambda *a: True)
    monkeypatch.setattr(magic, "damage", lambda *a, **kw: True)
    magic.spell_lightning_breath(0, 20, caster, player, magic.TARGET_CHAR)
    assert player["equip"]["hold"] is None


def test_weapon_proc_flaming_wires_fire_effect(out, monkeypatch, force_roll):
    """combat._weapon_procs' flaming branch calls fire_effect(victim,
    wlevel/2, pdam, TARGET_CHAR) before dealing proc damage (cf. fight.c
    one_hit:831-838)."""
    player = _make_player()
    mob = _make_mob(2)
    player["fighting"] = 2
    mob["fighting"] = 1
    mob["inv"].append({"vnum": BREAD_VNUM})
    wobj = {"vnum": 9516, "level": 20, "weapon_flags": {"flaming": True}}
    ITEM_DEFS._data[9516] = {
        "keywords": "sword test", "short_descr": "a test sword",
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "weapon_flags": {}, "level": 20,
        "wear_flags": {"take": True, "wield": True},
    }
    player["equip"]["wield"] = wobj
    monkeypatch.setattr(combat, "damage", lambda *a, **kw: None)
    combat._weapon_procs(player, mob, wobj, ITEM_DEFS[9516])
    assert not mob["inv"]  # bread destroyed by the fire_effect(mob, ...) call


# -- act() TO_ALL routing ---------------------------------------------------------

def test_to_all_is_room_scoped_including_ch(out):
    """TO_ALL reaches ch and ch's room only, never another room.

    Guards the ROM 2.4 semantics restored in handler.py: TO_ALL is
    TO_ROOM | TO_CHAR, not 1stMud's mud-wide BIT_E broadcast. Both flips
    that redefinition caused are covered -- ch getting dropped (case 1) and
    room chatter leaking world-wide (case 3). See docs/FIXES.md.
    """
    player = _make_player()

    # 1. player is ch: 1stMud's "vch != ch" dropped this message entirely
    handler.act("You feel $t.", player, "warm", None, handler.TO_ALL)
    assert any("You feel warm." in l for l in out)

    # 2. mob in the player's room: player receives it as a bystander
    del out[:]
    mob = _make_mob(2)
    handler.act("$n barks.", mob, None, None, handler.TO_ALL)
    assert any("barks" in l for l in out)

    # 3. mob in another room: silent (the gangland-spam regression)
    del out[:]
    _stub_room(ROOM_VNUM + 1)
    far = _make_mob(3, room=ROOM_VNUM + 1)
    handler.act("$n barks.", far, None, None, handler.TO_ALL)
    assert not out
