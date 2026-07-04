"""Tests for lock/unlock/pick door commands."""
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
    player.update({"id": 1, "room": 3001, "level": 5,
                   "inv": [{"vnum": KEY_VNUM}]})
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


class TestLock:
    def test_lock_with_key(self, scene, out):
        movement.do_lock(scene, ["north"])
        assert _door()["locked"] is True
        assert _door(3002, "s")["locked"] is True  # reverse side
        assert "*Click*" in out

    def test_lock_without_key(self, scene, out):
        scene["inv"] = []
        movement.do_lock(scene, ["north"])
        assert not _door().get("locked")
        assert "You lack the key." in out

    def test_lock_open_door(self, scene, out):
        _door()["closed"] = False
        movement.do_lock(scene, ["north"])
        assert "It's not closed." in out

    def test_lock_keyless_door(self, scene, out):
        del _door()["key"]
        movement.do_lock(scene, ["north"])
        assert "It can't be locked." in out

    def test_already_locked(self, scene, out):
        _door()["locked"] = True
        movement.do_lock(scene, ["north"])
        assert "It's already locked." in out


class TestUnlock:
    def test_unlock_with_key(self, scene, out):
        _door()["locked"] = True
        _door(3002, "s")["locked"] = True
        movement.do_unlock(scene, ["north"])
        assert _door()["locked"] is False
        assert _door(3002, "s")["locked"] is False
        assert "*Click*" in out

    def test_already_unlocked(self, scene, out):
        movement.do_unlock(scene, ["north"])
        assert "It's already unlocked." in out


class TestPick:
    def test_pick_success(self, scene, out, monkeypatch):
        _door()["locked"] = True
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 100)
        monkeypatch.setattr(movement, "randint", lambda a, b: 1)
        monkeypatch.setattr(movement, "check_improve", lambda *a: None)
        movement.do_pick(scene, ["north"])
        assert _door()["locked"] is False
        assert "*Click*" in out

    def test_pick_skill_fail(self, scene, out, monkeypatch):
        _door()["locked"] = True
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 0)
        monkeypatch.setattr(movement, "randint", lambda a, b: 100)
        monkeypatch.setattr(movement, "check_improve", lambda *a: None)
        movement.do_pick(scene, ["north"])
        assert _door()["locked"] is True
        assert "You failed." in out

    def test_pick_pickproof(self, scene, out, monkeypatch):
        _door()["locked"] = True
        _door()["pickproof"] = True
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 100)
        monkeypatch.setattr(movement, "randint", lambda a, b: 1)
        movement.do_pick(scene, ["north"])
        assert _door()["locked"] is True
        assert "You failed." in out

    def test_high_level_mob_blocks(self, scene, out, monkeypatch):
        from world import MOB_DEFS
        old_mobs = dict(MOB_DEFS._data)
        MOB_DEFS._data[9001] = {"short_descr": "a titan", "keywords": "titan",
                                "level": 50, "description": "big"}
        mob = _char_base()
        mob.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                    "level": 50, "pos": "standing"})
        world.chars[2] = mob
        world.rooms[3001]["mobs"] = [2]
        _door()["locked"] = True
        try:
            movement.do_pick(scene, ["north"])
            assert _door()["locked"] is True
            assert any("standing too close to the lock" in l for l in out)
        finally:
            MOB_DEFS._data.clear()
            MOB_DEFS._data.update(old_mobs)


