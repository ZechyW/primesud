"""Tests for exits / commands / consider / compare (Phase 1 ports)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
import commands
import info
import inventory
import world
from handler import _char_base
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    """Capture tprint output across all modules under test."""
    lines = []
    cap = lambda s="", end="\n": lines.append(s)
    # info/combat no longer import tprint (output routes via handler)
    for mod in (inventory, commands):
        monkeypatch.setattr(mod, "tprint", cap)
    import handler
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_room_defs = dict(ROOM_DEFS._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)

    r1 = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    r2 = {"name": "North Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    r3 = {"name": "East Room", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data[3001] = r1
    world.rooms._data[3002] = r2
    world.rooms._data[3003] = r3
    ROOM_DEFS._data[3001] = r1
    ROOM_DEFS._data[3002] = r2
    ROOM_DEFS._data[3003] = r3
    r1["exits"] = {"n": 3002, "e": {"to": 3003, "isdoor": True, "closed": True}}

    MOB_DEFS._data[9001] = {"short_descr": "a guard", "keywords": "guard",
                            "level": 10, "description": "A guard."}
    mob = _char_base()
    mob.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                "level": 10, "hit": 50, "max_hit": 50})
    world.chars[2] = mob
    r1["mobs"] = [2]

    ITEM_DEFS._data[8001] = {"type": "weapon", "keywords": "sword",
                             "short_descr": "a sword", "dice": (2, 6, 0),
                             "wear_flags": {"take": True, "wield": True}}
    ITEM_DEFS._data[8002] = {"type": "weapon", "keywords": "dagger",
                             "short_descr": "a dagger", "dice": (1, 4, 0),
                             "wear_flags": {"take": True, "wield": True}}
    ITEM_DEFS._data[8003] = {"type": "armor", "keywords": "vest",
                             "short_descr": "a vest", "armor": (5, 5, 5, 0),
                             "wear_flags": {"take": True, "body": True}}

    player = _char_base()
    player.update({"id": 1, "room": 3001, "level": 10,
                   "inv": [{"vnum": 8001}, {"vnum": 8002}, {"vnum": 8003}]})
    world.chars[1] = player

    yield player

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_room_defs)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


class TestExits:
    def test_open_exits_listed_closed_hidden(self, scene, out):
        info.do_exits(scene, [])
        assert out[0] == "Obvious exits:"
        assert any("North - North Room" in l for l in out)
        assert not any("East" in l for l in out)  # closed door hidden

    def test_no_exits(self, scene, out):
        ROOM_DEFS[3001]["exits"] = {}
        info.do_exits(scene, [])
        assert out == ["Obvious exits:", "None."]

    def test_runtime_room_state_shape(self, scene, out):
        # On device world.rooms entries are state-only ({"items", "mobs"});
        # static data lives in ROOM_DEFS. do_exits must not touch world.rooms.
        world.rooms._data[3001] = {"items": [], "mobs": []}
        world.rooms._data[3002] = {"items": [], "mobs": []}
        info.do_exits(scene, [])
        assert any("North - North Room" in l for l in out)


class TestCommands:
    def test_lists_known_commands(self, scene, out, monkeypatch):
        # do_commands routes through the tpage pager, not tprint
        monkeypatch.setattr(commands, "tpage", lambda lines: out.extend(lines))
        commands.do_commands(scene, [])
        blob = "\n".join(out)
        assert "kill" in blob and "look" in blob and "wimpy" in blob


class TestConsider:
    @pytest.mark.parametrize("mob_level,frag", [
        (0,  "naked and weaponless"),
        (5,  "no match for you"),
        (8,  "an easy kill"),
        (11, "The perfect match!"),
        (14, "Do you feel lucky, punk?"),
        (19, "laughs at you mercilessly"),
        (20, "Death will thank you"),
    ])
    def test_level_diff_messages(self, scene, out, mob_level, frag):
        world.chars[2]["level"] = mob_level
        combat.do_consider(scene, ["guard"])
        assert any(frag in l for l in out), out

    def test_not_here(self, scene, out):
        combat.do_consider(scene, ["dragon"])
        assert out == ["They're not here."]


class TestCompare:
    def test_better(self, scene, out):
        inventory.do_compare(scene, ["sword", "dagger"])
        assert any("looks better than" in l for l in out)

    def test_same_item(self, scene, out):
        inventory.do_compare(scene, ["sword", "sword"])
        assert any("compare a sword to itself" in l.lower() for l in out)

    def test_cross_type(self, scene, out):
        inventory.do_compare(scene, ["sword", "vest"])
        assert any("can't compare" in l for l in out)

    def test_vs_worn(self, scene, out):
        scene["equip"]["wield"] = scene["inv"].pop(1)  # wear the dagger
        inventory.do_compare(scene, ["sword"])
        assert any("looks better than" in l for l in out)

    def test_nothing_comparable(self, scene, out):
        inventory.do_compare(scene, ["sword"])
        assert out == ["You aren't wearing anything comparable."]
