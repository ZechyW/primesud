"""Tests for auto-open/auto-close of unlocked doors during movement. [PRIMESUD]"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import movement
import world
from handler import _char_base
from world import ROOM_DEFS

KEY_VNUM = 8100


@pytest.fixture
def out(monkeypatch):
    lines = []
    cap = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(movement, "tprint", cap)
    monkeypatch.setattr(movement, "do_look", lambda ch, args: None)
    import handler
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_room_defs = dict(ROOM_DEFS._data)
    old_chars = dict(world.chars)

    door = {"to": 3002, "isdoor": True, "closed": True, "key": KEY_VNUM}
    rev_door = {"to": 3001, "isdoor": True, "closed": True, "key": KEY_VNUM}
    r1 = {"name": "Here", "desc": "x", "exits": {"n": door}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    r2 = {"name": "There", "desc": "x", "exits": {"s": rev_door}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    for vnum, room in ((3001, r1), (3002, r2)):
        world.rooms._data[vnum] = room
        ROOM_DEFS._data[vnum] = room

    player = _char_base()
    player.update({"id": 1, "room": 3001, "level": 5, "pos": "standing",
                   "move": 100, "inv": [{"vnum": KEY_VNUM}]})
    world.chars[1] = player

    yield player

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_room_defs)
    world.chars.clear()
    world.chars.update(old_chars)


def _door(vnum=3001, d="n"):
    return ROOM_DEFS[vnum]["exits"][d]


class TestAutoDoor:
    def test_closed_unlocked_door_auto_opens_and_recloses(self, scene, out):
        movement.move_char(scene, "n")
        assert scene["room"] == 3002
        assert _door()["closed"] is True
        assert _door(3002, "s")["closed"] is True
        assert "You open the door." in out
        assert "You close the door behind you." in out

    def test_locked_door_stays_blocked(self, scene, out):
        _door()["locked"] = True
        movement.move_char(scene, "n")
        assert scene["room"] == 3001
        assert "The door is closed." in out
        assert _door()["closed"] is True

    def test_keyword_used_in_messages(self, scene, out):
        _door()["keyword"] = "gate iron"
        _door(3002, "s")["keyword"] = "gate iron"
        movement.move_char(scene, "n")
        assert "You open the gate." in out
        assert "You close the gate behind you." in out

    def test_noclose_door_stays_open(self, scene, out):
        _door()["noclose"] = True
        movement.move_char(scene, "n")
        assert scene["room"] == 3002
        assert not _door().get("closed")
        assert not any("You close the door behind you." in l for l in out)

    def test_pass_door_skips_auto_open(self, scene, out):
        scene["affected_by"] = {"pass_door": True}
        movement.move_char(scene, "n")
        assert scene["room"] == 3002
        assert _door()["closed"] is True
        assert not any("You open the door." in l for l in out)

    def test_npc_actor_stays_blocked(self, scene, out):
        scene["is_npc"] = True
        world.rooms[3001]["mobs"] = [1]
        movement.move_char(scene, "n")
        assert scene["room"] == 3001
        assert "The door is closed." in out
        assert _door()["closed"] is True