class TestDoorActRouting:
    def test_close_room_act_and_ok(self, scene, out):
        _door()["closed"] = False
        _door(3002, "s")["closed"] = False
        movement.do_close(scene, ["north"])
        assert _door()["closed"] is True
        assert _door(3002, "s")["closed"] is True
        assert "Ok." in out
        assert not any("closes the" in l for l in out)

    def test_close_far_side_message(self, scene, out):
        from world import MOB_DEFS
        old_mobs = dict(MOB_DEFS._data)
        MOB_DEFS._data[9002] = {"short_descr": "a test dog",
                                "keywords": "dog test"}
        _door()["closed"] = False
        _door(3002, "s")["closed"] = False
        npc = _char_base()
        npc.update({"is_npc": True, "id": 2, "tpl": 9002, "room": 3001,
                    "level": 5, "pos": "standing"})
        world.chars[2] = npc
        world.rooms[3001]["mobs"] = [2]
        scene["room"] = 3002
        try:
            movement.do_close(npc, ["north"])
            assert _door()["closed"] is True
            assert any("The door closes" in l for l in out)
            assert "Ok." not in out
        finally:
            MOB_DEFS._data.clear()
            MOB_DEFS._data.update(old_mobs)
            if 2 in world.chars:
                del world.chars[2]

    def test_close_npc_room_act_visible(self, scene, out):
        from world import MOB_DEFS
        old_mobs = dict(MOB_DEFS._data)
        MOB_DEFS._data[9002] = {"short_descr": "a test dog",
                                "keywords": "dog test"}
        _door()["closed"] = False
        _door(3002, "s")["closed"] = False
        npc = _char_base()
        npc.update({"is_npc": True, "id": 2, "tpl": 9002, "room": 3001,
                    "level": 5, "pos": "standing"})
        world.chars[2] = npc
        world.rooms[3001]["mobs"] = [2]
        try:
            movement.do_close(npc, ["north"])
            assert any("closes the door" in l for l in out)
            assert "Ok." not in out
        finally:
            MOB_DEFS._data.clear()
            MOB_DEFS._data.update(old_mobs)
            if 2 in world.chars:
                del world.chars[2]

    def test_lock_npc_no_click_leak(self, scene, out, monkeypatch):
        from world import MOB_DEFS
        old_mobs = dict(MOB_DEFS._data)
        MOB_DEFS._data[9002] = {"short_descr": "a test dog",
                                "keywords": "dog test"}
        _door()["closed"] = True
        _door()["locked"] = False
        _door(3002, "s")["closed"] = True
        _door(3002, "s")["locked"] = False
        npc = _char_base()
        npc.update({"is_npc": True, "id": 2, "tpl": 9002, "room": 3001,
                    "level": 5, "pos": "standing", "inv": [{"vnum": KEY_VNUM}]})
        world.chars[2] = npc
        world.rooms[3001]["mobs"] = [2]
        try:
            movement.do_lock(npc, ["north"])
            assert _door()["locked"] is True
            assert any("locks the door" in l for l in out)
            assert "*Click*" not in out
        finally:
            MOB_DEFS._data.clear()
            MOB_DEFS._data.update(old_mobs)
            if 2 in world.chars:
                del world.chars[2]

    def test_unlock_npc_room_act(self, scene, out):
        from world import MOB_DEFS
        old_mobs = dict(MOB_DEFS._data)
        MOB_DEFS._data[9002] = {"short_descr": "a test dog",
                                "keywords": "dog test"}
        _door()["closed"] = True
        _door()["locked"] = True
        _door(3002, "s")["closed"] = True
        _door(3002, "s")["locked"] = True
        npc = _char_base()
        npc.update({"is_npc": True, "id": 2, "tpl": 9002, "room": 3001,
                    "level": 5, "pos": "standing", "inv": [{"vnum": KEY_VNUM}]})
        world.chars[2] = npc
        world.rooms[3001]["mobs"] = [2]
        try:
            movement.do_unlock(npc, ["north"])
            assert _door()["locked"] is False
            assert any("unlocks the door" in l for l in out)
            assert "*Click*" not in out
        finally:
            MOB_DEFS._data.clear()
            MOB_DEFS._data.update(old_mobs)
            if 2 in world.chars:
                del world.chars[2]

    def test_pick_npc_room_act(self, scene, out, monkeypatch):
        from world import MOB_DEFS
        old_mobs = dict(MOB_DEFS._data)
        MOB_DEFS._data[9002] = {"short_descr": "a test dog",
                                "keywords": "dog test"}
        _door()["closed"] = True
        _door()["locked"] = True
        _door(3002, "s")["closed"] = True
        _door(3002, "s")["locked"] = True
        npc = _char_base()
        npc.update({"is_npc": True, "id": 2, "tpl": 9002, "room": 3001,
                    "level": 5, "pos": "standing"})
        world.chars[2] = npc
        world.rooms[3001]["mobs"] = [2]
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 100)
        monkeypatch.setattr(movement, "randint", lambda a, b: 1)
        monkeypatch.setattr(movement, "check_improve", lambda *a: None)
        try:
            movement.do_pick(npc, ["north"])
            assert _door()["locked"] is False
            assert any("picks the door" in l for l in out)
            assert "*Click*" not in out
        finally:
            MOB_DEFS._data.clear()
            MOB_DEFS._data.update(old_mobs)
            if 2 in world.chars:
                del world.chars[2]
