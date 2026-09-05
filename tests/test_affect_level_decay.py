"""Tests for per-tick affect level decay in _tick_affects (cf. 1stMud char_update affect loop in update.c:650-651). [PRIMESUD test]
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import player
from player import GSN_PLAGUE
from world import ROOM_DEFS

ROOM_VNUM = 9701


def _stub_room(vnum=ROOM_VNUM, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    return room


def _make_player(room=ROOM_VNUM, **overrides):
    ch = _char_base()
    ch.update({"id": 1, "name": "Tester", "level": 10, "room": room})
    ch.update(overrides)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    _stub_room()
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)


def _plague_level(level, duration=5):
    return {"type": GSN_PLAGUE, "level": level, "duration": duration}


def test_tick_affects_decays_level_on_one_in_five_roll(monkeypatch):
    """cf. 1stMud update.c:650-651 -- number_range(0,4)==0 drops level by 1."""
    monkeypatch.setattr(player, "randint", lambda a, b: 0)
    ch = _make_player()
    ch["affect_list"].append(_plague_level(3))
    player._tick_affects(ch, None)
    aff = ch["affect_list"][0]
    assert aff["duration"] == 4
    assert aff["level"] == 2


def test_tick_affects_keeps_level_when_roll_misses(monkeypatch):
    """cf. 1stMud update.c:650-651 -- a non-zero roll leaves level intact."""
    monkeypatch.setattr(player, "randint", lambda a, b: 1)
    ch = _make_player()
    ch["affect_list"].append(_plague_level(3))
    player._tick_affects(ch, None)
    aff = ch["affect_list"][0]
    assert aff["duration"] == 4
    assert aff["level"] == 3


def test_tick_affects_level_floor_at_zero(monkeypatch):
    """cf. 1stMud update.c:650-651 -- paf->level>0 guard: level 0 stays 0."""
    monkeypatch.setattr(player, "randint", lambda a, b: 0)
    ch = _make_player()
    ch["affect_list"].append(_plague_level(0))
    player._tick_affects(ch, None)
    aff = ch["affect_list"][0]
    assert aff["duration"] == 4
    assert aff["level"] == 0
