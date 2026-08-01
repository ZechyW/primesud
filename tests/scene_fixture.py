"""Shared room/mob/item scene fixtures for the gear and info-command tests.

Not a test module (no `test_` prefix, so pytest skips collection): a plain
sibling import for the handful of files that need the same three-room,
one-mob, three-item world.  Lives here rather than in conftest.py because 32
other test modules define their own `out` fixture, and a conftest-level one
would shadow-collide with all of them.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import commands
import inventory
import world
from handler import _char_base
from skills_table import GSN_DAGGER, GSN_SWORD
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
                             "weapon_type": "sword",
                             "wear_flags": {"take": True, "wield": True}}
    ITEM_DEFS._data[8002] = {"type": "weapon", "keywords": "dagger",
                             "short_descr": "a dagger", "dice": (1, 4, 0),
                             "weapon_type": "dagger",
                             "wear_flags": {"take": True, "wield": True}}
    ITEM_DEFS._data[8003] = {"type": "armor", "keywords": "vest",
                             "short_descr": "a vest", "armor": (5, 5, 5, 0),
                             "wear_flags": {"take": True, "body": True}}

    player = _char_base()
    player.update({"id": 1, "room": 3001, "level": 10,
                   "learned": {GSN_SWORD: 80, GSN_DAGGER: 80},
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
