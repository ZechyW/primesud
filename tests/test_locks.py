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
from world import ROOM_DEFS, ITEM_DEFS

KEY_VNUM = 8100
CHEST_VNUM = 8101


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
    old_items = dict(ITEM_DEFS._data)

    # cf. get_obj_here/get_obj_list's ITEM_DEFS[vnum] template lookup on
    # every carried item -- container-branch resolution in do_open et al.
    # (movement.py) now probes the player's inventory before falling back
    # to door lookup, so the fake test key needs a real template. [PRIMESUD test]
    ITEM_DEFS._data[KEY_VNUM] = {
        "keywords": "key test", "short_descr": "a test key",
        "type": "key", "wear_flags": {"take": True}, "level": 0, "weight": 1,
    }
    ITEM_DEFS._data[CHEST_VNUM] = {
        "keywords": "chest wooden", "short_descr": "a wooden chest",
        "type": "container", "wear_flags": {}, "level": 0, "weight": 50,
        "container_flags": {"closeable": True, "closed": True},
        "container_key": KEY_VNUM,
    }

    door = {"to": 3002, "isdoor": True, "closed": True, "key": KEY_VNUM}
    rev_door = {"to": 3001, "isdoor": True, "closed": True, "key": KEY_VNUM}
    chest = {"vnum": CHEST_VNUM}
    r1 = {"name": "Here", "desc": "x", "exits": {"n": door}, "items": [chest],
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
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


def _door(vnum=3001, d="n"):
    return ROOM_DEFS[vnum]["exits"][d]


def _chest():
    return world.rooms[3001]["items"][0]


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


class TestContainer:
    """Container branches of do_open/do_close/do_lock/do_unlock (cf. 1stMud
    act_move.c ITEM_CONTAINER branches). [PRIMESUD test]
    """

    def test_open_closed_container(self, scene, out):
        movement.do_open(scene, ["chest"])
        # cf. set_item_container_flag/RemBit -- disabled flags are deleted,
        # not set to a literal False (same convention as extra_flags).
        assert not _chest()["container_flags"].get("closed")
        assert any("You open a wooden chest." in l for l in out)

    def test_open_already_open_container(self, scene, out):
        _chest()["container_flags"] = {"closeable": True, "closed": False}
        movement.do_open(scene, ["chest"])
        assert "It's already open." in out

    def test_open_non_closeable_container(self, scene, out):
        _chest()["container_flags"] = {"closed": True}
        movement.do_open(scene, ["chest"])
        assert "You can't do that." in out

    def test_open_locked_container(self, scene, out):
        _chest()["container_flags"] = {
            "closeable": True, "closed": True, "locked": True}
        movement.do_open(scene, ["chest"])
        assert "It's locked." in out
        assert _chest()["container_flags"]["closed"] is True

    def test_close_open_container(self, scene, out):
        _chest()["container_flags"] = {"closeable": True, "closed": False}
        movement.do_close(scene, ["chest"])
        assert _chest()["container_flags"]["closed"] is True
        assert any("You close a wooden chest." in l for l in out)

    def test_close_already_closed_container(self, scene, out):
        movement.do_close(scene, ["chest"])  # template starts closed
        assert "It's already closed." in out

    def test_close_non_closeable_container(self, scene, out):
        _chest()["container_flags"] = {"closed": False}
        movement.do_close(scene, ["chest"])
        assert "You can't do that." in out

    def test_lock_container_with_key(self, scene, out):
        movement.do_lock(scene, ["chest"])  # template starts closed, unlocked
        assert _chest()["container_flags"]["locked"] is True
        assert any("You lock a wooden chest." in l for l in out)
        assert "*Click*" not in out  # [PRIMESUD] no Click for containers

    def test_lock_container_without_key(self, scene, out):
        scene["inv"] = []
        movement.do_lock(scene, ["chest"])
        assert not _chest().get("container_flags", {}).get("locked")
        assert "You lack the key." in out

    def test_lock_open_container(self, scene, out):
        _chest()["container_flags"] = {"closeable": True, "closed": False}
        movement.do_lock(scene, ["chest"])
        assert "It's not closed." in out

    def test_lock_keyless_container(self, scene, out):
        del ITEM_DEFS._data[CHEST_VNUM]["container_key"]
        movement.do_lock(scene, ["chest"])
        assert "It can't be locked." in out

    def test_lock_already_locked_container(self, scene, out):
        _chest()["container_flags"] = {
            "closeable": True, "closed": True, "locked": True}
        movement.do_lock(scene, ["chest"])
        assert "It's already locked." in out

    def test_unlock_container_with_key(self, scene, out):
        _chest()["container_flags"] = {
            "closeable": True, "closed": True, "locked": True}
        movement.do_unlock(scene, ["chest"])
        assert not _chest()["container_flags"].get("locked")
        assert any("You unlock a wooden chest." in l for l in out)
        assert "*Click*" not in out  # [PRIMESUD] no Click for containers

    def test_unlock_already_unlocked_container(self, scene, out):
        movement.do_unlock(scene, ["chest"])  # template starts unlocked
        assert "It's already unlocked." in out

    def test_lock_reports_not_a_container_for_non_container_obj(self, scene, out):
        # KEY_VNUM item is carried, not a container -- exercises the
        # "not ITEM_CONTAINER" branch shared by open/close/lock/unlock.
        movement.do_lock(scene, ["key"])
        assert "That's not a container." in out

    def test_open_plain_vnum_container(self, scene, out):
        # Reset-spawned items are plain vnum ints (see item.promote_obj) --
        # flag mutation must promote to an instance dict, not TypeError.
        world.rooms[3001]["items"][0] = CHEST_VNUM
        movement.do_open(scene, ["chest"])
        chest = _chest()
        assert isinstance(chest, dict)  # promoted in place
        assert not chest["container_flags"].get("closed")
        assert any("You open a wooden chest." in l for l in out)

    def test_look_in_closed_container_blocked(self, scene, out):
        # cf. 1stMud do_look 'in' CONT_CLOSED check, act_info.c:1225
        import info
        _chest()["contents"] = [{"vnum": KEY_VNUM}]
        info._look_in(scene, ["chest"])
        assert "It is closed." in out
        assert not any("holds:" in l for l in out)

    def test_look_in_open_container_shows_contents(self, scene, out):
        import info
        _chest()["container_flags"] = {"closeable": True}
        _chest()["contents"] = [{"vnum": KEY_VNUM}]
        info._look_in(scene, ["chest"])
        assert any("holds:" in l for l in out)


class TestContainerSaveToken:
    """container_flags and instance type survive save-token round trip.
    [PRIMESUD test]"""

    def test_container_flags_round_trip(self, scene):
        from item import serialize_item_token, parse_item_token
        obj = {"vnum": CHEST_VNUM,
               "container_flags": {"closeable": True, "locked": True}}
        loaded = parse_item_token(serialize_item_token(obj))
        assert loaded["container_flags"] == {"closeable": True, "locked": True}

    def test_empty_container_flags_round_trip(self, scene):
        # opened chest whose instance flags dropped every bit must still
        # override a closed template after reload
        from item import serialize_item_token, parse_item_token
        obj = {"vnum": CHEST_VNUM, "container_flags": {}}
        loaded = parse_item_token(serialize_item_token(obj))
        assert loaded["container_flags"] == {}

    def test_instance_type_round_trip(self, scene):
        from item import serialize_item_token, parse_item_token
        obj = {"vnum": CHEST_VNUM, "type": "trash", "poisoned": True}
        loaded = parse_item_token(serialize_item_token(obj))
        assert loaded["type"] == "trash"
        assert loaded["poisoned"] is True
