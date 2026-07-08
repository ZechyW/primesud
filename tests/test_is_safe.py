"""Tests for is_safe / is_safe_spell ROOM_SAFE + ACT_PET gates vs 1stMud fight.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
from combat import is_safe, is_safe_spell
import world
from world import ROOM_DEFS, MOB_DEFS


MOB_TPL = 9401
SAFE_ROOM = 9001
OPEN_ROOM = 9002


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "d", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _player(room=OPEN_ROOM):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    world.chars[1] = ch
    return ch


def _mob(mid=2, room=OPEN_ROOM, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = MOB_TPL
    ch["name"] = "a test dog"
    ch["level"] = 5
    ch["room"] = room
    ch.update(overrides)
    world.chars[mid] = ch
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test dog", "keywords": "dog", "level": 5,
        "race": "Human", "hp_dice": (1, 1, 10), "damage": (1, 4, 0),
        "hitroll": 0, "armor": (0, 0, 0, 0),
    }
    _stub_room(SAFE_ROOM, flags={"safe": True})
    _stub_room(OPEN_ROOM)
    yield
    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear(); world.rooms._data.update(old_wrooms)
    world.chars.clear(); world.chars.update(old_chars)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_mobs)


class TestIsSafe:
    def test_room_safe_blocks(self, capsys):
        player = _player(SAFE_ROOM)
        victim = _mob(room=SAFE_ROOM)
        assert is_safe(player, victim) is True
        assert "Not in this room." in capsys.readouterr().out

    def test_pet_blocks(self, capsys):
        player = _player()
        victim = _mob()
        victim["act_flags"]["pet"] = True
        assert is_safe(player, victim) is True
        assert "cute and cuddly" in capsys.readouterr().out

    def test_open_room_normal_mob_not_safe(self, capsys):
        player = _player()
        victim = _mob()
        assert is_safe(player, victim) is False


class TestIsSafeSpell:
    def test_room_safe_blocks(self):
        player = _player(SAFE_ROOM)
        victim = _mob(room=SAFE_ROOM)
        assert is_safe_spell(player, victim, False) is True

    def test_pet_blocks(self):
        player = _player()
        victim = _mob()
        victim["act_flags"]["pet"] = True
        assert is_safe_spell(player, victim, False) is True

    def test_open_room_normal_mob_not_safe(self):
        player = _player()
        victim = _mob()
        assert is_safe_spell(player, victim, False) is False
