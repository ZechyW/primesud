"""Tests for _death_cry: part-gated messages, body-part drops, poison food,
and adjacent-room cry broadcast (cf. 1stMud death_cry in fight.c). [PRIMESUD]
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
import world
from world import ROOM_DEFS, ITEM_DEFS, MOB_DEFS
from player import create_char
from races import RACE_TABLE

MOB_TPL = 9403

# Real area_limbo.txt #12/#13/#16 templates, stubbed here so tests don't
# depend on the on-disk area file or global lazy-load state (cf.
# tests/test_bugs.py _stub_item_tpl pattern).
I_HEAD  = 12
I_HEART = 13
I_GUTS  = 16


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_char(cid=1, npc=False, **overrides):
    ch = _char_base()
    ch["id"] = cid
    ch["is_npc"] = npc
    ch["name"] = "Tester" if not npc else "a test mob"
    ch["level"] = 20
    ch["room"] = 9001
    if npc:
        ch["tpl"] = MOB_TPL
    ch.update(overrides)
    world.chars[cid] = ch
    if npc and ch["room"] in world.rooms._data:
        world.rooms._data[ch["room"]]["mobs"].append(cid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test mob", "long_descr": "A test mob is here.",
        "keywords": "mob test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    ITEM_DEFS._data[I_HEAD] = {
        "keywords": "head", "short_descr": "The head of %s",
        "description": "The severed head of %s is lying here.",
        "material": "meat", "type": "trash", "level": 0, "weight": 50, "value": 0,
    }
    ITEM_DEFS._data[I_HEART] = {
        "keywords": "heart", "short_descr": "The heart of %s",
        "description": "The torn-out heart of %s is lying here.",
        "material": "meat", "type": "food", "level": 0, "weight": 20, "value": 0,
    }
    ITEM_DEFS._data[I_GUTS] = {
        "keywords": "guts entrails", "short_descr": "The guts of %s",
        "description": "A steaming pile of %s's entrails is lying here.",
        "material": "meat", "type": "food", "level": 0, "weight": 20, "value": 0,
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
    cap = lambda s="", end="\n": lines.append(s)
    import handler
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


def _force_roll(monkeypatch, roll):
    """Force the case-selection roll while leaving other randint calls
    (e.g. the body-part obj timer) untouched. [PRIMESUD]"""
    monkeypatch.setattr(combat, "randint",
                         lambda a, b: roll if (a, b) == (0, 15) else b)


class TestPartGatedDrop:
    def test_case_one_npc_falls_through_to_guts(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={"guts": True})
        _force_roll(monkeypatch, 1)

        combat._death_cry(mob)

        assert any("spills" in line and "guts" in line for line in out)
        assert world.rooms[9001]["items"][0]["vnum"] == combat._OBJ_VNUM_GUTS

    def test_case_one_pc_keeps_blood_message(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        victim = _make_char(2, npc=False, room=9001)
        _force_roll(monkeypatch, 1)

        combat._death_cry(victim)

        assert any("splatters blood" in line for line in out)
        assert world.rooms[9001]["items"] == []

    def test_guts_flag_set_drops_object_and_message(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={"guts": True})
        _force_roll(monkeypatch, 2)  # case 2: guts

        combat._death_cry(mob)

        assert any("spills" in l and "guts" in l for l in out)
        room = world.rooms[9001]
        assert len(room["items"]) == 1
        obj = room["items"][0]
        assert obj["vnum"] == combat._OBJ_VNUM_GUTS
        assert obj["short_descr"] == "The guts of a test mob"
        assert obj["description"] == "A steaming pile of a test mob's entrails is lying here."
        assert 4 <= obj["timer"] <= 7

    def test_guts_flag_absent_no_object_falls_back_to_default(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={})
        _force_roll(monkeypatch, 2)  # case 2: guts, but flag unset

        combat._death_cry(mob)

        assert any("death cry" in l for l in out)
        assert not any("guts" in l for l in out)
        assert world.rooms[9001]["items"] == []

    def test_head_gated_object_uses_trash_template(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={"head": True})
        _force_roll(monkeypatch, 3)  # case 3: head

        combat._death_cry(mob)

        room = world.rooms[9001]
        assert len(room["items"]) == 1
        obj = room["items"][0]
        assert obj["vnum"] == I_HEAD
        assert obj["short_descr"] == "The head of a test mob"
        # head template is ITEM_TRASH, not food -- poison/edible logic must not fire
        assert "poisoned" not in obj
        assert "type" not in obj


class TestPoisonFood:
    def test_form_poison_sets_poisoned_flag(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={"heart": True},
                          form_flags={"poison": True, "edible": True})
        _force_roll(monkeypatch, 4)  # case 4: heart

        combat._death_cry(mob)

        obj = world.rooms[9001]["items"][0]
        assert obj["vnum"] == I_HEART
        assert obj["poisoned"] is True
        assert "type" not in obj

    def test_non_edible_non_poison_food_downgrades_to_trash(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={"heart": True},
                          form_flags={"edible": False})
        _force_roll(monkeypatch, 4)  # case 4: heart

        combat._death_cry(mob)

        obj = world.rooms[9001]["items"][0]
        assert obj["vnum"] == I_HEART
        assert obj.get("poisoned") is not True
        assert obj["type"] == "trash"

    def test_edible_food_untouched(self, monkeypatch, out):
        player = _make_char(1, npc=False, room=9001)
        mob = _make_char(2, npc=True, part_flags={"heart": True},
                          form_flags={"edible": True})
        _force_roll(monkeypatch, 4)  # case 4: heart

        combat._death_cry(mob)

        obj = world.rooms[9001]["items"][0]
        assert "poisoned" not in obj
        assert "type" not in obj


class TestPCRaceFormParts:
    """PC form_flags/part_flags come from RACE_TABLE via player.create_char
    (cf. 1stMud nanny.c:533-534 / save.c:723-724), so PC deaths hit the same
    part-drop logic as mobs. [PRIMESUD] regression test for TODO.md's
    "PC victims never drop body parts"."""

    def test_create_char_populates_race_combat_defaults(self):
        ch = create_char(race_name="Elf")
        elf = RACE_TABLE["Elf"]
        expected_stats = {
            "str": elf["stats"][0] + 3, "dex": elf["stats"][1],
            "int": elf["stats"][2], "wis": elf["stats"][3],
            "con": elf["stats"][4],
        }
        assert ch["affected_by"] == dict(elf["aff"])
        assert ch["imm_flags"] == dict(elf["imm"])
        assert ch["res_flags"] == dict(elf["res"])
        assert ch["vuln_flags"] == dict(elf["vuln"])
        assert ch["perm_stat"] == expected_stats
        assert ch["size"] == elf["size"]

    def test_create_char_populates_form_and_part_flags_from_race(self):
        ch = create_char()
        human = RACE_TABLE["Human"]
        assert ch["form_flags"] == dict(human["form"])
        assert ch["part_flags"] == dict(human["parts"])

    def test_pc_victim_of_part_bearing_race_drops_body_part(self, monkeypatch, out):
        victim = create_char()
        victim["id"] = 2
        victim["room"] = 9001
        victim["name"] = "Tester"
        world.chars[2] = victim
        player = _make_char(1, npc=False, room=9001)
        _force_roll(monkeypatch, 2)  # case 2: guts

        combat._death_cry(victim)

        assert any("spills" in l and "guts" in l for l in out)
        room = world.rooms[9001]
        assert len(room["items"]) == 1
        obj = room["items"][0]
        assert obj["vnum"] == combat._OBJ_VNUM_GUTS
        assert obj["short_descr"] == "The guts of Tester"
        assert obj["description"] == "A steaming pile of Tester's entrails is lying here."


class TestAdjacentRoomCry:
    def test_cry_heard_in_adjacent_room(self, monkeypatch, out):
        _stub_room(9002, exits={"s": {"to": 9001}})
        ROOM_DEFS._data[9001]["exits"] = {"n": {"to": 9002}}
        mob = _make_char(2, npc=True, part_flags={})
        player = _make_char(1, npc=False, room=9002)
        _force_roll(monkeypatch, 8)  # no case -> default msg, no object

        combat._death_cry(mob)

        assert any("You hear something's death cry." in l for l in out)

    def test_no_cry_when_player_not_adjacent(self, monkeypatch, out):
        _stub_room(9099)  # unrelated, unconnected room
        mob = _make_char(2, npc=True, part_flags={})
        player = _make_char(1, npc=False, room=9099)
        _force_roll(monkeypatch, 8)

        combat._death_cry(mob)

        assert not any("death cry" in l for l in out)

    def test_pc_victim_uses_someone_variant(self, monkeypatch, out):
        _stub_room(9002, exits={"s": {"to": 9001}})
        ROOM_DEFS._data[9001]["exits"] = {"n": {"to": 9002}}
        victim = _make_char(2, npc=False, room=9001)
        player = _make_char(1, npc=False, room=9002)
        _force_roll(monkeypatch, 8)

        combat._death_cry(victim)

        assert any("You hear someone's death cry." in l for l in out)
